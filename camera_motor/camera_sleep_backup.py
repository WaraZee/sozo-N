#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Raspberry Pi 4 / Debian Bullseye / OV5647: real-time eye closure test.

Based on camera_ear_compare.py settings that worked on the user's Pi:
- Picamera2, 640x480, RGB888 (the returned array is OpenCV BGR order)
- MediaPipe FaceMesh, refine_landmarks=True, FULL 640x480 inference
- 2D EAR using six points around each eye

Usage (activate the existing camera-env first):
  python camera_sleep.py --test
  python camera_sleep.py --face-only --headless --duration 20 --snapshot
  python camera_sleep.py --headless --duration 30 --snapshot
  python camera_sleep.py                 # Pi desktop only, q to close

Stop VLC/libcamera-vid before running. No GPIO motor or bell is controlled.
"""

import argparse
import csv
import datetime as dt
import math
import statistics
import sys
import time
from collections import deque
from pathlib import Path

WIDTH, HEIGHT = 640, 480
CAMERA_FPS = 10              # Same initial target FPS as camera_ear_compare.py
EAR_CLOSED = 0.20            # Preliminary values: calibrate with measured CSV
EAR_OPEN = 0.25
DROWSY_SECONDS = 0.8
ALERT_SECONDS = 3.0
SMOOTH_FRAMES = 3            # Median of last 3 frames; excludes isolated spikes
UNKNOWN_GRACE = 0.4         # Hold prior evidence <= 0.4 s; do not count blind time
MAX_FRAME_GAP = 0.8         # Long stalled frame should not count as continued closure
REPORT_EVERY = 5.0
SNAPSHOT_EVERY = 1.0

LEFT_EYE = (362, 385, 387, 263, 373, 380)
RIGHT_EYE = (33, 160, 158, 133, 153, 144)
CSV_COLUMNS = (
    "datetime", "state", "face_detected", "eye_state",
    "left_EAR", "right_EAR", "avg_EAR", "smoothed_EAR",
    "closed_seconds", "alert_trigger",
)


def eye_aspect_ratio(landmarks, indices, width, height):
    """Calculate 2D EAR exactly as in camera_ear_compare.py."""
    pts = [(landmarks[i].x * width, landmarks[i].y * height) for i in indices]
    horiz = math.dist(pts[0], pts[3])
    if horiz < 1e-6:
        return None, pts
    vertical = math.dist(pts[1], pts[5]) + math.dist(pts[2], pts[4])
    return vertical / (2.0 * horiz), pts


class EyeSmoother:
    """Median filter for the mean of the two eyes; drop stale data after loss."""

    def __init__(self, window=SMOOTH_FRAMES):
        self.values = deque(maxlen=window)
        self.last_valid_time = None

    def push(self, ear_value, now):
        if ear_value is None:
            # Do not put '0' into history: missing eyes are NOT closed eyes.
            if self.last_valid_time is not None and now - self.last_valid_time > UNKNOWN_GRACE:
                self.values.clear()
            return None
        if self.last_valid_time is not None and now - self.last_valid_time > UNKNOWN_GRACE:
            self.values.clear()
        self.values.append(ear_value)
        self.last_valid_time = now
        return statistics.median(self.values)


class ClosedEyeTracker:
    """Count observed closed-eye time; bridge tiny unknown intervals without credit."""

    def __init__(self):
        self.closed_seconds = 0.0
        self.last_closed_time = None
        self.unknown_since = None
        self.alert_latched = False

    def reset(self):
        self.closed_seconds = 0.0
        self.last_closed_time = None
        self.unknown_since = None
        self.alert_latched = False

    def update(self, eye_state, now):
        if eye_state == "open":
            self.reset()
            return self.closed_seconds

        if eye_state == "closed":
            if self.last_closed_time is None:
                self.closed_seconds = 0.0
                self.alert_latched = False
            elif self.unknown_since is not None:
                # Recovered after a short unknown interval: keep accumulated
                # evidence, but DO NOT include the unknown interval in the timer.
                if now - self.unknown_since > UNKNOWN_GRACE:
                    self.closed_seconds = 0.0
                    self.alert_latched = False
            else:
                dt_frame = now - self.last_closed_time
                if 0 <= dt_frame <= MAX_FRAME_GAP:
                    self.closed_seconds += dt_frame
                else:
                    self.closed_seconds = 0.0
                    self.alert_latched = False
            self.last_closed_time = now
            self.unknown_since = None
            return self.closed_seconds

        # For "uncertain" or "no_face": neither a positive nor negative
        # closure observation; pause timer and forget only after grace window.
        if self.last_closed_time is not None:
            if self.unknown_since is None:
                self.unknown_since = now
            elif now - self.unknown_since > UNKNOWN_GRACE:
                self.reset()
        return self.closed_seconds


def state_for(eye_state, seconds):
    if eye_state == "no_face":
        return "NO_FACE"
    if eye_state == "uncertain":
        return "UNCERTAIN"
    if eye_state == "open":
        return "AWAKE"
    if eye_state == "closed":
        if seconds >= ALERT_SECONDS:
            return "POSSIBLE_SLEEP"
        if seconds >= DROWSY_SECONDS:
            return "DROWSY"
        return "BRIEF_CLOSURE"
    return "UNKNOWN"


def write_csv_row(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def create_mesh():
    try:
        import mediapipe as mp
    except ImportError as exc:
        raise RuntimeError(
            "MediaPipe is unavailable. Run: source ~/camera-env/bin/activate"
        ) from exc
    if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "face_mesh"):
        raise RuntimeError("This program requires MediaPipe FaceMesh (tested with 0.10.14).")
    return mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,                 # Same as successful EAR comparison
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )


def face_detector(cv2):
    path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(path)
    if detector.empty():
        raise RuntimeError("OpenCV cascade missing: " + path)
    return detector


def annotate_face(cv2, frame, landmarks, points_per_eye):
    # Draw the six EAR measurement points, not a full eyelid outline.
    for pts in points_per_eye:
        for px, py in pts:
            cv2.circle(frame, (int(px), int(py)), 2, (0, 255, 255), -1)
    xs = [p.x for p in landmarks]
    ys = [p.y for p in landmarks]
    x1 = max(0, int(min(xs) * WIDTH))
    y1 = max(0, int(min(ys) * HEIGHT))
    x2 = min(WIDTH - 1, int(max(xs) * WIDTH))
    y2 = min(HEIGHT - 1, int(max(ys) * HEIGHT))
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 225, 0), 2)


def self_test():
    # Tests no camera or third-party modules; safe on Windows/CI too.
    import types
    points = [types.SimpleNamespace(x=x / 640, y=y / 480) for x, y in
              [(20, 50), (24, 45), (34, 45), (40, 50), (34, 55), (24, 55)]]
    ear, _ = eye_aspect_ratio(points, range(6), 640, 480)
    assert abs(ear - 0.5) < 1e-10, ear
    filt = EyeSmoother()
    assert filt.push(0.30, 0.0) == 0.30
    filt.push(0.30, 0.1)
    assert filt.push(0.05, 0.2) == 0.30, "Median should reject one low spike"
    assert filt.push(0.04, 0.3) == 0.05, "Sustained closure should be detected"
    assert filt.push(None, 1.0) is None
    assert filt.push(0.33, 1.1) == 0.33, "Stale EAR must be cleared"
    clock = ClosedEyeTracker()
    clock.update("closed", 1.0)
    clock.update("closed", 1.2)
    assert abs(clock.closed_seconds - 0.2) < 1e-9
    clock.update("uncertain", 1.3)
    clock.update("closed", 1.5)
    assert abs(clock.closed_seconds - 0.2) < 1e-9, "Unknown time must not count"
    clock.update("closed", 1.7)
    assert abs(clock.closed_seconds - 0.4) < 1e-9
    clock.update("open", 1.8)
    assert clock.closed_seconds == 0
    assert state_for("closed", 3.1) == "POSSIBLE_SLEEP"
    print("SELF TEST OK: EAR, median filter, closure timer, state transitions")


def run(args):
    if args.self_test:
        self_test()
        return 0

    try:
        import cv2
        from picamera2 import Picamera2
    except ImportError as exc:
        raise RuntimeError("Please check OpenCV and Picamera2 in the camera-env environment") from exc

    mesh = None
    detector = None
    if not args.test:
        if args.face_only:
            detector = face_detector(cv2)
            print("FACE ONLY: Haar face detection (no EAR/sleep classification)")
        else:
            mesh = create_mesh()
            print("EAR MODE: FaceMesh 640x480 refine_landmarks=True; 2D EAR median filter")

    camera = Picamera2()
    camera_started = False
    window_created = False
    smoother = EyeSmoother()
    tracker = ClosedEyeTracker()
    last_state = None
    last_log_at = None
    last_snapshot_at = None

    try:
        config = camera.create_video_configuration(
            main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
            controls={"FrameRate": CAMERA_FPS},
        )
        camera.configure(config)
        camera.start()
        camera_started = True
        time.sleep(1)

        if args.test:
            frame = camera.capture_array("main")
            path = Path("test_picamera2.jpg")
            if frame is None or not cv2.imwrite(str(path), frame):
                raise RuntimeError("Could not save test photo")
            print("CAMERA TEST OK:", path.resolve())
            return 0

        if not args.headless:
            cv2.namedWindow("EAR sleep test", cv2.WINDOW_NORMAL)
            window_created = True

        started_at = time.monotonic()
        print("Started. Ctrl+C to stop; q when using a Pi desktop window.")
        print("NOTE: Alert is text-only. No GPIO/bell/motor is driven.")
        while True:
            if args.duration and time.monotonic() - started_at >= args.duration:
                break
            # Picamera2 'RGB888' gives a BGR array for OpenCV on this setup.
            frame = camera.capture_array("main")
            if frame is None:
                raise RuntimeError("Failed to capture a camera frame")
            now = time.monotonic()
            timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
            found = False
            left = right = avg = smooth = None
            eye_state = "no_face"

            if detector is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = detector.detectMultiScale(
                    gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
                found = len(faces) > 0
                for x, y, w, h in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 225, 0), 2)
            else:
                # FULL resolution, matching camera_ear_compare.py; no resize.
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = mesh.process(rgb)
                if result.multi_face_landmarks:
                    found = True
                    landmarks = result.multi_face_landmarks[0].landmark
                    left, lpts = eye_aspect_ratio(landmarks, LEFT_EYE, WIDTH, HEIGHT)
                    right, rpts = eye_aspect_ratio(landmarks, RIGHT_EYE, WIDTH, HEIGHT)
                    annotate_face(cv2, frame, landmarks, (lpts, rpts))
                    if left is not None and right is not None:
                        avg = (left + right) / 2.0
                        smooth = smoother.push(avg, now)
                        if smooth <= EAR_CLOSED:
                            eye_state = "closed"
                        elif smooth >= EAR_OPEN:
                            eye_state = "open"
                        else:
                            eye_state = "uncertain"
                    else:
                        eye_state = "uncertain"
                        smoother.push(None, now)
                else:
                    smoother.push(None, now)

            if args.face_only:
                tracker.reset()
                state = "FACE_FOUND_EYES_UNKNOWN" if found else "NO_FACE"
                seconds = 0.0
            else:
                seconds = tracker.update(eye_state, now)
                state = state_for(eye_state, seconds)

            alert_now = state == "POSSIBLE_SLEEP" and not tracker.alert_latched
            if alert_now:
                tracker.alert_latched = True
                print("ALERT: 3秒相当の確認済み閉眼を検知（ベルはまだ鳴らしません）")

            ear_text = (f"EAR L:{left:.3f} R:{right:.3f} Avg:{avg:.3f} Med:{smooth:.3f}"
                        if smooth is not None else "EAR --")
            color = ((0, 0, 255) if state == "POSSIBLE_SLEEP" else
                     (0, 165, 255) if state == "DROWSY" else (0, 225, 0))
            cv2.putText(frame, state, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.72, color, 2, cv2.LINE_AA)
            cv2.putText(frame, ear_text, (12, 55), cv2.FONT_HERSHEY_SIMPLEX,
                        0.47, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, f"Observed closed: {seconds:.1f}s", (12, 78),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.54, (255, 255, 255), 1, cv2.LINE_AA)

            due = state != last_state or last_log_at is None or now - last_log_at >= REPORT_EVERY
            if due:
                row = dict(
                    datetime=timestamp,
                    state=state,
                    face_detected=int(found),
                    eye_state=("face_only" if args.face_only else eye_state),
                    left_EAR=(f"{left:.4f}" if left is not None else ""),
                    right_EAR=(f"{right:.4f}" if right is not None else ""),
                    avg_EAR=(f"{avg:.4f}" if avg is not None else ""),
                    smoothed_EAR=(f"{smooth:.4f}" if smooth is not None else ""),
                    closed_seconds=f"{seconds:.2f}",
                    alert_trigger=int(alert_now),
                )
                write_csv_row(args.log, row)
                print(f"{timestamp} {state}  {ear_text}  closed={seconds:.1f}s", flush=True)
                last_log_at = now
                last_state = state

            if args.snapshot and (last_snapshot_at is None or now-last_snapshot_at >= SNAPSHOT_EVERY):
                if not cv2.imwrite("annotated_latest.jpg", frame):
                    print("WARNING: could not save annotated_latest.jpg", file=sys.stderr)
                last_snapshot_at = now

            if window_created:
                cv2.imshow("EAR sleep test", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        print("\nCtrl+C: stopped")
    finally:
        if mesh is not None:
            mesh.close()
        if camera_started:
            camera.stop()
        camera.close()
        if window_created:
            cv2.destroyAllWindows()
        if not args.test:
            print("CSV:", Path(args.log).resolve())
            if args.snapshot:
                print("Snapshot:", Path("annotated_latest.jpg").resolve())
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Raspberry Pi FaceMesh EAR drowsiness prototype")
    parser.add_argument("--test", action="store_true", help="Take one camera photo and exit")
    parser.add_argument("--self-test", action="store_true", help="Test processing logic without camera")
    parser.add_argument("--face-only", action="store_true", help="OpenCV face-only test")
    parser.add_argument("--headless", action="store_true", help="Run without local GUI (SSH)")
    parser.add_argument("--duration", type=float, default=0, help="Seconds to run (0 = until Ctrl+C)")
    parser.add_argument("--snapshot", action="store_true", help="Save annotated_latest.jpg every ~1 s")
    parser.add_argument("--log", default="sleep_detection_log_v2.csv", help="CSV output path")
    args = parser.parse_args()
    if args.duration < 0:
        parser.error("--duration must be >= 0")
    return args


if __name__ == "__main__":
    try:
        sys.exit(run(parse_args()))
    except (RuntimeError, OSError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(1)

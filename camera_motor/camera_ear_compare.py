#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Raspberry Pi 4 + Picamera2 + MediaPipe FaceMesh: 2D/3D EAR measurement.

Run from the camera-env virtual environment after stopping libcamera-vid:
    python camera_ear_compare.py --label open --seconds 12
    python camera_ear_compare.py --label closed --seconds 8

Produces ear_open.csv / ear_closed.csv and corresponding annotated jpg files
in the current working directory. No Bell, sleep or alarm judgments.
"""

import argparse
import csv
import datetime as dt
import math
import statistics
import sys
import time
from pathlib import Path

EYES = {
    'left': (362, 385, 387, 263, 373, 380),
    'right': (33, 160, 158, 133, 153, 144),
}


def calculate_ear(landmarks, eye_indices, width, height, three_d=False):
    """Return eye aspect ratio and 2D eye positions for annotation."""
    points_2d = [(landmarks[i].x * width, landmarks[i].y * height)
                 for i in eye_indices]
    if three_d:
        # MediaPipe's relative z scale is approximately the scale of x.
        # This is NOT a metric, calibrated 3D reconstruction.
        points = [(landmarks[i].x * width,
                   landmarks[i].y * height,
                   landmarks[i].z * width) for i in eye_indices]
    else:
        points = points_2d
    horizontal = math.dist(points[0], points[3])
    if horizontal < 1e-6:
        return None, points_2d
    vertical = math.dist(points[1], points[5]) + math.dist(points[2], points[4])
    return vertical / (2.0 * horizontal), points_2d


def print_summary(rows, label):
    valid = [r for r in rows if r['avg_ear_2d'] is not None]
    print(f'\n--- {label} test ---')
    print(f'Captured: {len(rows)} frames; face detected: {len(valid)} frames')
    if not valid:
        print('No eye landmarks: check face position, camera angle and light.')
        return
    for key in ('avg_ear_2d', 'avg_ear_3d'):
        values = sorted(r[key] for r in valid)
        print(f'{key}: min={values[0]:.3f}, median={statistics.median(values):.3f}, '
              f'max={values[-1]:.3f}')
    if label == 'open':
        incorrect = sum(r['avg_ear_2d'] <= 0.20 for r in valid)
        print(f'Open-eye frames wrongly below old 2D threshold 0.20: '
              f'{incorrect}/{len(valid)}')
    print('3D EAR is exploratory; do not reuse the 2D threshold for 3D.')


def main():
    parser = argparse.ArgumentParser(description='Measure 2D and 3D eye aspect ratios')
    parser.add_argument('--label', choices=('open', 'closed'), required=True,
                        help='Ground truth: keep BOTH eyes in this state for the recording')
    parser.add_argument('--seconds', type=float, default=10)
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error('--seconds must be greater than zero')

    import cv2
    import mediapipe as mp
    from picamera2 import Picamera2

    csv_path = Path(f'ear_{args.label}.csv')
    jpg_path = Path(f'ear_{args.label}_preview.jpg')
    camera = Picamera2()
    mesh = None
    rows = []
    last_annotated = None
    try:
        config = camera.create_video_configuration(
            main={'size': (640, 480), 'format': 'RGB888'},
            controls={'FrameRate': 10},
        )
        camera.configure(config)
        camera.start()
        time.sleep(1)
        mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False, max_num_faces=1,
            refine_landmarks=True, min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        print(f'Please keep BOTH eyes {args.label} for {args.seconds:g} seconds.')
        print('Stop VLC/libcamera-vid before recording. Ctrl+C ends early.')
        start = time.monotonic()
        last_print = -1
        while time.monotonic() - start < args.seconds:
            frame_bgr = camera.capture_array('main')
            if frame_bgr is None:
                continue
            height, width = frame_bgr.shape[:2]
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            detected = mesh.process(rgb).multi_face_landmarks
            entry = {'timestamp': dt.datetime.now().astimezone().isoformat(timespec='milliseconds'),
                     'label': args.label, 'face_found': int(bool(detected)),
                     'left_ear_2d': None, 'right_ear_2d': None,
                     'avg_ear_2d': None, 'left_ear_3d': None,
                     'right_ear_3d': None, 'avg_ear_3d': None}
            if detected:
                lm = detected[0].landmark
                for side, indices in EYES.items():
                    e2, pts = calculate_ear(lm, indices, width, height, False)
                    e3, _ = calculate_ear(lm, indices, width, height, True)
                    entry[f'{side}_ear_2d'] = e2
                    entry[f'{side}_ear_3d'] = e3
                    # Draw six landmarks, not an anatomical eyelid outline.
                    for px, py in pts:
                        cv2.circle(frame_bgr, (int(px), int(py)), 2, (0, 255, 255), -1)
                for suffix in ('2d', '3d'):
                    left = entry[f'left_ear_{suffix}']
                    right = entry[f'right_ear_{suffix}']
                    if left is not None and right is not None:
                        entry[f'avg_ear_{suffix}'] = (left + right) / 2
            rows.append(entry)
            text = ('2D: %.3f   3D: %.3f' %
                    (entry['avg_ear_2d'], entry['avg_ear_3d'])
                    if entry['avg_ear_2d'] is not None else 'NO FACE')
            cv2.putText(frame_bgr, text, (12, 32), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (255, 255, 255), 2)
            cv2.putText(frame_bgr, f'TEST: {args.label.upper()}', (12, 62),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            last_annotated = frame_bgr
            seconds = int(time.monotonic() - start)
            if seconds != last_print:
                print(f'{seconds:2d}s  {text}')
                last_print = seconds
    except KeyboardInterrupt:
        print('Recording interrupted.')
    finally:
        if mesh is not None:
            mesh.close()
        camera.stop()
        camera.close()

    if not rows:
        print('No frames collected.', file=sys.stderr)
        return 1
    with csv_path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    if last_annotated is not None:
        import cv2
        if not cv2.imwrite(str(jpg_path), last_annotated):
            print(f'WARNING: could not save {jpg_path}', file=sys.stderr)
    print_summary(rows, args.label)
    print(f'CSV: {csv_path.resolve()}')
    print(f'Image: {jpg_path.resolve()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

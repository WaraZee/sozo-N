#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Raspberry Pi 4 / Bullseye / OV5647 目の開閉・居眠り判定の試作。

動作確認:
  python3 camera_sleep.py --test
  python3 camera_sleep.py --face-only --headless --duration 20
  python3 camera_sleep.py --headless --duration 30 --snapshot

通常の目判定には MediaPipe 0.10.14 の旧 FaceMesh API が必要。
--face-only の場合は OpenCV の顔検出だけ行い、目や居眠りは判定しない。
ベルのGPIO/モータ駆動は未実装。閉眼3秒時には ALERT を一度出力する。
"""

import argparse
import csv
import datetime
import sys
import time
from pathlib import Path

WIDTH, HEIGHT = 640, 480
FPS = 15
CLOSED_EAR = 0.20          # 仮値。実測で調整する
OPEN_EAR = 0.25            # 仮値。実測で調整する
DROWSY_SECONDS = 0.8
ALERT_SECONDS = 3.0        # 試験用。実際の仕様に合わせて変更
REPORT_INTERVAL = 5.0

# 6点: 左端→上側2点→右端→下側2点
LEFT_EYE = (362, 385, 387, 263, 373, 380)
RIGHT_EYE = (33, 160, 158, 133, 153, 144)
CSV_COLUMNS = ("datetime", "state", "face_detected", "eye_state", "left_EAR",
               "right_EAR", "closed_seconds", "alert_trigger")


def ear(landmarks, indices, image_w, image_h):
    """MediaPipe正規化ランドマークからEARを計算する。"""
    points = [(landmarks[i].x * image_w, landmarks[i].y * image_h) for i in indices]

    def distance(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    horizontal = distance(points[0], points[3])
    if horizontal < 1e-6:
        return None
    return (distance(points[1], points[5]) + distance(points[2], points[4])) / (2 * horizontal)


def load_camera_and_cv2():
    try:
        import cv2
        from picamera2 import Picamera2
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV/Picamera2 を読み込めません。"
            " sudo apt install python3-opencv python3-picamera2 を確認してください。"
        ) from exc
    return cv2, Picamera2


def create_mesh():
    try:
        import mediapipe as mp
    except ImportError as exc:
        raise RuntimeError(
            "MediaPipe が未導入です。先に --face-only で試すか、"
            "互換版 mediapipe==0.10.14 を仮想環境に導入してください。"
        ) from exc
    if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "face_mesh"):
        raise RuntimeError(
            f"MediaPipe {getattr(mp, '__version__', 'unknown')} は mp.solutions.face_mesh "
            "を提供していません。互換版 0.10.14 を使ってください。"
        )
    return mp.solutions.face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )


def create_haar_detector(cv2):
    model = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(model)
    if detector.empty():
        raise RuntimeError("OpenCV顔検出モデルが見つかりません: " + model)
    return detector


def write_csv(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if needs_header:
            writer.writeheader()
        writer.writerow(values)


def main():
    parser = argparse.ArgumentParser(description="Picamera2 + MediaPipe EAR 居眠り判定")
    parser.add_argument("--test", action="store_true", help="Picamera2で写真を1枚保存して終了")
    parser.add_argument("--face-only", action="store_true", help="MediaPipeなしで顔検出だけ試験")
    parser.add_argument("--headless", action="store_true", help="SSH用（画面を表示しない）")
    parser.add_argument("--duration", type=float, default=0, help="動作秒数。0ならCtrl+Cまで実行")
    parser.add_argument("--snapshot", action="store_true", help="annotated_latest.jpgを定期保存")
    parser.add_argument("--log", default="sleep_detection_log.csv", help="CSV記録の保存場所")
    args = parser.parse_args()
    if args.duration < 0:
        parser.error("--duration は0以上にしてください")

    cv2, Picamera2 = load_camera_and_cv2()
    mesh = None
    detector = None
    if not args.test:
        if args.face_only:
            detector = create_haar_detector(cv2)
            print("FACE ONLY: 顔検出テスト（目/居眠り判定は行いません）")
        else:
            mesh = create_mesh()
            print("EAR MODE: MediaPipeによる目の開閉判定")

    camera = Picamera2()
    camera_started = False
    window_open = False
    try:
        config = camera.create_video_configuration(
            main={"size": (WIDTH, HEIGHT), "format": "RGB888"},
            controls={"FrameRate": FPS},
        )
        camera.configure(config)
        camera.start()
        camera_started = True
        time.sleep(1)

        if args.test:
            photo = camera.capture_array("main")
            filename = "test_picamera2.jpg"
            if not cv2.imwrite(filename, photo):
                raise RuntimeError("写真を保存できません: " + filename)
            print("CAMERA TEST OK: " + str(Path(filename).resolve()))
            return

        if not args.headless:
            cv2.namedWindow("Camera eye test", cv2.WINDOW_NORMAL)
            window_open = True

        started_at = time.monotonic()
        previous_state = None
        last_report = 0.0
        closed_since = None
        alert_sent = False
        print("動作中: Ctrl+Cで終了。--headless省略時はプレビュー画面で q も可")

        while True:
            now = time.monotonic()
            if args.duration and now - started_at >= args.duration:
                break
            # RGB888はPicamera2の配列上ではBGR順。OpenCV用の再変換は不要。
            frame = camera.capture_array("main")
            if frame is None:
                raise RuntimeError("カメラからフレームを取得できません")
            face_found = False
            eye_state = "unknown"
            left_ear = None
            right_ear = None

            if detector is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = detector.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5,
                                                  minSize=(60, 60))
                face_found = len(faces) > 0
                for x, y, w, h in faces:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 220, 0), 2)
            else:
                # MediaPipeはRGB画像を受け付けるためBGRから変換する。
                small_bgr = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_AREA)
                result = mesh.process(cv2.cvtColor(small_bgr, cv2.COLOR_BGR2RGB))
                if result.multi_face_landmarks:
                    face_found = True
                    lm = result.multi_face_landmarks[0].landmark
                    left_ear = ear(lm, LEFT_EYE, 320, 240)
                    right_ear = ear(lm, RIGHT_EYE, 320, 240)
                    if left_ear is not None and right_ear is not None:
                        average = (left_ear + right_ear) / 2
                        if average <= CLOSED_EAR:
                            eye_state = "closed"
                        elif average >= OPEN_EAR:
                            eye_state = "open"
                        else:
                            eye_state = "uncertain"
                    x_values = [p.x for p in lm]
                    y_values = [p.y for p in lm]
                    x1 = max(0, int(min(x_values) * WIDTH))
                    y1 = max(0, int(min(y_values) * HEIGHT))
                    x2 = min(WIDTH - 1, int(max(x_values) * WIDTH))
                    y2 = min(HEIGHT - 1, int(max(y_values) * HEIGHT))
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)

            if eye_state == "closed":
                if closed_since is None:
                    closed_since = now
            else:
                # 顔が見つからない場合も「閉眼」とは扱わない。
                closed_since = None
                alert_sent = False
            closed_seconds = now - closed_since if closed_since is not None else 0.0

            if not face_found:
                state = "NO_FACE"
            elif args.face_only:
                state = "FACE_FOUND_EYES_UNKNOWN"
            elif eye_state == "open":
                state = "AWAKE"
            elif eye_state == "uncertain":
                state = "UNCERTAIN"
            elif eye_state == "closed" and closed_seconds >= ALERT_SECONDS:
                state = "POSSIBLE_SLEEP"
            elif eye_state == "closed" and closed_seconds >= DROWSY_SECONDS:
                state = "DROWSY"
            else:
                state = "BRIEF_CLOSURE"

            alert_now = state == "POSSIBLE_SLEEP" and not alert_sent
            if alert_now:
                alert_sent = True
                # ここが③ベルのトリガーを後から接続する位置。
                # モータの仕様とドライバ・配線が確定するまではGPIO操作しない。
                print("ALERT: 3秒の連続閉眼を検知（ベルの実駆動は未接続）")

            ear_label = (f"EAR L:{left_ear:.3f} R:{right_ear:.3f}"
                         if left_ear is not None and right_ear is not None else "EAR --")
            cv2.putText(frame, state, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.65, (0, 0, 255) if state == "POSSIBLE_SLEEP" else (0, 220, 0), 2)
            cv2.putText(frame, f"{ear_label} Closed:{closed_seconds:.1f}s", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

            due = state != previous_state or now - last_report >= REPORT_INTERVAL
            if due:
                timestamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
                row = {
                    "datetime": timestamp,
                    "state": state,
                    "face_detected": int(face_found),
                    "eye_state": eye_state,
                    "left_EAR": f"{left_ear:.4f}" if left_ear is not None else "",
                    "right_EAR": f"{right_ear:.4f}" if right_ear is not None else "",
                    "closed_seconds": f"{closed_seconds:.2f}",
                    "alert_trigger": int(alert_now),
                }
                write_csv(args.log, row)
                print(f"{timestamp} {state}  {ear_label}  closed={closed_seconds:.1f}s")
                if args.snapshot and not cv2.imwrite("annotated_latest.jpg", frame):
                    print("警告: annotated_latest.jpg を保存できません", file=sys.stderr)
                previous_state = state
                last_report = now

            if window_open:
                cv2.imshow("Camera eye test", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        print("Ctrl+C: 終了します")
    finally:
        if mesh is not None:
            mesh.close()
        if camera_started:
            camera.stop()
        camera.close()
        if window_open:
            cv2.destroyAllWindows()
        if not args.test:
            print("CSV記録:", str(Path(args.log).resolve()))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as exc:
        print("エラー:", exc, file=sys.stderr)
        sys.exit(1)

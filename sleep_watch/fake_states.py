"""検証用: カメラやバンドの代わりに、判定に使うファイルを書き続ける

本物のどちらか一方の代わりにも使える（心拍は下がるまで数分かかるので、その代わりなど）。
  python3 fake_states.py --heart sleepy            → 心拍が下がった、ことにする
  python3 fake_states.py --camera closed           → 目を閉じ続けている（秒数が増えていく）
  python3 fake_states.py --camera open --heart awake
Ctrl+C で止める。
"""
import argparse
import csv
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "heart"))
from heart_rate import write_state  # noqa: E402
from sleep_watch import CAMERA_LOG, HEART_FILE  # noqa: E402

CAMERA_COLUMNS = ["datetime", "state", "face_detected", "eye_state", "closed_seconds"]


def write_camera(path, eye_state, closed_seconds):
    new_file = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CAMERA_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow({"datetime": datetime.now().astimezone().isoformat(timespec="seconds"), "state": "FAKE",
                         "face_detected": 1, "eye_state": eye_state, "closed_seconds": "%.2f" % closed_seconds})


def main():
    parser = argparse.ArgumentParser(description="判定に使うファイルを偽物で書き続ける")
    parser.add_argument("--camera", choices=["open", "closed", "no_face"], help="目の状態")
    parser.add_argument("--heart", choices=["awake", "sleepy"], help="心拍の状態")
    parser.add_argument("--seconds", type=float, default=0, help="この秒数で止める（0 = Ctrl+C まで）")
    args = parser.parse_args()
    if not args.camera and not args.heart:
        parser.error("--camera か --heart を指定してください")

    start = time.time()
    try:
        while not args.seconds or time.time() - start < args.seconds:
            now = time.time()
            if args.camera:
                write_camera(CAMERA_LOG, args.camera, now - start if args.camera == "closed" else 0.0)
            if args.heart:
                write_state(HEART_FILE, {
                    "time": now, "bpm": 55 if args.heart == "sleepy" else 63,
                    "average": None, "baseline": 63.0, "state": args.heart,
                })
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

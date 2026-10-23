"""カメラとバンドの2つで居眠りを見張り、居眠りならスマホとバンドで起こす

先に別々に動かしておく（どちらも判定結果を /tmp のファイルに書く）:
  カメラ: source ~/camera-env/bin/activate && python camera_motor/camera_sleep.py --headless
  バンド: python3 heart/heart_rate.py 30
そのうえで:
  python3 sleep_watch/sleep_watch.py            → 居眠りならスマホの wake.sh を呼ぶ
  python3 sleep_watch/sleep_watch.py --dry-run  → 呼ばずに表示だけ（試し用）
"""
import argparse
import json
import subprocess
import time

from fusion import SleepFusion

CAMERA_FILE = "/tmp/maneki_camera.json"  # camera_sleep.py が書く
HEART_FILE = "/tmp/maneki_heart.json"    # heart_rate.py が書く
PHONE = "u0@10.27.74.140"  # スマホの Termux（IP は DHCP で変わることがある）
PHONE_PORT = 8022
CHECK_EVERY = 0.5   # 何秒ごとに見るか
REPORT_EVERY = 10   # 何秒ごとに今の様子を表示するか
HEART_NAMES = {"calibrating": "測定中", "awake": "ふつう", "sleepy": "下がった"}
EYE_NAMES = {"open": "目を開けている", "uncertain": "目がはっきりしない", "no_face": "顔が見えない"}


def read_state(path):
    """書き出された判定を読む。まだない・読めないときは None"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def phone(command, dry_run):
    print("  スマホ:", command)
    if dry_run:
        return
    try:
        subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                        "-p", str(PHONE_PORT), PHONE, command], timeout=30)
    except subprocess.TimeoutExpired:
        print("  スマホにつながりませんでした")


def describe(now, fusion, camera, heart):
    if fusion._fresh(camera, now):
        eyes = "目を閉じて%.1f秒" % camera["closed_seconds"] if camera["eye_state"] == "closed" \
            else EYE_NAMES.get(camera["eye_state"], camera["eye_state"])
    else:
        eyes = "カメラのデータなし"
    if fusion._fresh(heart, now):
        beat = "心拍 %s（%s）" % (heart.get("bpm"), HEART_NAMES.get(heart["state"], heart["state"]))
    else:
        beat = "バンドのデータなし"
    return "%s / %s" % (eyes, beat)


def main():
    parser = argparse.ArgumentParser(description="カメラとバンドで居眠りを見張る")
    parser.add_argument("--dry-run", action="store_true", help="スマホを鳴らさず表示だけ")
    args = parser.parse_args()

    fusion = SleepFusion()
    print("見張り開始: 目を%d秒閉じて、心拍も下がったら起こします（Ctrl+Cで終了）"
          % fusion.closed_seconds)
    next_report = 0
    try:
        while True:
            now = time.time()
            camera, heart = read_state(CAMERA_FILE), read_state(HEART_FILE)
            event = fusion.update(now, camera, heart)
            clock = time.strftime("%H:%M:%S")
            if event == "wake":
                print("%s  ★ 居眠り！ %s" % (clock, describe(now, fusion, camera, heart)))
                phone("~/maneki/wake.sh", args.dry_run)
            elif event == "stop":
                print("%s  ★ 起きた（目を開けた）" % clock)
                phone("~/maneki/stop.sh", args.dry_run)
            if now >= next_report:
                print("%s  %s%s" % (clock, describe(now, fusion, camera, heart),
                                    "  [鳴らし中]" if fusion.alarming else ""))
                next_report = now + REPORT_EVERY
            time.sleep(CHECK_EVERY)
    except KeyboardInterrupt:
        if fusion.alarming:
            phone("~/maneki/stop.sh", args.dry_run)


if __name__ == "__main__":
    main()

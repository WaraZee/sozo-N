"""カメラとバンドで居眠りを見張り、寝ていたらモーターとスマホ・バンドを鳴らす。スマホの通知を押すと止まる

先に別々に動かしておく:
  カメラ: source ~/camera-env/bin/activate
          python ~/sozo-N/camera_motor/camera_sleep.py --headless --flip --log /tmp/maneki_camera.csv
  バンド: python3 ~/sozo-N/heart/heart_rate.py 30
そのうえで:
  python3 sleep_watch.py            → 見張る（判定は judges.py）
  python3 sleep_watch.py --dry-run  → 鳴らさず表示だけ（試し用）
"""
import argparse
import json
import subprocess
import time

import phone_finder
from alarm import Alarm
from camera_log import camera_at, last_row
from judges import SleepJudge, is_fresh

CAMERA_LOG = "/tmp/maneki_camera.csv"  # camera_sleep.py の --log
HEART_FILE = "/tmp/maneki_heart.json"  # heart_rate.py が書く
PHONE_PORT = phone_finder.PHONE_PORT  # スマホの Termux の SSH（IP は起動時に phone_finder で探す）
PHONE_FLAG = "~/maneki/ringing"  # wake.sh が作り、通知を押すと stop.sh が消す
MOTOR_PORT = "A"
MOTOR_SPEED = 100
MIN_VOLTAGE = 7.2
CHECK_EVERY = 0.5   # 何秒ごとに見るか
REPORT_EVERY = 10   # 何秒ごとに今の様子を表示するか
HEART_NAMES = {"calibrating": "測定中", "awake": "ふつう", "sleepy": "下がった", "no_reading": "取れない"}
EYE_NAMES = {"open": "目を開けている", "uncertain": "目がはっきりしない", "no_face": "顔が見えない"}


class BuildHatMotor:
    def __init__(self):
        from buildhat import Hat, Motor
        vin = Hat().get_vin()
        print("Build HAT の電圧: %.1fV" % vin)
        if vin < MIN_VOLTAGE:
            raise SystemExit("電圧が低いので動かしません（電池を確認してください）")
        self.motor = Motor(MOTOR_PORT)

    def start(self):
        self.motor.start(MOTOR_SPEED)
        print("  モーター: 回転開始（速さ %d）" % MOTOR_SPEED)

    def stop(self):
        self.motor.stop()
        print("  モーター: 停止")


class Phone:
    def __init__(self, host):
        self.host = host  # "u0@10.27.74.56" など

    def _run(self, command, timeout=15):
        return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-p", str(PHONE_PORT),
                               self.host, command], capture_output=True, text=True, timeout=timeout)

    def _call(self, command, timeout=15):
        """最後まで終わったら True"""
        try:
            if self._run(command, timeout).returncode == 0:
                return True
            print("  スマホの %s に失敗しました" % command)
        except subprocess.TimeoutExpired:
            print("  スマホの %s が%d秒で終わりませんでした" % (command, timeout))
        return False

    def wake(self):
        # 前回の「鳴っている」印が残っていると wake.sh は何もしないので、先に片付ける
        # 2026-10-30 は15秒では終わらなかったので、長めに待つ
        return self._call("~/maneki/stop.sh; ~/maneki/wake.sh", timeout=40)

    def stop(self):
        self._call("~/maneki/stop.sh")

    def is_ringing(self):
        try:
            output = self._run("[ -f %s ] && echo ringing || echo stopped" % PHONE_FLAG).stdout
        except subprocess.TimeoutExpired:
            return None
        if "ringing" in output:
            return True
        return False if "stopped" in output else None


class DryRunMotor:
    def start(self):
        print("  （モーターを回すところ）")

    def stop(self):
        pass


class DryRunPhone:
    def wake(self):
        print("  （スマホを鳴らすところ）")
        return True

    def stop(self):
        print("  （スマホを止めるところ）")

    def is_ringing(self):
        return None


def read_heart():
    try:
        with open(HEART_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def describe(now, camera, heart):
    if camera is None:
        eyes = "カメラのデータなし"
    elif camera["eye_state"] == "closed":
        eyes = "目を閉じて%.1f秒" % camera["closed_seconds"]
    else:
        eyes = EYE_NAMES.get(camera["eye_state"], camera["eye_state"])
    if is_fresh(heart, now):
        beat = "心拍 %s（%s）" % (heart.get("bpm"), HEART_NAMES.get(heart["state"], heart["state"]))
    else:
        beat = "バンドのデータなし"
    return "%s / %s" % (eyes, beat)


def main():
    parser = argparse.ArgumentParser(description="カメラとバンドで居眠りを見張る")
    parser.add_argument("--dry-run", action="store_true", help="モーターもスマホも動かさず表示だけ")
    parser.add_argument("--phone", help="スマホの IP（指定しなければ自動で探す）")
    args = parser.parse_args()

    judge = SleepJudge()
    if args.dry_run:
        alarm = Alarm(DryRunMotor(), DryRunPhone())
    else:
        if args.phone:
            host = "%s@%s" % (phone_finder.PHONE_USER, args.phone)
        else:
            print("スマホを探しています…")
            host = phone_finder.locate()
            if host is None:
                raise SystemExit("スマホが見つかりません。スマホで Termux を開いて sshd を打ってください")
        print("スマホ:", host)
        alarm = Alarm(BuildHatMotor(), Phone(host))
    print("見張り開始: %s（Ctrl+Cで終了）" % judge.name)

    next_report = 0
    try:
        while True:
            now = time.time()
            camera = camera_at(last_row(CAMERA_LOG), now)
            heart = read_heart()
            event = alarm.update(now, judge.update(now, camera, heart))
            clock = time.strftime("%H:%M:%S")
            if event == "start":
                print("%s  ★ 寝ている！ %s" % (clock, describe(now, camera, heart)))
            elif event == "released":
                print("%s  ★ 通知が押されたので止めました" % clock)
            elif event == "timeout":
                print("%s  ★ %d秒たったので止めました" % (clock, alarm.max_seconds))
            if now >= next_report:
                print("%s  %s%s" % (clock, describe(now, camera, heart), "  [鳴らし中]" if alarm.ringing else ""))
                next_report = now + REPORT_EVERY
            time.sleep(CHECK_EVERY)
    except KeyboardInterrupt:
        pass
    finally:
        alarm.shutdown()


if __name__ == "__main__":
    main()

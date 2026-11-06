"""検証用: カメラと心拍の記録を4案の判定に通して、いつ鳴るかを比べる

使い方: python replay.py カメラ.csv 心拍.csv [--from 15:00] [--to 15:20]
  --from / --to で場面（勉強中、寝ている時など）の時間を指定する。
"""
import argparse
import bisect
import csv
from datetime import datetime

from camera_log import camera_at, load_rows, row_time
from judges import JUDGES


def load_heart(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [{"time": datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S").timestamp(),
                 "state": r["state"]} for r in csv.DictReader(f)]


def latest(items, times, t):
    i = bisect.bisect_right(times, t) - 1
    return items[i] if i >= 0 else None


def alarm_times(judge, camera_rows, heart_rows, start, end):
    """start〜end の間で「寝ている」に変わった時刻の一覧。判定は記録の最初から動かしておく"""
    camera_times = [row_time(r) for r in camera_rows]
    heart_times = [r["time"] for r in heart_rows]
    begin = int(min(camera_times[:1] + heart_times[:1] + [start]))
    found = []
    was_sleeping = False
    for t in range(begin, int(end) + 1):
        sleeping = judge.update(t, camera_at(latest(camera_rows, camera_times, t), t),
                                latest(heart_rows, heart_times, t))
        if sleeping and not was_sleeping and t >= start:
            found.append(t)
        was_sleeping = sleeping
    return found


def clock_on(day, text):
    """"15:00" や "15:00:30" を、day と同じ日の時刻にする"""
    parts = [int(p) for p in text.split(":")] + [0]
    return day.replace(hour=parts[0], minute=parts[1], second=parts[2], microsecond=0).timestamp()


def main():
    parser = argparse.ArgumentParser(description="記録を4案の判定に通して比べる")
    parser.add_argument("camera_log")
    parser.add_argument("heart_log")
    parser.add_argument("--from", dest="start", help="場面の始まり（例 15:00）")
    parser.add_argument("--to", dest="end", help="場面の終わり（例 15:20）")
    args = parser.parse_args()

    camera_rows = load_rows(args.camera_log)
    heart_rows = load_heart(args.heart_log)
    if not camera_rows or not heart_rows:
        raise SystemExit("記録が空です")
    first = row_time(camera_rows[0])
    last = max(row_time(camera_rows[-1]), heart_rows[-1]["time"])
    day = datetime.fromtimestamp(first)
    start = clock_on(day, args.start) if args.start else first
    end = clock_on(day, args.end) if args.end else last

    def clock(t):
        return datetime.fromtimestamp(t).strftime("%H:%M:%S")

    print("場面: %s 〜 %s（%.1f分）" % (clock(start), clock(end), (end - start) / 60))
    for key, judge_class in JUDGES.items():
        judge = judge_class()
        times = alarm_times(judge, camera_rows, heart_rows, start, end)
        if times:
            detail = "%d回 鳴る／最初は %d秒後（%s）" % (len(times), times[0] - start, clock(times[0]))
        else:
            detail = "鳴らない"
        print("  %s: %s" % (judge.name, detail))


if __name__ == "__main__":
    main()

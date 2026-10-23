"""heart_rate.py の記録（CSV）をグラフにして、居眠りラインの候補ごとの誤判定を数える

使い方: python plot_log.py logs/heart_20261023_144600.csv
        → 同じ名前の .png ができる
"""
import csv
import sys
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

matplotlib.rcParams["font.family"] = ["Yu Gothic", "MS Gothic", "sans-serif"]

BASELINE_SECONDS = 120   # sleep_judge.py と同じ：最初の2分が「起きている時の平均」
DROPS = [0.08, 0.10]     # 比べる居眠りラインの候補
WINDOWS = [30, 60]       # 比べる平均の長さ（秒）


def load(path):
    times, bpms = [], []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            times.append(datetime.strptime(row["time"], "%Y-%m-%d %H:%M:%S"))
            bpms.append(int(row["bpm"]))
    return times, bpms


def moving_average(times, bpms, window):
    out = []
    start = 0
    for i, t in enumerate(times):
        while (t - times[start]).total_seconds() > window:
            start += 1
        part = bpms[start:i + 1]
        out.append(sum(part) / len(part))
    return out


def seconds_below(times, values, line, skip_until):
    """line 以下だった合計秒数（最初の測定期間は除く）"""
    total = 0.0
    for i in range(1, len(times)):
        if times[i] > skip_until and values[i] <= line:
            total += (times[i] - times[i - 1]).total_seconds()
    return total


def main(path):
    times, bpms = load(path)
    t0 = times[0]
    calib = [b for t, b in zip(times, bpms) if (t - t0).total_seconds() < BASELINE_SECONDS]
    baseline = sum(calib) / len(calib)
    skip_until = times[len(calib) - 1]
    minutes = (times[-1] - skip_until).total_seconds() / 60

    print("記録: %s 〜 %s（%d件）" % (times[0].strftime("%H:%M"), times[-1].strftime("%H:%M"), len(bpms)))
    print("心拍数: 最小 %d / 最大 %d / 全体の平均 %.1f" % (min(bpms), max(bpms), sum(bpms) / len(bpms)))
    print("起きている時の平均（最初の%d秒）: %.1f" % (BASELINE_SECONDS, baseline))
    print("\n起きているのに「居眠り」と判定されてしまう時間（判定期間 %.0f 分のうち）:" % minutes)

    averages = {w: moving_average(times, bpms, w) for w in WINDOWS}
    for drop in DROPS:
        line = baseline * (1 - drop)
        for w in WINDOWS:
            s = seconds_below(times, averages[w], line, skip_until)
            print("  %d%%下（%.1f）・%d秒平均: %4.0f 秒" % (drop * 100, line, w, s))

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(times, bpms, color="#bbbbbb", lw=0.8, label="心拍数（届いた値）")
    for w, color in zip(WINDOWS, ["#1f77b4", "#d62728"]):
        ax.plot(times, averages[w], color=color, lw=1.8, label="%d秒平均" % w)
    ax.axhline(baseline, color="black", ls="-", lw=1, label="起きている時の平均 %.1f" % baseline)
    for drop, style in zip(DROPS, ["--", ":"]):
        line = baseline * (1 - drop)
        ax.axhline(line, color="black", ls=style, lw=1, label="%d%%下 %.1f" % (drop * 100, line))
    ax.axvspan(times[0], skip_until, color="#fff3c4", label="平均の測定（最初の2分）")
    ax.set_xlabel("時刻")
    ax.set_ylabel("心拍数（回/分）")
    ax.set_title("心拍数の記録 %s（起きて課題をしていた時）" % times[0].strftime("%Y/%m/%d"))
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))
    fig.tight_layout()
    out = path.rsplit(".", 1)[0] + ".png"
    fig.savefig(out, dpi=120)
    print("\nグラフ:", out)


if __name__ == "__main__":
    main(sys.argv[1])

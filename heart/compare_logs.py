"""「起きている時」と「寝るつもりの時」の記録を、開始からの経過時間でそろえて比べる

使い方: python compare_logs.py 起きている時.csv 寝るつもりの時.csv [出力.png]
居眠りラインは、起きている時の記録の最初2分の平均を基準に引く（sleep_judge.py と同じ）。
「出力_threshold.png」に、ラインを何%にすると何分で気づけるかのグラフも作る。
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from plot_log import BASELINE_SECONDS, DROPS, load, moving_average

matplotlib.rcParams["font.family"] = ["Yu Gothic", "MS Gothic", "sans-serif"]
WINDOW = 60  # 比べる平均の長さ（秒）


def first_crossing(minutes, values, line, after):
    """after 分より後で、初めて line 以下になった経過分"""
    for m, v in zip(minutes, values):
        if m > after and v <= line:
            return m
    return None


def main(awake_path, sleep_path, out):
    fig, ax = plt.subplots(figsize=(11, 5))
    baseline = None
    series = []
    for path, label, color in [(awake_path, "起きて課題をしていた時", "#1f77b4"),
                               (sleep_path, "寝るつもりで目を閉じた時", "#d62728")]:
        times, bpms = load(path)
        minutes = [(t - times[0]).total_seconds() / 60 for t in times]
        avg = moving_average(times, bpms, WINDOW)
        if baseline is None:
            calib = [b for m, b in zip(minutes, bpms) if m * 60 < BASELINE_SECONDS]
            baseline = sum(calib) / len(calib)
        ax.plot(minutes, bpms, color=color, lw=0.6, alpha=0.25)
        ax.plot(minutes, avg, color=color, lw=2, label="%s（%d秒平均）" % (label, WINDOW))
        series.append((label, minutes, avg))

    ax.axhline(baseline, color="black", lw=1, label="起きている時の平均 %.1f" % baseline)
    print("起きている時の平均（課題の最初2分）: %.1f" % baseline)
    for drop, style in zip(DROPS, ["--", ":"]):
        line = baseline * (1 - drop)
        ax.axhline(line, color="black", ls=style, lw=1, label="%d%%下 %.1f" % (drop * 100, line))
        for label, minutes, avg in series:
            m = first_crossing(minutes, avg, line, after=BASELINE_SECONDS / 60)
            print("  %d%%下（%.1f）: %s → %s" % (
                drop * 100, line, label, "%.1f分後に下回った" % m if m is not None else "一度も下回らない"))

    ax.set_xlabel("開始からの時間（分）")
    ax.set_ylabel("心拍数（回/分）")
    ax.set_title("起きている時と、寝るつもりの時の心拍数")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print("グラフ:", out)


def threshold_chart(awake_path, sleep_path, out, chosen=0.08):
    """ラインを何%にすると、寝るつもりの時に何分で気づけるか・起きている時に誤作動するか"""
    curves = []
    for path in (awake_path, sleep_path):
        times, bpms = load(path)
        minutes = [(t - times[0]).total_seconds() / 60 for t in times]
        curves.append((minutes, moving_average(times, bpms, WINDOW), bpms))
    (aw_m, aw_avg, aw_b), (sl_m, sl_avg, _) = curves
    calib = [b for m, b in zip(aw_m, aw_b) if m * 60 < BASELINE_SECONDS]
    baseline = sum(calib) / len(calib)
    after = BASELINE_SECONDS / 60
    awake_drop = (1 - min(v for m, v in zip(aw_m, aw_avg) if m > after) / baseline) * 100
    sleep_drop = (1 - min(v for m, v in zip(sl_m, sl_avg) if m > after) / baseline) * 100

    percents = [p / 2 for p in range(2, 41)]  # 1%〜20%
    detect = [first_crossing(sl_m, sl_avg, baseline * (1 - p / 100), after) for p in percents]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axvspan(0, awake_drop, color="#f8d0d0", label="起きているのに誤作動する範囲（〜%.1f%%）" % awake_drop)
    ax.axvspan(sleep_drop, 20.5, color="#dddddd", label="寝ても気づけない範囲（%.1f%%〜）" % sleep_drop)
    ok = [(p, d) for p, d in zip(percents, detect) if d is not None]
    ax.plot([p for p, _ in ok], [d for _, d in ok], "o-", color="#d62728", label="目を閉じてから気づくまでの時間")
    chosen_time = first_crossing(sl_m, sl_avg, baseline * (1 - chosen), after)
    ax.axvline(chosen * 100, color="#1f77b4", lw=2,
               label="採用: %d%%（%.1f分で気づく）" % (chosen * 100, chosen_time))
    ax.set_xlim(0, 20.5)
    ax.set_xlabel("居眠りライン（起きている時の平均より何%下か）")
    ax.set_ylabel("気づくまでの時間（分）")
    ax.set_title("居眠りラインを何%%にするか（%d秒平均）" % WINDOW)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    print("グラフ:", out)


if __name__ == "__main__":
    out = sys.argv[3] if len(sys.argv) > 3 else "logs/compare.png"
    main(sys.argv[1], sys.argv[2], out)
    threshold_chart(sys.argv[1], sys.argv[2], out.rsplit(".", 1)[0] + "_threshold.png")

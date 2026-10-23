"""スマートバンドの心拍ブロードキャストを受け取り、1秒ごとの値と30秒平均を表示する

使い方: バンドの「心拍数の共有」をオンにしてから python3 heart_rate.py
        python3 heart_rate.py 5   → 5秒ごとに、最新の心拍数と5秒平均だけを表示

居眠りの判定結果（sleep_judge.py）を STATE_FILE に書き出すので、
カメラなど別のプログラムから読める。
"""
import asyncio
import csv
import json
import os
import time

HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"      # 心拍サービス
HR_MEASUREMENT = "00002a37-0000-1000-8000-00805f9b34fb"  # 心拍数の値
AVERAGE_SECONDS = 30  # 平均をとる長さ（この間隔で表示もする）
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")  # 実験の記録
STATE_FILE = "/tmp/maneki_heart.json"  # 最新の心拍数と居眠り判定
STATE_NAMES = {"calibrating": "起きている時の心拍数を測定中", "awake": "起きている", "sleepy": "居眠りかも"}


def parse_bpm(data):
    """BLE 心拍プロトコルのデータから心拍数を取り出す"""
    if data[0] & 0x01:
        return int.from_bytes(data[1:3], "little")
    return data[1]


def average(samples, now, window):
    """(時刻, 心拍数) のうち、now から window 秒以内の平均。なければ None"""
    recent = [bpm for t, bpm in samples if now - t <= window]
    if not recent:
        return None
    return sum(recent) / len(recent)


def write_state(path, state):
    """途中まで書いたファイルを読まれないよう、別名で書いてから置き換える"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, path)


async def main(report_seconds=None):
    """report_seconds を指定すると、その間隔でまとめて表示する（指定なしは毎回表示＋30秒平均）"""
    show_each = report_seconds is None
    window = report_seconds or AVERAGE_SECONDS
    from bleak import BleakClient, BleakScanner
    from bleak.exc import BleakError
    from sleep_judge import HeartSleepJudge

    samples = []
    next_report = time.monotonic() + window
    judge = HeartSleepJudge()
    print("最初の%d秒で、起きている時の心拍数を測ります" % judge.baseline_seconds)

    # 実験用に、受け取った心拍数をすべて CSV に記録する
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, time.strftime("heart_%Y%m%d_%H%M%S.csv"))
    log = open(log_path, "w", newline="", encoding="utf-8")
    writer = csv.writer(log)
    writer.writerow(["time", "bpm", "average", "baseline", "state"])
    print("記録ファイル:", log_path)

    def on_heart_rate(_, data):
        nonlocal next_report
        now = time.monotonic()
        bpm = parse_bpm(data)
        samples.append((now, bpm))
        del samples[:-window * 5]  # 古いデータを捨てる
        clock = time.strftime("%H:%M:%S")
        before = judge.state
        judge.add(now, bpm)
        if judge.state != before:
            if before == "calibrating":
                print("%s  起きている時の平均: %.0f" % (clock, judge.baseline))
            print("%s  ★ %s（直近%d秒の平均 %.0f）" % (
                clock, STATE_NAMES[judge.state], judge.window, judge.recent_average))
        write_state(STATE_FILE, {
            "time": time.time(), "bpm": bpm, "average": judge.recent_average,
            "baseline": judge.baseline, "state": judge.state,
        })
        writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), bpm,
                         "%.1f" % judge.recent_average,
                         "" if judge.baseline is None else "%.1f" % judge.baseline,
                         judge.state])
        log.flush()
        if show_each:
            print("%s  心拍数 %d" % (clock, bpm))
        if now >= next_report:
            avg = average(samples, now, window)
            if show_each:
                print("  ── 直近%d秒の平均: %.0f" % (window, avg))
            else:
                print("%s  心拍数 %d（直近%d秒の平均 %.0f）" % (clock, bpm, window, avg))
            next_report = now + window

    # 接続が切れても、止めるまで探し直してつなぎ直す
    try:
        while True:
            print("心拍数を送っているバンドを探しています…")
            device = await BleakScanner.find_device_by_filter(
                lambda d, adv: HR_SERVICE in [u.lower() for u in adv.service_uuids],
                timeout=20,
            )
            if device is None:
                print("見つかりませんでした。バンドの「心拍数の共有」がオンか確認してください")
                await asyncio.sleep(10)
                continue
            print("見つかりました:", device.name)
            try:
                async with BleakClient(device, timeout=20) as client:
                    await client.start_notify(HR_MEASUREMENT, on_heart_rate)
                    print("受信中（Ctrl+Cで終了）")
                    while client.is_connected:
                        await asyncio.sleep(1)
                    print("%s  バンドとの接続が切れました" % time.strftime("%H:%M:%S"))
            except (BleakError, asyncio.TimeoutError) as e:
                # ラズパイの Bluetooth はたまに接続に失敗するので、少し待ってやり直す
                print("接続失敗: %s" % e)
            await asyncio.sleep(2)
    finally:
        log.close()


if __name__ == "__main__":
    import sys
    try:
        asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else None))
    except KeyboardInterrupt:
        pass

"""心拍数で居眠りを判定する（起きている時の平均より8%以上下がったら居眠り）

企画書の例は10%。2026-10-23 の実験（logs/compare_20261023.png）で、
課題中は最大2.4%しか下がらず、目を閉じると15.5%まで下がったので、
どちらにも余裕のある8%（60秒平均）にした。
"""
from heart_rate import average


class HeartSleepJudge:
    """
    state は次の3つ:
      "calibrating" … 最初の baseline_seconds 秒で、起きている時の平均を測っている
      "awake"       … 起きている
      "sleepy"      … 直近 window 秒の平均が、起きている時より drop_ratio 以上下がった
    """

    def __init__(self, baseline_seconds=120, window=60, drop_ratio=0.08):
        self.baseline_seconds = baseline_seconds
        self.window = window
        self.drop_ratio = drop_ratio
        self.baseline = None
        self.recent_average = None
        self.state = "calibrating"
        self._start = None
        self._calibration = []
        self._samples = []

    def add(self, t, bpm):
        """t 秒（time.monotonic() など）に心拍数 bpm を受け取った"""
        if self._start is None:
            self._start = t
        if self.baseline is None:
            if t - self._start < self.baseline_seconds:
                self._calibration.append(bpm)
            else:
                self.baseline = sum(self._calibration) / len(self._calibration)
                self.state = "awake"

        self._samples.append((t, bpm))
        self._samples = [(st, b) for st, b in self._samples if t - st <= self.window]
        self.recent_average = average(self._samples, t, self.window)

        if self.baseline is not None:
            self._update_state()

    def _update_state(self):
        sleepy_line = self.baseline * (1 - self.drop_ratio)
        # 境目でパタパタ切り替わらないよう、起きた判定は半分まで戻ったときにする
        awake_line = self.baseline * (1 - self.drop_ratio / 2)
        if self.state == "awake" and self.recent_average <= sleepy_line:
            self.state = "sleepy"
        elif self.state == "sleepy" and self.recent_average >= awake_line:
            self.state = "awake"

import unittest

from sleep_judge import HeartSleepJudge


def feed(judge, start, end, bpm):
    """start〜end 秒のあいだ、1秒ごとに同じ心拍数を入れる"""
    for t in range(start, end):
        judge.add(t, bpm)


class TestHeartSleepJudge(unittest.TestCase):
    def make(self):
        # 最初の60秒で「起きている時の平均」を測り、直近30秒の平均で判定する
        return HeartSleepJudge(baseline_seconds=60, window=30, drop_ratio=0.10)

    def test_calibrating_at_first(self):
        judge = self.make()
        feed(judge, 0, 30, 70)
        self.assertEqual(judge.state, "calibrating")
        self.assertIsNone(judge.baseline)

    def test_baseline_is_average_of_first_period(self):
        judge = self.make()
        feed(judge, 0, 30, 60)
        feed(judge, 30, 61, 80)
        self.assertAlmostEqual(judge.baseline, 70, delta=0.5)
        self.assertEqual(judge.state, "awake")

    def test_small_drop_is_still_awake(self):
        judge = self.make()
        feed(judge, 0, 61, 70)
        feed(judge, 61, 100, 65)  # 7% 下がっただけ
        self.assertEqual(judge.state, "awake")

    def test_drop_of_10_percent_is_sleepy(self):
        judge = self.make()
        feed(judge, 0, 61, 70)
        feed(judge, 61, 100, 62)  # 70 の 10% 下 = 63 以下
        self.assertEqual(judge.state, "sleepy")

    def test_recovers_when_heart_rate_comes_back(self):
        judge = self.make()
        feed(judge, 0, 61, 70)
        feed(judge, 61, 100, 60)
        self.assertEqual(judge.state, "sleepy")
        feed(judge, 100, 140, 70)
        self.assertEqual(judge.state, "awake")

    def test_no_flicker_near_threshold(self):
        # 境目（63）を少し超えただけでは起きた扱いにしない
        judge = self.make()
        feed(judge, 0, 61, 70)
        feed(judge, 61, 100, 60)
        feed(judge, 100, 140, 64)
        self.assertEqual(judge.state, "sleepy")

    def test_average_uses_recent_window_only(self):
        judge = self.make()
        feed(judge, 0, 61, 70)
        feed(judge, 61, 70, 50)    # 一瞬だけ大きく下がっても
        feed(judge, 70, 101, 70)   # 直近30秒が元に戻っていれば
        self.assertEqual(judge.state, "awake")


if __name__ == "__main__":
    unittest.main()

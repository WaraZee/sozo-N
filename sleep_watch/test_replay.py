import unittest
from datetime import datetime

from judges import SleepJudge
from replay import alarm_times, restate


def ts(clock):
    return datetime.fromisoformat("2026-10-30T15:%s+09:00" % clock).timestamp()


def camera_row(clock, eye_state, closed="0.00"):
    return {"datetime": "2026-10-30T15:%s+09:00" % clock, "eye_state": eye_state, "closed_seconds": closed}


def heart_rows(start, end, state):
    return [{"time": t, "state": state} for t in range(int(ts(start)), int(ts(end)))]


class ReplayTest(unittest.TestCase):
    def closed_for_19_seconds(self):
        return [camera_row("00:00", "open"), camera_row("00:05", "closed"),
                camera_row("00:10", "closed", "5.00"), camera_row("00:15", "closed", "10.00"),
                camera_row("00:20", "closed", "15.00"), camera_row("00:25", "open")]

    def test_鳴る時刻を返す(self):
        heart = heart_rows("00:00", "00:30", "sleepy")  # 心拍が下がっていれば目を3秒で鳴る
        times = alarm_times(SleepJudge(), self.closed_for_19_seconds(), heart, ts("00:00"), ts("00:30"))
        self.assertEqual(times, [int(ts("00:08"))])

    def test_条件を満たさなければ鳴らない(self):
        heart = heart_rows("00:00", "00:30", "awake")  # ふつうなら20秒まで閉じていないので鳴らない
        self.assertEqual(alarm_times(SleepJudge(), self.closed_for_19_seconds(), heart, ts("00:00"), ts("00:30")), [])

    def test_指定した場面より前に鳴ったものは数えない(self):
        heart = heart_rows("00:00", "00:30", "sleepy")
        self.assertEqual(alarm_times(SleepJudge(), self.closed_for_19_seconds(), heart, ts("00:20"), ts("00:30")), [])

    def test_一度寝ている状態から戻ってまた寝たら2回と数える(self):
        rows = self.closed_for_19_seconds() + [camera_row("00:30", "closed"), camera_row("00:40", "closed", "10.00")]
        heart = heart_rows("00:00", "00:45", "sleepy")
        times = alarm_times(SleepJudge(), rows, heart, ts("00:00"), ts("00:45"))
        self.assertEqual(times, [int(ts("00:08")), int(ts("00:33"))])


class RestateTest(unittest.TestCase):
    """記録の state ではなく bpm から判定し直す（11/06 の記録は、バンドを外した 0 で sleepy になっていた）"""

    def rows(self, pieces):
        rows, t = [], 0
        for seconds, bpm in pieces:
            for _ in range(seconds):
                rows.append({"time": float(t), "bpm": bpm, "state": "sleepy"})
                t += 1
        return rows

    def test_バンドを外した0は取れない扱いになる(self):
        rows = restate(self.rows([(130, 70), (60, 0)]))
        self.assertEqual(rows[100]["state"], "calibrating")
        self.assertEqual(rows[125]["state"], "awake")
        self.assertEqual(rows[-1]["state"], "no_reading")

    def test_本当に下がったときは下がった扱い(self):
        rows = restate(self.rows([(130, 70), (80, 60)]))
        self.assertEqual(rows[-1]["state"], "sleepy")


if __name__ == "__main__":
    unittest.main()

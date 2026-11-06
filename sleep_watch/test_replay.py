import unittest
from datetime import datetime

from judges import BothJudge, EitherJudge
from replay import alarm_times


def ts(clock):
    return datetime.fromisoformat("2026-10-30T15:%s+09:00" % clock).timestamp()


def camera_row(clock, eye_state, closed="0.00"):
    return {"datetime": "2026-10-30T15:%s+09:00" % clock, "eye_state": eye_state, "closed_seconds": closed}


def heart_rows(start, end, state):
    return [{"time": t, "state": state} for t in range(int(ts(start)), int(ts(end)))]


class ReplayTest(unittest.TestCase):
    def closed_for_20_seconds(self):
        return [camera_row("00:00", "open"), camera_row("00:05", "closed"),
                camera_row("00:10", "closed", "5.00"), camera_row("00:15", "closed", "10.00"),
                camera_row("00:20", "closed", "15.00"), camera_row("00:25", "open")]

    def test_鳴る時刻を返す(self):
        heart = heart_rows("00:00", "00:30", "awake")
        times = alarm_times(EitherJudge(), self.closed_for_20_seconds(), heart, ts("00:00"), ts("00:30"))
        self.assertEqual(times, [int(ts("00:15"))])

    def test_条件を満たさなければ鳴らない(self):
        heart = heart_rows("00:00", "00:30", "awake")
        self.assertEqual(alarm_times(BothJudge(), self.closed_for_20_seconds(), heart, ts("00:00"), ts("00:30")), [])

    def test_指定した場面より前に鳴ったものは数えない(self):
        heart = heart_rows("00:00", "00:30", "awake")
        self.assertEqual(alarm_times(EitherJudge(), self.closed_for_20_seconds(), heart, ts("00:20"), ts("00:30")), [])

    def test_一度寝ている状態から戻ってまた寝たら2回と数える(self):
        rows = self.closed_for_20_seconds() + [camera_row("00:30", "closed"), camera_row("00:40", "closed", "10.00")]
        heart = heart_rows("00:00", "00:45", "awake")
        times = alarm_times(EitherJudge(), rows, heart, ts("00:00"), ts("00:45"))
        self.assertEqual(times, [int(ts("00:15")), int(ts("00:40"))])


if __name__ == "__main__":
    unittest.main()

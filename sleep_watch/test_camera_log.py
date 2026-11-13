import os
import tempfile
import unittest
from datetime import datetime

from camera_log import camera_at, last_row, load_rows


def ts(text):
    return datetime.fromisoformat(text).timestamp()


def row(clock, eye_state="closed", closed="0.00"):
    return {"datetime": "2026-10-30T15:00:%s+09:00" % clock, "state": "X", "face_detected": "1",
            "eye_state": eye_state, "closed_seconds": closed}


class CameraAtTest(unittest.TestCase):
    def test_目を閉じている間は記録のあとの時間も足す(self):
        t = ts("2026-10-30T15:00:10+09:00")
        camera = camera_at(row("05", closed="2.00"), t)
        self.assertEqual(camera["closed_seconds"], 7.0)
        self.assertEqual(camera["eye_state"], "closed")

    def test_目を開けていれば足さない(self):
        t = ts("2026-10-30T15:00:10+09:00")
        self.assertEqual(camera_at(row("05", "open"), t)["closed_seconds"], 0.0)

    def test_時刻は記録の時刻ではなく見ている時刻にする(self):
        t = ts("2026-10-30T15:00:08+09:00")
        self.assertEqual(camera_at(row("05", "open"), t)["time"], t)

    def test_カメラが止まって記録が古ければNone(self):
        t = ts("2026-10-30T15:00:40+09:00")
        self.assertIsNone(camera_at(row("05"), t))

    def test_行がなければNone(self):
        self.assertIsNone(camera_at(None, 100))


class CameraFileTest(unittest.TestCase):
    HEADER = "datetime,state,face_detected,eye_state,closed_seconds\r\n"

    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8-sig", newline="")
        f.write(text)
        f.close()
        self.addCleanup(os.remove, f.name)
        return f.name

    def test_最後の行を読む(self):
        path = self.write(self.HEADER + "a,AWAKE,1,open,0.00\r\nb,DROWSY,1,closed,1.00\r\n")
        self.assertEqual(last_row(path)["eye_state"], "closed")
        self.assertEqual(last_row(path)["datetime"], "b")

    def test_書きかけの行は読まない(self):
        path = self.write(self.HEADER + "a,AWAKE,1,open,0.00\r\nb,DRO")
        self.assertEqual(last_row(path)["datetime"], "a")

    def test_ファイルがない_中身がなければNone(self):
        self.assertIsNone(last_row("/no/such/file.csv"))
        self.assertIsNone(last_row(self.write(self.HEADER)))

    def test_全部の行を読む(self):
        path = self.write(self.HEADER + "a,AWAKE,1,open,0.00\r\nb,DROWSY,1,closed,1.00\r\n")
        self.assertEqual([r["datetime"] for r in load_rows(path)], ["a", "b"])


if __name__ == "__main__":
    unittest.main()

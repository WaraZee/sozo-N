import unittest

from fusion import SleepFusion


def camera(t, closed_seconds=0.0, eye_state="closed"):
    return {"time": t, "eye_state": eye_state, "closed_seconds": closed_seconds}


def heart(t, state="sleepy"):
    return {"time": t, "state": state}


class SleepFusionTest(unittest.TestCase):
    def setUp(self):
        self.f = SleepFusion(closed_seconds=10, open_seconds=2, stale_seconds=10)

    def test_起こすのは目を10秒閉じていて心拍も下がったとき(self):
        self.assertIsNone(self.f.update(100, camera(100, 9.9), heart(100)))
        self.assertEqual(self.f.update(101, camera(101, 10.0), heart(101)), "wake")
        self.assertTrue(self.f.alarming)

    def test_目を閉じていても心拍が下がっていなければ起こさない(self):
        self.assertIsNone(self.f.update(100, camera(100, 30), heart(100, "awake")))
        self.assertIsNone(self.f.update(100, camera(100, 30), heart(100, "calibrating")))

    def test_心拍が下がっていても目を開けていれば起こさない(self):
        self.assertIsNone(self.f.update(100, camera(100, 0, "open"), heart(100)))

    def test_どちらかのデータが届いていなければ起こさない(self):
        self.assertIsNone(self.f.update(100, None, heart(100)))
        self.assertIsNone(self.f.update(100, camera(100, 30), None))

    def test_古いデータでは起こさない(self):
        self.assertIsNone(self.f.update(100, camera(80, 30), heart(100)))
        self.assertIsNone(self.f.update(100, camera(100, 30), heart(80)))

    def test_鳴っている間はもう一度起こさない(self):
        self.f.update(100, camera(100, 10), heart(100))
        self.assertIsNone(self.f.update(101, camera(101, 11), heart(101)))

    def test_目を2秒開け続けたら止める(self):
        self.f.update(100, camera(100, 10), heart(100))
        self.assertIsNone(self.f.update(101, camera(101, eye_state="open"), heart(101)))
        self.assertIsNone(self.f.update(102.5, camera(102.5, eye_state="open"), heart(102.5)))
        self.assertEqual(self.f.update(103, camera(103, eye_state="open"), heart(103)), "stop")
        self.assertFalse(self.f.alarming)

    def test_一瞬目を開けただけでは止めない(self):
        self.f.update(100, camera(100, 10), heart(100))
        self.f.update(101, camera(101, eye_state="open"), heart(101))
        self.f.update(102, camera(102, 0.5), heart(102))
        self.assertIsNone(self.f.update(103.5, camera(103.5, eye_state="open"), heart(103.5)))
        self.assertTrue(self.f.alarming)

    def test_鳴っている間に心拍が戻っても目を閉じていれば止めない(self):
        self.f.update(100, camera(100, 10), heart(100))
        self.assertIsNone(self.f.update(110, camera(110, 20), heart(110, "awake")))
        self.assertTrue(self.f.alarming)

    def test_鳴っている間にカメラが止まっても止めない(self):
        self.f.update(100, camera(100, 10), heart(100))
        self.assertIsNone(self.f.update(130, camera(100, 10), heart(130)))
        self.assertTrue(self.f.alarming)

    def test_止めたあとまた寝たらまた起こす(self):
        self.f.update(100, camera(100, 10), heart(100))
        self.f.update(101, camera(101, eye_state="open"), heart(101))
        self.f.update(103, camera(103, eye_state="open"), heart(103))
        self.assertEqual(self.f.update(120, camera(120, 10), heart(120)), "wake")


if __name__ == "__main__":
    unittest.main()

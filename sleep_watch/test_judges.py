import unittest

from judges import BothJudge, ClosedRatioJudge, CombinedJudge, EitherJudge


def camera(t, closed_seconds=0.0, eye_state="closed"):
    return {"time": t, "eye_state": eye_state, "closed_seconds": closed_seconds}


def heart(t, state="sleepy"):
    return {"time": t, "state": state}


class BothJudgeTest(unittest.TestCase):
    def test_目を10秒閉じて心拍も下がったら寝ている(self):
        j = BothJudge()
        self.assertFalse(j.update(100, camera(100, 9.9), heart(100)))
        self.assertTrue(j.update(100, camera(100, 10), heart(100)))

    def test_片方だけなら寝ていない(self):
        j = BothJudge()
        self.assertFalse(j.update(100, camera(100, 30), heart(100, "awake")))
        self.assertFalse(j.update(100, camera(100, 0, "open"), heart(100)))

    def test_データがないか古ければ寝ていない(self):
        j = BothJudge()
        self.assertFalse(j.update(100, None, heart(100)))
        self.assertFalse(j.update(100, camera(100, 30), None))
        self.assertFalse(j.update(100, camera(80, 30), heart(100)))
        self.assertFalse(j.update(100, camera(100, 30), heart(80)))


class EitherJudgeTest(unittest.TestCase):
    def test_どちらか片方で寝ている(self):
        j = EitherJudge()
        self.assertTrue(j.update(100, camera(100, 10), heart(100, "awake")))
        self.assertTrue(j.update(100, camera(100, 0, "open"), heart(100)))

    def test_カメラがなくても心拍だけで判定できる(self):
        self.assertTrue(EitherJudge().update(100, None, heart(100)))

    def test_どちらもふつうなら寝ていない(self):
        j = EitherJudge()
        self.assertFalse(j.update(100, camera(100, 9.9), heart(100, "awake")))
        self.assertFalse(j.update(100, None, None))


class CombinedJudgeTest(unittest.TestCase):
    def test_心拍が下がっていれば目を3秒で寝ている(self):
        j = CombinedJudge()
        self.assertFalse(j.update(100, camera(100, 2.9), heart(100)))
        self.assertTrue(j.update(100, camera(100, 3), heart(100)))

    def test_心拍がふつうなら目を30秒で寝ている(self):
        j = CombinedJudge()
        self.assertFalse(j.update(100, camera(100, 29.9), heart(100, "awake")))
        self.assertTrue(j.update(100, camera(100, 30), heart(100, "awake")))

    def test_心拍のデータがなければふつうと同じ(self):
        j = CombinedJudge()
        self.assertFalse(j.update(100, camera(100, 29.9), None))
        self.assertTrue(j.update(100, camera(100, 30), None))

    def test_心拍が下がって顔が10秒見えなければ寝ている(self):
        j = CombinedJudge()
        self.assertFalse(j.update(100, camera(100, 0, "no_face"), heart(100)))
        self.assertFalse(j.update(109, camera(109, 0, "no_face"), heart(109)))
        self.assertTrue(j.update(110, camera(110, 0, "no_face"), heart(110)))

    def test_心拍がふつうなら顔が見えなくても寝ていない(self):
        j = CombinedJudge()  # 席を立っただけかもしれない
        j.update(100, camera(100, 0, "no_face"), heart(100, "awake"))
        self.assertFalse(j.update(200, camera(200, 0, "no_face"), heart(200, "awake")))

    def test_顔が見えたら数え直す(self):
        j = CombinedJudge()
        j.update(100, camera(100, 0, "no_face"), heart(100))
        j.update(105, camera(105, 0, "open"), heart(105))
        j.update(106, camera(106, 0, "no_face"), heart(106))
        self.assertFalse(j.update(112, camera(112, 0, "no_face"), heart(112)))

    def test_カメラが止まっただけでは顔が見えないと数えない(self):
        j = CombinedJudge()
        j.update(100, camera(100, 0, "no_face"), heart(100))
        self.assertFalse(j.update(130, camera(100, 0, "no_face"), heart(130)))


class ClosedRatioJudgeTest(unittest.TestCase):
    def feed(self, j, start, seconds, eye_state):
        result = False
        for t in range(start, start + seconds):
            result = j.update(t, camera(t, 0, eye_state), None)
        return result

    def test_60秒のうち30秒閉じたら寝ている(self):
        j = ClosedRatioJudge()
        self.assertFalse(self.feed(j, 0, 30, "closed"))
        self.assertTrue(j.update(30, camera(30, 0, "open"), None))

    def test_途中で目を開けても合計で数える(self):
        j = ClosedRatioJudge()
        self.feed(j, 0, 16, "closed")
        self.feed(j, 16, 5, "open")
        self.assertFalse(self.feed(j, 21, 14, "closed"))
        self.assertTrue(self.feed(j, 35, 3, "closed"))

    def test_60秒より前に閉じていた分は数えない(self):
        j = ClosedRatioJudge()
        self.feed(j, 0, 20, "closed")
        self.feed(j, 20, 60, "open")
        self.assertFalse(self.feed(j, 80, 20, "closed"))

    def test_古いカメラのデータは閉じていると数えない(self):
        j = ClosedRatioJudge()
        j.update(0, camera(0, 0, "closed"), None)
        self.assertFalse(j.update(100, camera(0, 0, "closed"), None))
        self.assertFalse(j.update(140, camera(0, 0, "closed"), None))


if __name__ == "__main__":
    unittest.main()

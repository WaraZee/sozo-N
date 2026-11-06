import unittest

from judges import SleepJudge


def camera(t, closed_seconds=0.0, eye_state="closed"):
    return {"time": t, "eye_state": eye_state, "closed_seconds": closed_seconds}


def heart(t, state="sleepy"):
    return {"time": t, "state": state}


class SleepJudgeTest(unittest.TestCase):
    def test_心拍が下がっていれば目を3秒で寝ている(self):
        j = SleepJudge()
        self.assertFalse(j.update(100, camera(100, 2.9), heart(100)))
        self.assertTrue(j.update(100, camera(100, 3), heart(100)))

    def test_心拍がふつうなら目を20秒で寝ている(self):
        j = SleepJudge()
        self.assertFalse(j.update(100, camera(100, 19.9), heart(100, "awake")))
        self.assertTrue(j.update(100, camera(100, 20), heart(100, "awake")))

    def test_心拍のデータがなければふつうと同じ(self):
        j = SleepJudge()
        self.assertFalse(j.update(100, camera(100, 19.9), None))
        self.assertTrue(j.update(100, camera(100, 20), None))

    def test_バンドを外していればふつうと同じ(self):
        j = SleepJudge()
        self.assertFalse(j.update(100, camera(100, 19.9), heart(100, "no_reading")))
        self.assertTrue(j.update(100, camera(100, 20), heart(100, "no_reading")))

    def test_心拍が下がって顔が10秒見えなければ寝ている(self):
        j = SleepJudge()
        self.assertFalse(j.update(100, camera(100, 0, "no_face"), heart(100)))
        self.assertFalse(j.update(109, camera(109, 0, "no_face"), heart(109)))
        self.assertTrue(j.update(110, camera(110, 0, "no_face"), heart(110)))

    def test_心拍がふつうなら顔が見えなくても寝ていない(self):
        j = SleepJudge()  # 席を立っただけかもしれない
        j.update(100, camera(100, 0, "no_face"), heart(100, "awake"))
        self.assertFalse(j.update(200, camera(200, 0, "no_face"), heart(200, "awake")))

    def test_顔が見えたら数え直す(self):
        j = SleepJudge()
        j.update(100, camera(100, 0, "no_face"), heart(100))
        j.update(105, camera(105, 0, "open"), heart(105))
        j.update(106, camera(106, 0, "no_face"), heart(106))
        self.assertFalse(j.update(112, camera(112, 0, "no_face"), heart(112)))

    def test_カメラが止まっただけでは顔が見えないと数えない(self):
        j = SleepJudge()
        j.update(100, camera(100, 0, "no_face"), heart(100))
        self.assertFalse(j.update(130, camera(100, 0, "no_face"), heart(130)))


    def test_データが古ければ使わない(self):
        j = SleepJudge()
        self.assertFalse(j.update(100, None, heart(100)))
        self.assertFalse(j.update(100, camera(80, 30), heart(100)))
        self.assertFalse(j.update(100, camera(100, 5), heart(80)))  # 心拍が古ければふつう扱い


if __name__ == "__main__":
    unittest.main()

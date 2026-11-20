import unittest

from alarm import Alarm
from judges import SleepJudge
from sleep_watch import NoPhone, Phone, should_trigger_sleep_alarm


class FakeMotor:
    def __init__(self):
        self.calls = []

    def start(self):
        self.calls.append("start")

    def stop(self):
        self.calls.append("stop")


class NoPhoneTest(unittest.TestCase):
    def setUp(self):
        self.phone = NoPhone()

    def camera(self, state, fresh=True):
        return {"eye_state": state, "time": 100 if fresh else 0}

    def test_開いた目を検出したら鳴り止んだとみなす(self):
        self.phone.see(100, self.camera("open"))
        self.assertFalse(self.phone.is_ringing())

    def test_目がはっきりしない場合も開いたとみなす(self):
        self.phone.see(100, self.camera("uncertain"))
        self.assertFalse(self.phone.is_ringing())

    def test_顔が見えないだけでは鳴り止んだとみなさない(self):
        self.phone.see(100, self.camera("no_face"))
        self.assertTrue(self.phone.is_ringing())

    def test_古いカメラ情報では鳴り止んだとみなさない(self):
        self.phone.see(100, self.camera("open", fresh=False))
        self.assertTrue(self.phone.is_ringing())

    def test_目がはっきりしなくてもモーターを止める(self):
        motor = FakeMotor()
        alarm = Alarm(motor, self.phone, check_every=2)

        self.phone.see(100, self.camera("closed"))
        self.assertEqual(alarm.update(100, True), "start")
        self.phone.see(102, self.camera("uncertain"))
        self.assertEqual(alarm.update(102, False), "released")
        self.assertEqual(motor.calls, ["start", "stop"])


class PhoneEyeTest(unittest.TestCase):
    def camera(self, state, fresh=True):
        return {"eye_state": state, "time": 100 if fresh else 0}

    def test_スマホモードでも目を開けたら鳴り止める(self):
        phone = Phone("u0@192.0.2.1")
        phone.see(100, self.camera("uncertain"))
        self.assertFalse(phone.is_ringing())

    def test_スマホモードで顔が見えないだけでは鳴り止めない(self):
        phone = Phone("u0@192.0.2.1")
        phone.see(100, self.camera("no_face"))
        self.assertFalse(phone.eyes_open)


class RequireHeartTest(unittest.TestCase):
    def camera(self, closed_seconds):
        return {
            "time": 100,
            "eye_state": "closed",
            "closed_seconds": closed_seconds,
        }

    def heart(self, state, timestamp=100):
        return {"time": timestamp, "state": state}

    def test_missing_heart_does_not_fall_back_to_camera_only(self):
        judge = SleepJudge()
        self.assertFalse(
            should_trigger_sleep_alarm(judge, 100, self.camera(20), None, True)
        )

    def test_stale_or_calibrating_heart_does_not_enable_alarm(self):
        self.assertFalse(
            should_trigger_sleep_alarm(
                SleepJudge(), 100, self.camera(20), self.heart("awake", 80), True
            )
        )
        self.assertFalse(
            should_trigger_sleep_alarm(
                SleepJudge(), 100, self.camera(20), self.heart("calibrating"), True
            )
        )

    def test_fresh_sleepy_heart_can_trigger_with_short_eye_closure(self):
        self.assertTrue(
            should_trigger_sleep_alarm(
                SleepJudge(), 100, self.camera(3), self.heart("sleepy"), True
            )
        )


if __name__ == "__main__":
    unittest.main()

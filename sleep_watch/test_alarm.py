import unittest

from alarm import Alarm


class FakeMotor:
    def __init__(self):
        self.calls = []

    def start(self):
        self.calls.append("start")

    def stop(self):
        self.calls.append("stop")


class FakePhone:
    def __init__(self):
        self.calls = []
        self.ringing = True

    def wake(self):
        self.calls.append("wake")
        return self.wake_ok

    wake_ok = True

    def stop(self):
        self.calls.append("stop")

    def is_ringing(self):
        return self.ringing


class AlarmTest(unittest.TestCase):
    def setUp(self):
        self.motor, self.phone = FakeMotor(), FakePhone()
        self.alarm = Alarm(self.motor, self.phone, max_seconds=300, quiet_seconds=60, check_every=2)

    def test_寝ているとモーターとスマホを鳴らす(self):
        self.assertEqual(self.alarm.update(100, True), "start")
        self.assertEqual(self.motor.calls, ["start"])
        self.assertEqual(self.phone.calls, ["wake"])

    def test_寝ていなければ鳴らさない(self):
        self.assertIsNone(self.alarm.update(100, False))
        self.assertEqual(self.motor.calls, [])

    def test_鳴っている間にもう一度鳴らさない(self):
        self.alarm.update(100, True)
        self.alarm.update(101, True)
        self.assertEqual(self.motor.calls, ["start"])

    def test_目を開けても通知を押すまで止まらない(self):
        self.alarm.update(100, True)
        self.assertIsNone(self.alarm.update(110, False))
        self.assertTrue(self.alarm.ringing)

    def test_通知を押したらモーターを止める(self):
        self.alarm.update(100, True)
        self.phone.ringing = False
        self.assertEqual(self.alarm.update(102, False), "released")
        self.assertEqual(self.motor.calls, ["start", "stop"])
        self.assertEqual(self.phone.calls, ["wake"])  # スマホはもう止まっている

    def test_スマホを確認するのは数秒おき(self):
        self.alarm.update(100, True)
        self.phone.ringing = False
        self.assertIsNone(self.alarm.update(101, False))
        self.assertEqual(self.alarm.update(102, False), "released")

    def test_スマホにつながらないときは止めない(self):
        self.alarm.update(100, True)
        self.phone.ringing = None
        self.assertIsNone(self.alarm.update(102, False))
        self.assertTrue(self.alarm.ringing)

    def test_呼び出しが時間切れでまだ印がないときは止めない(self):
        # 2026-10-30: 呼び出しが15秒で時間切れになり、印ができる前に「押された」と勘違いした
        self.phone.wake_ok = False
        self.alarm.update(100, True)
        self.phone.ringing = False
        self.assertIsNone(self.alarm.update(102, False))
        self.assertTrue(self.alarm.ringing)

    def test_呼び出しが時間切れでも印が見えたあとに消えたら止める(self):
        self.phone.wake_ok = False
        self.alarm.update(100, True)
        self.phone.ringing = True
        self.alarm.update(102, False)
        self.phone.ringing = False
        self.assertEqual(self.alarm.update(104, False), "released")

    def test_だれも押さなくても時間が来たら止める(self):
        self.alarm.update(100, True)
        self.phone.ringing = None
        self.assertEqual(self.alarm.update(400, True), "timeout")
        self.assertEqual(self.motor.calls, ["start", "stop"])
        self.assertEqual(self.phone.calls, ["wake", "stop"])

    def test_止めたあとしばらくは鳴らさない(self):
        self.alarm.update(100, True)
        self.phone.ringing = False
        self.alarm.update(102, True)
        self.assertIsNone(self.alarm.update(161, True))
        self.assertEqual(self.alarm.update(162, True), "start")

    def test_shutdownで鳴っていれば止める(self):
        self.alarm.update(100, True)
        self.alarm.shutdown()
        self.assertEqual(self.motor.calls, ["start", "stop"])
        self.assertEqual(self.phone.calls, ["wake", "stop"])

    def test_鳴っていなければshutdownでスマホは呼ばない(self):
        self.alarm.shutdown()
        self.assertEqual(self.motor.calls, ["stop"])
        self.assertEqual(self.phone.calls, [])

    def test_スマホでエラーが起きてもモーターは止める(self):
        self.alarm.update(100, True)

        def broken():
            raise OSError("no phone")
        self.phone.stop = broken
        with self.assertRaises(OSError):
            self.alarm.shutdown()
        self.assertEqual(self.motor.calls, ["start", "stop"])


if __name__ == "__main__":
    unittest.main()

"""実機を使わず、連続回転・時間指定・異常時の停止を検証する。"""

import unittest
from unittest.mock import Mock, patch

from arm.motor_control import MotorController, SleepMotor


class TestMotorController(unittest.TestCase):
    def test_sleep_transitions(self):
        motor = Mock()
        controller = SleepMotor(motor)
        controller.update("AWAKE")
        motor.start.assert_not_called()
        controller.update("POSSIBLE_SLEEP")
        controller.update("POSSIBLE_SLEEP")
        motor.start.assert_called_once_with(speed=20)
        controller.update("NO_FACE")
        motor.stop.assert_called_once_with()
        self.assertFalse(controller.running)

    def test_timed_rotation_stops_even_when_interrupted(self):
        for interruption in (None, KeyboardInterrupt(), RuntimeError("test")):
            with self.subTest(interruption=interruption):
                motor = Mock()
                controller = MotorController(motor)
                with patch("arm.motor_control.time.sleep", side_effect=interruption) as sleep:
                    if interruption is None:
                        controller.run_for_seconds(3)
                    else:
                        with self.assertRaises(type(interruption)):
                            controller.run_for_seconds(3)
                sleep.assert_called_once_with(3)
                motor.start.assert_called_once_with(speed=20)
                motor.stop.assert_called_once_with()
                self.assertFalse(controller.running)

    def test_failed_start_attempts_stop(self):
        motor = Mock()
        motor.start.side_effect = RuntimeError("start failed")
        controller = MotorController(motor)
        with self.assertRaises(RuntimeError):
            controller.start()
        motor.stop.assert_called_once_with()

    def test_invalid_duration_never_starts(self):
        motor = Mock()
        controller = MotorController(motor)
        for seconds in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                controller.run_for_seconds(seconds)
        motor.start.assert_not_called()


if __name__ == "__main__":
    unittest.main()

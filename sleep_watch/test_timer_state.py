import json
import os
import tempfile
import unittest

from timer_state import clear_timer_state, set_timer_state, timer_is_active


class TimerStateTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "timer-state.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_timer_is_active_until_its_deadline(self):
        set_timer_state(30, now=100, path=self.path, boot_id="boot-a")

        self.assertTrue(timer_is_active(129.9, self.path, "boot-a"))
        self.assertFalse(timer_is_active(130, self.path, "boot-a"))

    def test_state_from_another_boot_is_inactive(self):
        set_timer_state(30, now=100, path=self.path, boot_id="boot-a")

        self.assertFalse(timer_is_active(101, self.path, "boot-b"))

    def test_missing_state_is_inactive_and_clear_is_idempotent(self):
        self.assertFalse(timer_is_active(100, self.path, "boot-a"))

        clear_timer_state(self.path)
        self.assertFalse(os.path.exists(self.path))

    def test_malformed_state_is_reported(self):
        with open(self.path, "w", encoding="utf-8") as state_file:
            json.dump({"boot_id": "boot-a", "expires_at": "later"}, state_file)

        with self.assertRaises(ValueError):
            timer_is_active(100, self.path, "boot-a")

    def test_nonpositive_duration_is_rejected(self):
        with self.assertRaises(ValueError):
            set_timer_state(0, now=100, path=self.path, boot_id="boot-a")


if __name__ == "__main__":
    unittest.main()

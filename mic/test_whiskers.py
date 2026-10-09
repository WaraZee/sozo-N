import unittest

from whiskers import lit_count


class TestLitCount(unittest.TestCase):
    def test_full_at_start(self):
        self.assertEqual(lit_count(60, 60, 6), 6)

    def test_one_goes_off_every_sixth(self):
        # 60秒タイマーなら10秒ごとに1本ずつ消える
        self.assertEqual(lit_count(55, 60, 6), 6)
        self.assertEqual(lit_count(50, 60, 6), 5)
        self.assertEqual(lit_count(49.9, 60, 6), 5)
        self.assertEqual(lit_count(40, 60, 6), 4)
        self.assertEqual(lit_count(10, 60, 6), 1)
        self.assertEqual(lit_count(0.1, 60, 6), 1)

    def test_none_when_finished(self):
        self.assertEqual(lit_count(0, 60, 6), 0)
        self.assertEqual(lit_count(-1, 60, 6), 0)

    def test_never_more_than_count(self):
        self.assertEqual(lit_count(70, 60, 6), 6)


if __name__ == "__main__":
    unittest.main()

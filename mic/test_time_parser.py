import unittest

from time_parser import parse_duration


class TestParseDuration(unittest.TestCase):
    def test_minutes(self):
        self.assertEqual(parse_duration("五 分"), 300)
        self.assertEqual(parse_duration("十 分"), 600)
        self.assertEqual(parse_duration("十分"), 600)
        self.assertEqual(parse_duration("三 十 分"), 1800)
        self.assertEqual(parse_duration("三十 分"), 1800)
        self.assertEqual(parse_duration("二十五 分"), 1500)
        self.assertEqual(parse_duration("四十五分"), 2700)

    def test_seconds_and_hours(self):
        self.assertEqual(parse_duration("三十 秒"), 30)
        self.assertEqual(parse_duration("九十 秒"), 90)
        self.assertEqual(parse_duration("一 時間"), 3600)
        self.assertEqual(parse_duration("百 二十 秒"), 120)

    def test_combined(self):
        self.assertEqual(parse_duration("一 時間 三十 分"), 5400)
        self.assertEqual(parse_duration("一 分 三十 秒"), 90)
        self.assertEqual(parse_duration("一 時間 半"), 5400)
        self.assertEqual(parse_duration("五 分 半"), 330)

    def test_kana_units(self):
        self.assertEqual(parse_duration("五 ふん"), 300)
        self.assertEqual(parse_duration("十 ぷん"), 600)

    def test_digits(self):
        self.assertEqual(parse_duration("30分"), 1800)
        self.assertEqual(parse_duration("３０分"), 1800)

    def test_extra_words_are_ignored(self):
        self.assertEqual(parse_duration("[unk] 十 分 タイマー"), 600)
        self.assertEqual(parse_duration("タイマー 五 分 [unk]"), 300)
        self.assertEqual(parse_duration("五 分 後 に 教えて"), 300)

    def test_no_duration(self):
        self.assertIsNone(parse_duration(""))
        self.assertIsNone(parse_duration("[unk]"))
        self.assertIsNone(parse_duration("タイマー"))
        self.assertIsNone(parse_duration("五"))
        self.assertIsNone(parse_duration("分"))


if __name__ == "__main__":
    unittest.main()

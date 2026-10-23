import unittest

from heart_rate import average, parse_bpm


class TestParseBpm(unittest.TestCase):
    def test_8bit_value(self):
        # 先頭バイトの最下位ビットが 0 なら、心拍数は1バイト
        self.assertEqual(parse_bpm(bytes([0x00, 72])), 72)

    def test_8bit_with_other_flags(self):
        # 接触センサーなど、ほかのフラグが立っていても読める
        self.assertEqual(parse_bpm(bytes([0x06, 95])), 95)

    def test_16bit_value(self):
        # 最下位ビットが 1 なら、心拍数は2バイト（リトルエンディアン）
        self.assertEqual(parse_bpm(bytes([0x01, 0x2C, 0x01])), 300)


class TestAverage(unittest.TestCase):
    def test_only_recent_values(self):
        # (時刻, 心拍数) のうち、最新から window 秒以内だけを平均する
        samples = [(0, 100), (5, 60), (10, 70), (20, 80)]
        self.assertEqual(average(samples, now=20, window=12), 75)  # 10秒と20秒の2つ
        self.assertEqual(average(samples, now=20, window=15), 70)  # ちょうど15秒前も入る

    def test_empty(self):
        self.assertIsNone(average([], now=0, window=30))


if __name__ == "__main__":
    unittest.main()

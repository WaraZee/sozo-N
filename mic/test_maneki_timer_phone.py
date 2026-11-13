import unittest

from maneki_timer_phone import TIME_WORDS, WhiskerTimer, hear_duration, kanji_number


class FakeRecognizer:
    def __init__(self, text):
        self.text = text
        self.fed = []

    def AcceptWaveform(self, data):
        self.fed.append(data)
        return False

    def FinalResult(self):
        return '{"text": "%s"}' % self.text


class HearDurationTest(unittest.TestCase):
    def test_言い終わりまで聞いて時間にする(self):
        recognizer = FakeRecognizer("十八 秒")
        self.assertEqual(hear_duration(recognizer, b"..."), ("十八 秒", 18))
        self.assertEqual(recognizer.fed, [b"..."])

    def test_時間がなければNone(self):
        self.assertEqual(hear_duration(FakeRecognizer(""), b"..."), ("", None))


class TimeWordsTest(unittest.TestCase):
    def test_漢数字(self):
        self.assertEqual([kanji_number(n) for n in (1, 10, 18, 30, 45, 60)],
                         ["一", "十", "十八", "三十", "四十五", "六十"])

    def test_1から60まで全部聞き取れる(self):
        for n in range(1, 61):
            self.assertIn(kanji_number(n), TIME_WORDS)
        for word in ["九十", "百", "百二十", "秒", "分", "時間"]:
            self.assertIn(word, TIME_WORDS)


class FakeWhiskers:
    def __init__(self):
        self.shown = []

    def show(self, count):
        self.shown.append(count)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class WhiskerTimerTest(unittest.TestCase):
    def make(self):
        self.whiskers = FakeWhiskers()
        self.finished = []
        self.clock = FakeClock()
        return WhiskerTimer(self.whiskers, self.finished.append, clock=self.clock, sleep=self.clock.sleep)

    def test_18秒なら3秒ごとに1本ずつ消えて最後に知らせる(self):
        timer = self.make()
        timer.run(timer.generation, 18)
        self.assertEqual(self.whiskers.shown, [6, 5, 4, 3, 2, 1, 0])
        self.assertEqual(self.finished, [18])
        self.assertAlmostEqual(self.clock.now, 18, delta=0.2)

    def test_止めたら知らせない(self):
        timer = self.make()
        generation = timer.generation
        timer.cancel()
        timer.run(generation, 18)
        self.assertEqual(self.finished, [])


if __name__ == "__main__":
    unittest.main()

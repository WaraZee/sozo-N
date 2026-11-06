import unittest

from hello_maneki_phone import WakeListener, is_wake_word


class WakeWordTest(unittest.TestCase):
    def test_漢字でもひらがなでも反応する(self):
        for text in ["招き猫", "まねきねこ", "ねえ 招き猫"]:
            self.assertTrue(is_wake_word(text), text)

    def test_ほかの言葉には反応しない(self):
        for text in ["", "猫", "まねき", "こんにちは"]:
            self.assertFalse(is_wake_word(text), text)


class FakeRecognizer:
    """AcceptWaveform に渡された音を、決めておいた結果に変える"""

    def __init__(self, results):
        self.results = list(results)  # (区切りがついたか, 結果の文字) の並び
        self.reset_count = 0

    def AcceptWaveform(self, data):
        self.final, self.text = self.results.pop(0)
        return self.final

    def Result(self):
        return '{"text": "%s"}' % self.text

    def PartialResult(self):
        return '{"partial": "%s"}' % self.text

    def Reset(self):
        self.reset_count += 1


class WakeListenerTest(unittest.TestCase):
    def test_区切りのついた結果で反応する(self):
        listener = WakeListener(FakeRecognizer([(True, "招き猫")]))
        self.assertTrue(listener.feed(b"..."))

    def test_録音の切れ目で言いかけでも途中経過で反応する(self):
        listener = WakeListener(FakeRecognizer([(False, "招き猫")]))
        self.assertTrue(listener.feed(b"..."))

    def test_関係ない音には反応しない(self):
        listener = WakeListener(FakeRecognizer([(True, ""), (False, "")]))
        self.assertFalse(listener.feed(b"..."))
        self.assertFalse(listener.feed(b"..."))

    def test_反応したら聞き取りをやり直す(self):
        recognizer = FakeRecognizer([(False, "招き猫"), (False, "")])
        listener = WakeListener(recognizer)
        listener.feed(b"...")
        self.assertEqual(recognizer.reset_count, 1)
        self.assertFalse(listener.feed(b"..."))  # 同じ「招き猫」で2回反応しない


if __name__ == "__main__":
    unittest.main()

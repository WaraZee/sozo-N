import json
import subprocess
import unittest
from unittest import mock

from maneki_timer import (
    LED_PIN,
    READY_MESSAGE,
    SAMPLE_RATE,
    WAKE_WORDS,
    WHISKER_PINS,
    make_recognizer,
    run_timer,
)


class FakeStream:
    def read(self, size):
        return b""


class FakeMic:
    def __init__(self):
        self.stdout = FakeStream()
        self.terminated = False

    def terminate(self):
        self.terminated = True

    def wait(self):
        return 0


class FakePhone:
    def __init__(self, mic):
        self.mic = mic
        self.commands = []

    def run(self, command, timeout):
        if not self.mic.terminated:
            raise AssertionError("microphone must stop before speaking")
        self.commands.append(command)
        return subprocess.CompletedProcess([], 0, b"", b"")


class FakeGPIO:
    LOW = 0
    HIGH = 1

    def __init__(self):
        self.outputs = []

    def output(self, pin, value):
        self.outputs.append((pin, value))


class TimerStartupTest(unittest.TestCase):
    def test_importable_and_announces_after_stopping_mic_then_cleans_up(self):
        first_mic = FakeMic()
        listening_mic = FakeMic()
        mics = iter((first_mic, listening_mic))
        phone = FakePhone(first_mic)
        gpio = FakeGPIO()

        with mock.patch("builtins.print"):
            run_timer(gpio, phone, None, None, lambda: next(mics))

        self.assertEqual(phone.commands, ["timeout 25 termux-tts-speak '%s'" % READY_MESSAGE])
        self.assertTrue(first_mic.terminated)
        self.assertTrue(listening_mic.terminated)
        self.assertEqual(
            gpio.outputs,
            [(LED_PIN, gpio.LOW)] + [(pin, gpio.LOW) for pin in WHISKER_PINS],
        )

    def test_recognizer_factory_receives_sample_rate_and_restricted_grammar(self):
        calls = []

        def factory(model, sample_rate, grammar):
            calls.append((model, sample_rate, json.loads(grammar)))
            return object()

        model = object()
        recognizer = make_recognizer(model, WAKE_WORDS, factory)

        self.assertIsNotNone(recognizer)
        self.assertEqual(calls, [(model, SAMPLE_RATE, WAKE_WORDS + ["[unk]"])])


if __name__ == "__main__":
    unittest.main()

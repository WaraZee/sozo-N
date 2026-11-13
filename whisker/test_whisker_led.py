import unittest

from whisker_led import PINS, Whiskers


class FakePWM:
    def __init__(self):
        self.duty = None
        self.stopped = False

    def start(self, duty):
        self.duty = duty

    def ChangeDutyCycle(self, duty):
        self.duty = duty

    def stop(self):
        self.stopped = True


class FakeGPIO:
    BCM = "BCM"
    OUT = "OUT"
    LOW = 0

    def __init__(self):
        self.pwms = {}
        self.cleaned = False

    def setmode(self, mode):
        self.mode = mode

    def setup(self, pin, direction, initial=None):
        pass

    def PWM(self, pin, frequency):
        self.pwms[pin] = FakePWM()
        return self.pwms[pin]

    def cleanup(self):
        self.cleaned = True


class WhiskersTest(unittest.TestCase):
    def setUp(self):
        self.gpio = FakeGPIO()
        self.w = Whiskers(gpio=self.gpio)

    def duties(self):
        return [self.gpio.pwms[pin].duty for pin in PINS]

    def test_最初は全部消えている(self):
        self.assertEqual(self.duties(), [0, 0, 0, 0, 0, 0])

    def test_指定した番号だけつける(self):
        self.w.on(1, 3)
        self.assertEqual(self.duties(), [100, 0, 100, 0, 0, 0])

    def test_指定した番号だけ消す(self):
        self.w.all_on()
        self.w.off(2, 6)
        self.assertEqual(self.duties(), [100, 0, 100, 100, 100, 0])

    def test_全部つけて全部消す(self):
        self.w.all_on()
        self.assertEqual(self.duties(), [100] * 6)
        self.w.all_off()
        self.assertEqual(self.duties(), [0] * 6)

    def test_本数を指定すると1本目から順につける(self):
        self.w.show(4)
        self.assertEqual(self.duties(), [100, 100, 100, 100, 0, 0])
        self.w.show(1)
        self.assertEqual(self.duties(), [100, 0, 0, 0, 0, 0])
        self.w.show(0)
        self.assertEqual(self.duties(), [0] * 6)

    def test_明るさはついているひげだけに効く(self):
        self.w.on(1)
        self.w.brightness(30)
        self.assertEqual(self.duties(), [30, 0, 0, 0, 0, 0])

    def test_明るさを変えたあとにつけたひげも同じ明るさ(self):
        self.w.brightness(30)
        self.w.on(2)
        self.assertEqual(self.duties(), [0, 30, 0, 0, 0, 0])

    def test_範囲外はエラーになる(self):
        for bad in (0, 7):
            with self.assertRaises(ValueError):
                self.w.on(bad)
        with self.assertRaises(ValueError):
            self.w.show(7)
        with self.assertRaises(ValueError):
            self.w.brightness(101)

    def test_閉じると消してGPIOを片付ける(self):
        self.w.all_on()
        self.w.close()
        self.assertEqual(self.duties(), [0] * 6)
        self.assertTrue(all(pwm.stopped for pwm in self.gpio.pwms.values()))
        self.assertTrue(self.gpio.cleaned)


if __name__ == "__main__":
    unittest.main()

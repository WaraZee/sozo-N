"""ひげLED 6本を、1本ずつ・本数指定・明るさ指定で制御する

プログラムから使うとき:
  from whisker_led import Whiskers
  w = Whiskers()
  w.on(1, 3)        # 1本目と3本目をつける
  w.show(4)         # 1〜4本目をつけて、残りを消す
  w.brightness(30)  # 明るさ30%
  w.close()         # 最後に必ず呼ぶ（全部消える）

試すとき:
  python3 whisker_led.py demo             → 順番・本数・明るさを一通り動かす
  python3 whisker_led.py on 1 3 --seconds 5  → 1本目と3本目を5秒つける
  python3 whisker_led.py show 4 --seconds 5  → 4本つける
"""
import argparse
import time

PINS = [17, 27, 16, 26, 20, 21]  # 1〜6本目（物理ピン 11/13/36/37/38/40）
PWM_HZ = 200  # 明るさを変える点滅の速さ（ちらつかない程度）


class Whiskers:
    def __init__(self, gpio=None):
        if gpio is None:
            import RPi.GPIO as gpio
        self._gpio = gpio
        self._level = 100
        self._lit = [False] * len(PINS)
        gpio.setmode(gpio.BCM)
        self._pwms = []
        for pin in PINS:
            gpio.setup(pin, gpio.OUT, initial=gpio.LOW)
            pwm = gpio.PWM(pin, PWM_HZ)
            pwm.start(0)
            self._pwms.append(pwm)

    def _set(self, index, lit):
        self._lit[index] = lit
        self._pwms[index].ChangeDutyCycle(self._level if lit else 0)

    def _indexes(self, numbers):
        for number in numbers:
            if not 1 <= number <= len(PINS):
                raise ValueError("ひげの番号は1〜%dです: %r" % (len(PINS), number))
        return [number - 1 for number in numbers]

    def on(self, *numbers):
        for index in self._indexes(numbers):
            self._set(index, True)

    def off(self, *numbers):
        for index in self._indexes(numbers):
            self._set(index, False)

    def all_on(self):
        self.show(len(PINS))

    def all_off(self):
        self.show(0)

    def show(self, count):
        """1本目から count 本つけて、残りを消す"""
        if not 0 <= count <= len(PINS):
            raise ValueError("本数は0〜%dです: %r" % (len(PINS), count))
        for index in range(len(PINS)):
            self._set(index, index < count)

    def brightness(self, percent):
        """明るさを 0〜100% にする。ついているひげにすぐ効く"""
        if not 0 <= percent <= 100:
            raise ValueError("明るさは0〜100です: %r" % percent)
        self._level = percent
        for index, lit in enumerate(self._lit):
            self._set(index, lit)

    def close(self):
        self.all_off()
        for pwm in self._pwms:
            pwm.stop()
        self._gpio.cleanup()


def demo(w):
    print("1本ずつ順番に光らせます")
    for number in range(1, len(PINS) + 1):
        print("  %d本目" % number)
        w.show(0)
        w.on(number)
        time.sleep(1)
    print("本数を1本ずつ増やします")
    for count in range(len(PINS) + 1):
        w.show(count)
        time.sleep(0.5)
    print("だんだん暗くして、だんだん明るくします")
    for percent in list(range(100, -1, -10)) + list(range(0, 101, 10)):
        w.brightness(percent)
        time.sleep(0.2)


def main():
    parser = argparse.ArgumentParser(description="ひげLED 6本を制御する")
    parser.add_argument("command", choices=["demo", "on", "show"])
    parser.add_argument("numbers", nargs="*", type=int, help="on: つけるひげの番号 / show: 本数")
    parser.add_argument("--seconds", type=float, default=5, help="つけておく秒数（終わると消える）")
    parser.add_argument("--brightness", type=float, default=100, help="明るさ 0〜100")
    args = parser.parse_args()

    w = Whiskers()
    try:
        w.brightness(args.brightness)
        if args.command == "demo":
            demo(w)
        else:
            if args.command == "on":
                w.on(*args.numbers)
            else:
                w.show(*args.numbers)
            time.sleep(args.seconds)
    except KeyboardInterrupt:
        pass
    finally:
        w.close()


if __name__ == "__main__":
    main()

import time

import RPi.GPIO as GPIO

# ひげLED（バーグラフの20〜25列）につないだピン
WHISKER_PINS = [17, 27, 22, 26, 20, 21]

GPIO.setmode(GPIO.BCM)
for pin in WHISKER_PINS:
    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

try:
    # 1. 1個ずつ順番に光らせて配線を確認する
    print("1個ずつ光らせます")
    for i, pin in enumerate(WHISKER_PINS, 1):
        print("  %d本目（GPIO%d）" % (i, pin))
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(pin, GPIO.LOW)

    # 2. 全部つけてから1個ずつ消す（ひげタイマーの動き）
    print("全部つけて、1秒ごとに1個ずつ消します")
    for pin in WHISKER_PINS:
        GPIO.output(pin, GPIO.HIGH)
    time.sleep(1)
    for i, pin in enumerate(reversed(WHISKER_PINS)):
        GPIO.output(pin, GPIO.LOW)
        print("  残り%d本" % (len(WHISKER_PINS) - i - 1))
        time.sleep(1)

except KeyboardInterrupt:
    pass

finally:
    GPIO.cleanup()

"""LED 1個の配線確認。物理ピン番号を指定して点滅させる

使い方: python3 led_check.py 26   （26番ピンのLEDを確認）
"""
import sys
import time

import RPi.GPIO as GPIO

pin = int(sys.argv[1]) if len(sys.argv) > 1 else 26  # 物理ピン番号

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)  # 物理ピン番号で指定する
GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

try:
    print("%d番ピン: 1秒ごとに点滅（5回）" % pin)
    for _ in range(5):
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(1)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(1)
    print("%d番ピン: つけっぱなし（15秒）" % pin)
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(15)
except KeyboardInterrupt:
    pass
finally:
    GPIO.cleanup()
    print("=== 終了")

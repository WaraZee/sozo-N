import json
import os
import subprocess

import RPi.GPIO as GPIO
from vosk import KaldiRecognizer, Model, SetLogLevel

LED_PIN = 25
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-ja-0.22")
MIC_DEVICE = "plughw:CARD=Device,DEV=0"  # USBマイク（arecord -l で確認）
SAMPLE_RATE = 16000
KEYWORD = "ライト"

SetLogLevel(-1)
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

model = Model(MODEL_PATH)
# 認識する言葉を「ライト」に絞る（それ以外は [unk] になる）
recognizer = KaldiRecognizer(model, SAMPLE_RATE, json.dumps([KEYWORD, "[unk]"], ensure_ascii=False))

mic = subprocess.Popen(
    ["arecord", "-D", MIC_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
     "-c", "1", "-t", "raw", "-q"],
    stdout=subprocess.PIPE,
)

print("「ライト」と言うとLEDが光ります（Ctrl+Cで終了）")

try:
    while True:
        data = mic.stdout.read(4000)
        if not data:
            break
        if recognizer.AcceptWaveform(data):
            text = json.loads(recognizer.Result())["text"]
            if not text:
                continue
            print("認識:", text)
            if KEYWORD in text:
                GPIO.output(LED_PIN, GPIO.HIGH)
                print("→ LED ON")

except KeyboardInterrupt:
    pass

finally:
    mic.terminate()
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.cleanup()

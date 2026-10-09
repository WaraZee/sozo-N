import json
import os
import subprocess

from vosk import KaldiRecognizer, Model, SetLogLevel

from time_parser import format_duration, parse_duration

MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-ja-0.22")
MIC_DEVICE = "plughw:CARD=Device,DEV=0"  # USBマイク（arecord -l で確認）
SAMPLE_RATE = 16000

# 認識する言葉をしぼると数字の聞き間違いが減る（辞書にない語は無視される）
NUMBERS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百",
           "十五", "二十", "三十", "四十", "五十", "六十", "九十",
           "二分", "三分", "十分"]
UNITS = ["分", "ふん", "ぷん", "秒", "時間", "半"]
COMMANDS = ["タイマー", "セット", "ストップ", "キャンセル"]
GRAMMAR = NUMBERS + UNITS + COMMANDS + ["[unk]"]

SetLogLevel(-1)
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, SAMPLE_RATE,
                             json.dumps(GRAMMAR, ensure_ascii=False))

mic = subprocess.Popen(
    ["arecord", "-D", MIC_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
     "-c", "1", "-t", "raw", "-q"],
    stdout=subprocess.PIPE,
)

print("「5分タイマー」「1時間半」などと話しかけてください（Ctrl+Cで終了）")

try:
    while True:
        data = mic.stdout.read(4000)
        if not data:
            break
        if recognizer.AcceptWaveform(data):
            text = json.loads(recognizer.Result())["text"]
            if not text or text == "[unk]":
                continue
            seconds = parse_duration(text)
            if seconds:
                print("認識: %s → %s（%d秒）" % (text, format_duration(seconds), seconds))
            else:
                print("認識: %s → 時間なし" % text)

except KeyboardInterrupt:
    pass

finally:
    mic.terminate()

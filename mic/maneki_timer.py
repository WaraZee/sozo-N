import json
import os
import subprocess
import time

import RPi.GPIO as GPIO
from vosk import KaldiRecognizer, Model, SetLogLevel

from time_parser import format_duration, parse_duration

LED_PIN = 25
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-ja-0.22")
VOICE_PATH = os.path.expanduser("~/models/mei/mei_happy.htsvoice")
DIC_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
MIC_DEVICE = "plughw:CARD=Device,DEV=0"  # USBマイク（arecord -l で確認）
SPEAKER_DEVICE = "plughw:CARD=Headphones,DEV=0"  # ラズパイのイヤホン端子（aplay -l で確認）
SAMPLE_RATE = 16000
LISTEN_SECONDS = 8  # 呼ばれてから時間を待つ長さ

WAKE_WORDS = ["まねきねこ", "招き猫"]
TIME_WORDS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百",
              "十五", "二十", "三十", "四十", "五十", "六十", "九十",
              "二分", "三分", "十分",
              "分", "ふん", "ぷん", "秒", "時間", "半", "タイマー", "セット"]

GREETING = "こんにちは。金子さん。タイマー何分セットする？"
ACCEPTED = "%s、分かりました"
FINISHED = "お疲れ様でした。%s経ちました"


def make_recognizer(model, words):
    return KaldiRecognizer(model, SAMPLE_RATE,
                           json.dumps(words + ["[unk]"], ensure_ascii=False))


def start_mic():
    return subprocess.Popen(
        ["arecord", "-D", MIC_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
         "-c", "1", "-t", "raw", "-q"],
        stdout=subprocess.PIPE,
    )


def speak(text):
    """Open JTalk で音声を作り、スピーカーで再生する"""
    print("ねこ:", text)
    wav = "/tmp/maneki_voice.wav"
    subprocess.run(["open_jtalk", "-x", DIC_PATH, "-m", VOICE_PATH, "-ow", wav],
                   input=text.encode("utf-8"), check=True)
    subprocess.run(["aplay", "-D", SPEAKER_DEVICE, "-q", wav], check=True)


def talk(mic, text):
    """自分の声を聞き取らないよう、マイクを止めてからしゃべり、新しいマイクを返す"""
    mic.terminate()
    speak(text)
    return start_mic()


SetLogLevel(-1)
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

model = Model(MODEL_PATH)
wake_recognizer = make_recognizer(model, WAKE_WORDS)
time_recognizer = make_recognizer(model, TIME_WORDS)

mic = start_mic()
listening_until = None  # None のときは呼びかけ待ち
timer_end = None        # None のときはタイマーが動いていない
timer_label = ""

print("「招き猫」と呼んでください（Ctrl+Cで終了）")

try:
    while True:
        data = mic.stdout.read(4000)
        if not data:
            break

        # タイマー終了
        if timer_end is not None and time.monotonic() >= timer_end:
            GPIO.output(LED_PIN, GPIO.LOW)
            print("→ タイマー終了、LED OFF")
            timer_end = None
            mic = talk(mic, FINISHED % timer_label)
            wake_recognizer.Reset()
            time_recognizer.Reset()
            continue

        if listening_until is None:
            # 呼びかけ待ち
            if not wake_recognizer.AcceptWaveform(data):
                continue
            text = json.loads(wake_recognizer.Result())["text"]
            if not any(word in text for word in WAKE_WORDS):
                continue
            print("認識:", text)
            mic = talk(mic, GREETING)
            time_recognizer.Reset()
            listening_until = time.monotonic() + LISTEN_SECONDS

        else:
            # 時間の聞き取り中
            if time.monotonic() > listening_until:
                print("時間が聞き取れなかったので、呼びかけ待ちに戻ります")
                wake_recognizer.Reset()
                listening_until = None
                continue
            if not time_recognizer.AcceptWaveform(data):
                continue
            text = json.loads(time_recognizer.Result())["text"]
            seconds = parse_duration(text)
            if not seconds:
                continue
            timer_label = format_duration(seconds)
            print("認識: %s → %d秒" % (text, seconds))
            mic = talk(mic, ACCEPTED % timer_label)

            # しゃべり終わってからタイマー開始
            GPIO.output(LED_PIN, GPIO.HIGH)
            print("→ LED ON（%s）" % timer_label)
            timer_end = time.monotonic() + seconds

            wake_recognizer.Reset()
            listening_until = None

except KeyboardInterrupt:
    pass

finally:
    mic.terminate()
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.cleanup()

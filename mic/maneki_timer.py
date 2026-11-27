import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sleep_watch"))
import phone_finder  # noqa: E402
from hello_maneki_phone import Phone, speak_command  # noqa: E402
from time_parser import format_duration, parse_duration
from whiskers import lit_count

LED_PIN = 25
WHISKER_PINS = [17, 27, 16, 26, 20, 21]  # ひげLED（物理ピン 11/13/36/37/38/40、15番は Build HAT が使う）
MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-ja-0.22")
MIC_DEVICE = "plughw:CARD=Device,DEV=0"  # USBマイク（arecord -l で確認）
SAMPLE_RATE = 16000
LISTEN_SECONDS = 10  # 呼ばれてから時間を待つ長さ

WAKE_WORDS = ["まねきねこ", "招き猫"]
TIME_WORDS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百",
              "十五", "二十", "三十", "四十", "五十", "六十", "九十",
              "二分", "三分", "十分",
              "分", "ふん", "ぷん", "秒", "時間", "半", "タイマー", "セット"]

GREETING = "こんにちは。タイマー何分セットする？"
ACCEPTED = "%s、分かりました"
FINISHED = "お疲れ様でした。%s経ちました"
READY_MESSAGE = "起動しました"


def make_recognizer(model, words, recognizer_factory):
    return recognizer_factory(model, SAMPLE_RATE,
                              json.dumps(words + ["[unk]"], ensure_ascii=False))


def start_mic():
    return subprocess.Popen(
        ["arecord", "-D", MIC_DEVICE, "-f", "S16_LE", "-r", str(SAMPLE_RATE),
         "-c", "1", "-t", "raw", "-q"],
        stdout=subprocess.PIPE,
    )


def speak(text, phone):
    """スマホのスピーカーで読み上げる"""
    print("ねこ:", text)
    result = phone.run(speak_command(text), 30)
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        if not detail:
            detail = "終了コード %d" % result.returncode
        raise RuntimeError("スマホの読み上げに失敗しました: %s" % detail)


def show_whiskers(gpio, n):
    """ひげを左から n 本つけ、残りを消す"""
    for i, pin in enumerate(WHISKER_PINS):
        gpio.output(pin, gpio.HIGH if i < n else gpio.LOW)


def talk(mic, text, phone, mic_factory=start_mic):
    """自分の声を聞き取らないよう、マイクを止めてからしゃべり、新しいマイクを返す"""
    mic.terminate()
    mic.wait()
    speak(text, phone)
    return mic_factory()


def run_timer(gpio, phone, wake_recognizer, time_recognizer, mic_factory=start_mic):
    mic = mic_factory()
    listening_until = None
    timer_end = None
    timer_total = 0
    timer_label = ""
    whiskers_on = 0

    try:
        mic = talk(mic, READY_MESSAGE, phone, mic_factory)
        print("「招き猫」と呼んでください（Ctrl+Cで終了）")
        while True:
            data = mic.stdout.read(4000)
            if not data:
                break

            if timer_end is not None:
                n = lit_count(timer_end - time.monotonic(), timer_total, len(WHISKER_PINS))
                if n != whiskers_on:
                    show_whiskers(gpio, n)
                    whiskers_on = n
                    print("  ひげ残り%d本" % n)

            if timer_end is not None and time.monotonic() >= timer_end:
                gpio.output(LED_PIN, gpio.LOW)
                print("→ タイマー終了、LED OFF")
                timer_end = None
                mic = talk(mic, FINISHED % timer_label, phone, mic_factory)
                wake_recognizer.Reset()
                time_recognizer.Reset()
                continue

            if listening_until is None:
                if not wake_recognizer.AcceptWaveform(data):
                    continue
                text = json.loads(wake_recognizer.Result())["text"]
                if not any(word in text for word in WAKE_WORDS):
                    continue
                print("認識:", text)
                mic = talk(mic, GREETING, phone, mic_factory)
                time_recognizer.Reset()
                listening_until = time.monotonic() + LISTEN_SECONDS
                continue

            timed_out = time.monotonic() > listening_until
            if time_recognizer.AcceptWaveform(data):
                text = json.loads(time_recognizer.Result())["text"]
            elif timed_out:
                # 制限時間直前に話していた場合、そこまでの認識結果で判定する。
                text = json.loads(time_recognizer.FinalResult())["text"]
            else:
                continue
            seconds = parse_duration(text)
            if text:
                print("聞き取り: %s → %s" % (text, "%d秒" % seconds if seconds else "時間なし"))
            if not seconds:
                if timed_out:
                    print("時間が聞き取れなかったので、呼びかけ待ちに戻ります")
                    wake_recognizer.Reset()
                    listening_until = None
                continue

            timer_label = format_duration(seconds)
            print("認識: %s → %d秒" % (text, seconds))
            mic = talk(mic, ACCEPTED % timer_label, phone, mic_factory)
            # 確認音声が終わってからカウントを開始する。
            gpio.output(LED_PIN, gpio.HIGH)
            show_whiskers(gpio, len(WHISKER_PINS))
            whiskers_on = len(WHISKER_PINS)
            print("→ LED ON、ひげ%d本（%s）" % (whiskers_on, timer_label))
            timer_total = seconds
            timer_end = time.monotonic() + seconds
            wake_recognizer.Reset()
            listening_until = None
    except KeyboardInterrupt:
        pass
    finally:
        mic.terminate()
        gpio.output(LED_PIN, gpio.LOW)
        show_whiskers(gpio, 0)


def main():
    import RPi.GPIO as GPIO
    from vosk import KaldiRecognizer, Model, SetLogLevel

    host = phone_finder.locate()
    if host is None:
        raise SystemExit("スマホが見つかりません。Termux を開いて sshd を起動してください")
    phone = Phone(host)
    print("スマホスピーカー:", host)

    SetLogLevel(-1)
    GPIO.setmode(GPIO.BCM)
    try:
        GPIO.setup(LED_PIN, GPIO.OUT)
        for pin in WHISKER_PINS:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

        model = Model(MODEL_PATH)
        wake_recognizer = make_recognizer(model, WAKE_WORDS, KaldiRecognizer)
        time_recognizer = make_recognizer(model, TIME_WORDS, KaldiRecognizer)
        run_timer(GPIO, phone, wake_recognizer, time_recognizer)
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()

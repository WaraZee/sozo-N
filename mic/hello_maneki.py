import json
import os
import subprocess

from vosk import KaldiRecognizer, Model, SetLogLevel

MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-ja-0.22")
VOICE_PATH = os.path.expanduser("~/models/mei/mei_happy.htsvoice")
DIC_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
MIC_DEVICE = "plughw:CARD=Device,DEV=0"  # USBマイク（arecord -l で確認）
SPEAKER_DEVICE = "plughw:CARD=Headphones,DEV=0"  # ラズパイのイヤホン端子（aplay -l で確認）
SAMPLE_RATE = 16000

WAKE_WORDS = ["まねきねこ", "招き猫"]
REPLY = "こんにちは。私は招き猫です"


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


SetLogLevel(-1)
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, SAMPLE_RATE,
                             json.dumps(WAKE_WORDS + ["[unk]"], ensure_ascii=False))

mic = start_mic()
print("「招き猫」と呼んでください（Ctrl+Cで終了）")

try:
    while True:
        data = mic.stdout.read(4000)
        if not data:
            break
        if not recognizer.AcceptWaveform(data):
            continue
        text = json.loads(recognizer.Result())["text"]
        if not any(word in text for word in WAKE_WORDS):
            continue
        print("認識:", text)
        # 自分の声（「招き猫です」）を聞き取らないよう、しゃべる間はマイクを止める
        mic.terminate()
        speak(REPLY)
        mic = start_mic()
        recognizer.Reset()

except KeyboardInterrupt:
    pass

finally:
    mic.terminate()

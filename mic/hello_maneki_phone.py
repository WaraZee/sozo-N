"""hello_maneki.py のスマホ版。スマホのマイクで「招き猫」を聞き取り、スマホのスピーカーで返事する

スマホで3秒ずつ録音して Pi に送り、Pi の Vosk で聞き取る（ネットは要らない）。
Termux からスマホの音声認識（termux-speech-to-text）を呼ぶ方法は、この機種ではすぐ空で終わってしまい使えなかった。

スマホで Termux を開いて sshd を打ってから、Pi で python3 hello_maneki_phone.py
初めてのときは、スマホの「設定→アプリ→Termux:API→権限→マイク」を許可しておく。
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sleep_watch"))
import phone_finder  # noqa: E402

MODEL_PATH = os.path.expanduser("~/models/vosk-model-small-ja-0.22")
SAMPLE_RATE = 16000
WAKE_WORDS = ["まねきねこ", "招き猫"]
REPLY = "こんにちは。私は招き猫です"
CHUNK_SECONDS = 3  # 1回に録音する長さ
SPEAK_LIMIT = 25   # 読み上げがこれより長くかかったら打ち切る


def is_wake_word(text):
    return any(word in text for word in WAKE_WORDS)


class WakeListener:
    """録音を続けて流し込み、「招き猫」と聞こえたら True を返す"""

    def __init__(self, recognizer):
        self.recognizer = recognizer
        self.last_text = ""  # 直前に聞き取った言葉（確認用）

    def feed(self, pcm):
        if self.recognizer.AcceptWaveform(pcm):
            text = json.loads(self.recognizer.Result())["text"]
        else:
            # 録音の切れ目で言い終わっていなくても反応できるよう、途中経過も見る
            text = json.loads(self.recognizer.PartialResult())["partial"]
        self.last_text = text
        if is_wake_word(text):
            self.recognizer.Reset()
            return True
        return False


def speak_command(text):
    """スマホで text を読み上げるコマンド
    途中で止めると読み上げがスマホに残って固まり、そのあと何もしゃべらなくなった（2026-11-06）ので、
    スマホの側でも SPEAK_LIMIT 秒で打ち切る"""
    return "timeout %d termux-tts-speak '%s'" % (SPEAK_LIMIT, text)


def record_command(seconds):
    """スマホで seconds 秒録音して、m4a を出力するコマンド
    録音の時間がたってもすぐにはファイルが書き終わらない（0.4秒待ちでは壊れていた）ので、
    スマホが録音を終えたのを確かめてから出力する"""
    return ("f=~/maneki/chunk.m4a; rm -f $f; termux-microphone-record -l %d -f $f >/dev/null; sleep %d; "
            "for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do "
            "termux-microphone-record -i | grep -q '\"isRecording\": true' || break; sleep 0.2; done; "
            "sleep 0.3; cat $f" % (seconds, seconds))


class Phone:
    def __init__(self, host):
        self.host = host

    def run(self, command, timeout):
        # SSH のつなぎ直しを省く ControlMaster は、出力の受け取りが終わらなくなるので使わない
        args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-p", str(phone_finder.PHONE_PORT),
                self.host, command]
        try:
            return subprocess.run(args, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            # スマホが返事をしなくても止まらず、録音できなかった扱いで続ける
            print("（スマホが%d秒たっても終わりませんでした）" % timeout)
            self.stop_recording_quietly()
            return subprocess.CompletedProcess(args, 1, b"", b"")

    def stop_recording_quietly(self):
        try:
            subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-p",
                            str(phone_finder.PHONE_PORT), self.host, "termux-microphone-record -q"],
                           capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            pass

    def record(self, seconds=CHUNK_SECONDS):
        """seconds 秒録音して、m4a のデータを返す"""
        return self.run(record_command(seconds), seconds + 20).stdout

    def say(self, text):
        self.run(speak_command(text), 30)

    def say_and_record(self, text, seconds):
        """しゃべり終わったらすぐ録音する（別々に呼ぶと、つなぎ直す1〜2秒の間に言われた言葉を逃す）"""
        return self.run("%s; %s" % (speak_command(text), record_command(seconds)), seconds + 40).stdout

    def stop_recording(self):
        self.run("termux-microphone-record -q >/dev/null 2>&1", 10)


def to_pcm(m4a):
    """m4a を Vosk が読める 16kHz・モノラルの生データにする
    m4a は最後まで読まないと中身が分からないので、パイプでは渡せず一度ファイルにする"""
    with tempfile.NamedTemporaryFile(suffix=".m4a") as f:
        f.write(m4a)
        f.flush()
        return subprocess.run(["ffmpeg", "-loglevel", "error", "-i", f.name, "-ar", str(SAMPLE_RATE),
                               "-ac", "1", "-f", "s16le", "pipe:1"], capture_output=True).stdout


def main():
    from vosk import KaldiRecognizer, Model, SetLogLevel

    verbose = "--verbose" in sys.argv  # 3秒ごとに、何が聞こえたかを表示する

    host = phone_finder.locate()
    if host is None:
        raise SystemExit("スマホが見つかりません。スマホで Termux を開いて sshd を打ってください")
    print("スマホ:", host)
    phone = Phone(host)

    SetLogLevel(-1)
    recognizer = KaldiRecognizer(Model(MODEL_PATH), SAMPLE_RATE,
                                 json.dumps(WAKE_WORDS + ["[unk]"], ensure_ascii=False))
    listener = WakeListener(recognizer)
    print("スマホに向かって「招き猫」と呼んでください（Ctrl+Cで終了）")

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        next_chunk = pool.submit(phone.record)
        while True:
            m4a = next_chunk.result()
            next_chunk = pool.submit(phone.record)  # 聞き取っている間に、次の3秒を録音しておく
            if not m4a:
                print("（録音できませんでした。マイクの権限か、スマホの Termux を確認してください）")
                continue
            pcm = to_pcm(m4a)
            woke = listener.feed(pcm)
            if verbose:
                print("%s  %.1f秒の音 → 「%s」" % (time.strftime("%H:%M:%S"), len(pcm) / 2 / SAMPLE_RATE,
                                                 listener.last_text))
            if woke:
                print("ねこ:", REPLY)
                phone.say(REPLY)
                next_chunk.result()  # 返事の間に録った音は、自分の声が入っているので捨てる
                next_chunk = pool.submit(phone.record)
    except KeyboardInterrupt:
        pass
    finally:
        pool.shutdown(wait=False)
        phone.stop_recording()


if __name__ == "__main__":
    main()

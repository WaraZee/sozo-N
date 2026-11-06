"""maneki_timer.py のスマホ版。スマホに「招き猫」と呼ぶと時間を聞き、ひげLED 6本で残り時間を見せる

  「招き猫」→ ねこ「こんにちは。タイマー何分セットする？」→「18秒」など →
  ひげが6本つき、時間がたつごとに1本ずつ消える → 終わるとスマホで「お疲れ様でした」

聞き取りとスマホとのやりとりは hello_maneki_phone.py と同じ（スマホで録音し、Pi の Vosk で聞き取る）。
スマホで Termux を開いて sshd を打ってから、Pi で python3 maneki_timer_phone.py [--verbose]
"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "whisker"))
from hello_maneki_phone import MODEL_PATH, SAMPLE_RATE, WAKE_WORDS, Phone, WakeListener, to_pcm  # noqa: E402
from time_parser import format_duration, parse_duration  # noqa: E402
from whiskers import lit_count  # noqa: E402



def kanji_number(n):
    """1〜99 を漢数字にする（例: 18 → 十八、30 → 三十）"""
    digits = "一二三四五六七八九"
    tens, ones = divmod(n, 10)
    text = ""
    if tens:
        text += ("" if tens == 1 else digits[tens - 1]) + "十"
    if ones:
        text += digits[ones - 1]
    return text


# 言われそうな数（1〜60、九十、百、百二十）と単位。どれも Vosk の辞書にあるのを 2026-11-06 に確かめた
TIME_WORDS = ([kanji_number(n) for n in range(1, 61)] + ["九十", "百", "百二十"] +
              ["二分", "三分", "十分", "分", "ふん", "ぷん", "秒", "時間", "半", "タイマー", "セット"])
WHISKER_COUNT = 6
GREETING = "こんにちは。タイマー何分セットする？"
RETRY = "もう一度、時間を言ってください"
ACCEPTED = "%sですね、分かりました！"
FINISHED = "お疲れ様でした。%s経ちました"
TIME_RECORD_SECONDS = 6  # 時間を聞くときは、言い切れるよう長めに録る
TIME_TRIES = 2           # 聞き取れなかったら、もう一度だけ聞く


def hear_duration(recognizer, pcm):
    """録った音を最後まで聞き取って (聞こえた言葉, 秒数) を返す。時間がなければ秒数は None"""
    recognizer.AcceptWaveform(pcm)
    text = json.loads(recognizer.FinalResult())["text"]  # FinalResult で次の聞き取りはやり直しになる
    return text, parse_duration(text)


class WhiskerTimer:
    """ひげで残り時間を見せるタイマー。聞き取りを止めないよう、別のスレッドで動かす"""

    def __init__(self, whiskers, on_finish, clock=time.monotonic, sleep=time.sleep):
        self.whiskers = whiskers
        self.on_finish = on_finish
        self.clock = clock
        self.sleep = sleep
        self.generation = 0  # start や cancel のたびに増やし、古いタイマーを止める

    def start(self, seconds):
        self.generation += 1
        threading.Thread(target=self.run, args=(self.generation, seconds), daemon=True).start()

    def cancel(self):
        self.generation += 1

    def run(self, generation, seconds):
        end = self.clock() + seconds
        shown = None
        while generation == self.generation:
            remaining = end - self.clock()
            count = lit_count(remaining, seconds, WHISKER_COUNT)
            if count != shown:
                self.whiskers.show(count)
                shown = count
                print("%s  ひげ残り%d本" % (time.strftime("%H:%M:%S"), count))
            if remaining <= 0:
                self.on_finish(seconds)
                return
            self.sleep(0.1)


def main():
    from vosk import KaldiRecognizer, Model, SetLogLevel
    from whisker_led import Whiskers
    import phone_finder

    verbose = "--verbose" in sys.argv  # 何が聞こえたかを毎回表示する

    host = phone_finder.locate()
    if host is None:
        raise SystemExit("スマホが見つかりません。スマホで Termux を開いて sshd を打ってください")
    print("スマホ:", host)
    phone = Phone(host)

    def say(text):
        print("ねこ:", text)
        phone.say(text)

    SetLogLevel(-1)
    model = Model(MODEL_PATH)
    listener = WakeListener(KaldiRecognizer(model, SAMPLE_RATE,
                                            json.dumps(WAKE_WORDS + ["[unk]"], ensure_ascii=False)))
    time_recognizer = KaldiRecognizer(model, SAMPLE_RATE, json.dumps(TIME_WORDS + ["[unk]"], ensure_ascii=False))
    whiskers = Whiskers()
    timer = WhiskerTimer(whiskers, lambda seconds: say(FINISHED % format_duration(seconds)))
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
            woke = listener.feed(to_pcm(m4a))
            if verbose:
                print("%s  「%s」" % (time.strftime("%H:%M:%S"), listener.last_text))
            if not woke:
                continue

            print("%s  呼ばれた" % time.strftime("%H:%M:%S"))
            # 次の3秒の録音はもう始まっているので、止めて捨ててから聞く（マイクは同時に1つしか使えない）
            phone.stop_recording()
            next_chunk.result()
            seconds = None
            for attempt in range(TIME_TRIES):
                prompt = GREETING if attempt == 0 else RETRY
                print("ねこ:", prompt)
                m4a = phone.say_and_record(prompt, TIME_RECORD_SECONDS)
                text, seconds = hear_duration(time_recognizer, to_pcm(m4a))
                print("聞き取り: 「%s」 → %s" % (text, "%d秒" % seconds if seconds else "時間なし"))
                if seconds:
                    break
            if seconds:
                say(ACCEPTED % format_duration(seconds))
                timer.start(seconds)  # しゃべり終わってからタイマー開始
            else:
                print("時間が聞き取れなかったので、呼びかけ待ちに戻ります")
            next_chunk = pool.submit(phone.record)
    except KeyboardInterrupt:
        pass
    finally:
        timer.cancel()
        pool.shutdown(wait=False)
        phone.stop_recording()
        whiskers.close()


if __name__ == "__main__":
    main()

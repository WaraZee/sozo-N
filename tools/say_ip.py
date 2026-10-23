"""起動したら IP アドレスをスピーカーで読み上げる（モニターなしで SSH 先を知るため）"""
import os
import subprocess
import time

VOICE_PATH = os.path.expanduser("~sozo/models/mei/mei_happy.htsvoice")
DIC_PATH = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
SPEAKER_DEVICE = "plughw:CARD=Headphones,DEV=0"
WAIT_SECONDS = 90  # Wi-Fi につながるのを待つ長さ
REPEAT = 2


def get_ip():
    out = subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.split()
    return next((ip for ip in out if "." in ip), None)


def speak(text):
    wav = "/tmp/say_ip.wav"
    subprocess.run(["open_jtalk", "-x", DIC_PATH, "-m", VOICE_PATH, "-ow", wav],
                   input=text.encode("utf-8"), check=True)
    subprocess.run(["aplay", "-D", SPEAKER_DEVICE, "-q", wav], check=True)


def ip_to_speech(ip):
    """10.27.72.18 → 「10、てん、27、てん、72、てん、18」"""
    return "、てん、".join(ip.split("."))


end = time.monotonic() + WAIT_SECONDS
ip = get_ip()
while ip is None and time.monotonic() < end:
    time.sleep(2)
    ip = get_ip()

if ip is None:
    text = "ネットワークにつながっていません"
else:
    text = "アイピーアドレスは、%sです" % ip_to_speech(ip)
print(text)
for _ in range(REPEAT):
    speak(text)
    time.sleep(1)

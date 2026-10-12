import re

KANJI_DIGITS = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
                "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
KANJI_UNITS = {"十": 10, "百": 100, "千": 1000}
UNIT_SECONDS = {"時間": 3600, "分": 60, "秒": 1}
ZENKAKU = str.maketrans("０１２３４５６７８９", "0123456789")


def kanji_to_int(text):
    """漢数字を整数にする（例: 二十五 → 25, 百二十 → 120）"""
    total = 0
    current = 0
    for ch in text:
        if ch in KANJI_DIGITS:
            current = current * 10 + KANJI_DIGITS[ch]
        else:
            total += (current or 1) * KANJI_UNITS[ch]
            current = 0
    return total + current


def normalize(text):
    # [unk] をまたいで数字がつながらないよう区切りを入れてから空白を消す
    text = text.replace("[unk]", "|").replace(" ", "")
    text = text.translate(ZENKAKU)
    text = text.replace("ふん", "分").replace("ぷん", "分")
    return re.sub("[〇一二三四五六七八九十百千]+",
                  lambda m: str(kanji_to_int(m.group())), text)


def parse_duration(text):
    """音声認識の結果から時間を読み取り、秒数で返す。見つからなければ None"""
    seconds = 0
    found = False
    for number, unit, half in re.findall(r"(\d+)(時間|分|秒)(半)?", normalize(text)):
        seconds += int(number) * UNIT_SECONDS[unit]
        if half:
            seconds += UNIT_SECONDS[unit] // 2
        found = True
    return seconds if found else None


def format_duration(seconds):
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    parts = []
    if h:
        parts.append("%d時間" % h)
    if m:
        parts.append("%d分" % m)
    if s:
        parts.append("%d秒" % s)
    return "".join(parts) or "0秒"

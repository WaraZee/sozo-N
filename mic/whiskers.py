import math


def lit_count(remaining, total, count):
    """残り時間から、つけておくひげの本数を返す（total/count 秒ごとに1本ずつ減る）"""
    if remaining <= 0:
        return 0
    return min(count, math.ceil(remaining * count / total))

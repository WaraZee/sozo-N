"""「寝ている」の判定を4案用意して、比べられるようにする（1つに決めたら残りは消す）

どの案も update(now, camera, heart) に最新の状態を渡すと、寝ているかどうかを返す。
  camera: {"time": 時刻, "eye_state": "open"/"closed"/"no_face"/..., "closed_seconds": 秒}（なければ None）
  heart:  {"time": 時刻, "state": "calibrating"/"awake"/"sleepy"}（なければ None）
秒数や割合は仮の値。検証の記録を replay.py に通して決める。
"""
STALE_SECONDS = 10  # これより古いデータは使わない


class Judge:
    name = ""

    def _fresh(self, data, now):
        return data is not None and now - data["time"] <= STALE_SECONDS

    def _closed_seconds(self, now, camera):
        return camera["closed_seconds"] if self._fresh(camera, now) else 0.0

    def _heart_low(self, now, heart):
        return self._fresh(heart, now) and heart["state"] == "sleepy"

    def update(self, now, camera, heart):
        raise NotImplementedError


class BothJudge(Judge):
    """案1: 目を10秒閉じて、かつ心拍が下がっている"""
    name = "案1 両方"

    def update(self, now, camera, heart):
        return self._closed_seconds(now, camera) >= 10 and self._heart_low(now, heart)


class EitherJudge(Judge):
    """案2: 目を10秒閉じている、または心拍が下がっている"""
    name = "案2 どちらか"

    def update(self, now, camera, heart):
        return self._closed_seconds(now, camera) >= 10 or self._heart_low(now, heart)


class CombinedJudge(Judge):
    """案3: 心拍が下がっていれば少しの閉眼やうつむきで、ふつうなら長い閉眼で判定する"""
    name = "案3 組み合わせ"
    CLOSED_WHEN_LOW = 3
    CLOSED_WHEN_NORMAL = 30
    NO_FACE_WHEN_LOW = 10

    def __init__(self):
        self._no_face_since = None

    def update(self, now, camera, heart):
        if self._fresh(camera, now) and camera["eye_state"] == "no_face":
            if self._no_face_since is None:
                self._no_face_since = now
        else:
            self._no_face_since = None

        closed = self._closed_seconds(now, camera)
        if not self._heart_low(now, heart):
            return closed >= self.CLOSED_WHEN_NORMAL
        no_face = 0 if self._no_face_since is None else now - self._no_face_since
        return closed >= self.CLOSED_WHEN_LOW or no_face >= self.NO_FACE_WHEN_LOW


class ClosedRatioJudge(Judge):
    """案4: 直近60秒のうち、目を閉じていた時間が半分以上（心拍は使わない）"""
    name = "案4 閉じている割合"
    WINDOW = 60
    CLOSED_TOTAL = 30

    def __init__(self):
        self._segments = []  # 目を閉じていた (始まり, 終わり)
        self._last_time = None
        self._last_closed = False

    def update(self, now, camera, heart):
        if self._last_closed and now - self._last_time <= STALE_SECONDS:
            self._segments.append((self._last_time, now))
        self._last_time = now
        self._last_closed = self._fresh(camera, now) and camera["eye_state"] == "closed"

        start = now - self.WINDOW
        self._segments = [s for s in self._segments if s[1] > start]
        return sum(end - max(begin, start) for begin, end in self._segments) >= self.CLOSED_TOTAL


JUDGES = {"1": BothJudge, "2": EitherJudge, "3": CombinedJudge, "4": ClosedRatioJudge}

"""カメラ（目を閉じている時間）とバンド（心拍数）の2つから居眠りを判定する

企画書どおり「目を閉じて10秒以上」かつ「心拍数が下がった」ときに起こす。
止めるのは、目を開けたのがカメラで確かめられたとき。
心拍数は60秒平均で見ているので戻るのが遅く、止める判定には使わない。
"""


class SleepFusion:
    """
    update() に、カメラとバンドの最新の状態（dict。なければ None）を渡す。
      camera: {"time": 書いた時刻, "eye_state": "open"/"closed"/..., "closed_seconds": 秒}
      heart:  {"time": 書いた時刻, "state": "calibrating"/"awake"/"sleepy"}
    戻り値は "wake"（起こす）、"stop"（止める）、None（そのまま）。
    """

    def __init__(self, closed_seconds=10, open_seconds=2, stale_seconds=10):
        self.closed_seconds = closed_seconds  # これだけ目を閉じ続けたら居眠りの疑い
        self.open_seconds = open_seconds      # これだけ目を開け続けたら起きた
        self.stale_seconds = stale_seconds    # これより古いデータは使わない
        self.alarming = False
        self._open_since = None

    def _fresh(self, data, now):
        return data is not None and now - data["time"] <= self.stale_seconds

    def eyes_closed(self, now, camera):
        return self._fresh(camera, now) and camera["closed_seconds"] >= self.closed_seconds

    def heart_low(self, now, heart):
        return self._fresh(heart, now) and heart["state"] == "sleepy"

    def update(self, now, camera, heart):
        if not self.alarming:
            if self.eyes_closed(now, camera) and self.heart_low(now, heart):
                self.alarming = True
                self._open_since = None
                return "wake"
            return None

        if self._fresh(camera, now) and camera["eye_state"] == "open":
            if self._open_since is None:
                self._open_since = now
            if now - self._open_since >= self.open_seconds:
                self.alarming = False
                self._open_since = None
                return "stop"
        elif self._fresh(camera, now):
            self._open_since = None  # また目を閉じたので数え直す
        return None

"""「寝ている」の判定（2026-11-06 に4案を比べて、案3「組み合わせ」に決めた）

  心拍が下がっている … 目を3秒閉じる、または顔が10秒見えなければ寝ている
  心拍がふつう・バンドのデータがない・外した … 目を20秒閉じたら寝ている

決めた理由（場面 A 作業 / B 目を5秒・伸び / C 目を15秒休む / D 席を立つ / E 寝る の記録を replay.py で比べた）:
  ・A〜D で鳴らず、E で鳴ったのは案3だけだった
      案1 両方（目10秒かつ心拍）… E で鳴らない
      案2 どちらか（目10秒か心拍）… A と C で鳴る
      案4 閉じている割合（60秒中30秒）… C で鳴る
  ・ふつうのときの秒数: C では「15秒閉じて」と頼んでも16.8秒閉じていたので、15秒だと鳴ってしまう。
    20秒なら C で鳴らず、E では30秒のときより10秒早く鳴る

update(now, camera, heart) に最新の状態を渡すと、寝ているかどうかを返す。
  camera: {"time": 時刻, "eye_state": "open"/"closed"/"no_face"/..., "closed_seconds": 秒}（なければ None）
  heart:  {"time": 時刻, "state": "calibrating"/"awake"/"sleepy"/"no_reading"}（なければ None）
"""
STALE_SECONDS = 10  # これより古いデータは使わない


def is_fresh(data, now):
    return data is not None and now - data["time"] <= STALE_SECONDS


class SleepJudge:
    name = "案3 組み合わせ"
    CLOSED_WHEN_LOW = 3      # 心拍が下がっているとき、目を何秒閉じたら寝ているか
    CLOSED_WHEN_NORMAL = 20  # 心拍がふつうのとき
    NO_FACE_WHEN_LOW = 10    # 心拍が下がっているとき、顔が何秒見えなければ寝ているか（うつむき）

    def __init__(self):
        self._no_face_since = None

    def update(self, now, camera, heart):
        if is_fresh(camera, now) and camera["eye_state"] == "no_face":
            if self._no_face_since is None:
                self._no_face_since = now
        else:
            self._no_face_since = None

        closed = camera["closed_seconds"] if is_fresh(camera, now) else 0.0
        heart_low = is_fresh(heart, now) and heart["state"] == "sleepy"
        if not heart_low:
            return closed >= self.CLOSED_WHEN_NORMAL
        no_face = 0 if self._no_face_since is None else now - self._no_face_since
        return closed >= self.CLOSED_WHEN_LOW or no_face >= self.NO_FACE_WHEN_LOW

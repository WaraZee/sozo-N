"""寝ていると判定されたらモーターとスマホ（バンド）を鳴らし、スマホの通知を押したら止める"""


class Alarm:
    """
    motor: start() / stop()
    phone: wake() / stop() / is_ringing()
      wake() は呼び出しが最後まで終わったら True を返す
      is_ringing() は 鳴っている True、止まった False、分からない None を返す
    update() の戻り値は "start"、"released"（通知で止まった）、"timeout"、None
    """

    def __init__(self, motor, phone, max_seconds=300, quiet_seconds=60, check_every=2):
        self.motor = motor
        self.phone = phone
        self.max_seconds = max_seconds      # だれも止めなくてもこれで止める（スマホ側と同じ5分）
        self.quiet_seconds = quiet_seconds  # 止めた直後は心拍がまだ低いので、しばらく鳴らさない
        self.check_every = check_every      # 通知が押されたかをスマホに聞く間隔
        self.ringing = False
        self._seen_ringing = False  # スマホが鳴っているのを確かめたか
        self._started = None
        self._next_check = None
        self._quiet_until = None

    def update(self, now, sleeping):
        if not self.ringing:
            if sleeping and (self._quiet_until is None or now >= self._quiet_until):
                self.ringing = True
                self._started = now
                self._next_check = now + self.check_every
                self.motor.start()
                # 呼び出しが時間切れだと、スマホの印がまだできていないことがあるので、
                # 印が一度見えるまでは「印がない＝通知が押された」とみなさない
                self._seen_ringing = self.phone.wake() is True
                return "start"
            return None

        if now - self._started >= self.max_seconds:
            self._finish(now)
            self.phone.stop()
            return "timeout"
        if now >= self._next_check:
            self._next_check = now + self.check_every
            ringing = self.phone.is_ringing()
            if ringing:
                self._seen_ringing = True
            elif ringing is False and self._seen_ringing:
                self._finish(now)
                return "released"
        return None

    def _finish(self, now):
        self.ringing = False
        self._quiet_until = now + self.quiet_seconds
        self.motor.stop()

    def shutdown(self):
        """プログラムを終えるとき。モーターは必ず止める"""
        was_ringing = self.ringing
        self.ringing = False
        self.motor.stop()
        if was_ringing:
            self.phone.stop()

"""Build HATモーターの共通部品。接続するまでは実機を操作しない。"""

import math
import time

MOTOR_PORT = "A"
MOTOR_SPEED = 20


class MotorController:
    def __init__(self, motor, speed=MOTOR_SPEED):
        if not math.isfinite(speed) or not 0 < abs(speed) <= 100:
            raise ValueError("speed must be between -100 and 100, excluding 0")
        self.motor = motor
        self.speed = speed
        self.running = False

    @classmethod
    def connect(cls, port=MOTOR_PORT, speed=MOTOR_SPEED):
        try:
            from buildhat import Hat, Motor
        except ImportError as exc:
            raise RuntimeError(
                "Build HAT library unavailable. Install buildhat in the active Python environment."
            ) from exc
        hat = Hat()
        voltage = hat.get_vin()
        print(f"Build HAT power: {voltage:.1f} V")
        if not math.isfinite(voltage) or voltage < 7.2:
            raise RuntimeError("Build HAT motor power is missing or too low (minimum 7.2 V)")
        controller = cls(Motor(port), speed)
        controller.stop()
        return controller

    def start(self):
        """停止するまで連続回転。繰り返し呼んでも開始命令は一度だけ。"""
        if not self.running:
            self.running = True
            try:
                self.motor.start(speed=self.speed)
            except BaseException:
                self.stop()
                raise
            print(f"MOTOR: started (speed {self.speed})")

    def stop(self):
        """停止命令を送る。既に停止中でも送信する。"""
        self.motor.stop()
        self.running = False
        print("MOTOR: stopped")

    def run_for_seconds(self, seconds):
        """指定秒数回して停止。この呼び出し中は呼び出し元が待機する。"""
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("seconds must be finite and greater than 0")
        try:
            self.start()
            time.sleep(seconds)
        finally:
            self.stop()


class SleepMotor(MotorController):
    """睡眠判定を、共通の開始・停止操作に変換する。"""

    def update(self, state):
        if state == "POSSIBLE_SLEEP":
            self.start()
        elif self.running:
            self.stop()

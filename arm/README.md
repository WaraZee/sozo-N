# モーター制御

`motor_control.py` にBuild HATの共通処理をまとめています。
標準設定は **Aポート・速度20** です。モーター用の外部電源が必要です。
`motor_test.py` は従来の「90度回して戻す」単体テストとして残しています。

## 共通部品の使い方

リポジトリのルートから実行するPythonコードの例です。

```python
from arm.motor_control import MotorController

motor = MotorController.connect()
try:
    motor.run_for_seconds(3)  # 例：3秒回して停止。終わるまで待機する。
    # motor.start()          # 連続回転する場合はこちら。
    # motor.stop()           # 連続回転を止める。
finally:
    motor.stop()
```

`start()` は一方向に連続回転します。腕を往復させる動作ではありません。
睡眠判定では `SleepMotor.update(state)` が `POSSIBLE_SLEEP` の間に回転させ、
目が開く・顔が見えない・判定不明など、他の状態になったら停止します。

## カメラから使う

Raspberry Piで、リポジトリのルートから実行します。
有効なPython環境に `buildhat` が必要です。

```bash
source ~/camera-env/bin/activate
python camera_motor/camera_sleep.py --headless
```

モーターを使わない場合は `--no-motor` を追加します。
通常終了・Ctrl+C・例外時には停止処理を呼びます。

## 音声タイマーから使う

担当者が回転時間を決めるまでは、引数なしでは従来どおり音声とLEDだけで通知します。

```bash
python3 mic/maneki_timer.py
```

例えば終了時に3秒だけ回す設定を試す場合：

```bash
python3 mic/maneki_timer.py --motor-seconds 3
```

3秒は使用例で、確定した仕様ではありません。正の秒数を指定できます。
タイマー終了 → 指定秒数回転 → 停止 → 終了音声、の順です。
回転中は音声命令を処理せず、Ctrl+Cで中断できます。
停止命令で止める運用は未決定なので、タイマーの無期限回転は有効にしていません。

カメラと音声タイマーは、同じBuild HATを別々に操作するため同時実行せず、
どちらか一方を起動してください。同時運用する場合は一つのプログラムに統合する必要があります。

## 実機なしのテスト

```bash
python -m unittest arm.test_motor_control
python camera_motor/camera_sleep.py --self-test
```

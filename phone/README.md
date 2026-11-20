# スマホ（Termux）に置くスクリプト

居眠りを検知したときにスマホとバンドを鳴らし、停止通知から止めるスクリプトです。
スマホ本体の `~/maneki/` に置いて使います。

| ファイル | 役割 |
|---|---|
| `wake.sh` | バンドを着信のように振動させ、通知とスマホのアラームを鳴らす |
| `stop.sh` | バンドの振動、スマホのアラーム、通知を止めて音量を元に戻す |

このフォルダにあるファイルは、スマホ本体の実機から取得した内容です。

## 必要なもの

- Termux
- Termux:API
- Gadgetbridge
- ポート8022で動く `sshd`
- ラズパイから鍵認証でスマホへ接続できること

## スマホへの配置

スマホでTermuxを開き、次のコマンドを実行します。

```sh
mkdir -p ~/maneki
chmod 700 ~/maneki
pkg install openssh termux-api
sshd
```

PCからラズパイ経由でなく、このリポジトリのファイルを直接スマホへ送る場合は、
ラズパイで次のコマンドを使います。

```sh
scp -P 8022 phone/wake.sh u0@スマホのIP:~/maneki/wake.sh
scp -P 8022 phone/stop.sh u0@スマホのIP:~/maneki/stop.sh
ssh -p 8022 u0@スマホのIP 'chmod 700 ~/maneki/wake.sh ~/maneki/stop.sh'
```

スマホの通知から `stop.sh` を呼ぶため、スマホ側の通知権限と
Termux:APIの権限も確認してください。

## 動作確認

スマホでTermuxを開いたまま `sshd` を起動し、ラズパイで確認します。

```sh
python3 ~/sozo-N/sleep_watch/phone_finder.py
ssh -p 8022 u0@スマホのIP 'sh -n ~/maneki/wake.sh && sh -n ~/maneki/stop.sh'
```

## タイマーの読み上げにスマホを使う

タイマーの音声入力と認識はラズパイのUSBマイクで行い、案内と終了音声だけスマホのスピーカーから読み上げます。
スマホでTermuxとTermux:APIを使える状態にし、`sshd`を起動してから、ラズパイで実行します。
音声認識の準備ができると、スマホが「起動しました」と読み上げます。

```sh
python3 ~/sozo-N/mic/maneki_timer.py
```

### ラズパイ起動時に自動で待ち受ける

ラズパイで一度だけ次を実行すると、起動時にタイマーが開始し、停止するまで自動で再起動します。
スマホのTermux/`sshd`がまだ使えない場合も、タイマーは10秒おきに再試行します。

```sh
sudo install -m 644 ~/sozo-N/tools/maneki-timer.service /etc/systemd/system/maneki-timer.service
sudo systemctl daemon-reload
sudo systemctl enable --now maneki-timer.service
```

状態とログは次で確認できます。

```sh
systemctl status maneki-timer.service
journalctl -u maneki-timer.service -f
```

### 居眠り判定をラズパイ起動時に自動で開始する

現時点ではカメラだけで居眠り判定を行い、心拍数の連携は後から導入します。
閉眼が20秒続くとアラームが動作するため、実機確認ではモーターとスマホのアラームに注意してください。

```sh
sudo install -m 644 ~/sozo-N/tools/maneki-camera.service /etc/systemd/system/maneki-camera.service
sudo install -m 644 ~/sozo-N/tools/maneki-sleep-watch.service /etc/systemd/system/maneki-sleep-watch.service
sudo systemctl daemon-reload
sudo systemctl enable --now maneki-camera.service maneki-sleep-watch.service
```

状態やログは次で確認できます。

```sh
systemctl status maneki-camera.service maneki-sleep-watch.service
journalctl -fu maneki-camera.service -u maneki-sleep-watch.service
```

心拍数を後から追加する場合は、対応するBLE心拍センサーまたはスマホ中継を用意してから設定します。

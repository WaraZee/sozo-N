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

```sh
python3 ~/sozo-N/mic/maneki_timer.py
```

#!/data/data/com.termux/files/usr/bin/sh
# 招き猫: バンドに着信のような長い振動をさせ、スマホも鳴らす。通知をタップしたら止まる
# 使い方: wake.sh [表示する名前]   止める: stop.sh
GB=nodomain.freeyourgadget.gadgetbridge
NAME="${1:-招き猫}"
DIR="$HOME/maneki"
FLAG="$DIR/ringing"
MAX_SECONDS=300   # だれも止めなくても5分で止める
ALARM_VOLUME=15   # 鳴らしている間のアラーム音量（最大15）

[ -f "$FLAG" ] && exit 0  # もう鳴っている
touch "$FLAG"
# 今のアラーム音量を覚えておき、止めたときに戻す
termux-volume | tr -d ' \n' | sed 's/.*"stream":"alarm","volume":\([0-9]*\).*/\1/' > "$DIR/alarm_volume"
termux-volume alarm $ALARM_VOLUME

am broadcast -a $GB.command.DEBUG_INCOMING_CALL -p $GB --es caller "$NAME" >/dev/null 2>&1
termux-notification --id maneki-wake --title "$NAME" --content "起きて！タップで止める" \
  --priority high --ongoing --action "$DIR/stop.sh" \
  --button1 "起きた" --button1-action "$DIR/stop.sh"

# スマホを鳴らし続ける（SSH が切れても続くよう、裏で動かす）
nohup setsid sh -c '
  termux-wake-lock
  end=$(( $(date +%s) + '"$MAX_SECONDS"' ))
  while [ -f "'"$FLAG"'" ] && [ $(date +%s) -lt $end ]; do
    termux-vibrate -f -d 1000
    termux-tts-speak -s ALARM -p 1.9 -r 1.1 "おきてください"
    sleep 1
  done
  [ -f "'"$FLAG"'" ] && "'"$DIR"'/stop.sh"
  termux-wake-unlock
' >/dev/null 2>&1 &

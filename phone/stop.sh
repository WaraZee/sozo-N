#!/data/data/com.termux/files/usr/bin/sh
# 招き猫: バンドの振動（着信）とスマホの音を止めて、通知を消し、アラーム音量を元に戻す
GB=nodomain.freeyourgadget.gadgetbridge
DIR="$HOME/maneki"
rm -f "$DIR/ringing"  # これで鳴らし続けるループが止まる
am broadcast -a $GB.command.DEBUG_END_CALL -p $GB >/dev/null 2>&1
termux-notification-remove maneki-wake
if [ -s "$DIR/alarm_volume" ]; then
  termux-volume alarm "$(cat "$DIR/alarm_volume")"
  rm -f "$DIR/alarm_volume"
fi

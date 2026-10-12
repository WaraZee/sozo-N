from buildhat import Hat, Motor

# Build HAT の配線（物理ピン）: 7=GPIO4, 8=GPIO14, 10=GPIO15, 15=GPIO22, 9=GND
# 5V・3.3V はつながない。HAT の電源は丸い端子（7.2〜8.5V）から入れる
PORT = "A"

print("Build HAT に接続中…（初回はファームウェアの書き込みで10秒ほどかかります）")
hat = Hat()
print("つながっている機器:", hat.get())
vin = hat.get_vin()
print("電源電圧: %.1fV" % vin)

motor = Motor(PORT)
print("モーターの角度: %d度" % motor.get_aposition())

if vin < 7.2:
    print("丸い端子の電源が来ていないので、モーターは回さずに終わります（8V±10%が必要）")
    raise SystemExit

print("90度まわします")
motor.run_for_degrees(90, speed=20)
print("もとに戻します")
motor.run_for_degrees(-90, speed=20)
print("モーターの角度: %d度" % motor.get_aposition())
print("=== 終了")

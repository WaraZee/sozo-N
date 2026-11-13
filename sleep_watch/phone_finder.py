"""スマホ（Termux）の IP を自動で探す。IP は DHCP で毎回変わるので

  1. 前回見つけた IP を試す
  2. だめなら、同じネットワークで 8022番（Termux の SSH）が開いている機器を探す
  3. 鍵で SSH ログインできて ~/maneki/wake.sh があるものを、招き猫のスマホとみなす
スマホでは Termux を開いて sshd を打っておく。

使い方: python3 phone_finder.py   → 見つけた IP を表示する
"""
import ipaddress
import os
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor

PHONE_USER = "u0"
PHONE_PORT = 8022
CACHE_FILE = os.path.expanduser("~/.maneki_phone_ip")
INTERFACE = "wlan0"


def find_phone(network, cached, is_open, verify, own=None):
    """招き猫のスマホの IP を返す。見つからなければ None"""
    if cached and is_open(cached) and verify(cached):
        return cached
    hosts = [str(h) for h in network.hosts() if str(h) not in (own, cached)]
    with ThreadPoolExecutor(max_workers=200) as pool:
        opened = [ip for ip, ok in zip(hosts, pool.map(is_open, hosts)) if ok]
    for ip in opened:
        if verify(ip):
            return ip
    return None


def port_open(ip, port=PHONE_PORT, timeout=0.5):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_maneki_phone(ip):
    """鍵でログインできて、wake.sh があるか"""
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
             "-p", str(PHONE_PORT), "%s@%s" % (PHONE_USER, ip), "test -x ~/maneki/wake.sh && echo maneki-ok"],
            capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return False
    return "maneki-ok" in result.stdout


def own_network():
    """(自分の IP, ネットワーク)。例: ("10.27.74.160", 10.27.72.0/22)"""
    output = subprocess.run(["ip", "-o", "-4", "addr", "show", INTERFACE],
                            capture_output=True, text=True).stdout.split()
    interface = ipaddress.ip_interface(output[output.index("inet") + 1])
    return str(interface.ip), interface.network


def load_cached(path=CACHE_FILE):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def save_cached(path, ip):
    with open(path, "w", encoding="utf-8") as f:
        f.write(ip + "\n")


def locate():
    """スマホを探して "u0@IP" を返す。見つからなければ None"""
    own, network = own_network()
    ip = find_phone(network, load_cached(), port_open, is_maneki_phone, own=own)
    if ip is None:
        return None
    save_cached(CACHE_FILE, ip)
    return "%s@%s" % (PHONE_USER, ip)


if __name__ == "__main__":
    host = locate()
    print(host or "見つかりませんでした。スマホで Termux を開いて sshd を打ってください")

"""camera_sleep.py の記録（--log の CSV）から、カメラの状態を読み取る

記録は状態が変わったときと5秒おきにしか増えないので、目を閉じている間は
記録のあとに過ぎた時間も足して、今の閉眼秒数にする。
"""
import csv
import io
from datetime import datetime

STALE_SECONDS = 10  # これより記録が古ければ、カメラが止まっているとみなす
TAIL_BYTES = 4096


def row_time(row):
    return datetime.fromisoformat(row["datetime"]).timestamp()


def camera_at(row, now):
    """記録の1行から、now 時点のカメラの状態を作る。使えなければ None"""
    if row is None:
        return None
    age = now - row_time(row)
    if age > STALE_SECONDS:
        return None
    closed = float(row["closed_seconds"])
    if row["eye_state"] == "closed":
        closed += max(age, 0.0)
    return {"time": now, "eye_state": row["eye_state"], "closed_seconds": closed}


def load_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def last_row(path):
    """最後まで書き終わった行を読む。ファイルや行がなければ None"""
    try:
        with open(path, "rb") as f:
            header = f.readline().decode("utf-8-sig").strip()
            f.seek(0, 2)
            f.seek(max(f.tell() - TAIL_BYTES, 0))
            tail = f.read().decode("utf-8-sig", errors="ignore")
    except OSError:
        return None
    lines = tail.splitlines(keepends=True)
    complete = [line.strip() for line in lines if line.endswith("\n") and line.strip()]
    if not complete or complete[-1] == header:
        return None
    return next(csv.DictReader(io.StringIO(header + "\n" + complete[-1] + "\n")))

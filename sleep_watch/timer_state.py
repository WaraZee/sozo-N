"""Shared timer state used to gate sleep monitoring."""

import json
import math
import os
import time

STATE_FILE = os.path.expanduser("~/.cache/maneki/timer-state.json")
BOOT_ID_FILE = "/proc/sys/kernel/random/boot_id"


def _read_boot_id():
    with open(BOOT_ID_FILE, encoding="ascii") as state_file:
        return state_file.read().strip()


def set_timer_state(seconds, now=None, path=STATE_FILE, boot_id=None):
    if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds) or seconds <= 0):
        raise ValueError("Timer duration must be positive")
    boot_id = _read_boot_id() if boot_id is None else boot_id
    deadline = (time.time() if now is None else now) + seconds
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as state_file:
        json.dump({"boot_id": boot_id, "expires_at": deadline}, state_file)
        state_file.write("\n")
    os.replace(temporary_path, path)


def clear_timer_state(path=STATE_FILE):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def timer_is_active(now=None, path=STATE_FILE, boot_id=None):
    try:
        with open(path, encoding="utf-8") as state_file:
            state = json.load(state_file)
    except FileNotFoundError:
        return False

    if not isinstance(state, dict):
        raise ValueError("Timer state must be a JSON object")
    state_boot_id = state.get("boot_id")
    expires_at = state.get("expires_at")
    if not isinstance(state_boot_id, str):
        raise ValueError("Timer state is missing a boot ID")
    if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)):
        raise ValueError("Timer state has an invalid expiry")
    if not math.isfinite(expires_at):
        raise ValueError("Timer state has a non-finite expiry")
    current_boot_id = _read_boot_id() if boot_id is None else boot_id
    if state_boot_id != current_boot_id:
        return False
    return (time.time() if now is None else now) < expires_at

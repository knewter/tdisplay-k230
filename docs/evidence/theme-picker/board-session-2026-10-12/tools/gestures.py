"""Injected gesture programs for the 18.3 motion trial (board, root; software input only).

Imported by run.py. The same Linux input_event packet format as tools/theme-picker-profile.py
`native_touch`, but with an arbitrary absolute-time path so a program can flick, hold, reverse
and re-touch inside one process. The device must be the verified virtual 'K230 injected touchscreen'.
"""
import os
import struct
import time
from pathlib import Path

PANEL = (568, 1232)
EVENT = struct.Struct("@llHHi")
DEVICE_NAME = "K230 injected touchscreen"
ROW_Y = {"theme": 430, "background": 990}
BACK_TAP = (90, 52)
THEMES_TAP = (480, 130)


def verify_device(device):
    path = Path("/sys/class/input") / Path(device).name / "device/name"
    if path.read_text().strip() != DEVICE_NAME or not str(path.resolve()).startswith("/sys/devices/virtual/input/"):
        raise RuntimeError("refusing a non-virtual or misnamed input device")


def _position(px, py):
    dx = px * 1024 // 568
    dy = py * 2400 // 1232
    return [(3, 53, dx), (3, 54, dy), (3, 0, dx), (3, 1, dy)]


def inject(device, program):
    """program: list of (t_ms, kind, x, y) with kind in down/move/up, absolute from the first event.
    Returns {'down_s': [...], 'up_s': [...], 'moves': [(monotonic_s, x, y)]} on CLOCK_MONOTONIC."""
    verify_device(device)
    for _, kind, x, y in program:
        if kind != "up" and not (0 <= x < PANEL[0] and 0 <= y < PANEL[1]):
            raise ValueError("touch outside native panel")
    fd = os.open(device, os.O_WRONLY | os.O_CLOEXEC)
    log = {"down_s": [], "up_s": [], "moves": []}

    def frame(events):
        packet = b"".join(EVENT.pack(0, 0, *v) for v in [*events, (0, 0, 0)])
        if os.write(fd, packet) != len(packet):
            raise OSError("short input-event write")

    start = time.monotonic()
    touching = False
    try:
        for t_ms, kind, x, y in program:
            wait = start + t_ms / 1000 - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            now = time.monotonic()
            if kind == "down":
                frame([(3, 47, 0), (3, 57, 7), (3, 48, 3), (1, 330, 1), *_position(x, y)])
                touching = True
                log["down_s"].append(now)
                log["moves"].append((now, x, y))
            elif kind == "move":
                frame(_position(x, y))
                log["moves"].append((now, x, y))
            else:
                frame([(3, 57, -1), (1, 330, 0)])
                touching = False
                log["up_s"].append(now)
    finally:
        if touching:
            frame([(3, 57, -1), (1, 330, 0)])
        os.close(fd)
    return log


def line(t0, x0, x1, y, ms, step):
    n = max(1, ms // step)
    return [(t0 + (i * ms) // n, "move", x0 + (x1 - x0) * i // n, y) for i in range(1, n + 1)]


def program(name, row):
    y = ROW_Y[row]
    if name == "flick":          # 300 px in 80 ms, release at speed
        return [(0, "down", 460, y), *line(0, 460, 160, y, 80, 10), (90, "up", 160, y)]
    if name == "slow":           # 300 px in 1.5 s, release at the last sample
        return [(0, "down", 460, y), *line(0, 460, 160, y, 1500, 20), (1520, "up", 160, y)]
    if name == "hold-release":   # 240 px in 300 ms, hold still 700 ms, release
        return [(0, "down", 460, y), *line(0, 460, 220, y, 300, 10), (1000, "up", 220, y)]
    if name == "reversal":       # 200 px left in 200 ms, then 150 px back in 150 ms, release
        return [(0, "down", 460, y), *line(0, 460, 260, y, 200, 10), *line(200, 260, 410, y, 150, 10), (360, "up", 410, y)]
    if name == "interrupt":      # flick, then a new touch 300 ms later drags 30 px against the coast
        return [(0, "down", 460, y), *line(0, 460, 160, y, 80, 10), (90, "up", 160, y),
                (390, "down", 300, y), *line(390, 300, 330, y, 100, 10), (500, "up", 330, y)]
    raise ValueError(name)


GESTURES = ("flick", "slow", "hold-release", "reversal", "interrupt")

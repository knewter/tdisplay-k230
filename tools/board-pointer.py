#!/usr/bin/env python3
"""Drive the board's compositor with a temporary absolute pointer.

`swaymsg seat - cursor press/set/move` moves sway's cursor but sends no
motion to the client while a button is held, so it cannot drag or swipe.
This script creates a uinput absolute pointer (like a VM tablet), which
sway and libinput treat as a real mouse, runs a short script of actions and
removes the device. Run it as root on the board; it needs only the Python
standard library, e.g.

    ssh k230 "$PY - 1280x800 'swipe 900 400 200 400 250'" < tools/board-pointer.py

Actions, separated by ';' (coordinates are output pixels):

    move X Y              put the pointer at X,Y
    down | up             press / release the left button
    rdown | rup           press / release the right button
    wait MS               sleep
    click X Y             move, press, release
    rclick X Y            the same with the right button
    swipe X1 Y1 X2 Y2 MS  press at X1,Y1, move to X2,Y2 over MS ms, release
    hold X Y MS           press at X,Y, wait MS ms (a long press), stay down
"""
import fcntl
import os
import struct
import sys
import time

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
SYN_REPORT = 0
BTN_LEFT, BTN_RIGHT = 0x110, 0x111
ABS_X, ABS_Y = 0, 1
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_ABSBIT = 0x40045564, 0x40045565, 0x40045567
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
ABS_MAX = 65535


def open_device(name: bytes):
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    for bit in (EV_SYN, EV_KEY, EV_ABS):
        fcntl.ioctl(fd, UI_SET_EVBIT, bit)
    for key in (BTN_LEFT, BTN_RIGHT):
        fcntl.ioctl(fd, UI_SET_KEYBIT, key)
    for axis in (ABS_X, ABS_Y):
        fcntl.ioctl(fd, UI_SET_ABSBIT, axis)
    absmax = [0] * 64
    absmax[ABS_X] = absmax[ABS_Y] = ABS_MAX
    # struct uinput_user_dev: name[80], input_id (4 x u16), ff_effects_max,
    # absmax[64], absmin[64], absfuzz[64], absflat[64].
    dev = struct.pack("80sHHHHi", name, 3, 0x1, 0x1, 1, 0)
    dev += struct.pack("64i", *absmax) + struct.pack("64i", *([0] * 64)) * 3
    os.write(fd, dev)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    return fd


def emit(fd, etype, code, value):
    now = time.time()
    sec = int(now)
    os.write(fd, struct.pack("llHHi", sec, int((now - sec) * 1e6), etype, code, value))


def syn(fd):
    emit(fd, EV_SYN, SYN_REPORT, 0)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    width, height = (int(v) for v in sys.argv[1].split("x"))
    fd = open_device(b"k230 scripted pointer")
    time.sleep(0.8)  # let the compositor add the device

    def move(x, y):
        emit(fd, EV_ABS, ABS_X, round(float(x) / max(width - 1, 1) * ABS_MAX))
        emit(fd, EV_ABS, ABS_Y, round(float(y) / max(height - 1, 1) * ABS_MAX))
        syn(fd)

    def button(code, value):
        emit(fd, EV_KEY, code, value)
        syn(fd)

    try:
        for action in filter(None, (a.strip() for a in sys.argv[2].split(";"))):
            word, *args = action.split()
            nums = [float(a) for a in args]
            if word == "move":
                move(*nums)
            elif word in ("down", "up"):
                button(BTN_LEFT, word == "down")
            elif word in ("rdown", "rup"):
                button(BTN_RIGHT, word == "rdown")
            elif word == "wait":
                time.sleep(nums[0] / 1000)
            elif word in ("click", "rclick"):
                code = BTN_LEFT if word == "click" else BTN_RIGHT
                move(*nums)
                time.sleep(0.05)
                button(code, 1)
                time.sleep(0.06)
                button(code, 0)
            elif word == "swipe":
                x1, y1, x2, y2, ms = nums
                move(x1, y1)
                time.sleep(0.05)
                button(BTN_LEFT, 1)
                steps = max(int(ms / 16), 2)
                for i in range(1, steps + 1):
                    time.sleep(ms / 1000 / steps)
                    move(x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps)
                button(BTN_LEFT, 0)
            elif word == "hold":
                x, y, ms = nums
                move(x, y)
                time.sleep(0.05)
                button(BTN_LEFT, 1)
                time.sleep(ms / 1000)
            else:
                sys.exit(f"unknown action: {action}")
            time.sleep(0.03)
    finally:
        time.sleep(0.2)
        fcntl.ioctl(fd, UI_DEV_DESTROY)
        os.close(fd)


if __name__ == "__main__":
    main()

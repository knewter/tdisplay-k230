#!/usr/bin/env python3
"""Keyboard base companion for the shell session (keyboard-base task 6.1).

Reads the base's TCA8418 evdev device without grabbing it, so Sway still
receives every key. On key presses it:

- hides the on-screen keyboard (wvkbd) if it is shown;
- turns the key backlight on, and off again after an idle timeout or while
  the panel is off;
- tracks Caps Lock and lights its LED.

Caps Lock follows xkb's own rule for the Caps_Lock keysym: each press
toggles the lock. Sway starts with the lock off and so does this process,
so the LED follows the lock xkb applies to typing on this device.
"""
import argparse
import glob
import json
import logging
import os
from pathlib import Path
import selectors
import struct
import subprocess
import time

EV_KEY = 1
KEY_CAPSLOCK = 58
INPUT_EVENT = struct.Struct("llHHi")  # riscv64: timeval, type, code, value
NAME = "tca8418"
LOG = logging.getLogger("k230-keyboard-based")


class Policy:
    """Pure key/time policy; actions go through the injected callbacks."""

    def __init__(self, set_capslock, set_backlight, hide_osk, panel_on,
                 idle_seconds=30.0):
        self.set_capslock = set_capslock
        self.set_backlight = set_backlight
        self.hide_osk = hide_osk
        self.panel_on = panel_on
        self.idle_seconds = idle_seconds
        self.caps = False
        self.backlight = False
        self.last_key = None
        set_capslock(False)
        set_backlight(False)

    def _backlight(self, on):
        if on != self.backlight:
            self.backlight = on
            self.set_backlight(on)

    def key(self, code, value, now):
        if value != 1:  # releases and auto-repeat are not new presses
            return
        self.last_key = now
        self.hide_osk()
        if code == KEY_CAPSLOCK:
            self.caps = not self.caps
            self.set_capslock(self.caps)
        self._backlight(self.panel_on())

    def tick(self, now):
        if not self.backlight:
            return
        idle = self.last_key is None or now - self.last_key >= self.idle_seconds
        if idle or not self.panel_on():
            self._backlight(False)


def find_device(name=NAME):
    for path in sorted(glob.glob("/sys/class/input/event*/device/name")):
        if Path(path).read_text().strip() == name:
            return "/dev/input/" + path.split("/")[4]
    return None


def write_led(name, on):
    path = Path("/sys/class/leds") / name / "brightness"
    try:
        path.write_text("1" if on else "0")
    except OSError as exc:
        LOG.warning("cannot set %s: %s", name, exc)


class Session:
    """Talks to Sway and the on-screen keyboard helper."""

    def __init__(self, swaymsg, osk_signal, runtime_dir):
        self.swaymsg = swaymsg
        self.osk_signal = osk_signal
        self.marker = Path(runtime_dir) / "k230-keyboard-visible"
        self.panel_cache = (0.0, True)

    def hide_osk(self):
        try:
            shown = self.marker.read_text().strip() == "show"
        except OSError:
            shown = False
        if shown:
            subprocess.run([self.osk_signal, "hide"], check=False)

    def panel_on(self, now=None):
        # Sway is asked at most every 2 s; DSI-1 off means the panel is dark.
        now = time.monotonic() if now is None else now
        at, value = self.panel_cache
        if now - at < 2.0:
            return value
        try:
            out = subprocess.run([self.swaymsg, "-t", "get_outputs", "-r"],
                                 capture_output=True, text=True, timeout=2).stdout
            outputs = json.loads(out)
            value = any(o.get("name") == "DSI-1" and o.get("power", True) for o in outputs)
        except (OSError, ValueError, subprocess.SubprocessError):
            value = True
        self.panel_cache = (now, value)
        return value


def run(args):
    session = Session(args.swaymsg, args.osk_signal, os.environ.get("XDG_RUNTIME_DIR", "/run/shell"))
    policy = Policy(lambda on: write_led(args.capslock_led, on),
                    lambda on: write_led(args.backlight_led, on),
                    session.hide_osk, session.panel_on, args.idle_seconds)
    while True:
        dev = find_device()
        if dev is None:
            # No keyboard base attached: check again later, quietly.
            time.sleep(10)
            continue
        LOG.info("reading %s", dev)
        try:
            with open(dev, "rb", buffering=0) as f:
                sel = selectors.DefaultSelector()
                sel.register(f, selectors.EVENT_READ)
                while True:
                    if sel.select(timeout=1.0):
                        data = f.read(INPUT_EVENT.size * 64)
                        for off in range(0, len(data) - INPUT_EVENT.size + 1, INPUT_EVENT.size):
                            _, _, etype, code, value = INPUT_EVENT.unpack_from(data, off)
                            if etype == EV_KEY:
                                policy.key(code, value, time.monotonic())
                    policy.tick(time.monotonic())
        except OSError as exc:
            LOG.info("device gone: %s", exc)
            policy.tick(float("inf"))
            time.sleep(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--swaymsg", default="swaymsg")
    ap.add_argument("--osk-signal", default="k230-keyboard-gesture-signal")
    ap.add_argument("--capslock-led", default="k230:green:capslock")
    ap.add_argument("--backlight-led", default="k230::kbd_backlight")
    ap.add_argument("--idle-seconds", type=float, default=30.0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    run(args)


if __name__ == "__main__":
    main()

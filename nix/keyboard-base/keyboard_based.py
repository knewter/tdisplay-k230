#!/usr/bin/env python3
"""Keyboard base companion for the shell session (keyboard-base task 6.1).

Reads the base's TCA8418 evdev device without grabbing it, so Sway still
receives every key. On key presses it:

- hides the on-screen keyboard (wvkbd) if it is shown;
- turns the key backlight on, and off again after an idle timeout or while
  the panel is off, and keeps it off while the Settings preference
  (keyboard-base task 6.3) is off;
- tracks Caps Lock and lights its LED;
- with --escape-back, treats Esc as the shell's back action when no app has
  focus. Sway still delivers Esc to a focused app, because nothing is
  grabbed or bound.

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
KEY_ESC = 1
KEY_CAPSLOCK = 58
INPUT_EVENT = struct.Struct("llHHi")  # riscv64: timeval, type, code, value
NAME = "tca8418"
LOG = logging.getLogger("k230-keyboard-based")


class Policy:
    """Pure key/time policy; actions go through the injected callbacks."""

    def __init__(self, set_capslock, set_backlight, hide_osk, panel_on,
                 idle_seconds=30.0, escape=None, backlight_enabled=None):
        self.set_capslock = set_capslock
        self.set_backlight = set_backlight
        self.hide_osk = hide_osk
        self.panel_on = panel_on
        self.escape = escape
        self.backlight_enabled = backlight_enabled or (lambda: True)
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
        elif code == KEY_ESC and self.escape:
            self.escape()
        self._backlight(self.panel_on() and self.backlight_enabled())

    def tick(self, now):
        if not self.backlight:
            return
        idle = self.last_key is None or now - self.last_key >= self.idle_seconds
        if idle or not self.panel_on() or not self.backlight_enabled():
            self._backlight(False)


def app_focused(node):
    """True when the focused Sway node is an application window."""
    if node.get("focused"):
        return node.get("type") in ("con", "floating_con") and bool(node.get("pid"))
    return any(app_focused(child) for key in ("nodes", "floating_nodes")
               for child in node.get(key, []))


def find_device(name=NAME):
    for path in sorted(glob.glob("/sys/class/input/event*/device/name")):
        if Path(path).read_text().strip() == name:
            return "/dev/input/" + path.split("/")[4]
    return None


def backlight_preference(path):
    """The Settings "Key backlight" choice; on unless the file says off.

    Re-read on each use so a change in Settings applies at the next key press
    or tick. The file is written by the shell client (`keyboard_base.rs`).
    """
    try:
        return Path(path).read_text().strip() not in ("off", "0")
    except OSError:
        return True


def led_on_value(led_dir):
    """The LED's `max_brightness`: 1 for a GPIO LED, 255 for the PWM backlight."""
    try:
        return max(1, int((Path(led_dir) / "max_brightness").read_text()))
    except (OSError, ValueError):
        return 1


def write_led(name, on, leds_root="/sys/class/leds"):
    led_dir = Path(leds_root) / name
    try:
        (led_dir / "brightness").write_text(str(led_on_value(led_dir)) if on else "0")
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

    def back_if_unfocused(self):
        try:
            out = subprocess.run([self.swaymsg, "-t", "get_tree", "-r"],
                                 capture_output=True, text=True, timeout=2).stdout
            tree = json.loads(out)
        except (OSError, ValueError, subprocess.SubprocessError):
            return
        if not app_focused(tree):
            subprocess.run([self.swaymsg, "card_shell", "back"], capture_output=True, check=False)

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
                    session.hide_osk, session.panel_on, args.idle_seconds,
                    session.back_if_unfocused if args.escape_back else None,
                    lambda: backlight_preference(args.backlight_pref))
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
    ap.add_argument("--backlight-pref", default="/var/lib/k230-keyboard-base/key-backlight")
    ap.add_argument("--idle-seconds", type=float, default=30.0)
    ap.add_argument("--escape-back", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    run(args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Physical PMU power key policy for the coherent handheld session.

The kernel emits KEY_POWER edges; this process owns gesture duration. The
shell owns power actions and confirmation. No key event calls systemctl.
"""
import argparse
import fcntl
import json
import logging
import os
from pathlib import Path
import selectors
import socket
import struct
import subprocess
import time

KEY_POWER = 116
EV_KEY = 1
EVIOCGRAB = 0x40044590  # _IOW('E', 0x90, int), Linux evdev
INPUT_EVENT = struct.Struct("llHHi")  # riscv64: timeval, type, code, value
HOLD_SECONDS = 0.7
NAME = "K230 PMU Power Key"
LOG = logging.getLogger("k230-power-keyd")


class KeyPolicy:
    """Emit exactly one short or hold result per complete physical press."""

    def __init__(self, emit, hold_seconds=HOLD_SECONDS):
        self.emit = emit
        self.hold_seconds = hold_seconds
        self.down_at = None
        self.hold_fired = False

    def key(self, value, now):
        if value == 1:
            if self.down_at is None:
                self.down_at = now
                self.hold_fired = False
        elif value == 0 and self.down_at is not None:
            self.tick(now)
            if not self.hold_fired:
                self.emit("short")
            self.down_at = None
            self.hold_fired = False
        # value 2 is an auto-repeat, never a new physical press.

    def tick(self, now):
        if self.down_at is not None and not self.hold_fired:
            if now - self.down_at + 1e-9 >= self.hold_seconds:
                self.hold_fired = True
                self.emit("hold")

    def disconnect(self):
        # A missing release may not turn the display off or open the sheet.
        self.down_at = None
        self.hold_fired = False


def named_device(sys_class=Path("/sys/class/input")):
    for event in sorted(sys_class.glob("event*")):
        try:
            if (event / "device/name").read_text().strip() == NAME:
                return Path("/dev/input") / event.name
        except OSError:
            continue
    return None


class Actions:
    def __init__(self, swaymsg, sway_socket, shell_socket):
        self.swaymsg = swaymsg
        self.sway_socket = sway_socket
        self.shell_socket = shell_socket
        self.dark = False

    def output(self, on):
        cmd = [self.swaymsg, "-s", self.sway_socket, "-r", "output", "DSI-1", "power", "on" if on else "off"]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5)
            reply = json.loads(result.stdout)
            if not isinstance(reply, list) or not reply or not all(
                isinstance(item, dict) and item.get("success") is True for item in reply
            ):
                raise ValueError("Sway refused output power change")
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            LOG.warning("display power command failed: %s", exc)
            return False
        self.dark = not on
        return True

    def show_sheet(self):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(3)
                client.connect(self.shell_socket)
                client.sendall(b"power\n")
                if client.recv(16) != b"OK\n":
                    raise ValueError("shell refused power sheet")
        except (OSError, ValueError) as exc:
            LOG.warning("power sheet unavailable: %s", exc)

    def __call__(self, action):
        if action == "short":
            self.output(self.dark)
        elif action == "hold":
            if self.dark and not self.output(True):
                return
            self.show_sheet()


def run(actions, input_dir=Path("/sys/class/input")):
    policy = KeyPolicy(actions)
    while True:
        device = named_device(input_dir)
        if device is None:
            time.sleep(1)
            continue
        try:
            with device.open("rb", buffering=0) as source:
                # Own this key exclusively: a wake tap must not leak through
                # the compositor to an app as a separate keyboard action.
                fcntl.ioctl(source.fileno(), EVIOCGRAB, struct.pack("i", 1))
                LOG.info("reading %s", device)
                selector = selectors.DefaultSelector()
                selector.register(source, selectors.EVENT_READ)
                try:
                    pending = b""
                    while True:
                        for _key, _mask in selector.select(timeout=0.1):
                            data = source.read(INPUT_EVENT.size * 16)
                            if not data:
                                raise OSError("power key input closed")
                            pending += data
                            while len(pending) >= INPUT_EVENT.size:
                                event, pending = pending[:INPUT_EVENT.size], pending[INPUT_EVENT.size:]
                                _sec, _usec, kind, code, value = INPUT_EVENT.unpack(event)
                                if kind == EV_KEY and code == KEY_POWER:
                                    policy.key(value, time.monotonic())
                        policy.tick(time.monotonic())
                finally:
                    selector.close()
        except OSError as exc:
            LOG.warning("power key input unavailable: %s", exc)
            policy.disconnect()
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--swaymsg", required=True)
    parser.add_argument("--sway-socket", default="/run/shell/sway-ipc.sock")
    parser.add_argument("--shell-socket", default="/run/shell/k230-shell-rust.sock")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    actions = Actions(args.swaymsg, args.sway_socket, args.shell_socket)
    # Recover a dark display after a daemon restart before waiting for input.
    actions.output(True)
    run(actions)


if __name__ == "__main__":
    main()

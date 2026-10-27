#!/usr/bin/env python3
"""Idle dim and display-off steps, driven by swayidle's timeout/resume hooks.

swayidle (ext-idle-notify-v1, so Sway's own idle inhibitors apply) runs one
of these subcommands per event; this process never waits or polls.

  dim     brightness -> 25% of the current value, never higher
  off     display off with the power key's own command (`output * power off`)
  resume  undo whatever dim/off did; idempotent
  wake    resume, then tell Sway there was activity (power-key wake path)

Restoring is conditional: the saved brightness comes back only when the
backlight still holds the value dim wrote, so a slider move made meanwhile
is never overwritten.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import subprocess
import sys

LOG = logging.getLogger("k230-idle-dimmer")
DIM_FRACTION = 0.25


class Dimmer:
    def __init__(self, backlight, state_path, swaymsg, sway_socket):
        self.backlight = Path(backlight)  # the backlight class directory
        self.state_path = Path(state_path)
        self.swaymsg = swaymsg
        self.sway_socket = sway_socket

    # -- state: {"saved": raw|None, "dimmed": raw|None, "off": bool} --------
    def load(self):
        try:
            data = json.loads(self.state_path.read_text())
            return {"saved": data.get("saved"), "dimmed": data.get("dimmed"),
                    "off": bool(data.get("off"))}
        except (OSError, ValueError, AttributeError):
            return {"saved": None, "dimmed": None, "off": False}

    def store(self, state):
        if state == {"saved": None, "dimmed": None, "off": False}:
            try:
                self.state_path.unlink()
            except OSError:
                pass
            return
        tmp = self.state_path.with_name(self.state_path.name + ".tmp")
        tmp.write_text(json.dumps(state))
        os.replace(tmp, self.state_path)

    # -- backlight ----------------------------------------------------------
    def read_raw(self):
        try:
            return int((self.backlight / "brightness").read_text().strip())
        except (OSError, ValueError):
            return None

    def write_raw(self, value):
        try:
            (self.backlight / "brightness").write_text(str(int(value)))
            return True
        except (OSError, ValueError) as exc:
            LOG.warning("backlight write failed: %s", exc)
            return False

    @staticmethod
    def dim_target(current):
        """25% of the current raw value, at least 1, never above it."""
        if current is None or current <= 1:
            return None
        target = max(1, round(current * DIM_FRACTION))
        return target if target < current else None

    # -- sway ---------------------------------------------------------------
    def sway(self, *words):
        cmd = [self.swaymsg, "-s", self.sway_socket, "-r", *words]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=5)
            reply = json.loads(result.stdout)
            return isinstance(reply, list) and all(
                isinstance(item, dict) and item.get("success") is True for item in reply)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            LOG.warning("swaymsg %s failed: %s", " ".join(words), exc)
            return False

    # -- steps --------------------------------------------------------------
    def dim(self):
        state = self.load()
        if state["dimmed"] is not None:
            return  # already dimmed; never dim the dimmed value again
        current = self.read_raw()
        target = self.dim_target(current)
        if target is None:
            return
        # Record first: a crash after the write must still be restorable.
        self.store({"saved": current, "dimmed": target, "off": state["off"]})
        if not self.write_raw(target):
            self.store({"saved": None, "dimmed": None, "off": state["off"]})

    def off(self):
        # Same command as the power key, so power_keyd's toggle (which syncs
        # from Sway's output state) stays consistent.
        if self.sway("output", "*", "power", "off"):
            state = self.load()
            state["off"] = True
            self.store(state)

    def resume(self):
        state = self.load()
        if state["off"]:
            self.sway("output", "*", "power", "on")
        if state["saved"] is not None and self.read_raw() == state["dimmed"]:
            self.write_raw(state["saved"])
        self.store({"saved": None, "dimmed": None, "off": False})

    def wake(self):
        self.resume()
        # Input that a daemon consumed (the power key is grabbed) never reaches
        # Sway, so swayidle would stay idle; a zero cursor move is activity.
        self.sway("seat", "*", "cursor", "move", "0", "0")


def find_backlight(sys_class=Path("/sys/class/backlight")):
    entries = sorted(sys_class.iterdir())
    if len(entries) != 1:
        raise SystemExit("no unique panel backlight")
    return entries[0]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["dim", "off", "resume", "wake"])
    parser.add_argument("--swaymsg", required=True)
    parser.add_argument("--sway-socket", default="/run/shell/sway-ipc.sock")
    parser.add_argument("--state", default="/run/shell/idle-dimmer.json")
    parser.add_argument("--backlight")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    backlight = Path(args.backlight) if args.backlight else find_backlight()
    getattr(Dimmer(backlight, args.state, args.swaymsg, args.sway_socket), args.action)()


if __name__ == "__main__":
    sys.exit(main())

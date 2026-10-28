#!/usr/bin/env python3
"""Idle dim and display-off steps, driven by swayidle's timeout/resume hooks.

swayidle (ext-idle-notify-v1, so Sway's own idle inhibitors apply) runs one
of these subcommands per event; this process never waits or polls.

  dim     brightness -> 25% of the current value, never higher; on the
          charger with "Idle on charger" at Clock, also open the exhibition
  off     display off with the power key's own command (`output * power off`),
          unless the exhibition is up and the charger is still connected
  resume  undo whatever dim/off did; idempotent; ends the exhibition only when
          the display had been off (nothing reached the card then)
  wake    end the exhibition, resume, then tell Sway there was activity
          (power-key wake path)
  exhibit-end  the exhibition's own request (charger gone, or its cap): off
  exhibit-now  the shade's Clock tile: on the charger, dim and open the
          exhibition at once, as if idle had; does nothing on battery. The
          card it opens calls `resume` itself when input closes it, since
          swayidle never saw the idle and will not.

Restoring is conditional: the saved brightness comes back only when the
backlight still holds the value dim wrote, so a slider move made meanwhile
is never overwritten.
"""
import argparse
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys

LOG = logging.getLogger("k230-idle-dimmer")
DIM_FRACTION = 0.25
PREFS_DIR = "/var/lib/k230-shell-prefs"
IDLE_ON_CHARGER_FILE = "idle-on-charger"
POWER_SUPPLY_ROOT = "/sys/class/power_supply"
EXHIBITION_PID_FILE = "/run/shell/exhibition.pid"


def read_idle_on_charger(prefs_dir=PREFS_DIR):
    """"clock" or "sleep". Only the exact word `sleep` selects sleep; a
    missing, unreadable or unrecognised file means the default, clock. The
    Settings row (shell_prefs.rs) writes the same file."""
    try:
        text = (Path(prefs_dir) / IDLE_ON_CHARGER_FILE).read_text()
    except (OSError, ValueError):
        return "clock"
    return "sleep" if text.strip() == "sleep" else "clock"


def charger_online(root=POWER_SUPPLY_ROOT):
    """True when any supply that is not the Battery reports online 1. Same
    rule as k230_exhibition.charger_online (a test holds them together)."""
    try:
        entries = sorted(Path(root).iterdir())
    except OSError:
        return False
    for entry in entries:
        try:
            kind = (entry / "type").read_text().strip()
            online = (entry / "online").read_text().strip()
        except OSError:
            continue
        if kind != "Battery" and online == "1":
            return True
    return False


def exhibit_wanted(preference, charging):
    """The whole decision: show the exhibition only on the charger with the
    preference at clock."""
    return preference == "clock" and bool(charging)


class Dimmer:
    def __init__(self, backlight, state_path, swaymsg, sway_socket, exhibit_exec=None,
                 prefs_dir=PREFS_DIR, power_supply=POWER_SUPPLY_ROOT,
                 pid_file=EXHIBITION_PID_FILE, proc_root="/proc", exhibit_now_exec=None):
        self.backlight = Path(backlight)  # the backlight class directory
        self.state_path = Path(state_path)
        self.swaymsg = swaymsg
        self.sway_socket = sway_socket
        # The command that opens the exhibition card; None disables it.
        self.exhibit_exec = exhibit_exec
        # The same card for the shade's tile, which also resumes on close.
        self.exhibit_now_exec = exhibit_now_exec
        self.prefs_dir = prefs_dir
        self.power_supply = power_supply
        self.pid_file = Path(pid_file)
        self.proc_root = Path(proc_root)

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

    # -- exhibition ---------------------------------------------------------
    def exhibit_wanted(self):
        return bool(self.exhibit_exec) and exhibit_wanted(
            read_idle_on_charger(self.prefs_dir), charger_online(self.power_supply))

    def exhibit_pid(self):
        """The running card's pid, or None (a stale pid file is not a card)."""
        try:
            pid = int(self.pid_file.read_text().strip())
            cmdline = (self.proc_root / str(pid) / "cmdline").read_bytes()
        except (OSError, ValueError):
            return None
        return pid if b"k230_exhibition" in cmdline else None

    def start_exhibit(self, command=None):
        if self.exhibit_pid() is None:
            self.sway("exec", command or self.exhibit_exec)

    def stop_exhibit(self):
        pid = self.exhibit_pid()
        if pid is not None:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

    # -- steps --------------------------------------------------------------
    def dim(self):
        self.dim_backlight()
        if self.exhibit_wanted():
            self.start_exhibit()

    def exhibit_now(self):
        """Start the clock screen on request. The preference is not read: it
        picks what idle does, and the person has just asked. On battery
        nothing starts, so a flat battery is never spent on the clock."""
        command = self.exhibit_now_exec or self.exhibit_exec
        if not command or not charger_online(self.power_supply):
            return
        if self.exhibit_pid() is not None:
            return
        self.dim_backlight()
        self.start_exhibit(command)

    def dim_backlight(self):
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
        if self.exhibit_pid() is not None and self.exhibit_wanted():
            return  # the exhibition keeps the display on while docked
        self.blank()

    def exhibit_end(self):
        """The card asks for the display off: the charger went away, or the
        card reached its time cap."""
        self.blank()

    def blank(self):
        # Same command as the power key, so power_keyd's toggle (which syncs
        # from Sway's output state) stays consistent.
        if self.sway("output", "*", "power", "off"):
            state = self.load()
            state["off"] = True
            self.store(state)

    def resume(self):
        state = self.load()
        if state["off"]:
            # Nothing reached the card through a dark panel; input that did
            # reach it closes it itself, and a kill here would drop the lift.
            self.stop_exhibit()
            self.sway("output", "*", "power", "on")
        if state["saved"] is not None and self.read_raw() == state["dimmed"]:
            self.write_raw(state["saved"])
        self.store({"saved": None, "dimmed": None, "off": False})

    def wake(self):
        self.stop_exhibit()
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
    parser.add_argument("action", choices=["dim", "off", "resume", "wake", "exhibit-end", "exhibit-now"])
    parser.add_argument("--exhibit-exec", help="command that opens the exhibition card")
    parser.add_argument("--exhibit-now-exec", help="command that opens the card for exhibit-now")
    parser.add_argument("--prefs-dir", default=PREFS_DIR)
    parser.add_argument("--power-supply", default=POWER_SUPPLY_ROOT)
    parser.add_argument("--exhibition-pid", default=EXHIBITION_PID_FILE)
    parser.add_argument("--swaymsg", required=True)
    parser.add_argument("--sway-socket", default="/run/shell/sway-ipc.sock")
    parser.add_argument("--state", default="/run/k230-idle/idle-dimmer.json")
    parser.add_argument("--backlight")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    backlight = Path(args.backlight) if args.backlight else find_backlight()
    dimmer = Dimmer(backlight, args.state, args.swaymsg, args.sway_socket,
                    exhibit_exec=args.exhibit_exec, exhibit_now_exec=args.exhibit_now_exec,
                    prefs_dir=args.prefs_dir,
                    power_supply=args.power_supply, pid_file=args.exhibition_pid)
    getattr(dimmer, args.action.replace("-", "_"))()


if __name__ == "__main__":
    sys.exit(main())

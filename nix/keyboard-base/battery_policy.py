#!/usr/bin/env python3
"""Low-battery policy for the keyboard base's cell (keyboard-base task 6.4).

Reads the gauge's power_supply while the battery discharges:

- at the warn level (15 %) and again at the urgent level (5 %) it raises one
  shell notification each per discharge;
- at the shutdown level (3 %), after two consecutive readings, it raises an
  ongoing critical notification and powers off cleanly after a countdown
  (60 s);
- charging cancels the countdown and re-arms the warnings.

Runs as root, so the notification center labels it "System". Levels come from
the command line (Nix options); a JSON file in /run can override them for a
board test, so a real discharge crosses them without a rebuild.
"""
import argparse
import glob
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import time

LOG = logging.getLogger("k230-battery-policy")
TAG = "battery"


class Policy:
    """Pure state machine: readings and time in, notifications and poweroff out."""

    def __init__(self, notify, poweroff, warn=15, urgent=5, shutdown=3,
                 countdown=60.0, enabled=True):
        self.notify = notify
        self.poweroff = poweroff
        self.warn, self.urgent, self.shutdown = warn, urgent, shutdown
        self.countdown = countdown
        self.enabled = enabled
        self.warned = False
        self.urged = False
        self.low_readings = 0
        self.deadline = None

    def reading(self, capacity, discharging, now):
        if not self.enabled:
            return
        if not discharging:
            if self.deadline is not None:
                self.deadline = None
                self.notify("Charging", "Shutdown cancelled.", "ordinary", False)
            self.warned = self.urged = False
            self.low_readings = 0
            return
        if capacity <= self.shutdown:
            self.low_readings += 1
            if self.low_readings >= 2 and self.deadline is None:
                self.deadline = now + self.countdown
                self.notify("Battery critically low",
                            f"Shutting down in {int(self.countdown)} seconds. Connect a charger to cancel.",
                            "critical", True)
            return
        self.low_readings = 0
        if capacity <= self.urgent and not self.urged:
            self.urged = self.warned = True
            self.notify("Battery very low", f"{capacity}% remaining.", "important", False)
        elif capacity <= self.warn and not self.warned:
            self.warned = True
            self.notify("Battery low", f"{capacity}% remaining.", "ordinary", False)

    def tick(self, now):
        if self.deadline is not None and now >= self.deadline:
            self.deadline = None
            self.poweroff()

    def interval(self):
        return 5.0 if self.deadline is not None else 30.0


def find_battery():
    for path in sorted(glob.glob("/sys/class/power_supply/*")):
        try:
            if Path(path, "type").read_text().strip() == "Battery":
                return Path(path)
        except OSError:
            continue
    return None


def read_battery(path):
    capacity = int(Path(path, "capacity").read_text())
    status = Path(path, "status").read_text().strip()
    return capacity, status == "Discharging"


def send_notification(socket_path, summary, body, priority, ongoing):
    request = {"operation": "emit", "summary": summary, "body": body, "tag": TAG,
               "priority": priority, "private": False, "ongoing": ongoing}
    try:
        with socket.socket(socket.AF_UNIX) as conn:
            conn.settimeout(3)
            conn.connect(str(socket_path))
            conn.sendall(json.dumps(request).encode() + b"\n")
            conn.recv(4096)
    except OSError as exc:
        LOG.warning("notification not delivered: %s", exc)
    LOG.info("%s: %s", summary, body)


def apply_override(policy, path):
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return
    for key in ("warn", "urgent", "shutdown"):
        if isinstance(data.get(key), int):
            setattr(policy, key, data[key])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--warn", type=int, default=15)
    ap.add_argument("--urgent", type=int, default=5)
    ap.add_argument("--shutdown", type=int, default=3)
    ap.add_argument("--countdown", type=float, default=60.0)
    ap.add_argument("--override", default="/run/k230-battery-policy.json")
    ap.add_argument("--socket", default="/run/shell-notifications/events.sock")
    ap.add_argument("--poweroff", default="systemctl poweroff")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    policy = Policy(lambda s, b, p, o: send_notification(args.socket, s, b, p, o),
                    lambda: subprocess.run(args.poweroff.split(), check=False),
                    args.warn, args.urgent, args.shutdown, args.countdown)
    while True:
        apply_override(policy, args.override)
        battery = find_battery()
        if battery is not None:
            try:
                capacity, discharging = read_battery(battery)
                policy.reading(capacity, discharging, time.monotonic())
            except (OSError, ValueError) as exc:
                LOG.warning("cannot read %s: %s", battery, exc)
        policy.tick(time.monotonic())
        time.sleep(policy.interval())


if __name__ == "__main__":
    main()

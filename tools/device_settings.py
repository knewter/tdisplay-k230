#!/usr/bin/env python3
"""Small JSON interface for the handheld's real capabilities and confirmed actions.

No network names, addresses, command output, or guessed battery state cross this
interface. The UI owns scrolling and focus; this helper owns capability reads,
short-lived confirmation, and bounded execution. Run commands asynchronously.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import time


def control(state, value=None, **extra):
    return {"state": state, "value": value, **extra}


class Settings:
    def __init__(self, sysfs=Path("/sys"), runtime=None, run=subprocess.run):
        self.sysfs = Path(sysfs)
        self.runtime = Path(runtime or os.environ.get("K230_SETTINGS_RUNTIME", "/run/shell/settings"))
        self.run = run

    def command(self, argv):
        try:
            result = self.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=3, check=False)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def integer(path):
        with path.open() as stream:
            value = stream.read(32).strip()
        if not re.fullmatch(r"[0-9]{1,10}", value):
            raise ValueError("invalid capability value")
        return int(value)

    def network(self):
        """Carrier means a link exists, never that the Internet is reachable."""
        states = []
        try:
            for path in sorted((self.sysfs / "class/net").iterdir())[:64]:
                if path.name == "lo":
                    continue
                try:
                    states.append(self.integer(path / "carrier"))
                except (OSError, ValueError):
                    states.append(None)
        except OSError:
            pass
        if 1 in states:
            return control("read-only", "link-up", label="Network link available")
        if states and all(value == 0 for value in states):
            return control("read-only", "disconnected", label="No network link")
        return control("unavailable", label="Network state unavailable")

    def backlight(self):
        # Multiple unrelated backlights need an explicit panel binding; do not
        # silently choose whichever device happens to sort first.
        paths = list((self.sysfs / "class/backlight").iterdir())
        if len(paths) != 1:
            raise ValueError("no unique panel backlight")
        path = paths[0]
        maximum = self.integer(path / "max_brightness")
        actual = self.integer(path / "actual_brightness")
        if maximum <= 0 or actual > maximum:
            raise ValueError("invalid brightness range")
        return path, maximum, actual

    def brightness(self):
        try:
            path, maximum, actual = self.backlight()
            writable = os.access(path / "brightness", os.W_OK)
            return control("writable" if writable else "read-only",
                           round(actual * 100 / maximum), label="Brightness", unit="percent")
        except (OSError, ValueError):
            return control("unavailable", label="Brightness control unavailable")

    def keyboard(self):
        available = self.command([os.environ.get("K230_PGREP", "pgrep"),
                                  "-u", str(os.getuid()), "-x", "wvkbd-mobintl"])
        return control("action" if available else "unavailable", label="Toggle keyboard",
                       action="keyboard-toggle" if available else None)

    def status(self):
        motion = os.environ.get("K230_SETTINGS_REDUCED_MOTION")
        return {"schema": 1, "controls": {
            "network": self.network(), "brightness": self.brightness(),
            "keyboard": self.keyboard(),
            "motion": control("read-only" if motion in ("0", "1") else "unavailable",
                              motion == "1" if motion in ("0", "1") else None,
                              label="Reduced motion", detail="Session preference"),
        }}

    def change_brightness(self, percent):
        if not 0 <= percent <= 100:
            return {"state": "failed", "error": "invalid-value"}
        previous = self.brightness()
        try:
            path, maximum, _ = self.backlight()
            if previous["state"] != "writable":
                raise PermissionError()
            with (path / "brightness").open("w") as stream:
                stream.write(str(round(percent * maximum / 100)))
            current = self.brightness()
            return {"state": "applied" if current["value"] == percent else "pending",
                    "requested": percent, "control": current}
        except (OSError, ValueError):
            return {"state": "failed", "error": "brightness-denied", "control": previous}

    def locked(self):
        self.runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.runtime.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise PermissionError("unsafe settings runtime")
        fd = os.open(self.runtime / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        lock = os.fdopen(fd, "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            lock.close()
            raise
        return lock

    def power(self, operation, value):
        if operation not in ("request", "confirm", "cancel"):
            return {"state": "failed", "error": "unknown-operation"}
        if operation == "request" and value not in ("reboot", "poweroff"):
            return {"state": "failed", "error": "unknown-action"}
        if operation != "request" and not re.fullmatch(r"[0-9a-f]{32}", value):
            return {"state": "failed", "error": "invalid-confirmation"}
        try:
            with self.locked():
                path = self.runtime / "confirmation.json"
                if operation == "request":
                    token = secrets.token_hex(16)
                    record = {"token": token, "action": value, "created": time.monotonic()}
                    # Only one pending action; new requests invalidate old taps.
                    tmp = self.runtime / (token + ".tmp")
                    with tmp.open("x") as stream:
                        json.dump(record, stream)
                    os.replace(tmp, path)
                    return {"state": "confirmation", "action": value, "token": token,
                            "label": "Restart device?" if value == "reboot" else "Power off device?",
                            "cancel": True, "expires_in_seconds": 30}
                with path.open() as stream:
                    record = json.loads(stream.read(512))
                if record.get("token") != value:
                    return {"state": "failed", "error": "stale-confirmation"}
                path.unlink()  # Consume before any attempt, including denial.
                if operation == "cancel":
                    return {"state": "cancelled"}
                elapsed = time.monotonic() - record["created"]
                if not 0 <= elapsed <= 30 or record["action"] not in ("reboot", "poweroff"):
                    return {"state": "failed", "error": "expired-confirmation"}
                ok = self.command([os.environ.get("K230_SUDO", "/run/wrappers/bin/sudo"), "-n",
                                   os.environ.get("K230_SYSTEMCTL", "systemctl"), record["action"]])
                return {"state": "requested" if ok else "failed", "action": record["action"],
                        "error": None if ok else "action-denied", "retry": not ok}
        except (OSError, ValueError, KeyError, TypeError):
            return {"state": "failed", "error": "confirmation-unavailable", "retry": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["status", "request", "confirm", "cancel", "keyboard-toggle", "brightness"])
    parser.add_argument("value", nargs="?")
    args = parser.parse_args()
    settings = Settings()
    if args.operation == "status":
        result = settings.status()
    elif args.operation == "keyboard-toggle":
        ok = settings.command([os.environ.get("K230_PKILL", "pkill"), "-RTMIN", "-u", str(os.getuid()), "-x", "wvkbd-mobintl"])
        result = {"state": "requested" if ok else "failed", "error": None if ok else "keyboard-unavailable"}
    elif args.operation == "brightness":
        if args.value is None or not re.fullmatch(r"[0-9]{1,3}", args.value):
            parser.error("brightness requires a percentage")
        result = settings.change_brightness(int(args.value))
    else:
        if args.value is None:
            parser.error("action or confirmation token required")
        result = settings.power(args.operation, args.value)
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()

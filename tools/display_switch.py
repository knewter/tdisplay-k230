#!/usr/bin/env python3
"""One-shot HDMI boot selection; the panel payload is never overwritten.

Production paths and executable identities come from the Nix-generated config.
Tests instantiate the controller against a temporary filesystem instead.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

PANEL = "k230-tdisplay.dtb"
HDMI = "k230-tdisplay-hdmi.dtb"
MARKER = "k230-display-restore.json"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class DisplaySwitch:
    def __init__(self, config, boot=Path("/boot"), current=Path("/run/current-system"),
                 drm=Path("/sys/class/drm"), lock=Path("/run/k230-display-switch.lock"),
                 run=subprocess.run):
        self.config, self.boot, self.current = config, Path(boot), Path(current)
        self.drm, self.lock, self.run = Path(drm), Path(lock), run

    def bootargs(self):
        data = (self.boot / "bootargs.txt").read_text()
        if len(data) > 4096 or not data.startswith("bootargs=") or data.count("\n") != 1 or not data.endswith("\n") or "\0" in data:
            raise ValueError("invalid boot arguments")
        args = data[9:-1]
        expected = "init=" + str(self.current.resolve(strict=True)) + "/init"
        if [arg for arg in args.split() if arg.startswith("init=")] != [expected]:
            raise ValueError("boot selection does not match the running system")
        return args

    def status(self):
        result = {"state": "unavailable", "next_boot": "unknown", "active": "unknown"}
        try:
            self.bootargs()
            selector = (self.boot / "force_dtb").read_text()
            if selector not in (PANEL, HDMI):
                return result
            if not (self.boot / PANEL).is_file() or not (self.boot / "Image").is_file():
                return result
            result["next_boot"] = "HDMI" if selector == HDMI else "AMOLED"
            for path in sorted(self.drm.glob("*-*/status")):
                if path.read_text().strip() == "connected":
                    if "-HDMI-A-" in path.parent.name:
                        result["active"] = "HDMI"
                        break
                    if "-DSI-" in path.parent.name:
                        result["active"] = "AMOLED"
            result["state"] = "action" if (result["active"] == "AMOLED"
                and selector == PANEL and not (self.boot / MARKER).exists()) else "read-only"
        except (OSError, ValueError):
            pass
        return result

    @contextmanager
    def writable(self):
        # A mount failure must happen before any boot-partition write.
        self.run([self.config["mount"], "-o", "remount,rw", str(self.boot)], check=True,
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=10)
        try:
            yield
        finally:
            self.run([self.config["mount"], "-o", "remount,ro", str(self.boot)], check=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=10)

    def sync_directory(self):
        fd = os.open(self.boot, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def replace(self, name, data):
        target = self.boot / name
        if target.is_symlink():
            raise ValueError("boot target is a symlink")
        fd, temporary = tempfile.mkstemp(prefix=".k230-display-", dir=self.boot)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fchmod(stream.fileno(), 0o644)
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            self.sync_directory()
        finally:
            Path(temporary).unlink(missing_ok=True)

    def dtb(self, source, args):
        with tempfile.TemporaryDirectory(prefix="k230-display-") as directory:
            target = Path(directory) / "tree.dtb"
            target.write_bytes(Path(source).read_bytes())
            self.run([self.config["fdtput"], "-t", "s", str(target), "/chosen", "bootargs", args],
                     check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=10)
            return target.read_bytes()

    def restore_locked(self):
        marker = self.boot / MARKER
        if not marker.exists():
            return False
        if marker.is_symlink() or json.loads(marker.read_text()) != {"schema": 1, "panel": PANEL}:
            raise ValueError("invalid restore marker")
        # Restore independently of the running profile/HDMI health. Never use
        # a pathname from the marker as a copy destination or source.
        if (self.boot / PANEL).read_bytes()[:4] != bytes.fromhex("d00dfeed"):
            raise ValueError("panel recovery tree is missing")
        with self.writable():
            self.replace("force_dtb", PANEL.encode())
            marker.unlink()
            self.sync_directory()
        return True

    def hdmi_locked(self):
        if self.status()["state"] != "action":
            raise ValueError("HDMI switching is unavailable")
        args = self.bootargs()
        if digest(self.boot / "Image") != digest(Path(self.config["kernel"])):
            raise ValueError("boot kernel does not match this system")
        panel = self.dtb(self.config["panel"], args)
        if (self.boot / PANEL).read_bytes() != panel:
            raise ValueError("panel recovery tree does not match this system")
        hdmi = self.dtb(self.config["hdmi"], args)
        with self.writable():
            self.replace(MARKER, json.dumps({"schema": 1, "panel": PANEL}).encode())
            try:
                self.replace(HDMI, hdmi)
                self.replace("force_dtb", HDMI.encode())
            except BaseException:
                self.replace("force_dtb", PANEL.encode())
                (self.boot / MARKER).unlink()
                self.sync_directory()
                raise
        try:
            self.run([self.config["systemctl"], "reboot", "--no-block"], check=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=10)
        except BaseException:
            self.restore_locked()
            raise

    def mutate(self, operation):
        with self.lock.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self.restore_locked() if operation == "restore" else self.hdmi_locked()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("operation", choices=("status", "hdmi", "restore"))
    args = parser.parse_args()
    controller = DisplaySwitch(json.loads(args.config.read_text()))
    if args.operation == "status":
        print(json.dumps(controller.status()))
        return
    if os.geteuid() != 0 or not os.path.ismount("/boot"):
        parser.error("boot changes require root and the mounted boot partition")
    try:
        controller.mutate(args.operation)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # No command output, network values or configuration contents.
        raise SystemExit("display switch failed: " + type(error).__name__) from None


if __name__ == "__main__":
    main()

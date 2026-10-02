#!/usr/bin/env python3
"""Run one bounded rdinit=/bin/sh trial from the exact mainline DRM bundle.

Raw serial output can contain private machine details. The controller writes
it only to a newly-created mode-0600 log outside the repository and never
prints it to stdout.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


BUNDLE = Path(
    "/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-"
    "k230-mainline-drm-trial-boot-files"
)
SYSTEM = "/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd"
MANIFEST_DEFAULT = Path("/home/jadams/tmp/k230-coordination/mainline-boot-manifest.json")
PRIVATE_LOG_DIR = Path("/home/jadams/tmp/k230-coordination/mainline-initrd-private")
LOCK_PATH = Path("/tmp/k230-board.lock")
SERIAL_DEVICE = "/dev/ttyACM0"
PROMPT = b"K230# "
LOADS = (
    ("bootargs.txt", "1:2", "0x7000000", "/var/lib/k230-mainline-drm-trial/bootargs.txt"),
    ("fw_jump_add_uboot_head.bin", "1:1", "0x8000000", "/fw_jump_add_uboot_head.bin"),
    ("Image-mainline-drm", "1:2", "0x200000", "/var/lib/k230-mainline-drm-trial/Image-mainline-drm"),
    ("k230-tdisplay-mainline-drm.dtb", "1:2", "0x8400000", "/var/lib/k230-mainline-drm-trial/k230-tdisplay-mainline-drm.dtb"),
    ("initrd.uimg", "1:2", "0x9000000", "/var/lib/k230-mainline-drm-trial/initrd.uimg"),
)
PROBE = (
    "echo K230_RDINIT_PROBE_BEGIN; "
    "cat /proc/uptime /proc/interrupts /proc/cmdline /proc/mounts; "
    "ls -l /dev/disk/by-label; dmesg; "
    "echo K230_RDINIT_PROBE_END; sleep 10; reboot -f"
)


def trial_bootargs(original: str, system: str = SYSTEM) -> str:
    """Add the sole diagnostic variable and require the matching NixOS init."""
    args = original.strip()
    if not re.search(rf"(?:^|\s)init={re.escape(system)}/init(?:\s|$)", args):
        raise ValueError("bootargs do not select the matching trial system")
    if re.search(r"(?:^|\s)rdinit=", args):
        raise ValueError("original bootargs already contain rdinit")
    if "\n" in args or "\r" in args:
        raise ValueError("bootargs must be a single line")
    return f"{args} rdinit=/bin/sh"


def verified_load(reply: bytes | None, expected: dict[str, object]) -> bool:
    """Accept exactly the expected byte-count line and U-Boot CRC result."""
    if reply is None:
        return False
    sizes = re.findall(rb"(?m)^([0-9]+) bytes read", reply)
    crcs = re.findall(rb"(?m)==> ([0-9a-fA-F]{8})", reply)
    expected_size = str(expected["bytes"]).encode()
    expected_crc = str(expected["crc32"]).lower().encode()
    return sizes == [expected_size] and crcs == [expected_crc]


class PrivateSession:
    def __init__(self, serial, log_file):
        self.port = serial.Serial(SERIAL_DEVICE, 115200, timeout=0.1, exclusive=True)
        self.log = log_file
        self.buffer = b""

    def write(self, data: bytes) -> None:
        self.port.write(data)
        self.port.flush()

    def line(self, command: str, *, interrupt: bool = True) -> None:
        if interrupt:
            self.write(b"\x15")
            time.sleep(0.05)
        self.log.write((f"\n--- command: {command} ---\n").encode())
        self.buffer = b""
        self.write(command.encode() + b"\r")

    def pump(self) -> bytes:
        chunk = self.port.read(65536)
        if chunk:
            self.log.write(chunk)
            self.buffer = (self.buffer + chunk)[-131072:]
        return chunk

    def wait_for(self, token: bytes, timeout: float) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.pump()
            if token in self.buffer:
                return True
        return False

    def command(self, command: str, timeout: float = 30) -> bytes | None:
        self.line(command)
        if not self.wait_for(PROMPT, timeout):
            return None
        return self.buffer

    def close(self) -> None:
        self.port.close()


def safe_log_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    if resolved == repo or repo in resolved.parents:
        raise ValueError("raw serial log must be outside the repository")
    if resolved.exists():
        raise FileExistsError("private log already exists; choose a new path")
    if resolved.parent == PRIVATE_LOG_DIR:
        resolved.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(resolved.parent, 0o700)
    elif not resolved.parent.is_dir():
        raise FileNotFoundError("custom private log directory must already exist")
    if resolved.parent.stat().st_mode & 0o077:
        raise PermissionError("private log directory must not be accessible to group/other")
    return resolved


def run_trial(manifest_path: Path, log_path: Path) -> None:
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("pyserial is required; use nix shell nixpkgs#python3Packages.pyserial") from exc

    manifest = json.loads(manifest_path.read_text())
    if manifest.get("system") != SYSTEM:
        raise ValueError("manifest does not name the expected matching trial system")
    files = manifest.get("files", {})
    if set(files) != {name for name, _, _, _ in LOADS}:
        raise ValueError("manifest file set does not match the exact trial bundle")
    for name, _, _, _ in LOADS:
        if name == "fw_jump_add_uboot_head.bin":
            continue  # Loaded from the unchanged normal boot partition.
        artifact = BUNDLE / name
        expected = files[name]
        if not artifact.is_file() or artifact.stat().st_size != int(expected["bytes"]):
            raise FileNotFoundError(f"exact trial bundle artifact is missing or has wrong size: {name}")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest != str(expected["sha256"]).lower():
            raise ValueError(f"exact trial bundle artifact hash mismatch: {name}")
    original_args = (BUNDLE / "bootargs.txt").read_text()
    expected_args = trial_bootargs(original_args)

    log_path = safe_log_path(log_path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(log_path, flags, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "wb", buffering=0) as log_file:
        lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("board lock is held; no serial device was opened") from exc
        session = None
        boot_started = False
        in_uboot = False
        try:
            session = PrivateSession(serial, log_file)
            session.write(b"\x03\r")
            time.sleep(0.4)
            session.pump()
            session.line("reboot")
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                session.pump()
                if b"Hit any key to stop autoboot" in session.buffer:
                    session.write(b" ")
                if PROMPT in session.buffer:
                    break
            else:
                raise RuntimeError("U-Boot prompt not reached; no files were loaded")
            in_uboot = True

            for command in ("mmc list", "ext4ls mmc 1:1 /", "printenv bootcmd", "printenv blinux"):
                if session.command(command, 30) is None:
                    raise RuntimeError("U-Boot preflight did not return to its prompt")

            for name, partition, address, source_path in LOADS:
                expected = files[name]
                load = session.command(
                    f"ext4load mmc {partition} {address} {source_path}", 90
                )
                if load is None or not re.search(
                    rb"(?m)^([0-9]+) bytes read", load
                ):
                    raise RuntimeError(f"load failed for {name}; no candidate boot was issued")
                crc = session.command(f"crc32 {address} {hex(int(expected['bytes']))}", 40)
                if not verified_load(load + (crc or b""), expected):
                    raise RuntimeError(f"count/CRC mismatch for {name}; no candidate boot was issued")

            args = session.command(
                f"env import -t 0x7000000 {hex(int(files['bootargs.txt']['bytes']))}", 15
            )
            if args is None:
                raise RuntimeError("could not import the matching volatile bootargs")
            # U-Boot imports the complete exact bootargs file above. Expand its
            # saved value only inside volatile RAM, then append this one variable.
            command = 'setenv bootargs "${bootargs} rdinit=/bin/sh"'
            if session.command(command, 15) is None:
                raise RuntimeError("could not set volatile rdinit bootargs")
            printed = session.command("printenv bootargs", 15)
            if printed is None or b"rdinit=/bin/sh" not in printed or f"init={SYSTEM}/init".encode() not in printed:
                raise RuntimeError("volatile bootargs do not contain both matching init paths")
            if "rdinit=/bin/sh" not in expected_args:
                raise AssertionError("pure bootargs validation disagreed with U-Boot check")

            session.line("bootm 0x8000000 0x9000000 0x8400000", interrupt=False)
            boot_started = True
            in_uboot = False
            if not session.wait_for(b"Linux version 7.3.0-rc5", 45):
                raise RuntimeError("Linux version banner not observed; reset may be required")
            time.sleep(5)
            session.pump()

            # The command does not exit the shell: rdinit is PID 1. Its final
            # reboot -f is a child command that returns to the untouched U-Boot
            # selection after the bounded proc/sysfs snapshot.
            session.write((PROBE + "\n").encode())
            if not session.wait_for(b"K230_RDINIT_PROBE_END", 30):
                raise RuntimeError("PID 1 shell probe did not complete; do not send exit")
            if not session.wait_for(b"nixos login:", 180):
                raise RuntimeError("normal login not observed after initrd reboot")
            print(f"Trial completed; private serial log: {log_path}")
            print("Normal NixOS login prompt observed after volatile reboot.")
        except Exception:
            if session is not None and in_uboot and not boot_started:
                # All pre-boot failures leave Linux/normal boot files intact.
                session.line("reset", interrupt=False)
                print("Pre-boot failure: reset requested; normal boot selection is unchanged.", file=sys.stderr)
            elif boot_started:
                print(
                    "Linux started; PID 1 may still be the diagnostic shell. Do not send exit. "
                    "Use the agreed physical power-cycle recovery if automatic reboot did not occur.",
                    file=sys.stderr,
                )
            raise
        finally:
            if session is not None:
                session.close()
            os.close(lock_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_DEFAULT)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser.add_argument(
        "--log", type=Path,
        default=PRIVATE_LOG_DIR / f"mainline-initrd-shell-{stamp}.private.log",
    )
    args = parser.parse_args()
    try:
        run_trial(args.manifest, args.log)
    except Exception as exc:
        print(f"Trial stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

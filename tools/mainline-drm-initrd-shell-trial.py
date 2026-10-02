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
import importlib.util
import json
import os
import re
import shlex
import sys
import time
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path


BUNDLE = Path(
    "/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-"
    "k230-mainline-drm-trial-boot-files"
)
SYSTEM = "/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd"
NORMAL_REPORT = Path("/home/jadams/tmp/k230-coherent-boot-board/received/after.json")
NORMAL_BASELINE = Path(__file__).resolve().parents[1] / "docs/evidence/boot-verification/coherent-ordinary-boot/postboot.json"
# The protected stage-one wrapper's CRC in the committed physical trial manifest.
NORMAL_WRAPPER_CRC32 = "99b89787"
STORE_ROOT = Path("/nix/store")
NORMAL_HELPER = Path(__file__).with_name("mainline-drm-normal-state.py")
NORMAL_STAGE = "/var/lib/k230-mainline-drm-trial"
BOARD_PYTHON = "/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3"
MANIFEST_DEFAULT = Path("/home/jadams/tmp/k230-coordination/mainline-boot-manifest.json")
PRIVATE_LOG_DIR = Path("/home/jadams/tmp/k230-coordination/mainline-initrd-private")
LOCK_PATH = Path("/tmp/k230-board.lock")
SERIAL_DEVICE = "/dev/ttyACM0"
PROMPT = b"K230# "
RECEPTION_MAX_ATTEMPTS = 8
RECEPTION_ATTEMPT_TIMEOUT = 1.0
_PROTOCOL_SPEC = importlib.util.spec_from_file_location(
    "rvv_board_boot", Path(__file__).with_name("rvv-board-boot.py")
)
_PROTOCOL = importlib.util.module_from_spec(_PROTOCOL_SPEC)
_PROTOCOL_SPEC.loader.exec_module(_PROTOCOL)
LOADS = (
    ("bootargs.txt", "1:2", "0x7000000", "/var/lib/k230-mainline-drm-trial/bootargs.txt"),
    ("fw_jump_add_uboot_head.bin", "1:1", "0x8000000", "/fw_jump_add_uboot_head.bin"),
    ("Image-mainline-drm", "1:2", "0x200000", "/var/lib/k230-mainline-drm-trial/Image-mainline-drm"),
    ("k230-tdisplay-mainline-drm.dtb", "1:2", "0x8400000", "/var/lib/k230-mainline-drm-trial/k230-tdisplay-mainline-drm.dtb"),
    ("initrd.uimg", "1:2", "0x9000000", "/var/lib/k230-mainline-drm-trial/initrd.uimg"),
)
PROBE_DATA = (
    "_k230_probe_rc=0; _k230_block_count=0; _k230_label_ok=0; _k230_nixos_sd=0; "
    "mkdir -p /proc /sys /dev; _k230_mkdir_rc=$?; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN mkdir-done\\n'; "
    "test $_k230_mkdir_rc -eq 0 || _k230_probe_rc=1; "
    "mount -t proc proc /proc 2>/dev/null || test -r /proc/mounts || _k230_probe_rc=1; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN proc-mount-check\\n'; "
    "_k230_have_sys=0; _k230_have_dev=0; "
    "while read _src _mnt _fs _rest; do "
    "test \"$_mnt\" = /sys && test \"$_fs\" = sysfs && _k230_have_sys=1; "
    "test \"$_mnt\" = /dev && test \"$_fs\" = devtmpfs && _k230_have_dev=1; "
    "done < /proc/mounts; "
    "test $_k230_have_sys -eq 1 || mount -t sysfs sysfs /sys || _k230_probe_rc=1; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN sys-mount-check\\n'; "
    "test $_k230_have_dev -eq 1 || mount -t devtmpfs devtmpfs /dev || _k230_probe_rc=1; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN dev-mount-check\\n'; "
    "_k230_have_proc=0; _k230_have_sys=0; _k230_have_dev=0; "
    "while read _src _mnt _fs _rest; do "
    "test \"$_mnt\" = /proc && test \"$_fs\" = proc && _k230_have_proc=1; "
    "test \"$_mnt\" = /sys && test \"$_fs\" = sysfs && _k230_have_sys=1; "
    "test \"$_mnt\" = /dev && test \"$_fs\" = devtmpfs && _k230_have_dev=1; "
    "done < /proc/mounts; "
    "test $_k230_have_proc -eq 1 && test $_k230_have_sys -eq 1 && "
    "test $_k230_have_dev -eq 1 || _k230_probe_rc=1; "
    "test -r /proc/partitions || _k230_probe_rc=1; "
    "test -r /proc/interrupts || _k230_probe_rc=1; "
    "test -d /sys/block || _k230_probe_rc=1; "
    "echo K230_PROC; printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN proc-read-start\\n'; "
    "cat /proc/uptime /proc/interrupts /proc/cmdline /proc/partitions /proc/mounts; "
    "_k230_proc_read_rc=$?; printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN proc-read-done\\n'; "
    "test $_k230_proc_read_rc -eq 0 || _k230_probe_rc=1; "
    "echo K230_SYS_BLOCK; ls -l /sys/block; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN sys-block-read-done\\n'; "
    "echo K230_DEV_BLOCK; ls -l /dev/mmcblk* 2>&1; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN dev-block-read-done\\n'; "
    "echo K230_UDEV_LABEL_LINKS; ls -l /dev/disk/by-label; "
    "for dev in /dev/mmcblk*p*; do "
    "if test -b \"$dev\"; then _k230_block_count=$((_k230_block_count+1)); "
    "if _k230_label=$(e2label \"$dev\" 2>&1); then _k230_label_ok=1; "
    "else _k230_label=unreadable; fi; "
    "printf 'K230_EXT4_LABEL %s %s\\n' \"$dev\" \"$_k230_label\"; "
    "test \"$_k230_label\" = NIXOS_SD && _k230_nixos_sd=1; fi; done; "
    "test $_k230_block_count -gt 0 || _k230_probe_rc=1; "
    "printf 'K230_RDINIT_STAGE K230_STAGE_TOKEN labels-read-done\\n'; "
    "test $_k230_label_ok -eq 1 || _k230_probe_rc=1; "
    "printf 'K230_LABEL_NIXOS_SD=%s\\n' \"$_k230_nixos_sd\""
)


def trial_bootargs(
    original: str, system: str = SYSTEM, *, ignore_unused_clocks: bool = False,
    debug_shutdown: bool = False,
) -> str:
    """Add diagnostic arguments and require the matching NixOS init."""
    args = original.strip()
    params = args.removeprefix("bootargs=").split()
    init_args = [arg for arg in params if arg.startswith("init=")]
    if init_args != [f"init={system}/init"]:
        raise ValueError("bootargs do not select the matching trial system")
    if any(arg.startswith("rdinit=") for arg in params):
        raise ValueError("original bootargs already contain rdinit")
    if any(ord(char) < 32 for char in args):
        raise ValueError("bootargs must be a single line")
    if ignore_unused_clocks and any(arg.split("=", 1)[0] == "clk_ignore_unused" for arg in params):
        raise ValueError("original bootargs already contain clk_ignore_unused")
    if debug_shutdown:
        if ignore_unused_clocks:
            raise ValueError("shutdown debug and clock diagnostics cannot be combined")
        for arg in params:
            name, _, value = arg.partition("=")
            if (name in {"initcall_debug", "ignore_loglevel", "quiet", "debug", "dyndbg"}
                    or name.endswith(".dyndbg")
                    or (name == "loglevel" and value not in tuple(str(n) for n in range(8)))):
                raise ValueError("original bootargs contain conflicting shutdown debug arguments")
    extra = " clk_ignore_unused" if ignore_unused_clocks else ""
    if debug_shutdown:
        # The bundle's existing loglevel=4/7 is preserved; the final 8 wins.
        extra = " initcall_debug loglevel=8"
    return f"{args} rdinit=/bin/sh" + extra


def volatile_bootargs_command(ignore_unused_clocks: bool = False, *, debug_shutdown: bool = False) -> str:
    if ignore_unused_clocks and debug_shutdown:
        raise ValueError("shutdown debug and clock diagnostics cannot be combined")
    extra = " clk_ignore_unused" if ignore_unused_clocks else ""
    if debug_shutdown:
        extra = " initcall_debug loglevel=8"
    return 'setenv bootargs "${bootargs} rdinit=/bin/sh' + extra + '"'


def immutable_store_path(path: Path, description: str) -> Path:
    """Require a direct, existing, read-only store directory, not an alias."""
    if path.parent != STORE_ROOT or not re.fullmatch(r"[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+", path.name):
        raise ValueError(f"{description} must be a direct immutable /nix/store path")
    if path.resolve(strict=True) != path or not path.is_dir() or path.stat().st_mode & 0o222:
        raise ValueError(f"{description} must be an immutable store directory")
    return path


def validate_file_record(info: object, name: str) -> None:
    if not isinstance(info, dict) or type(info.get("bytes")) is not int or info["bytes"] <= 0:
        raise ValueError(f"invalid positive artifact size: {name}")
    if not isinstance(info.get("sha256"), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", info["sha256"]):
        raise ValueError(f"invalid artifact SHA-256: {name}")


def validate_load_ranges(files: dict[str, object]) -> None:
    """Check actual verified payload sizes at the exact U-Boot load addresses."""
    intervals = []
    for name, _, address, _ in LOADS:
        validate_file_record(files[name], name)
        start = int(address, 16)
        end = start + files[name]["bytes"]
        if not 0 <= start < end <= 0x40000000:
            raise ValueError(f"artifact load exceeds the board's 1 GiB RAM: {name}")
        intervals.append((start, end, name))
    intervals.sort()
    for left, right in zip(intervals, intervals[1:]):
        if left[1] > right[0]:
            raise ValueError(f"artifact load overlap: {left[2]} and {right[2]}")


def verified_bootargs(reply: bytes | None, expected: str) -> bool:
    if reply is None:
        return False
    matches = re.findall(rb"^bootargs=([^\n]*)\n", _PROTOCOL.uart_text(reply), re.M)
    return matches == [expected.removeprefix("bootargs=").encode()]


def verified_load(reply: bytes | None, expected: dict[str, object]) -> bool:
    """Use the shared strict parser for complete, non-echoed U-Boot reports."""
    try:
        _PROTOCOL.verify_load(reply, int(expected["bytes"]))
    except (RuntimeError, TypeError, ValueError):
        return False
    return True


def verified_crc(reply: bytes | None, expected: dict[str, object]) -> bool:
    try:
        _PROTOCOL.verify_crc(reply, str(expected["crc32"]).lower())
    except (RuntimeError, TypeError, ValueError):
        return False
    return True


PROBE_STAGE_NAMES = (
    "shell-start", "mkdir-done", "proc-mount-check", "sys-mount-check",
    "dev-mount-check", "proc-read-start", "proc-read-done",
    "sys-block-read-done", "dev-block-read-done", "labels-read-done",
)


def _validate_token(token: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("probe token must be a 32-character lowercase UUID")


def reception_command(token: str) -> str:
    _validate_token(token)
    return f"PATH=/bin:/sbin; export PATH; printf 'K230_RDINIT_RX {token}\\n'"


def true_command(token: str) -> str:
    _validate_token(token)
    return f"/bin/true; printf 'K230_RDINIT_TRUE {token} RC=%s\\n' \"$?\""


def uptime_command(token: str) -> str:
    _validate_token(token)
    return (
        f"printf 'K230_RDINIT_UP_BEGIN {token}\\n'; /bin/cat /proc/uptime; "
        f"printf 'K230_RDINIT_UP_END {token} RC=%s\\n' \"$?\""
    )


def proc_mount_command(token: str) -> str:
    _validate_token(token)
    return (
        f"printf 'K230_RDINIT_MOUNT_BEGIN {token}\\n'; "
        "/bin/mkdir -p /proc; _k230_mkdir_rc=$?; _k230_mount_attempted=0; _k230_mount_rc=255; "
        "if test $_k230_mkdir_rc -eq 0; then _k230_mount_attempted=1; "
        "/bin/mount -t proc proc /proc; _k230_mount_rc=$?; fi; "
        f"printf 'K230_RDINIT_MOUNT_END {token} MKDIR_RC=%s MOUNT_ATTEMPTED=%s MOUNT_RC=%s\\n' "
        "\"$_k230_mkdir_rc\" \"$_k230_mount_attempted\" \"$_k230_mount_rc\""
    )


def reboot_command(token: str) -> str:
    _validate_token(token)
    return f"printf 'K230_RDINIT_REBOOT {token}\\n'; /bin/reboot -ff"


def label_setup_command(token: str, stage: str) -> str:
    _validate_token(token)
    commands = {
        "dev-mkdir": "/bin/mkdir -p /dev 2>/dev/null; _k230_rc=$?",
        "dev-mount": (
            "_k230_have_dev=0; while read _src _mnt _fs _rest; do "
            "if test \"$_mnt\" = /dev && test \"$_fs\" = devtmpfs; then _k230_have_dev=1; fi; "
            "done < /proc/mounts; _k230_rc=$?; "
            "if test $_k230_rc -eq 0 && test $_k230_have_dev -eq 0; then "
            "/bin/mount -t devtmpfs devtmpfs /dev 2>/dev/null; _k230_rc=$?; fi"
        ),
        "node": "test -b /dev/mmcblk1p2; _k230_rc=$?",
    }
    if stage not in commands:
        raise ValueError("unknown label setup stage")
    return (
        f"printf 'K230_RDINIT_LABEL_SETUP_BEGIN {token} STAGE={stage}\\n'; "
        f"{commands[stage]}; "
        f"printf 'K230_RDINIT_LABEL_SETUP_END {token} STAGE={stage} RC=%s\\n' \"$_k230_rc\""
    )


def label_command(token: str) -> str:
    _validate_token(token)
    return (
        f"printf 'K230_RDINIT_LABEL_BEGIN {token}\\n'; "
        "_k230_label=$(/bin/e2label /dev/mmcblk1p2 2>/dev/null); _k230_rc=$?; _k230_match=0; "
        "if test $_k230_rc -eq 0 && test \"$_k230_label\" = NIXOS_SD; then _k230_match=1; fi; "
        f"printf 'K230_RDINIT_LABEL_END {token} RC=%s MATCH=%s\\n' \"$_k230_rc\" \"$_k230_match\""
    )


def label_result(output: bytes, token: str, stage: str = "label") -> dict[str, int | bool] | None:
    _validate_token(token)
    if stage not in ("dev-mkdir", "dev-mount", "node", "label"):
        raise ValueError("unknown label stage")
    prefix = b"K230_RDINIT_LABEL" + (b"_SETUP" if stage != "label" else b"")
    suffix = b" STAGE=" + stage.encode() if stage != "label" else b""
    text = _PROTOCOL.uart_text(output)
    starts = list(re.finditer(rb"^" + prefix + b"_BEGIN " + token.encode() + suffix + rb"\n", text, re.M))
    ends = list(re.finditer(
        rb"^" + prefix + b"_END " + token.encode() + suffix +
        rb" RC=([0-9]{1,3})" + (rb" MATCH=([01])" if stage == "label" else b"") + rb"\n",
        text, re.M,
    ))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    rc = int(ends[0].group(1))
    if rc > 255:
        return None
    result = {"rc": rc}
    if stage == "label":
        match = ends[0].group(2) == b"1"
        if rc != 0 and match:
            return None
        result["match"] = match
    return result


def root_stage_command(token: str, stage: str, system: str = SYSTEM) -> str:
    _validate_token(token)
    scan = (
        "_k230_count=0; _k230_valid=0; while read _src _mnt _fs _opts _rest; do "
        "if test \"$_mnt\" = /sysroot; then _k230_count=$((_k230_count+1)); "
        "_ro=0; _noload=0; case \",$_opts,\" in *,ro,*) _ro=1;; esac; "
        "case \",$_opts,\" in *,noload,*|*,norecovery,*) _noload=1;; esac; "
        "if test \"$_src\" = /dev/mmcblk1p2 && test \"$_fs\" = ext4 && "
        "test $_ro -eq 1 && test $_noload -eq 1; then _k230_valid=$((_k230_valid+1)); fi; fi; "
        "done < /proc/mounts; _k230_rc=$?; _k230_mounted=0; "
        "if test $_k230_count -gt 0; then _k230_mounted=1; fi; "
    )
    commands = {
        "unmounted": scan + "if test $_k230_rc -eq 0 && test $_k230_count -ne 0; then _k230_rc=1; fi",
        "flags": scan + "if test $_k230_rc -eq 0; then "
                 "if test $_k230_count -ne 1 || test $_k230_valid -ne 1; then _k230_rc=1; fi; fi",
        "mkdir": "/bin/mkdir -p /sysroot 2>/dev/null; _k230_rc=$?",
        "empty": "_k230_rc=0; test -d /sysroot || _k230_rc=1; "
                 "for _path in /sysroot/* /sysroot/.[!.]* /sysroot/..?*; do "
                 "if test -e \"$_path\" || test -L \"$_path\"; then _k230_rc=1; fi; done",
        "mount": "/bin/mount -t ext4 -o ro,noload /dev/mmcblk1p2 /sysroot 2>/dev/null; _k230_rc=$?",
        "init": f"test -x {shlex.quote('/sysroot' + system + '/init')}; _k230_rc=$?",
        "prepare-root": f"test -x {shlex.quote('/sysroot' + system + '/prepare-root')}; _k230_rc=$?",
        "umount": "/bin/umount /sysroot 2>/dev/null; _k230_rc=$?",
    }
    commands["after-umount"] = commands["unmounted"]
    if stage not in commands:
        raise ValueError("unknown root mount stage")
    mounted = " MOUNTED=%s" if stage in ("unmounted", "after-umount", "flags") else ""
    values = ' "$_k230_rc"' + (' "$_k230_mounted"' if mounted else "")
    return (
        f"printf 'K230_RDINIT_ROOT_BEGIN {token} STAGE={stage}\\n'; "
        f"{commands[stage]}; "
        f"printf 'K230_RDINIT_ROOT_END {token} STAGE={stage} RC=%s{mounted}\\n'{values}"
    )


def root_stage_result(output: bytes, token: str, stage: str) -> dict[str, int | bool] | None:
    _validate_token(token)
    if stage not in ("unmounted", "after-umount", "flags", "mkdir", "empty", "mount", "init", "prepare-root", "umount"):
        raise ValueError("unknown root mount stage")
    text = _PROTOCOL.uart_text(output)
    scope = token.encode() + b" STAGE=" + stage.encode()
    starts = list(re.finditer(rb"^K230_RDINIT_ROOT_BEGIN " + scope + rb"\n", text, re.M))
    has_mounted = stage in ("unmounted", "after-umount", "flags")
    ends = list(re.finditer(
        rb"^K230_RDINIT_ROOT_END " + scope + rb" RC=([0-9]{1,3})" +
        (rb" MOUNTED=([01])" if has_mounted else b"") + rb"\n", text, re.M,
    ))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    rc = int(ends[0].group(1))
    if rc > 255:
        return None
    result = {"rc": rc}
    if has_mounted:
        result["mounted"] = ends[0].group(2) == b"1"
        if rc == 0 and result["mounted"] != (stage == "flags"):
            return None
    return result


def run_root_mount_protocol(session, token: str, system: str, timeout: float, clock):
    def stage(name):
        session.write((root_stage_command(token, name, system) + "\r").encode())
        bound = 60.0 if name in ("mount", "init", "prepare-root", "umount") else timeout
        result = await_protocol_marker(
            session, lambda output, fresh: root_stage_result(output, fresh, name), token, bound, clock,
        )
        if result is None:
            raise ProbeProtocolError(f"root-mount {name}")
        return {"attempted": True, **result}

    outcome = {
        "mount": {"attempted": False}, "init": {"attempted": False},
        "prepare-root": {"attempted": False}, "umount": {"attempted": False},
    }
    for name in ("unmounted", "mkdir", "empty"):
        outcome[name] = stage(name)
        if outcome[name]["rc"] != 0:
            return outcome, False
    outcome["mount"] = stage("mount")
    outcome["flags"] = stage("flags")
    ok = outcome["mount"]["rc"] == 0 and outcome["flags"]["rc"] == 0
    if ok:
        for name in ("init", "prepare-root"):
            outcome[name] = stage(name)
            if outcome[name]["rc"] != 0:
                ok = False
                break
    if outcome["mount"]["rc"] == 0 or outcome["flags"]["mounted"]:
        outcome["umount"] = stage("umount")
        ok = ok and outcome["umount"]["rc"] == 0
        if outcome["umount"]["rc"] == 0:
            outcome["after-umount"] = stage("after-umount")
            ok = ok and outcome["after-umount"]["rc"] == 0
    return outcome, ok


def survey_command(token: str) -> str:
    _validate_token(token)
    data = PROBE_DATA.replace("K230_STAGE_TOKEN", token)
    return (
        "PATH=/bin:/sbin; export PATH; "
        f"{data}; "
        f"printf 'K230_RDINIT_SURVEY {token} RC=%s\\n' \"$_k230_probe_rc\""
    )


def probe_stage_markers(output: bytes, token: str) -> tuple[str, ...]:
    """Return only unique complete stage lines for this fresh probe token."""
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("probe token must be a 32-character lowercase UUID")
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(
        rb"^K230_RDINIT_STAGE " + re.escape(token.encode()) + rb" ([a-z-]+)\n",
        text,
        re.M,
    )
    allowed = set(PROBE_STAGE_NAMES)
    if any(match.decode() not in allowed for match in matches):
        return ()
    if len(matches) != len(set(matches)):
        return ()
    return tuple(name for name in PROBE_STAGE_NAMES if name.encode() in matches)


class ProbeProtocolError(RuntimeError):
    def __init__(self, stage: str):
        super().__init__(f"initrd minimal protocol did not complete at {stage}; do not send more probe input")
        self.stage = stage


def receive_marker(output: bytes, token: str) -> bool | None:
    _validate_token(token)
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(rb"^K230_RDINIT_RX " + re.escape(token.encode()) + rb"\n", text, re.M)
    return True if len(matches) == 1 else None


def protocol_rc_marker(output: bytes, token: str, stage: str) -> int | None:
    _validate_token(token)
    tags = {"true": "K230_RDINIT_TRUE", "uptime": "K230_RDINIT_UP_END", "survey": "K230_RDINIT_SURVEY"}
    if stage not in tags:
        raise ValueError("unknown protocol RC stage")
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(
        rb"^" + tags[stage].encode() + rb" " + re.escape(token.encode()) + rb" RC=([0-9]{1,3})\n",
        text,
        re.M,
    )
    if len(matches) != 1:
        return None
    value = int(matches[0])
    return value if value <= 255 else None


def uptime_result(output: bytes, token: str) -> dict[str, object] | None:
    _validate_token(token)
    text = _PROTOCOL.uart_text(output)
    starts = list(re.finditer(rb"^K230_RDINIT_UP_BEGIN " + re.escape(token.encode()) + rb"\n", text, re.M))
    ends = list(re.finditer(rb"^K230_RDINIT_UP_END " + re.escape(token.encode()) + rb" RC=([0-9]{1,3})\n", text, re.M))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    values = re.findall(rb"^([0-9]+\.[0-9]+) ([0-9]+\.[0-9]+)$", text[starts[0].end():ends[0].start()], re.M)
    rc = int(ends[0].group(1))
    if rc > 255:
        return None
    if rc == 0 and len(values) != 1:
        return None
    if len(values) > 1:
        return None
    uptime = None
    if values:
        uptime = [values[0][0].decode(), values[0][1].decode()]
    return {"rc": rc, "uptime": uptime}


def proc_mount_result(output: bytes, token: str) -> dict[str, int | bool] | None:
    _validate_token(token)
    text = _PROTOCOL.uart_text(output)
    starts = list(re.finditer(rb"^K230_RDINIT_MOUNT_BEGIN " + re.escape(token.encode()) + rb"\n", text, re.M))
    ends = list(re.finditer(
        rb"^K230_RDINIT_MOUNT_END " + re.escape(token.encode()) +
        rb" MKDIR_RC=([0-9]{1,3}) MOUNT_ATTEMPTED=([01]) MOUNT_RC=([0-9]{1,3})\n",
        text,
        re.M,
    ))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    mkdir_rc, attempted, mount_rc = (int(value) for value in ends[0].groups())
    if mkdir_rc > 255 or mount_rc > 255:
        return None
    if (mkdir_rc == 0) != (attempted == 1):
        return None
    if not attempted and mount_rc != 255:
        return None
    return {"mkdir_rc": mkdir_rc, "mount_attempted": bool(attempted), "mount_rc": mount_rc}


def survey_rc_marker(output: bytes, token: str) -> int | None:
    return protocol_rc_marker(output, token, "survey")


def reboot_marker(output: bytes, token: str) -> bool | None:
    _validate_token(token)
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(rb"^K230_RDINIT_REBOOT " + re.escape(token.encode()) + rb"\n", text, re.M)
    return True if len(matches) == 1 else None


def reboot_chroot_refusal(output: bytes) -> bool:
    text = _PROTOCOL.uart_text(output)
    return len(re.findall(rb"^Running in chroot, ignoring request\.\n", text, re.M)) == 1


def await_protocol_marker(session, parser, token: str, timeout: float, clock=time.monotonic):
    deadline = clock() + timeout
    while clock() < deadline:
        session.pump()
        result = parser(session.buffer, token)
        if result is not None:
            return result
    return None


def await_reception(
    session,
    first_token: str,
    *,
    attempts: int = RECEPTION_MAX_ATTEMPTS,
    timeout: float = RECEPTION_ATTEMPT_TIMEOUT,
    token_factory=None,
    clock=time.monotonic,
):
    """Retry only the safe builtin receipt line until the console accepts one fresh token."""
    _validate_token(first_token)
    if not 1 <= attempts <= RECEPTION_MAX_ATTEMPTS:
        raise ValueError(f"reception attempts must be between 1 and {RECEPTION_MAX_ATTEMPTS}")
    if not 0 < timeout <= RECEPTION_ATTEMPT_TIMEOUT:
        raise ValueError(f"reception timeout must be positive and at most {RECEPTION_ATTEMPT_TIMEOUT}s")
    make_token = token_factory or (lambda: uuid.uuid4().hex)
    seen = {first_token}
    for attempt in range(attempts):
        token = first_token if attempt == 0 else make_token()
        _validate_token(token)
        if attempt and token in seen:
            raise ValueError("reception retry tokens must be fresh")
        seen.add(token)
        # Drain pending console bytes before each retry. Parser matching is scoped
        # to this fresh token, so an echo or delayed response from an older line
        # cannot make the current attempt ready.
        session.pump()
        session.write((reception_command(token) + "\r").encode())
        if await_protocol_marker(session, receive_marker, token, timeout, clock) is True:
            return token, attempt + 1
    return None


def run_probe_protocol(
    session,
    token: str,
    mode: str,
    *,
    timeout: float = 30.0,
    readiness_attempts: int = RECEPTION_MAX_ATTEMPTS,
    readiness_timeout: float = RECEPTION_ATTEMPT_TIMEOUT,
    token_factory=None,
    clock=time.monotonic,
    system: str = SYSTEM,
):
    """Run sequential tests; label and survey require every minimal RC to be zero."""
    if mode not in ("minimal", "survey", "label", "root-mount"):
        raise ValueError("probe mode must be minimal, survey, label or root-mount")
    prerequisite_schema = (
        f"k230-initrd-{mode}-prerequisite-failure-v1" if mode in ("label", "root-mount")
        else "k230-initrd-prerequisite-failure-v1"
    )
    received = await_reception(
        session,
        token,
        attempts=readiness_attempts,
        timeout=readiness_timeout,
        token_factory=token_factory,
        clock=clock,
    )
    if received is None:
        raise ProbeProtocolError("reception")
    token, reception_attempts_used = received

    session.write((true_command(token) + "\r").encode())
    true_rc = await_protocol_marker(
        session, lambda output, fresh: protocol_rc_marker(output, fresh, "true"), token, timeout, clock
    )
    if true_rc is None:
        raise ProbeProtocolError("/bin/true")

    minimal = {
        "reception_marker": True,
        "reception_attempts": reception_attempts_used,
        "true_rc": true_rc,
    }
    if true_rc != 0:
        diagnostic = {
            "schema": prerequisite_schema,
            "requested_mode": mode,
            **minimal,
            "proc_mount": {"attempted": False},
        }
        return {
            "diagnostic": diagnostic,
            "diagnostic_ok": False,
            "reboot_marker": False,
            "recovery_required": True,
            "recovery_reason": "true-command-nonzero",
        }

    session.write((proc_mount_command(token) + "\r").encode())
    mount_rc = await_protocol_marker(session, proc_mount_result, token, timeout, clock)
    if mount_rc is None:
        raise ProbeProtocolError("/bin/mkdir -p /proc and /bin/mount -t proc proc /proc")
    minimal["proc_mount"] = mount_rc
    if mount_rc["mkdir_rc"] != 0 or not mount_rc["mount_attempted"] or mount_rc["mount_rc"] != 0:
        diagnostic = {
            "schema": prerequisite_schema,
            "requested_mode": mode,
            **minimal,
            "uptime": {"attempted": False},
        }
        recovery_reason = (
            "proc-directory-setup-nonzero"
            if mount_rc["mkdir_rc"] != 0 or not mount_rc["mount_attempted"]
            else "proc-mount-nonzero"
        )
        return {
            "diagnostic": diagnostic,
            "diagnostic_ok": False,
            "reboot_marker": False,
            "recovery_required": True,
            "recovery_reason": recovery_reason,
        }

    session.write((uptime_command(token) + "\r").encode())
    uptime = await_protocol_marker(session, uptime_result, token, timeout, clock)
    if uptime is None:
        raise ProbeProtocolError("/bin/cat /proc/uptime")
    minimal["uptime_rc"] = uptime["rc"]
    minimal["uptime"] = uptime["uptime"]
    if uptime["rc"] != 0:
        diagnostic = {
            "schema": prerequisite_schema,
            "requested_mode": mode,
            **minimal,
        }
        return {
            "diagnostic": diagnostic,
            "diagnostic_ok": False,
            "reboot_marker": False,
            "recovery_required": True,
            "recovery_reason": "proc-uptime-nonzero",
        }
    minimal_ok = True
    label = None
    label_setup = {}
    if mode in ("label", "root-mount"):
        for stage in ("dev-mkdir", "dev-mount", "node"):
            session.write((label_setup_command(token, stage) + "\r").encode())
            outcome = await_protocol_marker(
                session, lambda output, fresh: label_result(output, fresh, stage), token, timeout, clock,
            )
            if outcome is None:
                raise ProbeProtocolError(f"label {stage}")
            label_setup[stage] = outcome
            if outcome["rc"] != 0:
                return {
                    "diagnostic": {
                        "schema": f"k230-initrd-{mode}-v1", "minimal": minimal,
                        "setup": label_setup, "label": {"attempted": False},
                        **({"root": {"attempted": False}} if mode == "root-mount" else {}),
                    },
                    "diagnostic_ok": False, "reboot_marker": False,
                    "recovery_required": True, "recovery_reason": f"label-{stage}-nonzero",
                }
        session.write((label_command(token) + "\r").encode())
        label = await_protocol_marker(session, label_result, token, 60.0, clock)
        if label is None:
            raise ProbeProtocolError("label read")
    root = {"attempted": False}
    root_ok = False
    if mode == "root-mount" and label["rc"] == 0 and label["match"]:
        root, root_ok = run_root_mount_protocol(session, token, system, timeout, clock)
        root = {"attempted": True, **root}
    survey = None
    if mode == "survey" and minimal_ok:
        session.write((survey_command(token) + "\r").encode())
        survey_rc = await_protocol_marker(session, survey_rc_marker, token, max(timeout, 60.0), clock)
        if survey_rc is None:
            raise ProbeProtocolError("optional survey")
        survey = {"status": "complete", "rc": survey_rc, "nixos_sd_label_present": probe_nixos_label(session.buffer)}
    elif mode == "survey":
        survey = {"status": "skipped", "reason": "minimal-stage-rc-failure"}

    # Start a fresh rolling buffer before the reboot request. A fixed offset
    # into the capped buffer stops seeing new bytes once verbose output fills
    # it; clearing also excludes pretrial login/refusal markers.
    session.buffer = b""
    session.write((reboot_command(token) + "\r").encode())
    reboot_seen = await_protocol_marker(session, reboot_marker, token, min(timeout, 5.0), clock)
    if mode == "root-mount":
        diagnostic = {
            "schema": "k230-initrd-root-mount-v1", "minimal": minimal,
            "setup": label_setup, "label": {"attempted": True, **label}, "root": root,
        }
        diagnostic_ok = root_ok
    elif mode == "label":
        diagnostic = {
            "schema": "k230-initrd-label-v1", "minimal": minimal,
            "setup": label_setup, "label": {"attempted": True, **label},
        }
        diagnostic_ok = label["rc"] == 0 and label["match"]
    elif mode == "minimal":
        diagnostic = {"schema": "k230-initrd-minimal-v2", **minimal}
        diagnostic_ok = minimal_ok
    else:
        diagnostic = {"schema": "k230-initrd-survey-v2", "minimal": minimal, "survey": survey}
        diagnostic_ok = minimal_ok and (survey is None or survey.get("rc") == 0)
    return {
        "diagnostic": diagnostic,
        "diagnostic_ok": diagnostic_ok,
        "reboot_marker": reboot_seen is True,
    }


def probe_result(output: bytes, token: str) -> int | None:
    """Return only a full output line, after stripping the known UART prefix."""
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("probe token must be a 32-character lowercase UUID")
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(
        rb"^K230_RDINIT_PROBE " + re.escape(token.encode()) + rb" RC=([0-9]{1,3})\n",
        text,
        re.M,
    )
    if len(matches) != 1:
        return None
    return int(matches[0])


def probe_nixos_label(output: bytes) -> bool | None:
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(rb"^K230_LABEL_NIXOS_SD=([01])\n", text, re.M)
    if len(matches) != 1:
        return None
    return matches[0] == b"1"


def normal_expectation(
    report_path: Path, manifest: dict[str, object], bundle: Path = BUNDLE, system: str = SYSTEM,
) -> dict[str, object]:
    report = json.loads(report_path.read_text())
    baseline = json.loads(NORMAL_BASELINE.read_text())
    if report.get("system") != "/nix/store/p1a1hz9n8s4g8qyr55ffl3dzbnjgqwr8-nixos-system-nixos-26.11.20260919.20b1ddd":
        raise ValueError("protected normal system differs from the current installed baseline")
    if report.get("profile") != report["system"]:
        raise ValueError("protected normal profile does not select the current system")
    if report.get("services") != ["active"] * 3:
        raise ValueError("protected normal report does not show all shell services active")
    if set(report.get("boot_files", {})) != {
        "Image", "initrd.uimg", "k230-tdisplay.dtb", "bootargs.txt",
        "fw_jump_add_uboot_head.bin", "force_dtb", "lcd_dtb", "hdmi_dtb",
    }:
        raise ValueError("protected normal boot-file set is incomplete")
    if report.get("kernel") != baseline["kernel"] or report["boot_files"] != baseline["boot_files"]:
        raise ValueError("protected normal kernel or boot-file identities differ from the committed baseline")
    if not isinstance(report.get("boot_id"), str) or not re.fullmatch(
        r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", report["boot_id"],
    ):
        raise ValueError("protected normal report lacks a valid boot ID")
    wrapper = manifest["files"]["fw_jump_add_uboot_head.bin"]
    protected_wrapper = report["boot_files"]["fw_jump_add_uboot_head.bin"]
    if wrapper["bytes"] != protected_wrapper["bytes"] or wrapper["sha256"].lower() != protected_wrapper["sha256"]:
        raise ValueError("manifest stage-one wrapper differs from the protected normal wrapper")
    if wrapper["crc32"].lower() != NORMAL_WRAPPER_CRC32:
        raise ValueError("manifest stage-one wrapper CRC differs from the protected normal wrapper")
    uname = "6.6.36"  # Fresh serial report and nix/kernel.nix modDirVersion.
    files = manifest["files"]
    candidate_files = {
        name: {"bytes": int(files[name]["bytes"]), "sha256": str(files[name]["sha256"]).lower()}
        for name in ("Image-mainline-drm", "k230-tdisplay-mainline-drm.dtb", "initrd.uimg", "bootargs.txt")
    }
    metadata = {}
    for name in ("registration", "store-paths", "SHA256SUMS"):
        path = bundle / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size <= 0 or path.stat().st_mode & 0o222:
            raise FileNotFoundError(f"exact trial bundle metadata is missing or unsafe: {name}")
        metadata[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "system": report["system"], "profile": report["profile"], "kernel": report["kernel"],
        "uname": uname, "boot_id": report["boot_id"], "boot_files": report["boot_files"],
        "init": "init=" + report["system"] + "/init",
        "stage": NORMAL_STAGE, "candidate_system": system,
        "candidate_files": candidate_files, "metadata_sha256": metadata,
    }


def prepare_trial(manifest_path: Path, bundle: Path, report_path: Path) -> dict[str, object]:
    """Fail closed on selected host identities before any board/serial access."""
    bundle = immutable_store_path(bundle, "candidate bundle")
    if not (bundle / "system").is_symlink():
        raise ValueError("candidate bundle must contain its system symlink")
    system_path = immutable_store_path((bundle / "system").resolve(strict=True), "candidate system")
    system = str(system_path)
    if not (system_path / "init").is_file() or not os.access(system_path / "init", os.X_OK):
        raise FileNotFoundError("candidate system init is missing")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("system") != system:
        raise ValueError("manifest does not name the expected matching trial system")
    files = manifest.get("files", {})
    if not isinstance(files, dict) or set(files) != {name for name, _, _, _ in LOADS}:
        raise ValueError("manifest file set does not match the exact trial bundle")
    validate_load_ranges(files)
    for name, _, _, _ in LOADS:
        expected = files[name]
        if not isinstance(expected.get("crc32"), str) or not re.fullmatch(r"[0-9a-fA-F]{8}", expected["crc32"]):
            raise ValueError(f"invalid artifact CRC32: {name}")
        if name == "fw_jump_add_uboot_head.bin":
            continue  # Protected normal partition; anchored below, verified on board before boot.
        artifact = bundle / name
        if (artifact.is_symlink() or not artifact.is_file()
                or artifact.stat().st_mode & 0o222 or artifact.stat().st_size != expected["bytes"]):
            raise FileNotFoundError(f"exact trial bundle artifact is missing or has wrong size: {name}")
        content = artifact.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected["sha256"].lower():
            raise ValueError(f"exact trial bundle artifact hash mismatch: {name}")
        if f"{zlib.crc32(content):08x}" != expected["crc32"].lower():
            raise ValueError(f"exact trial bundle artifact CRC mismatch: {name}")
    original_args = (bundle / "bootargs.txt").read_text()
    if not original_args.startswith("bootargs="):
        raise ValueError("bundle bootargs must be a U-Boot bootargs assignment")
    expected_args = trial_bootargs(original_args, system)
    normal = normal_expectation(report_path, manifest, bundle, system)
    return {
        "bundle": bundle, "system": system, "manifest": manifest,
        "bootargs": expected_args, "normal": normal, "helper_text": NORMAL_HELPER.read_text(),
    }


def state_marker(output: bytes, token: str, mode: str) -> dict[str, object] | None:
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(
        rb"^K230_MAINLINE_STATE " + re.escape(token.encode()) + rb" " + mode.encode() + rb" (\{[^\n]+\})\n",
        text,
        re.M,
    )
    if len(matches) != 1:
        return None
    try:
        value = json.loads(matches[0])
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def upload_marker(output: bytes, token: str) -> bool:
    text = _PROTOCOL.uart_text(output)
    lines = re.findall(
        rb"^K230_UPLOAD_" + re.escape(token.encode()) + rb"\n", text, re.M
    )
    return len(lines) == 1


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

    def upload_text(self, destination: str, content: str, token: str) -> None:
        if not re.fullmatch(r"/run/k230-mainline-[a-z-]+\.(?:py|json)", destination):
            raise ValueError("unexpected in-memory helper destination")
        self.buffer = b""
        self.write(f"cat > {destination} <<'K230_EOF'\r".encode())
        time.sleep(0.1)
        for line in content.splitlines():
            if len(line.encode()) > 2000:
                raise ValueError("helper transfer line exceeds serial shell limit")
            self.write(line.encode() + b"\r")
            time.sleep(0.002)
        self.write(b"K230_EOF\r")
        self.write(f"printf 'K230_UPLOAD_{token}\\n'\r".encode())
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            self.pump()
            if upload_marker(self.buffer, token):
                return
        raise RuntimeError("in-memory diagnostic helper transfer did not complete")

    def run_state(self, mode: str, token: str) -> dict[str, object]:
        if mode not in ("preflight", "postflight"):
            raise ValueError("unknown state mode")
        self.line(f"{BOARD_PYTHON} -I /run/k230-mainline-normal-state.py {mode} {token}", interrupt=False)
        deadline = time.monotonic() + (180 if mode == "preflight" else 90)
        while time.monotonic() < deadline:
            self.pump()
            state = state_marker(self.buffer, token, mode)
            if state is not None:
                return state
        raise RuntimeError(f"protected normal {mode} did not return a complete identity marker")

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

    def wait_for_normal_login(self, timeout: float) -> str | None:
        """Inspect only the rolling phase started before the reboot request."""
        end = time.monotonic() + timeout
        while True:
            if re.search(rb"^nixos login:(?:[ \t]|$)", _PROTOCOL.uart_text(self.buffer), re.M):
                return "login"
            if reboot_chroot_refusal(self.buffer):
                return "chroot-refusal"
            if time.monotonic() >= end:
                return None
            self.pump()

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


def write_private_result(path: Path, value: dict[str, object]) -> None:
    result_fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(result_fd, "w") as result_file:
        json.dump(value, result_file, indent=2, sort_keys=True)
        result_file.write("\n")


def run_trial(
    manifest_path: Path, log_path: Path, result_path: Path, mode: str,
    bundle: Path = BUNDLE, normal_report: Path = NORMAL_REPORT,
    ignore_unused_clocks: bool = False,
    debug_shutdown: bool = False,
) -> bool:
    if mode not in ("minimal", "survey", "label", "root-mount"):
        raise ValueError("probe mode must be minimal, survey, label or root-mount")
    if ignore_unused_clocks and mode != "label":
        raise ValueError("--ignore-unused-clocks requires --mode label")
    if debug_shutdown and mode != "minimal":
        raise ValueError("--debug-shutdown requires --mode minimal")
    prepared = prepare_trial(manifest_path, bundle, normal_report)
    manifest = prepared["manifest"]
    system = prepared["system"]
    files = manifest["files"]
    expected_args = prepared["bootargs"]
    if ignore_unused_clocks or debug_shutdown:
        expected_args = trial_bootargs(
            (bundle / "bootargs.txt").read_text(), system,
            ignore_unused_clocks=ignore_unused_clocks, debug_shutdown=debug_shutdown,
        )
    normal = prepared["normal"]
    helper_text = prepared["helper_text"]
    selection = {"ignore_unused_clocks": ignore_unused_clocks} if mode == "label" else {}
    if debug_shutdown:
        selection["debug_shutdown"] = True
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError("pyserial is required; use nix shell nixpkgs#python3Packages.pyserial") from exc

    log_path = safe_log_path(log_path)
    result_path = safe_log_path(result_path)
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
        recovery_login_seen = False
        recovery_identity_verified = False
        probe_outcome = None
        try:
            session = PrivateSession(serial, log_file)
            session.write(b"\x03\r")
            if not session.wait_for(b"root@nixos", 15):
                raise RuntimeError("root serial shell not observed; no reboot or file access attempted")

            preflight_token = uuid.uuid4().hex
            session.upload_text("/run/k230-mainline-normal-state.py", helper_text, preflight_token)
            session.upload_text(
                "/run/k230-mainline-expected.json",
                json.dumps(normal, indent=2),
                preflight_token,
            )
            observed_before = session.run_state("preflight", preflight_token)
            if (
                observed_before.get("system") != normal["system"]
                or observed_before.get("profile") != normal["profile"]
                or observed_before.get("kernel") != normal["kernel"]
                or observed_before.get("uname") != normal["uname"]
                or observed_before.get("init") != normal["init"]
                or observed_before.get("boot_files") != {
                    name: info["sha256"] for name, info in normal["boot_files"].items()
                }
            ):
                raise RuntimeError("preflight identity differs from the fresh protected normal report")
            normal["trial_from_boot_id"] = observed_before["boot_id"]

            session.line("reboot", interrupt=False)
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
                crc = session.command(f"crc32 {address} {hex(int(expected['bytes']))}", 40)
                if not verified_load(load, expected):
                    raise RuntimeError(f"strict load report failed for {name}; no candidate boot was issued")
                if not verified_crc(crc, expected):
                    raise RuntimeError(f"count/CRC mismatch for {name}; no candidate boot was issued")

            args = session.command(
                f"env import -t 0x7000000 {hex(int(files['bootargs.txt']['bytes']))}", 15
            )
            if args is None:
                raise RuntimeError("could not import the matching volatile bootargs")
            # U-Boot imports the complete exact bootargs file above. Expand its
            # saved value only inside volatile RAM, then append diagnostic arguments.
            command = volatile_bootargs_command(
                ignore_unused_clocks, **({"debug_shutdown": True} if debug_shutdown else {}),
            )
            if session.command(command, 15) is None:
                raise RuntimeError("could not set volatile rdinit bootargs")
            printed = session.command("printenv bootargs", 15)
            if not verified_bootargs(printed, expected_args):
                raise RuntimeError("volatile bootargs do not contain both matching init paths")
            if "rdinit=/bin/sh" not in expected_args:
                raise AssertionError("pure bootargs validation disagreed with U-Boot check")

            session.line("bootm 0x8000000 0x9000000 0x8400000", interrupt=False)
            boot_started = True
            in_uboot = False
            if not session.wait_for(b"Linux version 7.3.0-rc5", 45):
                raise RuntimeError("Linux version banner not observed; reset may be required")
            token = uuid.uuid4().hex
            try:
                probe_outcome = run_probe_protocol(session, token, mode, system=system)
            except ProbeProtocolError as exc:
                if mode not in ("label", "root-mount"):
                    raise
                write_private_result(result_path, {
                    "result_schema": f"mainline-initrd-{mode}-unknown-v1",
                    "status": "recovery-required-unknown-no-reboot-requested",
                    "mode": f"volatile-rdinit-{mode}", **selection,
                    "candidate_system": system, "candidate_bundle": str(prepared["bundle"]),
                    "normal_preflight": observed_before,
                    "probe": {"schema": f"k230-initrd-{mode}-unknown-v1", "stage": exc.stage},
                    "reboot_marker_observed": False, "normal_recovery": None,
                    "persistent_boot_selection_changed": False, "raw_serial_log_path": str(log_path),
                })
                print(f"{mode} protocol incomplete at {exc.stage}; no further probe or recovery input was sent. "
                      "Protected normal recovery is required and unverified.", file=sys.stderr)
                return False
            if probe_outcome.get("recovery_required"):
                reason = str(probe_outcome["recovery_reason"])
                write_private_result(result_path, {
                    "result_schema": "mainline-initrd-diagnostic-v3",
                    **selection,
                    "status": "recovery-required-no-reboot-requested",
                    "mode": f"volatile-rdinit-{mode}",
                    "candidate_system": system,
                    "candidate_bundle": str(prepared["bundle"]),
                    "normal_preflight": observed_before,
                    "probe": probe_outcome["diagnostic"],
                    "reboot_marker_observed": False,
                    "normal_recovery": None,
                    "recovery_reason": reason,
                    "persistent_boot_selection_changed": False,
                    "raw_serial_log_path": str(log_path),
                })
                print(
                    f"Diagnostic stopped at {reason}; no reboot was requested because safe reset prerequisites failed. "
                    f"Protected normal recovery is not yet verified; private serial log: {log_path}",
                    file=sys.stderr,
                )
                return False

            login_state = session.wait_for_normal_login(180)
            if login_state == "chroot-refusal":
                write_private_result(result_path, {
                    "result_schema": "mainline-initrd-diagnostic-v3",
                    **selection,
                    "status": "recovery-required-systemctl-chroot-refusal",
                    "mode": f"volatile-rdinit-{mode}",
                    "candidate_system": system,
                    "candidate_bundle": str(prepared["bundle"]),
                    "normal_preflight": observed_before,
                    "probe": probe_outcome["diagnostic"],
                    "reboot_marker_observed": probe_outcome["reboot_marker"],
                    "normal_recovery": None,
                    "recovery_reason": "systemctl-reboot-alias-refused-in-chroot",
                    "persistent_boot_selection_changed": False,
                    "raw_serial_log_path": str(log_path),
                })
                print(
                    "systemctl refused the reboot as a chroot; no retry was sent. "
                    f"Protected normal recovery is not verified; private serial log: {log_path}",
                    file=sys.stderr,
                )
                return False
            if login_state != "login":
                raise RuntimeError("normal login not observed after initrd reboot")
            recovery_login_seen = True
            if not session.wait_for(b"root@nixos", 30):
                raise RuntimeError("recovered root shell not observed; preserved recovery identities remain unchecked")
            post_token = uuid.uuid4().hex
            session.upload_text("/run/k230-mainline-normal-state.py", helper_text, post_token)
            session.upload_text(
                "/run/k230-mainline-expected.json",
                json.dumps(normal, indent=2),
                post_token,
            )
            observed_after = session.run_state("postflight", post_token)
            if (
                observed_after.get("system") != normal["system"]
                or observed_after.get("profile") != normal["profile"]
                or observed_after.get("kernel") != normal["kernel"]
                or observed_after.get("uname") != normal["uname"]
                or observed_after.get("init") != normal["init"]
                or observed_after.get("boot_files") != {
                    name: info["sha256"] for name, info in normal["boot_files"].items()
                }
                or observed_after.get("services") != ["active"] * 3
            ):
                raise RuntimeError("recovered system/kernel/profile/services/protected files differ from baseline")
            recovery_identity_verified = True
            diagnostic_ok = bool(probe_outcome["diagnostic_ok"])
            status = (
                "recovery-verified-diagnostic-passed"
                if diagnostic_ok else "recovery-verified-diagnostic-failed"
            )
            print(f"Protected normal recovery identities verified; private serial log: {log_path}")
            print("Recovered system, kernel, profile, services, boot ID, and eight protected boot-file hashes verified.")
            print(f"Diagnostic mode: {mode}; result: {status}; reboot marker: {probe_outcome['reboot_marker']}.")
            safe_result = {
                "result_schema": "mainline-initrd-diagnostic-v3",
                **selection,
                "status": status,
                "mode": f"volatile-rdinit-{mode}",
                "candidate_system": system,
                "candidate_bundle": str(prepared["bundle"]),
                "normal_preflight": observed_before,
                "probe": probe_outcome["diagnostic"],
                "reboot_marker_observed": probe_outcome["reboot_marker"],
                "normal_recovery": observed_after,
                "persistent_boot_selection_changed": False,
                "raw_serial_log_path": str(log_path),
            }
            write_private_result(result_path, safe_result)
            return diagnostic_ok
        except Exception:
            if session is not None and in_uboot and not boot_started:
                # All pre-boot failures leave Linux/normal boot files intact.
                session.line("reset", interrupt=False)
                print("Pre-boot failure: reset requested; normal boot selection is unchanged.", file=sys.stderr)
            elif boot_started:
                if recovery_identity_verified:
                    print(
                        "Protected normal recovery identities were verified; the diagnostic probe "
                        "failed its required mount/block-label checks. Keep the physical gate open.",
                        file=sys.stderr,
                    )
                elif recovery_login_seen:
                    print(
                        "Normal login returned but recovered identities were not verified. "
                        "Do not declare recovery or change boot files; preserve the board for inspection.",
                        file=sys.stderr,
                    )
                else:
                    print(
                        "Linux started; PID 1 may still be the diagnostic shell. Do not send exit. "
                        "Keep the reservation and use the agreed physical power-cycle recovery only "
                        "if automatic reboot did not return to normal login.",
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
    parser.add_argument("--bundle", type=Path, default=BUNDLE,
                        help="exact immutable candidate boot bundle; system is derived from its system symlink")
    parser.add_argument("--normal-report", type=Path, default=NORMAL_REPORT,
                        help="protected normal identity report matching the committed baseline")
    parser.add_argument(
        "--mode", choices=("minimal", "survey", "label", "root-mount"), default="minimal",
        help="minimal by default; label, read-only root mount and full survey require explicit modes",
    )
    parser.add_argument("--ignore-unused-clocks", action="store_true",
                        help="label mode only: add volatile clk_ignore_unused for the bounded clock discriminator")
    parser.add_argument("--debug-shutdown", action="store_true",
                        help="minimal mode only: add volatile initcall_debug loglevel=8 shutdown tracing")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser.add_argument(
        "--log", type=Path,
        default=PRIVATE_LOG_DIR / f"mainline-initrd-shell-{stamp}.private.log",
    )
    parser.add_argument(
        "--result", type=Path,
        default=PRIVATE_LOG_DIR / f"mainline-initrd-shell-{stamp}.result.json",
    )
    args = parser.parse_args()
    if args.ignore_unused_clocks and args.mode != "label":
        parser.error("--ignore-unused-clocks requires --mode label")
    if args.debug_shutdown and args.mode != "minimal":
        parser.error("--debug-shutdown requires --mode minimal")
    try:
        diagnostic_ok = run_trial(
            args.manifest, args.log, args.result, args.mode, args.bundle, args.normal_report,
            **({"ignore_unused_clocks": True} if args.ignore_unused_clocks else {}),
            **({"debug_shutdown": True} if args.debug_shutdown else {}),
        )
    except Exception as exc:
        print(f"Trial stopped: {exc}", file=sys.stderr)
        return 1
    return 0 if diagnostic_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

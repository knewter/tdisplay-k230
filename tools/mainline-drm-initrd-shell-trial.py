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
from datetime import datetime, timezone
from pathlib import Path


BUNDLE = Path(
    "/nix/store/gf3aqks2dg0z3ksz33ysfprnlbk83vw3-"
    "k230-mainline-drm-trial-boot-files"
)
SYSTEM = "/nix/store/k9f4r2i9k9qj58z8z4l2kssy9rpwxxm1-nixos-system-nixos-26.11.20260919.20b1ddd"
NORMAL_REPORT = Path("/home/jadams/tmp/k230-coherent-boot-board/received/after.json")
NORMAL_HELPER = Path(__file__).with_name("mainline-drm-normal-state.py")
NORMAL_STAGE = "/var/lib/k230-mainline-drm-trial"
BOARD_PYTHON = "/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3"
MANIFEST_DEFAULT = Path("/home/jadams/tmp/k230-coordination/mainline-boot-manifest.json")
PRIVATE_LOG_DIR = Path("/home/jadams/tmp/k230-coordination/mainline-initrd-private")
LOCK_PATH = Path("/tmp/k230-board.lock")
SERIAL_DEVICE = "/dev/ttyACM0"
PROMPT = b"K230# "
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


def reboot_command(token: str) -> str:
    _validate_token(token)
    return f"printf 'K230_RDINIT_REBOOT {token}\\n'; /bin/reboot -ff"


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


def survey_rc_marker(output: bytes, token: str) -> int | None:
    return protocol_rc_marker(output, token, "survey")


def reboot_marker(output: bytes, token: str) -> bool | None:
    _validate_token(token)
    text = _PROTOCOL.uart_text(output)
    matches = re.findall(rb"^K230_RDINIT_REBOOT " + re.escape(token.encode()) + rb"\n", text, re.M)
    return True if len(matches) == 1 else None


def await_protocol_marker(session, parser, token: str, timeout: float, clock=time.monotonic):
    deadline = clock() + timeout
    while clock() < deadline:
        session.pump()
        result = parser(session.buffer, token)
        if result is not None:
            return result
    return None


def run_probe_protocol(session, token: str, mode: str, *, timeout: float = 30.0, clock=time.monotonic):
    """Run short sequential tests; survey is gated on every minimal RC being zero."""
    if mode not in ("minimal", "survey"):
        raise ValueError("probe mode must be minimal or survey")
    session.write((reception_command(token) + "\r").encode())
    if await_protocol_marker(session, receive_marker, token, timeout, clock) is None:
        raise ProbeProtocolError("reception")

    session.write((true_command(token) + "\r").encode())
    true_rc = await_protocol_marker(
        session, lambda output, fresh: protocol_rc_marker(output, fresh, "true"), token, timeout, clock
    )
    if true_rc is None:
        raise ProbeProtocolError("/bin/true")

    session.write((uptime_command(token) + "\r").encode())
    uptime = await_protocol_marker(session, uptime_result, token, timeout, clock)
    if uptime is None:
        raise ProbeProtocolError("/bin/cat /proc/uptime")

    minimal = {"reception_marker": True, "true_rc": true_rc, "uptime_rc": uptime["rc"], "uptime": uptime["uptime"]}
    minimal_ok = true_rc == 0 and uptime["rc"] == 0
    survey = None
    if mode == "survey" and minimal_ok:
        session.write((survey_command(token) + "\r").encode())
        survey_rc = await_protocol_marker(session, survey_rc_marker, token, max(timeout, 60.0), clock)
        if survey_rc is None:
            raise ProbeProtocolError("optional survey")
        survey = {"status": "complete", "rc": survey_rc, "nixos_sd_label_present": probe_nixos_label(session.buffer)}
    elif mode == "survey":
        survey = {"status": "skipped", "reason": "minimal-stage-rc-failure"}

    session.write((reboot_command(token) + "\r").encode())
    reboot_seen = await_protocol_marker(session, reboot_marker, token, min(timeout, 5.0), clock)
    if mode == "minimal":
        diagnostic = {"schema": "k230-initrd-minimal-v1", **minimal}
        diagnostic_ok = minimal_ok
    else:
        diagnostic = {"schema": "k230-initrd-survey-v1", "minimal": minimal, "survey": survey}
        diagnostic_ok = minimal_ok and (survey is None or survey.get("rc") == 0)
    return {"diagnostic": diagnostic, "diagnostic_ok": diagnostic_ok, "reboot_marker": reboot_seen is True}


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


def normal_expectation(report_path: Path, manifest: dict[str, object]) -> dict[str, object]:
    report = json.loads(report_path.read_text())
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
    uname = "6.6.36"  # Fresh serial report and nix/kernel.nix modDirVersion.
    files = manifest["files"]
    candidate_files = {
        name: {"bytes": int(files[name]["bytes"]), "sha256": str(files[name]["sha256"]).lower()}
        for name in ("Image-mainline-drm", "k230-tdisplay-mainline-drm.dtb", "initrd.uimg", "bootargs.txt")
    }
    bundle = BUNDLE
    metadata = {}
    for name in ("registration", "store-paths", "SHA256SUMS"):
        metadata[name] = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
    return {
        "system": report["system"], "profile": report["profile"], "kernel": report["kernel"],
        "uname": uname, "boot_id": report["boot_id"], "boot_files": report["boot_files"],
        "init": "init=" + report["system"] + "/init",
        "stage": NORMAL_STAGE, "candidate_system": SYSTEM,
        "candidate_files": candidate_files, "metadata_sha256": metadata,
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


def run_trial(manifest_path: Path, log_path: Path, result_path: Path, mode: str) -> bool:
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
        try:
            session = PrivateSession(serial, log_file)
            session.write(b"\x03\r")
            if not session.wait_for(b"root@nixos", 15):
                raise RuntimeError("root serial shell not observed; no reboot or file access attempted")

            normal = normal_expectation(NORMAL_REPORT, manifest)
            preflight_token = uuid.uuid4().hex
            helper_text = NORMAL_HELPER.read_text()
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
            token = uuid.uuid4().hex
            probe_outcome = run_probe_protocol(session, token, mode)
            if not session.wait_for(b"nixos login:", 180):
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
                "result_schema": "mainline-initrd-diagnostic-v2",
                "status": status,
                "mode": f"volatile-rdinit-{mode}",
                "candidate_system": SYSTEM,
                "normal_preflight": observed_before,
                "probe": probe_outcome["diagnostic"],
                "reboot_marker_observed": probe_outcome["reboot_marker"],
                "normal_recovery": observed_after,
                "persistent_boot_selection_changed": False,
                "raw_serial_log_path": str(log_path),
            }
            result_fd = os.open(result_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(result_fd, "w") as result_file:
                json.dump(safe_result, result_file, indent=2, sort_keys=True)
                result_file.write("\n")
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
    parser.add_argument(
        "--mode", choices=("minimal", "survey"), default="minimal",
        help="minimal sequential discriminator by default; full device survey requires explicit survey mode",
    )
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
    try:
        diagnostic_ok = run_trial(args.manifest, args.log, args.result, args.mode)
    except Exception as exc:
        print(f"Trial stopped: {exc}", file=sys.stderr)
        return 1
    return 0 if diagnostic_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

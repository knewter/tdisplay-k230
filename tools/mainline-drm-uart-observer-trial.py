#!/usr/bin/env python3
"""Reserved-operator observer trial: one receipt, then passive candidate return.

The selected Zstandard initrd requires host Python 3.14 compression.zstd.
Unsupported hosts fail artifact preparation before opening the UART.
"""
from __future__ import annotations

import argparse
import fcntl
import gzip
import hashlib
import importlib.util
import io
import json
import os
import posixpath
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import zlib

_spec = importlib.util.spec_from_file_location("observer_debug", Path(__file__).with_name("mainline-drm-initrd-debug-trial.py"))
debug = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(debug)
system, rd = debug.system, debug.rd
BASE_BUNDLE = Path("/nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files")
BASE_KERNEL = "/nix/store/9vdk79pa4pm38mlmbflkqh4i4sc9kha0-linux-riscv64-unknown-linux-gnu-7.3.0-rc5"
MAX_PAYLOAD = 384
STREAM_LIMIT = 1048576
STAGES = ("ready", "before", "after", "return")
KERNEL_PREFIX = rb"(?:\[\s*[0-9]+\.[0-9]+\] )?"
SAMPLE_FIELDS = {"sample", "iflag", "oflag", "cflag", "lflag", "ispeed_code", "ospeed_code", "ldisc", "rx", "tx", "frame", "overrun", "parity", "brk", "buf_overrun", "irq", "irq_available", "irq_total", "runtime"}
SOURCE_FILE = Path(__file__).resolve().parents[1] / "nix/mainline-uart-observer/observer.c"
BASE_DEBUG_UNIT_SHA = "edc8fe166b94d3c9e76879662780679b6092944f88e9966a27a41f0aa2767a81"
ARCHIVE_LIMIT = 134217728


def riscv_elf(content):
    return len(content) >= 64 and content[:7] == b"\x7fELF\x02\x01\x01" and int.from_bytes(content[18:20], "little") == 243


def archive_entries(compressed):
    """Read a bounded exact newc archive; no extraction into the host filesystem."""
    if compressed.startswith(b"\x28\xb5\x2f\xfd"):
        try:
            from compression import zstd
        except ImportError as exc:
            raise ValueError("Zstandard initrd inspection requires host Python 3.14 compression.zstd") from exc
        stream_reader = lambda: zstd.ZstdFile(io.BytesIO(compressed))
    elif compressed.startswith(b"\x1f\x8b"):
        stream_reader = lambda: gzip.GzipFile(fileobj=io.BytesIO(compressed))
    else:
        raise ValueError("unsupported observer initrd compression")
    with stream_reader() as stream:
        data = stream.read(ARCHIVE_LIMIT + 1)
        if len(data) > ARCHIVE_LIMIT:
            raise ValueError("observer initrd uncompressed size exceeds bound")
    entries = {}
    offset = 0
    trailer = False
    while offset < len(data):
        if data[offset:offset + 6] == bytes(6) and not any(data[offset:]):
            break
        if data[offset:offset + 6] != b"070701" or offset + 110 > len(data):
            raise ValueError("observer initrd is not a complete newc archive")
        try:
            fields = [int(data[offset + 6 + i * 8:offset + 14 + i * 8], 16) for i in range(13)]
        except ValueError as exc:
            raise ValueError("malformed newc header") from exc
        size, name_size = fields[6], fields[11]
        name_start = offset + 110
        body_start = (name_start + name_size + 3) & ~3
        body_end = body_start + size
        if not 0 < name_size <= 4096 or body_end > len(data) or data[name_start + name_size - 1:name_start + name_size] != b"\0":
            raise ValueError("truncated newc entry")
        name = data[name_start:name_start + name_size - 1].decode("utf-8", "strict").removeprefix("./")
        if name == "TRAILER!!!":
            trailer = True
            offset = (body_end + 3) & ~3
            if any(data[offset:]):
                raise ValueError("unexpected data after initrd trailer")
            break
        if name.startswith("/") or ".." in name.split("/") or name in entries:
            raise ValueError("unsafe or duplicate newc path")
        entries[name] = (fields[1], data[body_start:body_end])
        offset = (body_end + 3) & ~3
    if not trailer:
        raise ValueError("missing initrd trailer")
    return entries


def archive_resolve(entries, path):
    path = path.lstrip("/")
    for _ in range(32):
        parts = path.split("/")
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            mode, body = entries.get(prefix, (0, b""))
            if mode & 0o170000 == 0o120000:
                target = body.decode("utf-8", "strict")
                tail = "/".join(parts[i:])
                absolute = target if target.startswith("/") else "/" + posixpath.dirname(prefix) + "/" + target
                path = posixpath.normpath(absolute + "/" + tail).lstrip("/")
                break
        else:
            if path not in entries:
                raise ValueError("required initrd path missing")
            return path
    raise ValueError("initrd symlink chain exceeds bound")


def inspect_initrd(payload, helper_path, helper_bytes):
    entries = archive_entries(payload)
    helper_name = archive_resolve(entries, helper_path)
    mode, body = entries[helper_name]
    if mode & 0o170000 != 0o100000 or not mode & 0o111 or body != helper_bytes or not riscv_elf(body):
        raise ValueError("selected initrd lacks exact executable RISC-V observer")
    unit_name = archive_resolve(entries, "/etc/systemd/system/debug-shell.service")
    unit_body = entries[unit_name][1]
    if hashlib.sha256(unit_body).hexdigest() != BASE_DEBUG_UNIT_SHA:
        raise ValueError("original debug-shell unit changed")
    root = archive_resolve(entries, "/etc/systemd/system")
    dropins = [name for name in entries if name.startswith(root + "/debug-shell.service.d/") and name.endswith(".conf")]
    if len(dropins) != 1:
        raise ValueError("expected one observer debug-shell drop-in")
    dropin_body = entries[archive_resolve(entries, dropins[0])][1]
    lines = [line for line in dropin_body.decode("utf-8", "strict").splitlines() if line and not line.startswith("#")]
    environment = []
    service_seen = False
    for line in lines:
        if line == "[Service]":
            service_seen = True
        if line.startswith("Environment="):
            if not service_seen:
                raise ValueError("observer environment outside service section")
            environment.extend(shlex.split(line.removeprefix("Environment=")))
    env = [item.split("=", 1) for item in environment]
    if (len(env) != 2 or any(len(pair) != 2 for pair in env)
            or {pair[0] for pair in env} != {"LOCALE_ARCHIVE", "TZDIR"}
            or any(not re.fullmatch(r"/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+/(?:lib/locale/locale-archive|share/zoneinfo)", pair[1]) for pair in env)):
        raise ValueError("observer drop-in environment changed")
    if any(not value.endswith("/lib/locale/locale-archive" if key == "LOCALE_ARCHIVE" else "/share/zoneinfo") for key, value in env):
        raise ValueError("observer locale/timezone environment mismatch")
    lines = [line for line in lines if not line.startswith("Environment=")]
    expected = ["[Unit]", "ConditionKernelCommandLine=k230.uobs.nonce", "[Service]", "ExecStart=", "ExecStart=" + helper_path, "Restart=no"]
    if lines != expected:
        raise ValueError("observer debug-shell drop-in contents changed")
    version = entries[archive_resolve(entries, "/etc/k230-uobs-version")][1]
    if version != b"1\n":
        raise ValueError("observer version marker missing")
    return {"helper_sha256": hashlib.sha256(body).hexdigest(), "unit_sha256": hashlib.sha256(unit_body).hexdigest(), "dropin_sha256": hashlib.sha256(dropin_body).hexdigest(), "initrd_sha256": hashlib.sha256(payload).hexdigest()}


class Invalid(RuntimeError):
    pass


def console_arguments(original, serial_console_only=False):
    if not serial_console_only:
        return original
    args = original.removesuffix("\n")
    value = args.removeprefix("bootargs=")
    tokens = list(re.finditer(r"\S+", value))
    consoles = [m.group() for m in tokens if m.group().partition("=")[0] == "console"]
    blanks = [m.group() for m in tokens if m.group().partition("=")[0] == "consoleblank"]
    if sorted(consoles) != ["console=tty0", "console=ttyS0,115200n8"] or blanks != ["consoleblank=0"]:
        raise ValueError("serial comparison requires sole exact tty0/ttyS0 consoles and consoleblank=0")
    match = next(m for m in tokens if m.group() == "console=tty0")
    start, end = match.span()
    if value[end:end + 1] == " ":
        end += 1
    elif start and value[start - 1] == " ":
        start -= 1
    result = "bootargs=" + value[:start] + value[end:]
    return result + ("\n" if original.endswith("\n") else "")


def uboot_literal(value):
    # Double-quoted literal data: no expansion, substitution or command syntax.
    if not value or not re.fullmatch(r"[A-Za-z0-9_./,:=+? -]+", value):
        raise ValueError("unsafe volatile U-Boot argument syntax")
    return '"' + value + '"'


def bootargs(original, selected, nonce, normal_boot, *, serial_console_only=False):
    rd._validate_token(nonce)
    if not debug.valid_boot_id(normal_boot):
        raise ValueError("normal boot ID must be exact")
    for arg in original.removeprefix("bootargs=").split():
        if arg.partition("=")[0].startswith("k230.uobs."):
            raise ValueError("preexisting observer argument")
    result = debug.bootargs(console_arguments(original, serial_console_only), selected) + f" k230.uobs.nonce={nonce} k230.uobs.from={normal_boot} k230.uobs.init={selected}/init"
    uboot_literal(result.removeprefix("bootargs="))
    return result


def receipt_command(nonce):
    rd._validate_token(nonce)
    return f"printf '\\nK230_UOBS_RX {nonce}\\n'".encode() + b"\r"


def dt_hardware_equal(base, candidate):
    """Only remove /chosen/bootargs from owned temporary copies, never sources."""
    with tempfile.TemporaryDirectory(prefix="k230-uobs-dtb-", dir=Path.home() / "tmp") as scratch:
        normalized = []
        for name, source in (("base", base), ("candidate", candidate)):
            target = Path(scratch) / (name + ".dtb")
            target.write_bytes(source.read_bytes())
            subprocess.run(["fdtput", "-d", str(target), "/chosen", "bootargs"], check=True, capture_output=True, timeout=10)
            normalized.append(subprocess.run(["dtc", "-I", "dtb", "-O", "dts", "-s", str(target)], check=True, capture_output=True, timeout=10).stdout)
        return normalized[0] == normalized[1]


def prepare(bundle, manifest, normal_report, blkid_result, nonce, *, serial_console_only=False):
    p = rd.prepare_trial(manifest, bundle, normal_report)
    base = rd.immutable_store_path(BASE_BUNDLE, "proven base bundle")
    base_system = rd.immutable_store_path((base / "system").resolve(strict=True), "proven base system")
    debug.validate_prerequisite(debug.private_input(blkid_result), {"bundle": base, "system": str(base_system), "normal": p["normal"]})
    path = p["bundle"] / "observer.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o222 or path.stat().st_size > 8192:
        raise ValueError("unsafe observer metadata")
    metadata = json.loads(path.read_text())
    required = {"schema", "protocol", "helper", "helper_sha256", "helper_source_sha256", "system", "init", "kernel", "dtb_sha256", "base_bundle", "window_ms", "payload_max", "base_dtb_sha256", "base_kernel", "dtb_bootargs_only"}
    if set(metadata) != required:
        raise ValueError("unexpected observer metadata fields")
    expected = {"schema": "k230-uart-observer-artifact-v1", "protocol": "K230_UOBS_V1", "system": p["system"], "init": p["system"] + "/init", "kernel": BASE_KERNEL, "base_bundle": str(base), "window_ms": 12000, "payload_max": MAX_PAYLOAD, "base_kernel": BASE_KERNEL, "dtb_bootargs_only": True}
    if any(type(metadata.get(key)) is not type(value) or metadata.get(key) != value for key, value in expected.items()):
        raise ValueError("observer metadata identity or protocol mismatch")
    helper = Path(metadata["helper"])
    if helper.name != "k230-uart-observer" or helper.parent.name != "bin":
        raise ValueError("unexpected observer executable")
    rd.immutable_store_path(helper.parent.parent, "observer executable package")
    if helper.is_symlink() or not helper.is_file() or helper.stat().st_mode & 0o222 or not os.access(helper, os.X_OK):
        raise ValueError("unsafe observer executable")
    if not riscv_elf(helper.read_bytes()):
        raise ValueError("observer executable is not ELF64 little-endian RISC-V")
    dtb_name = "k230-tdisplay-mainline-drm.dtb"
    checks = {"helper_sha256": helper, "helper_source_sha256": SOURCE_FILE, "dtb_sha256": p["bundle"] / dtb_name, "base_dtb_sha256": base / dtb_name}
    if any(not re.fullmatch(r"[0-9a-f]{64}", metadata[k]) or hashlib.sha256(v.read_bytes()).hexdigest() != metadata[k] for k, v in checks.items()):
        raise ValueError("observer source or artifact digest mismatch")
    covered = re.findall(r"^([0-9a-f]{64})  observer\.json$", (p["bundle"] / "SHA256SUMS").read_text(), re.M)
    if covered != [hashlib.sha256(path.read_bytes()).hexdigest()]:
        raise ValueError("observer metadata not uniquely SHA-covered")
    kernel = (Path(p["system"]) / "kernel").resolve(strict=True)
    if str(kernel) != BASE_KERNEL + "/Image" or (p["bundle"] / "Image-mainline-drm").read_bytes() != (base / "Image-mainline-drm").read_bytes():
        raise ValueError("observer changed the proven base kernel")
    if not dt_hardware_equal(base / dtb_name, p["bundle"] / dtb_name):
        raise ValueError("observer changed DT hardware properties")
    image = (p["bundle"] / "initrd.uimg").read_bytes()
    if len(image) < 64:
        raise ValueError("observer ramdisk wrapper truncated")
    header = struct.unpack(">7I4B32s", image[:64])
    check_header = bytearray(image[:64]); check_header[4:8] = bytes(4)
    if (header[0] != 0x27051956 or header[7:11] != (5, 26, 3, 0)
            or header[3] != len(image) - 64 or header[6] != zlib.crc32(image[64:])
            or header[1] != zlib.crc32(check_header)
            or image[64:] != (Path(p["system"]) / "initrd").read_bytes()):
        raise ValueError("observer ramdisk differs from selected system")
    paths = (p["bundle"] / "store-paths").read_text().splitlines()
    if any(str(path) not in paths for path in (helper.parent.parent, Path(p["system"]), kernel.parent)):
        raise ValueError("observer closure lacks selected helper/system/kernel")
    p["initrd_inspection"] = inspect_initrd(image[64:], str(helper), helper.read_bytes())
    selected_args = (p["bundle"] / "bootargs.txt").read_text()
    dt_args = subprocess.run(["fdtget", str(p["bundle"] / dtb_name), "/chosen", "bootargs"], check=True, capture_output=True, text=True, timeout=10).stdout.strip()
    if dt_args != selected_args.removeprefix("bootargs=").rstrip("\n"):
        raise ValueError("observer DT bootargs mismatch")
    p["bootargs"] = bootargs(selected_args, p["system"], nonce, p["normal"]["boot_id"], serial_console_only=serial_console_only)
    p["serial_console_only"] = serial_console_only
    p["original_bootargs"] = selected_args
    p["observer"] = metadata
    p["helper_text"] = "from pathlib import Path\nassert not Path('/nix-path-registration').exists() and not Path('/nix-path-registration').is_symlink(), 'registration marker present'\n" + p["helper_text"]
    volatile_commands(p)  # Validate every outgoing argument command before UART.
    return p


def validate_record(record, previous, from_boot):
    stage, fields = record["stage"], record["properties"]
    if stage in ("ready", "return"):
        required = {"boot_id", "shell_pid", "guards", "window_ms" if stage == "ready" else "reboot"}
        if set(fields) != required or fields["guards"] != "1" or not debug.valid_boot_id(fields["boot_id"]) or fields["boot_id"] == from_boot or not re.fullmatch(r"[1-9][0-9]{0,9}", fields["shell_pid"]) or not 1 < int(fields["shell_pid"]) < 2**31:
            raise Invalid("observer identity or guards invalid")
        if fields["window_ms" if stage == "ready" else "reboot"] != ("12000" if stage == "ready" else "1"):
            raise Invalid("observer timing or return acknowledgement invalid")
        if stage == "return" and any(fields[k] != previous[0]["properties"][k] for k in ("boot_id", "shell_pid")):
            raise Invalid("observer return identity changed")
    elif stage in ("before", "after"):
        if set(fields) != SAMPLE_FIELDS or fields["sample"] != stage or fields["runtime"] not in ("active", "suspended", "unknown"):
            raise Invalid("observer sample fields invalid")
        for key in ("iflag", "oflag", "cflag", "lflag"):
            if not re.fullmatch(r"[0-9a-f]{8}", fields[key]):
                raise Invalid("observer termios flag malformed")
        for key in SAMPLE_FIELDS - {"sample", "runtime", "iflag", "oflag", "cflag", "lflag"}:
            if not re.fullmatch(r"[0-9]{1,20}", fields[key]) or int(fields[key]) > 2**64 - 1:
                raise Invalid("observer numeric field malformed")
        if fields["irq_available"] not in ("0", "1") or fields["irq_available"] == "0" and fields["irq_total"] != "0":
            raise Invalid("observer unavailable IRQ counter inconsistent")
        if stage == "after" and fields["irq"] != previous[1]["properties"]["irq"]:
            raise Invalid("observer UART IRQ identity changed")
    else:
        raise Invalid("unknown observer stage")


def decode_frame(line, nonce):
    """One whole printk record; inserted output cannot be stripped into validity."""
    rd._validate_token(nonce)
    start = re.match(KERNEL_PREFIX + rb"K230_UOBS_V1 ([0-9a-f]{32})(?: |$)", line)
    if start is None:
        if re.match(KERNEL_PREFIX + rb"K230_UOBS_V1(?: |$)", line):
            raise Invalid("malformed observer record")
        return None
    if start[1] != nonce.encode():
        return None
    match = re.fullmatch(KERNEL_PREFIX + rb"K230_UOBS_V1 ([0-9a-f]{32}) ([0-9]+) ([a-z-]+) ([0-9]+) ([0-9a-f]{8}) ([0-9a-f]+)\n", line)
    if match is None:
        raise Invalid("malformed fresh observer record")
    seq, stage, size = int(match[2]), match[3].decode(), int(match[4])
    if not 0 < size <= MAX_PAYLOAD or len(match[6]) != size * 2:
        raise Invalid("observer payload size mismatch")
    raw = bytes.fromhex(match[6].decode())
    if f"{zlib.crc32(raw):08x}".encode() != match[5]:
        raise Invalid("observer payload checksum mismatch")
    if not raw.endswith(b"\n") or any(c < 32 and c != 10 or c > 126 for c in raw):
        raise Invalid("observer payload must be complete ASCII properties")
    pairs = [row.split("=", 1) for row in raw.decode().splitlines()]
    if any(len(pair) != 2 or not re.fullmatch(r"[a-z][a-z0-9_]*", pair[0]) for pair in pairs) or len({p[0] for p in pairs}) != len(pairs):
        raise Invalid("malformed or duplicate observer fields")
    return {"seq": seq, "stage": stage, "properties": dict(pairs), "bytes": size, "sha256": hashlib.sha256(raw).hexdigest()}


class Observation:
    """Accumulate returned chunks independently of the transport's rolling buffer."""
    def __init__(self, nonce, from_boot):
        rd._validate_token(nonce)
        self.nonce = nonce
        self.from_boot = from_boot
        self.text = b""
        self.frames = []
        self.failure = None
        self.banner = self.manager = self.primary = False
        self.spl = self.normal_banner = self.normal_login = self.normal_prompt = False
        self.receipt_count = 0
        self.pending = b""
        self.sent = False
        self.total_bytes = 0
        self.failed_frame = None

    def fail(self, reason):
        self.failure = self.failure or reason

    def feed(self, chunk):
        self.total_bytes += len(chunk)
        self.text += chunk
        if len(self.text) > STREAM_LIMIT:
            self.fail("observer stream exceeded byte bound")
            # Continue passive recovery with bounded parsing memory.
            self.text = self.text[-131072:]
        self.pending += chunk
        while b"\n" in self.pending:
            line, self.pending = self.pending.split(b"\n", 1)
            line = line.rstrip(b"\r") + b"\n"
            if len(line) > MAX_PAYLOAD * 2 + 256:
                self.fail("observer line exceeded byte bound")
                continue
            if re.match(KERNEL_PREFIX + rb"Linux version 7\.3\.0-rc5(?: |\n)", line):
                self.banner = True
            if self.banner and re.search(rb"systemd 261\.2(?= |\n)", line):
                self.manager = True
            if self.banner:
                try:
                    record = decode_frame(line, self.nonce)
                    if record is not None:
                        if self.spl:
                            raise Invalid("observer record arrived after recovery began")
                        expected = len(self.frames)
                        if record["stage"] == "failed":
                            fields = record["properties"]
                            if (record["seq"] != expected or set(fields) != {"phase", "reason"}
                                    or fields["phase"] not in ("initial", "observe", "renew")
                                    or fields["reason"] not in ("guard", "snapshot", "fork", "clock")):
                                raise Invalid("malformed observer failure frame")
                            self.failed_frame = record
                            self.fail("observer reported failed guards or work")
                        elif expected >= len(STAGES) or (record["seq"], record["stage"]) != (expected, STAGES[expected]):
                            self.fail("duplicate or out-of-order observer frame")
                        else:
                            validate_record(record, self.frames, self.from_boot)
                            self.frames.append(record)
                except (Invalid, ValueError) as exc:
                    self.fail(str(exc))
                if line == f"K230_UOBS_RX {self.nonce}\n".encode():
                    if not self.sent:
                        self.fail("receipt output preceded the single stimulus")
                    self.receipt_count += 1
                    if self.receipt_count > 1:
                        self.fail("duplicate receipt output")
            # Recovery has its own fresh ordered gate. A failed/missing
            # candidate banner must not hide a later protected normal boot.
            if re.match(rb"U-Boot SPL(?: |\n)", line):
                self.spl = True
            if self.spl and re.match(KERNEL_PREFIX + rb"Linux version 6\.6\.36(?: |\n)", line):
                self.normal_banner = True
            if self.normal_banner and re.match(rb"nixos login:(?: |\n)", line):
                self.normal_login = True
        if len(self.pending) > MAX_PAYLOAD * 2 + 256:
            self.fail("incomplete observer line exceeded byte bound")
            self.pending = self.pending[-256:]
        # A primary prompt may be followed immediately by asynchronous status.
        normalized = rd._PROTOCOL.uart_text(self.text)
        banner = re.search(rb"(?:^|\n)" + KERNEL_PREFIX + rb"Linux version 7\.3\.0-rc5(?: |\n)", normalized)
        if banner:
            tail = normalized[banner.end():]
            manager = re.search(rb"systemd 261\.2(?= |\n)", tail)
            if manager and re.search(rb"(?:^|\n)(?:\x1b\[\?2004h)?sh-[0-9]+\.[0-9]+# ", tail[manager.end():]):
                self.primary = True
        if self.normal_login and system.prompt(normalized):
            self.normal_prompt = True

    @property
    def ready(self):
        return self.failure is None and self.banner and self.manager and self.primary and len(self.frames) >= 2 and self.frames[0]["stage"] == "ready" and self.frames[1]["stage"] == "before"


def monitor(session, nonce, from_boot, *, clock=time.monotonic, ready_timeout=180, return_timeout=180):
    system.finite_timeout(ready_timeout, 180)
    system.finite_timeout(return_timeout, 180)
    state = Observation(nonce, from_boot)
    start = clock()
    deadline = start + ready_timeout
    ready_at = returned_at = None
    while clock() < deadline:
        try:
            state.feed(session.pump())
        except Exception as exc:
            state.fail("passive transport failed: " + type(exc).__name__)
            break
        now = clock()
        if ready_at is None and state.frames:
            ready_at = now
            deadline = max(deadline, ready_at + return_timeout)
        if returned_at is None and len(state.frames) == 4:
            returned_at = now
            deadline = max(deadline, returned_at + return_timeout)
        # The observer's window closes before renewed guards/direct return.
        # Do not send a late command merely because an old prompt is visible.
        if not state.sent and state.ready and len(state.frames) == 2 and not state.spl and now < ready_at + 12:
            state.sent = True
            session.write(receipt_command(nonce))
        if ready_at is not None and returned_at is None and now >= ready_at + 60:
            state.fail("autonomous return acknowledgement unknown after 60s")
        if state.normal_prompt:
            break
    if not state.normal_prompt:
        state.fail("fresh protected normal return unknown after bounded passive wait")
    if not state.sent:
        state.fail("READY/before/primary-prompt reception gate incomplete")
    if state.receipt_count != 1:
        state.fail("single receipt acknowledgement unknown or duplicate")
    if len(state.frames) != 4:
        state.fail("autonomous observer frames incomplete")
    facts = {
        "readiness_observed": state.sent,
        "receipt_attempted": state.sent,
        "receipt_acknowledged": state.receipt_count == 1,
        "frames": state.frames,
        "failed_frame": state.failed_frame,
        "observer_complete": len(state.frames) == 4,
        "return_acknowledged": len(state.frames) == 4,
        "spl_observed": state.spl,
        "normal_banner_observed": state.normal_banner,
        "normal_login_observed": state.normal_login,
        "normal_prompt_observed": state.normal_prompt,
        "wire_bytes": state.total_bytes,
        "passed": state.failure is None,
    }
    if state.failure:
        facts["failure"] = state.failure
    return facts


def volatile_commands(p):
    base = console_arguments(p["original_bootargs"], p.get("serial_console_only", False)).rstrip("\n")
    if not p["bootargs"].startswith(base + " "):
        raise ValueError("volatile observer argument prefix mismatch")
    controls = p["bootargs"][len(base) + 1:]
    uboot_literal(controls)
    commands = [f"env import -t 0x7000000 {hex(p['manifest']['files']['bootargs.txt']['bytes'])}"]
    if p.get("serial_console_only", False):
        commands.append("setenv bootargs " + uboot_literal(base.removeprefix("bootargs=")))
    commands.append('setenv bootargs "${bootargs} ' + controls + '"')
    if any(len(command.encode()) >= 512 for command in commands):
        raise ValueError("volatile U-Boot command exceeds conservative line bound")
    return commands


def boot(session, p, clock=time.monotonic):
    commands = volatile_commands(p)
    session.buffer = b""
    session.line("reboot", interrupt=False)
    end = clock() + 35
    while clock() < end:
        session.pump()
        if b"Hit any key to stop autoboot" in session.buffer:
            session.write(b" ")
        if rd.PROMPT in session.buffer:
            break
    else:
        raise Invalid("U-Boot prompt unknown")
    for name, partition, address, source in rd.LOADS:
        expected = p["manifest"]["files"][name]
        if not rd.verified_load(session.command(f"ext4load mmc {partition} {address} {source}", 90), expected):
            raise Invalid("candidate load mismatch; no boot")
        if not rd.verified_crc(session.command(f"crc32 {address} {hex(expected['bytes'])}", 40), expected):
            raise Invalid("candidate CRC mismatch; no boot")
    for command in commands:
        if session.command(command, 15) is None:
            raise Invalid("volatile observer arguments unverified")
    if not rd.verified_bootargs(session.command("printenv bootargs", 15), p["bootargs"]):
        raise Invalid("printed exact observer bootargs mismatch; no boot")
    session.buffer = b""
    session.line("bootm 0x8000000 0x9000000 0x8400000", interrupt=False)


def run(args):
    log_path = rd.safe_log_path(args.log)
    result_path = rd.safe_log_path(args.result)
    if log_path == result_path:
        raise ValueError("distinct private log/result paths required")
    comparison = getattr(args, "serial_console_only", False)
    result = {"schema": "mainline-uart-observer-v1", "status": "not-started-no-serial-opened", "candidate_bundle": str(args.bundle), "serial_console_only": comparison, "diagnostic": {}, "normal_recovery": None, "persistent_boot_selection_changed": False, "raw_serial_log_path": str(log_path)}
    session = None
    lock_fd = None
    log_created = False
    try:
        nonce = uuid.uuid4().hex
        p = prepare(args.bundle, args.manifest, args.normal_report, args.blkid_result, nonce, serial_console_only=comparison)
        result.update(candidate_system=p["system"], observer_artifact=p["observer"], initrd_inspection=p["initrd_inspection"], nonce=nonce)
        normal = dict(p["normal"])
        import serial
        lock_fd = os.open(rd.LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with os.fdopen(os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb", buffering=0) as log:
            log_created = True
            session = rd.PrivateSession(serial, log)
            result["status"] = "recovery-required-unknown"
            session.buffer = b""
            session.write(b"\r")
            if not system.wait_prompt(session):
                raise Invalid("fresh protected normal prompt unknown")
            before = system.normal_check(session, p, normal, "preflight")
            result["normal_preflight"] = before
            normal["trial_from_boot_id"] = before["boot_id"]
            p["bootargs"] = bootargs(p["original_bootargs"], p["system"], nonce, before["boot_id"], serial_console_only=comparison)
            result["expected_bootargs"] = p["bootargs"]
            boot(session, p)
            result["candidate_boot_issued"] = True
            facts = monitor(session, nonce, before["boot_id"])
            result["diagnostic"] = facts
            if not facts["normal_prompt_observed"]:
                raise Invalid("no fresh protected normal return; operator recovery required")
            # Only a new SPL -> exact normal banner -> login -> prompt permits
            # input again. No candidate recovery command is ever sent here.
            result["normal_recovery"] = system.normal_check(session, p, normal, "postflight")
            result["status"] = ("recovery-verified-diagnostic-passed" if facts["passed"] else "recovery-verified-diagnostic-failed")
        wire = log_path.read_bytes()
        result["raw_serial_log_bytes"] = len(wire)
        result["raw_serial_log_sha256"] = hashlib.sha256(wire).hexdigest()
        rd.write_private_result(result_path, result)
        return result["status"] == "recovery-verified-diagnostic-passed"
    except Exception as exc:
        result["failure"] = type(exc).__name__ + ": " + str(exc)
        if log_created:
            wire = log_path.read_bytes()
            result["raw_serial_log_bytes"] = len(wire)
            result["raw_serial_log_sha256"] = hashlib.sha256(wire).hexdigest()
        rd.write_private_result(result_path, result)
        print("Observer trial stopped; private evidence preserved. No candidate input or reboot retry.", file=sys.stderr)
        return False
    finally:
        if session is not None:
            session.close()
        if lock_fd is not None:
            os.close(lock_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "manifest", "normal-report", "blkid-result", "log", "result"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--serial-console-only", action="store_true", help="volatile comparison: remove only the sole console=tty0; hardware result UNVERIFIED")
    return 0 if run(parser.parse_args()) else 2


if __name__ == "__main__":
    raise SystemExit(main())

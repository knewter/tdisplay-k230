#!/usr/bin/env python3
"""Qualified ordinary-init trial; only the reserved operator may run this.

begin leaves the candidate running. touch and finish require the same fresh
boot identity. Unknown command completion stops input, without recovery guesses.
Raw output and resumable state stay in protected files outside the repository.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import time
import uuid

_spec = importlib.util.spec_from_file_location("mainline_rdinit", Path(__file__).with_name("mainline-drm-initrd-shell-trial.py"))
rd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rd)
CONTROLS = ("fsck.mode=skip", "systemd.mask=k230-root-growth.service", "systemd.mask=register-nix-paths.service")
TRACE_ENABLE = ("k230.boot_trace=1", "k230.boot_trace_sbi_only=1")
INITRD_DEBUG_LOGGING = ("rd.systemd.log_level=debug", "rd.systemd.log_target=console")
STAGES = {
    "identity": ("uid", "system", "booted", "kernel", "uname", "boot_id", "pid1", "getty"),
    "persistent": ("profile", "registration_absent", "root_source", "root_type", "root_options", "root_uuid", "root_label"),
    "bootargs": ("cmdline", "growth_mask", "registration_mask"),
    "hashes": tuple(sorted(json.loads(rd.NORMAL_BASELINE.read_text())["boot_files"])),
    "device": ("count", "event", "ancestry"),
    "capture": ("capture_rc",),
    "reboot": ("reboot_rc",),
}


class Unknown(RuntimeError):
    def __init__(self, reason: str, facts=None):
        super().__init__(reason)
        self.facts = facts


def finite_timeout(value: float, maximum: float) -> None:
    if not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError("timeout must be positive, finite and bounded")


def diagnostic_controls(wait_initramfs_in_initcall: bool = False, *, without_boot_markers: bool = False,
                        initrd_debug_logging: bool = False) -> tuple[str, ...]:
    if type(wait_initramfs_in_initcall) is not bool:
        raise ValueError("initramfs comparison selector must be boolean")
    if type(without_boot_markers) is not bool:
        raise ValueError("marker comparison selector must be boolean")
    if type(initrd_debug_logging) is not bool:
        raise ValueError("initrd logging selector must be boolean")
    if initrd_debug_logging and not (wait_initramfs_in_initcall and without_boot_markers):
        raise ValueError("initrd logging requires synchronous initramfs and marker-free ordinary init")
    if without_boot_markers and not wait_initramfs_in_initcall:
        raise ValueError("marker comparison requires the earlier initramfs join comparison")
    return CONTROLS + (("initramfs_async=0",) if wait_initramfs_in_initcall else ()) + (INITRD_DEBUG_LOGGING if initrd_debug_logging else ())


def ordinary_bootargs(original: str, system: str, *, wait_initramfs_in_initcall: bool = False,
                      without_boot_markers: bool = False, initrd_debug_logging: bool = False) -> str:
    controls = diagnostic_controls(wait_initramfs_in_initcall, without_boot_markers=without_boot_markers,
                                   initrd_debug_logging=initrd_debug_logging)
    args = original[:-1] if original.endswith("\n") else original
    if not original.startswith("bootargs=") or args.strip() != args:
        raise ValueError("expected exact single-line bundle bootargs")
    if any(ord(c) < 32 for c in args):
        raise ValueError("bootargs contain control characters")
    params = args.removeprefix("bootargs=").split()
    if [p for p in params if p.startswith("init=")] != [f"init={system}/init"] or params.count("root=fstab") != 1:
        raise ValueError("bootargs do not select the exact init and root")
    for p in params:
        name, _, value = p.partition("=")
        canonical = name.replace("-", "_").removeprefix("rd.")
        if initrd_debug_logging and (canonical.startswith(("systemd.log_", "systemd.journald.", "udev.",
                                                           "k230.uart_progress", "k230.uobs.")) or
                                    canonical in {"systemd.setenv", "systemd.unit", "systemd.mask", "systemd.debug_shell",
                                                  "systemd.break", "fsck.mode", "initcall_debug", "clk_ignore_unused",
                                                  "ignore_loglevel", "debug", "quiet", "nohz", "nohlt"}):
            raise ValueError("conflicting inherited initrd logging/instrumentation argument")
        if (name in {"rdinit", "PATH", "clk_ignore_unused", "initcall_debug", "initramfs_async", "fsck.mode", "systemd.mask", "systemd.unit", "systemd.debug_shell", "systemd.break", "rd.systemd.unit", "rd.systemd.mask", "rd.systemd.debug_shell", "rd.systemd.break", "ignore_loglevel", "debug", "quiet", "dyndbg"}
                or name.endswith(".dyndbg") or (name == "loglevel" and value not in tuple(map(str, range(8))))):
            raise ValueError("conflicting ordinary-init diagnostic argument")
    if wait_initramfs_in_initcall:
        if any([p for p in params if p.partition("=")[0] == flag.partition("=")[0]] != [flag]
               for flag in TRACE_ENABLE):
            raise ValueError("initramfs comparison requires the qualified SBI-only candidate")
        if [p for p in params if p.partition("=")[0] == "console"] != ["console=ttyS0,115200n8"]:
            raise ValueError("initramfs comparison requires the sole qualified serial console")
        if any(p.partition("=")[0] in {"earlycon", "keep_bootcon", "k230.boot_trace_sbi"} for p in params):
            raise ValueError("conflicting initramfs comparison instrumentation")
    if without_boot_markers:
        args = "bootargs=" + " ".join(p for p in params if p not in TRACE_ENABLE)
    return args + " " + " ".join(controls)


def prepare(bundle: Path, manifest: Path, normal_report: Path, *, wait_initramfs_in_initcall: bool = False,
            without_boot_markers: bool = False, initrd_debug_logging: bool = False) -> dict:
    controls = diagnostic_controls(wait_initramfs_in_initcall, without_boot_markers=without_boot_markers,
                                   initrd_debug_logging=initrd_debug_logging)
    p = rd.prepare_trial(manifest, bundle, normal_report)
    p["bootargs"] = ordinary_bootargs((bundle / "bootargs.txt").read_text(), p["system"],
                                     wait_initramfs_in_initcall=wait_initramfs_in_initcall,
                                     without_boot_markers=without_boot_markers,
                                     initrd_debug_logging=initrd_debug_logging)
    p["diagnostic_controls"] = controls
    p["without_boot_markers"] = without_boot_markers
    if initrd_debug_logging:
        p["initrd_debug_logging"] = True
    volatile_bootargs_command(p)
    p["kernel"] = str((Path(p["system"]) / "kernel").resolve().parent)
    p["pid1"] = str((Path(p["system"]) / "init").resolve())
    for tool in ("sh", "cat", "id", "readlink", "uname", "findmnt", "systemctl", "sha256sum", "timeout", "evtest"):
        if not os.access(Path(p["system"]) / "sw/bin" / tool, os.X_OK):
            raise ValueError("candidate lacks a required shell diagnostic tool")
    # Original helper remains unchanged. Both protected phases reject a pending
    # registration marker before executing any checks or printing success.
    p["helper_text"] = "from pathlib import Path\nassert not Path('/nix-path-registration').exists() and not Path('/nix-path-registration').is_symlink(), 'registration marker present'\n" + p["helper_text"]
    return p


def prompt(output: bytes) -> bool:
    text = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", rd._PROTOCOL.uart_text(output))
    return re.search(rb"(?:^|\n)[^\n]*root@nixos[^\n]*# ?$", text) is not None


def wait_prompt(session, timeout=15.0, clock=time.monotonic) -> bool:
    finite_timeout(timeout, 180)
    end = clock() + timeout
    while clock() < end:
        session.pump()
        if prompt(session.buffer):
            return True
    return False


def wait_candidate(session, timeout=180.0, clock=time.monotonic) -> bool:
    """Fresh boot phase only; no input before banner, autologin and root prompt."""
    finite_timeout(timeout, 180)
    end = clock() + timeout
    banner_seen = False
    login_seen = False
    while clock() < end:
        chunk = session.pump()
        output = rd._PROTOCOL.uart_text(session.buffer)
        if not banner_seen:
            m = re.search(rb"(?:^|\n)(?:\[\s*[0-9]+\.[0-9]+\] )?Linux version 7\.3\.0-rc5(?: |\n)", output)
            if m:
                banner_seen = True
                session.buffer = output[m.end():]
        elif not login_seen:
            m = re.search(rb"(?:^|\n)nixos login:(?: |\n)", output)
            if m:
                login_seen = True
                session.buffer = output[m.end():]
        if banner_seen and login_seen and prompt(session.buffer):
            return True
    return False


def envelope(token: str, stage: str, body: str) -> str:
    rd._validate_token(token)
    if stage not in STAGES:
        raise ValueError("unknown system stage")
    return f"printf 'K230_SYS_BEGIN {token} {stage}\\n'; " + body + f"; printf 'K230_SYS_END {token} {stage}\\n'"


def field(token: str, name: str, command: str) -> str:
    return f"_v=$({command}); _rc=$?; printf 'K230_SYS {token} {name} RC=%s VALUE=%s\\n' \"$_rc\" \"$_v\""


def report_command(token: str, stage: str, system: str) -> str:
    b = f"_b={shlex.quote(system + '/sw/bin')}; "
    commands = {
        "identity": {
            "uid": '"$_b/id" -u', "system": '"$_b/readlink" -f /run/current-system',
            "booted": '"$_b/readlink" -f /run/booted-system', "kernel": '"$_b/readlink" -f /run/booted-system/kernel',
            "uname": '"$_b/uname" -r', "boot_id": '"$_b/cat" /proc/sys/kernel/random/boot_id',
            "pid1": '"$_b/readlink" -f /proc/1/exe', "getty": '"$_b/systemctl" is-active serial-getty@ttyS0.service',
        },
        "persistent": {
            "profile": '"$_b/readlink" -f /nix/var/nix/profiles/system',
            "registration_absent": "if test ! -e /nix-path-registration && test ! -L /nix-path-registration; then printf 1; else printf 0; fi",
            **{f"root_{key}": f'"$_b/findmnt" -n -o {column} --target /' for key, column in (("source", "SOURCE"), ("type", "FSTYPE"), ("options", "OPTIONS"), ("uuid", "UUID"), ("label", "LABEL"))},
        },
        "bootargs": {
            "cmdline": '"$_b/cat" /proc/cmdline',
            "growth_mask": '"$_b/systemctl" show -p LoadState --value k230-root-growth.service',
            "registration_mask": '"$_b/systemctl" show -p LoadState --value register-nix-paths.service',
        },
        "hashes": {name: f'"$_b/sha256sum" /boot/{shlex.quote(name)}' for name in STAGES["hashes"]},
    }
    if stage not in commands:
        raise ValueError("not an identity report stage")
    command = envelope(token, stage, b + "; ".join(field(token, k, v) for k, v in commands[stage].items()))
    if len(command.encode()) >= 3500:
        raise ValueError("report exceeds serial line bound")
    return command


def parse_report(output: bytes, token: str, stage: str) -> dict | None:
    rd._validate_token(token)
    text = rd._PROTOCOL.uart_text(output)
    start = f"K230_SYS_BEGIN {token} {stage}\n".encode()
    end = f"K230_SYS_END {token} {stage}\n".encode()
    starts = list(re.finditer(rb"^" + re.escape(start), text, re.M))
    ends = list(re.finditer(rb"^" + re.escape(end), text, re.M))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    body = text[starts[0].end():ends[0].start()]
    rows = re.findall(rb"^K230_SYS " + token.encode() + rb" ([a-zA-Z0-9_.-]+) RC=([0-9]{1,3}) VALUE=([^\n]*)\n", body, re.M)
    if len(rows) != len(STAGES[stage]) or {k.decode() for k, _, _ in rows} != set(STAGES[stage]):
        return None
    if b"".join(f"K230_SYS {token} ".encode() + k + b" RC=" + rc + b" VALUE=" + value + b"\n" for k, rc, value in rows) != body:
        return None
    if stage != "reboot" and not prompt(text[ends[0].end():]):
        return None
    try:
        values = {k.decode(): {"rc": int(rc), "value": value.decode("utf-8", "strict")} for k, rc, value in rows}
    except UnicodeError:
        return None
    return values if all(v["rc"] <= 255 for v in values.values()) else None


def exchange(session, token: str, stage: str, command: str, timeout=20.0, clock=time.monotonic) -> dict:
    finite_timeout(timeout, 60)
    session.system_stage = stage
    session.buffer = b""
    session.write(command.encode() + b"\r")
    deadline = clock() + timeout
    received = b""
    while clock() < deadline:
        chunk = session.pump()
        if isinstance(chunk, bytes):
            received += chunk
        else:
            received = session.buffer
        if len(received) > 262144:
            raise Unknown(stage + " output exceeded bound")
        result = parse_report(received, token, stage)
        if result is not None:
            if any(v["rc"] != 0 for v in result.values()):
                raise Unknown(stage + " returned nonzero", facts=result)
            return {k: v["value"] for k, v in result.items()}
    raise Unknown(stage + " completion unverified")


def identity(session, prepared: dict, normal: dict, *, expected_boot: str | None = None, root: dict | None = None, facts=None) -> dict:
    facts = {} if facts is None else facts
    for stage in ("identity", "persistent", "bootargs", "hashes"):
        token = uuid.uuid4().hex
        try:
            value = exchange(session, token, stage, report_command(token, stage, prepared["system"]))
        except Unknown as exc:
            if exc.facts is not None:
                facts[stage] = {"failed_fields": exc.facts}
            raise
        facts[stage] = value
        validate_stage(stage, value, prepared, normal, expected_boot=expected_boot, root=root)
    return facts


def validate_stage(stage: str, v: dict, p: dict, normal: dict, *, expected_boot=None, root=None) -> None:
    if stage == "identity":
        expected = {"uid": "0", "system": p["system"], "booted": p["system"], "kernel": p["kernel"] + "/Image", "uname": "7.3.0-rc5", "pid1": p["pid1"], "getty": "active"}
        if any(v.get(k) != x for k, x in expected.items()) or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", v.get("boot_id", "")):
            raise Unknown("candidate identity mismatch")
        if v["boot_id"] == normal["trial_from_boot_id"] or (expected_boot is not None and v["boot_id"] != expected_boot):
            raise Unknown("candidate boot identity is stale or changed")
    elif stage == "persistent":
        if (v["profile"] != normal["profile"] or v["registration_absent"] != "1" or v["root_type"] != "ext4"
                or v["root_label"] != "NIXOS_SD" or not v["root_uuid"] or v["root_source"] != "/dev/mmcblk1p2"
                or "rw" not in v["root_options"].split(",") or "ro" in v["root_options"].split(",")):
            raise Unknown("persistent profile or root identity mismatch")
        if root is not None and any(v[k] != root[k] for k in ("root_source", "root_type", "root_uuid", "root_label")):
            raise Unknown("root differs from preflight")
    elif stage == "bootargs":
        if v["cmdline"].split() != p["bootargs"].removeprefix("bootargs=").split() or v["growth_mask"] != "masked" or v["registration_mask"] != "masked":
            raise Unknown("qualified boot controls mismatch")
    elif stage == "hashes":
        for name, info in normal["boot_files"].items():
            if v[name].split() != [info["sha256"], "/boot/" + name]:
                raise Unknown("protected boot hash changed")


def device_command(token: str, system: str) -> str:
    body = f"_b={shlex.quote(system + '/sw/bin')}; _n=0; _e=; _a=; "
    body += "for _p in /sys/class/input/event*; do if test -r \"$_p/device/name\" && test \"$(\"$_b/cat\" \"$_p/device/name\")\" = 'Goodix Berlin Capacitive TouchScreen'; then _n=$((_n+1)); _e=${_p##*/}; _a=$(\"$_b/readlink\" -f \"$_p/device\"); fi; done; "
    body += "; ".join(field(token, k, cmd) for k, cmd in (("count", 'printf %s "$_n"'), ("event", 'printf %s "$_e"'), ("ancestry", 'printf %s "$_a"')))
    return envelope(token, "device", body)


def validate_device(v: dict) -> str:
    if v.get("count") != "1" or not re.fullmatch(r"event[0-9]+", v.get("event", "")) or not re.fullmatch(r"/sys/devices/platform/soc/91408000\.i2c/i2c-[0-9]+/[0-9]+-005d/input/input[0-9]+", v.get("ancestry", "")):
        raise Unknown("Goodix node is absent, ambiguous or has unexpected physical ancestry")
    return "/dev/input/" + v["event"]


def capture_command(token: str, system: str, event: str, seconds=30) -> str:
    rd._validate_token(token)
    if type(seconds) is not int or not 1 <= seconds <= 30 or not re.fullmatch(r"/dev/input/event[0-9]+", event):
        raise ValueError("invalid bounded touch capture")
    b = shlex.quote(system + "/sw/bin")
    command = f"if test -c {event}; then umask 077; {b}/timeout --signal=TERM --kill-after=2s {seconds}s {b}/evtest {event} > /run/k230-mainline-touch-{token}.log 2>&1; _v=$?; else _v=255; fi; printf 'K230_SYS {token} capture_rc RC=0 VALUE=%s\\n' \"$_v\""
    return envelope(token, "capture", command)


def parse_touch(output: bytes) -> dict:
    rows = []
    for line in output.splitlines():
        m = re.fullmatch(rb"Event: time [0-9]+\.[0-9]+, type [0-9]+ \((EV_ABS|EV_SYN)\), code [0-9]+ \((ABS_MT_SLOT|ABS_MT_TRACKING_ID|ABS_MT_POSITION_X|ABS_MT_POSITION_Y|SYN_REPORT)\), value (-?[0-9]+)", line)
        if m:
            rows.append((m[1], m[2], int(m[3])))
        elif re.fullmatch(rb"Event: time [0-9]+\.[0-9]+, -+ SYN_REPORT -+", line):
            rows.append((b"EV_SYN", b"SYN_REPORT", 0))
    slots = {}
    slot = 0
    down = up = False
    moved = False
    complete = False
    syn_after_up = False
    for typ, code, value in rows:
        code = code.decode()
        if code == "ABS_MT_SLOT" and value >= 0:
            slot = value
        elif code == "ABS_MT_TRACKING_ID" and value >= 0:
            slots[slot] = {"active": True, "position": {}, "frames": set(), "released": False}
            down = True
        elif code == "ABS_MT_TRACKING_ID" and value == -1 and slots.get(slot, {}).get("active"):
            slots[slot]["active"] = False; slots[slot]["released"] = True; up = True
        elif code in ("ABS_MT_POSITION_X", "ABS_MT_POSITION_Y") and slots.get(slot, {}).get("active"):
            slots[slot]["position"][code] = value
        elif typ == b"EV_SYN" and code == "SYN_REPORT":
            for contact in slots.values():
                if contact["active"] and len(contact["position"]) == 2:
                    contact["frames"].add(tuple(sorted(contact["position"].items())))
                    moved = moved or len(contact["frames"]) >= 2
                elif contact["released"]:
                    syn_after_up = True
                    complete = complete or len(contact["frames"]) >= 2
                    contact["released"] = False
    return {"down": down, "position_change": moved, "up": up, "syn_after_up": syn_after_up, "complete_contact": complete, "event_rows": len(rows), "coordinate_mapping": "UNVERIFIED"}


def touch(session, p: dict) -> dict:
    token = uuid.uuid4().hex
    device = exchange(session, token, "device", device_command(token, p["system"]))
    event = validate_device(device)
    token = uuid.uuid4().hex
    result = exchange(session, token, "capture", capture_command(token, p["system"], event), timeout=40)
    if result["capture_rc"] not in ("0", "124"):
        raise Unknown("touch capture failed; no file retrieval attempted")
    session.buffer = b""
    session.system_stage = "touch-retrieval"
    command = f"printf 'K230_TOUCH_BEGIN {token}\\n'; {shlex.quote(p['system'] + '/sw/bin/cat')} /run/k230-mainline-touch-{token}.log; _rc=$?; printf 'K230_TOUCH_END {token} RC=%s\\n' \"$_rc\""
    session.write(command.encode() + b"\r")
    deadline = time.monotonic() + 20
    data = b""
    while time.monotonic() < deadline:
        chunk = session.pump(); data += chunk or b""
        if len(data) > 262144:
            raise Unknown("touch retrieval exceeded bound")
        text = rd._PROTOCOL.uart_text(data)
        pattern = rb"^K230_TOUCH_BEGIN " + token.encode() + rb"\n(.*?)^K230_TOUCH_END " + token.encode() + rb" RC=0\n"
        matches = list(re.finditer(pattern, text, re.M | re.S))
        if len(matches) == 1 and prompt(text[matches[0].end():]):
            if len(re.findall(rb"^K230_TOUCH_(?:BEGIN|END) " + token.encode() + rb"(?: |\n)", text, re.M)) != 2:
                break
            return {"device": device, "capture_rc": int(result["capture_rc"]), "events": parse_touch(matches[0].group(1)), "provenance": "operator-declared-real-glass; serial events alone cannot prove provenance"}
    raise Unknown("touch retrieval completion unverified")


def normal_check(session, p: dict, normal: dict, mode: str) -> dict:
    token = uuid.uuid4().hex
    session.upload_text("/run/k230-mainline-normal-state.py", p["helper_text"], token)
    session.upload_text("/run/k230-mainline-expected.json", json.dumps(normal, indent=2), token)
    state = session.run_state(mode, token)
    required = {"system": normal["system"], "profile": normal["profile"], "kernel": normal["kernel"], "uname": normal["uname"], "init": normal["init"], "services": ["active"] * 3, "boot_files": {k: v["sha256"] for k, v in normal["boot_files"].items()}}
    if any(state.get(k) != value for k, value in required.items()) or (mode == "postflight" and state.get("boot_id") == normal["trial_from_boot_id"]):
        raise Unknown("protected normal identity mismatch")
    return {**state, "nix_path_registration_absent": True}


def wait_normal(session, timeout=180.0, clock=time.monotonic) -> bool:
    finite_timeout(timeout, 180)
    deadline = clock() + timeout
    spl = banner = login = False
    while clock() < deadline:
        session.pump()
        text = rd._PROTOCOL.uart_text(session.buffer)
        spl = spl or b"U-Boot SPL" in text
        banner = banner or re.search(rb"(?:^|\n)(?:\[\s*[0-9]+\.[0-9]+\] )?Linux version 6\.6\.36(?: |\n)", text) is not None
        login = login or re.search(rb"(?:^|\n)nixos login:(?: |\n)", text) is not None
        if spl and banner and login and prompt(text):
            return True
    return False


def volatile_bootargs_command(p: dict) -> str:
    controls = tuple(p.get("diagnostic_controls", CONTROLS))
    debug = p.get("initrd_debug_logging", False)
    without = p.get("without_boot_markers", False)
    diagnostic_controls(controls != CONTROLS, without_boot_markers=without, initrd_debug_logging=debug)
    allowed = diagnostic_controls(True, without_boot_markers=True, initrd_debug_logging=True) if debug else None
    if controls not in ((allowed,) if debug else (CONTROLS, diagnostic_controls(True))):
        raise ValueError("unexpected volatile diagnostic controls")
    if type(without) is not bool:
        raise ValueError("marker comparison selector must be boolean")
    if without:
        value = p["bootargs"].removeprefix("bootargs=")
        if not p["bootargs"].startswith("bootargs=") or not re.fullmatch(r"[A-Za-z0-9_./:=,+@% \-]+", value):
            raise ValueError("unsafe explicit volatile bootargs")
        params = value.split()
        if any(v.partition("=")[0] in {"k230.boot_trace", "k230.boot_trace_sbi_only"} for v in params):
            raise ValueError("marker enable token remains in explicit comparison")
        if controls != diagnostic_controls(True, without_boot_markers=True, initrd_debug_logging=debug) or params.count("initramfs_async=0") != 1:
            raise ValueError("marker comparison lost the earlier initramfs join control")
        if debug:
            received = [token for token in params if token.partition("=")[0].replace("-", "_").removeprefix("rd.")
                        in {"systemd.log_level", "systemd.log_target"}]
            if received != list(INITRD_DEBUG_LOGGING):
                raise ValueError("initrd logging lost its exact singleton controls")
        command = 'setenv bootargs "' + value + '"'
    else:
        command = 'setenv bootargs "${bootargs} ' + " ".join(controls) + '"'
    if len(command.encode()) >= 512:
        raise ValueError("volatile bootargs command exceeds U-Boot input bound")
    return command


def boot(session, p: dict) -> None:
    bootargs_command = volatile_bootargs_command(p)
    session.line("reboot", interrupt=False)
    end = time.monotonic() + 35
    while time.monotonic() < end:
        session.pump()
        if b"Hit any key to stop autoboot" in session.buffer:
            session.write(b" ")
        if rd.PROMPT in session.buffer:
            break
    else:
        raise Unknown("U-Boot prompt not observed")
    for name, partition, address, source in rd.LOADS:
        expected = p["manifest"]["files"][name]
        load = session.command(f"ext4load mmc {partition} {address} {source}", 90)
        if not rd.verified_load(load, expected):
            raise Unknown("candidate load mismatch; no boot issued")
        crc = session.command(f"crc32 {address} {hex(expected['bytes'])}", 40)
        if not rd.verified_crc(crc, expected):
            raise Unknown("candidate CRC mismatch; no boot issued")
    size = p["manifest"]["files"]["bootargs.txt"]["bytes"]
    for command in (f"env import -t 0x7000000 {hex(size)}", bootargs_command):
        if session.command(command, 15) is None:
            raise Unknown("volatile bootargs setup unverified")
    if not rd.verified_bootargs(session.command("printenv bootargs", 15), p["bootargs"]):
        raise Unknown("printed bootargs mismatch; no boot issued")
    session.line("bootm 0x8000000 0x9000000 0x8400000", interrupt=False)
    if not wait_candidate(session):
        raise Unknown("ordinary init login readiness unverified")


def private_existing(path: Path) -> dict:
    path = path.expanduser().absolute()
    if path.is_symlink() or path.stat().st_mode & 0o077 or path.stat().st_uid != os.getuid():
        raise ValueError("unsafe private state")
    if path.parent.stat().st_mode & 0o077 or Path(__file__).resolve().parents[1] in path.resolve().parents:
        raise ValueError("private state must be protected and outside repository")
    value = json.loads(path.read_text())
    if value.get("schema") != "mainline-system-trial-v1" or value.get("status") != "candidate-ready":
        raise ValueError("state does not allow candidate input")
    return value


def save_state(path: Path, value: dict, *, new=False) -> None:
    if new:
        rd.write_private_result(path, value)
    else:
        # Only this owned private state is replaced; keep its permissions and
        # require the same guarded parent. Never overwrite raw result/log files.
        temp = path.with_name(path.name + "." + uuid.uuid4().hex)
        rd.write_private_result(temp, value)
        os.replace(temp, path)


def run(args) -> bool:
    requested_debug = getattr(args, "initrd_debug_logging", False)
    if type(requested_debug) is not bool or (requested_debug and args.phase != "begin"):
        raise ValueError("--initrd-debug-logging is typed and begin-only; resume uses protected state")
    saved = None if args.phase == "begin" else private_existing(args.state)
    wait_initramfs_in_initcall = (saved.get("wait_initramfs_in_initcall", False) if saved is not None
                                  else getattr(args, "wait_initramfs_in_initcall", False))
    without_boot_markers = (saved.get("without_boot_markers", False) if saved is not None
                            else getattr(args, "without_boot_markers", False))
    initrd_debug_logging = saved.get("initrd_debug_logging", False) if saved is not None else requested_debug
    diagnostic_controls(wait_initramfs_in_initcall, without_boot_markers=without_boot_markers,
                        initrd_debug_logging=initrd_debug_logging)
    if saved:
        for key in ("bundle", "manifest", "normal_report"):
            setattr(args, key, Path(saved[key]))
    if args.phase == "touch" and not args.real_touch:
        raise ValueError("touch requires --real-touch for deliberate glass interaction")
    p = prepare(args.bundle, args.manifest, args.normal_report, wait_initramfs_in_initcall=wait_initramfs_in_initcall,
                without_boot_markers=without_boot_markers,
                **({"initrd_debug_logging": True} if initrd_debug_logging else {}))
    normal = dict(p["normal"] if saved is None else saved["normal"])
    state_path = rd.safe_log_path(args.state) if saved is None else args.state.expanduser().absolute()
    log_path = rd.safe_log_path(args.log); result_path = rd.safe_log_path(args.result)
    if len({state_path, log_path, result_path}) != 3:
        raise ValueError("state, log and result must have distinct private paths")
    import serial
    result = {"schema": "mainline-system-trial-v1", "phase": args.phase, "status": "recovery-required-unknown", "qualified_controls": list(CONTROLS), "production_unmasked": "UNVERIFIED", "candidate_bundle": str(args.bundle), "candidate_system": p["system"], "raw_serial_log_path": str(log_path), "normal_recovery": None}
    result["wait_initramfs_in_initcall"] = wait_initramfs_in_initcall
    result["without_boot_markers"] = without_boot_markers
    result["initrd_debug_logging"] = initrd_debug_logging
    lock_fd = os.open(rd.LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o600)
    session = None
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with os.fdopen(os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb", buffering=0) as log:
            session = rd.PrivateSession(serial, log)
            session.buffer = b""; session.write(b"\r")
            if not wait_prompt(session):
                raise Unknown("fresh root prompt not observed; no command sent")
            if args.phase == "begin":
                before = normal_check(session, p, normal, "preflight")
                result["normal_preflight"] = before
                normal["trial_from_boot_id"] = before["boot_id"]
                token = uuid.uuid4().hex
                root = exchange(session, token, "persistent", report_command(token, "persistent", p["system"]))
                validate_stage("persistent", root, p, normal)
                boot(session, p)
                result["candidate"] = {}
                facts = identity(session, p, normal, root=root, facts=result["candidate"])
                saved = {"schema": "mainline-system-trial-v1", "status": "candidate-ready", "bundle": str(args.bundle), "manifest": str(args.manifest), "normal_report": str(args.normal_report), "normal": normal, "root": root, "candidate_boot_id": facts["identity"]["boot_id"], "candidate": facts}
                saved["wait_initramfs_in_initcall"] = wait_initramfs_in_initcall
                saved["without_boot_markers"] = without_boot_markers
                saved["initrd_debug_logging"] = initrd_debug_logging
                save_state(state_path, saved, new=True)
                result.update(status="candidate-ready-qualified-ordinary-init", candidate=facts)
            else:
                result["candidate"] = {}
                facts = identity(session, p, normal, expected_boot=saved["candidate_boot_id"], root=saved["root"], facts=result["candidate"])
                if args.phase == "touch":
                    result["touch"] = touch(session, p)
                    saved["touch"] = result["touch"]
                    save_state(state_path, saved)
                    result["status"] = "candidate-retained-touch-complete" if result["touch"]["events"]["complete_contact"] else "candidate-retained-touch-not-proved"
                else:
                    token = uuid.uuid4().hex
                    body = f"umask 077; {shlex.quote(p['system'] + '/sw/bin/systemctl')} reboot > /run/k230-mainline-reboot-{token}.log 2>&1; _v=$?; printf 'K230_SYS {token} reboot_rc RC=0 VALUE=%s\\n' \"$_v\""
                    command = envelope(token, "reboot", body)
                    ack = exchange(session, token, "reboot", command)
                    result["reboot"] = ack
                    if ack["reboot_rc"] != "0":
                        raise Unknown("stage2 reboot request failed; no retry")
                    if not wait_normal(session):
                        raise Unknown("normal return not observed within deadline")
                    result["normal_recovery"] = normal_check(session, p, normal, "postflight")
                    if result["normal_recovery"]["boot_id"] == saved["candidate_boot_id"]:
                        raise Unknown("recovery reused candidate boot identity")
                    saved["status"] = "normal-recovery-verified"; save_state(state_path, saved)
                    result["status"] = "normal-recovery-verified"
        rd.write_private_result(result_path, result)
        return args.phase != "touch" or result["touch"]["events"]["complete_contact"]
    except Exception as exc:
        result["failure"] = type(exc).__name__ + ": " + str(exc)
        if session is None:
            result["status"] = "not-started-no-serial-opened"
        else:
            result["last_protocol_stage"] = getattr(session, "system_stage", None)
        if session is not None and saved is not None and saved.get("status") == "candidate-ready":
            saved["status"] = "recovery-required-unknown"; save_state(state_path, saved)
        rd.write_private_result(result_path, result)
        print("Trial stopped; received facts preserved privately. No further board input or recovery retry sent.", file=sys.stderr)
        return False
    finally:
        if session is not None:
            session.close()
        os.close(lock_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("begin", "touch", "finish"))
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--normal-report", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--real-touch", action="store_true")
    parser.add_argument("--wait-initramfs-in-initcall", action="store_true",
                        help="begin-only SBI-only comparison: add volatile initramfs_async=0; keep the same async worker")
    parser.add_argument("--without-boot-markers", action="store_true",
                        help="begin-only comparison with the earlier join: remove both marker-enable tokens from volatile arguments")
    parser.add_argument("--initrd-debug-logging", action="store_true",
                        help="begin-only marker-free/initramfs comparison: two fixed initrd manager logging settings")
    args = parser.parse_args()
    if args.phase == "begin" and any(getattr(args, k) is None for k in ("bundle", "manifest", "normal_report")):
        parser.error("begin requires --bundle, --manifest and --normal-report")
    if args.phase != "begin" and any(getattr(args, k) is not None for k in ("bundle", "manifest", "normal_report")):
        parser.error("resumed phases select artifacts only from protected state")
    if args.real_touch and args.phase != "touch":
        parser.error("--real-touch is touch-only")
    if args.wait_initramfs_in_initcall and args.phase != "begin":
        parser.error("--wait-initramfs-in-initcall is begin-only; resumed phases use protected state")
    if args.without_boot_markers and (args.phase != "begin" or not args.wait_initramfs_in_initcall):
        parser.error("--without-boot-markers is begin-only and requires --wait-initramfs-in-initcall")
    if args.initrd_debug_logging and (args.phase != "begin" or not args.wait_initramfs_in_initcall or not args.without_boot_markers):
        parser.error("--initrd-debug-logging is begin-only and requires both earlier comparison selectors")
    try:
        return 0 if run(args) else 1
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

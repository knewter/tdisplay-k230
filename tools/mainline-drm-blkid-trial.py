#!/usr/bin/env python3
"""Operator-only single initrd metadata probe; unknown completion stops input."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import uuid

_spec = importlib.util.spec_from_file_location("mainline_system", Path(__file__).with_name("mainline-drm-system-trial.py"))
system = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(system)
rd = system.rd
STAGES = ("sys-mkdir", "sys-mount", "dev-mkdir", "dev-mount", "mounts", "ancestry", "output", "blkid")


class Stopped(RuntimeError):
    pass


def prepare(bundle, manifest, normal_report):
    prepared = rd.prepare_trial(manifest, bundle, normal_report)
    prepared["helper_text"] = "from pathlib import Path\nassert not Path('/nix-path-registration').exists() and not Path('/nix-path-registration').is_symlink(), 'registration marker present'\n" + prepared["helper_text"]
    return prepared


def finite_timeout(value):
    if not math.isfinite(value) or not 0 < value <= 30:
        raise ValueError("stage timeout must be positive, finite and at most 30s")


def stage_command(token: str, stage: str, directory_token: str | None = None) -> str:
    rd._validate_token(token)
    if stage not in STAGES:
        raise ValueError("unknown blkid stage")
    directory_token = directory_token or token
    rd._validate_token(directory_token)
    directory = f"/k230-blkid-{directory_token}"
    output = directory + "/output"
    match = "if test $_rc -eq 0; then _match=1; fi; "
    if stage in ("sys-mkdir", "sys-mount"):
        # Reuse the proven sysfs-only setup, never the trace parameter stages.
        command = rd.runtime_trace_command(token, stage)
        return command.replace("K230_RDINIT_TRACE_", "K230_BLKID_")
    if stage in ("dev-mkdir", "dev-mount"):
        command = rd.label_setup_command(token, stage)
        return command.replace("K230_RDINIT_LABEL_SETUP_", "K230_BLKID_").replace(" RC=%s\\n", " RC=%s MATCH=%s\\n").replace('"$_k230_rc"', '"$_k230_rc" "$(test $_k230_rc -eq 0 && printf 1 || printf 0)"')
    if stage == "mounts":
        body = "_p=0; _s=0; _d=0; _bad=0; while read _src _mnt _fs _rest; do case $_mnt in /proc) _p=$((_p+1)); test \"$_fs\" = proc || _bad=1;; /sys) _s=$((_s+1)); test \"$_fs\" = sysfs || _bad=1;; /dev) _d=$((_d+1)); test \"$_fs\" = devtmpfs || _bad=1;; esac; done < /proc/mounts; _rc=$?; if test $_rc -eq 0 && test $_p -eq 1 && test $_s -eq 1 && test $_d -eq 1 && test $_bad -eq 0; then _match=1; fi; "
    elif stage == "ancestry":
        body = (
            "_a=$(/bin/readlink -f /sys/class/block/mmcblk1p2); _rc=$?; "
            "_h=$(/bin/readlink -f /sys/class/mmc_host/mmc1); _hrc=$?; "
            "_p=''; IFS= read -r _p < /sys/class/block/mmcblk1p2/partition; _prc=$?; "
            "_dev=''; IFS= read -r _dev < /sys/class/block/mmcblk1p2/dev; _drc=$?; "
            "_hex=$(/bin/stat -c '%t:%T' /dev/mmcblk1p2); _nrc=$?; "
            "_major=${_dev%:*}; _minor=${_dev#*:}; _ma=${_hex%:*}; _mi=${_hex#*:}; "
            "_ids=1; for _v in \"$_major\" \"$_minor\"; do case $_v in ''|*[!0-9]*) _ids=0;; esac; done; "
            "for _v in \"$_ma\" \"$_mi\"; do case $_v in ''|*[!0-9a-fA-F]*) _ids=0;; esac; done; "
            "case $_h in /sys/devices/*/91581000.sdhci1/mmc_host/mmc1) "
            "case $_a in \"$_h\"/mmc1:[0-9a-f][0-9a-f][0-9a-f][0-9a-f]/block/mmcblk1/mmcblk1p2) "
            "if test $_rc -eq 0 && test $_hrc -eq 0 && test $_prc -eq 0 && test $_drc -eq 0 && test $_nrc -eq 0 "
            "&& test $_ids -eq 1 && test \"$_p\" = 2 && test -b /dev/mmcblk1p2 "
            "&& test \"$_major\" -eq \"$((16#$_ma))\" && test \"$_minor\" -eq \"$((16#$_mi))\"; then _match=1; fi;; esac;; esac; "
        )
    elif stage == "output":
        body = (
            f"umask 077; test ! -e {directory} && test ! -L {directory} "
            f"&& /bin/mkdir -m 700 {directory} && test -d {directory} && test ! -L {directory} "
            "&& test -x /bin/udevadm && test -x /bin/timeout; _rc=$?; " + match
        )
    else:
        body = (
            f"umask 077; /bin/timeout --signal=TERM --kill-after=2s 20s /bin/udevadm test-builtin blkid "
            f"/sys/class/block/mmcblk1p2 > {output} 2>&1; _rc=$?; "
            "_types=0; _labels=0; _goodtype=0; _goodlabel=0; "
            "while IFS= read -r _line; do case $_line in ID_FS_TYPE=*) _types=$((_types+1)); "
            "test \"$_line\" = ID_FS_TYPE=ext4 && _goodtype=1;; ID_FS_LABEL=*) _labels=$((_labels+1)); "
            "test \"$_line\" = ID_FS_LABEL=NIXOS_SD && _goodlabel=1;; esac; done "
            f"< {output}; _readrc=$?; "
            "if test $_rc -eq 0 && test $_readrc -eq 0 && test $_types -eq 1 && test $_labels -eq 1 "
            "&& test $_goodtype -eq 1 && test $_goodlabel -eq 1; then _match=1; fi; "
        )
    return (f"printf 'K230_BLKID_BEGIN {token} STAGE={stage}\\n'; _rc=255; _match=0; " + body +
            f"printf 'K230_BLKID_END {token} STAGE={stage} RC=%s MATCH=%s\\n' \"$_rc\" \"$_match\"")


def stage_result(output: bytes, token: str, stage: str):
    rd._validate_token(token)
    if stage not in STAGES:
        raise ValueError("unknown blkid stage")
    text = rd._PROTOCOL.uart_text(output)
    prefix = token.encode() + b" STAGE=" + stage.encode()
    begins = list(re.finditer(rb"^K230_BLKID_BEGIN " + prefix + rb"\n", text, re.M))
    ends = list(re.finditer(rb"^K230_BLKID_END " + prefix + rb" RC=([0-9]{1,3}) MATCH=([01])\n", text, re.M))
    if len(begins) != 1 or len(ends) != 1 or begins[0].end() > ends[0].start():
        return None
    rc = int(ends[0].group(1)); match = ends[0].group(2) == b"1"
    if rc > 255 or (rc != 0 and match):
        return None
    return {"rc": rc, "match": match}


def retrieval_command(token: str, directory_token: str) -> str:
    rd._validate_token(token); rd._validate_token(directory_token)
    path = f"/k230-blkid-{directory_token}/output"
    return (
        f"_size=$(/bin/stat -c %s {path}); _src=$?; _rc=255; "
        "case $_size in ''|*[!0-9]*) _src=1;; esac; "
        "if test $_src -eq 0 && test \"$_size\" -gt 0 && test \"$_size\" -le 16384; then "
        f"printf 'K230_BLKID_RAW_BEGIN {token} SIZE=%s\\n' \"$_size\"; "
        f"/bin/cat {path}; _rc=$?; "
        f"printf 'K230_BLKID_RAW_END {token} RC=%s\\n' \"$_rc\"; "
        f"else printf 'K230_BLKID_RAW_FAILED {token}\\n'; fi"
    )


def retrieval_result(output: bytes, token: str):
    rd._validate_token(token)
    text = rd._PROTOCOL.uart_text(output)
    begins = list(re.finditer(rb"^K230_BLKID_RAW_BEGIN " + token.encode() + rb" SIZE=([0-9]{1,5})\n", text, re.M))
    ends = list(re.finditer(rb"^K230_BLKID_RAW_END " + token.encode() + rb" RC=0\n", text, re.M))
    if len(begins) != 1 or len(ends) != 1 or begins[0].end() > ends[0].start():
        return None
    raw = text[begins[0].end():ends[0].start()]
    if not 0 < len(raw) <= 16384 or len(raw) != int(begins[0].group(1)):
        return None
    # The command's fresh shell prompt must follow its complete receipt.
    if re.fullmatch(rb"sh-[0-9]+\.[0-9]+# ", text[ends[0].end():]) is None:
        return None
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "rc": 0}


def diagnostic(session, facts: dict, *, timeout=30.0, clock=time.monotonic, token_factory=lambda: uuid.uuid4().hex):
    """No diagnostic or reboot command follows a failed or unknown stage."""
    finite_timeout(timeout)
    token = token_factory()
    received = rd.await_reception(session, token, attempts=1, timeout=min(timeout, rd.RECEPTION_ATTEMPT_TIMEOUT), clock=clock)
    if received is None:
        raise Stopped("reception unknown")
    facts["reception"] = True
    for name, command, parser in (
        ("true", rd.true_command(token), lambda b, t: rd.protocol_rc_marker(b, t, "true")),
        ("proc", rd.proc_mount_command(token), rd.proc_mount_result),
        ("uptime", rd.uptime_command(token), rd.uptime_result),
    ):
        session.buffer = b""
        session.write((command + "\r").encode())
        outcome = rd.await_protocol_marker(session, parser, token, timeout, clock)
        if outcome is None:
            raise Stopped(name + " completion unknown")
        facts[name] = outcome
        ok = outcome == 0 if name == "true" else (outcome["rc"] == 0 if name == "uptime" else outcome["mkdir_rc"] == 0 and outcome["mount_attempted"] and outcome["mount_rc"] == 0)
        if not ok:
            raise Stopped(name + " prerequisite failed")
    seen = {token}
    for name in STAGES:
        fresh = token_factory(); rd._validate_token(fresh)
        if fresh in seen:
            raise ValueError("stage token must be fresh")
        seen.add(fresh)
        session.buffer = b""
        session.write((stage_command(fresh, name, token) + "\r").encode())
        outcome = rd.await_protocol_marker(session, lambda b, t: stage_result(b, t, name), fresh, timeout, clock)
        if outcome is None:
            raise Stopped(name + " completion unknown")
        facts[name] = outcome
        if outcome["rc"] != 0 or not outcome["match"]:
            raise Stopped(name + " gate failed")
    fresh = token_factory(); rd._validate_token(fresh)
    if fresh in seen:
        raise ValueError("retrieval token must be fresh")
    facts["retrieval"] = {"attempted": True, "complete": False}
    session.buffer = b""
    session.write((retrieval_command(fresh, token) + "\r").encode())
    captured = rd.await_protocol_marker(session, retrieval_result, fresh, timeout, clock)
    if captured is None:
        raise Stopped("private raw retrieval incomplete; no reboot")
    facts["retrieval"] = {"attempted": True, "complete": True, **captured}
    facts["passed"] = True


def boot(session, prepared):
    session.buffer = b""; session.line("reboot", interrupt=False)
    end = time.monotonic() + 35
    while time.monotonic() < end:
        session.pump()
        if b"Hit any key to stop autoboot" in session.buffer:
            session.write(b" ")
        if rd.PROMPT in session.buffer:
            break
    else:
        raise Stopped("U-Boot prompt unknown")
    for name, partition, address, source in rd.LOADS:
        expected = prepared["manifest"]["files"][name]
        if not rd.verified_load(session.command(f"ext4load mmc {partition} {address} {source}", 90), expected):
            raise Stopped("strict load failed; no candidate boot")
        if not rd.verified_crc(session.command(f"crc32 {address} {hex(expected['bytes'])}", 40), expected):
            raise Stopped("CRC failed; no candidate boot")
    size = prepared["manifest"]["files"]["bootargs.txt"]["bytes"]
    for command in (f"env import -t 0x7000000 {hex(size)}", rd.volatile_bootargs_command()):
        if session.command(command, 15) is None:
            raise Stopped("volatile bootargs unknown")
    if not rd.verified_bootargs(session.command("printenv bootargs", 15), prepared["bootargs"]):
        raise Stopped("printed exact rdinit bootargs mismatch; no candidate boot")
    session.buffer = b""
    session.line("bootm 0x8000000 0x9000000 0x8400000", interrupt=False)
    if not rd.await_initrd_ready(session):
        raise Stopped("fresh candidate init entry/shell readiness unknown")


def run(args):
    prepared = prepare(args.bundle, args.manifest, args.normal_report)
    normal = dict(prepared["normal"])
    log_path = rd.safe_log_path(args.log); result_path = rd.safe_log_path(args.result)
    if log_path == result_path:
        raise ValueError("log and result must be distinct private paths")
    result = {"schema": "mainline-initrd-blkid-v1", "status": "recovery-required-unknown", "candidate_bundle": str(prepared["bundle"]), "candidate_system": prepared["system"], "diagnostic": {}, "normal_recovery": None, "reboot_marker_observed": False, "persistent_boot_selection_changed": False, "raw_serial_log_path": str(log_path)}
    import serial
    lock_fd = os.open(rd.LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o600)
    session = None
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with os.fdopen(os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb", buffering=0) as log:
            session = rd.PrivateSession(serial, log)
            session.buffer = b""; session.write(b"\r")
            if not system.wait_prompt(session):
                raise Stopped("fresh normal prompt unknown; no command sent")
            before = system.normal_check(session, prepared, normal, "preflight")
            result["normal_preflight"] = before
            normal["trial_from_boot_id"] = before["boot_id"]
            boot(session, prepared)
            result["initrd_readiness_observed"] = True
            diagnostic(session, result["diagnostic"])
            token = uuid.uuid4().hex
            session.buffer = b""
            session.write((rd.reboot_command(token) + "\r").encode())
            ack = rd.await_protocol_marker(session, rd.reboot_marker, token, 5.0)
            result["reboot_marker_observed"] = ack is True
            if ack is not True:
                raise Stopped("reboot receipt unknown; no retry")
            if not system.wait_normal(session):
                raise Stopped("normal return unknown after 180s; no retry")
            result["normal_recovery"] = system.normal_check(session, prepared, normal, "postflight")
            result["status"] = "recovery-verified-diagnostic-passed"
        rd.write_private_result(result_path, result)
        return True
    except Exception as exc:
        result["failure"] = type(exc).__name__ + ": " + str(exc)
        if session is None:
            result["status"] = "not-started-no-serial-opened"
        rd.write_private_result(result_path, result)
        print("Trial stopped; facts preserved privately. No further input or recovery retry sent.", file=sys.stderr)
        return False
    finally:
        if session is not None:
            session.close()
        os.close(lock_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--normal-report", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run(args) else 2


if __name__ == "__main__":
    raise SystemExit(main())

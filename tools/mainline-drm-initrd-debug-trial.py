#!/usr/bin/env python3
"""Operator-only bounded ordinary-initrd coldplug diagnostic; unknown stops input."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
import uuid

_spec = importlib.util.spec_from_file_location("mainline_system", Path(__file__).with_name("mainline-drm-system-trial.py"))
system = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(system)
rd = system.rd
CONTROLS = system.CONTROLS + ("rd.systemd.unit=basic.target", "rd.systemd.debug_shell=ttyS0")
ROOT_UNITS = ("sysroot.mount", "initrd-find-nixos-closure.service", "initrd-nixos-activation.service", "initrd-switch-root.target", "initrd-switch-root.service")
UDEV_UNITS = ("systemd-udev-trigger.service", "systemd-udevd.service")
RAW_LIMIT = 65536


class Stopped(RuntimeError):
    pass


def bootargs(original, selected):
    # Reject every preexisting systemd/udev option, including supported but
    # conflicting debug/default-tty/logging options the ordinary helper excludes.
    for p in original.removeprefix("bootargs=").split():
        if p.partition("=")[0].startswith(("rd.", "systemd.", "udev.")):
            raise ValueError("conflicting initrd diagnostic argument")
    return system.ordinary_bootargs(original, selected) + " " + " ".join(CONTROLS[-2:])


def private_input(path):
    path = path.expanduser().absolute()
    if path.is_symlink() or path.stat().st_mode & 0o077 or path.stat().st_uid != os.getuid():
        raise ValueError("unsafe private prerequisite")
    if path.parent.stat().st_mode & 0o077 or Path(__file__).resolve().parents[1] in path.resolve().parents:
        raise ValueError("prerequisite must be protected and outside repository")
    return json.loads(path.read_text())


def validate_prerequisite(value, prepared):
    normal = prepared["normal"]
    expected = {k: normal[k] for k in ("system", "profile", "kernel", "uname", "init")}
    expected.update(services=["active"] * 3, boot_files={k: v["sha256"] for k, v in normal["boot_files"].items()})
    recovered = value.get("normal_recovery") or {}
    before = value.get("normal_preflight") or {}
    if (value.get("schema") != "mainline-initrd-blkid-v1"
            or value.get("status") != "recovery-verified-diagnostic-passed"
            or value.get("candidate_bundle") != str(prepared["bundle"])
            or value.get("candidate_system") != prepared["system"]
            or value.get("diagnostic", {}).get("passed") is not True
            or value.get("diagnostic", {}).get("retrieval", {}).get("complete") is not True
            or value.get("reboot_marker_observed") is not True
            or any(recovered.get(k) != v for k, v in expected.items())
            or not valid_boot_id(recovered.get("boot_id", ""))
            or not valid_boot_id(before.get("boot_id", ""))
            or recovered["boot_id"] == before["boot_id"]):
        raise ValueError("matching successful blkid/protected-return prerequisite required")


def prepare(bundle, manifest, normal_report, blkid_result):
    p = rd.prepare_trial(manifest, bundle, normal_report)
    p["bootargs"] = bootargs((p["bundle"] / "bootargs.txt").read_text(), p["system"])
    p["pid1"] = str((Path(p["system"]) / "init").resolve(strict=True))
    p["helper_text"] = "from pathlib import Path\nassert not Path('/nix-path-registration').exists() and not Path('/nix-path-registration').is_symlink(), 'registration marker present'\n" + p["helper_text"]
    validate_prerequisite(private_input(blkid_result), p)
    return p


def valid_boot_id(value):
    return re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value) is not None


def prompt(text):
    # Only bash's bracketed-paste controls; no arbitrary kernel-line stripping.
    text = text.replace(b"\x1b[?2004h", b"").replace(b"\x1b[?2004l", b"")
    return re.fullmatch(rb"sh-[0-9]+\.[0-9]+# ", text) is not None


def wait_ready(session, timeout=90, clock=time.monotonic):
    system.finite_timeout(timeout, 90)
    end = clock() + timeout
    while clock() < end:
        session.pump()
        text = rd._PROTOCOL.uart_text(session.buffer)
        banner = re.search(rb"(?:^|\n)(?:\[\s*[0-9]+\.[0-9]+\] )?Linux version 7\.3\.0-rc5(?: |\n)", text)
        if banner:
            after_banner = text[banner.end():]
            manager = re.search(rb"systemd 261\.2(?= |\n)", after_banner)
            if manager:
                # The interactive prompt has no newline. Asynchronous boot
                # status can start immediately after its trailing space, so
                # readiness records the observed fresh line boundary rather
                # than requiring that prompt to remain the buffer tail.
                after_manager = after_banner[manager.end():]
                if re.search(rb"(?:^|\n)(?:\x1b\[\?2004h)?sh-[0-9]+\.[0-9]+# ", after_manager):
                    return True
    return False


def envelope(token, stage, body):
    rd._validate_token(token)
    if not re.fullmatch(r"[a-z-]+", stage):
        raise ValueError("invalid stage")
    command = (f"printf 'K230_IDBG_BEGIN {token} {stage}\\n'; " + body +
               f"; _k230_rc=$?; printf '\\nK230_IDBG_END {token} {stage} RC=%s\\n' \"$_k230_rc\"")
    if len(command.encode()) >= 3500:
        raise ValueError("serial command exceeds bound")
    return command


def frame(output, token, stage):
    rd._validate_token(token)
    text = rd._PROTOCOL.uart_text(output)
    start = f"K230_IDBG_BEGIN {token} {stage}\n".encode()
    end = f"K230_IDBG_END {token} {stage} RC=".encode()
    starts = list(re.finditer(rb"^" + re.escape(start), text, re.M))
    ends = list(re.finditer(rb"^" + re.escape(end) + rb"([0-9]{1,3})\n", text, re.M))
    if len(starts) != 1 or len(ends) != 1 or starts[0].end() > ends[0].start():
        return None
    body = text[starts[0].end():ends[0].start()]
    if not body.endswith(b"\n") or not prompt(text[ends[0].end():]) or int(ends[0].group(1)) > 255:
        return None
    return {"rc": int(ends[0].group(1)), "body": body[:-1]}


def exchange(session, token, stage, body, *, timeout=10, clock=time.monotonic, deadline=None):
    if deadline is not None:
        timeout = min(timeout, deadline - clock())
        if timeout <= 0:
            raise Stopped("overall observation deadline expired; no further input")
    system.finite_timeout(timeout, 15)
    command = envelope(token, stage, body)
    session.buffer = b""
    session.write(command.encode() + b"\r")
    end = clock() + timeout
    if deadline is not None:
        end = min(end, deadline)
    received = b""
    ready_at = None
    while clock() < end:
        chunk = session.pump()
        received += chunk
        if len(received) > 262144:
            raise Stopped(stage + " output exceeded bound")
        answer = frame(received, token, stage)
        if answer is not None:
            now = clock()
            if ready_at is None or chunk:
                ready_at = now
            elif now - ready_at >= .2:
                return answer
        else:
            ready_at = None
    raise Stopped(stage + " completion unknown; no further input")


def properties(body, expected_keys):
    rows = body.decode("utf-8", "strict").splitlines()
    pairs = [row.split("=", 1) for row in rows]
    if (any(len(pair) != 2 for pair in pairs) or len(pairs) != len(expected_keys)
            or {p[0] for p in pairs} != set(expected_keys)):
        raise Stopped("malformed or duplicate properties")
    return dict(pairs)


def unit_properties(body, names, fields):
    blocks = body.decode("utf-8", "strict").strip("\n").split("\n\n")
    parsed = [properties(block.encode(), fields) for block in blocks]
    if len(parsed) != len(names) or {p["Id"] for p in parsed} != set(names):
        raise Stopped("unexpected or duplicate units")
    return {p["Id"]: p for p in parsed}


def identity_command():
    return ("printf 'shell_pid=%s\\nshell_ppid=%s\\n' \"$$\" \"$PPID\"; "
            "printf 'uid='; /bin/id -u; printf 'uname='; /bin/uname -r; "
            "printf 'boot_id='; /bin/cat /proc/sys/kernel/random/boot_id; "
            "printf 'pid1='; /bin/readlink -f /proc/1/exe; "
            "printf 'tty='; /bin/readlink /proc/$$/fd/0; "
            "printf 'cmdline='; /bin/cat /proc/cmdline; "
            "if test -f /etc/initrd-release && test -x /bin/timeout && test -x /bin/systemctl "
            "&& test -x /bin/journalctl && test -x /bin/udevadm && test -x /bin/sha256sum "
            "&& test -x /bin/stat; then printf 'initrd=1\\n'; else printf 'initrd=0\\n'; fi")


def mounts_command():
    # Explicit case terminators avoid a false final while-body status when the
    # last table entry does not match a requested mount.
    return ("_p=0; _s=0; _d=0; _c=0; _r=0; _bad=0; "
            "while read -r _src _mnt _fs _rest; do case $_mnt in "
            "/proc) _p=$((_p+1)); test \"$_fs\" = proc || _bad=1;; "
            "/sys) _s=$((_s+1)); test \"$_fs\" = sysfs || _bad=1;; "
            "/dev) _d=$((_d+1)); test \"$_fs\" = devtmpfs || _bad=1;; "
            "/sys/fs/cgroup) _c=$((_c+1)); test \"$_fs\" = cgroup2 || _bad=1;; "
            "/) _r=$((_r+1)); case $_fs in rootfs|tmpfs|ramfs) :;; *) _bad=1;; esac;; "
            "/sysroot|/sysroot/*) _bad=1;; esac; :; done < /proc/mounts; _readrc=$?; "
            "if test $_readrc -eq 0 && test $_p -eq 1 && test $_s -eq 1 && test $_d -eq 1 "
            "&& test $_c -eq 1 && test $_r -eq 1 && test $_bad -eq 0; then printf 'mounts=1\\n'; "
            "else printf 'mounts=0\\n'; fi")


def guard(session, prepared, normal, fresh, *, expected_boot=None, clock=time.monotonic, deadline=None):
    result = exchange(session, fresh(), "identity", identity_command(), clock=clock, deadline=deadline)
    if result["rc"]:
        raise Stopped("identity failed")
    v = properties(result["body"], ("shell_pid", "shell_ppid", "uid", "uname", "boot_id", "pid1", "tty", "cmdline", "initrd"))
    if (v["uid"] != "0" or v["uname"] != "7.3.0-rc5" or v["pid1"] != prepared["pid1"] or v["initrd"] != "1"
            or v["tty"] != "/dev/ttyS0" or v["shell_ppid"] != "1" or not re.fullmatch(r"[1-9][0-9]*", v["shell_pid"])
            or v["shell_pid"] == "1" or not valid_boot_id(v["boot_id"])
            or v["boot_id"] == normal["trial_from_boot_id"]
            or (expected_boot is not None and v["boot_id"] != expected_boot)
            or v["cmdline"].split() != prepared["bootargs"].removeprefix("bootargs=").split()):
        raise Stopped("candidate/initrd/shell identity mismatch")
    for stage, body in (
        ("mounts", mounts_command()),
        ("ownership", "/bin/timeout --signal=TERM --kill-after=2s 5s /bin/systemctl --no-pager show debug-shell.service --property=Id,ExecMainPID,ActiveState,SubState,TTYPath,Job"),
        ("boundary", "/bin/timeout --signal=TERM --kill-after=2s 5s /bin/systemctl --no-pager show " + " ".join(ROOT_UNITS) + " --property=Id,ActiveState,SubState,Job"),
    ):
        got = exchange(session, fresh(), stage, body, clock=clock, deadline=deadline)
        if got["rc"]:
            raise Stopped(stage + " guard failed")
        if stage == "mounts":
            if properties(got["body"], ("mounts",)) != {"mounts": "1"}:
                raise Stopped("mount/root boundary failed")
        elif stage == "ownership":
            unit = unit_properties(got["body"], ("debug-shell.service",), ("Id", "ExecMainPID", "ActiveState", "SubState", "TTYPath", "Job"))["debug-shell.service"]
            if any(unit[k] != x for k, x in {"ExecMainPID": v["shell_pid"], "ActiveState": "active", "SubState": "running", "TTYPath": "/dev/ttyS0", "Job": ""}.items()):
                raise Stopped("debug shell terminal/PID ownership mismatch")
        else:
            units = unit_properties(got["body"], ROOT_UNITS, ("Id", "ActiveState", "SubState", "Job"))
            if any(p["ActiveState"] != "inactive" or p["SubState"] not in ("dead", "inactive") or p["Job"] for p in units.values()):
                raise Stopped("root activation/switch-root is active or pending")
    return {"boot_id": v["boot_id"], "shell_pid": v["shell_pid"], "guards_passed": True}


def retrieval_command(path):
    path = shlex.quote(path)
    return (f"_n=$(/bin/stat -c %s {path}); _s=$?; _h=$(/bin/sha256sum {path}); _hrc=$?; _h=${{_h%% *}}; "
            "case $_n in ''|*[!0-9]*) _s=1;; esac; "
            f"if test $_s -eq 0 && test $_hrc -eq 0 && test \"$_n\" -le {RAW_LIMIT}; then "
            "printf 'SIZE=%s SHA256=%s\\n' \"$_n\" \"$_h\"; "
            f"/bin/cat {path}; else false; fi")


def captured(body):
    head, sep, raw = body.partition(b"\n")
    match = re.fullmatch(rb"SIZE=([0-9]{1,5}) SHA256=([0-9a-f]{64})", head)
    if (not sep or match is None or len(raw) > RAW_LIMIT or len(raw) != int(match.group(1))
            or hashlib.sha256(raw).hexdigest().encode() != match.group(2)):
        raise Stopped("raw retrieval incomplete or modified; no reboot")
    return raw


def worker_command(groups):
    expected = {"/system.slice/" + n for n in UDEV_UNITS}
    if not set(groups) <= expected or len(set(groups)) != len(groups):
        raise ValueError("unexpected worker cgroup")
    paths = " ".join(shlex.quote("/sys/fs/cgroup" + g + "/cgroup.procs") for g in groups)
    script = ("_n=0; for _cg in " + paths + "; do while IFS= read -r _pid; do "
              "case $_pid in ''|*[!0-9]*) exit 1;; esac; _n=$((_n+1)); test $_n -le 16 || exit 1; "
              "test -d /proc/$_pid || continue; _member=0; while IFS= read -r _v; do "
              "if test \"$_v\" = \"$_pid\"; then _member=1; fi; done < \"$_cg\" || exit 1; "
              "test $_member -eq 1 || continue; _comm=; _state=; _w=; "
              "IFS= read -r _comm < /proc/$_pid/comm || continue; "
              "while IFS= read -r _line; do case $_line in State:*) _state=${_line#State:};; esac; :; "
              "done < /proc/$_pid/status || continue; "
              "IFS= read -r _w < /proc/$_pid/wchan || test -n \"$_w\" || _w=unavailable; "
              "printf 'PID=%s COMM=%s STATE=%s WCHAN=%s\\n' \"$_pid\" \"$_comm\" \"$_state\" \"$_w\"; "
              "done < \"$_cg\" || exit 1; done")
    return "/bin/timeout --signal=TERM --kill-after=2s 5s /bin/sh -c " + shlex.quote(script)


def diagnostic(session, prepared, normal, facts, *, clock=time.monotonic, token_factory=lambda: uuid.uuid4().hex):
    seen = set()
    deadline = clock() + 90
    def fresh():
        token = token_factory(); rd._validate_token(token)
        if token in seen:
            raise ValueError("protocol token must be fresh")
        seen.add(token)
        return token
    first = fresh()
    received = exchange(session, first, "receipt", "printf 'receipt=1\\n'", clock=clock, deadline=deadline)
    if received != {"rc": 0, "body": b"receipt=1\n"}:
        raise Stopped("fresh shell reception unverified")
    facts["initial_guard"] = guard(session, prepared, normal, fresh, clock=clock, deadline=deadline)
    directory = "/k230-initrd-debug-" + first
    create = (f"umask 077; test ! -e {directory} && test ! -L {directory} "
              f"&& /bin/mkdir -m 700 {directory} && test -d {directory} && test ! -L {directory}")
    if exchange(session, fresh(), "output", create, clock=clock, deadline=deadline)["rc"]:
        raise Stopped("private volatile output setup failed")
    facts["snapshots"] = {}
    commands = {
        "jobs": "/bin/timeout --signal=TERM --kill-after=2s 5s /bin/systemctl --no-pager --plain --no-legend list-jobs",
        "units": "/bin/timeout --signal=TERM --kill-after=2s 5s /bin/systemctl --no-pager show " + " ".join(UDEV_UNITS) + " --property=Id,ActiveState,SubState,Result,ExecMainPID,ControlPID,ExecMainStatus,ControlGroup",
        "ping": "/bin/timeout --signal=TERM --kill-after=2s 5s /bin/udevadm control --ping --timeout=3",
        "journal": "/bin/timeout --signal=TERM --kill-after=2s 5s /bin/journalctl --no-pager --boot --lines=80 --output=short-monotonic --unit=systemd-udev-trigger.service --unit=systemd-udevd.service",
    }
    for stage in ("jobs", "units", "ping", "journal", "workers"):
        if clock() >= deadline:
            raise Stopped("overall observation deadline expired")
        if stage == "workers":
            commands[stage] = worker_command(groups)
        path = directory + "/" + stage
        result = exchange(session, fresh(), stage, "umask 077; " + commands[stage] + " > " + path + " 2>&1", clock=clock, deadline=deadline)
        facts["snapshots"][stage] = {"rc": result["rc"], "retrieved": False}
        if result["body"] != b"":
            raise Stopped("unexpected snapshot protocol output")
        # A known returned failure still gets its private output preserved, then
        # stops. Unknown command completion never enters retrieval.
        got = exchange(session, fresh(), "raw-" + stage, retrieval_command(path), timeout=15, clock=clock, deadline=deadline)
        if got["rc"]:
            raise Stopped("raw retrieval failed")
        raw = captured(got["body"])
        facts["snapshots"][stage].update(retrieved=True, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if result["rc"]:
            raise Stopped(stage + " returned nonzero; output preserved; no further input")
        if stage == "units":
            units = unit_properties(raw, UDEV_UNITS, ("Id", "ActiveState", "SubState", "Result", "ExecMainPID", "ControlPID", "ExecMainStatus", "ControlGroup"))
            groups = [u["ControlGroup"] for u in units.values() if u["ControlGroup"]]
            worker_command(groups)  # validate before any subsequent observation
    if clock() >= deadline:
        raise Stopped("overall observation deadline expired")
    facts["renewed_guard"] = guard(session, prepared, normal, fresh, expected_boot=facts["initial_guard"]["boot_id"], clock=clock, deadline=deadline)
    if facts["renewed_guard"]["shell_pid"] != facts["initial_guard"]["shell_pid"]:
        raise Stopped("debug shell changed; no reboot")
    facts["complete"] = True


def boot(session, p, clock=time.monotonic):
    session.buffer = b""; session.line("reboot", interrupt=False)
    end = clock() + 35
    while clock() < end:
        session.pump()
        if b"Hit any key to stop autoboot" in session.buffer:
            session.write(b" ")
        if rd.PROMPT in session.buffer:
            break
    else:
        raise Stopped("U-Boot prompt unknown")
    for name, partition, address, source in rd.LOADS:
        expected = p["manifest"]["files"][name]
        if not rd.verified_load(session.command(f"ext4load mmc {partition} {address} {source}", 90), expected):
            raise Stopped("load mismatch; no candidate boot")
        if not rd.verified_crc(session.command(f"crc32 {address} {hex(expected['bytes'])}", 40), expected):
            raise Stopped("CRC mismatch; no candidate boot")
    size = p["manifest"]["files"]["bootargs.txt"]["bytes"]
    for command in (f"env import -t 0x7000000 {hex(size)}", 'setenv bootargs "${bootargs} ' + " ".join(CONTROLS) + '"'):
        if session.command(command, 15) is None:
            raise Stopped("volatile arguments unverified")
    if not rd.verified_bootargs(session.command("printenv bootargs", 15), p["bootargs"]):
        raise Stopped("printed exact bootargs mismatch; no boot")
    session.buffer = b""; session.line("bootm 0x8000000 0x9000000 0x8400000", interrupt=False)
    if not wait_ready(session):
        raise Stopped("fresh initrd debug shell readiness unknown")


def run(args):
    p = prepare(args.bundle, args.manifest, args.normal_report, args.blkid_result)
    normal = dict(p["normal"])
    log_path = rd.safe_log_path(args.log); result_path = rd.safe_log_path(args.result)
    if log_path == result_path:
        raise ValueError("distinct private log/result paths required")
    result = {"schema": "mainline-initrd-debug-v1", "status": "recovery-required-unknown", "candidate_bundle": str(p["bundle"]), "candidate_system": p["system"], "diagnostic": {}, "normal_recovery": None, "reboot_marker_observed": False, "persistent_boot_selection_changed": False, "raw_serial_log_path": str(log_path)}
    import serial
    lock_fd = os.open(rd.LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o600)
    session = None
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with os.fdopen(os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb", buffering=0) as log:
            session = rd.PrivateSession(serial, log)
            session.buffer = b""; session.write(b"\r")
            if not system.wait_prompt(session):
                raise Stopped("fresh protected normal prompt unknown")
            before = system.normal_check(session, p, normal, "preflight")
            result["normal_preflight"] = before
            normal["trial_from_boot_id"] = before["boot_id"]
            boot(session, p)
            result["initrd_readiness_observed"] = True
            diagnostic(session, p, normal, result["diagnostic"])
            session.buffer = b""; token = uuid.uuid4().hex
            session.write((rd.reboot_command(token) + "\r").encode())
            ack = rd.await_protocol_marker(session, rd.reboot_marker, token, 5)
            result["reboot_marker_observed"] = ack is True
            if ack is not True:
                raise Stopped("reboot receipt unknown; no retry")
            if not system.wait_normal(session):
                raise Stopped("protected normal return unknown after 180s")
            result["normal_recovery"] = system.normal_check(session, p, normal, "postflight")
            result["status"] = "recovery-verified-diagnostic-complete"
        rd.write_private_result(result_path, result)
        return True
    except Exception as exc:
        result["failure"] = type(exc).__name__ + ": " + str(exc)
        if session is None:
            result["status"] = "not-started-no-serial-opened"
        rd.write_private_result(result_path, result)
        print("Trial stopped; private evidence preserved. No further input or recovery retry.", file=sys.stderr)
        return False
    finally:
        if session is not None:
            session.close()
        os.close(lock_fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "manifest", "normal-report", "blkid-result", "log", "result"):
        parser.add_argument("--" + name, type=Path, required=True)
    return 0 if run(parser.parse_args()) else 2


if __name__ == "__main__":
    raise SystemExit(main())

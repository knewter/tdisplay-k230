import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("system_trial", Path(__file__).parents[1] / "tools/mainline-drm-system-trial.py")
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)
SYSTEM = "/nix/store/" + "a" * 32 + "-candidate-system"
KERNEL = "/nix/store/" + "b" * 32 + "-kernel"
NORMAL = "/nix/store/" + "c" * 32 + "-normal"
BOOT = "12345678-1234-1234-1234-123456789abc"
OLD = "00000000-0000-0000-0000-000000000001"
RECOVERED = "00000000-0000-0000-0000-000000000002"
TOKEN = "a" * 32
ARGS = f"bootargs=console=ttyS0,115200n8 root=fstab loglevel=4 loglevel=7 init={SYSTEM}/init\n"


def prepared():
    files = {k: {"bytes": 123, "sha256": "d" * 64, "crc32": "abcdef01"} for k, _, _, _ in trial.rd.LOADS}
    return {"system": SYSTEM, "kernel": KERNEL, "pid1": "/nix/store/systemd/lib/systemd/systemd", "bootargs": trial.ordinary_bootargs(ARGS, SYSTEM), "helper_text": "helper", "manifest": {"files": files}, "normal": {"system": NORMAL, "profile": NORMAL, "kernel": "/normal/Image", "uname": "6.6.36", "init": "init=" + NORMAL + "/init", "services": ["active"] * 3, "boot_id": OLD, "trial_from_boot_id": OLD, "boot_files": {name: {"sha256": "d" * 64} for name in trial.STAGES["hashes"]}}}


def facts():
    p = prepared()
    return {
        "identity": {"uid": "0", "system": SYSTEM, "booted": SYSTEM, "kernel": KERNEL + "/Image", "uname": "7.3.0-rc5", "boot_id": BOOT, "pid1": p["pid1"], "getty": "active"},
        "persistent": {"profile": NORMAL, "registration_absent": "1", "root_source": "/dev/mmcblk1p2", "root_type": "ext4", "root_options": "rw,relatime", "root_uuid": "fixture-uuid", "root_label": "NIXOS_SD"},
        "bootargs": {"cmdline": p["bootargs"].removeprefix("bootargs="), "growth_mask": "masked", "registration_mask": "masked"},
        "hashes": {name: "d" * 64 + "  /boot/" + name for name in trial.STAGES["hashes"]},
        "device": {"count": "1", "event": "event7", "ancestry": "/sys/devices/platform/soc/91408000.i2c/i2c-3/3-005d/input/input9"},
        "capture": {"capture_rc": "124"}, "reboot": {"reboot_rc": "0"},
    }


def report(token, stage, values=None, rc=0, with_prompt=True):
    values = facts()[stage] if values is None else values
    body = f"K230_SYS_BEGIN {token} {stage}\n" + "".join(f"K230_SYS {token} {k} RC={rc} VALUE={v}\n" for k, v in values.items()) + f"K230_SYS_END {token} {stage}\n"
    return (body + ("[root@nixos:~]# " if with_prompt else "")).encode()


def touch_rows(move=True, up=True, sync=True):
    def row(code, value):
        return f"Event: time 1.000001, type 3 (EV_ABS), code 57 ({code}), value {value}\n".encode()
    syn = b"Event: time 1.000001, -------------- SYN_REPORT ------------\n"
    out = row("ABS_MT_TRACKING_ID", 4) + row("ABS_MT_POSITION_X", 100) + row("ABS_MT_POSITION_Y", 200) + syn
    if move:
        out += row("ABS_MT_POSITION_X", 120) + syn
    if up:
        out += row("ABS_MT_TRACKING_ID", -1)
        if sync:
            out += syn
    return out


# The counts the real board-side awk (trial.touch_summary_command) computes for
# the default touch_rows() (move=True, up=True, sync=True) capture.
def touch_summary_bytes(token, down=1, up=1, pos_x=2, pos_y=1, syn=3, tracking_release=1,
                        first_down_line=1, last_up_line=7, rows=8):
    return (f"K230_TOUCH_SUMMARY {token} down={down} up={up} pos_x={pos_x} pos_y={pos_y} syn={syn} "
            f"tracking_release={tracking_release} first_down_line={first_down_line} "
            f"last_up_line={last_up_line} rows={rows}\n").encode()


class Clock:
    def __init__(self): self.value = 0
    def __call__(self): self.value += 0.1; return self.value


class PumpSession:
    """Use the actual PrivateSession.pump and its rolling-buffer limit."""
    pump = trial.rd.PrivateSession.pump
    def __init__(self, chunks):
        import io
        self.chunks = list(chunks); self.writes = []; self.buffer = b""; self.log = io.BytesIO()
        self.port = SimpleNamespace(read=lambda n: self.chunks.pop(0) if self.chunks else b"")
    def write(self, data): self.writes.append(data)


class FlowSession(PumpSession):
    instances = []
    values = None
    fail_stage = None
    def __init__(self, serial, log):
        super().__init__([]); self.log = log; self.closed = False
        type(self).instances.append(self)
    def write(self, data):
        super().write(data)
        text = data.decode()
        m = re.search(r"K230_SYS_BEGIN ([0-9a-f]{32}) ([a-z]+)", text)
        if m:
            token, stage = m.groups()
            self.chunks.append(report(token, stage, (self.values or facts())[stage], rc=1 if self.fail_stage == stage else 0))
            if stage == "reboot":
                self.chunks.append(b"U-Boot SPL 2022.10\nLinux version 6.6.36 test\nnixos login: root\n[root@nixos:~]# ")
        elif text.startswith("printf 'K230_TOUCH_BEGIN"):
            token = re.search(r"K230_TOUCH_BEGIN ([a-f0-9]{32})", text)[1]
            self.chunks.append(f"K230_TOUCH_BEGIN {token}\n".encode() + touch_summary_bytes(token) + f"K230_TOUCH_END {token} RC=0\n[root@nixos:~]# ".encode())
        elif data == b"\r": self.chunks.append(b"[root@nixos:~]# ")
    def line(self, command, interrupt=True):
        self.buffer = b""; self.write(command.encode() + b"\r")
        if command == "reboot": self.chunks.append(b"U-Boot SPL\nK230# ")
        if command.startswith("bootm"):
            self.chunks.append(b"Linux version 7.3.0-rc5 test\nnixos login: root\n[root@nixos:~]# ")
    def command(self, command, timeout):
        self.writes.append(command.encode())
        if command.startswith("ext4load"): return b"123 bytes read in 1 ms\nK230# "
        if command.startswith("crc32"): return b"CRC32 for 0 ... 1 ==> abcdef01\nK230# "
        if command == "printenv bootargs": return (prepared()["bootargs"] + "\nK230# ").encode()
        return b"K230# "
    def upload_text(self, path, data, token): self.writes.append(("upload " + path).encode())
    def run_state(self, mode, token):
        n = prepared()["normal"]
        return {k: v for k, v in {**n, "boot_files": {k: v["sha256"] for k, v in n["boot_files"].items()}, "boot_id": OLD if mode == "preflight" else RECOVERED}.items()}
    def close(self): self.closed = True


class SystemTrialTests(unittest.TestCase):
    def marker_free_prepared(self):
        p = self.comparison_prepared()
        p["bootargs"] = trial.ordinary_bootargs(self.comparison_args(), SYSTEM,
                                               wait_initramfs_in_initcall=True, without_boot_markers=True)
        p["without_boot_markers"] = True
        return p

    def test_marker_free_comparison_removes_only_both_exact_enable_tokens(self):
        original = self.comparison_args()
        before = trial.ordinary_bootargs(original, SYSTEM, wait_initramfs_in_initcall=True)
        after = trial.ordinary_bootargs(original, SYSTEM, wait_initramfs_in_initcall=True, without_boot_markers=True)
        self.assertEqual(after.split(), [token for token in before.split() if token not in trial.TRACE_ENABLE])
        self.assertEqual(original, self.comparison_args())
        self.assertEqual(after.split().count("initramfs_async=0"), 1)
        self.assertFalse(any(token.partition("=")[0] in ("k230.boot_trace", "k230.boot_trace_sbi_only")
                             for token in after.split()))
        for changed in (original.replace("k230.boot_trace=1", "k230.boot_trace=0"),
                        original.replace("k230.boot_trace_sbi_only=1", "k230.boot_trace_sbi_only=0"),
                        original.rstrip() + " k230.boot_trace=1", original.rstrip() + " k230.boot_trace_sbi_only=0"):
            with self.assertRaises(ValueError):
                trial.ordinary_bootargs(changed, SYSTEM, wait_initramfs_in_initcall=True, without_boot_markers=True)
        with self.assertRaises(ValueError):
            trial.ordinary_bootargs(original, SYSTEM, without_boot_markers=True)
        for selector in (1, "false", None):
            with self.assertRaises(ValueError):
                trial.ordinary_bootargs(original, SYSTEM, wait_initramfs_in_initcall=True, without_boot_markers=selector)

    def test_marker_free_actual_uboot_command_has_no_variable_expansion_or_enable_tokens(self):
        p = self.marker_free_prepared()
        class MarkerFreeSession(FlowSession):
            def command(self, command, timeout):
                if command == "printenv bootargs":
                    self.writes.append(command.encode())
                    return (p["bootargs"] + "\nK230# ").encode()
                return super().command(command, timeout)
        s = MarkerFreeSession(None, SimpleNamespace(write=lambda x: None))
        trial.boot(s, p)
        writes = [w for w in s.writes if w.startswith(b"setenv bootargs ")]
        self.assertEqual(writes, [('setenv bootargs "' + p["bootargs"].removeprefix("bootargs=") + '"').encode()])
        self.assertNotIn(b"${", writes[0]); self.assertNotIn(b"k230.boot_trace", writes[0])
        self.assertIn(b"initramfs_async=0", writes[0]); self.assertLess(len(writes[0]), 512)
        self.assertEqual(sum(w.startswith(b"ext4load ") for w in s.writes), 5)
        self.assertEqual(sum(w.startswith(b"crc32 ") for w in s.writes), 5)
        self.assertFalse(any(b"saveenv" in w for w in s.writes))

        s = FlowSession(None, SimpleNamespace(write=lambda x: None))
        with self.assertRaises(trial.Unknown): trial.boot(s, p)
        self.assertFalse(any(w.startswith(b"bootm ") for w in s.writes))
        s = MarkerFreeSession(None, SimpleNamespace(write=lambda x: None))
        with mock.patch.object(trial, "wait_candidate", return_value=False):
            with self.assertRaises(trial.Unknown): trial.boot(s, p)
        self.assertEqual(s.writes[-1], b"bootm 0x8000000 0x9000000 0x8400000\r")

    def test_marker_free_transport_rejects_unsafe_oversize_or_remaining_tokens_before_input(self):
        p = self.marker_free_prepared()
        for suffix in (' $unsafe', ' "bad"', ' ;saveenv', ' `bad`', '\n', ' filler=' + 'a' * 512,
                       ' k230.boot_trace=0', ' k230.boot_trace_sbi_only'):
            bad = copy.deepcopy(p); bad["bootargs"] += suffix
            s = FlowSession(None, SimpleNamespace(write=lambda x: None))
            with self.subTest(suffix=suffix), self.assertRaises(ValueError): trial.boot(s, bad)
            self.assertEqual(s.writes, [])
        bad = copy.deepcopy(p); bad["bootargs"] = bad["bootargs"].replace("initramfs_async=0", "initramfs_async=1")
        s = FlowSession(None, SimpleNamespace(write=lambda x: None))
        with self.assertRaises(ValueError): trial.boot(s, bad)
        self.assertEqual(s.writes, [])

    def test_marker_free_runtime_argument_guard_rejects_any_restored_enable_token(self):
        p = self.marker_free_prepared(); value = facts()["bootargs"].copy()
        value["cmdline"] = p["bootargs"].removeprefix("bootargs=")
        trial.validate_stage("bootargs", value, p, p["normal"])
        for flag in trial.TRACE_ENABLE:
            bad = value.copy(); bad["cmdline"] += " " + flag
            with self.assertRaises(trial.Unknown): trial.validate_stage("bootargs", bad, p, p["normal"])

    def test_marker_free_mode_saved_and_restored_for_finish(self):
        p = self.marker_free_prepared(); values = facts()
        values["bootargs"]["cmdline"] = p["bootargs"].removeprefix("bootargs=")
        class MarkerFreeSession(FlowSession):
            def command(self, command, timeout):
                if command == "printenv bootargs":
                    self.writes.append(command.encode())
                    return (p["bootargs"] + "\nK230# ").encode()
                return super().command(command, timeout)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); root.chmod(0o700)
            args = SimpleNamespace(phase="begin", bundle=Path("/nix/store/bundle"), manifest=root/"manifest",
                                   normal_report=root/"normal-report", state=root/"state.json", log=root/"begin.log",
                                   result=root/"begin.json", real_touch=False, wait_initramfs_in_initcall=True,
                                   without_boot_markers=True)
            FlowSession.values = values; FlowSession.fail_stage = None
            with mock.patch.dict(sys.modules, {"serial": SimpleNamespace()}), \
                 mock.patch.object(trial, "prepare", return_value=p) as prepare_call, \
                 mock.patch.object(trial.rd, "PrivateSession", MarkerFreeSession), \
                 mock.patch.object(trial.rd, "LOCK_PATH", root/"lock"):
                self.assertTrue(trial.run(args))
                self.assertTrue(json.loads(args.state.read_text())["without_boot_markers"])
                args.phase = "finish"; args.log = root/"finish.log"; args.result = root/"finish.json"
                args.without_boot_markers = args.wait_initramfs_in_initcall = False
                self.assertTrue(trial.run(args))
                self.assertTrue(prepare_call.call_args.kwargs["without_boot_markers"])
                self.assertTrue(prepare_call.call_args.kwargs["wait_initramfs_in_initcall"])
                self.assertTrue(json.loads(args.result.read_text())["without_boot_markers"])
                self.assertEqual(json.loads(args.result.read_text())["status"], "normal-recovery-verified")
            FlowSession.values = None

    def test_marker_free_bad_saved_mode_rejected_before_serial(self):
        for mode, joined in (("false", True), (True, False)):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); root.chmod(0o700)
                state = self.state(); state.update(without_boot_markers=mode, wait_initramfs_in_initcall=joined)
                path = root/"state.json"; path.write_text(json.dumps(state)); path.chmod(0o600)
                args = SimpleNamespace(phase="finish", state=path, real_touch=False)
                with mock.patch.object(trial.rd, "PrivateSession") as session:
                    with self.assertRaises(ValueError): trial.run(args)
                    session.assert_not_called()

    def test_marker_free_cli_requires_begin_and_earlier_join_before_serial(self):
        for phase, flags in (("begin", []), ("touch", []), ("finish", [])):
            cmd = [sys.executable, str(Path(trial.__file__)), phase, "--state", "/nonexistent/state",
                   "--log", "/nonexistent/log", "--result", "/nonexistent/result", "--without-boot-markers"]
            if phase == "begin": cmd += ["--bundle", "/none", "--manifest", "/none", "--normal-report", "/none"]
            result = subprocess.run(cmd + flags, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"requires --wait-initramfs-in-initcall", result.stderr)

    def comparison_args(self):
        return ARGS.rstrip() + " k230.boot_trace=1 k230.boot_trace_sbi_only=1\n"

    def comparison_prepared(self):
        p = prepared()
        p["bootargs"] = trial.ordinary_bootargs(self.comparison_args(), SYSTEM, wait_initramfs_in_initcall=True)
        p["diagnostic_controls"] = trial.diagnostic_controls(True)
        return p

    def test_initramfs_comparison_changes_only_one_volatile_token(self):
        original = self.comparison_args()
        before = trial.ordinary_bootargs(original, SYSTEM)
        after = trial.ordinary_bootargs(original, SYSTEM, wait_initramfs_in_initcall=True)
        self.assertEqual(after, before + " initramfs_async=0")
        self.assertEqual(after.split().count("initramfs_async=0"), 1)
        for conflict in ("initramfs_async", "initramfs_async=0", "initramfs_async=1", "initramfs_async=false"):
            for selected in (False, True):
                with self.subTest(conflict=conflict, selected=selected), self.assertRaises(ValueError):
                    trial.ordinary_bootargs(original.rstrip() + " " + conflict, SYSTEM,
                                            wait_initramfs_in_initcall=selected)

    def test_comparison_rejects_different_console_instrumentation_and_untyped_selector(self):
        original = self.comparison_args()
        for changed in (ARGS, original.replace("k230.boot_trace_sbi_only=1", "k230.boot_trace_sbi=1"),
                        original.replace("console=ttyS0,115200n8", "console=tty0"),
                        original.rstrip() + " console=tty0", original.rstrip() + " earlycon=sbi",
                        original.rstrip() + " keep_bootcon", original.rstrip() + " k230.boot_trace_sbi=1",
                        original.rstrip() + " k230.boot_trace=1"):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                trial.ordinary_bootargs(changed, SYSTEM, wait_initramfs_in_initcall=True)
        for name in ("k230.boot_trace", "k230.boot_trace_sbi_only", "k230.boot_trace_sbi", "console",
                     "earlycon", "keep_bootcon"):
            for suffix in ("", "=0", "=1", "=false"):
                with self.subTest(name=name, suffix=suffix), self.assertRaises(ValueError):
                    trial.ordinary_bootargs(original.rstrip() + " " + name + suffix, SYSTEM,
                                            wait_initramfs_in_initcall=True)
        for value in (1, 0, "false", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                trial.ordinary_bootargs(original, SYSTEM, wait_initramfs_in_initcall=value)

    def test_comparison_real_boot_keeps_load_crc_printed_args_and_passive_readiness_gates(self):
        p = self.comparison_prepared()
        class ComparisonSession(FlowSession):
            def command(self, command, timeout):
                if command == "printenv bootargs":
                    self.writes.append(command.encode())
                    return (p["bootargs"] + "\nK230# ").encode()
                return super().command(command, timeout)
        s = ComparisonSession(None, SimpleNamespace(write=lambda x: None))
        trial.boot(s, p)
        self.assertEqual(sum(w.startswith(b"ext4load ") for w in s.writes), 5)
        self.assertEqual(sum(w.startswith(b"crc32 ") for w in s.writes), 5)
        setenv = [w for w in s.writes if w.startswith(b"setenv bootargs ")]
        self.assertEqual(setenv, [('setenv bootargs "${bootargs} ' + " ".join(trial.CONTROLS)
                                  + ' initramfs_async=0"').encode()])
        self.assertLess(len(setenv[0]), 512)
        self.assertEqual(sum(w.startswith(b"bootm ") for w in s.writes), 1)
        self.assertFalse(any(b"saveenv" in w for w in s.writes))

        # A returned printed line without the token must stop before bootm.
        s = FlowSession(None, SimpleNamespace(write=lambda x: None))
        with self.assertRaises(trial.Unknown): trial.boot(s, p)
        self.assertFalse(any(w.startswith(b"bootm ") for w in s.writes))

        # After bootm, unknown readiness must not send a receipt or retry.
        s = ComparisonSession(None, SimpleNamespace(write=lambda x: None))
        with mock.patch.object(trial, "wait_candidate", return_value=False):
            with self.assertRaises(trial.Unknown): trial.boot(s, p)
        self.assertEqual(s.writes[-1], b"bootm 0x8000000 0x9000000 0x8400000\r")
        self.assertEqual(sum(w.startswith(b"reboot") for w in s.writes), 1)

    def test_comparison_identity_requires_exact_runtime_token(self):
        p = self.comparison_prepared()
        value = facts()["bootargs"].copy()
        value["cmdline"] = p["bootargs"].removeprefix("bootargs=")
        trial.validate_stage("bootargs", value, p, p["normal"])
        for replacement in ("", "initramfs_async=1", "initramfs_async=0 initramfs_async=0"):
            bad = value.copy(); bad["cmdline"] = value["cmdline"].replace("initramfs_async=0", replacement)
            with self.assertRaises(trial.Unknown): trial.validate_stage("bootargs", bad, p, p["normal"])

    def test_comparison_mode_saved_and_restored_without_cli_reselection(self):
        p = self.comparison_prepared()
        values = facts(); values["bootargs"]["cmdline"] = p["bootargs"].removeprefix("bootargs=")
        class ComparisonSession(FlowSession):
            def command(self, command, timeout):
                if command == "printenv bootargs":
                    self.writes.append(command.encode())
                    return (p["bootargs"] + "\nK230# ").encode()
                return super().command(command, timeout)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); root.chmod(0o700)
            args = SimpleNamespace(phase="begin", bundle=Path("/nix/store/bundle"), manifest=root/"manifest",
                                   normal_report=root/"normal-report", state=root/"state.json", log=root/"begin.log",
                                   result=root/"begin.json", real_touch=False, wait_initramfs_in_initcall=True)
            FlowSession.values = values; FlowSession.fail_stage = None
            with mock.patch.dict(sys.modules, {"serial": SimpleNamespace()}), \
                 mock.patch.object(trial, "prepare", return_value=p) as prepare_call, \
                 mock.patch.object(trial.rd, "PrivateSession", ComparisonSession), \
                 mock.patch.object(trial.rd, "LOCK_PATH", root/"lock"):
                self.assertTrue(trial.run(args))
                self.assertTrue(json.loads(args.state.read_text())["wait_initramfs_in_initcall"])
                self.assertTrue(json.loads(args.result.read_text())["wait_initramfs_in_initcall"])
                args.phase = "finish"; args.log = root/"finish.log"; args.result = root/"finish.json"
                args.wait_initramfs_in_initcall = False
                self.assertTrue(trial.run(args))
                self.assertTrue(prepare_call.call_args.kwargs["wait_initramfs_in_initcall"])
                self.assertTrue(json.loads(args.result.read_text())["wait_initramfs_in_initcall"])
                self.assertEqual(json.loads(args.result.read_text())["status"], "normal-recovery-verified")
            FlowSession.values = None

    def test_invalid_saved_comparison_mode_fails_before_serial_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); root.chmod(0o700)
            state = self.state(); state["wait_initramfs_in_initcall"] = "false"
            path = root/"state.json"; path.write_text(json.dumps(state)); path.chmod(0o600)
            args = SimpleNamespace(phase="finish", state=path, real_touch=False)
            with mock.patch.object(trial.rd, "PrivateSession") as session:
                with self.assertRaises(ValueError): trial.run(args)
                session.assert_not_called()

    def test_cli_comparison_option_is_begin_only_before_any_serial_access(self):
        for phase in ("touch", "finish"):
            cmd = [sys.executable, str(Path(trial.__file__)), phase, "--state", "/nonexistent/state",
                   "--log", "/nonexistent/log", "--result", "/nonexistent/result", "--wait-initramfs-in-initcall"]
            result = subprocess.run(cmd, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"begin-only", result.stderr)

    def test_exact_qualified_bootargs_and_forbidden_controls(self):
        self.assertEqual(trial.ordinary_bootargs(ARGS, SYSTEM), ARGS.rstrip() + " " + " ".join(trial.CONTROLS))
        for extra in ("rdinit=/bin/sh", "PATH=/bin", "clk_ignore_unused", "initcall_debug", "loglevel=8", "fsck.mode=skip", "systemd.mask=x", "systemd.unit=rescue.target", "rd.systemd.debug_shell", "debug", "dyndbg=x"):
            with self.subTest(extra=extra), self.assertRaises(ValueError): trial.ordinary_bootargs(ARGS.rstrip() + " " + extra, SYSTEM)
        for bad in (ARGS.replace(SYSTEM, NORMAL), ARGS.replace("root=fstab", "root=/dev/root"), ARGS + "\n", ARGS.replace("bootargs=", "")):
            with self.assertRaises(ValueError): trial.ordinary_bootargs(bad, SYSTEM)

    def test_reports_reject_echo_wrong_token_duplicate_truncated_and_nonzero(self):
        good = report(TOKEN, "identity")
        self.assertIsNotNone(trial.parse_report(good, TOKEN, "identity"))
        for bad in (b"echo " + good, good + good, good[:-20], good.replace(TOKEN.encode(), b"b" * 32), good.replace(b"uid RC=0", b"uid RC=999"), good.replace(b"uid RC=0", b"uid RC=0\n"), good.replace(b"K230_SYS_END", b"echo K230_SYS_END")):
            self.assertIsNone(trial.parse_report(bad, TOKEN, "identity"))
        session = PumpSession([report(TOKEN, "identity", rc=1)])
        with self.assertRaises(trial.Unknown): trial.exchange(session, TOKEN, "identity", "probe", clock=Clock())
        self.assertEqual(session.writes, [b"probe\r"])

    def test_real_pump_split_and_stale_rolling_buffer(self):
        good = report(TOKEN, "identity")
        session = PumpSession([b"noise" * 30000 + b"\n", good[:70], good[70:200], good[200:]])
        session.buffer = good  # Pre-command stale success must not satisfy.
        value = trial.exchange(session, TOKEN, "identity", "probe", clock=Clock())
        self.assertEqual(value["boot_id"], BOOT)
        self.assertLessEqual(len(session.buffer), 131072)
        self.assertEqual(len(session.writes), 1)

    def test_timeouts_validate_before_input_and_unknown_sends_no_retry(self):
        for timeout in (0, -1, float("inf"), float("nan"), 61):
            session = PumpSession([])
            with self.assertRaises(ValueError): trial.exchange(session, TOKEN, "identity", "probe", timeout=timeout)
            self.assertEqual(session.writes, [])
        session = PumpSession([])
        with self.assertRaises(trial.Unknown): trial.exchange(session, TOKEN, "identity", "probe", timeout=0.5, clock=Clock())
        self.assertEqual(session.writes, [b"probe\r"])

    def test_verbose_candidate_readiness_beyond_eight_seconds_has_no_input(self):
        chunks = [b"Linux version 7.3.0-rc5 test\n"] + [b"kernel progress\n" * 5000] * 100 + [b"nixos login: root\n", b"[root@nixos:~]", b"# "]
        session = PumpSession(chunks)
        self.assertTrue(trial.wait_candidate(session, timeout=30, clock=Clock()))
        self.assertEqual(session.writes, [])
        self.assertLessEqual(len(session.buffer), 131072)

    def test_candidate_readiness_rejects_prebanner_prompt_normal_and_continuation(self):
        for chunk in (b"nixos login: root\n[root@nixos:~]# ", b"Linux version 6.6.36 test\nnixos login: root\n[root@nixos:~]# ", b"Linux version 7.3.0-rc5 test\nnixos login: root\n> "):
            self.assertFalse(trial.wait_candidate(PumpSession([chunk]), timeout=0.5, clock=Clock()))

    def test_each_identity_mismatch_stops_before_later_stage(self):
        p = prepared(); n = p["normal"]
        for stage, key, value in (("identity", "uid", "1"), ("identity", "system", NORMAL), ("identity", "boot_id", OLD), ("identity", "boot_id", RECOVERED), ("persistent", "profile", SYSTEM), ("persistent", "registration_absent", "0"), ("persistent", "root_options", "ro,relatime"), ("bootargs", "registration_mask", "loaded"), ("bootargs", "cmdline", ARGS), ("hashes", "Image", "f" * 64 + " /boot/Image")):
            v = facts()[stage].copy(); v[key] = value
            with self.subTest(stage=stage,key=key), self.assertRaises(trial.Unknown): trial.validate_stage(stage, v, p, n, expected_boot=BOOT, root=facts()["persistent"])
        for stage in ("identity", "persistent", "bootargs", "hashes"):
            trial.validate_stage(stage, facts()[stage], p, n, expected_boot=BOOT, root=facts()["persistent"])

    def test_partial_identity_facts_survive_later_failure(self):
        observed = {}
        with mock.patch.object(trial, "exchange", side_effect=[facts()["identity"], trial.Unknown("persistent timeout")]):
            with self.assertRaises(trial.Unknown): trial.identity(None, prepared(), prepared()["normal"], facts=observed)
        self.assertEqual(observed, {"identity": facts()["identity"]})

    def test_physical_goodix_selection_and_bounded_capture(self):
        self.assertEqual(trial.validate_device(facts()["device"]), "/dev/input/event7")
        for key, value in (("count", "0"), ("count", "2"), ("event", "event7;reboot"), ("ancestry", "/sys/devices/virtual/input/input9"), ("ancestry", "/sys/devices/platform/soc/other/input/input9")):
            v = facts()["device"].copy(); v[key] = value
            with self.assertRaises(trial.Unknown): trial.validate_device(v)
        cmd = trial.capture_command(TOKEN, SYSTEM, "/dev/input/event7")
        self.assertIn("--signal=TERM --kill-after=2s 30s", cmd)
        self.assertNotIn("--grab", cmd); self.assertNotIn("uinput", cmd)
        for seconds in (0,31,1.5):
            with self.assertRaises(ValueError): trial.capture_command(TOKEN,SYSTEM,"/dev/input/event7",seconds)

    def test_real_evtest_frames_require_single_contact_move_release_and_syn(self):
        self.assertTrue(trial.parse_touch(touch_rows())["complete_contact"])
        for data in (b"", touch_rows(move=False), touch_rows(up=False), touch_rows(sync=False), b"Supported events: ABS_MT_TRACKING_ID SYN_REPORT\n", touch_rows(move=False) + touch_rows(move=False)):
            self.assertFalse(trial.parse_touch(data)["complete_contact"])

    def test_multitouch_slots_cannot_mix_separate_stationary_contacts_into_drag(self):
        switch=b"Event: time 1.000001, type 3 (EV_ABS), code 47 (ABS_MT_SLOT), value 1\n"
        second=touch_rows(move=False).replace(b"value 100",b"value 300").replace(b"value 200",b"value 400")
        data=touch_rows(move=False,up=False)+switch+second
        data+=b"Event: time 1.000001, type 3 (EV_ABS), code 47 (ABS_MT_SLOT), value 0\n"
        data+=b"Event: time 1.000001, type 3 (EV_ABS), code 57 (ABS_MT_TRACKING_ID), value -1\nEvent: time 1.000001, -------------- SYN_REPORT ------------\n"
        result=trial.parse_touch(data)
        self.assertTrue(result["down"]);self.assertTrue(result["up"])
        self.assertFalse(result["position_change"]);self.assertFalse(result["complete_contact"])

    def test_bad_capture_and_unknown_device_completion_never_retrieve_or_reboot(self):
        for replies in ([trial.Unknown("device timeout")], [facts()["device"], {"capture_rc": "137"}], [facts()["device"], trial.Unknown("capture timeout")]):
            session=PumpSession([])
            with mock.patch.object(trial,"exchange",side_effect=replies):
                with self.assertRaises(trial.Unknown): trial.touch(session,prepared())
            self.assertEqual(session.writes,[])

    def test_retrieval_missing_duplicate_or_nonzero_end_never_sends_more_input(self):
        for reply in (b"", f"K230_TOUCH_BEGIN {TOKEN}\nK230_TOUCH_END {TOKEN} RC=1\n[root@nixos:~]# ".encode(), (f"K230_TOUCH_BEGIN {TOKEN}\nK230_TOUCH_END {TOKEN} RC=0\n"*2+"[root@nixos:~]# ").encode()):
            session=PumpSession([reply])
            with mock.patch.object(trial,"exchange",side_effect=[facts()["device"],facts()["capture"]]), mock.patch.object(trial.uuid,"uuid4",return_value=SimpleNamespace(hex=TOKEN)), mock.patch.object(trial.time,"monotonic",side_effect=Clock()):
                with self.assertRaises(trial.Unknown): trial.touch(session,prepared())
            self.assertEqual(len(session.writes),1)
            self.assertNotIn(b"reboot",session.writes[0])

    def test_protected_postflight_rejects_hash_profile_services_and_old_boot(self):
        session=FlowSession(None,SimpleNamespace(write=lambda x: None))
        good=session.run_state("postflight",TOKEN)
        for key,value in (("profile",SYSTEM),("services",["inactive"]*3),("boot_id",OLD),("boot_files",{})):
            bad=copy.deepcopy(good); bad[key]=value
            with mock.patch.object(session,"run_state",return_value=bad):
                with self.assertRaises(trial.Unknown): trial.normal_check(session,prepared(),prepared()["normal"],"postflight")

    def test_generated_reports_execute_only_isolated_fixture_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); b = root / "sw/bin"; b.mkdir(parents=True)
            for tool in ("id", "readlink", "uname", "cat", "findmnt", "systemctl", "sha256sum"):
                script = b / tool
                script.write_text("#!/bin/sh\nprintf fixture\n")
                script.chmod(0o700)
            for stage in ("identity", "persistent", "bootargs", "hashes"):
                cmd = trial.report_command(TOKEN, stage, str(root))
                # No generated command may access host proc/sys/run/mounts or
                # persistent profile files. All absolute probe targets replaced.
                for prefix in ("/proc/", "/sys/", "/run/", "/boot/", "/nix/var/"):
                    cmd = cmd.replace(prefix, str(root / "targets") + prefix)
                cmd = cmd.replace("/nix-path-registration", str(root / "absent-registration"))
                result = subprocess.run(["/bin/sh", "-c", cmd], capture_output=True, check=True)
                parsed = trial.parse_report(result.stdout + b"[root@nixos:~]# ", TOKEN, stage)
                self.assertEqual(set(parsed), set(trial.STAGES[stage]))
                self.assertTrue(all(v["rc"] == 0 for v in parsed.values()))
                self.assertLess(len(cmd), 3500)

    def run_phase(self, directory, phase, state=None, **patches):
        root = Path(directory); root.chmod(0o700)
        state_path = root / "state.json"
        if state is not None:
            state_path.write_text(json.dumps(state)); state_path.chmod(0o600)
        args = SimpleNamespace(phase=phase,bundle=Path("/nix/store/bundle"),manifest=root/"manifest",normal_report=root/"normal-report",state=state_path,log=root/(phase+".log"),result=root/(phase+".json"),real_touch=phase=="touch")
        FlowSession.instances=[]; FlowSession.values=None; FlowSession.fail_stage=None
        with mock.patch.dict(sys.modules,{"serial":SimpleNamespace()}), mock.patch.object(trial,"prepare",return_value=prepared()), mock.patch.object(trial.rd,"PrivateSession",FlowSession), mock.patch.object(trial.rd,"LOCK_PATH",root/"lock"):
            if patches:
                with mock.patch.multiple(trial,**patches): ok=trial.run(args)
            else: ok=trial.run(args)
        return ok,json.loads(args.result.read_text()),json.loads(state_path.read_text()) if state_path.exists() else None,FlowSession.instances[-1]

    def state(self):
        return {"schema":"mainline-system-trial-v1","status":"candidate-ready","bundle":"/nix/store/bundle","manifest":"/private/manifest","normal_report":"/private/report","normal":prepared()["normal"],"root":facts()["persistent"],"candidate_boot_id":BOOT,"candidate":facts()}

    def test_complete_begin_touch_finish_protocol_with_private_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok,result,state,s=self.run_phase(tmp,"begin")
            self.assertTrue(ok); self.assertEqual(result["status"],"candidate-ready-qualified-ordinary-init")
            self.assertFalse(any(b"evtest" in w or b"systemctl reboot" in w for w in s.writes))
            ok,result,state,s=self.run_phase(tmp,"touch",state)
            self.assertTrue(ok); self.assertTrue(result["touch"]["events"]["complete_contact"])
            self.assertEqual(sum(b"/evtest " in w for w in s.writes),1)
            ok,result,state,s=self.run_phase(tmp,"finish",state)
            self.assertTrue(ok); self.assertEqual(state["status"],"normal-recovery-verified")
            self.assertEqual(sum(b"/systemctl reboot" in w for w in s.writes),1)
            self.assertEqual(result["normal_recovery"]["boot_id"],RECOVERED)
            self.assertTrue(s.closed)

    def test_guard_unknown_suppresses_evtest_reboot_and_invalidates_state(self):
        for phase in ("touch","finish"):
            with tempfile.TemporaryDirectory() as tmp:
                ok,result,state,s=self.run_phase(tmp,phase,self.state(),identity=mock.Mock(side_effect=trial.Unknown("identity timeout")))
                self.assertFalse(ok); self.assertEqual(state["status"],"recovery-required-unknown")
                self.assertEqual(s.writes,[b"\r"])
                self.assertIsNone(result["normal_recovery"])

    def test_finish_normal_timeout_preserves_identity_and_one_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok,result,state,s=self.run_phase(tmp,"finish",self.state(),wait_normal=mock.Mock(return_value=False))
            self.assertFalse(ok); self.assertEqual(result["candidate"]["identity"]["boot_id"],BOOT)
            self.assertEqual(result["reboot"],{"reboot_rc":"0"})
            self.assertEqual(sum(b"/systemctl reboot" in w for w in s.writes),1)
            self.assertFalse(any(w.startswith(b"upload") for w in s.writes))
            self.assertEqual(state["status"],"recovery-required-unknown")

    def test_reboot_ack_does_not_need_shell_prompt_or_discard_normal_bytes(self):
        session=PumpSession([report(TOKEN,"reboot",with_prompt=False)+b"U-Boot SPL\nLinux version 6.6.36 test\nnixos login: root\n[root@nixos:~]# "])
        self.assertEqual(trial.exchange(session,TOKEN,"reboot","request",clock=Clock()),{"reboot_rc":"0"})
        self.assertTrue(trial.wait_normal(session,timeout=1,clock=Clock()))

    def test_normal_recovery_requires_fresh_spl_kernel_login_prompt(self):
        for chunk in (b"nixos login: root\n[root@nixos:~]# ",b"U-Boot SPL\nLinux version 7.3.0-rc5 test\nnixos login: root\n[root@nixos:~]# "):
            self.assertFalse(trial.wait_normal(PumpSession([chunk]),timeout=0.5,clock=Clock()))

    def test_private_state_rejects_wrong_boot_phase_permissions_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); root.chmod(0o700); p=root/"state"; p.write_text(json.dumps(self.state())); p.chmod(0o600)
            self.assertEqual(trial.private_existing(p)["candidate_boot_id"],BOOT)
            p.chmod(0o644)
            with self.assertRaises(ValueError): trial.private_existing(p)
            p.chmod(0o600); link=root/"link"; link.symlink_to(p)
            with self.assertRaises(ValueError): trial.private_existing(link)
            state=self.state(); state["status"]="recovery-required-unknown"; p.write_text(json.dumps(state))
            with self.assertRaises(ValueError): trial.private_existing(p)

    def test_busy_board_lock_opens_no_serial_and_preserves_ready_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o700);state=root/"state.json"
            state.write_text(json.dumps(self.state()));state.chmod(0o600)
            args=SimpleNamespace(phase="finish",state=state,log=root/"log",result=root/"result",real_touch=False)
            with mock.patch.dict(sys.modules,{"serial":SimpleNamespace()}),mock.patch.object(trial,"prepare",return_value=prepared()),mock.patch.object(trial.rd,"LOCK_PATH",root/"lock"),mock.patch.object(trial.fcntl,"flock",side_effect=BlockingIOError),mock.patch.object(trial.rd,"PrivateSession") as session:
                self.assertFalse(trial.run(args));session.assert_not_called()
            self.assertEqual(json.loads(state.read_text())["status"],"candidate-ready")
            self.assertEqual(json.loads(args.result.read_text())["status"],"not-started-no-serial-opened")


class NormalBannerTests(unittest.TestCase):
    def test_mainline_normal_relies_on_spl_and_duplicate_banner(self):
        self.assertIsNone(trial.normal_banner({"uname": "7.3.0-rc5"}))
        self.assertFalse(trial.returned_to_normal(b"[ 0.0] Linux version 7.3.0-rc5 x\n", None))
        self.assertTrue(trial.returned_to_normal(b"U-Boot SPL 2022.10\n", None))

    def test_distinct_normal_kernel_is_detected(self):
        banner = trial.normal_banner({"uname": "6.6.36"})
        self.assertTrue(trial.returned_to_normal(b"[ 0.0] Linux version 6.6.36 vendor\n", banner))

    def test_committed_baseline_is_the_installed_mainline(self):
        self.assertIsNone(trial.NORMAL_BANNER)


if __name__ == "__main__": unittest.main()

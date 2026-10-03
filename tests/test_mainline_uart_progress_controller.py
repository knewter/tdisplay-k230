"""Host fixture/wire checks only. No serial, Nix build, or hardware activity."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("shell_fixtures", ROOT / "tests/test_mainline_shell_pid1_comparison.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
trial = fixtures.trial
TOKEN = "a" * 32
ARGS = trial.shell_pid1_bootargs(fixtures.ORIGINAL, fixtures.SYSTEM) + " " + trial.UART_PROGRESS_FLAG
BANNER = b"[    0.1] Linux version 7.3.0-rc5 candidate\n"
CMDLINE = ("[    0.2] Kernel command line: " + ARGS.removeprefix("bootargs=") + "\n").encode()
BOOT = BANNER + CMDLINE
READY = b"[    4.1] Run /bin/sh as init process\nsh: cannot set terminal process group (-1): Inappropriate ioctl for device\nsh: no job control in this shell\nsh-5.3# "
NORMAL = b"\nU-Boot SPL 2022.10 test\n[    0.1] Linux version 6.6.36 normal\nnixos login: \nroot@nixos:~# "


def record(n, state=0, **changes):
    fields = {key: 1 for key in trial.UART_PROGRESS_FIELDS}
    fields.update(j=n * 1250, t=n * 5000000000, u=17, ti=5, ui=n * 10, tc=n * 20)
    if state:
        fields.update({key: 0 for key in trial.UART_PROGRESS_UART_FIELDS})
    fields.update(changes)
    return (f"\nK230_UP1 n={n} s={state}" + "".join(
        f" {key}={fields[key]:0{16 if key in ('j', 't') else 8}x}" for key in trial.UART_PROGRESS_FIELDS) + "\n").encode()


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): self.now += 0.1; return self.now


class Wire:
    pump = trial.PrivateSession.pump
    def __init__(self, chunks, reply=True):
        self.chunks = list(chunks); self.buffer = b"stale normal login\nsh-5.3# "
        self.writes = []; self.reply = reply; self.log = io.BytesIO()
        self.port = SimpleNamespace(read=lambda size: self.chunks.pop(0) if self.chunks else b"")
    def write(self, data):
        self.writes.append(data)
        if self.reply:
            self.chunks.insert(0, f"\nK230_RDINIT_RX {TOKEN}\nsh-5.3# ".encode())


def observe(wire, **kwargs):
    return trial.observe_uart_progress(wire, TOKEN, ARGS, timeout=5, readiness_timeout=3,
                                       clock=Clock(), **kwargs)


class UartProgressControllerTests(unittest.TestCase):
    def test_exact_numeric_protocol_all_states_and_maximum(self):
        for state in range(6):
            r = trial.uart_progress_record(record(0, state).lstrip(b"\n"))
            self.assertEqual(r["s"], state)
        maximum = record(5, **{k: 2 ** (64 if k in ("j", "t") else 32) - 1 for k in trial.UART_PROGRESS_FIELDS})
        self.assertLess(len(maximum), 256)
        self.assertIsNotNone(trial.uart_progress_record(maximum.lstrip(b"\n")))

    def test_protocol_rejects_unknown_version_case_width_state_and_insertions(self):
        valid = record(0).lstrip(b"\n")
        for bad in (valid[:-1], valid + valid, valid.replace(b"UP1", b"UP2"),
                    valid.replace(b"n=0", b"n=00"), valid.replace(b"s=0", b"s=6"),
                    valid.replace(b"u=00000011", b"u=0000001A"),
                    valid.replace(b"rx=00000001", b"rx=0000001"),
                    valid.replace(b" tx=", b" [1.1] printk tx="),
                    record(1, 2, rx=1).lstrip(b"\n"), record(1, ti=0, tc=1).lstrip(b"\n"),
                    record(1, u=0).lstrip(b"\n")):
            with self.subTest(bad=bad): self.assertIsNone(trial.uart_progress_record(bad))

    def test_real_pump_split_ready_then_exactly_one_receipt_no_further_input(self):
        wire = Wire([BOOT[:20], BOOT[20:] + READY[:40], READY[40:], *[record(n) for n in range(6)]])
        result = observe(wire)
        self.assertTrue(result["readiness_observed"]); self.assertTrue(result["receipt_observed"])
        self.assertTrue(result["records_complete"]); self.assertEqual(result["stimulus_attempts"], 1)
        self.assertEqual(wire.writes, [(trial.reception_command(TOKEN) + "\r").encode()])
        self.assertFalse(result["reboot_requested"])
        self.assertEqual(result["samples_observed_after_stimulus"], 6)

    def test_records_before_prompt_are_not_post_stimulus_rx_evidence(self):
        wire = Wire([BOOT + b"".join(record(n) for n in range(6)) + READY])
        result = observe(wire)
        self.assertTrue(result["records_complete"])
        self.assertEqual(result["samples_observed_after_stimulus"], 0)
        self.assertEqual(len(wire.writes), 1)

    def test_prompt_and_first_report_same_pump_batch_and_actual_elapsed(self):
        wire = Wire([BOOT + READY + record(0), *[record(n) for n in range(1, 6)], NORMAL])
        result = observe(wire)
        self.assertTrue(result["readiness_observed"]); self.assertEqual(len(wire.writes), 1)
        self.assertFalse(result["records"][0]["observed_after_stimulus"])
        self.assertEqual(result["capture_timeout_seconds"], 5)
        self.assertLess(result["capture_seconds"], 5)
        for suffix in (b"\nunrelated injected status\n", b"\nK230_UP1 malformed\n", record(0)[:-1]):
            wire = Wire([BOOT + READY + suffix])
            self.assertEqual(observe(wire)["stimulus_attempts"], 0)

    def test_exact_fresh_kernel_received_arguments_required_before_stimulus(self):
        for cmdline, status in ((b"", "UNKNOWN"), (CMDLINE.replace(b"initramfs_async=0", b"initramfs_async=1"), "MISMATCH"),
                                (CMDLINE + CMDLINE, "DUPLICATE")):
            wire = Wire([CMDLINE, BANNER + cmdline + READY, *[record(n) for n in range(6)]])
            result = observe(wire)
            self.assertEqual(result["kernel_args_status"], status)
            self.assertFalse(result["readiness_observed"]); self.assertEqual(wire.writes, [])

    def test_missing_receipt_never_retries_or_requests_reboot(self):
        wire = Wire([BOOT + READY, *[record(n) for n in range(6)]], reply=False)
        result = observe(wire)
        self.assertFalse(result["receipt_observed"]); self.assertEqual(result["receipt_status"], "UNKNOWN")
        self.assertTrue(result["records_complete"]); self.assertEqual(len(wire.writes), 1)

    def test_stale_echo_continuation_preentry_and_wrong_banner_never_send(self):
        for output in (READY, BOOT + b"sh-5.3# ", BOOT + READY.replace(b"sh-5.3# ", b"> "),
                       BOOT.replace(b"7.3.0-rc5", b"6.6.36") + READY,
                       BOOT + READY.replace(b"sh-5.3# ", b"printf 'sh-5.3# '")):
            wire = Wire([output, b"unrelated\n"])
            result = observe(wire)
            self.assertEqual(wire.writes, []); self.assertEqual(result["stimulus_attempts"], 0)

    def test_readiness_after_deadline_cannot_send(self):
        wire = Wire([BOOT, *[b"noise\n"] * 20, READY])
        result = trial.observe_uart_progress(wire, TOKEN, ARGS, timeout=5, readiness_timeout=1, clock=Clock())
        self.assertEqual(wire.writes, []); self.assertFalse(result["readiness_observed"])

    def test_partial_duplicate_malformed_and_reordered_frames_remain_unknown(self):
        for rows, error in (([record(0), record(0)], "duplicate-record"),
                            ([record(1), record(0)], "record-order"),
                            ([record(0).replace(b"UP1", b"UP9")], "malformed-record"),
                            ([record(0)[:-1]], "truncated-record")):
            wire = Wire([BOOT + READY, *rows], reply=False)
            result = observe(wire)
            self.assertIn(error, result["protocol_errors"]); self.assertFalse(result["records_complete"])
            self.assertEqual(len(wire.writes), 1)

    def test_bad_record_before_ready_prevents_stimulus(self):
        wire = Wire([BOOT + record(0).replace(b"UP1", b"UP2") + READY])
        result = observe(wire)
        self.assertEqual(wire.writes, []); self.assertIn("malformed-record", result["protocol_errors"])

    def test_duplicate_receipt_is_unknown_without_second_input(self):
        wire = Wire([BOOT + READY, f"\nK230_RDINIT_RX {TOKEN}\n".encode()])
        result = observe(wire)
        self.assertIn("duplicate-receipt", result["protocol_errors"])
        self.assertFalse(result["receipt_observed"]); self.assertEqual(len(wire.writes), 1)

    def test_transport_unknown_preserves_attempt_count_and_never_retries(self):
        class WriteFailure(Wire):
            def write(self, data):
                self.writes.append(data)
                raise OSError("fixture disconnect")
        wire = WriteFailure([BOOT + READY])
        result = observe(wire)
        self.assertEqual(result["stimulus_attempts"], 1)
        self.assertIn("stimulus-write-unknown", result["protocol_errors"])
        self.assertEqual(len(wire.writes), 1)
        wire = Wire([])
        wire.port.read = mock.Mock(side_effect=OSError("fixture disconnect"))
        result = observe(wire)
        self.assertIn("transport-read-unknown", result["protocol_errors"])
        self.assertEqual(wire.writes, [])

    def test_fresh_normal_return_independent_of_candidate_readiness_and_rollover(self):
        wire = Wire([b"U-Boot SPL 2022.10 recovery\n", *[b"noise\n" * 11000] * 3,
                     b"[    0.1] Linux version 6.6.36 normal\nnixos login: \nroot@nixos:~# "])
        result = observe(wire)
        self.assertTrue(result["normal_prompt_observed"]); self.assertFalse(result["candidate_banner"])
        self.assertEqual(wire.writes, [])
        for output in (NORMAL.split(b"U-Boot SPL", 1)[1], NORMAL.replace(b"6.6.36", b"7.3.0-rc5"),
                       NORMAL.replace(b"nixos login: ", b"unrelated")):
            self.assertFalse(observe(Wire([output]))["normal_prompt_observed"])

    def test_capture_overflow_stops_stimulus_but_preserves_later_recovery(self):
        wire = Wire([BOOT, *[b"x" * 65536] * 17, READY, NORMAL])
        result = observe(wire)
        self.assertIn("capture-byte-bound", result["protocol_errors"])
        self.assertTrue(result["normal_prompt_observed"]); self.assertEqual(wire.writes, [])

    def test_selector_cli_types_conflicts_and_default_compatibility(self):
        for flag, shell, mode in ((1, True, "minimal"), (None, True, "minimal"),
                                 (True, False, "minimal"), *[(True, True, m) for m in ("survey", "label", "root-mount")]):
            with mock.patch.object(trial, "prepare_trial") as prep, mock.patch.object(trial, "PrivateSession") as port:
                with self.assertRaises(ValueError): trial.run_trial(Path("m"), Path("l"), Path("r"), mode, uart_progress=flag, same_image_shell_pid1=shell)
                prep.assert_not_called(); port.assert_not_called()
        for args in (["--uart-progress"], ["--uart-progress", "--same-image-shell-pid1", "--debug-shutdown"]):
            with mock.patch.object(sys, "argv", ["trial", *args]), mock.patch.object(trial, "run_trial") as run, mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit): trial.main()
                run.assert_not_called()
        with mock.patch.object(sys, "argv", ["trial"]), mock.patch.object(trial, "run_trial", return_value=True) as run:
            self.assertEqual(trial.main(), 0); self.assertNotIn("uart_progress", run.call_args.kwargs)

    def test_exact_volatile_transform_preparation_transport_and_config_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            p = {"bundle": Path(directory), "system": fixtures.SYSTEM, "normal": fixtures.normal(), "helper_text": "pass\n"}
            (p["bundle"] / "bootargs.txt").write_text(fixtures.ORIGINAL)
            with mock.patch.object(trial, "inspect_shell_initrd", return_value={"bash": fixtures.BASH}), mock.patch.object(trial, "inspect_uart_progress_kernel", return_value={"config_sha256": "fixture"}):
                prepared = trial.prepare_uart_progress(p)
            expected = trial.shell_pid1_bootargs(fixtures.ORIGINAL, fixtures.SYSTEM) + " " + trial.UART_PROGRESS_FLAG
            self.assertEqual(prepared["bootargs"], expected)
            self.assertEqual(prepared["transport"], 'setenv bootargs "' + expected.removeprefix("bootargs=") + '"')
            self.assertEqual(expected.split().count(trial.UART_PROGRESS_FLAG), 1)
            self.assertIn(".is_symlink()", prepared["helper_text"])
            with self.assertRaises(ValueError): trial.shell_pid1_transport(expected, fixtures.SYSTEM)
            for bad in (expected + " ;saveenv", expected + " $x", expected + "\n", expected + " " + trial.UART_PROGRESS_FLAG):
                with self.assertRaises(ValueError): trial.shell_pid1_transport(bad, fixtures.SYSTEM, uart_progress=True)

    def test_same_derivation_realized_config_required_no_implicit_build(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial, "immutable_store_path", side_effect=lambda p, label: p):
            root = Path(directory); system = root / "system"; kernel = root / "kernel"; dev = root / "kernel-dev"
            system.mkdir(); kernel.mkdir(); dev.mkdir(); (kernel / "Image").write_bytes(b"fixture")
            (system / "kernel").symlink_to(kernel / "Image")
            config = dev / "lib/modules/7.3.0-rc5/build/.config"; config.parent.mkdir(parents=True)
            names = ("K230_UART_PROGRESS", "RISCV_SBI", "RISCV_TIMER", "SERIAL_8250", "SERIAL_8250_DW", "OF")
            content = "".join(f"CONFIG_{name}=y\n" for name in names)
            drv = "/nix/store/" + "a" * 32 + "-kernel.drv"
            for kind in ("valid", "missing", "disabled", "duplicate", "wrong-output", "unknown-deriver"):
                if kind == "missing": config.unlink(missing_ok=True)
                else: config.write_text(content.replace("CONFIG_K230_UART_PROGRESS=y", "CONFIG_K230_UART_PROGRESS=n") if kind == "disabled" else content + ("CONFIG_K230_UART_PROGRESS=y\n" if kind == "duplicate" else ""))
                results = ["unknown-deriver\n" if kind == "unknown-deriver" else drv + "\n", "\n".join([str(kernel) if kind != "wrong-output" else "/wrong", str(dev)]) + "\n"]
                with mock.patch.object(trial.subprocess, "check_output", side_effect=results) as query:
                    if kind == "valid": self.assertEqual(trial.inspect_uart_progress_kernel({"system": str(system)})["derivation"], drv)
                    else:
                        with self.assertRaises(ValueError): trial.inspect_uart_progress_kernel({"system": str(system)})
                    for call in query.call_args_list:
                        self.assertEqual(call.args[0][:2], ["nix-store", "--query"])
                        self.assertNotIn("--realise", call.args[0])

    def test_full_transport_and_passive_failure_preserve_result_without_more_input(self):
        class Session(fixtures.Session):
            def line(self, text, interrupt=True):
                super().line(text, interrupt)
                if text.startswith("bootm"):
                    self.chunks = [BOOT + READY, *[record(n) for n in range(6)]]
            def write(self, data):
                self.writes.append(data)  # deliberately no receipt
            def command(self, text, timeout):
                if text == "printenv bootargs":
                    self.writes.append(text.encode())
                    return (trial.shell_pid1_bootargs(fixtures.ORIGINAL, fixtures.SYSTEM) + " " + trial.UART_PROGRESS_FLAG + "\nK230# ").encode()
                return super().command(text, timeout)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); bundle = root / "bundle"; bundle.mkdir(); (bundle / "bootargs.txt").write_text(fixtures.ORIGINAL)
            p = {"system": fixtures.SYSTEM, "bundle": bundle, "normal": fixtures.normal(), "helper_text": "pass\n",
                 "manifest": {"files": {name: {"bytes": 123, "crc32": "abcdef01"} for name, _, _, _ in trial.LOADS}}}
            session = Session(); original = trial.observe_uart_progress
            def fast(active, token, args): return original(active, token, args, timeout=5, readiness_timeout=3, clock=Clock())
            with mock.patch.object(trial, "prepare_trial", return_value=p), mock.patch.object(trial, "inspect_shell_initrd", return_value={"bash": fixtures.BASH}), \
                    mock.patch.object(trial, "inspect_uart_progress_kernel", return_value={"config_sha256": "fixture"}), \
                    mock.patch.object(trial, "LOCK_PATH", root / "lock"), mock.patch.object(trial, "PrivateSession", return_value=session), \
                    mock.patch.object(trial, "observe_uart_progress", side_effect=fast), mock.patch.dict(sys.modules, {"serial": mock.Mock()}):
                self.assertFalse(trial.run_trial(root / "manifest", root / "log", root / "result", "minimal", bundle, root / "report", same_image_shell_pid1=True, uart_progress=True))
            result = json.loads((root / "result").read_text())
            self.assertEqual(result["status"], "recovery-required-observation-only")
            self.assertTrue(result["probe"]["records_complete"]); self.assertIsNone(result["normal_recovery"])
            self.assertFalse(result["reboot_requested"])
            boot_index = next(i for i, w in enumerate(session.writes) if w.startswith(b"bootm"))
            self.assertEqual(len(session.writes[boot_index + 1:]), 1)
            self.assertIn(b"K230_RDINIT_RX", session.writes[-1])
            self.assertNotIn(b"/bin/reboot", b"".join(session.writes))
            self.assertEqual(sum(w.startswith(b"ext4load") for w in session.writes), 5)
            self.assertEqual(sum(w.startswith(b"crc32") for w in session.writes), 5)

    def test_protected_return_requires_fresh_ids_services_hashes_and_complete_observation(self):
        p = {"normal": fixtures.normal(), "helper_text": "pass", "system": fixtures.SYSTEM,
             "bundle": Path("/nix/store/fixture"), "bootargs": "fixture", "uart_progress_kernel": {}}
        p["normal"]["trial_from_boot_id"] = fixtures.OLD
        good = observe(Wire([BOOT + READY, *[record(n) for n in range(6)], NORMAL]))
        for bad in (None, "id", "files", "services", "timeout", "incomplete"):
            session = fixtures.Session()
            state = session.run_state("postflight", TOKEN)
            if bad == "id": state["boot_id"] = fixtures.OLD
            if bad == "files": state["boot_files"] = {}
            if bad == "services": state["services"] = ["inactive"] * 3
            observation = dict(good)
            if bad == "incomplete": observation["records_complete"] = False
            with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial, "observe_uart_progress", return_value=observation), \
                    mock.patch.object(session, "run_state", side_effect=TimeoutError if bad == "timeout" else None, return_value=state):
                result_path = Path(directory) / "result"
                ok = trial.finish_uart_progress(session, TOKEN, p, {}, Path(directory) / "log", result_path)
                result = json.loads(result_path.read_text())
                self.assertEqual(ok, bad is None)
                if bad == "incomplete": self.assertEqual(result["status"], "recovery-verified-diagnostic-incomplete")
                elif bad: self.assertIsNone(result["normal_recovery"])
                self.assertEqual(session.writes, [])


if __name__ == "__main__": unittest.main()

"""Host fixtures only: fixed bytes, real pump, artifact gates, no UART/build."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("progress_fixtures", ROOT / "tests/test_mainline_uart_progress_controller.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
trial = old.trial
ARGS = old.ARGS + " " + trial.UART_PROGRESS_BREADCRUMBS_FLAG
CMDLINE = ("[    0.2] Kernel command line: " + ARGS.removeprefix("bootargs=") + "\n").encode()
BOOT = old.BANNER + CMDLINE
ENTRY, WAKE = (b"\n" + line for line in trial.UART_PROGRESS_BREADCRUMBS)


def observe(wire):
    return trial.observe_uart_progress(wire, old.TOKEN, ARGS, timeout=5, readiness_timeout=3,
                                       clock=old.Clock(), uart_progress_breadcrumbs=True)


class BreadcrumbControllerTests(unittest.TestCase):
    def test_exact_fixed_bytes_reject_alternate_echo_inserted_and_truncated(self):
        self.assertEqual(trial.uart_progress_breadcrumb(ENTRY[1:]), "worker-entry")
        self.assertEqual(trial.uart_progress_breadcrumb(WAKE[1:]), "first-post-sleep")
        for bad in (ENTRY, ENTRY[1:-1], ENTRY[1:] + WAKE[1:], ENTRY[1:].replace(b"UPB1", b"UPB2"),
                    ENTRY[1:].replace(b"entry", b"other"), ENTRY[1:].replace(b"\n", b" extra=1\n"),
                    b"printf '" + ENTRY[1:] + b"'", ENTRY[1:].replace(b"point=", b"[1.0] point=")):
            with self.subTest(bad=bad): self.assertIsNone(trial.uart_progress_breadcrumb(bad))

    def test_split_and_prebanner_breadcrumbs_retained_only_after_matching_args(self):
        wire = old.Wire([ENTRY[:7], ENTRY[7:], BOOT[:35], BOOT[35:] + old.READY,
                         WAKE, *[old.record(n) for n in range(6)]])
        result = observe(wire)
        self.assertTrue(result["breadcrumbs_complete"]); self.assertTrue(result["records_complete"])
        self.assertTrue(result["receipt_observed"]); self.assertEqual(len(wire.writes), 1)
        self.assertFalse(result["breadcrumbs"][0]["observed_after_stimulus"])
        self.assertTrue(result["breadcrumbs"][1]["observed_after_stimulus"])

    def test_unqualified_missing_wrong_duplicate_or_stale_args_never_trust_records(self):
        for boot in (b"", old.BANNER, old.BANNER + old.CMDLINE,
                     old.BANNER + CMDLINE + CMDLINE, old.BANNER.replace(b"7.3.0-rc5", b"6.6.36") + CMDLINE):
            wire = old.Wire([ENTRY, WAKE, boot + old.READY])
            result = observe(wire)
            self.assertEqual(wire.writes, []); self.assertEqual(result["breadcrumbs"], [])
            self.assertFalse(result["breadcrumbs_complete"])
        wire = old.Wire([BOOT + old.READY])
        wire.buffer = ENTRY + WAKE + BOOT + old.READY
        result = observe(wire)
        self.assertEqual(result["breadcrumbs"], [])  # stale capped buffer is not capture

    def test_prompt_followed_by_breadcrumb_same_read_allows_only_one_stimulus(self):
        wire = old.Wire([BOOT + old.READY + ENTRY + WAKE, *[old.record(n) for n in range(6)]])
        result = observe(wire)
        self.assertTrue(result["readiness_observed"]); self.assertTrue(result["breadcrumbs_complete"])
        self.assertEqual(wire.writes, [(trial.reception_command(old.TOKEN) + "\r").encode()])

    def test_breadcrumbs_never_authorize_stimulus_without_fresh_init_prompt(self):
        for ready in (b"", old.READY.replace(b"sh-5.3# ", b"> "), b"sh-5.3# "):
            wire = old.Wire([BOOT, ENTRY, WAKE, ready])
            result = observe(wire)
            self.assertTrue(result["breadcrumbs_complete"]); self.assertEqual(wire.writes, [])

    def test_duplicate_reorder_unknown_echo_and_interleaving_fail_without_input(self):
        for rows, error in ((ENTRY + ENTRY, "duplicate-breadcrumb"), (WAKE + ENTRY, "breadcrumb-order"),
                            (ENTRY.replace(b"UPB1", b"UPB2"), "malformed-breadcrumb"),
                            (ENTRY.replace(b"point=", b"point=[1.2] kernel\n"), "malformed-breadcrumb"),
                            (b"printf '" + ENTRY[1:] + b"'\n", "malformed-breadcrumb")):
            wire = old.Wire([BOOT + rows + old.READY])
            result = observe(wire)
            self.assertIn(error, result["protocol_errors"]); self.assertFalse(result["breadcrumbs_complete"])
            self.assertEqual(wire.writes, [])

    def test_truncated_or_late_duplicate_preserves_single_attempt_and_partial_facts(self):
        for rows, error in ((ENTRY + ENTRY, "duplicate-breadcrumb"), (ENTRY[:-1], "truncated-breadcrumb")):
            wire = old.Wire([BOOT + old.READY, rows], reply=False)
            result = observe(wire)
            self.assertIn(error, result["protocol_errors"]); self.assertEqual(len(wire.writes), 1)
            self.assertFalse(result["reboot_requested"])

    def test_post_sleep_without_entry_is_incomplete_not_a_causal_failure(self):
        result = observe(old.Wire([BOOT + old.READY, WAKE], reply=False))
        self.assertEqual(result["breadcrumbs"], [{"point": "first-post-sleep", "observed_after_stimulus": True}])
        self.assertFalse(result["breadcrumbs_complete"]); self.assertEqual(result["protocol_errors"], [])
        self.assertFalse(result["receipt_observed"]); self.assertFalse(result["reboot_requested"])

    def test_breadcrumb_after_numeric_sample_cannot_be_complete_sequence(self):
        wire = old.Wire([BOOT + old.READY, old.record(0), ENTRY, WAKE])
        result = observe(wire)
        self.assertIn("breadcrumb-after-sample", result["protocol_errors"])
        self.assertFalse(result["breadcrumbs_complete"]); self.assertEqual(len(wire.writes), 1)

    def test_missing_markers_keep_numeric_coverage_distinct_and_old_mode_unchanged(self):
        result = observe(old.Wire([BOOT + old.READY, *[old.record(n) for n in range(6)]]))
        self.assertTrue(result["records_complete"]); self.assertFalse(result["breadcrumbs_complete"])
        old_result = old.observe(old.Wire([old.BOOT + old.READY, *[old.record(n) for n in range(6)]]))
        self.assertTrue(old_result["records_complete"]); self.assertNotIn("breadcrumbs", old_result)

    def test_independent_normal_return_does_not_make_missing_breadcrumbs_pass(self):
        result = observe(old.Wire([old.NORMAL]))
        self.assertTrue(result["normal_prompt_observed"]); self.assertFalse(result["breadcrumbs_complete"])
        self.assertEqual(result["stimulus_attempts"], 0)

    def test_selector_types_cli_and_legacy_default_compatibility(self):
        for flag, reporter, shell, mode in ((1, True, True, "minimal"), (None, True, True, "minimal"),
                                          (True, False, True, "minimal"), (True, True, False, "minimal"),
                                          *[(True, True, True, m) for m in ("label", "survey", "root-mount")]):
            with mock.patch.object(trial, "prepare_trial") as prep, mock.patch.object(trial, "PrivateSession") as port:
                with self.assertRaises(ValueError):
                    trial.run_trial(Path("m"), Path("l"), Path("r"), mode, same_image_shell_pid1=shell,
                                    uart_progress=reporter, uart_progress_breadcrumbs=flag)
                prep.assert_not_called(); port.assert_not_called()
        with mock.patch.object(sys, "argv", ["trial", "--uart-progress-breadcrumbs"]), mock.patch.object(trial, "run_trial") as run, mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit): trial.main()
            run.assert_not_called()
        for flags, enabled in (([], False), (["--same-image-shell-pid1", "--uart-progress", "--uart-progress-breadcrumbs"], True)):
            with mock.patch.object(sys, "argv", ["trial", *flags]), mock.patch.object(trial, "run_trial", return_value=True) as run:
                self.assertEqual(trial.main(), 0)
                self.assertEqual(run.call_args.kwargs.get("uart_progress_breadcrumbs", False), enabled)

    def test_qualified_full_literal_only_adds_one_breadcrumb_token(self):
        command = trial.shell_pid1_transport(ARGS, old.fixtures.SYSTEM, uart_progress=True, uart_progress_breadcrumbs=True)
        self.assertEqual(command, 'setenv bootargs "' + ARGS.removeprefix("bootargs=") + '"')
        self.assertEqual(ARGS.split(), old.ARGS.split() + [trial.UART_PROGRESS_BREADCRUMBS_FLAG])
        self.assertLess(len(command), 512); self.assertNotIn("${", command); self.assertNotIn("saveenv", command)
        for args in (ARGS + " " + trial.UART_PROGRESS_BREADCRUMBS_FLAG, ARGS + "\n", ARGS + " ;saveenv", ARGS.replace("=1", "=0")):
            with self.assertRaises(ValueError): trial.shell_pid1_transport(args, old.fixtures.SYSTEM, uart_progress=True, uart_progress_breadcrumbs=True)

    def artifact_fixture(self, root):
        source = root / "source"; (source / "drivers/soc/canaan").mkdir(parents=True)
        worker = source / "drivers/soc/canaan/k230-uart-progress.c"; worker.write_bytes(b"reviewed worker fixture")
        kernel = root / "kernel"; kernel.mkdir()
        image = kernel / "Image"
        image.write_bytes(b"prefix" + ENTRY + b"\0" + WAKE + b"\0k230.uart_progress_breadcrumbs=\0")
        drv = "/nix/store/" + "a" * 32 + "-kernel.drv"
        p = {"uart_progress_kernel": {"kernel": str(kernel), "derivation": drv, "config": "fixture"}}
        return p, source, worker, image

    def test_same_selected_derivation_source_hash_and_compiled_marker_proof(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial, "immutable_store_path", side_effect=lambda p, label: p):
            p, source, worker, image = self.artifact_fixture(Path(directory))
            digest = hashlib.sha256(worker.read_bytes()).hexdigest(); drv = p["uart_progress_kernel"]["derivation"]
            for schema in ("legacy", "current"):
                desc = {drv: {"env": {"src": str(source)}}} if schema == "legacy" else {
                    "version": 4, "derivations": {Path(drv).name: {"structuredAttrs": {"src": str(source)}}}}
                with mock.patch.object(trial, "UART_BREADCRUMB_SOURCE_SHA256", digest), mock.patch.object(trial.subprocess, "check_output", return_value=json.dumps(desc)) as query:
                    proof = trial.inspect_uart_breadcrumb_kernel(p)
                    self.assertEqual(proof["source"], str(source)); self.assertEqual(proof["worker_sha256"], digest)
                    self.assertEqual(len(proof["marker_offsets"]), 2)
                    self.assertIn("--offline", query.call_args.args[0]); self.assertEqual(query.call_args.args[0][-1], drv)
                    self.assertNotIn("build", query.call_args.args[0])

    def test_legacy_config_y_wrong_source_or_unlinked_marker_image_reject(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(trial, "immutable_store_path", side_effect=lambda p, label: p):
            p, source, worker, image = self.artifact_fixture(Path(directory))
            digest = hashlib.sha256(worker.read_bytes()).hexdigest(); good = image.read_bytes()
            drv = p["uart_progress_kernel"]["derivation"]
            desc = {drv: {"env": {"src": str(source)}}}
            for failure in ("old-source", "missing-source", "old-image", "duplicate", "missing-gate", "wrong-derivation", "unknown-schema"):
                worker.write_bytes(b"legacy worker" if failure == "old-source" else b"reviewed worker fixture")
                image.write_bytes(b"legacy Image" if failure == "old-image" else good + ENTRY + b"\0" if failure == "duplicate" else good.replace(b"k230.uart_progress_breadcrumbs=\0", b"wrong") if failure == "missing-gate" else good)
                description = {} if failure == "wrong-derivation" else {drv: {"env": {}}} if failure == "missing-source" else {"version": 99, "derivations": {}} if failure == "unknown-schema" else desc
                with mock.patch.object(trial, "UART_BREADCRUMB_SOURCE_SHA256", digest), mock.patch.object(trial.subprocess, "check_output", return_value=json.dumps(description)), self.assertRaises(ValueError):
                    trial.inspect_uart_breadcrumb_kernel(p)

    def test_variant_qualification_failure_prevents_serial_even_with_reporter_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "bootargs.txt").write_text(old.fixtures.ORIGINAL)
            p = {"bundle": root, "system": old.fixtures.SYSTEM, "normal": old.fixtures.normal(), "helper_text": "pass"}
            with mock.patch.object(trial, "prepare_trial", return_value=p), mock.patch.object(trial, "inspect_shell_initrd", return_value={"bash": old.fixtures.BASH}), \
                    mock.patch.object(trial, "inspect_uart_progress_kernel", return_value={"config_sha256": "CONFIG=y fixture"}), \
                    mock.patch.object(trial, "inspect_uart_breadcrumb_kernel", side_effect=ValueError("legacy source")), mock.patch.object(trial, "PrivateSession") as port:
                with self.assertRaises(ValueError):
                    trial.run_trial(root / "m", root / "l", root / "r", "minimal", same_image_shell_pid1=True, uart_progress=True, uart_progress_breadcrumbs=True)
                port.assert_not_called(); self.assertFalse((root / "l").exists())

    def test_full_wire_transport_single_stimulus_then_passive_result(self):
        class Session(old.fixtures.Session):
            def line(self, text, interrupt=True):
                super().line(text, interrupt)
                if text.startswith("bootm"):
                    self.chunks = [ENTRY, BOOT + old.READY, WAKE, *[old.record(n) for n in range(6)]]
            def write(self, data): self.writes.append(data)  # no receipt; no retry allowed
            def command(self, text, timeout):
                if text == "printenv bootargs":
                    self.writes.append(text.encode()); return (ARGS + "\nK230# ").encode()
                return super().command(text, timeout)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); bundle = root / "bundle"; bundle.mkdir(); (bundle / "bootargs.txt").write_text(old.fixtures.ORIGINAL)
            p = {"bundle": bundle, "system": old.fixtures.SYSTEM, "normal": old.fixtures.normal(), "helper_text": "pass\n",
                 "manifest": {"files": {name: {"bytes": 123, "crc32": "abcdef01"} for name, _, _, _ in trial.LOADS}}}
            s = Session(); original = trial.observe_uart_progress
            def fast(active, token, args, **kwargs): return original(active, token, args, timeout=5, readiness_timeout=3, clock=old.Clock(), **kwargs)
            with mock.patch.object(trial, "prepare_trial", return_value=p), mock.patch.object(trial, "inspect_shell_initrd", return_value={"bash": old.fixtures.BASH}), \
                    mock.patch.object(trial, "inspect_uart_progress_kernel", return_value={"config_sha256": "fixture"}), mock.patch.object(trial, "inspect_uart_breadcrumb_kernel", return_value={"worker_sha256": "fixture"}), \
                    mock.patch.object(trial, "LOCK_PATH", root / "lock"), mock.patch.object(trial, "PrivateSession", return_value=s), mock.patch.object(trial, "observe_uart_progress", side_effect=fast), \
                    mock.patch.dict(sys.modules, {"serial": mock.Mock()}):
                self.assertFalse(trial.run_trial(root / "m", root / "l", root / "r", "minimal", bundle, root / "n", same_image_shell_pid1=True, uart_progress=True, uart_progress_breadcrumbs=True))
            result = json.loads((root / "r").read_text())
            self.assertTrue(result["uart_progress_breadcrumbs"]); self.assertTrue(result["probe"]["breadcrumbs_complete"])
            self.assertFalse(result["reboot_requested"]); self.assertIsNone(result["normal_recovery"])
            boot = next(i for i, w in enumerate(s.writes) if w.startswith(b"bootm"))
            self.assertEqual(len(s.writes[boot + 1:]), 1); self.assertIn(b"K230_RDINIT_RX", s.writes[-1])
            self.assertIn(trial.shell_pid1_transport(ARGS, old.fixtures.SYSTEM, uart_progress=True, uart_progress_breadcrumbs=True).encode(), s.writes)
            self.assertEqual(sum(w.startswith(b"ext4load") for w in s.writes), 5)
            self.assertEqual(sum(w.startswith(b"crc32") for w in s.writes), 5)


if __name__ == "__main__": unittest.main()

"""Focused tests for the plain-mode --ignore-unused-resources controller flag.

Fixtures and session/flow helpers are reused from test_mainline_drm_system_trial.py
rather than duplicated here.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

_BASE_SPEC = importlib.util.spec_from_file_location(
    "mainline_system_trial_base", Path(__file__).with_name("test_mainline_drm_system_trial.py"))
base = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(base)

trial = base.trial
SYSTEM = base.SYSTEM
ARGS = base.ARGS
IGNORE_UNUSED_TOKENS = ("clk_ignore_unused", "pd_ignore_unused")


class IgnoreUnusedResourcesTests(unittest.TestCase):
    # -- diagnostic_controls / ordinary_bootargs: exact appended tokens --

    def test_diagnostic_controls_default_unchanged(self):
        self.assertEqual(trial.diagnostic_controls(), trial.CONTROLS)

    def test_diagnostic_controls_appends_exact_tokens_after_controls(self):
        controls = trial.diagnostic_controls(ignore_unused_resources=True)
        self.assertEqual(controls, trial.CONTROLS + IGNORE_UNUSED_TOKENS)
        self.assertEqual(controls[:len(trial.CONTROLS)], trial.CONTROLS)
        self.assertEqual(controls[len(trial.CONTROLS):], IGNORE_UNUSED_TOKENS)

    def test_ordinary_bootargs_default_unchanged(self):
        self.assertEqual(trial.ordinary_bootargs(ARGS, SYSTEM), ARGS.rstrip() + " " + " ".join(trial.CONTROLS))

    def test_ordinary_bootargs_appends_exact_tokens(self):
        result = trial.ordinary_bootargs(ARGS, SYSTEM, ignore_unused_resources=True)
        self.assertEqual(result, ARGS.rstrip() + " " + " ".join(trial.CONTROLS + IGNORE_UNUSED_TOKENS))
        self.assertEqual(result, ARGS.rstrip() + " " + " ".join(trial.CONTROLS) + " clk_ignore_unused pd_ignore_unused")

    # -- rejection when combined with any incompatible selector --

    def test_rejects_combination_with_each_incompatible_selector(self):
        combos = (
            {"wait_initramfs_in_initcall": True},
            {"wait_initramfs_in_initcall": True, "without_boot_markers": True},
            {"wait_initramfs_in_initcall": True, "without_boot_markers": True, "initrd_debug_logging": True},
            {"wait_initramfs_in_initcall": True, "without_boot_markers": True, "initrd_info_logging": True},
            {"wait_initramfs_in_initcall": True, "without_boot_markers": True, "initrd_info_kmsg_logging": True},
            {"wait_initramfs_in_initcall": True, "without_boot_markers": True, "init_exec_return": True},
            {"wait_initramfs_in_initcall": True, "without_boot_markers": True, "init_exec_return": True, "init_exec_transition": True},
        )
        for kwargs in combos:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    trial.diagnostic_controls(ignore_unused_resources=True, **kwargs)
                with self.assertRaises(ValueError):
                    trial.ordinary_bootargs(ARGS, SYSTEM, ignore_unused_resources=True, **kwargs)
                with self.assertRaises(ValueError):
                    trial.prepare(Path("/none"), Path("/none"), Path("/none"), ignore_unused_resources=True, **kwargs)

    def test_cli_rejects_each_incompatible_flag_before_any_serial(self):
        common = [sys.executable, str(Path(trial.__file__)), "begin", "--state", "/nonexistent/state",
                  "--log", "/nonexistent/log", "--result", "/nonexistent/result",
                  "--bundle", "/none", "--manifest", "/none", "--normal-report", "/none",
                  "--ignore-unused-resources"]
        combos = (
            ["--wait-initramfs-in-initcall"],
            ["--wait-initramfs-in-initcall", "--without-boot-markers"],
            ["--wait-initramfs-in-initcall", "--without-boot-markers", "--initrd-debug-logging"],
            ["--wait-initramfs-in-initcall", "--without-boot-markers", "--initrd-info-logging"],
            ["--wait-initramfs-in-initcall", "--without-boot-markers", "--initrd-info-kmsg-logging"],
            ["--wait-initramfs-in-initcall", "--without-boot-markers", "--init-exec-return"],
            ["--wait-initramfs-in-initcall", "--without-boot-markers", "--init-exec-return", "--init-exec-transition"],
        )
        for extra in combos:
            with self.subTest(extra=extra):
                result = subprocess.run(common + extra, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn(b"--ignore-unused-resources", result.stderr)

    def test_cli_ignore_unused_resources_is_begin_only_before_any_serial(self):
        for phase in ("touch", "finish"):
            cmd = [sys.executable, str(Path(trial.__file__)), phase, "--state", "/nonexistent/state",
                   "--log", "/nonexistent/log", "--result", "/nonexistent/result", "--ignore-unused-resources"]
            result = subprocess.run(cmd, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"--ignore-unused-resources", result.stderr)
            self.assertIn(b"begin-only", result.stderr)

    # -- rejection of inherited tokens from the BUNDLE's own bootargs.txt --

    def test_rejects_inherited_pd_ignore_unused_and_keeps_clk_rejection(self):
        for extra in ("pd_ignore_unused", "clk_ignore_unused"):
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    trial.ordinary_bootargs(ARGS.rstrip() + " " + extra + "\n", SYSTEM)
                with self.assertRaises(ValueError):
                    trial.ordinary_bootargs(ARGS.rstrip() + " " + extra + "\n", SYSTEM, ignore_unused_resources=True)

    # -- volatile bootargs command appends tokens / rejects mismatch --

    def test_volatile_bootargs_command_appends_tokens_after_controls(self):
        p = base.prepared()
        p["bootargs"] = trial.ordinary_bootargs(ARGS, SYSTEM, ignore_unused_resources=True)
        p["diagnostic_controls"] = trial.diagnostic_controls(ignore_unused_resources=True)
        p["ignore_unused_resources"] = True
        command = trial.volatile_bootargs_command(p)
        self.assertEqual(command, 'setenv bootargs "${bootargs} ' + " ".join(trial.CONTROLS + IGNORE_UNUSED_TOKENS) + '"')

    def test_volatile_bootargs_command_rejects_mismatched_controls_or_flag(self):
        p = base.prepared()
        p["bootargs"] = trial.ordinary_bootargs(ARGS, SYSTEM, ignore_unused_resources=True)
        p["diagnostic_controls"] = trial.diagnostic_controls(ignore_unused_resources=True)
        p["ignore_unused_resources"] = True
        trial.volatile_bootargs_command(p)  # sanity: valid combination succeeds

        stale_controls = dict(p); stale_controls["diagnostic_controls"] = trial.CONTROLS
        with self.assertRaises(ValueError):
            trial.volatile_bootargs_command(stale_controls)

        flag_cleared = dict(p); flag_cleared["ignore_unused_resources"] = False
        with self.assertRaises(ValueError):
            trial.volatile_bootargs_command(flag_cleared)

        untyped = dict(p); untyped["ignore_unused_resources"] = 1
        with self.assertRaises(ValueError):
            trial.volatile_bootargs_command(untyped)

    def test_volatile_bootargs_command_default_path_unaffected(self):
        p = base.prepared()
        self.assertEqual(trial.volatile_bootargs_command(p),
                         'setenv bootargs "${bootargs} ' + " ".join(trial.CONTROLS) + '"')

    # -- received kernel command line / expected controls verification --

    def test_received_args_validation_accepts_exact_tokens_when_set(self):
        p = base.prepared()
        p["bootargs"] = trial.ordinary_bootargs(ARGS, SYSTEM, ignore_unused_resources=True)
        value = base.facts()["bootargs"].copy()
        value["cmdline"] = p["bootargs"].removeprefix("bootargs=")
        trial.validate_stage("bootargs", value, p, p["normal"])

    def test_received_args_validation_rejects_missing_or_extra_tokens(self):
        p = base.prepared()
        p["bootargs"] = trial.ordinary_bootargs(ARGS, SYSTEM, ignore_unused_resources=True)
        value = base.facts()["bootargs"].copy()
        value["cmdline"] = p["bootargs"].removeprefix("bootargs=")
        for missing in IGNORE_UNUSED_TOKENS:
            bad = value.copy()
            bad["cmdline"] = " ".join(t for t in value["cmdline"].split() if t != missing)
            with self.subTest(missing=missing), self.assertRaises(trial.Unknown):
                trial.validate_stage("bootargs", bad, p, p["normal"])

        # A plain-mode candidate must reject receiving the tokens unexpectedly.
        plain_p = base.prepared()
        plain_value = base.facts()["bootargs"].copy()
        plain_value["cmdline"] = plain_p["bootargs"].removeprefix("bootargs=") + " clk_ignore_unused pd_ignore_unused"
        with self.assertRaises(trial.Unknown):
            trial.validate_stage("bootargs", plain_value, plain_p, plain_p["normal"])

    # -- begin path threading: prepare kwargs, saved state, result fields --

    def test_begin_threads_flag_into_prepare_state_and_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); root.chmod(0o700)
            prepared = base.prepared()
            prepared["bootargs"] = trial.ordinary_bootargs(ARGS, SYSTEM, ignore_unused_resources=True)
            prepared["diagnostic_controls"] = trial.diagnostic_controls(ignore_unused_resources=True)
            prepared["ignore_unused_resources"] = True
            values = base.facts()
            values["bootargs"]["cmdline"] = prepared["bootargs"].removeprefix("bootargs=")

            class IgnoreUnusedSession(base.FlowSession):
                def command(self, command, timeout):
                    if command == "printenv bootargs":
                        self.writes.append(command.encode())
                        return (prepared["bootargs"] + "\nK230# ").encode()
                    return super().command(command, timeout)

            args = SimpleNamespace(phase="begin", bundle=Path("/nix/store/bundle"), manifest=root / "manifest",
                                   normal_report=root / "normal-report", state=root / "state.json",
                                   log=root / "begin.log", result=root / "begin.json", real_touch=False,
                                   ignore_unused_resources=True)
            base.FlowSession.instances = []; base.FlowSession.values = values; base.FlowSession.fail_stage = None
            with mock.patch.dict(sys.modules, {"serial": SimpleNamespace()}), \
                 mock.patch.object(trial, "prepare", return_value=prepared) as prepare_call, \
                 mock.patch.object(trial.rd, "PrivateSession", IgnoreUnusedSession), \
                 mock.patch.object(trial.rd, "LOCK_PATH", root / "lock"):
                self.assertTrue(trial.run(args))
                self.assertTrue(prepare_call.call_args.kwargs["ignore_unused_resources"])
                self.assertTrue(json.loads(args.state.read_text())["ignore_unused_resources"])
                self.assertTrue(json.loads(args.result.read_text())["ignore_unused_resources"])

                args.phase = "finish"; args.log = root / "finish.log"; args.result = root / "finish.json"
                args.ignore_unused_resources = False  # resumed phases rely on saved state, not CLI reselection
                self.assertTrue(trial.run(args))
                self.assertTrue(prepare_call.call_args.kwargs["ignore_unused_resources"])
                self.assertTrue(json.loads(args.result.read_text())["ignore_unused_resources"])
                self.assertEqual(json.loads(args.result.read_text())["status"], "normal-recovery-verified")
            base.FlowSession.values = None

    def test_default_run_result_records_flag_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); root.chmod(0o700)
            args = SimpleNamespace(phase="begin", bundle=Path("/nix/store/bundle"), manifest=root / "manifest",
                                   normal_report=root / "normal-report", state=root / "state.json",
                                   log=root / "begin.log", result=root / "begin.json", real_touch=False)
            base.FlowSession.instances = []; base.FlowSession.values = None; base.FlowSession.fail_stage = None
            with mock.patch.dict(sys.modules, {"serial": SimpleNamespace()}), \
                 mock.patch.object(trial, "prepare", return_value=base.prepared()), \
                 mock.patch.object(trial.rd, "PrivateSession", base.FlowSession), \
                 mock.patch.object(trial.rd, "LOCK_PATH", root / "lock"):
                self.assertTrue(trial.run(args))
            self.assertFalse(json.loads(args.result.read_text())["ignore_unused_resources"])
            self.assertFalse(json.loads(args.state.read_text())["ignore_unused_resources"])


if __name__ == "__main__":
    unittest.main()

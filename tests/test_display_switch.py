#!/usr/bin/env python3
"""Boot-selector fault/recovery checks against temporary files, never /boot."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("display_switch", Path(__file__).resolve().parents[1] / "tools/display_switch.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DisplaySwitchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.boot = self.root / "boot"
        self.boot.mkdir()
        current = self.root / "system"
        current.mkdir()
        (self.boot / "bootargs.txt").write_text(f"bootargs=console=ttyS0 init={current}/init\n")
        (self.boot / "force_dtb").write_text(module.PANEL)
        (self.boot / "Image").write_bytes(b"kernel")
        (self.root / "kernel").write_bytes(b"kernel")
        for name in ("panel", "hdmi"):
            (self.root / name).write_bytes(bytes.fromhex("d00dfeed") + name.encode())
        (self.boot / module.PANEL).write_bytes((self.root / "panel").read_bytes())
        drm = self.root / "drm"
        (drm / "card1-DSI-1").mkdir(parents=True)
        (drm / "card1-DSI-1/status").write_text("connected\n")
        self.calls = []
        self.fail = None
        self.controller = module.DisplaySwitch(
            {"kernel": str(self.root / "kernel"), "panel": str(self.root / "panel"),
             "hdmi": str(self.root / "hdmi"), "mount": "mount", "fdtput": "fdtput", "systemctl": "systemctl"},
            self.boot, current, drm, self.root / "lock", self.run_command)

    def run_command(self, argv, **kwargs):
        self.calls.append(argv)
        if self.fail == argv[0]:
            raise subprocess.CalledProcessError(1, argv)
        if argv[0] == "systemctl":
            # These checks happen at the reboot boundary, not after a test
            # helper has restored the panel behind our back.
            self.assertEqual((self.boot / "force_dtb").read_text(), module.HDMI)
            self.assertEqual(json.loads((self.boot / module.MARKER).read_text()), {"schema": 1, "panel": module.PANEL})
            self.assertEqual((self.boot / module.PANEL).read_bytes(), (self.root / "panel").read_bytes())
            self.assertEqual(self.calls[-2][2], "remount,ro")
        return subprocess.CompletedProcess(argv, 0)

    def test_hdmi_then_early_restore_and_repeated_restore(self):
        self.assertEqual(self.controller.status(), {"state": "action", "active": "AMOLED", "next_boot": "AMOLED"})
        self.controller.mutate("hdmi")
        self.assertEqual(self.controller.status()["next_boot"], "HDMI")
        self.assertEqual(self.controller.status()["state"], "read-only")
        self.assertTrue(self.controller.mutate("restore"))
        self.assertEqual((self.boot / "force_dtb").read_text(), module.PANEL)
        self.assertFalse((self.boot / module.MARKER).exists())
        self.assertFalse(self.controller.mutate("restore"))
        self.assertEqual(self.controller.status()["state"], "action")

    def test_restore_does_not_need_running_hdmi_or_matching_system(self):
        self.controller.mutate("hdmi")
        (self.boot / "bootargs.txt").unlink()
        (self.boot / "Image").unlink()
        self.controller.drm = self.root / "no-drm"
        self.assertTrue(self.controller.mutate("restore"))
        self.assertEqual((self.boot / "force_dtb").read_text(), module.PANEL)

    def test_interruption_after_marker_or_after_selector_recovers(self):
        for selector in (module.PANEL, module.HDMI):
            (self.boot / module.MARKER).write_text(json.dumps({"schema": 1, "panel": module.PANEL}))
            (self.boot / "force_dtb").write_text(selector)
            self.assertTrue(self.controller.mutate("restore"))
            self.assertEqual((self.boot / "force_dtb").read_text(), module.PANEL)

    def test_reboot_denial_rolls_back(self):
        self.fail = "systemctl"
        with self.assertRaises(subprocess.CalledProcessError):
            self.controller.mutate("hdmi")
        self.assertEqual((self.boot / "force_dtb").read_text(), module.PANEL)
        self.assertFalse((self.boot / module.MARKER).exists())

    def test_unmatched_kernel_or_panel_cannot_queue(self):
        for filename in ("Image", module.PANEL):
            original = (self.boot / filename).read_bytes()
            (self.boot / filename).write_bytes(b"unmatched")
            with self.assertRaises(ValueError):
                self.controller.mutate("hdmi")
            self.assertFalse((self.boot / module.MARKER).exists())
            self.assertEqual((self.boot / "force_dtb").read_text(), module.PANEL)
            (self.boot / filename).write_bytes(original)

    def test_unmatched_system_and_unknown_selector_are_unavailable(self):
        (self.boot / "bootargs.txt").write_text("bootargs=init=/nix/store/other/init\n")
        self.assertEqual(self.controller.status()["state"], "unavailable")
        with self.assertRaises(ValueError):
            self.controller.mutate("hdmi")
        (self.boot / "force_dtb").write_text("other.dtb")
        self.assertEqual(self.controller.status()["state"], "unavailable")
        self.assertEqual(self.calls, [])

    def test_missing_monitor_state_disables_action(self):
        self.controller.drm = self.root / "missing"
        self.assertEqual(self.controller.status()["state"], "read-only")
        with self.assertRaises(ValueError):
            self.controller.mutate("hdmi")

    def test_dtb_or_mount_failure_precedes_selection_write(self):
        for executable in ("fdtput", "mount"):
            self.fail = executable
            with self.assertRaises(subprocess.CalledProcessError):
                self.controller.mutate("hdmi")
            self.assertEqual((self.boot / "force_dtb").read_text(), module.PANEL)
            self.assertFalse((self.boot / module.MARKER).exists())

    def test_payload_write_failure_restores_panel(self):
        replace = self.controller.replace
        def failing(name, data):
            if name == module.HDMI:
                raise OSError("injected disk failure")
            replace(name, data)
        with patch.object(self.controller, "replace", failing):
            with self.assertRaises(OSError):
                self.controller.mutate("hdmi")
        self.assertEqual((self.boot / "force_dtb").read_text(), module.PANEL)
        self.assertFalse((self.boot / module.MARKER).exists())

    def test_invalid_marker_or_missing_panel_is_not_consumed(self):
        marker = self.boot / module.MARKER
        marker.write_text(json.dumps({"schema": 1, "panel": "../../arbitrary"}))
        with self.assertRaises(ValueError):
            self.controller.mutate("restore")
        marker.write_text(json.dumps({"schema": 1, "panel": module.PANEL}))
        (self.boot / module.PANEL).unlink()
        with self.assertRaises(OSError):
            self.controller.mutate("restore")
        self.assertTrue(marker.exists())

    def test_symlink_payload_is_rejected_without_reboot(self):
        (self.boot / module.HDMI).symlink_to(self.root / "outside")
        with self.assertRaises(ValueError):
            self.controller.mutate("hdmi")
        self.assertEqual((self.boot / "force_dtb").read_text(), module.PANEL)
        self.assertFalse((self.root / "outside").exists())
        self.assertFalse(any(call[0] == "systemctl" for call in self.calls))


if __name__ == "__main__":
    unittest.main()

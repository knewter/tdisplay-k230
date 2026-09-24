#!/usr/bin/env python3
"""Host capability and action protocol checks; no panel or system power action."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("device_settings", ROOT / "tools/device_settings.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = []
        self.code = 0
        self.settings = module.Settings(self.root / "sys", self.root / "runtime", self.run_command)

    def run_command(self, argv, **kwargs):
        self.calls.append(argv)
        self.assertEqual(kwargs["timeout"], 3)
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
        return subprocess.CompletedProcess(argv, self.code)

    def write(self, path, value):
        file = self.root / "sys" / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(str(value))
        return file

    def test_capability_states(self):
        self.code = 1
        with patch.dict(os.environ, {}, clear=True):
            state = self.settings.status()["controls"]
        self.assertTrue(all(row["state"] == "unavailable" for row in state.values()))
        self.write("class/net/eth0/carrier", 1)
        self.assertEqual(self.settings.network()["value"], "link-up")
        self.assertNotIn("internet", json.dumps(self.settings.network()).lower())
        self.write("class/net/eth0/carrier", 0)
        self.assertEqual(self.settings.network()["value"], "disconnected")
        self.write("class/net/eth0/carrier", "invalid")
        self.assertEqual(self.settings.network()["state"], "unavailable")

    def test_no_battery_or_network_identifiers(self):
        self.write("class/net/private-interface/carrier", 1)
        self.write("class/power_supply/battery/capacity", 75)
        payload = json.dumps(self.settings.status())
        for forbidden in ("battery", "private-interface", "ssid", "address"):
            self.assertNotIn(forbidden, payload)

    def test_fresh_home(self):
        with patch.dict(os.environ, {"HOME": str(self.root / "does-not-exist"),
                                    "K230_SETTINGS_REDUCED_MOTION": "1"}, clear=True):
            self.assertTrue(self.settings.status()["controls"]["motion"]["value"])
        self.assertFalse((self.root / "does-not-exist").exists())

    def test_real_brightness_and_pending(self):
        self.write("class/backlight/panel/max_brightness", 200)
        self.write("class/backlight/panel/actual_brightness", 100)
        output = self.write("class/backlight/panel/brightness", 100)
        self.assertEqual(self.settings.brightness()["value"], 50)
        result = self.settings.change_brightness(75)
        self.assertEqual(result["state"], "pending")
        self.assertEqual(result["control"]["value"], 50)
        self.assertEqual(output.read_text(), "150")
        self.write("class/backlight/panel/actual_brightness", 150)
        self.assertEqual(self.settings.brightness()["value"], 75)
        with patch.object(module.os, "access", return_value=False):
            self.assertEqual(self.settings.brightness()["state"], "read-only")
            self.assertEqual(self.settings.change_brightness(90)["state"], "failed")
        self.assertEqual(output.read_text(), "150")
        self.write("class/backlight/other/max_brightness", 1)
        self.assertEqual(self.settings.brightness()["state"], "unavailable")

    def test_restart_cancel(self):
        result = self.settings.power("request", "reboot")
        self.assertEqual(result["state"], "confirmation")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.settings.power("cancel", result["token"])["state"], "cancelled")
        self.assertEqual(self.settings.power("confirm", result["token"])["state"], "failed")
        self.assertEqual(self.calls, [])

    def test_denial_consumes_confirmation(self):
        self.code = 1
        request = self.settings.power("request", "poweroff")
        result = self.settings.power("confirm", request["token"])
        self.assertEqual(result["error"], "action-denied")
        self.assertTrue(result["retry"])
        self.assertEqual(self.calls[0][-1], "poweroff")
        self.assertIn("-n", self.calls[0])
        self.settings.power("confirm", request["token"])
        self.assertEqual(len(self.calls), 1)

    def test_expired_and_replaced_confirmation(self):
        old = self.settings.power("request", "reboot")
        new = self.settings.power("request", "poweroff")
        self.assertEqual(self.settings.power("confirm", old["token"])["error"], "stale-confirmation")
        with patch.object(module.time, "monotonic", return_value=10**20):
            self.assertEqual(self.settings.power("confirm", new["token"])["error"], "expired-confirmation")
        self.assertEqual(self.calls, [])

    def test_safe_runtime_and_action_allowlist(self):
        self.assertEqual(self.settings.power("request", "shell")["state"], "failed")
        self.assertFalse(self.settings.runtime.exists())
        self.settings.runtime.mkdir(mode=0o755)
        self.assertEqual(self.settings.power("request", "reboot")["state"], "failed")
        self.assertEqual(self.calls, [])

    def test_timeout_is_failure_not_success(self):
        def timed_out(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 3)
        self.settings.run = timed_out
        request = self.settings.power("request", "reboot")
        self.assertEqual(self.settings.power("confirm", request["token"])["state"], "failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", default=[])
    args = parser.parse_args()
    groups = {
        "capability-states": ["test_capability_states", "test_real_brightness_and_pending"],
        "no-battery": ["test_no_battery_or_network_identifiers"],
        "fresh-home": ["test_fresh_home"],
        "restart-cancel": ["test_restart_cancel", "test_expired_and_replaced_confirmation"],
        "denial": ["test_denial_consumes_confirmation", "test_safe_runtime_and_action_allowlist", "test_timeout_is_failure_not_success"],
    }
    if any(case not in groups for case in args.case):
        parser.error("unknown or not-yet-implemented case (scroll/flick require real UI tests)")
    names = sorted({name for case in args.case for name in groups[case]})
    suite = (unittest.TestSuite(SettingsTests(name) for name in names) if args.case
             else unittest.defaultTestLoader.loadTestsFromTestCase(SettingsTests))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

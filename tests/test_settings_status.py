"""Native status conformance against the existing Python capability oracle."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("device_settings", ROOT / "tools/device_settings.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


class StatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="k230-status-build-")
        cls.binary = Path(cls.build.name) / "status-test"
        # Test-only root injection; the production executable always uses /sys.
        driver = Path(cls.build.name) / "driver.c"
        driver.write_text('#define main production_main\n#include "' +
                          str(ROOT / "nix/settings-status.c") +
                          '"\n#undef main\nint main(int argc, char **argv) {\n'
                          'if (argc == 1) return production_main();\n'
                          'if (!strcmp(argv[1], "--proc")) return !keyboard_running(argv[2], strtoumax(argv[3], NULL, 10));\n'
                          'return print_status(argv[1], atoi(argv[2]), argc > 3 ? argv[3] : NULL);\n}\n')
        subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-O2", "-Wall", "-Wextra",
                        "-Werror", str(driver), "-o", str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k230-status-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sysfs = self.root / "sys"

    def write(self, path, value):
        p = self.sysfs / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(value))
        return p

    def compare(self, keyboard=False, motion=None):
        def run(argv, **kwargs):
            self.assertEqual(argv[-3:], [str(os.getuid()), "-x", "wvkbd-mobintl"])
            return subprocess.CompletedProcess(argv, 0 if keyboard else 1)

        args = [str(self.binary), str(self.sysfs), str(int(keyboard))]
        if motion is not None:
            args.append(motion)
        native = json.loads(subprocess.check_output(args))
        with patch.dict(os.environ, {}, clear=True):
            if motion is not None:
                os.environ["K230_SETTINGS_REDUCED_MOTION"] = motion
            expected = oracle.Settings(self.sysfs, self.root / "runtime", run).status()
        self.assertEqual(native, expected)
        return native

    def panel(self, maximum=200, actual=100):
        self.write("class/backlight/panel/max_brightness", maximum)
        self.write("class/backlight/panel/actual_brightness", actual)
        return self.write("class/backlight/panel/brightness", actual)

    def test_absent_and_fresh_state_no_home_or_cache(self):
        self.compare()
        self.panel()
        self.write("class/net/eth0/carrier", 0)
        self.compare(True, "0")
        self.write("class/backlight/panel/actual_brightness", 150)
        self.write("class/net/eth0/carrier", 1)
        value = self.compare(False, "1")
        self.assertEqual(value["controls"]["brightness"]["value"], 75)
        self.assertEqual(value["controls"]["network"]["value"], "link-up")
        self.assertFalse((self.root / "runtime").exists())

    def test_carriers_mixed_unknown_loopback_and_limit(self):
        self.write("class/net/lo/carrier", 1)
        self.compare()
        for value in [0, 1, 2, "", "bad", "-1", " 1\n", "1\x00"]:
            with self.subTest(carrier=value):
                self.write("class/net/eth0/carrier", value)
                self.compare()
        self.write("class/net/eth0/carrier", 0)
        self.write("class/net/wlan0/carrier", "bad")
        self.compare()
        self.write("class/net/eth0/carrier", 1)
        self.compare()
        for i in range(65):
            self.write(f"class/net/a{i:02}/carrier", 0)
        self.compare()

    def test_brightness_rounding_integer_limits_and_malformed_values(self):
        self.panel()
        for maximum, actual in [(200, x) for x in range(201)] + [
            (9999999999, 9999999999), (9999999999, 4999999999),
            (0, 0), (1, 2), ("bad", 0), (200, "bad"), (200, ""),
            (200, "-1"), (200, "１２"), (200, " 100\n"),
            (200, "10000000000"), (200, "100\x00"),
        ]:
            with self.subTest(maximum=maximum, actual=actual):
                self.write("class/backlight/panel/max_brightness", maximum)
                self.write("class/backlight/panel/actual_brightness", actual)
                self.compare()

    def test_unique_backlight_writability_and_disappearance(self):
        output = self.panel()
        self.compare()
        output.unlink()  # access(W_OK) false even while actual/max remain readable.
        self.assertEqual(self.compare()["controls"]["brightness"]["state"], "read-only")
        self.write("class/backlight/second/max_brightness", 20)
        self.compare()
        self.write("class/backlight/panel/max_brightness", "")
        self.compare()

    def test_motion_and_keyboard_capabilities(self):
        for motion in [None, "", "0", "1", "false", "2"]:
            for keyboard in [False, True]:
                with self.subTest(motion=motion, keyboard=keyboard):
                    self.compare(keyboard, motion)

    def test_no_identifiers_or_unrelated_capabilities(self):
        self.write("class/net/private-interface/carrier", 1)
        self.write("class/power_supply/battery/capacity", 75)
        result = json.dumps(self.compare())
        for name in ["private-interface", "battery", "ssid", "address", str(self.root)]:
            self.assertNotIn(name, result)

    def process(self, proc, pid, comm, euid):
        entry = proc / str(pid)
        entry.mkdir(parents=True)
        (entry / "comm").write_text(comm + "\n")
        (entry / "status").write_text(f"Name:\t{comm}\nUmask:\t0022\nState:\tS (sleeping)\n"
                                      f"Uid:\t7\t{euid}\t{euid}\t{euid}\n")

    def running(self, proc, uid):
        return subprocess.run([str(self.binary), "--proc", str(proc), str(uid)]).returncode == 0

    def test_keyboard_scan_matches_pgrep_u_x(self):
        proc = self.root / "proc"
        self.process(proc, 1, "systemd", 0)
        (proc / "self").mkdir()
        (proc / "sys").mkdir()
        self.assertFalse(self.running(proc, 1000))
        # pgrep -x: the whole name, not a prefix or substring.
        self.process(proc, 40, "wvkbd-mobintl2", 1000)
        self.process(proc, 41, "wvkbd", 1000)
        self.assertFalse(self.running(proc, 1000))
        # pgrep -u: the effective UID (second Uid: field), not the real one (7).
        self.process(proc, 42, "wvkbd-mobintl", 1000)
        self.assertTrue(self.running(proc, 1000))
        self.assertFalse(self.running(proc, 7))
        self.assertFalse(self.running(proc, 1001))
        # A process that exits between readdir and open is skipped.
        (proc / "43").mkdir()
        self.assertTrue(self.running(proc, 1000))
        self.assertFalse(self.running(self.root / "missing", 1000))

    def test_production_status_reads_live_proc_without_children(self):
        command = self.root / "pgrep"
        marker = self.root / "ran"
        command.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexit 0\n')
        command.chmod(0o700)
        start = time.monotonic()
        result = json.loads(subprocess.check_output([str(self.binary)],
                            env={**os.environ, "K230_PGREP": str(command)}, timeout=5))
        self.assertLess(time.monotonic() - start, 2)
        self.assertFalse(marker.exists())
        self.assertIn(result["controls"]["keyboard"]["state"], ["action", "unavailable"])

if __name__ == "__main__":
    unittest.main()

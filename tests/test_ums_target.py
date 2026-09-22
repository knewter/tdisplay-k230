"""The unattended writer must never accept a newly plugged-in reader."""
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "ums-session.py"
spec = importlib.util.spec_from_file_location("ums_session", SCRIPT)
ums = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ums)


class FlashTargetTests(unittest.TestCase):
    def setUp(self):
        self.properties = {"DEVTYPE": "disk", "ID_BUS": "usb",
                           "ID_VENDOR_ID": "29f1", "ID_MODEL_ID": "0230"}
        self.sectors = 249872384

    def test_observed_board_is_accepted(self):
        ums.validate_flash_target({ums.UMS_DISK}, self.properties, self.sectors, self.sectors)

    def test_other_disk_or_ambiguous_discovery_is_refused(self):
        for disks in (set(), {"usb-Generic_SD_Reader"},
                      {ums.UMS_DISK, "usb-Generic_SD_Reader"}):
            with self.subTest(disks=disks), self.assertRaises(ValueError):
                ums.validate_flash_target(disks, self.properties, self.sectors, self.sectors)

    def test_name_alone_does_not_authorize_a_write(self):
        for key in self.properties:
            wrong = {**self.properties, key: "unexpected"}
            with self.subTest(key=key), self.assertRaises(ValueError):
                ums.validate_flash_target({ums.UMS_DISK}, wrong, self.sectors, self.sectors)

    def test_different_card_size_is_refused(self):
        with self.assertRaises(ValueError):
            ums.validate_flash_target({ums.UMS_DISK}, self.properties, 62521344, self.sectors)

    def test_missing_capacity_fails_before_serial_access(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--out", "/dev/null",
                                 "--dev", "/does-not-exist", "--flash", "/does-not-exist"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--expected-sectors", result.stderr)
        self.assertNotIn("SerialException", result.stderr)


class ReadbackTests(unittest.TestCase):
    def test_identical_corrupt_and_short_readback(self):
        payload = bytes(range(256)) * 32
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image"
            target = Path(directory) / "target"
            image.write_bytes(payload)
            for name, data, expected in (
                ("identical", payload, True),
                ("corrupt", b"!" + payload[1:], False),
                ("short", payload[:4096], False),
            ):
                with self.subTest(name=name):
                    target.write_bytes(data)
                    session = SimpleNamespace(log=io.BytesIO(), pump=lambda: None,
                                              note=lambda message: None)
                    self.assertEqual(ums.verify_written_image(session, image, target),
                                     expected, session.log.getvalue())


class UsbHostVerdictTests(unittest.TestCase):
    def test_physical_candidate_two_record_passes_before_and_after_ums(self):
        trace = (SCRIPT.parents[1] / "tests" / "fixtures" /
                 "uboot-usb-host-coexist-v2.txt").read_bytes()
        self.assertEqual(
            ums.usb_host_verdict(trace, trace, trace, require_start=True), [])
        self.assertEqual(ums.usb_host_verdict(trace, trace), [])

    def test_original_host_baseline_is_not_misreported_as_coexistence_success(self):
        # This committed baseline predates UMS/gadget support.  It proves the
        # host controller and RTL8152 only; the parser must require the other
        # controller's gadget binding too before it can pass a coexistence run.
        trace = (SCRIPT.parents[1] / "docs" / "evidence" /
                 "uboot-ums-hardware.txt").read_bytes()
        failures = ums.usb_host_verdict(trace, trace, trace, require_start=True)
        self.assertNotIn("usb start reported no working controllers", failures)
        self.assertNotIn("usb tree did not enumerate the onboard RTL8152", failures)
        self.assertNotIn("dm tree lacks usbotg1 bound to dwc2_usb", failures)
        self.assertIn("dm tree lacks usbotg0 bound to dwc2-udc-otg", failures)

    def test_no_working_controller_is_an_explicit_host_failure(self):
        failures = ums.usb_host_verdict(
            b"USB is stopped. Please issue 'usb start' first.",
            b"usb 0 [ ] dwc2-udc-otg |-- usb-otg@91500000",
            b"starting USB...\nNo working controllers found\nK230# ",
            require_start=True)
        self.assertIn("usb start reported no working controllers", failures)
        self.assertIn("usb tree did not enumerate the onboard RTL8152", failures)
        self.assertIn("dm tree lacks usbotg1 bound to dwc2_usb", failures)

    def test_missing_usb_start_prompt_is_not_ignored_before_ums(self):
        failures = ums.usb_host_verdict(
            b"Realtek USB 10/100 LAN", b"dwc2_usb usb-otg@91540000\n"
            b"dwc2-udc-otg usb-otg@91500000", None, require_start=True)
        self.assertIn("usb start did not return to the U-Boot prompt", failures)

    def test_swapped_driver_node_bindings_fail(self):
        start = b"Bus usb-otg@91540000: dwc2_usb usb-otg@91540000: Core Release: 4.30a"
        tree = b"Realtek USB 10/100 LAN"
        swapped = (b"usb 0 [ + ] dwc2_usb |-- usb-otg@91500000\n"
                   b"usb 0 [ + ] dwc2-udc-otg |-- usb-otg@91540000")
        failures = ums.usb_host_verdict(tree, swapped, start, require_start=True)
        self.assertIn("dm tree lacks usbotg1 bound to dwc2_usb", failures)
        self.assertIn("dm tree lacks usbotg0 bound to dwc2-udc-otg", failures)


class PullTests(unittest.TestCase):
    def test_usb_host_check_is_opt_in_and_documented_without_serial_access(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--check-usb-host", result.stdout)
        self.assertIn("not packet connectivity", result.stdout)

    def test_pull_arguments_refuse_missing_target_guards_before_serial_access(self):
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "capture.tar")
            cases = (
                ("missing-sectors", ["--pull", "/var/lib/capture.tar",
                                     "--pull-output", output], "--expected-sectors"),
                ("relative-remote", ["--pull", "var/lib/capture.tar",
                                    "--pull-output", output, "--expected-sectors", "249872384"],
                 "absolute debugfs-safe path"),
                ("missing-output", ["--pull", "/var/lib/capture.tar",
                                    "--expected-sectors", "249872384"], "--pull-output"),
                ("orphan-output", ["--pull-output", output], "require --pull"),
            )
            for name, args, message in cases:
                with self.subTest(name=name):
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), "--out", "/dev/null",
                         "--dev", "/does-not-exist", *args],
                        capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(message, result.stderr)
                    self.assertNotIn("SerialException", result.stderr)

    def test_pull_refuses_existing_output_before_debugfs_can_leave_stale_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "capture.tar"
            output.write_bytes(b"old archive that must never pass as a new pull")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--out", "/dev/null",
                 "--dev", "/does-not-exist", "--pull", "/var/lib/capture.tar",
                 "--pull-output", str(output), "--expected-sectors", "249872384"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("must not already exist", result.stderr)
            self.assertNotIn("SerialException", result.stderr)

    def test_pull_hash_requires_nonempty_matching_output(self):
        payload = b"prepared png sample archive\n"
        expected = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "capture.tar"
            with self.assertRaises(ValueError):
                ums.validate_pull_result(output, expected)
            output.write_bytes(b"")
            with self.assertRaises(ValueError):
                ums.validate_pull_result(output, expected)
            output.write_bytes(payload)
            self.assertEqual(ums.validate_pull_result(output, expected), expected)
            with self.assertRaises(ValueError):
                ums.validate_pull_result(output, "0" * 64)

    def test_pull_uses_only_partition_two_and_debugfs_without_write_mode(self):
        payload = b"prepared archive"
        expected = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "capture.tar"
            output.write_bytes(payload)
            session = SimpleNamespace(log=io.BytesIO(), note=lambda message: None)
            completed = SimpleNamespace(returncode=0, stdout="", stderr="")
            with mock.patch.object(ums.os.path, "exists", return_value=True), \
                 mock.patch.object(ums.subprocess, "run", return_value=completed) as run:
                self.assertTrue(ums.pull_root_file(
                    session, "/dev/disk/by-id/" + ums.UMS_DISK,
                    "/var/lib/shell/capture.tar", str(output), expected))
            argv = run.call_args.args[0]
            self.assertEqual(argv[0], "debugfs")
            self.assertNotIn("-w", argv)
            self.assertTrue(argv[-1].endswith("-part2"))
            self.assertTrue(argv[2].startswith("dump -p "))


if __name__ == "__main__":
    unittest.main()

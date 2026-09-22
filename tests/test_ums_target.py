"""The unattended writer must never accept a newly plugged-in reader."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()

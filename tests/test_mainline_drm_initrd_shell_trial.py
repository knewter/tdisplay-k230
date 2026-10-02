import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "tools/mainline-drm-initrd-shell-trial.py"
SPEC = importlib.util.spec_from_file_location("initrd_trial", SCRIPT)
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)


class InitrdShellTrialTests(unittest.TestCase):
    def test_adds_only_rdinit_to_matching_trial_bootargs(self):
        original = f"console=ttyS0,115200n8 init={trial.SYSTEM}/init"
        self.assertEqual(
            trial.trial_bootargs(original),
            original + " rdinit=/bin/sh",
        )

    def test_rejects_mismatched_system_and_existing_rdinit(self):
        with self.assertRaisesRegex(ValueError, "matching trial system"):
            trial.trial_bootargs("console=ttyS0 init=/init")
        with self.assertRaisesRegex(ValueError, "already contain rdinit"):
            trial.trial_bootargs(f"init={trial.SYSTEM}/init rdinit=/init")
        with self.assertRaisesRegex(ValueError, "matching trial system"):
            trial.trial_bootargs(f"notinit={trial.SYSTEM}/init")

    def test_load_requires_both_exact_size_and_crc(self):
        expected = {"bytes": 1234, "crc32": "a1b2c3d4"}
        good = b"1234 bytes read\n==> a1b2c3d4"
        self.assertTrue(trial.verified_load(good, expected))
        self.assertFalse(trial.verified_load(b"1233 bytes read\n==> a1b2c3d4", expected))
        self.assertFalse(trial.verified_load(b"1234 bytes read\n==> deadbeef", expected))
        self.assertFalse(trial.verified_load(None, expected))

    def test_candidate_memory_ranges_do_not_overlap(self):
        sizes = {
            "bootargs.txt": 211,
            "fw_jump_add_uboot_head.bin": 270808,
            "Image-mainline-drm": 38530560,
            "k230-tdisplay-mainline-drm.dtb": 11025,
            "initrd.uimg": 27314097,
        }
        intervals = []
        for name, _, address, _ in trial.LOADS:
            start = int(address, 16)
            intervals.append((start, start + sizes[name], name))
        intervals.sort()
        for left, right in zip(intervals, intervals[1:]):
            self.assertLessEqual(left[1], right[0], f"{left[2]} overlaps {right[2]}")

    def test_probe_keeps_pid_one_running_then_reboots(self):
        self.assertNotIn("exit", trial.PROBE)
        self.assertIn("K230_RDINIT_PROBE_END", trial.PROBE)
        self.assertIn("reboot -f", trial.PROBE)


if __name__ == "__main__":
    unittest.main()

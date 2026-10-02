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
        good_load = b"ext4load mmc 1:2 0x200000 /Image\r\n1234 bytes read in 1 ms\r\nK230# "
        good_crc = b"crc32 0x200000 0x4d2\r\nCRC32 for 00200000 ... 002004d1 ==> a1b2c3d4\r\nK230# "
        self.assertTrue(trial.verified_load(good_load, expected))
        self.assertTrue(trial.verified_crc(good_crc, expected))
        for bad_load in (
            b"1233 bytes read in 1 ms\r\nK230# ",
            b"echo 1234 bytes read in 1 ms\r\nK230# ",
            b"1234 bytes read in 1 ms",
            b"1234 bytes read in 1 ms\r\n1234 bytes read in 1 ms\r\nK230# ",
            None,
        ):
            self.assertFalse(trial.verified_load(bad_load, expected))
        for bad_crc in (
            b"echo CRC32 for 00200000 ... 002004d1 ==> a1b2c3d4\r\nK230# ",
            b"CRC32 for 00200000 ... 002004d1 ==> deadbeef\r\nK230# ",
            b"CRC32 for 00200000 ... 002004d1 ==> a1b2c3d4",
            b"CRC32 for 00200000 ... 002004d1 ==> a1b2c3d4\r\nCRC32 for 00200000 ... 002004d1 ==> a1b2c3d4\r\nK230# ",
            None,
        ):
            self.assertFalse(trial.verified_crc(bad_crc, expected))

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
        command = trial.probe_command("a" * 32)
        self.assertNotIn("exit", command)
        self.assertTrue(command.startswith("PATH=/bin:/sbin; export PATH; "))
        self.assertIn("mount -t proc proc /proc", command)
        self.assertIn("mount -t sysfs sysfs /sys", command)
        self.assertIn("mount -t devtmpfs devtmpfs /dev", command)
        self.assertIn("done < /proc/mounts", command)
        self.assertIn("test $_k230_block_count -gt 0", command)
        self.assertIn("test $_k230_label_ok -eq 1", command)
        self.assertIn("K230_LABEL_NIXOS_SD", command)
        self.assertIn("e2label", command)
        self.assertNotIn("mount /dev/mmc", command)
        self.assertIn("/bin/reboot -ff", command)

    def test_probe_result_requires_fresh_complete_standalone_line(self):
        token = "a" * 32
        valid = f"K230_RDINIT_PROBE {token} RC=0\r\n".encode()
        self.assertEqual(trial.probe_result(valid, token), 0)
        self.assertEqual(trial.probe_result(valid.replace(b"RC=0", b"RC=1"), token), 1)
        for invalid in (
            b"echo K230_RDINIT_PROBE " + token.encode() + b" RC=0\r\n",
            b"printf 'K230_RDINIT_PROBE " + token.encode() + b" RC=0\\n'\r\n",
            f"K230_RDINIT_PROBE {token} RC=0".encode(),
            f"K230_RDINIT_PROBE {'b' * 32} RC=0\r\n".encode(),
            f"K230_RDINIT_PROBE {token} RC=0\r\nK230_RDINIT_PROBE {token} RC=0\r\n".encode(),
        ):
            with self.subTest(invalid=invalid):
                self.assertIsNone(trial.probe_result(invalid, token))

    def test_nixos_sd_label_is_reported_only_from_one_complete_line(self):
        self.assertTrue(trial.probe_nixos_label(b"K230_LABEL_NIXOS_SD=1\r\n"))
        self.assertFalse(trial.probe_nixos_label(b"K230_LABEL_NIXOS_SD=0\r\n"))
        for invalid in (
            b"echo K230_LABEL_NIXOS_SD=1\r\n",
            b"K230_LABEL_NIXOS_SD=1",
            b"K230_LABEL_NIXOS_SD=1\r\nK230_LABEL_NIXOS_SD=1\r\n",
        ):
            self.assertIsNone(trial.probe_nixos_label(invalid))

    def test_state_and_upload_markers_reject_echo_or_incomplete_lines(self):
        token = "c" * 32
        value = b'{"boot_id":"next","system":"/nix/store/system"}'
        marker = b"K230_MAINLINE_STATE " + token.encode() + b" postflight " + value + b"\r\n"
        self.assertEqual(trial.state_marker(marker, token, "postflight"), {"boot_id": "next", "system": "/nix/store/system"})
        self.assertTrue(trial.upload_marker(b"K230_UPLOAD_" + token.encode() + b"\r\n", token))
        self.assertFalse(trial.upload_marker(b"printf K230_UPLOAD_" + token.encode() + b"\\n\r\n", token))
        self.assertFalse(trial.upload_marker(b"K230_UPLOAD_" + token.encode(), token))
        self.assertIsNone(trial.state_marker(b"python3 state " + token.encode() + b"\r\n" + marker[:-2], token, "postflight"))
        self.assertIsNone(trial.state_marker(marker + marker, token, "postflight"))


if __name__ == "__main__":
    unittest.main()

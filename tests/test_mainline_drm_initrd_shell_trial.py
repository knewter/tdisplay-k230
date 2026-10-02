import importlib.util
import copy
import hashlib
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "tools/mainline-drm-initrd-shell-trial.py"
SPEC = importlib.util.spec_from_file_location("initrd_trial", SCRIPT)
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 0.001
        return self.now


class FakeSerialSession:
    def __init__(self, replies):
        self.replies = list(replies)
        self.pending = []
        self.writes = []
        self.buffer = b""

    def write(self, data):
        self.writes.append(data)
        if self.replies:
            reply = self.replies.pop(0)
            if reply is not None:
                self.pending.extend(reply if isinstance(reply, list) else [reply])

    def pump(self):
        if self.pending:
            self.buffer += self.pending.pop(0)


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
        trial.validate_load_ranges({
            name: {"bytes": size, "sha256": "a" * 64} for name, size in sizes.items()
        })

    def test_minimal_commands_are_short_and_survey_is_separate(self):
        token = "a" * 32
        commands = (
            trial.reception_command(token), trial.true_command(token),
            trial.proc_mount_command(token), trial.uptime_command(token), trial.reboot_command(token),
        )
        self.assertTrue(commands[0].startswith("PATH=/bin:/sbin; export PATH;"))
        self.assertTrue(all(len(command.encode()) < 500 for command in commands))
        self.assertIn("/bin/true", commands[1])
        self.assertIn("/bin/mount -t proc proc /proc", commands[2])
        self.assertIn("K230_RDINIT_MOUNT_BEGIN", commands[2])
        self.assertIn("K230_RDINIT_MOUNT_END", commands[2])
        self.assertIn("/bin/cat /proc/uptime", commands[3])
        self.assertIn("K230_RDINIT_UP_BEGIN", commands[3])
        self.assertIn("K230_RDINIT_UP_END", commands[3])
        self.assertIn("/bin/reboot -ff", commands[4])
        survey = trial.survey_command(token)
        self.assertIn("K230_PROC", survey)
        self.assertIn("K230_RDINIT_SURVEY", survey)
        self.assertLess(len(survey.encode()), 4096)
        for command in commands:
            for shell in ("bash", "sh"):
                import subprocess
                result = subprocess.run([shell, "-n"], input=command, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)

        label_loop = trial.PROBE_DATA.split("for dev in /dev/mmcblk*p*; do", 1)[1].split(
            "test $_k230_block_count -gt 0", 1
        )[0]
        self.assertIn("if _k230_label=$(e2label", label_loop)
        self.assertIn("else _k230_label=unreadable; fi;", label_loop)
        self.assertNotIn("_k230_probe_rc=1", label_loop)

    def test_probe_protocol_success_is_sequential_and_uses_distinct_schema(self):
        token = "b" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\r\n".encode(),
            [b"K230_RDINIT_TRUE " + token.encode() + b" RC=0\r", b"\n"],
            f"K230_RDINIT_MOUNT_BEGIN {token}\r\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\r\n".encode(),
            f"K230_RDINIT_UP_BEGIN {token}\r\n12.50 8.25\r\nK230_RDINIT_UP_END {token} RC=0\r\n".encode(),
            f"K230_RDINIT_REBOOT {token}\r\n".encode(),
        ])
        outcome = trial.run_probe_protocol(session, token, "minimal", timeout=0.02, clock=FakeClock())
        self.assertEqual(outcome["diagnostic"]["schema"], "k230-initrd-minimal-v2")
        self.assertEqual(outcome["diagnostic"]["uptime"], ["12.50", "8.25"])
        self.assertEqual(outcome["diagnostic"]["proc_mount"], {"mkdir_rc": 0, "mount_attempted": True, "mount_rc": 0})
        self.assertTrue(outcome["diagnostic_ok"])
        self.assertTrue(outcome["reboot_marker"])
        commands = [item.decode().rstrip("\r") for item in session.writes]
        self.assertEqual(len(commands), 5)
        self.assertTrue(commands[-1].startswith("printf 'K230_RDINIT_REBOOT"))
        self.assertFalse(any("K230_PROC" in command for command in commands))
        self.assertEqual(["/bin/true" in command for command in commands], [False, True, False, False, False])

    def test_early_receipt_is_retried_and_old_or_echoed_markers_cannot_pass_new_attempt(self):
        tokens = iter(("3" * 32, "4" * 32))
        token = "2" * 32
        echoed_second = f"printf 'K230_RDINIT_RX {'3' * 32}\\n'\r\n".encode()
        session = FakeSerialSession([
            None,  # First receipt line was sent before the shell consumed it.
            echoed_second + f"K230_RDINIT_RX {token}\r\n".encode(),  # Echo + late stale response.
            f"K230_RDINIT_RX {'4' * 32}\r\n".encode(),
            f"K230_RDINIT_TRUE {'4' * 32} RC=0\r\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {'4' * 32}\r\nK230_RDINIT_MOUNT_END {'4' * 32} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\r\n".encode(),
            f"K230_RDINIT_UP_BEGIN {'4' * 32}\r\n3.0 2.0\r\nK230_RDINIT_UP_END {'4' * 32} RC=0\r\n".encode(),
            f"K230_RDINIT_REBOOT {'4' * 32}\r\n".encode(),
        ])
        outcome = trial.run_probe_protocol(
            session, token, "minimal", timeout=0.02, readiness_timeout=0.01,
            token_factory=lambda: next(tokens), clock=FakeClock(),
        )
        self.assertEqual(outcome["diagnostic"]["reception_attempts"], 3)
        self.assertTrue(outcome["diagnostic_ok"])
        commands = [item.decode().rstrip("\r") for item in session.writes]
        self.assertEqual(len(commands), 7)
        self.assertIn(f"K230_RDINIT_RX {token}", commands[0])
        self.assertIn(f"K230_RDINIT_RX {'3' * 32}", commands[1])
        self.assertIn(f"K230_RDINIT_RX {'4' * 32}", commands[2])
        self.assertIn("/bin/true", commands[3])
        self.assertIn(f"K230_RDINIT_TRUE {'4' * 32}", commands[3])
        self.assertIn("/bin/mount -t proc proc /proc", commands[4])
        self.assertIn("/bin/cat /proc/uptime", commands[5])

    def test_receipt_retry_exhaustion_is_bounded_and_never_starts_external_probe(self):
        tokens = iter(("5" * 32, "6" * 32))
        session = FakeSerialSession([None, None, None])
        with self.assertRaisesRegex(trial.ProbeProtocolError, "reception"):
            trial.run_probe_protocol(
                session, "7" * 32, "minimal", readiness_attempts=3,
                readiness_timeout=0.01, token_factory=lambda: next(tokens), clock=FakeClock(),
            )
        self.assertEqual(len(session.writes), 3)
        self.assertTrue(all(b"K230_RDINIT_RX" in command for command in session.writes))
        self.assertFalse(any(b"/bin/true" in command for command in session.writes))
        untouched = FakeSerialSession([])
        with self.assertRaisesRegex(ValueError, "between 1 and 8"):
            trial.await_reception(untouched, "1" * 32, attempts=9, clock=FakeClock())
        self.assertEqual(untouched.writes, [])

    def test_true_rc_failure_stops_before_mount_uptime_survey_or_reboot(self):
        token = "c" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=127\n".encode(),
        ])
        outcome = trial.run_probe_protocol(session, token, "survey", timeout=0.02, clock=FakeClock())
        self.assertEqual(outcome["diagnostic"]["schema"], "k230-initrd-prerequisite-failure-v1")
        self.assertEqual(outcome["diagnostic"]["proc_mount"], {"attempted": False})
        self.assertFalse(outcome["diagnostic_ok"])
        self.assertTrue(outcome["recovery_required"])
        self.assertFalse(outcome["reboot_marker"])
        self.assertEqual(len(session.writes), 2)
        self.assertFalse(any(b"K230_PROC" in command for command in session.writes))
        self.assertFalse(any(b"/proc/uptime" in command or b"/bin/reboot" in command for command in session.writes))

    def test_mount_failure_is_structured_and_stops_before_uptime_survey_or_reboot(self):
        token = "a" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {token}\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=32\n".encode(),
        ])
        outcome = trial.run_probe_protocol(session, token, "survey", timeout=0.02, clock=FakeClock())
        self.assertEqual(outcome["diagnostic"]["schema"], "k230-initrd-prerequisite-failure-v1")
        self.assertEqual(outcome["diagnostic"]["proc_mount"], {"mkdir_rc": 0, "mount_attempted": True, "mount_rc": 32})
        self.assertEqual(outcome["diagnostic"]["uptime"], {"attempted": False})
        self.assertEqual(outcome["recovery_reason"], "proc-mount-nonzero")
        self.assertTrue(outcome["recovery_required"])
        self.assertFalse(outcome["reboot_marker"])
        self.assertEqual(len(session.writes), 3)
        self.assertFalse(any(b"K230_PROC" in command or b"/proc/uptime" in command or b"/bin/reboot" in command for command in session.writes))

    def test_missing_proc_directory_setup_rc_is_preserved_and_gates_all_later_stages(self):
        token = "9" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {token}\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=2 MOUNT_ATTEMPTED=0 MOUNT_RC=255\n".encode(),
        ])
        outcome = trial.run_probe_protocol(session, token, "survey", timeout=0.02, clock=FakeClock())
        self.assertEqual(
            outcome["diagnostic"]["proc_mount"],
            {"mkdir_rc": 2, "mount_attempted": False, "mount_rc": 255},
        )
        self.assertEqual(outcome["recovery_reason"], "proc-directory-setup-nonzero")
        self.assertEqual(outcome["diagnostic"]["uptime"], {"attempted": False})
        self.assertEqual(len(session.writes), 3)
        self.assertFalse(any(b"/bin/reboot" in command for command in session.writes))

    def test_missing_mount_marker_stops_with_unknown_result_and_no_later_commands(self):
        token = "b" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            None,
        ])
        with self.assertRaisesRegex(trial.ProbeProtocolError, "mount"):
            trial.run_probe_protocol(session, token, "minimal", timeout=0.01, clock=FakeClock())
        self.assertEqual(len(session.writes), 3)
        self.assertFalse(any(b"/proc/uptime" in command or b"/bin/reboot" in command for command in session.writes))

    def test_explicit_survey_runs_only_after_minimal_success(self):
        token = "e" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {token}\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\n".encode(),
            f"K230_RDINIT_UP_BEGIN {token}\n2.0 3.0\nK230_RDINIT_UP_END {token} RC=0\n".encode(),
            f"K230_LABEL_NIXOS_SD=0\nK230_RDINIT_SURVEY {token} RC=0\n".encode(),
            f"K230_RDINIT_REBOOT {token}\n".encode(),
        ])
        outcome = trial.run_probe_protocol(session, token, "survey", timeout=0.02, clock=FakeClock())
        self.assertEqual(outcome["diagnostic"]["survey"]["status"], "complete")
        self.assertFalse(outcome["diagnostic"]["survey"]["nixos_sd_label_present"])
        self.assertTrue(outcome["diagnostic_ok"])
        self.assertIn(b"K230_PROC", session.writes[4])

    def test_survey_timeout_stops_without_reboot_input(self):
        token = "9" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {token}\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\n".encode(),
            f"K230_RDINIT_UP_BEGIN {token}\n1.0 1.0\nK230_RDINIT_UP_END {token} RC=0\n".encode(),
            None,
        ])
        with self.assertRaisesRegex(trial.ProbeProtocolError, "optional survey"):
            trial.run_probe_protocol(session, token, "survey", timeout=0.01, clock=FakeClock())
        self.assertEqual(len(session.writes), 5)
        self.assertFalse(any(b"K230_RDINIT_REBOOT" in command for command in session.writes))

    def test_reboot_marker_timeout_is_reported_separately_from_successful_minimal_probe(self):
        token = "8" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {token}\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\n".encode(),
            f"K230_RDINIT_UP_BEGIN {token}\n1.0 1.0\nK230_RDINIT_UP_END {token} RC=0\n".encode(),
            None,
        ])
        outcome = trial.run_probe_protocol(session, token, "minimal", timeout=0.01, clock=FakeClock())
        self.assertTrue(outcome["diagnostic_ok"])
        self.assertFalse(outcome["reboot_marker"])
        self.assertEqual(len(session.writes), 5)

    def test_probe_stage_parser_requires_unique_complete_fresh_lines(self):
        token = "d" * 32
        valid = (
            f"K230_RDINIT_STAGE {token} shell-start\r\n"
            f"K230_RDINIT_STAGE {token} mkdir-done\r\n"
            f"K230_RDINIT_STAGE {token} proc-read-start\r\n"
        ).encode()
        self.assertEqual(
            trial.probe_stage_markers(valid, token),
            ("shell-start", "mkdir-done", "proc-read-start"),
        )
        for invalid in (
            f"printf 'K230_RDINIT_STAGE {token} shell-start\\n'\r\n".encode(),
            f"K230_RDINIT_STAGE {'e' * 32} shell-start\r\n".encode(),
            f"K230_RDINIT_STAGE {token} shell-start".encode(),
            (f"K230_RDINIT_STAGE {token} shell-start\r\n" * 2).encode(),
        ):
            with self.subTest(invalid=invalid):
                self.assertEqual(trial.probe_stage_markers(invalid, token), ())

    def test_minimal_markers_reject_echo_stale_truncated_and_duplicate_lines(self):
        token = "f" * 32
        other = "1" * 32
        self.assertTrue(trial.receive_marker(f"K230_RDINIT_RX {token}\r\n".encode(), token))
        self.assertEqual(trial.protocol_rc_marker(f"K230_RDINIT_TRUE {token} RC=0\r\n".encode(), token, "true"), 0)
        self.assertTrue(trial.reboot_marker(f"K230_RDINIT_REBOOT {token}\r\n".encode(), token))
        mount = f"K230_RDINIT_MOUNT_BEGIN {token}\r\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\r\n".encode()
        self.assertEqual(trial.proc_mount_result(mount, token), {"mkdir_rc": 0, "mount_attempted": True, "mount_rc": 0})
        self.assertTrue(trial.reboot_chroot_refusal(b"Running in chroot, ignoring request.\r\n"))
        self.assertFalse(trial.reboot_chroot_refusal(b"echo Running in chroot, ignoring request.\r\n"))
        uptime = f"K230_RDINIT_UP_BEGIN {token}\r\n5.00 4.00\r\nK230_RDINIT_UP_END {token} RC=0\r\n".encode()
        self.assertEqual(trial.uptime_result(uptime, token), {"rc": 0, "uptime": ["5.00", "4.00"]})
        invalid_receipts = (
            f"printf 'K230_RDINIT_RX {token}\\n'\r\n".encode(),
            f"K230_RDINIT_RX {other}\r\n".encode(),
            f"K230_RDINIT_RX {token}".encode(),
            (f"K230_RDINIT_RX {token}\r\n" * 2).encode(),
        )
        for invalid in invalid_receipts:
            with self.subTest(invalid=invalid):
                self.assertIsNone(trial.receive_marker(invalid, token))
        invalid_rc = (
            f"printf 'K230_RDINIT_TRUE {token} RC=0\\n'\r\n".encode(),
            f"K230_RDINIT_TRUE {other} RC=0\r\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0".encode(),
            (f"K230_RDINIT_TRUE {token} RC=0\r\n" * 2).encode(),
            f"K230_RDINIT_TRUE {token} RC=999\r\n".encode(),
        )
        for invalid in invalid_rc:
            with self.subTest(invalid=invalid):
                self.assertIsNone(trial.protocol_rc_marker(invalid, token, "true"))
        invalid_mounts = (
            f"printf 'K230_RDINIT_MOUNT_BEGIN {token}\\n'\r\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\r\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {other}\r\nK230_RDINIT_MOUNT_END {other} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\r\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {token}\r\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0".encode(),
            (f"K230_RDINIT_MOUNT_BEGIN {token}\r\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\r\n" * 2).encode(),
            mount.replace(b"MOUNT_RC=0", b"MOUNT_RC=999"),
            mount.replace(b"MOUNT_ATTEMPTED=1", b"MOUNT_ATTEMPTED=0"),
        )
        for invalid in invalid_mounts:
            with self.subTest(invalid=invalid):
                self.assertIsNone(trial.proc_mount_result(invalid, token))
        for invalid in (
            uptime.replace(token.encode(), other.encode()),
            uptime.replace(b"\r\n", b"", 1),
            uptime + uptime,
            f"K230_RDINIT_UP_BEGIN {token}\r\nK230_RDINIT_UP_END {token} RC=0\r\n".encode(),
        ):
            with self.subTest(invalid=invalid):
                self.assertIsNone(trial.uptime_result(invalid, token))

    def test_protocol_timeouts_stop_without_reboot_or_more_probe_input(self):
        token = "2" * 32
        bad_receipts = (
            None,
            f"printf 'K230_RDINIT_RX {token}\\n'\r\n".encode(),
            f"K230_RDINIT_RX {'3' * 32}\r\n".encode(),
            (f"K230_RDINIT_RX {token}\r\n" * 2).encode(),
        )
        for reply in bad_receipts:
            with self.subTest(reply=reply):
                session = FakeSerialSession([reply])
                with self.assertRaisesRegex(trial.ProbeProtocolError, "reception"):
                    trial.run_probe_protocol(
                        session, token, "minimal", timeout=0.01, readiness_attempts=1,
                        readiness_timeout=0.01, clock=FakeClock(),
                    )
                self.assertEqual(len(session.writes), 1)
        for replies, stage, write_count in (
            ([f"K230_RDINIT_RX {token}\n".encode(), None], "/bin/true", 2),
            ([f"K230_RDINIT_RX {token}\n".encode(), f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
              f"K230_RDINIT_MOUNT_BEGIN {token}\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\n".encode(),
              f"K230_RDINIT_UP_BEGIN {token}\n".encode()], "/bin/cat /proc/uptime", 4),
        ):
            with self.subTest(stage=stage):
                session = FakeSerialSession(replies)
                with self.assertRaisesRegex(trial.ProbeProtocolError, stage.replace("/", "\\/")):
                    trial.run_probe_protocol(session, token, "minimal", timeout=0.01, clock=FakeClock())
                self.assertEqual(len(session.writes), write_count)
                self.assertFalse(any(b"K230_RDINIT_REBOOT" in command for command in session.writes))

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


class LabelProbeTests(unittest.TestCase):
    token = "a" * 32

    def minimal_replies(self):
        t = self.token
        return [
            f"K230_RDINIT_RX {t}\n".encode(),
            f"K230_RDINIT_TRUE {t} RC=0\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {t}\nK230_RDINIT_MOUNT_END {t} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\n".encode(),
            f"K230_RDINIT_UP_BEGIN {t}\n1.0 2.0\nK230_RDINIT_UP_END {t} RC=0\n".encode(),
        ]

    def setup_reply(self, stage, rc=0):
        return (f"K230_RDINIT_LABEL_SETUP_BEGIN {self.token} STAGE={stage}\n"
                f"K230_RDINIT_LABEL_SETUP_END {self.token} STAGE={stage} RC={rc}\n").encode()

    def label_reply(self, rc=0, match=1):
        return (f"K230_RDINIT_LABEL_BEGIN {self.token}\n"
                f"K230_RDINIT_LABEL_END {self.token} RC={rc} MATCH={match}\n").encode()

    def run_protocol(self, replies):
        session = FakeSerialSession(replies)
        outcome = trial.run_probe_protocol(session, self.token, "label", timeout=0.02, clock=FakeClock())
        return session, outcome

    def setup_replies(self):
        return [self.setup_reply(stage) for stage in ("dev-mkdir", "dev-mount", "node")]

    def test_label_runs_once_only_after_all_gates_and_uses_distinct_schema(self):
        session, outcome = self.run_protocol(self.minimal_replies() + self.setup_replies() + [
            self.label_reply(), f"K230_RDINIT_REBOOT {self.token}\n".encode(),
        ])
        self.assertEqual(outcome["diagnostic"]["schema"], "k230-initrd-label-v1")
        self.assertEqual(outcome["diagnostic"]["label"], {"attempted": True, "rc": 0, "match": True})
        self.assertTrue(outcome["diagnostic_ok"])
        self.assertTrue(outcome["reboot_marker"])
        expected = [trial.reception_command(self.token), trial.true_command(self.token),
                    trial.proc_mount_command(self.token), trial.uptime_command(self.token),
                    *(trial.label_setup_command(self.token, s) for s in ("dev-mkdir", "dev-mount", "node")),
                    trial.label_command(self.token), trial.reboot_command(self.token)]
        self.assertEqual(session.writes, [(c + "\r").encode() for c in expected])
        self.assertEqual(sum(c.count(b"/bin/e2label /dev/mmcblk1p2") for c in session.writes), 1)

    def test_returned_nonmatch_and_failed_label_rc_allow_only_existing_recovery(self):
        for rc, match in ((0, 0), (1, 0), (127, 0)):
            with self.subTest(rc=rc):
                session, outcome = self.run_protocol(self.minimal_replies() + self.setup_replies() + [
                    self.label_reply(rc, match), f"K230_RDINIT_REBOOT {self.token}\n".encode(),
                ])
                self.assertFalse(outcome["diagnostic_ok"])
                self.assertEqual(outcome["diagnostic"]["label"]["rc"], rc)
                self.assertFalse(outcome["diagnostic"]["label"]["match"])
                self.assertEqual(session.writes[-1], (trial.reboot_command(self.token) + "\r").encode())

    def test_setup_rc_failure_and_node_absence_stop_before_label_or_reboot(self):
        for index, stage in enumerate(("dev-mkdir", "dev-mount", "node")):
            with self.subTest(stage=stage):
                replies = self.minimal_replies() + self.setup_replies()[:index] + [self.setup_reply(stage, 1)]
                session, outcome = self.run_protocol(replies)
                self.assertEqual(len(session.writes), 5 + index)
                self.assertTrue(outcome["recovery_required"])
                self.assertEqual(outcome["recovery_reason"], f"label-{stage}-nonzero")
                self.assertEqual(outcome["diagnostic"]["label"], {"attempted": False})
                self.assertFalse(any(b"/bin/e2label" in c or b"/bin/reboot" in c for c in session.writes))

    def test_minimal_gate_failures_cannot_start_dev_or_label_probe(self):
        cases = [
            self.minimal_replies()[:1] + [f"K230_RDINIT_TRUE {self.token} RC=1\n".encode()],
            self.minimal_replies()[:2] + [f"K230_RDINIT_MOUNT_BEGIN {self.token}\nK230_RDINIT_MOUNT_END {self.token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=1\n".encode()],
            self.minimal_replies()[:3] + [f"K230_RDINIT_UP_BEGIN {self.token}\nK230_RDINIT_UP_END {self.token} RC=1\n".encode()],
        ]
        for replies in cases:
            with self.subTest(replies=len(replies)):
                session, outcome = self.run_protocol(replies)
                self.assertTrue(outcome["recovery_required"])
                self.assertEqual(outcome["diagnostic"]["schema"], "k230-initrd-label-prerequisite-failure-v1")
                self.assertFalse(any(b"LABEL" in c or b"/bin/reboot" in c for c in session.writes))

    def test_incomplete_setup_and_label_never_retry_or_send_recovery_input(self):
        stages = ("dev-mkdir", "dev-mount", "node", "label")
        for index, stage in enumerate(stages):
            with self.subTest(stage=stage):
                session = FakeSerialSession(self.minimal_replies() + self.setup_replies()[:index] + [None])
                with self.assertRaisesRegex(trial.ProbeProtocolError, "label"):
                    trial.run_probe_protocol(session, self.token, "label", timeout=0.01, clock=FakeClock())
                self.assertEqual(len(session.writes), 5 + index)
                for command in session.writes:
                    self.assertNotIn(b"/bin/reboot", command)
                    self.assertNotIn(b"exit", command)
                    self.assertNotIn(b"\x03", command)
                    self.assertNotIn(b"K230_PROC", command)

    def test_label_parsers_reject_echo_stale_duplicates_truncation_and_wrong_order(self):
        for stage in ("dev-mkdir", "dev-mount", "node", "label"):
            good = self.label_reply() if stage == "label" else self.setup_reply(stage)
            self.assertIsNotNone(trial.label_result(good, self.token, stage))
            lines = good.splitlines(keepends=True)
            for invalid in (b"echo " + good, good.replace(self.token.encode(), b"b" * 32),
                            good + good, good[:-1], lines[1] + lines[0], lines[0], lines[1],
                            good.replace(b"RC=0", b"RC=256")):
                with self.subTest(stage=stage, invalid=invalid):
                    self.assertIsNone(trial.label_result(invalid, self.token, stage))
        self.assertIsNone(trial.label_result(self.label_reply(1, 1), self.token))

    def test_bad_label_final_markers_stop_protocol_without_child_retry(self):
        good = self.label_reply()
        for reply in (good[:-1], good + good, good.replace(self.token.encode(), b"b" * 32),
                      b"echo " + good, good.splitlines(keepends=True)[0]):
            with self.subTest(reply=reply):
                session = FakeSerialSession(self.minimal_replies() + self.setup_replies() + [reply])
                with self.assertRaises(trial.ProbeProtocolError):
                    trial.run_probe_protocol(session, self.token, "label", timeout=0.01, clock=FakeClock())
                self.assertEqual(len(session.writes), 8)
                self.assertEqual(sum(b"/bin/e2label" in c for c in session.writes), 1)
                self.assertFalse(any(b"/bin/reboot" in c for c in session.writes))

    def test_payload_is_readonly_absolute_and_prints_no_raw_label_or_cmdline(self):
        import subprocess
        commands = [*(trial.label_setup_command(self.token, s) for s in ("dev-mkdir", "dev-mount", "node")),
                    trial.label_command(self.token)]
        self.assertIn("/bin/e2label /dev/mmcblk1p2 2>/dev/null", commands[-1])
        self.assertEqual(commands[-1].count("/bin/e2label"), 1)
        for command in commands:
            self.assertLess(len(command), 1000)
            self.assertNotIn("/proc/cmdline", command)
            self.assertNotIn("/proc/interrupts", command)
            self.assertNotIn("2>&1", command)
            for shell in ("sh", "bash"):
                check = subprocess.run([shell, "-n"], input=command, text=True, capture_output=True)
                self.assertEqual(check.returncode, 0, check.stderr)
        self.assertNotIn('"$_k230_label"', commands[-1].split("printf 'K230_RDINIT_LABEL_END", 1)[1])

    def test_clock_flag_adds_exactly_one_argument_and_keeps_strict_identity(self):
        original = f"bootargs=console=ttyS0 init={trial.SYSTEM}/init"
        ordinary = trial.trial_bootargs(original)
        changed = trial.trial_bootargs(original, ignore_unused_clocks=True)
        self.assertEqual(changed.split(), ordinary.split() + ["clk_ignore_unused"])
        self.assertEqual(trial.volatile_bootargs_command(True),
                         'setenv bootargs "${bootargs} rdinit=/bin/sh clk_ignore_unused"')
        self.assertEqual(trial.volatile_bootargs_command(), 'setenv bootargs "${bootargs} rdinit=/bin/sh"')
        self.assertNotIn("saveenv", trial.volatile_bootargs_command(True))
        self.assertTrue(trial.verified_bootargs((changed + "\n").encode(), changed))
        self.assertFalse(trial.verified_bootargs((ordinary + "\n").encode(), changed))
        for suffix in ("clk_ignore_unused", "clk_ignore_unused=1"):
            with self.assertRaisesRegex(ValueError, "already contain clk_ignore_unused"):
                trial.trial_bootargs(original + " " + suffix, ignore_unused_clocks=True)
        with self.assertRaisesRegex(ValueError, "matching trial system"):
            trial.trial_bootargs("bootargs=init=/wrong", ignore_unused_clocks=True)

    def test_clock_flag_rejects_other_modes_before_preparation_or_serial(self):
        for mode in ("minimal", "survey"):
            with self.subTest(mode=mode), mock.patch.object(trial, "prepare_trial") as prepare, \
                    mock.patch.object(trial, "PrivateSession") as session, mock.patch.object(trial.os, "open") as opened:
                with self.assertRaisesRegex(ValueError, "requires --mode label"):
                    trial.run_trial(Path('/missing'), Path('/unused'), Path('/unused-result'), mode,
                                    ignore_unused_clocks=True)
                prepare.assert_not_called(); session.assert_not_called(); opened.assert_not_called()
            with mock.patch.object(sys, "argv", [str(SCRIPT), "--mode", mode, "--ignore-unused-clocks"]), \
                    mock.patch.object(trial, "run_trial") as runner, mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:
                    trial.main()
                self.assertEqual(error.exception.code, 2)
                runner.assert_not_called()

    def test_cli_explicit_label_and_clock_selection(self):
        with mock.patch.object(sys, "argv", [str(SCRIPT), "--mode", "label", "--ignore-unused-clocks"]), \
                mock.patch.object(trial, "run_trial", return_value=True) as runner:
            self.assertEqual(trial.main(), 0)
            self.assertEqual(runner.call_args.args[3], "label")
            self.assertEqual(runner.call_args.kwargs, {"ignore_unused_clocks": True})


class CandidateSelectionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = self.root / "store"
        self.store.mkdir()
        self.store_patch = mock.patch.object(trial, "STORE_ROOT", self.store)
        self.store_patch.start()
        self.report = json.loads(trial.NORMAL_BASELINE.read_text())
        self.report_path = self.root / "normal.json"
        self.report_path.write_text(json.dumps(self.report))
        self.bundle, self.system, self.manifest = self.make_bundle("1", "2")
        self.manifest_path = self.root / "manifest.json"
        self.save_manifest()

    def tearDown(self):
        self.store_patch.stop()
        for path in self.store.rglob("*"):
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)
        self.directory.cleanup()

    def make_bundle(self, bundle_hash, system_hash):
        bundle = self.store / (bundle_hash * 32 + "-k230-mainline-drm-trial-boot-files")
        system = self.store / (system_hash * 32 + "-nixos-system-test")
        bundle.mkdir(); system.mkdir()
        (system / "init").write_text("fixture init\n")
        (system / "init").chmod(0o555)
        (bundle / "system").symlink_to(system, target_is_directory=True)
        files = {}
        for name, _, _, _ in trial.LOADS:
            if name == "fw_jump_add_uboot_head.bin":
                files[name] = {**self.report["boot_files"][name], "crc32": trial.NORMAL_WRAPPER_CRC32}
                continue
            content = (f"bootargs=console=ttyS0 root=fstab init={system}/init\n".encode()
                       if name == "bootargs.txt" else (name + " fixture\n").encode())
            (bundle / name).write_bytes(content)
            (bundle / name).chmod(0o444)
            files[name] = self.record(content)
        for name in ("registration", "store-paths", "SHA256SUMS"):
            (bundle / name).write_text("fixture metadata\n")
            (bundle / name).chmod(0o444)
        system.chmod(0o555); bundle.chmod(0o555)
        return bundle, str(system), {"system": str(system), "files": files}

    @staticmethod
    def record(content):
        return {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                "crc32": f"{zlib.crc32(content):08x}"}

    def save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest))

    def replace_artifact(self, name, content):
        path = self.bundle / name
        path.chmod(0o644); path.write_bytes(content); path.chmod(0o444)
        self.manifest["files"][name] = self.record(content)
        self.save_manifest()

    def assert_rejected_before_board(self, error=ValueError, message=None, bundle=None):
        with mock.patch.object(trial, "PrivateSession") as serial_session, \
                mock.patch.object(trial.os, "open") as opened:
            with self.assertRaisesRegex(error, message or "."):
                trial.run_trial(self.manifest_path, self.root / "trial.log", self.root / "result.json",
                                "minimal", bundle or self.bundle, self.report_path)
            serial_session.assert_not_called()
            opened.assert_not_called()
        self.assertFalse((self.root / "trial.log").exists())

    def test_changed_bundle_derives_system_and_threads_metadata_without_mutating_defaults(self):
        bundle, system, manifest = self.make_bundle("3", "4")
        self.manifest_path.write_text(json.dumps(manifest))
        defaults = trial.BUNDLE, trial.SYSTEM
        with mock.patch.object(trial, "PrivateSession") as serial_session:
            prepared = trial.prepare_trial(self.manifest_path, bundle, self.report_path)
            serial_session.assert_not_called()
        self.assertEqual(prepared["system"], system)
        self.assertEqual(prepared["bundle"], bundle)
        self.assertEqual(prepared["normal"]["candidate_system"], system)
        self.assertEqual(prepared["normal"]["metadata_sha256"]["registration"],
                         hashlib.sha256((bundle / "registration").read_bytes()).hexdigest())
        self.assertEqual(prepared["bootargs"].count(" init="), 1)
        self.assertIn("init=" + system + "/init", prepared["bootargs"])
        self.assertEqual((trial.BUNDLE, trial.SYSTEM), defaults)

    def test_manifest_system_mismatch_stops_before_board(self):
        self.manifest["system"] = trial.SYSTEM
        self.save_manifest()
        self.assert_rejected_before_board(message="matching trial system")

    def test_mutable_or_non_store_bundle_selection_stops_before_board(self):
        self.assert_rejected_before_board(message="immutable /nix/store", bundle=self.root)
        self.bundle.chmod(0o755)
        self.assert_rejected_before_board(message="immutable store directory")

    def test_store_alias_and_unsafe_system_target_stop_before_board(self):
        alias = self.store / ("5" * 32 + "-bundle-alias")
        alias.symlink_to(self.bundle, target_is_directory=True)
        self.assert_rejected_before_board(message="immutable store directory", bundle=alias)
        self.bundle.chmod(0o755)
        (self.bundle / "system").unlink()
        (self.bundle / "system").symlink_to(self.root, target_is_directory=True)
        self.bundle.chmod(0o555)
        self.assert_rejected_before_board(message="immutable /nix/store")

    def test_missing_system_symlink_or_init_stops_before_board(self):
        self.bundle.chmod(0o755); (self.bundle / "system").unlink(); self.bundle.chmod(0o555)
        self.assert_rejected_before_board(message="system symlink")
        self.bundle.chmod(0o755)
        (self.bundle / "system").symlink_to(self.system, target_is_directory=True)
        self.bundle.chmod(0o555)
        system = Path(self.system); system.chmod(0o755); (system / "init").unlink(); system.chmod(0o555)
        self.assert_rejected_before_board(FileNotFoundError, "system init")

    def test_missing_load_artifacts_and_metadata_stop_before_board(self):
        for name in ("Image-mainline-drm", "bootargs.txt", "registration", "store-paths", "SHA256SUMS"):
            with self.subTest(name=name):
                path = self.bundle / name; content = path.read_bytes()
                self.bundle.chmod(0o755); path.unlink(); self.bundle.chmod(0o555)
                self.assert_rejected_before_board(FileNotFoundError)
                self.bundle.chmod(0o755); path.write_bytes(content); path.chmod(0o444); self.bundle.chmod(0o555)

    def test_manifest_artifact_sizes_hashes_and_crcs_are_checked_before_board(self):
        original = copy.deepcopy(self.manifest)
        for field, value in (("bytes", 1), ("sha256", "0" * 64), ("crc32", "0" * 8)):
            with self.subTest(field=field):
                self.manifest = copy.deepcopy(original)
                self.manifest["files"]["Image-mainline-drm"][field] = value
                self.save_manifest()
                self.assert_rejected_before_board((ValueError, FileNotFoundError))

    def test_bad_size_types_zero_negative_and_ram_overflow_stop_before_board(self):
        original = copy.deepcopy(self.manifest)
        for size in (0, -1, True, "1", 0x40000000):
            with self.subTest(size=size):
                self.manifest = copy.deepcopy(original)
                self.manifest["files"]["initrd.uimg"]["bytes"] = size
                self.save_manifest()
                self.assert_rejected_before_board(message="size|RAM")

    def test_selected_payload_overlap_stops_before_board(self):
        # This selection's manifest size (not the old fixture's static size)
        # makes the Image overwrite the next loaded payload.
        image = self.bundle / "Image-mainline-drm"
        image.chmod(0o644)
        with image.open("r+b") as stream:
            stream.truncate(0x7000000)
        image.chmod(0o444)
        self.manifest["files"]["Image-mainline-drm"]["bytes"] = 0x7000000
        self.assertEqual(image.stat().st_size, self.manifest["files"]["Image-mainline-drm"]["bytes"])
        self.save_manifest()
        self.assert_rejected_before_board(message="overlap")

    def test_missing_and_extra_manifest_files_stop_before_board(self):
        original = copy.deepcopy(self.manifest)
        del self.manifest["files"]["initrd.uimg"]; self.save_manifest()
        self.assert_rejected_before_board(message="file set")
        self.manifest = original
        self.manifest["files"]["extra"] = {}; self.save_manifest()
        self.assert_rejected_before_board(message="file set")

    def test_duplicate_mismatched_init_rdinit_and_multiline_args_stop_before_board(self):
        for args in (
            f"bootargs=init={self.system}/init init={self.system}/init\n",
            f"bootargs=init=/bad init={self.system}/init\n",
            f"bootargs=init={self.system}/init rdinit=/bin/sh\n",
            f"bootargs=rdinit=/bin/sh init={self.system}/init\n",
            f"bootargs=init={self.system}/init\nextra=value\n",
            f"init={self.system}/init\n",
        ):
            with self.subTest(args=args):
                self.replace_artifact("bootargs.txt", args.encode())
                self.assert_rejected_before_board(message="bootargs")

    def test_protected_normal_pin_kernel_hashes_services_and_boot_id_cannot_be_overridden(self):
        for key, value in (("system", self.system), ("profile", self.system),
                           ("kernel", "/nix/store/other/Image"), ("services", ["active"]),
                           ("boot_id", "invalid"), ("boot_files", {})):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.report); changed[key] = value
                self.report_path.write_text(json.dumps(changed))
                self.assert_rejected_before_board(message="protected normal")
        changed = copy.deepcopy(self.report)
        changed["boot_files"]["Image"]["sha256"] = "0" * 64
        self.report_path.write_text(json.dumps(changed))
        self.assert_rejected_before_board(message="committed baseline")

    def test_missing_report_and_changed_wrapper_fail_before_board(self):
        self.report_path.unlink()
        self.assert_rejected_before_board(FileNotFoundError)
        self.report_path.write_text(json.dumps(self.report))
        original = copy.deepcopy(self.manifest)
        for field, value in (("bytes", 1), ("sha256", "0" * 64), ("crc32", "0" * 8)):
            with self.subTest(field=field):
                self.manifest = copy.deepcopy(original)
                self.manifest["files"]["fw_jump_add_uboot_head.bin"][field] = value
                self.save_manifest()
                self.assert_rejected_before_board(message="stage-one wrapper")

    def test_printed_bootargs_require_exact_unique_complete_value(self):
        expected = trial.trial_bootargs(f"bootargs=init={self.system}/init", self.system)
        good = (expected + "\r\nK230# ").encode()
        self.assertTrue(trial.verified_bootargs(good, expected))
        duplicate = ((expected + "\r\n") * 2 + "K230# ").encode()
        for reply in (None, duplicate, good.replace(b"rdinit=/bin/sh", b"rdinit=/bad"),
                      good.replace(b"\r\n", b"", 1), b"echo " + good):
            self.assertFalse(trial.verified_bootargs(reply, expected))

    def test_cli_threads_explicit_selection_and_preserves_defaults(self):
        for args, bundle, report in (([], trial.BUNDLE, trial.NORMAL_REPORT),
                                   (["--bundle", str(self.bundle), "--normal-report", str(self.report_path)],
                                    self.bundle, self.report_path)):
            with self.subTest(args=args), mock.patch.object(sys, "argv", [str(SCRIPT), *args]), \
                    mock.patch.object(trial, "run_trial", return_value=True) as runner:
                self.assertEqual(trial.main(), 0)
                self.assertEqual(runner.call_args.args[3:], ("minimal", bundle, report))

    def test_outer_label_timeout_records_unknown_and_never_requests_recovery(self):
        normal = trial.prepare_trial(self.manifest_path, self.bundle, self.report_path)["normal"]
        observed = {
            **{key: normal[key] for key in ("system", "profile", "kernel", "uname", "init")},
            "boot_files": {name: info["sha256"] for name, info in normal["boot_files"].items()},
            "boot_id": normal["boot_id"],
        }
        session = mock.Mock()
        session.buffer = trial.PROMPT
        session.wait_for.return_value = True
        session.run_state.return_value = observed
        expected = trial.trial_bootargs((self.bundle / "bootargs.txt").read_text(), self.system,
                                        ignore_unused_clocks=True)
        session.command.side_effect = lambda command, timeout: (
            (expected + "\nK230# ").encode() if command == "printenv bootargs" else trial.PROMPT
        )

        def blocked_label(active_session, token, mode):
            self.assertIs(active_session, session)
            self.assertEqual(mode, "label")
            active_session.write((trial.label_command(token) + "\r").encode())
            raise trial.ProbeProtocolError("label read")

        result_path = self.root / "label.result.json"
        with mock.patch.dict(sys.modules, {"serial": mock.Mock()}), \
                mock.patch.object(trial, "PrivateSession", return_value=session), \
                mock.patch.object(trial, "LOCK_PATH", self.root / "host-fixture.lock"), \
                mock.patch.object(trial, "verified_load", return_value=True), \
                mock.patch.object(trial, "verified_crc", return_value=True), \
                mock.patch.object(trial, "run_probe_protocol", side_effect=blocked_label), \
                mock.patch('sys.stderr'):
            self.assertFalse(trial.run_trial(self.manifest_path, self.root / "label.private.log", result_path,
                                            "label", self.bundle, self.report_path, ignore_unused_clocks=True))
        result = json.loads(result_path.read_text())
        self.assertEqual(result["status"], "recovery-required-unknown-no-reboot-requested")
        self.assertEqual(result["result_schema"], "mainline-initrd-label-unknown-v1")
        self.assertEqual(result["probe"], {"schema": "k230-initrd-label-unknown-v1", "stage": "label read"})
        self.assertTrue(result["ignore_unused_clocks"])
        self.assertIsNone(result["normal_recovery"])
        self.assertFalse(result["reboot_marker_observed"])
        self.assertFalse(result["persistent_boot_selection_changed"])
        session.wait_for_normal_login.assert_not_called()
        session.close.assert_called_once()
        self.assertEqual([call.args[0] for call in session.line.call_args_list],
                         ["reboot", "bootm 0x8000000 0x9000000 0x8400000"])
        self.assertEqual(len(session.write.call_args_list), 2)
        self.assertIn(b"/bin/e2label /dev/mmcblk1p2", session.write.call_args_list[-1].args[0])
        self.assertIn(mock.call(trial.volatile_bootargs_command(True), 15), session.command.call_args_list)


if __name__ == "__main__":
    unittest.main()

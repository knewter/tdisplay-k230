import importlib.util
import copy
import hashlib
import io
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
    def __init__(self, step=0.001):
        self.now = 0.0
        self.step = step

    def __call__(self):
        self.now += self.step
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

    def test_generated_dev_mount_payload_executes_mount_table_and_error_semantics(self):
        import shlex
        import subprocess
        cases = (
            ("proc-only", "proc /proc proc rw 0 0\n", 0, 1, 0),
            ("dev-before-proc", "devtmpfs /dev devtmpfs rw 0 0\nproc /proc proc rw 0 0\n", 0, 0, 0),
            ("missing-table", None, 0, 0, None),
            ("mount-fails", "proc /proc proc rw 0 0\n", 32, 1, 32),
        )
        for shell in ("sh", "bash"):
            for name, table_text, mount_rc, calls, expected_rc in cases:
                with self.subTest(shell=shell, case=name), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    table, mount, log = root / "mounts", root / "stub-mount", root / "mount-calls"
                    if table_text is not None:
                        table.write_text(table_text)
                    mount.write_text(
                        "#!/bin/sh\n" + "printf '%s\\n' \"$*\" >> " + shlex.quote(str(log)) +
                        f"\nexit {mount_rc}\n"
                    )
                    mount.chmod(0o555)
                    # Execute the real generated shell logic; replace only its
                    # fixed input path and mount executable, never host proc/dev.
                    command = trial.label_setup_command(self.token, "dev-mount").replace(
                        "/proc/mounts", shlex.quote(str(table)),
                    ).replace("/bin/mount", shlex.quote(str(mount)))
                    result = subprocess.run([shell, "-c", command], text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    parsed = trial.label_result(result.stdout.encode(), self.token, "dev-mount")
                    self.assertIsNotNone(parsed)
                    if expected_rc is None:
                        self.assertGreater(parsed["rc"], 0)  # Shell redirection failure is preserved.
                    else:
                        self.assertEqual(parsed["rc"], expected_rc)
                    observed_calls = log.read_text().splitlines() if log.exists() else []
                    self.assertEqual(observed_calls, ["-t devtmpfs devtmpfs /dev"] * calls)

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
        for mode in ("minimal", "survey", "root-mount"):
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


class RootMountProbeTests(unittest.TestCase):
    token = "e" * 32

    def label_replies(self, rc=0, match=1):
        helper = LabelProbeTests()
        helper.token = self.token
        return helper.minimal_replies() + helper.setup_replies() + [helper.label_reply(rc, match)]

    def reply(self, stage, rc=0, mounted=None):
        suffix = f" MOUNTED={int(mounted)}" if mounted is not None else ""
        return (f"K230_RDINIT_ROOT_BEGIN {self.token} STAGE={stage}\n"
                f"K230_RDINIT_ROOT_END {self.token} STAGE={stage} RC={rc}{suffix}\n").encode()

    def root_replies(self):
        return [self.reply("unmounted", mounted=False), self.reply("mkdir"), self.reply("empty"),
                self.reply("mount"), self.reply("flags", mounted=True), self.reply("init"),
                self.reply("prepare-root"), self.reply("umount"), self.reply("after-umount", mounted=False)]

    def interleaved_mount_reply(self, token=None, rc=0, split=11):
        # Sanitized shape of the physical capture: only nonce/UUID replaced.
        token = token or self.token
        return (
            f"K230_RDINIT_ROOT_BEGIN {token} STAGE=mount\r\n"
            f"K230_RDINIT_ROOT_END {token[:split]}[    6.030241] EXT4-fs (mmcblk1p2): "
            "mounted filesystem 11111111-2222-3333-4444-555555555555 ro without journal. "
            "Quota mode: disabled.\r\n"
            f"{token[split:]} STAGE=mount RC={rc}\r\n\x1b[?2004hsh-5.3# "
        ).encode()

    def run_protocol(self, replies, system=trial.SYSTEM):
        session = FakeSerialSession(replies + [f"K230_RDINIT_REBOOT {self.token}\n".encode()])
        outcome = trial.run_probe_protocol(session, self.token, "root-mount", timeout=0.2,
                                           clock=FakeClock(0.05), system=system)
        return session, outcome

    def test_success_checks_selected_paths_unmounts_before_reboot_and_never_activates(self):
        system = "/nix/store/" + "3" * 32 + "-selected-system"
        session, outcome = self.run_protocol(self.label_replies() + self.root_replies(), system)
        self.assertTrue(outcome["diagnostic_ok"])
        self.assertEqual(outcome["diagnostic"]["schema"], "k230-initrd-root-mount-v1")
        self.assertEqual(outcome["diagnostic"]["root"]["after-umount"]["rc"], 0)
        commands = [command.decode() for command in session.writes]
        self.assertEqual(sum('/bin/mount -t ext4 -o ro,noload' in c for c in commands), 1)
        self.assertEqual(sum('/bin/umount /sysroot' in c for c in commands), 1)
        self.assertTrue(any(f"test -x /sysroot{system}/init" in c for c in commands))
        self.assertTrue(any(f"test -x /sysroot{system}/prepare-root" in c for c in commands))
        self.assertIn("STAGE=after-umount", commands[-2])
        self.assertIn("/bin/reboot -ff", commands[-1])
        self.assertFalse(any("fsck" in c or "chroot" in c or "activate" in c or "exec " in c for c in commands))

    def test_label_nonmatch_or_error_skips_mount_and_recovers_failed_diagnostic(self):
        for rc, match in ((0, 0), (1, 0)):
            with self.subTest(rc=rc):
                session, outcome = self.run_protocol(self.label_replies(rc, match))
                self.assertFalse(outcome["diagnostic_ok"])
                self.assertEqual(outcome["diagnostic"]["root"], {"attempted": False})
                self.assertFalse(any(b"K230_RDINIT_ROOT" in c for c in session.writes))
                self.assertIn(b"/bin/reboot", session.writes[-1])

    def test_failed_minimal_or_dev_setup_never_starts_root_or_label_child(self):
        helper = LabelProbeTests(); helper.token = self.token
        cases = [helper.minimal_replies()[:1] + [f"K230_RDINIT_TRUE {self.token} RC=1\n".encode()],
                 helper.minimal_replies() + helper.setup_replies()[:2] + [helper.setup_reply("node", 1)]]
        for replies in cases:
            session, outcome = self.run_protocol(replies)
            self.assertTrue(outcome["recovery_required"])
            self.assertFalse(any(b"/bin/e2label" in c or b"K230_RDINIT_ROOT" in c
                                 or b"/bin/reboot" in c for c in session.writes))

    def test_root_preconditions_fail_without_mount_or_path_access(self):
        for index, stage in enumerate(("unmounted", "mkdir", "empty")):
            with self.subTest(stage=stage):
                failure = self.reply(stage, 1, mounted=True if stage == "unmounted" else None)
                session, outcome = self.run_protocol(self.label_replies() + self.root_replies()[:index] + [failure])
                self.assertFalse(outcome["diagnostic_ok"])
                self.assertFalse(outcome["diagnostic"]["root"]["mount"]["attempted"])
                self.assertFalse(any(b"/bin/mount -t ext4" in c or b"test -x /sysroot" in c
                                     or b"/bin/umount" in c for c in session.writes))

    def test_mount_failure_without_observed_mount_skips_paths_and_unmount(self):
        session, outcome = self.run_protocol(self.label_replies() + self.root_replies()[:3] + [
            self.reply("mount", 32), self.reply("flags", 1, mounted=False),
        ])
        self.assertFalse(outcome["diagnostic_ok"])
        self.assertFalse(outcome["diagnostic"]["root"]["init"]["attempted"])
        self.assertFalse(outcome["diagnostic"]["root"]["umount"]["attempted"])
        self.assertFalse(any(b"test -x /sysroot" in c or b"/bin/umount" in c for c in session.writes))

    def test_failed_flags_or_mount_rc_with_observed_mount_cleans_up_without_paths(self):
        for mount_rc in (0, 32):
            with self.subTest(mount_rc=mount_rc):
                session, outcome = self.run_protocol(self.label_replies() + self.root_replies()[:3] + [
                    self.reply("mount", mount_rc), self.reply("flags", 1, mounted=True),
                    self.reply("umount"), self.reply("after-umount", mounted=False),
                ])
                self.assertFalse(outcome["diagnostic_ok"])
                self.assertFalse(any(b"test -x /sysroot" in c for c in session.writes))
                self.assertEqual(sum(b"/bin/umount" in c for c in session.writes), 1)

    def test_path_failure_stops_further_path_checks_but_unmounts_before_recovery(self):
        for index, stage in ((5, "init"), (6, "prepare-root")):
            with self.subTest(stage=stage):
                session, outcome = self.run_protocol(self.label_replies() + self.root_replies()[:index] + [
                    self.reply(stage, 1), self.reply("umount"), self.reply("after-umount", mounted=False),
                ])
                self.assertFalse(outcome["diagnostic_ok"])
                self.assertEqual(outcome["diagnostic"]["root"][stage]["rc"], 1)
                if stage == "init":
                    self.assertFalse(outcome["diagnostic"]["root"]["prepare-root"]["attempted"])
                self.assertIn(b"STAGE=umount", session.writes[-3])

    def test_failed_unmount_is_not_retried_or_reported_as_pass(self):
        session, outcome = self.run_protocol(self.label_replies() + self.root_replies()[:7] + [self.reply("umount", 32)])
        self.assertFalse(outcome["diagnostic_ok"])
        self.assertEqual(sum(b"/bin/umount" in c for c in session.writes), 1)
        self.assertNotIn("after-umount", outcome["diagnostic"]["root"])

    def test_missing_root_markers_stop_without_cleanup_reboot_or_more_input(self):
        stages = ("unmounted", "mkdir", "empty", "mount", "flags", "init", "prepare-root", "umount", "after-umount")
        for index, stage in enumerate(stages):
            with self.subTest(stage=stage):
                session = FakeSerialSession(self.label_replies() + self.root_replies()[:index] + [None])
                with self.assertRaisesRegex(trial.ProbeProtocolError, f"root-mount {stage}"):
                    trial.run_probe_protocol(session, self.token, "root-mount", timeout=0.2, clock=FakeClock(0.05))
                self.assertEqual(len(session.writes), 9 + index)
                self.assertFalse(any(b"/bin/reboot" in c or b"\x03" in c or b"exit" in c for c in session.writes))
                self.assertIn(f"STAGE={stage}".encode(), session.writes[-1])

    def test_root_marker_parsers_reject_stale_echo_duplicate_truncated_and_inconsistent_lines(self):
        for stage in ("unmounted", "after-umount", "flags", "mkdir", "empty", "mount", "init", "prepare-root", "umount"):
            mounted = stage == "flags" if stage in ("unmounted", "after-umount", "flags") else None
            good = self.reply(stage, mounted=mounted)
            self.assertIsNotNone(trial.root_stage_result(good, self.token, stage))
            lines = good.splitlines(keepends=True)
            for bad in (good[:-1], good + good, b"echo " + good, good.replace(self.token.encode(), b"f" * 32),
                        lines[1] + lines[0], lines[0], lines[1], good.replace(b"RC=0", b"RC=256")):
                self.assertIsNone(trial.root_stage_result(bad, self.token, stage))
            if mounted is not None:
                self.assertIsNone(trial.root_stage_result(self.reply(stage, mounted=not mounted), self.token, stage))

    def test_sanitized_captured_mount_interleave_requires_complete_fresh_nonce_and_rc(self):
        token = "0123456789abcdef0123456789abcdef"
        for split in range(1, 32):
            for rc in (0, 32, 255):
                with self.subTest(split=split, rc=rc):
                    capture = self.interleaved_mount_reply(token, rc, split)
                    self.assertEqual(trial.root_stage_result(capture, token, "mount"), {"rc": rc})
        capture = self.interleaved_mount_reply(token)
        end = capture.index(b"\r\n\x1b[?2004h")
        # In particular, no complete printk alone or partial final RC is proof.
        for cut in range(capture.index(b"K230_RDINIT_ROOT_END"), end + 1):
            self.assertIsNone(trial.root_stage_result(capture[:cut], token, "mount"))

    def test_mount_interleave_rejects_other_messages_stages_stale_echo_and_duplicates(self):
        token = "0123456789abcdef0123456789abcdef"
        capture = self.interleaved_mount_reply(token)
        log = (b"[    6.030241] EXT4-fs (mmcblk1p2): mounted filesystem "
               b"11111111-2222-3333-4444-555555555555 ro without journal. Quota mode: disabled.\r\n")
        invalid = [
            capture.replace(b"mmcblk1p2", b"mmcblk0p2"),
            capture.replace(b" ro without", b" r/w without"),
            capture.replace(b"without journal", b"with journal"),
            capture.replace(b"Quota mode: disabled.", b"Quota mode: enabled."),
            capture.replace(b"11111111-2222", b"not-a-uuid-2222"),
            capture.replace(b"[    6.030241]", b"[    6.03]"),
            capture.replace(b"[    6.030241]", b"[         6.030241]"),
            capture.replace(b"[    6.030241]", b"[12345678901.030241]"),
            capture.replace(log, b"[    6.030241] unknown kernel message\r\n"),
            capture.replace(log, log + b"unknown output\r\n"),
            capture.replace(log, log + log),
            capture.replace(b"disabled.", b"disabled"),
            capture.replace(b" STAGE=mount", b" STAGE=init"),
            capture.replace(b"RC=0", b"RC=256"),
            capture.replace(b"RC=0", b"RC=-1"),
            capture.replace(token[:11].encode(), b"f" * 11),
            capture.replace(token[11:].encode(), b"f" * 21),
            capture.replace(token.encode(), b"f" * 32),
            capture.replace(b"K230_RDINIT_ROOT_BEGIN", b"echo K230_RDINIT_ROOT_BEGIN"),
            capture.replace(b"K230_RDINIT_ROOT_END", b"echo K230_RDINIT_ROOT_END"),
            capture + capture,
            capture + self.reply("mount").replace(self.token.encode(), token.encode()),
            trial.root_stage_command(token, "mount").encode(),
        ]
        for output in invalid:
            with self.subTest(output=output):
                self.assertIsNone(trial.root_stage_result(output, token, "mount"))
        for stage in ("init", "prepare-root", "umount"):
            modified = capture.replace(b"STAGE=mount", b"STAGE=" + stage.encode())
            self.assertIsNone(trial.root_stage_result(modified, token, stage))

    def test_complete_mount_interleave_progresses_to_fresh_flags_paths_and_unmount(self):
        replies = self.root_replies()
        replies[3] = self.interleaved_mount_reply()
        # The next real command echo finishes the captured prompt's line.
        replies[4] = trial.root_stage_command(self.token, "flags").encode() + b"\r\n" + replies[4]
        session, outcome = self.run_protocol(self.label_replies() + replies)
        self.assertTrue(outcome["diagnostic_ok"])
        self.assertEqual(outcome["diagnostic"]["root"]["mount"]["rc"], 0)
        self.assertIn(b"STAGE=flags", session.writes[9 + 3])
        self.assertEqual(sum(b"/bin/mount -t ext4" in command for command in session.writes), 1)
        self.assertEqual(sum(b"/bin/umount /sysroot" in command for command in session.writes), 1)
        self.assertIn(b"/bin/reboot -ff", session.writes[-1])

    def test_unknown_mount_interleave_stops_without_flags_cleanup_or_reboot(self):
        reply = self.interleaved_mount_reply().replace(b"Quota mode: disabled.", b"unknown output")
        session = FakeSerialSession(self.label_replies() + self.root_replies()[:3] + [reply])
        with self.assertRaisesRegex(trial.ProbeProtocolError, "root-mount mount"):
            trial.run_probe_protocol(session, self.token, "root-mount", timeout=0.2, clock=FakeClock(0.05))
        self.assertEqual(len(session.writes), 12)
        self.assertIn(b"STAGE=mount", session.writes[-1])
        self.assertFalse(any(b"/bin/umount" in command or b"/bin/reboot" in command for command in session.writes))

    def test_generated_mount_scans_execute_strict_flags_with_false_last_entries(self):
        import shlex
        import subprocess
        good = "/dev/mmcblk1p2 /sysroot ext4 ro,norecovery 0 0\n"
        cases = ((good, 0, True), (good + "proc /proc proc rw 0 0\n", 0, True),
                 (good.replace("norecovery", "noload"), 0, True),
                 (good.replace("ro,norecovery", "errors=remount-ro,norecovery"), 1, True),
                 (good.replace("ro,norecovery", "ro"), 1, True),
                 (good.replace("ext4", "xfs"), 1, True),
                 (good.replace("mmcblk1p2", "mmcblk0p2"), 1, True),
                 (good + good, 1, True), ("proc /proc proc rw 0 0\n", 1, False), (None, None, False))
        for shell in ("sh", "bash"):
            for table_text, rc, mounted in cases:
                with self.subTest(shell=shell, table=table_text), tempfile.TemporaryDirectory() as directory:
                    table = Path(directory) / "mounts"
                    if table_text is not None:
                        table.write_text(table_text)
                    for stage in ("flags", "unmounted", "after-umount"):
                        command = trial.root_stage_command(self.token, stage).replace("/proc/mounts", shlex.quote(str(table)))
                        result = subprocess.run([shell, "-c", command], text=True, capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        parsed = trial.root_stage_result(result.stdout.encode(), self.token, stage)
                        self.assertIsNotNone(parsed)
                        self.assertEqual(parsed["mounted"], mounted)
                        expected_rc = rc if stage == "flags" else int(mounted)
                        if rc is None:
                            self.assertGreater(parsed["rc"], 0)
                        else:
                            self.assertEqual(parsed["rc"], expected_rc)

    def test_generated_mount_and_path_commands_execute_only_host_stubs_and_executable_tests(self):
        import shlex
        import subprocess
        for shell in ("sh", "bash"):
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); sysroot = root / "sysroot"; table = root / "mounts"; log = root / "calls"
                table.write_text("proc /proc proc rw 0 0\n")
                executable_dir = sysroot / trial.SYSTEM.lstrip('/')
                mount, umount = root / "stub-mount", root / "stub-umount"
                mount.write_text("#!/bin/sh\nprintf 'mount %s\\n' \"$*\" >> " + shlex.quote(str(log)) +
                                 "\nprintf '%s\\n' " + shlex.quote(f"/dev/mmcblk1p2 {sysroot} ext4 ro,norecovery 0 0") +
                                 " >> " + shlex.quote(str(table)) + "\n")
                umount.write_text("#!/bin/sh\nprintf 'umount %s\\n' \"$*\" >> " + shlex.quote(str(log)) +
                                  "\nprintf '%s\\n' 'proc /proc proc rw 0 0' > " + shlex.quote(str(table)) + "\n")
                mount.chmod(0o555); umount.chmod(0o555)
                for stage in ("unmounted", "mkdir", "empty", "mount", "flags", "init", "prepare-root", "umount", "after-umount"):
                    if stage == "init":
                        executable_dir.mkdir(parents=True)
                        for name in ("init", "prepare-root"):
                            path = executable_dir / name
                            path.write_text("#!/bin/sh\ntouch " + shlex.quote(str(root / "must-not-execute")) + "\n")
                            path.chmod(0o555)
                    command = trial.root_stage_command(self.token, stage).replace("/sysroot", str(sysroot)).replace(
                        "/proc/mounts", str(table)).replace("/bin/mount", str(mount)).replace("/bin/umount", str(umount))
                    check = subprocess.run([shell, "-c", command], text=True, capture_output=True)
                    self.assertEqual(check.returncode, 0, check.stderr)
                    self.assertEqual(trial.root_stage_result(check.stdout.encode(), self.token, stage)["rc"], 0)
                self.assertEqual(log.read_text().splitlines(),
                                 [f"mount -t ext4 -o ro,noload /dev/mmcblk1p2 {sysroot}", f"umount {sysroot}"])
                self.assertFalse((root / "must-not-execute").exists())


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

    def test_shutdown_conflicts_stop_after_identity_validation_before_board(self):
        for suffix in ("initcall_debug", "initcall_debug=0", "quiet", "debug",
                       "ignore_loglevel", 'dyndbg="+p"', 'reset_k230.dyndbg="+p"',
                       "loglevel=8", "loglevel=invalid"):
            with self.subTest(suffix=suffix):
                self.replace_artifact("bootargs.txt", f"bootargs=init={self.system}/init {suffix}\n".encode())
                with mock.patch.object(trial, "PrivateSession") as serial_session, \
                        mock.patch.object(trial.os, "open") as opened:
                    with self.assertRaisesRegex(ValueError, "conflicting shutdown debug"):
                        trial.run_trial(self.manifest_path, self.root / "unused.log", self.root / "unused.json",
                                        "minimal", self.bundle, self.report_path, debug_shutdown=True)
                    serial_session.assert_not_called(); opened.assert_not_called()

    def test_debug_trial_checks_printed_args_and_records_explicit_selection(self):
        normal = trial.prepare_trial(self.manifest_path, self.bundle, self.report_path)["normal"]
        observed = {
            **{key: normal[key] for key in ("system", "profile", "kernel", "uname", "init")},
            "boot_files": {name: info["sha256"] for name, info in normal["boot_files"].items()},
            "boot_id": normal["boot_id"],
        }
        expected = trial.trial_bootargs((self.bundle / "bootargs.txt").read_text(), self.system,
                                        debug_shutdown=True)
        for matched in (False, True):
            with self.subTest(matched=matched):
                session = mock.Mock(); session.buffer = trial.PROMPT
                session.wait_for.return_value = True; session.run_state.return_value = observed
                printed = expected if matched else expected.replace("loglevel=8", "loglevel=7")
                session.command.side_effect = lambda command, timeout: (
                    (printed + "\nK230# ").encode() if command == "printenv bootargs" else trial.PROMPT
                )
                result_path = self.root / f"debug-{matched}.json"
                with mock.patch.dict(sys.modules, {"serial": mock.Mock()}), \
                        mock.patch.object(trial, "PrivateSession", return_value=session), \
                        mock.patch.object(trial, "LOCK_PATH", self.root / "host-fixture.lock"), \
                        mock.patch.object(trial, "verified_load", return_value=True), \
                        mock.patch.object(trial, "verified_crc", return_value=True), \
                        mock.patch.object(trial, "await_initrd_ready", return_value=True) as ready, \
                        mock.patch.object(trial, "run_probe_protocol", return_value={
                            "diagnostic": {"schema": "k230-initrd-minimal-v2", "true_rc": 1},
                            "diagnostic_ok": False, "recovery_required": True,
                            "recovery_reason": "true-command-nonzero", "reboot_marker": False,
                        }) as probe, mock.patch('sys.stderr'):
                    if matched:
                        self.assertFalse(trial.run_trial(
                            self.manifest_path, self.root / "debug-good.log", result_path,
                            "minimal", self.bundle, self.report_path, debug_shutdown=True,
                        ))
                        result = json.loads(result_path.read_text())
                        self.assertTrue(result["debug_shutdown"])
                        self.assertTrue(result["initrd_readiness_observed"])
                        self.assertEqual(result["candidate_system"], self.system)
                        self.assertFalse(result["persistent_boot_selection_changed"])
                        probe.assert_called_once()
                        ready.assert_called_once_with(session)
                    else:
                        with self.assertRaisesRegex(RuntimeError, "volatile bootargs"):
                            trial.run_trial(self.manifest_path, self.root / "debug-bad.log", result_path,
                                            "minimal", self.bundle, self.report_path, debug_shutdown=True)
                        probe.assert_not_called()
                        ready.assert_not_called()
                        self.assertFalse(any(call.args[0].startswith("bootm") for call in session.line.call_args_list))
                self.assertIn(mock.call(trial.volatile_bootargs_command(False, debug_shutdown=True), 15),
                              session.command.call_args_list)

    def test_minimal_debug_readiness_timeout_records_unknown_without_candidate_input(self):
        self.assert_minimal_unknown("initrd readiness", debug=True, ready=False)

    def test_minimal_reception_failure_records_unknown_without_later_input(self):
        self.assert_minimal_unknown("reception", debug=False, ready=True)

    def test_runtime_unknown_result_preserves_write_ack_and_unverified_parameter_state(self):
        stage = "runtime shutdown trace readback"
        diagnostic = {
            "schema": "k230-initrd-minimal-unknown-v1", "stage": stage, "true_rc": 0,
            "runtime_shutdown_trace": {"attempted": True, "status": "unknown", "failed_stage": "readback",
                                       "stages": {"write": {"rc": 0, "match": True}},
                                       "enable_verified": False, "parameter_state": "UNVERIFIED"},
        }
        self.assert_minimal_unknown(stage, debug=False, ready=True, runtime=True, diagnostic=diagnostic)

    def assert_minimal_unknown(self, stage, *, debug, ready, runtime=False, diagnostic=None):
        normal = trial.prepare_trial(self.manifest_path, self.bundle, self.report_path)["normal"]
        observed = {
            **{key: normal[key] for key in ("system", "profile", "kernel", "uname", "init")},
            "boot_files": {name: info["sha256"] for name, info in normal["boot_files"].items()},
            "boot_id": normal["boot_id"],
        }
        session = mock.Mock(); session.buffer = trial.PROMPT
        session.wait_for.return_value = True; session.run_state.return_value = observed
        expected = trial.trial_bootargs((self.bundle / "bootargs.txt").read_text(), self.system,
                                        debug_shutdown=debug, runtime_shutdown_trace=runtime)
        session.command.side_effect = lambda command, timeout: (
            (expected + "\nK230# ").encode() if command == "printenv bootargs" else trial.PROMPT
        )
        result_path = self.root / f"unknown-{debug}.json"
        with mock.patch.dict(sys.modules, {"serial": mock.Mock()}), \
                mock.patch.object(trial, "PrivateSession", return_value=session), \
                mock.patch.object(trial, "LOCK_PATH", self.root / "host-fixture.lock"), \
                mock.patch.object(trial, "verified_load", return_value=True), \
                mock.patch.object(trial, "verified_crc", return_value=True), \
                mock.patch.object(trial, "await_initrd_ready", return_value=ready) as readiness, \
                mock.patch.object(trial, "run_probe_protocol", side_effect=trial.ProbeProtocolError(stage, diagnostic)) as probe, \
                mock.patch('sys.stderr'):
            self.assertFalse(trial.run_trial(self.manifest_path, self.root / f"unknown-{debug}.log", result_path,
                                            "minimal", self.bundle, self.report_path, debug_shutdown=debug,
                                            runtime_shutdown_trace=runtime))
        result = json.loads(result_path.read_text())
        self.assertEqual(result["status"], "recovery-required-unknown-no-reboot-requested")
        self.assertEqual(result["result_schema"], "mainline-initrd-minimal-unknown-v1")
        self.assertEqual(result["probe"], diagnostic or {"schema": "k230-initrd-minimal-unknown-v1", "stage": stage})
        self.assertEqual(result_path.stat().st_mode & 0o077, 0)
        self.assertIsNone(result["normal_recovery"])
        self.assertFalse(result["reboot_marker_observed"])
        self.assertFalse(result["persistent_boot_selection_changed"])
        session.wait_for_normal_login.assert_not_called()
        session.close.assert_called_once()
        self.assertEqual([call.args[0] for call in session.line.call_args_list],
                         ["reboot", "bootm 0x8000000 0x9000000 0x8400000"])
        # The sole raw write prepares the normal serial prompt, before candidate
        # Linux. No external probe, exit, retry or candidate reboot is sent.
        self.assertEqual(session.write.call_args_list, [mock.call(b"\x03\r")])
        self.assertEqual(result["initrd_readiness_observed"], ready)
        readiness.assert_called_once_with(session)
        if ready:
            probe.assert_called_once()
        else:
            probe.assert_not_called()
        if debug:
            self.assertTrue(result["debug_shutdown"])
        if runtime:
            self.assertTrue(result["runtime_shutdown_trace"])
            self.assertTrue(probe.call_args.kwargs["runtime_shutdown_trace"])
            self.assertNotIn("initcall_debug", expected)
            self.assertNotIn("loglevel=8", expected)

    def test_outer_label_timeout_records_unknown_and_never_requests_recovery(self):
        self.assert_outer_readonly_timeout("label")

    def test_outer_root_mount_timeout_records_unknown_without_unmount_or_reboot(self):
        self.assert_outer_readonly_timeout("root-mount")

    def test_normal_return_timeout_preserves_complete_runtime_probe_without_more_input(self):
        self.assert_normal_return_timeout(ignore_clocks=False)

    def test_clock_comparison_timeout_preserves_runtime_trace_and_explicit_selector(self):
        self.assert_normal_return_timeout(ignore_clocks=True)

    def assert_normal_return_timeout(self, *, ignore_clocks):
        helper = RuntimeShutdownTraceTests()
        _, outcome = helper.run_protocol(helper.minimal_replies() + [helper.reply(i) for i in range(6)] +
                                         [f"K230_RDINIT_REBOOT {helper.token}\n".encode()])
        normal = trial.prepare_trial(self.manifest_path, self.bundle, self.report_path)["normal"]
        observed = {
            **{key: normal[key] for key in ("system", "profile", "kernel", "uname", "init")},
            "boot_files": {name: info["sha256"] for name, info in normal["boot_files"].items()},
            "boot_id": normal["boot_id"],
        }
        session = mock.Mock(); session.buffer = trial.PROMPT
        session.wait_for.return_value = True; session.run_state.return_value = observed
        session.wait_for_normal_login.return_value = None
        expected = trial.trial_bootargs((self.bundle / "bootargs.txt").read_text(), self.system,
                                        runtime_shutdown_trace=True, ignore_unused_clocks=ignore_clocks)
        session.command.side_effect = lambda command, timeout: (
            (expected + "\nK230# ").encode() if command == "printenv bootargs" else trial.PROMPT
        )
        def probe(active, token, mode, **kwargs):
            active.write((trial.reboot_command(helper.token) + "\r").encode())
            return outcome
        result_path = self.root / "normal-timeout.json"
        with mock.patch.dict(sys.modules, {"serial": mock.Mock()}), \
                mock.patch.object(trial, "PrivateSession", return_value=session), \
                mock.patch.object(trial, "LOCK_PATH", self.root / "host-fixture.lock"), \
                mock.patch.object(trial, "verified_load", return_value=True), \
                mock.patch.object(trial, "verified_crc", return_value=True), \
                mock.patch.object(trial, "await_initrd_ready", return_value=True), \
                mock.patch.object(trial, "run_probe_protocol", side_effect=probe), mock.patch('sys.stderr'):
            self.assertFalse(trial.run_trial(self.manifest_path, self.root / "normal-timeout.log", result_path,
                                            "minimal", self.bundle, self.report_path, runtime_shutdown_trace=True,
                                            ignore_unused_clocks=ignore_clocks))
        result = json.loads(result_path.read_text())
        self.assertEqual(result["status"], "recovery-required-normal-return-timeout")
        self.assertEqual(result["probe"], outcome["diagnostic"])
        self.assertTrue(result["probe"]["runtime_shutdown_trace"]["enable_verified"])
        self.assertEqual(result["probe"]["runtime_shutdown_trace"]["parameter_state"], "Y")
        self.assertEqual(len(result["probe"]["runtime_shutdown_trace"]["stages"]), 6)
        self.assertTrue(result["reboot_marker_observed"])
        self.assertTrue(result["initrd_readiness_observed"])
        self.assertEqual(result["ignore_unused_clocks"], ignore_clocks)
        self.assertTrue(result["runtime_shutdown_trace"])
        self.assertIn(mock.call(trial.volatile_bootargs_command(ignore_clocks), 15), session.command.call_args_list)
        self.assertNotIn("initcall_debug", expected)
        self.assertNotIn("loglevel=8", expected)
        self.assertIsNone(result["normal_recovery"])
        self.assertFalse(result["persistent_boot_selection_changed"])
        self.assertEqual(result["normal_return_timeout_seconds"], 180)
        self.assertEqual(result_path.stat().st_mode & 0o077, 0)
        session.wait_for_normal_login.assert_called_once_with(180)
        self.assertEqual(session.run_state.call_count, 1)
        self.assertEqual(session.upload_text.call_count, 2)
        self.assertEqual(session.wait_for.call_args_list, [mock.call(b"root@nixos", 15),
                                                        mock.call(b"Linux version 7.3.0-rc5", 45)])
        self.assertEqual(session.write.call_args_list,
                         [mock.call(b"\x03\r"), mock.call((trial.reboot_command(helper.token) + "\r").encode())])
        self.assertEqual([call.args[0] for call in session.line.call_args_list],
                         ["reboot", "bootm 0x8000000 0x9000000 0x8400000"])

    def test_all_modes_pump_verbose_boot_before_any_receipt_or_external_child(self):
        self.assert_all_mode_readiness(ready=True)

    def test_all_modes_readiness_timeout_records_unknown_without_candidate_input(self):
        self.assert_all_mode_readiness(ready=False)

    def assert_all_mode_readiness(self, *, ready):
        normal = trial.prepare_trial(self.manifest_path, self.bundle, self.report_path)["normal"]
        observed = {
            **{key: normal[key] for key in ("system", "profile", "kernel", "uname", "init")},
            "boot_files": {name: info["sha256"] for name, info in normal["boot_files"].items()},
            "boot_id": normal["boot_id"],
        }
        original_ready = trial.await_initrd_ready
        original_probe = trial.run_probe_protocol
        for index, (mode, flags) in enumerate((("minimal", {}), ("minimal", {"runtime_shutdown_trace": True}),
                            ("minimal", {"runtime_shutdown_trace": True, "ignore_unused_clocks": True}),
                            ("minimal", {"debug_shutdown": True}), ("label", {}),
                            ("label", {"ignore_unused_clocks": True}), ("root-mount", {}), ("survey", {}))):
            with self.subTest(mode=mode, flags=flags, ready=ready):
                pending = []
                candidate = False
                clock = FakeClock(step=1)
                port = mock.Mock()
                port.read.side_effect = lambda size: pending.pop(0) if pending else b""
                serial = mock.Mock(); serial.Serial.return_value = port
                session = trial.PrivateSession(serial, io.BytesIO())
                session.wait_for = mock.Mock(return_value=True)
                session.upload_text = mock.Mock()
                session.run_state = mock.Mock(return_value=observed)
                session.wait_for_normal_login = mock.Mock()
                expected = trial.trial_bootargs((self.bundle / "bootargs.txt").read_text(), self.system, **flags)
                session.command = mock.Mock(side_effect=lambda command, timeout: (
                    (expected + "\nK230# ").encode() if command == "printenv bootargs" else trial.PROMPT
                ))

                def line(command, *, interrupt):
                    nonlocal candidate
                    session.buffer = b"Hit any key to stop autoboot\n" + trial.PROMPT
                    if command.startswith("bootm "):
                        candidate = True
                        session.buffer = InitrdReadinessTests.banner
                        pending.extend([b"[ 2.0] boot trace\n" + b"x" * 10000 + b"\n"] * 18)
                        if ready:
                            pending.extend([InitrdReadinessTests.ready, InitrdReadinessTests.warnings,
                                            b"sh-5.", b"3# "])
                session.line = mock.Mock(side_effect=line)
                candidate_writes = []

                def write(data):
                    if not candidate:
                        return
                    self.assertGreater(clock.now, 8)
                    if not candidate_writes:
                        self.assertTrue(session.log.getvalue().endswith(InitrdReadinessTests.prompt))
                    candidate_writes.append(data)
                    text = data.decode()
                    if "K230_RDINIT_RX " in text:
                        token = text.split("K230_RDINIT_RX ")[1][:32]
                        pending.append(data + f"\nK230_RDINIT_RX {token}\n".encode())
                    elif "K230_RDINIT_TRUE " in text:
                        token = text.split("K230_RDINIT_TRUE ")[1][:32]
                        pending.append(f"K230_RDINIT_TRUE {token} RC=1\n".encode())
                    else:
                        self.fail("external child, trace toggle or reboot reached after nonzero true")
                port.write.side_effect = write
                result_path = self.root / f"all-readiness-{index}.json"
                with mock.patch.dict(sys.modules, {"serial": serial}), \
                        mock.patch.object(trial, "PrivateSession", return_value=session), \
                        mock.patch.object(trial, "LOCK_PATH", self.root / "host-fixture.lock"), \
                        mock.patch.object(trial, "verified_load", return_value=True), \
                        mock.patch.object(trial, "verified_crc", return_value=True), \
                        mock.patch.object(trial, "await_initrd_ready", side_effect=lambda active: original_ready(active, clock=clock)), \
                        mock.patch.object(trial, "run_probe_protocol", side_effect=lambda *args, **kwargs: original_probe(
                            *args, **kwargs, timeout=0.05, clock=FakeClock())) as probe, \
                        mock.patch('sys.stderr'):
                    self.assertFalse(trial.run_trial(self.manifest_path, self.root / f"all-readiness-{index}.log", result_path,
                                                    mode, self.bundle, self.report_path, **flags))
                result = json.loads(result_path.read_text())
                self.assertEqual(result["initrd_readiness_observed"], ready)
                self.assertIsNone(result["normal_recovery"])
                session.wait_for_normal_login.assert_not_called()
                if ready:
                    probe.assert_called_once()
                    self.assertEqual(len(candidate_writes), 2)
                    self.assertEqual(result["recovery_reason"], "true-command-nonzero")
                else:
                    probe.assert_not_called()
                    self.assertEqual(candidate_writes, [])
                    self.assertEqual(result["status"], "recovery-required-unknown-no-reboot-requested")
                    self.assertEqual(result["probe"]["stage"], "initrd readiness")
                    self.assertEqual(result["result_schema"], f"mainline-initrd-{mode}-unknown-v1")

    def assert_outer_readonly_timeout(self, mode):
        clock_flag = mode == "label"
        blocked_stage = "label read" if clock_flag else "root-mount mount"
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
                                        ignore_unused_clocks=clock_flag)
        session.command.side_effect = lambda command, timeout: (
            (expected + "\nK230# ").encode() if command == "printenv bootargs" else trial.PROMPT
        )

        def blocked_probe(active_session, token, selected_mode, *, system):
            self.assertIs(active_session, session)
            self.assertEqual(selected_mode, mode)
            self.assertEqual(system, self.system)
            command = (trial.label_command(token) if clock_flag else trial.root_stage_command(token, "mount", system))
            active_session.write((command + "\r").encode())
            raise trial.ProbeProtocolError(blocked_stage)

        result_path = self.root / f"{mode}.result.json"
        with mock.patch.dict(sys.modules, {"serial": mock.Mock()}), \
                mock.patch.object(trial, "PrivateSession", return_value=session), \
                mock.patch.object(trial, "LOCK_PATH", self.root / "host-fixture.lock"), \
                mock.patch.object(trial, "verified_load", return_value=True), \
                mock.patch.object(trial, "verified_crc", return_value=True), \
                mock.patch.object(trial, "await_initrd_ready", return_value=True) as readiness, \
                mock.patch.object(trial, "run_probe_protocol", side_effect=blocked_probe), \
                mock.patch('sys.stderr'):
            self.assertFalse(trial.run_trial(self.manifest_path, self.root / f"{mode}.private.log", result_path,
                                            mode, self.bundle, self.report_path, ignore_unused_clocks=clock_flag))
        result = json.loads(result_path.read_text())
        self.assertEqual(result["status"], "recovery-required-unknown-no-reboot-requested")
        self.assertEqual(result["result_schema"], f"mainline-initrd-{mode}-unknown-v1")
        self.assertEqual(result["probe"], {"schema": f"k230-initrd-{mode}-unknown-v1", "stage": blocked_stage})
        readiness.assert_called_once_with(session)
        self.assertTrue(result["initrd_readiness_observed"])
        if clock_flag:
            self.assertTrue(result["ignore_unused_clocks"])
        else:
            self.assertNotIn("ignore_unused_clocks", result)
        self.assertIsNone(result["normal_recovery"])
        self.assertFalse(result["reboot_marker_observed"])
        self.assertFalse(result["persistent_boot_selection_changed"])
        session.wait_for_normal_login.assert_not_called()
        session.close.assert_called_once()
        self.assertEqual([call.args[0] for call in session.line.call_args_list],
                         ["reboot", "bootm 0x8000000 0x9000000 0x8400000"])
        self.assertEqual(len(session.write.call_args_list), 2)
        expected_child = b"/bin/e2label /dev/mmcblk1p2" if clock_flag else b"/bin/mount -t ext4 -o ro,noload"
        self.assertIn(expected_child, session.write.call_args_list[-1].args[0])
        self.assertIn(mock.call(trial.volatile_bootargs_command(clock_flag), 15), session.command.call_args_list)


class ShutdownDebugTests(unittest.TestCase):
    def test_volatile_args_preserve_init_and_require_exact_debug_selection(self):
        original = f"bootargs=console=ttyS0 loglevel=4 loglevel=7 init={trial.SYSTEM}/init"
        expected = trial.trial_bootargs(original, debug_shutdown=True)
        self.assertEqual(expected, original + " rdinit=/bin/sh initcall_debug loglevel=8")
        self.assertEqual(trial.volatile_bootargs_command(debug_shutdown=True),
                         'setenv bootargs "${bootargs} rdinit=/bin/sh initcall_debug loglevel=8"')
        self.assertTrue(trial.verified_bootargs((expected + "\n").encode(), expected))
        for bad in (trial.trial_bootargs(original), expected.replace("loglevel=8", "loglevel=7"),
                    expected.replace("initcall_debug", "initcall_debug=0"),
                    expected.replace(trial.SYSTEM, "/nix/store/wrong-system"),
                    expected + " clk_ignore_unused", expected + "\n" + expected):
            self.assertFalse(trial.verified_bootargs((bad + "\n").encode(), expected))
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            trial.trial_bootargs(original, debug_shutdown=True, ignore_unused_clocks=True)

    def test_flag_is_minimal_only_before_preparation_and_serial(self):
        for mode in ("survey", "label", "root-mount"):
            with self.subTest(mode=mode), mock.patch.object(trial, "prepare_trial") as prepare, \
                    mock.patch.object(trial, "PrivateSession") as session, mock.patch.object(trial.os, "open") as opened:
                with self.assertRaisesRegex(ValueError, "requires --mode minimal"):
                    trial.run_trial(Path('/missing'), Path('/unused'), Path('/unused-result'), mode,
                                    debug_shutdown=True)
                prepare.assert_not_called(); session.assert_not_called(); opened.assert_not_called()
            with mock.patch.object(sys, "argv", [str(SCRIPT), "--mode", mode, "--debug-shutdown"]), \
                    mock.patch.object(trial, "run_trial") as runner, mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:
                    trial.main()
                self.assertEqual(error.exception.code, 2); runner.assert_not_called()

    def test_cli_threads_only_explicit_minimal_debug_flag(self):
        with mock.patch.object(sys, "argv", [str(SCRIPT), "--mode", "minimal", "--debug-shutdown"]), \
                mock.patch.object(trial, "run_trial", return_value=True) as runner:
            self.assertEqual(trial.main(), 0)
            self.assertEqual(runner.call_args.args[3], "minimal")
            self.assertEqual(runner.call_args.kwargs, {"debug_shutdown": True})


class RecoveryStreamingTests(unittest.TestCase):
    token = "a" * 32

    def recovery_session(self, reboot_suffix=b""):
        """Run the real capped pump and protocol with a scripted serial port."""
        token = self.token
        stale = b"\nnixos login:\nRunning in chroot, ignoring request.\n"
        replies = [
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {token}\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\n".encode(),
            b"d" * 131072 + stale + f"K230_RDINIT_UP_BEGIN {token}\n1.0 2.0\nK230_RDINIT_UP_END {token} RC=0\n".encode(),
            f"K230_RDINIT_REBOOT {token}\n".encode() + reboot_suffix,
        ]
        pending = []
        port = mock.Mock()
        def write(data):
            reply = replies.pop(0)
            pending.extend(reply[i:i + 65536] for i in range(0, len(reply), 65536))
        port.write.side_effect = write
        port.read.side_effect = lambda size: pending.pop(0) if pending else b""
        serial = mock.Mock(); serial.Serial.return_value = port
        session = trial.PrivateSession(serial, io.BytesIO())
        outcome = trial.run_probe_protocol(session, token, "minimal", timeout=0.05, clock=FakeClock())
        self.assertTrue(outcome["diagnostic_ok"]); self.assertTrue(outcome["reboot_marker"])
        self.assertNotIn(stale, session.buffer)
        self.assertIn(stale, session.log.getvalue())
        return session, pending

    def wait(self, session):
        with mock.patch.object(trial.time, "monotonic", FakeClock()):
            return session.wait_for_normal_login(0.02)

    def test_fresh_login_survives_cap_rollover_and_split_marker(self):
        session, pending = self.recovery_session()
        pending.extend([b"d" * 65536] * 3 + [b"\nnixos log", b"in:\n"])
        self.assertEqual(self.wait(session), "login")
        self.assertEqual(len(session.buffer), 131072)

    def test_fresh_refusal_survives_rollover_and_split_marker(self):
        session, pending = self.recovery_session()
        pending.extend([b"d" * 65536] * 3 + [b"\nRunning in chroot, ", b"ignoring request.\n"])
        self.assertEqual(self.wait(session), "chroot-refusal")

    def test_pretrial_markers_and_echoed_refusal_do_not_satisfy_recovery(self):
        session, pending = self.recovery_session()
        pending.extend([b"d" * 65536] * 3 + [
            b"\nprintf 'Running in chroot, ignoring request.\\n'\n",
            b"echo nixos login:\n",
        ])
        self.assertIsNone(self.wait(session))

    def test_fresh_login_already_received_is_checked_before_another_read(self):
        session, pending = self.recovery_session(b"nixos login:\n")
        pending.append(b"d" * 131072)
        self.assertEqual(self.wait(session), "login")
        self.assertEqual(len(pending), 1)


class RuntimeShutdownTraceTests(unittest.TestCase):
    token = "e" * 32

    def minimal_replies(self):
        helper = LabelProbeTests(); helper.token = self.token
        return helper.minimal_replies()

    def stage_token(self, index):
        return f"{index + 1:032x}"

    def reply(self, index, rc=0, match=1):
        token, stage = self.stage_token(index), trial.RUNTIME_TRACE_STAGES[index]
        return (f"K230_RDINIT_TRACE_BEGIN {token} STAGE={stage}\n"
                f"K230_RDINIT_TRACE_END {token} STAGE={stage} RC={rc} MATCH={match}\n").encode()

    def run_protocol(self, replies):
        session = FakeSerialSession(replies)
        tokens = iter(self.stage_token(i) for i in range(6))
        outcome = trial.run_probe_protocol(session, self.token, "minimal", runtime_shutdown_trace=True,
                                           token_factory=lambda: next(tokens), timeout=0.02, clock=FakeClock())
        return session, outcome

    def test_complete_protocol_enables_only_after_minimal_and_prior_gates_then_reboots_once(self):
        session, outcome = self.run_protocol(
            self.minimal_replies() + [self.reply(i) for i in range(6)] +
            [f"K230_RDINIT_REBOOT {self.token}\n".encode()]
        )
        trace = outcome["diagnostic"]["runtime_shutdown_trace"]
        self.assertTrue(trace["enable_verified"]); self.assertEqual(trace["parameter_state"], "Y")
        self.assertTrue(outcome["diagnostic_ok"]); self.assertTrue(outcome["reboot_marker"])
        self.assertEqual(len(session.writes), 11)
        for index, stage in enumerate(trial.RUNTIME_TRACE_STAGES):
            self.assertIn(f"STAGE={stage}".encode(), session.writes[4 + index])
            self.assertIn(self.stage_token(index).encode(), session.writes[4 + index])
        writes = [i for i, command in enumerate(session.writes) if b"printf '1\\n' >" in command]
        self.assertEqual(writes, [8])
        self.assertIn(b"/bin/reboot -ff", session.writes[-1])
        self.assertFalse(any(b"/bin/reboot" in command for command in session.writes[:-1]))

    def test_known_nonzero_or_bad_match_stops_at_each_stage_without_next_input(self):
        for index in range(6):
            for rc, match in ((7, 0), (0, 0)):
                with self.subTest(stage=index, rc=rc):
                    session, outcome = self.run_protocol(
                        self.minimal_replies() + [self.reply(i) for i in range(index)] + [self.reply(index, rc, match)]
                    )
                    trace = outcome["diagnostic"]["runtime_shutdown_trace"]
                    self.assertEqual(trace["status"], "failed")
                    self.assertEqual(trace["stages"][trial.RUNTIME_TRACE_STAGES[index]], {"rc": rc, "match": False})
                    self.assertFalse(trace["enable_verified"])
                    self.assertTrue(outcome["recovery_required"]); self.assertFalse(outcome["reboot_marker"])
                    self.assertEqual(len(session.writes), 5 + index)
                    self.assertFalse(any(b"/bin/reboot" in command for command in session.writes))
                    if index < 4:
                        self.assertFalse(any(b"printf '1\\n' >" in command for command in session.writes))
                    else:
                        self.assertEqual(trace["parameter_state"], "UNVERIFIED")

    def test_timeouts_keep_partial_gates_and_unknown_parameter_after_write(self):
        for index in range(6):
            with self.subTest(stage=index):
                session = FakeSerialSession(self.minimal_replies() + [self.reply(i) for i in range(index)] + [None])
                tokens = iter(self.stage_token(i) for i in range(6))
                with self.assertRaises(trial.ProbeProtocolError) as caught:
                    trial.run_probe_protocol(session, self.token, "minimal", runtime_shutdown_trace=True,
                                             token_factory=lambda: next(tokens), timeout=0.01, clock=FakeClock())
                trace = caught.exception.diagnostic["runtime_shutdown_trace"]
                self.assertEqual(trace["status"], "unknown"); self.assertEqual(len(trace["stages"]), index)
                self.assertFalse(trace["enable_verified"])
                self.assertEqual(len(session.writes), 5 + index)
                self.assertFalse(any(b"/bin/reboot" in command for command in session.writes))
                if index >= 4:
                    self.assertEqual(trace["parameter_state"], "UNVERIFIED")
                if index == 5:
                    self.assertEqual(trace["stages"]["write"], {"rc": 0, "match": True})

    def test_parser_rejects_stale_echo_duplicate_truncated_inconsistent_and_malformed(self):
        good = self.reply(0); token = self.stage_token(0)
        self.assertEqual(trial.runtime_trace_result(good, token, "sys-mkdir"), {"rc": 0, "match": True})
        for bad in (good.replace(token.encode(), b"a" * 32), b"echo " + good,
                    good + good, good.rstrip(b"\n"), good.replace(b"RC=0", b"RC=256"),
                    good.replace(b"RC=0", b"RC=1"), good.replace(b"MATCH=1", b"MATCH=2"),
                    good.replace(b"RC=0", b"RC=bad"), good + good.splitlines(keepends=True)[1].replace(b"RC=0", b"RC=bad"),
                    b"\n".join(reversed(good.splitlines())) + b"\n", self.reply(1)):
            with self.subTest(bad=bad):
                self.assertIsNone(trial.runtime_trace_result(bad, token, "sys-mkdir"))

    def test_duplicate_final_marker_cannot_advance_protocol_to_toggle(self):
        session = FakeSerialSession(self.minimal_replies() + [self.reply(0) + self.reply(0)])
        with self.assertRaises(trial.ProbeProtocolError):
            trial.run_probe_protocol(session, self.token, "minimal", runtime_shutdown_trace=True,
                                     token_factory=lambda: self.stage_token(0), timeout=0.01, clock=FakeClock())
        self.assertEqual(len(session.writes), 5)
        self.assertFalse(any(b"printf '1\\n' >" in command or b"/bin/reboot" in command for command in session.writes))

    def test_failed_minimal_gates_never_begin_sysfs_or_toggle(self):
        for index in (1, 2, 3):
            with self.subTest(index=index):
                replies = self.minimal_replies()
                field = b"MOUNT_RC=0" if index == 2 else b"RC=0"
                replies[index] = replies[index].replace(field, field.replace(b"=0", b"=1"))
                session, outcome = self.run_protocol(replies)
                self.assertFalse(outcome["diagnostic"]["runtime_shutdown_trace"]["attempted"])
                self.assertEqual(len(session.writes), index + 1)
                self.assertFalse(any(b"K230_RDINIT_TRACE" in command or b"/bin/reboot" in command for command in session.writes))

    def test_stage_timeout_is_validated_before_any_write(self):
        for timeout in (0, -1, 21, float('nan'), float('inf')):
            with self.subTest(timeout=timeout):
                session = FakeSerialSession([])
                with self.assertRaisesRegex(ValueError, "positive, finite"):
                    trial.run_runtime_shutdown_trace(session, self.token, timeout=timeout)
                self.assertEqual(session.writes, [])

    def execute_stage(self, stage, *, mounts="", value=None, mount_rc=0, shell="sh"):
        import subprocess
        import shlex
        with tempfile.TemporaryDirectory(dir=Path.home() / "tmp") as temporary:
            root = Path(temporary)
            target, table, parameter, calls = (root / name for name in ("target", "mount-table", "parameter", "calls"))
            if mounts is not None:
                table.write_text(mounts.replace("/sys", str(target)))
            if value is not None:
                parameter.write_text(value)
            mkdir_stub, mount_stub = root / "mkdir-stub", root / "mount-stub"
            mkdir_stub.write_text(
                f"#!{sys.executable}\nfrom pathlib import Path\nimport sys\n"
                f"assert sys.argv[-1] == {str(target)!r}\n"
                f"Path({str(target)!r}).mkdir(exist_ok=True)\n"
                f"Path({str(calls)!r}).write_text('mkdir\\n')\n"
            )
            mount_stub.write_text(
                f"#!{sys.executable}\nfrom pathlib import Path\nimport sys\n"
                f"assert sys.argv[1:] == ['-t', 'sysfs', '-o', 'nosuid,nodev,noexec', 'sysfs', {str(target)!r}]\n"
                f"Path({str(calls)!r}).write_text('mount\\n')\n"
                f"if {mount_rc} == 0:\n"
                f" with Path({str(table)!r}).open('a') as stream: stream.write('sysfs {str(target)} sysfs rw 0 0\\n')\n"
                f"sys.exit({mount_rc})\n"
            )
            mkdir_stub.chmod(0o755); mount_stub.chmod(0o755)
            command = trial.runtime_trace_command(self.stage_token(0), stage)
            # Every target path and host-affecting utility is isolated before
            # shell execution. Neither real mount/mkdir nor host sysfs is used.
            for original, replacement in (
                (trial.RUNTIME_TRACE_PARAMETER, parameter), ("/proc/mounts", table),
                ("/bin/mkdir", mkdir_stub), ("/bin/mount", mount_stub), ("/sys", target),
            ):
                command = command.replace(original, shlex.quote(str(replacement)))
            for original in (trial.RUNTIME_TRACE_PARAMETER, "/proc/mounts", "/bin/mkdir", "/bin/mount"):
                self.assertNotIn(original, command)
            completed = subprocess.run([shell, "-c", command], text=True, capture_output=True, timeout=5)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stderr, "")
            parsed = trial.runtime_trace_result(completed.stdout.encode(), self.stage_token(0), stage)
            self.assertIsNotNone(parsed, completed.stdout)
            return parsed, calls.read_text() if calls.exists() else "", parameter.read_text() if parameter.exists() else None

    def test_generated_commands_execute_isolated_mount_scans_and_preserve_redirection_failure(self):
        for shell in ("bash", "sh"):
            for table, expected, mounted in (
                ("sysfs /sys sysfs rw 0 0\nproc /proc proc rw 0 0\n", True, False),
                ("sysfs /sys sysfs rw 0 0\nsysfs /sys sysfs rw 0 0\n", False, False),
                ("tmpfs /sys tmpfs rw 0 0\n", False, False),
                ("proc /proc proc rw 0 0\n", True, True),
            ):
                with self.subTest(shell=shell, table=table):
                    result, calls, _ = self.execute_stage("sys-mount", mounts=table, shell=shell)
                    self.assertEqual(result, {"rc": 0, "match": expected})
                    self.assertEqual(calls, "mount\n" if mounted else "")
            result, calls, _ = self.execute_stage("sys-mount", mounts=None, shell=shell)
            self.assertNotEqual(result["rc"], 0); self.assertFalse(result["match"]); self.assertEqual(calls, "")
            result, calls, _ = self.execute_stage("sys-mount", mount_rc=7, shell=shell)
            self.assertEqual(result, {"rc": 7, "match": False}); self.assertEqual(calls, "mount\n")

    def test_generated_read_write_commands_require_exact_values_and_keep_return_codes(self):
        for shell in ("bash", "sh"):
            result, calls, _ = self.execute_stage("sys-mkdir", shell=shell)
            self.assertEqual(result, {"rc": 0, "match": True}); self.assertEqual(calls, "mkdir\n")
            for stage, value, match in (("prior", "N\n", True), ("prior", "Y\n", False),
                                        ("prior", "N\nY\n", False), ("prior", "N", False),
                                        ("readback", "Y\n", True), ("readback", "1\n", False)):
                with self.subTest(shell=shell, stage=stage, value=value):
                    result, calls, _ = self.execute_stage(stage, value=value, shell=shell)
                    self.assertEqual(result["match"], match); self.assertEqual(calls, "")
            result, _, _ = self.execute_stage("prior", shell=shell)
            self.assertNotEqual(result["rc"], 0); self.assertFalse(result["match"])
            result, _, _ = self.execute_stage("permissions", shell=shell)
            self.assertNotEqual(result["rc"], 0); self.assertFalse(result["match"])
            result, _, _ = self.execute_stage("permissions", value="N\n", shell=shell)
            self.assertEqual(result, {"rc": 0, "match": True})
            result, _, after = self.execute_stage("write", value="N\n", shell=shell)
            self.assertEqual(result, {"rc": 0, "match": True}); self.assertEqual(after, "1\n")

    def test_runtime_bootargs_are_ordinary_and_boot_debug_is_exclusive_minimal_only(self):
        original = f"bootargs=loglevel=4 loglevel=7 init={trial.SYSTEM}/init"
        self.assertEqual(trial.trial_bootargs(original, runtime_shutdown_trace=True), trial.trial_bootargs(original))
        with self.assertRaisesRegex(ValueError, "conflicting shutdown debug"):
            trial.trial_bootargs(original + " initcall_debug", runtime_shutdown_trace=True)
        for mode, kwargs in (("survey", {}), ("label", {}), ("root-mount", {}),
                             ("survey", {"ignore_unused_clocks": True}), ("root-mount", {"ignore_unused_clocks": True}),
                             ("minimal", {"debug_shutdown": True})):
            with self.subTest(mode=mode, kwargs=kwargs), mock.patch.object(trial, "prepare_trial") as prepare, \
                    mock.patch.object(trial, "PrivateSession") as serial:
                with self.assertRaises(ValueError):
                    trial.run_trial(Path('/missing'), Path('/unused'), Path('/unused-result'), mode,
                                    runtime_shutdown_trace=True, **kwargs)
                prepare.assert_not_called(); serial.assert_not_called()
        for args in (["--mode", "label", "--runtime-shutdown-trace"],
                     ["--runtime-shutdown-trace", "--debug-shutdown"],
                     ["--mode", "root-mount", "--runtime-shutdown-trace", "--ignore-unused-clocks"],
                     ["--mode", "survey", "--runtime-shutdown-trace", "--ignore-unused-clocks"]):
            with mock.patch.object(sys, "argv", [str(SCRIPT), *args]), \
                    mock.patch.object(trial, "run_trial") as runner, mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit): trial.main()
                runner.assert_not_called()
        with mock.patch.object(sys, "argv", [str(SCRIPT), "--runtime-shutdown-trace"]), \
                mock.patch.object(trial, "run_trial", return_value=True) as runner:
            self.assertEqual(trial.main(), 0)
            self.assertEqual(runner.call_args.kwargs, {"runtime_shutdown_trace": True})

    def test_minimal_runtime_clock_comparison_is_exact_volatile_and_debug_conflicts_remain(self):
        original = f"bootargs=loglevel=4 loglevel=7 init={trial.SYSTEM}/init"
        ordinary = trial.trial_bootargs(original, runtime_shutdown_trace=True)
        compared = trial.trial_bootargs(original, runtime_shutdown_trace=True, ignore_unused_clocks=True)
        self.assertEqual(compared.split(), ordinary.split() + ["clk_ignore_unused"])
        self.assertEqual(compared.count("clk_ignore_unused"), 1)
        self.assertNotIn("initcall_debug", compared)
        self.assertNotIn("loglevel=8", compared)
        self.assertNotIn("saveenv", trial.volatile_bootargs_command(True))
        self.assertTrue(trial.verified_bootargs((compared + "\nK230# ").encode(), compared))
        for printed in (ordinary, compared + " clk_ignore_unused", compared + " loglevel=8"):
            self.assertFalse(trial.verified_bootargs((printed + "\nK230# ").encode(), compared))
        for suffix in ("clk_ignore_unused", "clk_ignore_unused=1", "initcall_debug", "initcall_debug=0",
                       "quiet", "debug", "ignore_loglevel", 'dyndbg="+p"', "loglevel=8", "loglevel=bad"):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                trial.trial_bootargs(original + " " + suffix, runtime_shutdown_trace=True, ignore_unused_clocks=True)
        with self.assertRaises(ValueError):
            trial.trial_bootargs(original, runtime_shutdown_trace=True, ignore_unused_clocks=True, debug_shutdown=True)

    def test_cli_allows_only_explicit_minimal_runtime_clock_pair(self):
        with mock.patch.object(sys, "argv", [str(SCRIPT), "--mode", "minimal", "--runtime-shutdown-trace",
                                              "--ignore-unused-clocks"]), \
                mock.patch.object(trial, "run_trial", return_value=True) as runner:
            self.assertEqual(trial.main(), 0)
            self.assertEqual(runner.call_args.args[3], "minimal")
            self.assertEqual(runner.call_args.kwargs, {"runtime_shutdown_trace": True, "ignore_unused_clocks": True})
        for args in (["--ignore-unused-clocks"], ["--ignore-unused-clocks", "--debug-shutdown"],
                     ["--mode", "survey", "--ignore-unused-clocks"],
                     ["--mode", "root-mount", "--ignore-unused-clocks"]):
            with self.subTest(args=args), mock.patch.object(sys, "argv", [str(SCRIPT), *args]), \
                    mock.patch.object(trial, "run_trial") as runner, mock.patch('sys.stderr'):
                with self.assertRaises(SystemExit): trial.main()
                runner.assert_not_called()


class InitrdReadinessTests(unittest.TestCase):
    banner = b"[    0.000000] Linux version 7.3.0-rc5 candidate\n"
    ready = b"[   12.000000] Run /bin/sh as init process\n"
    prompt = b"sh-5.3# "
    warnings = (b"sh: cannot set terminal process group (-1): Inappropriate ioctl for device\n"
                b"sh: no job control in this shell\n")

    def session(self, chunks, initial=b""):
        pending = list(chunks)
        port = mock.Mock()
        port.read.side_effect = lambda size: pending.pop(0) if pending else b""
        serial = mock.Mock(); serial.Serial.return_value = port
        session = trial.PrivateSession(serial, io.BytesIO()); session.buffer = initial
        return session, pending

    def test_verbose_boot_beyond_receipt_window_waits_without_input_then_runs_protocol(self):
        stale = b"[ 1.000000] Linux version 6.6.36 normal\n" + self.ready
        trace = b"[ 2.000000] calling debug_init\n" + b"x" * 10000 + b"\n"
        session, pending = self.session([self.banner] + [trace] * 18 + [self.ready, self.prompt], initial=stale)
        clock = FakeClock(step=1.0)
        self.assertTrue(trial.await_initrd_ready(session, clock=clock))
        self.assertGreater(clock.now, 8.0)
        session.port.write.assert_not_called()
        self.assertEqual(session.buffer, self.prompt)
        self.assertNotIn(stale, session.buffer)
        token = "a" * 32
        replies = [
            f"\nK230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            f"K230_RDINIT_MOUNT_BEGIN {token}\nK230_RDINIT_MOUNT_END {token} MKDIR_RC=0 MOUNT_ATTEMPTED=1 MOUNT_RC=0\n".encode(),
            f"K230_RDINIT_UP_BEGIN {token}\n21.0 22.0\nK230_RDINIT_UP_END {token} RC=0\n".encode(),
            f"K230_RDINIT_REBOOT {token}\n".encode(),
        ]
        def write(data):
            self.assertIn(self.ready, session.log.getvalue())
            pending.append(replies.pop(0))
        session.port.write.side_effect = write
        outcome = trial.run_probe_protocol(session, token, "minimal", timeout=0.02, clock=FakeClock())
        self.assertTrue(outcome["diagnostic_ok"])
        self.assertEqual(session.port.write.call_count, 5)

    def test_stale_normal_and_echoed_or_incomplete_ready_lines_do_not_satisfy_gate(self):
        stale = self.ready + b"[ 0.000000] Linux version 6.6.36 normal\n" + self.ready
        for output in (self.ready,
                       self.banner + b"echo " + self.ready,
                       self.banner + self.ready.rstrip(b"\n"),
                       self.banner + b"Run /bin/sh as init process\n",
                       self.banner + self.ready.replace(b"/bin/sh", b"/sbin/init")):
            with self.subTest(output=output):
                session, _ = self.session([output], initial=stale)
                self.assertFalse(trial.await_initrd_ready(session, timeout=3, clock=FakeClock(step=1)))
                session.port.write.assert_not_called()

    def test_ready_received_with_banner_is_preserved_and_checked_before_read(self):
        session, _ = self.session([], initial=self.banner + self.ready + self.prompt)
        self.assertTrue(trial.await_initrd_ready(session, clock=FakeClock()))
        session.port.read.assert_not_called(); session.port.write.assert_not_called()

    def test_real_pump_accepts_warning_lines_and_split_initial_prompt(self):
        session, _ = self.session([self.banner, self.ready, self.warnings, b"sh-5.", b"3#", b" "])
        self.assertTrue(trial.await_initrd_ready(session, clock=FakeClock(step=1)))
        session.port.write.assert_not_called()

    def test_init_entry_survives_postentry_buffer_rollover_before_prompt(self):
        session, _ = self.session([self.banner + self.ready] + [b"x" * 65536] * 3 + [b"\n" + self.prompt])
        self.assertTrue(trial.await_initrd_ready(session, clock=FakeClock(step=1)))
        self.assertNotIn(self.ready, session.buffer)
        self.assertEqual(len(session.buffer), 131072)
        session.port.write.assert_not_called()

    def test_entry_only_preentry_prompt_echo_and_continuation_never_qualify(self):
        for output in (self.ready, self.prompt + b"\n" + self.ready,
                       self.ready + b"> ", self.ready + b"echo " + self.prompt,
                       self.ready + self.prompt + b"printf 'unfinished\n> ",
                       self.ready + self.prompt + b"\n> ", self.ready + b"sh-5.3#"):
            with self.subTest(output=output):
                session, _ = self.session([self.banner + output])
                self.assertFalse(trial.await_initrd_ready(session, timeout=3, clock=FakeClock(step=0.1)))
                session.port.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()

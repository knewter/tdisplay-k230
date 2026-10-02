import importlib.util
import unittest
from pathlib import Path


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

    def test_minimal_commands_are_short_and_survey_is_separate(self):
        token = "a" * 32
        commands = (
            trial.reception_command(token), trial.true_command(token),
            trial.uptime_command(token), trial.reboot_command(token),
        )
        self.assertTrue(commands[0].startswith("PATH=/bin:/sbin; export PATH;"))
        self.assertTrue(all(len(command.encode()) < 200 for command in commands))
        self.assertIn("/bin/true", commands[1])
        self.assertIn("/bin/cat /proc/uptime", commands[2])
        self.assertIn("K230_RDINIT_UP_BEGIN", commands[2])
        self.assertIn("K230_RDINIT_UP_END", commands[2])
        self.assertIn("/bin/reboot -ff", commands[3])
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
            f"K230_RDINIT_UP_BEGIN {token}\r\n12.50 8.25\r\nK230_RDINIT_UP_END {token} RC=0\r\n".encode(),
            f"K230_RDINIT_REBOOT {token}\r\n".encode(),
        ])
        outcome = trial.run_probe_protocol(session, token, "minimal", timeout=0.02, clock=FakeClock())
        self.assertEqual(outcome["diagnostic"]["schema"], "k230-initrd-minimal-v1")
        self.assertEqual(outcome["diagnostic"]["uptime"], ["12.50", "8.25"])
        self.assertTrue(outcome["diagnostic_ok"])
        self.assertTrue(outcome["reboot_marker"])
        commands = [item.decode().rstrip("\r") for item in session.writes]
        self.assertEqual(len(commands), 4)
        self.assertTrue(commands[-1].startswith("printf 'K230_RDINIT_REBOOT"))
        self.assertFalse(any("K230_PROC" in command for command in commands))
        self.assertEqual(["/bin/true" in command for command in commands], [False, True, False, False])

    def test_early_receipt_is_retried_and_old_or_echoed_markers_cannot_pass_new_attempt(self):
        tokens = iter(("3" * 32, "4" * 32))
        token = "2" * 32
        echoed_second = f"printf 'K230_RDINIT_RX {'3' * 32}\\n'\r\n".encode()
        session = FakeSerialSession([
            None,  # First receipt line was sent before the shell consumed it.
            echoed_second + f"K230_RDINIT_RX {token}\r\n".encode(),  # Echo + late stale response.
            f"K230_RDINIT_RX {'4' * 32}\r\n".encode(),
            f"K230_RDINIT_TRUE {'4' * 32} RC=0\r\n".encode(),
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
        self.assertEqual(len(commands), 6)
        self.assertIn(f"K230_RDINIT_RX {token}", commands[0])
        self.assertIn(f"K230_RDINIT_RX {'3' * 32}", commands[1])
        self.assertIn(f"K230_RDINIT_RX {'4' * 32}", commands[2])
        self.assertIn("/bin/true", commands[3])
        self.assertIn(f"K230_RDINIT_TRUE {'4' * 32}", commands[3])

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

    def test_rc_failure_skips_explicit_survey_but_reboots_after_all_returns(self):
        token = "c" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=127\n".encode(),
            f"K230_RDINIT_UP_BEGIN {token}\nK230_RDINIT_UP_END {token} RC=1\n".encode(),
            f"K230_RDINIT_REBOOT {token}\n".encode(),
        ])
        outcome = trial.run_probe_protocol(session, token, "survey", timeout=0.02, clock=FakeClock())
        self.assertEqual(outcome["diagnostic"]["schema"], "k230-initrd-survey-v1")
        self.assertEqual(outcome["diagnostic"]["survey"]["status"], "skipped")
        self.assertFalse(outcome["diagnostic_ok"])
        self.assertTrue(outcome["reboot_marker"])
        self.assertEqual(len(session.writes), 4)
        self.assertFalse(any(b"K230_PROC" in command for command in session.writes))

    def test_explicit_survey_runs_only_after_minimal_success(self):
        token = "e" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            f"K230_RDINIT_UP_BEGIN {token}\n2.0 3.0\nK230_RDINIT_UP_END {token} RC=0\n".encode(),
            f"K230_LABEL_NIXOS_SD=0\nK230_RDINIT_SURVEY {token} RC=0\n".encode(),
            f"K230_RDINIT_REBOOT {token}\n".encode(),
        ])
        outcome = trial.run_probe_protocol(session, token, "survey", timeout=0.02, clock=FakeClock())
        self.assertEqual(outcome["diagnostic"]["survey"]["status"], "complete")
        self.assertFalse(outcome["diagnostic"]["survey"]["nixos_sd_label_present"])
        self.assertTrue(outcome["diagnostic_ok"])
        self.assertIn(b"K230_PROC", session.writes[3])

    def test_survey_timeout_stops_without_reboot_input(self):
        token = "9" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            f"K230_RDINIT_UP_BEGIN {token}\n1.0 1.0\nK230_RDINIT_UP_END {token} RC=0\n".encode(),
            None,
        ])
        with self.assertRaisesRegex(trial.ProbeProtocolError, "optional survey"):
            trial.run_probe_protocol(session, token, "survey", timeout=0.01, clock=FakeClock())
        self.assertEqual(len(session.writes), 4)
        self.assertFalse(any(b"K230_RDINIT_REBOOT" in command for command in session.writes))

    def test_reboot_marker_timeout_is_reported_separately_from_successful_minimal_probe(self):
        token = "8" * 32
        session = FakeSerialSession([
            f"K230_RDINIT_RX {token}\n".encode(),
            f"K230_RDINIT_TRUE {token} RC=0\n".encode(),
            f"K230_RDINIT_UP_BEGIN {token}\n1.0 1.0\nK230_RDINIT_UP_END {token} RC=0\n".encode(),
            None,
        ])
        outcome = trial.run_probe_protocol(session, token, "minimal", timeout=0.01, clock=FakeClock())
        self.assertTrue(outcome["diagnostic_ok"])
        self.assertFalse(outcome["reboot_marker"])
        self.assertEqual(len(session.writes), 4)

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
              f"K230_RDINIT_UP_BEGIN {token}\n".encode()], "/bin/cat /proc/uptime", 3),
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


if __name__ == "__main__":
    unittest.main()

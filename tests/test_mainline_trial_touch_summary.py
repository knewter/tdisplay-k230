"""Task 3.1: bounded on-board K230_TOUCH_SUMMARY replaces whole-log evtest
retrieval in tools/mainline-drm-system-trial.py. Fixtures cover a complete
contact, a contact with no release, a contact with no movement, a duplicate
summary record, a malformed record, and a missing record -- each must fail
closed except the first.
"""
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("touch_summary_fixtures", ROOT / "tests/test_mainline_drm_system_trial.py")
f = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(f)
trial = f.trial
TOKEN = f.TOKEN


def complete_line(token=TOKEN, **overrides):
    values = dict(down=1, up=1, pos_x=2, pos_y=1, syn=3, tracking_release=1,
                  first_down_line=1, last_up_line=7, rows=8)
    values.update(overrides)
    return f.touch_summary_bytes(token, **values)[:-1]  # strip trailing \n; record() matches without it


class TouchSummaryRecordTests(unittest.TestCase):
    """Fixture: valid complete contact."""

    def test_valid_complete_contact_parses_and_is_complete(self):
        line = complete_line()
        counts = trial.touch_summary_record(line, TOKEN)
        self.assertEqual(counts, {"down": 1, "up": 1, "pos_x": 2, "pos_y": 1, "syn": 3,
                                  "tracking_release": 1, "first_down_line": 1, "last_up_line": 7, "rows": 8})
        events = trial.summary_complete_contact(counts)
        self.assertTrue(events["down"]); self.assertTrue(events["up"])
        self.assertTrue(events["position_change"]); self.assertTrue(events["syn_after_up"])
        self.assertTrue(events["complete_contact"])
        self.assertEqual(events["event_rows"], 8)
        self.assertEqual(events["coordinate_mapping"], "UNVERIFIED")

    """Fixture: capture with no release (contact never lifted)."""

    def test_no_up_is_not_complete(self):
        counts = trial.touch_summary_record(complete_line(up=0, tracking_release=0, last_up_line=0), TOKEN)
        events = trial.summary_complete_contact(counts)
        self.assertTrue(events["down"]); self.assertFalse(events["up"])
        self.assertFalse(events["syn_after_up"]); self.assertFalse(events["complete_contact"])

    """Fixture: capture with no movement (stationary tap)."""

    def test_no_movement_is_not_complete(self):
        counts = trial.touch_summary_record(complete_line(pos_x=1, pos_y=1), TOKEN)
        events = trial.summary_complete_contact(counts)
        self.assertTrue(events["down"]); self.assertTrue(events["up"]); self.assertTrue(events["syn_after_up"])
        self.assertFalse(events["position_change"]); self.assertFalse(events["complete_contact"])

    def test_no_confirmed_release_is_not_complete_even_with_movement_and_up(self):
        # up happened but no later SYN_REPORT confirmed it (truncated capture).
        counts = trial.touch_summary_record(complete_line(tracking_release=0), TOKEN)
        events = trial.summary_complete_contact(counts)
        self.assertTrue(events["up"]); self.assertTrue(events["position_change"])
        self.assertFalse(events["syn_after_up"]); self.assertFalse(events["complete_contact"])

    """Fixture: malformed record."""

    def test_malformed_variants_all_rejected(self):
        good = complete_line()
        variants = [
            good.replace(b"a" * 32, b"b" * 32, 1),  # wrong token
            good + b" extra=1",  # trailing content
            good.replace(b"down=1", b"down=01"),  # non-canonical leading zero
            good.replace(b"down=1", b"down=-1"),  # negative not allowed
            good.replace(b"down=1 up=1", b"up=1 down=1"),  # reordered fields
            good.replace(b" rows=8", b""),  # missing trailing field
            good.replace(b"K230_TOUCH_SUMMARY", b"K230_TOUCH_SUMMARY_V2"),  # wrong tag
            good + b"\n",  # embedded newline (two logical lines)
            b"",  # empty
        ]
        for bad in variants:
            with self.subTest(bad=bad):
                self.assertIsNone(trial.touch_summary_record(bad, TOKEN))

    def test_token_itself_is_validated(self):
        with self.assertRaises(ValueError):
            trial.touch_summary_record(complete_line(), "not-a-token")
        with self.assertRaises(ValueError):
            trial.touch_summary_command("not-a-token", f.SYSTEM)


class TouchSummaryCommandTests(unittest.TestCase):
    def test_command_runs_awk_over_the_retained_log_and_never_cats_it(self):
        cmd = trial.touch_summary_command(TOKEN, f.SYSTEM)
        self.assertIn(f"K230_TOUCH_BEGIN {TOKEN}", cmd)
        self.assertIn(f"K230_TOUCH_END {TOKEN} RC=", cmd)
        self.assertIn("/sw/bin/awk ", cmd)
        self.assertIn(f"/run/k230-mainline-touch-{TOKEN}.log", cmd)
        self.assertIn(f"K230_TOUCH_SUMMARY {TOKEN} down=%d", cmd)
        self.assertNotIn("/sw/bin/cat", cmd)
        self.assertLess(len(cmd.encode()), 4000)
        # Bounded: wrap the awk run itself with the same timeout tool already required.
        self.assertIn("/sw/bin/timeout 5s /sw/bin/awk", cmd.replace(f.SYSTEM, ""))

    def test_required_tool_list_now_includes_awk(self):
        source = Path(trial.__file__).read_text()
        m = re.search(r'for tool in \(([^)]*)\):\n\s*if not os\.access', source)
        self.assertIsNotNone(m)
        tools = [t.strip().strip('"') for t in m.group(1).split(",")]
        self.assertIn("awk", tools)
        self.assertIn("evtest", tools)


class PrepareRequiresAwkTests(unittest.TestCase):
    """The required-tool tuple in prepare() must gate on a real missing/present awk."""

    def _bundle_and_system(self, directory, tools):
        root = Path(directory)
        system = root / "candidate-system"
        bin_dir = system / "sw/bin"
        bin_dir.mkdir(parents=True)
        for tool in tools:
            path = bin_dir / tool
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        bundle = root / "bundle"
        bundle.mkdir()
        (bundle / "bootargs.txt").write_text(
            f"bootargs=console=ttyS0,115200n8 root=fstab loglevel=4 loglevel=7 init={system}/init\n")
        return bundle, system

    def _source(self, system):
        return {"system": str(system), "helper_text": "fixture helper", "normal": {"fixture": True}, "manifest": {"fixture": True}}

    def test_missing_awk_fails_closed_before_any_serial_use(self):
        required = ("sh", "cat", "id", "readlink", "uname", "findmnt", "systemctl", "sha256sum", "timeout", "evtest")
        with tempfile.TemporaryDirectory() as directory:
            bundle, system = self._bundle_and_system(directory, required)  # awk deliberately absent
            with mock.patch.object(trial.rd, "prepare_trial", side_effect=lambda *a: dict(self._source(system))):
                with self.assertRaises(ValueError):
                    trial.prepare(bundle, Path("m"), Path("n"))

    def test_present_awk_allows_prepare_to_succeed(self):
        required = ("sh", "cat", "id", "readlink", "uname", "findmnt", "systemctl", "sha256sum", "timeout", "evtest", "awk")
        with tempfile.TemporaryDirectory() as directory:
            bundle, system = self._bundle_and_system(directory, required)
            with mock.patch.object(trial.rd, "prepare_trial", side_effect=lambda *a: dict(self._source(system))):
                p = trial.prepare(bundle, Path("m"), Path("n"))
            self.assertEqual(p["system"], str(system))


class TouchRetrievalProtocolTests(unittest.TestCase):
    """End-to-end touch() exchanges: duplicate, malformed and missing summaries
    must fail closed with no further board input."""

    def _run_touch(self, reply):
        session = f.PumpSession([reply])
        with mock.patch.object(trial, "exchange", side_effect=[f.facts()["device"], f.facts()["capture"]]), \
             mock.patch.object(trial.uuid, "uuid4", return_value=f.SimpleNamespace(hex=TOKEN)), \
             mock.patch.object(trial.time, "monotonic", side_effect=f.Clock()):
            return session, trial.touch(session, f.prepared())

    def _expect_unknown(self, reply):
        session = f.PumpSession([reply])
        with mock.patch.object(trial, "exchange", side_effect=[f.facts()["device"], f.facts()["capture"]]), \
             mock.patch.object(trial.uuid, "uuid4", return_value=f.SimpleNamespace(hex=TOKEN)), \
             mock.patch.object(trial.time, "monotonic", side_effect=f.Clock()):
            with self.assertRaises(trial.Unknown):
                trial.touch(session, f.prepared())
        self.assertEqual(len(session.writes), 1)
        self.assertNotIn(b"reboot", session.writes[0])
        return session

    def test_valid_summary_round_trip_reports_complete_contact(self):
        reply = (f"K230_TOUCH_BEGIN {TOKEN}\n".encode() + complete_line() + b"\n"
                 + f"K230_TOUCH_END {TOKEN} RC=0\n[root@nixos:~]# ".encode())
        _, result = self._run_touch(reply)
        self.assertTrue(result["events"]["complete_contact"])
        self.assertEqual(result["events"]["event_rows"], 8)

    def test_missing_summary_fails_closed(self):
        reply = f"K230_TOUCH_BEGIN {TOKEN}\nK230_TOUCH_END {TOKEN} RC=0\n[root@nixos:~]# ".encode()
        self._expect_unknown(reply)

    def test_duplicate_summary_fails_closed(self):
        body = complete_line() + b"\n" + complete_line() + b"\n"
        reply = (f"K230_TOUCH_BEGIN {TOKEN}\n".encode() + body
                 + f"K230_TOUCH_END {TOKEN} RC=0\n[root@nixos:~]# ".encode())
        self._expect_unknown(reply)

    def test_malformed_summary_fails_closed(self):
        bad = complete_line().replace(b"down=1", b"down=01") + b"\n"
        reply = (f"K230_TOUCH_BEGIN {TOKEN}\n".encode() + bad
                 + f"K230_TOUCH_END {TOKEN} RC=0\n[root@nixos:~]# ".encode())
        self._expect_unknown(reply)

    def test_extraneous_body_text_alongside_a_good_summary_fails_closed(self):
        body = b"warning: something\n" + complete_line() + b"\n"
        reply = (f"K230_TOUCH_BEGIN {TOKEN}\n".encode() + body
                 + f"K230_TOUCH_END {TOKEN} RC=0\n[root@nixos:~]# ".encode())
        self._expect_unknown(reply)


if __name__ == "__main__":
    unittest.main()

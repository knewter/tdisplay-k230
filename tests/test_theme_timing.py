"""Pure unit tests for the THEME_TIMING log helper; no board or daemon.

Asserts against `syslog.syslog`/`syslog.openlog` directly (mocked), not
against stdout/stderr: this module deliberately never touches those streams
-- see its own module doc for why (theme_catalog.rs's `command_error()`
parses a CLI's stderr as JSON byte-for-byte on a nonzero exit).
"""
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import theme_timing  # noqa: E402


class TimingTests(unittest.TestCase):
    def setUp(self):
        # Force `_ensure_open()` to run again under this test's own mocks,
        # regardless of what an earlier test (or import-time probing) did.
        theme_timing._opened = False

    def test_stopwatch_laps_are_positive_and_roughly_ordered(self):
        stopwatch = theme_timing.Stopwatch()
        time.sleep(0.01)
        first = stopwatch.lap("a")
        time.sleep(0.02)
        second = stopwatch.lap("b")
        self.assertGreater(first, 0)
        self.assertGreater(second, 0)
        self.assertEqual([name for name, _ in stopwatch.phases], ["a", "b"])
        self.assertGreaterEqual(stopwatch.total_ms(), first + second - 1)  # timer jitter tolerance

    def test_log_line_is_one_grep_friendly_message_with_phases_and_extras(self):
        stopwatch = theme_timing.Stopwatch()
        stopwatch.lap("hash")
        stopwatch.lap("stage")
        with mock.patch("syslog.openlog") as openlog, mock.patch("syslog.syslog") as emit:
            theme_timing.log("prepare", "activate", stopwatch, cache="hit", id="abc123")
        openlog.assert_called_once()
        emit.assert_called_once()
        (priority, message), _kwargs = emit.call_args
        self.assertEqual(priority, theme_timing.syslog.LOG_INFO)
        self.assertTrue(message.startswith("THEME_TIMING prepare activate "))
        self.assertIn("hash=", message)
        self.assertIn("stage=", message)
        self.assertIn("total=", message)
        self.assertIn("cache=hit", message)
        self.assertIn("id=abc123", message)

    def test_log_without_stopwatch_still_emits_extras_only(self):
        with mock.patch("syslog.openlog"), mock.patch("syslog.syslog") as emit:
            theme_timing.log("client", "list", path="daemon")
        (_priority, message), _kwargs = emit.call_args
        self.assertEqual(message, "THEME_TIMING client list path=daemon")

    def test_log_never_raises_when_syslog_is_unavailable(self):
        with mock.patch("syslog.openlog", side_effect=OSError("no /dev/log here")):
            theme_timing.log("prepare", "activate", cache="hit")  # must not raise
        # openlog() failing must not leave `_opened` stuck true for a later,
        # working call in the same process.
        self.assertFalse(theme_timing._opened)

    def test_openlog_is_only_called_once_across_repeated_logs(self):
        with mock.patch("syslog.openlog") as openlog, mock.patch("syslog.syslog"):
            theme_timing.log("client", "list")
            theme_timing.log("client", "preview")
        openlog.assert_called_once()


if __name__ == "__main__":
    unittest.main()

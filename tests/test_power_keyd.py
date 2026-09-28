"""The same press may never both darken the panel and request power UI."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("power_keyd", Path(__file__).parents[1] / "nix/power-keyd/power_keyd.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class KeyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.actions = []
        self.policy = MODULE.KeyPolicy(self.actions.append)

    def test_short_press_then_wake_press(self):
        self.policy.key(1, 10)
        self.policy.key(0, 10.2)
        self.policy.key(1, 11)
        self.policy.key(0, 11.1)
        self.assertEqual(self.actions, ["short", "short"])

    def test_hold_fires_once_while_still_down(self):
        self.policy.key(1, 10)
        self.policy.tick(10.71)
        self.policy.tick(12)
        self.policy.key(0, 12)
        self.assertEqual(self.actions, ["hold"])

    def test_repeat_and_bounce_do_not_duplicate(self):
        self.policy.key(1, 10)
        self.policy.key(1, 10.02)
        self.policy.key(2, 10.1)
        self.policy.key(0, 10.2)
        self.policy.key(0, 10.3)
        self.assertEqual(self.actions, ["short"])

    def test_missing_release_is_discarded(self):
        self.policy.key(1, 10)
        self.policy.disconnect()
        self.policy.key(0, 11)
        self.assertEqual(self.actions, [])

    def test_release_at_threshold_is_hold(self):
        self.policy.key(1, 10)
        self.policy.key(0, 10.7)
        self.assertEqual(self.actions, ["hold"])

    def test_hold_while_dark_wakes_before_sheet(self):
        actions = MODULE.Actions("/unused", "/unused", "/unused")
        events = []
        actions.dark = True
        actions.output = lambda on: events.append(("output", on)) or True
        actions.show_sheet = lambda: events.append(("sheet",))
        actions("hold")
        self.assertEqual(events, [("output", True), ("sheet",)])

    def test_short_off_then_wake_never_opens_a_sheet(self):
        actions = MODULE.Actions("/unused", "/unused", "/unused")
        events = []
        def fake_output(on):
            events.append(("output", on))
            actions.dark = not on
            return True
        actions.output = fake_output
        actions.show_sheet = lambda: events.append(("sheet",))
        actions("short")
        actions("short")
        self.assertEqual(events, [("output", False), ("output", True)])

    def test_failed_display_command_keeps_known_state(self):
        actions = MODULE.Actions("swaymsg", "/run/test.sock", "/run/shell.sock")
        with patch.object(MODULE.subprocess, "run", side_effect=OSError("unavailable")):
            self.assertFalse(actions.output(False))
        self.assertFalse(actions.dark)

    def test_sway_success_is_required_before_dark_state_changes(self):
        actions = MODULE.Actions("swaymsg", "/run/test.sock", "/run/shell.sock")
        completed = MODULE.subprocess.CompletedProcess([], 0, stdout='[{"success":false}]')
        with patch.object(MODULE.subprocess, "run", return_value=completed):
            self.assertFalse(actions.output(False))
        self.assertFalse(actions.dark)

    def test_empty_sway_reply_cannot_claim_a_display_change(self):
        actions = MODULE.Actions("swaymsg", "/run/test.sock", "/run/shell.sock")
        completed = MODULE.subprocess.CompletedProcess([], 0, stdout="[]")
        with patch.object(MODULE.subprocess, "run", return_value=completed):
            self.assertFalse(actions.output(False))
        self.assertFalse(actions.dark)


if __name__ == "__main__":
    unittest.main()

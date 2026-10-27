"""Idle dim/off/resume state logic against a fixture backlight and fake swaymsg."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "idle_dimmer", Path(__file__).parents[1] / "nix/idle-dimmer/idle_dimmer.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.backlight = root / "bl"
        self.backlight.mkdir()
        self.set_raw(254)
        self.sent = []
        self.sway_ok = True
        self.dimmer = MODULE.Dimmer(self.backlight, root / "state.json", "swaymsg", "sock")
        self.dimmer.sway = self.fake_sway

    def fake_sway(self, *words):
        self.sent.append(" ".join(words))
        return self.sway_ok

    def set_raw(self, value):
        (self.backlight / "brightness").write_text(str(value))

    def raw(self):
        return int((self.backlight / "brightness").read_text())


class DimmerTests(Fixture):
    def test_dim_is_a_quarter_and_resume_restores_exactly(self):
        self.dimmer.dim()
        self.assertEqual(self.raw(), 64)  # round(254 * .25) = round(63.5)
        self.dimmer.resume()
        self.assertEqual(self.raw(), 254)
        self.assertFalse(self.dimmer.state_path.exists())

    def test_dim_twice_does_not_dim_the_dimmed_value(self):
        self.dimmer.dim()
        self.dimmer.dim()
        self.assertEqual(self.raw(), 64)
        self.dimmer.resume()
        self.assertEqual(self.raw(), 254)

    def test_never_raises_brightness(self):
        for value in (0, 1):
            self.set_raw(value)
            self.dimmer.dim()
            self.assertEqual(self.raw(), value)
            self.assertFalse(self.dimmer.state_path.exists())
        self.set_raw(2)
        self.dimmer.dim()
        self.assertEqual(self.raw(), 1)
        self.dimmer.resume()
        self.assertEqual(self.raw(), 2)

    def test_off_uses_the_power_key_command_and_resume_powers_on(self):
        self.dimmer.dim()
        self.dimmer.off()
        self.assertEqual(self.sent, ["output * power off"])
        self.dimmer.resume()
        self.assertEqual(self.sent, ["output * power off", "output * power on"])
        self.assertEqual(self.raw(), 254)

    def test_off_without_dim_still_resumes(self):
        self.set_raw(1)  # nothing to dim
        self.dimmer.dim()
        self.dimmer.off()
        self.dimmer.resume()
        self.assertEqual(self.sent[-1], "output * power on")
        self.assertEqual(self.raw(), 1)

    def test_resume_without_idle_is_a_noop(self):
        self.dimmer.resume()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.raw(), 254)

    def test_changed_brightness_is_not_overwritten(self):
        self.dimmer.dim()
        self.set_raw(180)  # slider moved while dim
        self.dimmer.resume()
        self.assertEqual(self.raw(), 180)

    def test_failed_off_leaves_no_off_state(self):
        self.sway_ok = False
        self.dimmer.off()
        self.assertFalse(self.dimmer.load()["off"])
        self.dimmer.resume()
        self.assertEqual(self.sent, ["output * power off"])

    def test_wake_restores_and_reports_activity(self):
        self.dimmer.dim()
        self.dimmer.off()
        self.sent.clear()
        self.dimmer.wake()
        self.assertEqual(self.sent, ["output * power on", "seat * cursor move 0 0"])
        self.assertEqual(self.raw(), 254)

    def test_corrupt_state_is_treated_as_empty(self):
        self.dimmer.state_path.write_text("{not json")
        self.dimmer.resume()
        self.assertEqual(self.raw(), 254)


class ExhibitionTests(Fixture):
    """Idle on the charger: the exhibition replaces the blank."""

    def setUp(self):
        super().setUp()
        root = Path(self.tmp.name)
        self.supplies = root / "ps"
        self.prefs = root / "prefs"
        self.proc = root / "proc"
        for path in (self.supplies, self.prefs, self.proc):
            path.mkdir()
        self.pid_file = root / "exhibition.pid"
        self.dimmer = MODULE.Dimmer(
            self.backlight, root / "state.json", "swaymsg", "sock",
            exhibit_exec="/bin/k230-exhibition-card", prefs_dir=self.prefs,
            power_supply=self.supplies, pid_file=self.pid_file, proc_root=self.proc)
        self.dimmer.sway = self.fake_sway
        self.killed = []
        self.real_kill = MODULE.os.kill
        MODULE.os.kill = lambda pid, sig: self.killed.append((pid, sig))
        self.addCleanup(setattr, MODULE.os, "kill", self.real_kill)
        self.supply("battery", "Battery")
        self.supply("charger", "USB", online=0)

    def supply(self, name, kind, online=None):
        entry = self.supplies / name
        entry.mkdir(exist_ok=True)
        (entry / "type").write_text(kind + "\n")
        if online is not None:
            (entry / "online").write_text(f"{online}\n")

    def plug(self, online=1):
        self.supply("charger", "USB", online=online)

    def prefer(self, word):
        (self.prefs / MODULE.IDLE_ON_CHARGER_FILE).write_text(word)

    def card_running(self, pid=4242):
        self.pid_file.write_text(f"{pid}\n")
        (self.proc / str(pid)).mkdir(exist_ok=True)
        (self.proc / str(pid) / "cmdline").write_bytes(b"python3\0/x/k230_exhibition.py\0")

    def test_decision_needs_the_clock_preference_and_a_charger(self):
        self.assertTrue(MODULE.exhibit_wanted("clock", True))
        self.assertFalse(MODULE.exhibit_wanted("clock", False))
        self.assertFalse(MODULE.exhibit_wanted("sleep", True))

    def test_preference_defaults_to_clock_and_only_sleep_disables(self):
        self.assertEqual(MODULE.read_idle_on_charger(self.prefs), "clock")
        self.assertEqual(MODULE.read_idle_on_charger(self.prefs / "gone"), "clock")
        for text, want in (("clock\n", "clock"), ("sleep\n", "sleep"), (" sleep ", "sleep"),
                           ("SLEEP", "clock"), ("", "clock"), ("sleeping", "clock")):
            self.prefer(text)
            self.assertEqual(MODULE.read_idle_on_charger(self.prefs), want, repr(text))
        (self.prefs / MODULE.IDLE_ON_CHARGER_FILE).write_bytes(b"\xff\xfe")
        self.assertEqual(MODULE.read_idle_on_charger(self.prefs), "clock")

    def test_charger_is_any_non_battery_supply_online(self):
        self.assertFalse(MODULE.charger_online(self.supplies))
        self.plug()
        self.assertTrue(MODULE.charger_online(self.supplies))
        self.supply("battery", "Battery", online=1)  # a battery never counts
        self.plug(0)
        self.assertFalse(MODULE.charger_online(self.supplies))
        self.assertFalse(MODULE.charger_online(self.supplies / "gone"))

    def test_on_the_charger_dim_dims_and_opens_the_card(self):
        self.plug()
        self.dimmer.dim()
        self.assertEqual(self.raw(), 64)
        self.assertEqual(self.sent, ["exec /bin/k230-exhibition-card"])

    def test_on_battery_dim_opens_nothing(self):
        self.dimmer.dim()
        self.assertEqual(self.raw(), 64)
        self.assertEqual(self.sent, [])

    def test_sleep_preference_opens_nothing(self):
        self.plug()
        self.prefer("sleep")
        self.dimmer.dim()
        self.assertEqual(self.sent, [])

    def test_no_exec_configured_disables_the_card(self):
        self.plug()
        self.dimmer.exhibit_exec = None
        self.dimmer.dim()
        self.assertEqual(self.sent, [])

    def test_a_card_already_running_is_not_opened_twice(self):
        self.plug()
        self.card_running()
        self.dimmer.dim()
        self.assertEqual(self.sent, [])

    def test_a_stale_pid_file_is_not_a_card(self):
        self.plug()
        self.pid_file.write_text("999\n")  # no /proc/999
        self.assertIsNone(self.dimmer.exhibit_pid())
        (self.proc / "999").mkdir()
        (self.proc / "999" / "cmdline").write_bytes(b"sleep\0100\0")  # a reused pid
        self.assertIsNone(self.dimmer.exhibit_pid())
        self.dimmer.dim()
        self.assertEqual(self.sent, ["exec /bin/k230-exhibition-card"])

    def test_off_is_skipped_while_the_card_is_up_and_docked(self):
        self.plug()
        self.dimmer.dim()
        self.card_running()
        self.sent.clear()
        self.dimmer.off()
        self.assertEqual(self.sent, [])
        self.assertFalse(self.dimmer.load()["off"])

    def test_off_blanks_when_unplugged_or_the_choice_changed(self):
        self.plug()
        self.card_running()
        self.plug(0)
        self.dimmer.off()
        self.assertEqual(self.sent, ["output * power off"])
        self.sent.clear()
        self.plug()
        self.prefer("sleep")
        self.dimmer.off()
        self.assertEqual(self.sent, ["output * power off"])

    def test_off_blanks_when_no_card_is_up(self):
        self.plug()
        self.dimmer.off()
        self.assertEqual(self.sent, ["output * power off"])

    def test_exhibit_end_blanks_and_resume_restores(self):
        self.plug()
        self.dimmer.dim()
        self.card_running()
        self.plug(0)
        self.dimmer.exhibit_end()
        self.assertEqual(self.sent[-1], "output * power off")
        self.assertTrue(self.dimmer.load()["off"])
        self.dimmer.resume()
        self.assertEqual(self.raw(), 254)

    def test_resume_after_a_lit_idle_leaves_the_card_to_close_itself(self):
        self.plug()
        self.dimmer.dim()
        self.card_running()
        self.dimmer.resume()  # a touch: the card reads it and closes itself
        self.assertEqual(self.killed, [])
        self.assertEqual(self.raw(), 254)

    def test_resume_from_dark_ends_the_card(self):
        self.plug()
        self.dimmer.dim()
        self.dimmer.blank()
        self.card_running(777)
        self.dimmer.resume()
        self.assertEqual(self.killed, [(777, MODULE.signal.SIGTERM)])

    def test_the_power_key_wake_always_ends_the_card(self):
        self.plug()
        self.dimmer.dim()
        self.card_running(888)
        self.dimmer.wake()
        self.assertEqual(self.killed, [(888, MODULE.signal.SIGTERM)])
        self.assertEqual(self.sent[-1], "seat * cursor move 0 0")

    def test_the_card_and_the_dimmer_agree_on_the_charger(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "k230_exhibition", Path(__file__).parents[1] / "nix/term-apps/k230_exhibition.py")
        card = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(card)
        for online in (None, 0, 1):
            if online is not None:
                self.plug(online)
            self.assertEqual(card.charger_online(self.supplies), MODULE.charger_online(self.supplies))


if __name__ == "__main__":
    unittest.main()

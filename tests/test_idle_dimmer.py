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


if __name__ == "__main__":
    unittest.main()

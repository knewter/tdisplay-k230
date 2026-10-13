import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bp", ROOT / "nix/keyboard-base/battery_policy.py")
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)


class Recorder:
    def __init__(self, **kw):
        self.notes = []
        self.off = 0
        self.policy = bp.Policy(lambda s, b, p, o: self.notes.append((s, p, o)),
                                self.poweroff, **kw)

    def poweroff(self):
        self.off += 1

    def discharge(self, levels, start=0.0, step=30.0):
        t = start
        for level in levels:
            self.policy.reading(level, True, t)
            self.policy.tick(t)
            t += step
        return t


class BatteryPolicy(unittest.TestCase):
    def test_warn_and_urgent_once_each(self):
        r = Recorder()
        r.discharge([20, 16, 15, 15, 14, 10, 6, 5, 5, 4])
        self.assertEqual([n[0] for n in r.notes], ["Battery low", "Battery very low"])
        self.assertEqual(r.off, 0)

    def test_two_readings_at_shutdown_level_start_the_countdown(self):
        r = Recorder()
        t = r.discharge([4, 3])
        self.assertNotIn("Battery critically low", [n[0] for n in r.notes])
        r.discharge([3], start=t)
        self.assertIn(("Battery critically low", "critical", True), r.notes)

    def test_a_single_low_reading_does_not(self):
        r = Recorder()
        r.discharge([3, 4, 3, 4])
        self.assertNotIn("Battery critically low", [n[0] for n in r.notes])

    def test_countdown_then_poweroff(self):
        r = Recorder(countdown=60)
        r.policy.reading(3, True, 0.0)
        r.policy.reading(3, True, 30.0)  # countdown ends at 90
        r.policy.tick(89.0)
        self.assertEqual(r.off, 0)
        self.assertEqual(r.policy.interval(), 5.0)
        r.policy.tick(90.0)
        self.assertEqual(r.off, 1)
        r.policy.tick(200.0)
        self.assertEqual(r.off, 1)

    def test_charging_cancels_the_countdown_and_rearms(self):
        r = Recorder(countdown=60)
        r.policy.reading(3, True, 0.0)
        r.policy.reading(3, True, 30.0)
        r.policy.reading(3, False, 40.0)
        r.policy.tick(100.0)
        self.assertEqual(r.off, 0)
        self.assertIn(("Charging", "ordinary", False), r.notes)
        r.notes.clear()
        r.discharge([15], start=200.0)
        self.assertEqual([n[0] for n in r.notes], ["Battery low"])

    def test_disabled_does_nothing(self):
        r = Recorder(enabled=False)
        r.discharge([15, 5, 3, 3, 3])
        r.policy.tick(1e9)
        self.assertEqual((r.notes, r.off), ([], 0))

    def test_override_raises_levels(self):
        import json, tempfile
        r = Recorder()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"warn": 90, "urgent": 85, "shutdown": 80}, f)
        bp.apply_override(r.policy, f.name)
        Path(f.name).unlink()
        self.assertEqual((r.policy.warn, r.policy.urgent, r.policy.shutdown), (90, 85, 80))


if __name__ == "__main__":
    unittest.main()

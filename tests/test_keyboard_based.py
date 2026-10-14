import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kbd", ROOT / "nix/keyboard-base/keyboard_based.py")
kbd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kbd)

KEY_A = 30


class Fake:
    def __init__(self):
        self.caps = []
        self.light = []
        self.hidden = 0
        self.panel = True

    def policy(self, idle=30.0):
        return kbd.Policy(self.caps.append, self.light.append, self.hide,
                          lambda: self.panel, idle)

    def hide(self):
        self.hidden += 1


class KeyboardBasePolicy(unittest.TestCase):
    def test_starts_dark_with_caps_off(self):
        f = Fake(); f.policy()
        self.assertEqual(f.caps, [False])
        self.assertEqual(f.light, [False])

    def test_capslock_toggles_on_press_only(self):
        f = Fake(); p = f.policy()
        stream = [(kbd.KEY_CAPSLOCK, 1), (kbd.KEY_CAPSLOCK, 2), (kbd.KEY_CAPSLOCK, 0),
                  (KEY_A, 1), (KEY_A, 0), (kbd.KEY_CAPSLOCK, 1), (kbd.KEY_CAPSLOCK, 0)]
        for t, (code, value) in enumerate(stream):
            p.key(code, value, float(t))
        self.assertEqual(f.caps, [False, True, False])

    def test_backlight_follows_typing_and_idles_off(self):
        f = Fake(); p = f.policy(idle=30)
        p.key(KEY_A, 1, 0.0)
        self.assertEqual(f.light, [False, True])
        p.key(KEY_A, 1, 10.0)
        p.tick(39.0)
        self.assertEqual(f.light, [False, True])  # still within 30 s of last key
        p.tick(40.0)
        self.assertEqual(f.light, [False, True, False])

    def test_backlight_stays_off_with_panel_off(self):
        f = Fake(); p = f.policy()
        f.panel = False
        p.key(KEY_A, 1, 0.0)
        self.assertEqual(f.light, [False])
        f.panel = True
        p.key(KEY_A, 1, 1.0)
        f.panel = False
        p.tick(2.0)
        self.assertEqual(f.light, [False, True, False])

    def test_backlight_stays_off_while_the_preference_is_off(self):
        f = Fake(); enabled = [False]
        p = kbd.Policy(f.caps.append, f.light.append, f.hide, lambda: True, 30, None,
                       lambda: enabled[0])
        p.key(KEY_A, 1, 0.0)
        self.assertEqual(f.light, [False])  # typing does not light the keys
        self.assertEqual(f.hidden, 1)       # but the other key handling still runs
        enabled[0] = True
        p.key(KEY_A, 1, 1.0)
        self.assertEqual(f.light, [False, True])
        enabled[0] = False
        p.tick(2.0)                         # turned off in Settings mid-typing
        self.assertEqual(f.light, [False, True, False])

    def test_a_level_change_previews_at_once_then_idles_off(self):
        f = Fake(); enabled = [True]
        p = kbd.Policy(f.caps.append, f.light.append, f.hide, lambda: True, 30, None,
                       lambda: enabled[0], preview_seconds=3)
        p.preference_changed("high", 0.0)     # first read: no preview
        self.assertEqual(f.light, [False])
        p.preference_changed("low", 1.0)      # dragged in Settings: lit now
        self.assertEqual(f.light, [False, True])
        p.preference_changed("medium", 2.0)   # already lit: rewritten at the new level
        self.assertEqual(f.light, [False, True, True])
        p.preference_changed("medium", 2.5)   # unchanged: nothing written
        p.tick(4.9)
        self.assertEqual(f.light, [False, True, True])
        p.tick(5.0)                           # preview over, no typing: dark
        self.assertEqual(f.light, [False, True, True, False])
        enabled[0] = False
        p.preference_changed("off", 6.0)      # off never lights
        self.assertEqual(f.light, [False, True, True, False])

    def test_preference_file_reads_on_unless_it_says_off(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "key-backlight"
            self.assertTrue(kbd.backlight_preference(path))  # missing: default on
            path.write_text("off\n")
            self.assertFalse(kbd.backlight_preference(path))
            path.write_text("on\n")
            self.assertTrue(kbd.backlight_preference(path))

    def test_every_press_hides_the_on_screen_keyboard(self):
        f = Fake(); p = f.policy()
        p.key(KEY_A, 1, 0.0); p.key(KEY_A, 0, 0.1); p.key(KEY_A, 2, 0.2)
        self.assertEqual(f.hidden, 1)

    def test_escape_calls_back_only_when_enabled(self):
        f = Fake(); backs = []
        p = kbd.Policy(f.caps.append, f.light.append, f.hide, lambda: True, 30, lambda: backs.append(1))
        p.key(kbd.KEY_ESC, 1, 0.0); p.key(kbd.KEY_ESC, 0, 0.1); p.key(kbd.KEY_ESC, 2, 0.2)
        self.assertEqual(backs, [1])
        q = f.policy()
        q.key(kbd.KEY_ESC, 1, 0.0)  # no escape callback: nothing to call

    def test_app_focus_detection(self):
        workspace = {"type": "workspace", "focused": True, "nodes": []}
        self.assertFalse(kbd.app_focused({"nodes": [{"nodes": [workspace]}]}))
        app = {"type": "con", "focused": True, "pid": 42}
        tree = {"nodes": [{"nodes": [{"type": "workspace", "nodes": [app]}]}]}
        self.assertTrue(kbd.app_focused(tree))
        floating = {"type": "floating_con", "focused": True, "pid": 7}
        self.assertTrue(kbd.app_focused({"nodes": [{"type": "workspace", "floating_nodes": [floating]}]}))

    def test_event_record_layout(self):
        self.assertEqual(kbd.INPUT_EVENT.size, 24)



class WriteLed(unittest.TestCase):
    def led(self, root, name, max_brightness):
        d = Path(root) / name
        d.mkdir()
        (d / "brightness").write_text("0")
        if max_brightness is not None:
            (d / "max_brightness").write_text(f"{max_brightness}\n")
        return d

    def test_on_writes_max_brightness_and_off_writes_zero(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            pwm = self.led(root, "k230::kbd_backlight", 255)
            gpio = self.led(root, "k230:green:capslock", 1)
            kbd.write_led("k230::kbd_backlight", True, root)
            kbd.write_led("k230:green:capslock", True, root)
            self.assertEqual((pwm / "brightness").read_text(), "255")
            self.assertEqual((gpio / "brightness").read_text(), "1")
            kbd.write_led("k230::kbd_backlight", False, root)
            self.assertEqual((pwm / "brightness").read_text(), "0")

    def test_levels_scale_the_pwm_backlight_and_keep_a_gpio_led_lit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            pwm = self.led(root, "pwm", 255)
            gpio = self.led(root, "gpio", 1)
            pref = Path(root) / "key-backlight"
            for text, expected in [("low\n", "20"), ("medium\n", "76"),
                                   ("high\n", "255"), ("on\n", "255")]:
                pref.write_text(text)
                level = kbd.backlight_level(pref)
                kbd.write_led("pwm", True, root, level)
                kbd.write_led("gpio", True, root, level)
                self.assertEqual((pwm / "brightness").read_text(), expected, text)
                self.assertEqual((gpio / "brightness").read_text(), "1", text)
            self.assertEqual(kbd.backlight_level(Path(root) / "missing"), 1.0)

    def test_missing_max_brightness_falls_back_to_one(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            d = self.led(root, "x", None)
            kbd.write_led("x", True, root)
            self.assertEqual((d / "brightness").read_text(), "1")


if __name__ == "__main__":
    unittest.main()

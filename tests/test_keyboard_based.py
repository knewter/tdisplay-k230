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


if __name__ == "__main__":
    unittest.main()

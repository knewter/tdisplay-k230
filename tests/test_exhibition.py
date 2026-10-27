"""Exhibition card: schedule, drift, layout, dismissal and the loop, on the host."""
import importlib.util
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "k230_exhibition", ROOT / "nix/term-apps/k230_exhibition.py")
EX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EX)


class FakeSession:
    """Time only moves when the loop sleeps; scripted input at chosen instants."""

    def __init__(self, clock, size=(100, 30), inputs=None):
        self.clock = clock
        self.size_value = size
        self.inputs = dict(inputs or {})  # time -> bytes
        self.frames = []
        self.written = []
        self.released = []

    def size(self):
        return self.size_value

    def draw(self, frame):
        self.frames.append((self.clock.now, frame))

    def _write(self, text):
        self.written.append(text)

    def read_release(self, first):
        self.released.append(first)

    def wait(self, timeout):
        end = self.clock.now + timeout
        due = sorted(t for t in self.inputs if self.clock.now < t <= end)
        if due:
            self.clock.now = due[0]
            return [("input", self.inputs.pop(due[0]))]
        self.clock.now = end
        return [("timeout",)]


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


START = 1_800_000_000 - (1_800_000_000 % 60) + 1  # one second into a minute


def make(inputs=None, charger=lambda: True, display=lambda: True, ttfx=None,
         size=(100, 30), **cfg):
    clock = Clock(START)
    sess = FakeSession(clock, size, inputs)
    plays = []
    ends = []
    config = {"ttfx": ttfx, "banner": "K230.txt", "interval": 300, "max_up": 7200}
    config.update(cfg)
    ex = EX.Exhibition(
        sess, config, clock=clock, charger=charger, display=display,
        play=lambda effect: (plays.append((clock.now, effect)) or "done"),
        end=lambda: ends.append(clock.now), localtime=time.gmtime)
    ex.hold_banner = lambda: "done"
    return ex, sess, clock, plays, ends


class PureTests(unittest.TestCase):
    def test_drift_never_repeats_in_consecutive_minutes_and_stays_in_range(self):
        for max_dx, max_dy in ((6, 2), (3, 1), (1, 0), (0, 2), (0, 0)):
            seen = set()
            previous = None
            count = (2 * max_dx + 1) * (2 * max_dy + 1)
            for minute in range(count * 3):
                dx, dy = EX.drift(minute, max_dx, max_dy)
                self.assertTrue(-max_dx <= dx <= max_dx and -max_dy <= dy <= max_dy)
                if count > 1:
                    self.assertNotEqual((dx, dy), previous, (max_dx, max_dy, minute))
                if minute < count:
                    seen.add((dx, dy))
                previous = (dx, dy)
            self.assertEqual(len(seen), count, "one pass visits every offset once")

    def test_effects_rotate_through_the_fixed_list(self):
        names = [EX.effect_for(i) for i in range(len(EX.EFFECTS) * 2)]
        self.assertEqual(names[:len(EX.EFFECTS)], list(EX.EFFECTS))
        self.assertEqual(names[len(EX.EFFECTS):], list(EX.EFFECTS))
        self.assertNotIn("decrypt", EX.EFFECTS)  # does not end within the cap
        self.assertNotIn("matrix", EX.EFFECTS)

    def test_first_effect_is_soon_then_every_interval(self):
        self.assertEqual(EX.next_effect_at(100, None), 100 + EX.FIRST_EFFECT_DELAY)
        self.assertEqual(EX.next_effect_at(100, 200, 300), 500)

    def test_layout_stays_on_the_frame_at_every_minute_and_size(self):
        for cols, rows in ((100, 30), (60, 14), (40, 12), (160, 45)):
            for minute in range(70):
                frame = EX.clock_layout(cols, rows, time.gmtime(START + minute * 60), minute)
                ink = [(r, c) for r, line in enumerate(frame.cells) for c, (ch, _) in enumerate(line) if ch != " "]
                self.assertTrue(ink, (cols, rows))
                self.assertTrue(all(0 <= r < rows and 0 <= c < cols for r, c in ink))

    def test_the_clock_moves_between_minutes(self):
        a = EX.clock_layout(100, 30, time.gmtime(START), 10).plain()
        b = EX.clock_layout(100, 30, time.gmtime(START), 11).plain()
        self.assertNotEqual(a, b)

    def test_the_layout_shows_time_and_date(self):
        tm = time.gmtime(1_800_000_000)  # a Friday
        text = EX.clock_layout(100, 30, tm, 0).plain()
        self.assertIn(time.strftime("%A %-d %B", tm), text)

    def test_release_is_awaited_only_for_a_press_without_its_lift(self):
        press = b"\x1b[<0;10;20M"
        lift = b"\x1b[<0;10;20m"
        self.assertTrue(EX.needs_release(press))
        self.assertFalse(EX.needs_release(press + lift))
        self.assertFalse(EX.needs_release(b"x"))
        self.assertFalse(EX.needs_release(b""))
        self.assertTrue(EX.needs_release(lift + press))

    def test_charger_and_display_readers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ps = root / "ps"
            drm = root / "drm"
            for name, kind, online in (("bat", "Battery", None), ("chg", "USB", "1")):
                (ps / name).mkdir(parents=True)
                (ps / name / "type").write_text(kind)
                if online:
                    (ps / name / "online").write_text(online)
            self.assertTrue(EX.charger_online(ps))
            (ps / "chg" / "online").write_text("0\n")
            self.assertFalse(EX.charger_online(ps))
            self.assertFalse(EX.charger_online(root / "nope"))
            self.assertTrue(EX.display_on(root / "nope"), "unknown counts as on")
            (drm / "card0-DSI-1").mkdir(parents=True)
            (drm / "card0-DSI-1" / "status").write_text("connected\n")
            (drm / "card0-DSI-1" / "dpms").write_text("Off\n")
            self.assertFalse(EX.display_on(drm))
            (drm / "card0-DSI-1" / "dpms").write_text("On\n")
            self.assertTrue(EX.display_on(drm))
            (drm / "card0-HDMI-A-1").mkdir()
            (drm / "card0-HDMI-A-1" / "status").write_text("disconnected\n")
            (drm / "card0-HDMI-A-1" / "dpms").write_text("Off\n")
            (drm / "card0-DSI-1" / "dpms").write_text("Off\n")
            self.assertFalse(EX.display_on(drm), "a disconnected connector does not count")

    def test_ttfx_is_run_with_the_capped_frame_rate_and_the_banner(self):
        cmd = EX.ttfx_command("/bin/ttfx", "/b/K230.txt", "wipe", 24)
        self.assertEqual(cmd[:4], ["/bin/ttfx", "-i", "/b/K230.txt", "--frame-rate"])
        self.assertEqual(cmd[4], str(EX.EFFECT_FRAME_RATE))
        self.assertEqual(cmd[-1], "wipe")
        # Centred on the whole terminal, one row short so nothing scrolls.
        self.assertEqual(cmd[cmd.index("--canvas-width") + 1], "0")
        self.assertEqual(cmd[cmd.index("--canvas-height") + 1], "23")
        self.assertEqual(cmd[cmd.index("--anchor-canvas") + 1], "c")
        self.assertIn("--no-restore-cursor", cmd)
        self.assertLessEqual(EX.EFFECT_FRAME_RATE, 15)

    def test_the_banner_is_six_rows_of_block_and_box_glyphs(self):
        text = (ROOT / "nix/exhibition/K230.txt").read_text()
        rows = text.splitlines()
        self.assertEqual(len(rows), 6)
        # Full blocks and box drawing only: foot draws both itself, so no
        # font has to carry them.
        self.assertTrue(set(text) <= set(" \n█╗╔╝╚═║"), set(text))
        self.assertLessEqual(max(len(r) for r in rows), 60)


class LoopTests(unittest.TestCase):
    def test_it_redraws_once_a_minute_and_sleeps_between(self):
        ex, sess, clock, plays, ends = make(inputs={START + 185: b"x"})
        self.assertEqual(ex.run(), "input")
        self.assertEqual(plays, [])
        times = [t for t, _ in sess.frames]
        self.assertEqual(len(times), 4, times)  # minutes 0, 1, 2 and 3
        self.assertEqual([int(t // 60) - int(START // 60) for t in times], [0, 1, 2, 3])
        self.assertEqual(sess.released, [b"x"])

    def test_the_first_effect_comes_soon_and_the_next_after_the_interval(self):
        ex, sess, clock, plays, ends = make(ttfx="/bin/ttfx", inputs={START + 700: b"x"})
        self.assertEqual(ex.run(), "input")
        self.assertEqual([round(t - START) for t, _ in plays], [EX.FIRST_EFFECT_DELAY,
                                                                 EX.FIRST_EFFECT_DELAY + 300,
                                                                 EX.FIRST_EFFECT_DELAY + 600])
        self.assertEqual([e for _, e in plays], list(EX.EFFECTS[:3]))

    def test_no_ttfx_means_no_effects(self):
        ex, sess, clock, plays, ends = make(inputs={START + 400: b"x"})
        ex.run()
        self.assertEqual(plays, [])

    def test_input_during_an_effect_leaves(self):
        ex, sess, clock, plays, ends = make(ttfx="/bin/ttfx")
        ex.play = lambda effect: "input"
        self.assertEqual(ex.run(), "input")

    def test_unplugging_ends_it_within_one_poll(self):
        state = {"on": True}
        ex, sess, clock, plays, ends = make(charger=lambda: state["on"])
        original = sess.wait

        def wait(timeout):
            if clock.now + timeout >= START + 95:
                state["on"] = False  # unplugged during this sleep
            return original(timeout)
        sess.wait = wait
        self.assertEqual(ex.run(), "unplugged")
        self.assertEqual(len(ends), 1)
        self.assertLessEqual(ends[0] - (START + 95), EX.POLL_SECONDS + 0.1)

    def test_it_ends_after_the_cap(self):
        ex, sess, clock, plays, ends = make(max_up=600)
        self.assertEqual(ex.run(), "cap")
        self.assertEqual(len(ends), 1)
        self.assertLessEqual(ends[0] - START, 600 + EX.POLL_SECONDS + 0.1)

    def test_nothing_is_drawn_while_the_display_is_off(self):
        state = {"lit": False}
        ex, sess, clock, plays, ends = make(ttfx="/bin/ttfx", display=lambda: state["lit"],
                                            inputs={START + 400: b"x"})
        ex.run()
        self.assertEqual(sess.frames, [])
        self.assertEqual(plays, [])

    def test_it_wakes_at_most_every_poll_period(self):
        ex, sess, clock, plays, ends = make(inputs={START + 240: b"x"})
        sleeps = []
        original = sess.wait

        def wait(timeout):
            sleeps.append(timeout)
            return original(timeout)
        sess.wait = wait
        ex.run()
        self.assertTrue(all(t <= EX.POLL_SECONDS + 0.1 for t in sleeps), max(sleeps))
        # About 25 wake-ups in four minutes: poll every 10 s, plus minute edges.
        self.assertLess(len(sleeps), 40)

    def test_a_resize_redraws(self):
        ex, sess, clock, plays, ends = make(inputs={START + 20: b"x"})
        script = iter([[("resize",)], [("input", b"x")]])
        sess.wait = lambda timeout: next(script)
        ex.run()
        self.assertEqual(len(sess.frames), 2)


if __name__ == "__main__":
    unittest.main()

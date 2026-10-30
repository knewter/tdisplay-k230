import importlib.util
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "nix" / "term-apps" / "k230_term_apps.py"
spec = importlib.util.spec_from_file_location("k230_term_apps", MODULE)
apps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apps)

J1 = json.dumps({
    "current_condition": [{
        "temp_C": "21", "FeelsLikeC": "19", "humidity": "61",
        "windspeedKmph": "13", "winddir16Point": "NW",
        "weatherDesc": [{"value": "Partly cloudy"}],
    }],
    "weather": [
        {"maxtempC": "23", "mintempC": "14", "hourly": [
            {"time": "0", "tempC": "15", "weatherDesc": [{"value": "Clear"}]},
            {"time": "1200", "tempC": "22", "weatherDesc": [{"value": "Sunny"}]},
            {"time": "1500", "tempC": "23", "weatherDesc": [{"value": "Cloudy"}]},
            {"time": "1800", "tempC": "20", "weatherDesc": [{"value": "Cloudy"}]},
        ]},
        {"maxtempC": "20", "mintempC": "12", "hourly": [
            {"time": "0", "tempC": "13", "weatherDesc": [{"value": "Clear"}]},
            {"time": "300", "tempC": "12", "weatherDesc": [{"value": "Clear"}]},
            {"time": "600", "tempC": "12", "weatherDesc": [{"value": "Fog"}]},
            {"time": "900", "tempC": "17", "weatherDesc": [{"value": "Light rain"}]},
        ]},
    ],
    "nearest_area": [{"areaName": [{"value": "Boston"}], "region": [{"value": "Massachusetts"}]}],
})


class GlyphTests(unittest.TestCase):
    def test_every_glyph_is_five_rows_of_equal_width(self):
        for char, rows in apps._GLYPHS.items():
            self.assertEqual(len(rows), 5, char)
            self.assertEqual(len({len(r) for r in rows}), 1, char)

    def test_digit_rendering_width_and_height(self):
        rows = apps.render_text("12:30", 4, 2)
        self.assertEqual(len(rows), 10)
        self.assertEqual({len(r) for r in rows}, {apps.text_units("12:30") * 4})
        self.assertEqual(apps.text_units("12:30"), 3 * 4 + 1 + 4)

    def test_single_digit_uses_blocks(self):
        rows = apps.render_text("0", 1, 1)
        self.assertEqual(rows, ["█" * 3, "█ █", "█ █", "█ █", "█" * 3])

    def test_scale_fits_and_prefers_square_cells(self):
        for cols, rows in ((102, 23), (80, 24)):
            sx, sy = apps.pick_scale("12:34", cols, rows, reserve_rows=7)
            self.assertLessEqual(apps.text_units("12:34") * sx, cols * 0.7)
            self.assertLessEqual(5 * sy, rows - 7)
            self.assertGreaterEqual(sx, sy)
        self.assertEqual(apps.pick_scale("12:34", 102, 23, 7), (4, 2))

    def test_centring(self):
        self.assertEqual(apps.centre(10, 100), 45)
        self.assertEqual(apps.centre(11, 100), 44)
        self.assertEqual(apps.centre(200, 100), 0)

    def test_frame_clips_and_centres(self):
        f = apps.Frame(10, 3)
        f.put_centred(2, "abcd")
        f.put(3, 9, "xyz")
        lines = f.plain().split("\n")
        self.assertEqual(lines[1], "   abcd")
        self.assertEqual(lines[2], "        xy")


class ButtonTests(unittest.TestCase):
    def test_layout_is_centred_and_in_bounds(self):
        bs = apps.layout_buttons([("a", "Start"), ("b", "Reset")], 100, top=10)
        self.assertEqual(bs[0].y0, 10)
        self.assertEqual(bs[0].y1, 12)
        self.assertLess(bs[0].x1, bs[1].x0)
        self.assertEqual(bs[0].x0 - 1, 100 - bs[1].x1)

    def test_layout_shrinks_to_narrow_terminals(self):
        bs = apps.layout_buttons([("a", "Start"), ("b", "-1 min"), ("c", "+1 min"), ("d", "Reset")], 40, top=1)
        self.assertGreaterEqual(bs[0].x0, 1)
        self.assertLessEqual(bs[-1].x1, 40)

    def test_hit_test(self):
        bs = apps.layout_buttons([("a", "Start"), ("b", "Reset")], 100, top=10)
        a, b = bs
        self.assertEqual(apps.hit_test(bs, a.x0, a.y0), "a")
        self.assertEqual(apps.hit_test(bs, a.x1, a.y1), "a")
        self.assertEqual(apps.hit_test(bs, b.x0 + 1, b.y0 + 1), "b")
        self.assertIsNone(apps.hit_test(bs, a.x1 + 1, a.y0))
        self.assertIsNone(apps.hit_test(bs, a.x0, a.y1 + 1))
        self.assertIsNone(apps.hit_test(bs, a.x0 - 1, a.y0))


class InputTests(unittest.TestCase):
    def test_mouse_press_release_and_keys(self):
        ev, rest = apps.parse_input(b"\x1b[<0;12;7M\x1b[<0;12;7m r")
        self.assertEqual(ev, [("click", 12, 7), ("key", " "), ("key", "r")])
        self.assertEqual(rest, b"")

    def test_wheel_and_drag_are_ignored(self):
        ev, _ = apps.parse_input(b"\x1b[<64;5;5M\x1b[<32;5;5M")
        self.assertEqual(ev, [])

    def test_partial_sequence_is_kept(self):
        ev, rest = apps.parse_input(b"q\x1b[<0;12")
        self.assertEqual(ev, [("key", "q")])
        self.assertEqual(rest, b"\x1b[<0;12")

    def test_lone_escape(self):
        self.assertEqual(apps.parse_input(b"\x1b")[0], [("key", "esc")])


class TimerTests(unittest.TestCase):
    def test_start_pause_resume(self):
        s = apps.timer_new(300)
        s = apps.timer_start(s, 100.0)
        self.assertTrue(s.running)
        self.assertEqual(apps.timer_remaining(s, 130.0), 270)
        s = apps.timer_pause(s, 130.0)
        self.assertFalse(s.running)
        self.assertEqual(s.remaining, 270)
        s = apps.timer_toggle(s, 500.0)
        self.assertEqual(apps.timer_remaining(s, 500.0), 270)

    def test_add_and_subtract_idle_moves_reset_value(self):
        s = apps.timer_add(apps.timer_new(300), 60, 0)
        self.assertEqual((s.remaining, s.initial), (360, 360))
        s = apps.timer_add(apps.timer_new(30), -60, 0)
        self.assertEqual(s.remaining, 0)
        self.assertFalse(apps.timer_start(s, 0).running)

    def test_add_while_running_extends_deadline(self):
        s = apps.timer_start(apps.timer_new(300), 100.0)
        s = apps.timer_add(s, 60, 110.0)
        self.assertEqual(apps.timer_remaining(s, 110.0), 350)
        s = apps.timer_add(s, -600, 110.0)
        self.assertEqual(apps.timer_remaining(s, 110.0), 1)
        self.assertFalse(apps.timer_tick(s, 110.0).expired)

    def test_reset_restores_initial_and_stops(self):
        s = apps.timer_start(apps.timer_new(300), 0.0)
        s = apps.timer_reset(apps.timer_pause(s, 100.0))
        self.assertEqual((s.remaining, s.running, s.expired), (300, False, False))

    def test_expiry_then_reset_and_start(self):
        s = apps.timer_start(apps.timer_new(5), 0.0)
        self.assertEqual(apps.timer_tick(s, 4.9), s)
        s = apps.timer_tick(s, 5.0)
        self.assertTrue(s.expired)
        self.assertFalse(s.running)
        self.assertEqual(apps.timer_remaining(s, 6.0), 0)
        s2 = apps.timer_start(s, 10.0)
        self.assertTrue(s2.running)
        self.assertEqual(apps.timer_remaining(s2, 10.0), 5)
        self.assertEqual(apps.timer_reset(s).remaining, 5)

    def test_clamps(self):
        self.assertEqual(apps.timer_new(-5).remaining, 0)
        self.assertEqual(apps.timer_new(10 ** 9).remaining, apps.MAX_SECONDS)

    def test_actions_and_format(self):
        s = apps.timer_apply(apps.timer_new(60), "toggle", 0.0)
        self.assertTrue(s.running)
        self.assertEqual(apps.format_hms(75), "01:15")
        self.assertEqual(apps.format_hms(3725), "1:02:05")

    def test_delay_is_none_when_idle(self):
        self.assertIsNone(apps.timer_delay(apps.timer_new(60), 0.0))
        s = apps.timer_start(apps.timer_new(60), 0.0)
        self.assertTrue(0 < apps.timer_delay(s, 0.5) <= 1.02)

    def test_frames_show_expected_text(self):
        s = apps.timer_new(300)
        plain = apps.timer_frame(102, 23, s, 0.0).plain()
        self.assertIn("Start", plain)
        self.assertIn("Reset", plain)
        done = apps.timer_tick(apps.timer_start(apps.timer_new(1), 0.0), 2.0)
        self.assertIn("Time's up", apps.timer_frame(102, 23, done, 3.0).plain())


class ClockTests(unittest.TestCase):
    def test_frame_has_date_and_fits(self):
        tm = time.strptime("2026-10-26 09:05:30", "%Y-%m-%d %H:%M:%S")
        plain = apps.clock_frame(102, 23, tm).plain()
        self.assertIn("Monday 26 October", plain)
        self.assertLessEqual(len(plain.split("\n")), 23)

    def test_next_second_delay(self):
        self.assertAlmostEqual(apps.next_second_delay(10.25), 0.76, places=2)

    def test_twelve_hour_digits_and_marker(self):
        def at(hm):
            return time.strptime("2026-10-26 " + hm, "%Y-%m-%d %H:%M")
        self.assertEqual(apps.clock_digits(at("21:05")), "21:05")
        self.assertEqual(apps.clock_digits(at("21:05"), True), "9:05")
        self.assertEqual(apps.clock_digits(at("00:00"), True), "12:00")
        self.assertEqual(apps.clock_digits(at("12:30"), True), "12:30")
        self.assertEqual(apps.clock_text(at("00:10"), True), "12:10 AM")
        self.assertEqual(apps.clock_text(at("12:00"), True), "12:00 PM")
        self.assertEqual(apps.clock_text(at("21:05")), "21:05")
        plain = apps.clock_frame(102, 23, at("21:05"), twelve=True).plain()
        self.assertIn("PM · Monday 26 October", plain)

    def test_local_time_follows_a_zone_change_without_a_restart(self):
        # Settings rewrites /etc/localtime while apps run; TZ stands in for it
        # here, and both are only noticed through tzset.
        saved = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "UTC"
            self.assertEqual(apps.local_time(0).tm_hour, 0)
            os.environ["TZ"] = "Asia/Tokyo"
            self.assertEqual(apps.local_time(0).tm_hour, 9)
        finally:
            if saved is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = saved
            time.tzset()

    def test_the_preference_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(apps.read_twelve_hour(d))
            path = Path(d) / apps.CLOCK_FORMAT_FILE
            for word, want in (("12-hour\n", True), ("24-hour\n", False), ("12", False), ("", False)):
                path.write_text(word)
                self.assertEqual(apps.read_twelve_hour(d), want, word)


class WeatherTests(unittest.TestCase):
    def test_parse_j1(self):
        snap = apps.parse_wttr_j1(J1, 10, now=1000)
        self.assertEqual(snap["location"], "Boston")
        self.assertEqual(snap["region"], "Massachusetts")
        self.assertEqual(snap["condition"], "Partly cloudy")
        self.assertEqual((snap["temperature_c"], snap["feels_like_c"]), (21, 19))
        self.assertEqual((snap["high_c"], snap["low_c"]), (23, 14))
        self.assertEqual((snap["humidity"], snap["wind_kmph"], snap["wind_dir"]), (61, 13, "NW"))
        self.assertEqual(snap["fetched_unix_secs"], 1000)
        self.assertEqual([s["label"] for s in snap["slots"]], ["12pm", "3pm", "6pm", "12am", "3am", "6am"])
        self.assertEqual(len(snap["forecast"]), 5)

    def test_parse_rejects_non_j1(self):
        self.assertIsNone(apps.parse_wttr_j1("<html>rate limited</html>", 0))
        self.assertIsNone(apps.parse_wttr_j1("{}", 0))

    def test_stale_decision(self):
        self.assertTrue(apps.is_stale(None, 5000))
        snap = {"fetched_unix_secs": 1000}
        self.assertFalse(apps.is_stale(snap, 1000 + 1799))
        self.assertTrue(apps.is_stale(snap, 1000 + 1800))

    def test_fahrenheit(self):
        self.assertEqual(apps.fahrenheit(21), 70)
        self.assertEqual(apps.fahrenheit(-5), 23)

    def test_cache_path(self):
        self.assertEqual(apps.cache_path({"XDG_CACHE_HOME": "/x", "HOME": "/h"}), "/x/k230-shell/weather.json")
        self.assertEqual(apps.cache_path({"HOME": "/h"}), "/h/.cache/k230-shell/weather.json")
        self.assertIsNone(apps.cache_path({}))

    def test_cache_roundtrip_is_atomic_and_widget_shaped(self):
        snap = apps.parse_wttr_j1(J1, 10, now=1000)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "weather.json")
            apps.save_cache(path, snap)
            self.assertEqual(os.listdir(os.path.dirname(path)), ["weather.json"])
            self.assertEqual(apps.load_cache(path), snap)
            for key in ("location", "condition", "temperature_c", "feels_like_c",
                        "high_c", "low_c", "forecast", "fetched_unix_secs"):
                self.assertIn(key, snap)
            self.assertIsNone(apps.load_cache(os.path.join(d, "missing.json")))

    def test_frames(self):
        snap = apps.parse_wttr_j1(J1, 10, now=1000)
        frame, buttons = apps.weather_frame(102, 23, snap, False, 1000)
        plain = frame.plain()
        self.assertIn("Boston, Massachusetts", plain)
        self.assertIn("Humidity 61%", plain)
        self.assertEqual(buttons[0].key, "refresh")
        off, buttons = apps.weather_frame(80, 24, None, True, 1000)
        self.assertIn("No weather data", off.plain())
        self.assertIn("Retry", off.plain())
        self.assertEqual(apps.hit_test(buttons, buttons[0].x0, buttons[0].y0), "refresh")


class TimerHelpers(unittest.TestCase):
    """A fake broker, and a fake timer socket that starts instances."""

    def serve(self, directory):
        import socket
        import threading
        path = os.path.join(directory, "events.sock")
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(path)
        listener.listen(4)
        received = []

        def loop():
            while True:
                try:
                    conn, _ = listener.accept()
                except OSError:
                    return
                with conn:
                    received.append(json.loads(conn.makefile().readline()))
                    conn.sendall(b'{"state":"accepted","id":1}\n')

        threading.Thread(target=loop, daemon=True).start()
        self.addCleanup(listener.close)
        return path, received

    def wait_gone(self, pid, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            except PermissionError:
                return False
            try:
                os.waitpid(pid, os.WNOHANG)  # reap it when it is our child
            except ChildProcessError:
                pass
            time.sleep(0.02)
        return False

    def use_broker(self, sock):
        old = os.environ.get("K230_NOTIFICATION_SOCKET")
        os.environ["K230_NOTIFICATION_SOCKET"] = sock
        self.addCleanup(lambda: os.environ.pop("K230_NOTIFICATION_SOCKET", None) if old is None
                        else os.environ.__setitem__("K230_NOTIFICATION_SOCKET", old))

    def fake_timer_socket(self, directory, state_dir):
        """Stand in for k230-timer.socket: for each connection start a
        `timerd-serve` instance in its own session and process group, with the
        connection as stdin, as systemd does with Accept=yes. Returns (path,
        instances); each instance is a Popen that is not a child of the card's
        process group."""
        import socket
        import subprocess
        import sys
        import threading
        path = os.path.join(directory, "k230-timer.sock")
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(path)
        listener.listen(4)
        instances = []
        env = dict(os.environ, K230_TIMER_STATE_DIR=state_dir)

        def loop():
            while True:
                try:
                    conn, _ = listener.accept()
                except OSError:
                    return
                instances.append(subprocess.Popen(
                    [sys.executable, str(MODULE), "timerd-serve"], stdin=conn,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True, env=env))
                conn.close()

        threading.Thread(target=loop, daemon=True).start()
        self.addCleanup(listener.close)
        self.addCleanup(lambda: [p.kill() or p.wait() for p in instances if p.poll() is None])
        return path, instances


class TimerAlertTests(TimerHelpers):
    """Expiry reaches the broker, and survives a closed card (host only)."""

    def test_expiry_request_is_important_and_unredacted(self):
        request = apps.timer_expiry_request(300)
        self.assertEqual((request["operation"], request["priority"], request["tag"]), ("emit", "important", "timer"))
        self.assertIs(request["private"], False)
        self.assertEqual(request["body"], "05:00 elapsed")

    def test_notify_broker_posts_and_never_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            path, received = self.serve(directory)
            self.assertTrue(apps.notify_broker(apps.timer_expiry_request(60), path))
            self.assertEqual(received[0]["summary"], "Timer finished")
            self.assertFalse(apps.notify_broker({}, os.path.join(directory, "missing.sock")))

    def test_helper_sleeps_to_the_deadline_then_posts_once(self):
        sent, naps, now = [], [], [0.0]
        def sleep(seconds):
            naps.append(seconds)
            now[0] += seconds
        with tempfile.TemporaryDirectory() as directory:
            state = os.path.join(directory, "t.json")
            with open(state, "w") as handle:
                json.dump({"pid": os.getpid(), "deadline": 90.0, "initial": 90}, handle)
            apps.run_timerd(90.0, 90, state, clock=lambda: now[0], sleep=sleep, notify=sent.append)
            self.assertEqual(naps, [90.0])
            self.assertEqual([r["body"] for r in sent], ["01:30 elapsed"])
            self.assertFalse(os.path.exists(state))

    def test_closing_the_card_leaves_a_helper_that_alerts(self):
        with tempfile.TemporaryDirectory() as directory:
            sock, received = self.serve(directory)
            state_path = os.path.join(directory, "k230-timer.json")
            now = time.monotonic()
            state = apps.TimerState(5, 5, True, now + 0.4, False)
            self.use_broker(sock)
            pid = apps.timer_detach(state, state_path, os.path.join(directory, "absent.sock"))
            self.assertIsNotNone(pid)
            self.assertEqual(apps.timer_pending(state_path)["initial"], 5)
            self.assertTrue(self.wait_gone(pid))
            self.assertEqual([r["summary"] for r in received], ["Timer finished"])
            self.assertFalse(os.path.exists(state_path))

    def test_reopened_card_adopts_the_running_countdown(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "k230-timer.json")
            now = time.monotonic()
            pid = apps.timer_detach(apps.TimerState(120, 120, True, now + 60, False), state_path,
                                    os.path.join(directory, "absent.sock"))
            self.addCleanup(self.wait_gone, pid)
            adopted = apps.timer_adopt(state_path, now + 10)
            self.assertTrue(adopted.running)
            self.assertEqual((adopted.initial, apps.timer_remaining(adopted, now + 10)), (120, 50))
            self.assertTrue(self.wait_gone(pid))  # stopped by the adopter, so it never alerts
            self.assertFalse(os.path.exists(state_path))
            self.assertIsNone(apps.timer_adopt(state_path, now))

    def test_paused_or_expired_timers_leave_no_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = os.path.join(directory, "k230-timer.json")
            self.assertIsNone(apps.timer_detach(apps.timer_new(30), state_path))
            self.assertFalse(os.path.exists(state_path))


class TimerSurvivesShellRestartTests(TimerHelpers):
    """The waiting part is a socket-activated instance, not a child of the
    shell or its card (pending-timers-survive-restarts task 2.1, host only)."""

    def test_stopping_the_cards_process_group_does_not_stop_the_timer(self):
        import signal
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            broker, received = self.serve(directory)
            state_dir = os.path.join(directory, "state")
            os.mkdir(state_dir)
            self.use_broker(broker)
            timer_sock, instances = self.fake_timer_socket(directory, state_dir)
            state_path = os.path.join(state_dir, "k230-timer.json")
            # The "card" is its own process group (the shell's session): it
            # hands the countdown over the socket, then the group is killed
            # the way `systemctl restart shell` kills a cgroup.
            card = subprocess.Popen(
                [sys.executable, "-c",
                 "import importlib.util,sys,time\n"
                 f"s=importlib.util.spec_from_file_location('m',{str(MODULE)!r});m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
                 "st=m.TimerState(5,5,True,time.monotonic()+0.8,False)\n"
                 f"pid=m.timer_detach(st,{state_path!r},{timer_sock!r})\n"
                 "print(pid,flush=True);time.sleep(60)\n"],
                stdout=subprocess.PIPE, start_new_session=True, text=True,
                env=dict(os.environ, K230_NOTIFICATION_SOCKET=broker))
            instance_pid = int(card.stdout.readline())
            self.assertEqual(len(instances), 1)
            self.assertEqual(instance_pid, instances[0].pid)
            self.assertNotEqual(os.getpgid(instance_pid), os.getpgid(card.pid))
            self.assertEqual(apps.timer_pending(state_path)["initial"], 5)
            os.killpg(card.pid, signal.SIGKILL)
            card.wait(timeout=5)
            card.stdout.close()
            self.assertIsNone(instances[0].poll())  # still waiting
            instances[0].wait(timeout=5)
            self.assertEqual(instances[0].returncode, 0)
            self.assertEqual([r["summary"] for r in received], ["Timer finished"])
            self.assertEqual(received[0]["body"], "00:05 elapsed")
            self.assertFalse(os.path.exists(state_path))

    def test_adopting_ends_the_instance_without_an_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            broker, received = self.serve(directory)
            state_dir = os.path.join(directory, "state")
            os.mkdir(state_dir)
            self.use_broker(broker)
            timer_sock, instances = self.fake_timer_socket(directory, state_dir)
            state_path = os.path.join(state_dir, "k230-timer.json")
            now = time.monotonic()
            pid = apps.timer_detach(apps.TimerState(120, 120, True, now + 60, False), state_path, timer_sock)
            self.assertEqual(pid, instances[0].pid)
            adopted = apps.timer_adopt(state_path, time.monotonic())
            self.assertTrue(adopted.running)
            # The deadline the instance recorded is the card's, to a few ms.
            self.assertAlmostEqual(adopted.deadline, now + 60, delta=0.5)
            instances[0].wait(timeout=5)
            self.assertEqual(received, [])
            self.assertFalse(os.path.exists(state_path))

    def test_a_paused_card_hands_nothing_to_the_socket(self):
        with tempfile.TemporaryDirectory() as directory:
            state_dir = os.path.join(directory, "state")
            os.mkdir(state_dir)
            timer_sock, instances = self.fake_timer_socket(directory, state_dir)
            paused = apps.timer_pause(apps.timer_start(apps.timer_new(60), time.monotonic()), time.monotonic())
            self.assertIsNone(apps.timer_detach(paused, os.path.join(state_dir, "k230-timer.json"), timer_sock))
            reset = apps.timer_reset(paused)
            self.assertIsNone(apps.timer_detach(reset, os.path.join(state_dir, "k230-timer.json"), timer_sock))
            time.sleep(0.1)
            self.assertEqual(instances, [])

    def test_a_bad_request_is_refused_without_a_record(self):
        import socket
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "k230-timer.json")
            for raw in (b"not json\n", b'{"left":-1,"initial":5}\n', b'{"left":5}\n', b""):
                a, b = socket.socketpair()
                a.sendall(raw)
                a.shutdown(socket.SHUT_WR)
                self.assertIsNone(apps.serve_timer_request(b, path))
                a.close()
                b.close()
            self.assertEqual(os.listdir(directory), [])


if __name__ == "__main__":
    unittest.main()

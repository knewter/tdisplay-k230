#!/usr/bin/env python3
"""Execute the event model and real local broker; never claim panel/focus proof."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("notification_center", ROOT / "tools/notification_center.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SOURCE = {"id": "shell", "name": "Shell", "icon": "applications-system"}


class Notifications(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.targets = {12}
        self.focused = []
        def action(target, execute=False):
            if target not in self.targets:
                return False
            if execute:
                self.focused.append(target)
            return True
        self.history = module.History(clock=lambda: self.now, wall=lambda: 1234, action=action)

    def emit(self, **values):
        return self.history.emit({"summary": "Example", **values}, SOURCE)["id"]

    def test_priority(self):
        ordinary = self.emit(priority="ordinary")
        critical = self.emit(priority="critical")
        important = self.emit(priority="important")
        self.assertEqual([row["id"] for row in self.history.snapshot()["events"]], [critical, important, ordinary])

    def breakthrough(self, data, source=SOURCE):
        self.history = module.History(clock=lambda: self.now, wall=lambda: 1234)
        self.history.emit({"summary": "Example", **data}, source)
        state = self.history.snapshot()
        self.assertNotIn("breakthrough", state["events"][0])
        return state["preview"]["breakthrough"]

    def test_preview_breakthrough_flag(self):
        self.assertTrue(self.breakthrough({"priority": "critical", "ongoing": True}))
        self.assertTrue(self.breakthrough({"priority": "important", "private": False}))
        self.assertFalse(self.breakthrough({"priority": "ordinary"}))
        delegate = {"id": "dbus", "name": "Desktop notifications", "icon": None, "delegate": True}
        app = {"app": {"id": "chat", "name": "Chat"}}
        self.assertFalse(self.breakthrough({"priority": "important", **app}, delegate))
        self.assertFalse(self.breakthrough({"priority": "critical", **app}, delegate))
        sms = {"id": "sms", "name": "Messages", "icon": None}
        self.assertFalse(self.breakthrough({"priority": "ordinary"}, sms))
        self.assertFalse(self.breakthrough({"priority": "important"}, None))

    def test_privacy(self):
        self.emit(body="private text", summary="Private subject", target=12)
        state = self.history.snapshot()
        self.assertNotIn("Private subject", json.dumps(state["preview"]))
        self.assertNotIn("private text", json.dumps(state["preview"]))
        self.assertIsNone(state["preview"]["icon"])
        self.assertEqual(state["events"][0]["body"], "private text")
        self.assertFalse(state["preview"]["focus"])
        self.assertEqual(self.focused, [])

    def test_retention_deduplication_and_expiry(self):
        one = self.emit(tag="connection")
        self.assertEqual(self.emit(tag="connection", summary="Updated"), one)
        for index in range(100):
            self.emit(summary=str(index))
        self.assertEqual(self.history.snapshot()["count"], module.MAX_EVENTS)
        self.now += 3601
        self.assertEqual(self.history.snapshot()["count"], 0)

    def test_unknown_source(self):
        self.history.emit({"source": "System", "priority": "critical", "ongoing": True,
                           "private": False, "target": 12, "summary": "secret", "body": "body"}, None)
        state = self.history.snapshot()
        row = state["events"][0]
        self.assertEqual(row["source"], "Unknown source")
        self.assertEqual(row["priority"], "ordinary")
        self.assertTrue(row["dismissible"])
        self.assertFalse(row["action_available"])
        self.assertNotIn("secret", json.dumps(state["preview"]))

    def test_preview_timeout_preserves_history(self):
        self.emit()
        self.assertIsNotNone(self.history.snapshot()["preview"])
        self.now += 6
        self.assertIsNone(self.history.snapshot()["preview"])
        self.assertEqual(self.history.snapshot()["count"], 1)

    def test_action_gone_and_retry(self):
        identity = self.emit(target=12)
        self.targets.clear()
        result = self.history.request({"operation": "action", "id": identity}, SOURCE)
        self.assertEqual(result["error"], "target-unavailable")
        self.assertEqual(self.history.snapshot()["count"], 1)
        self.assertFalse(self.history.snapshot()["events"][0]["action_available"])
        self.targets.add(12)
        self.assertEqual(self.history.request({"operation": "action", "id": identity}, SOURCE)["state"], "requested")
        self.assertEqual(self.focused, [12])

    def test_critical_retained_until_resolved(self):
        identity = self.emit(priority="critical", ongoing=True, tag="recovery")
        self.now += 4000
        self.assertEqual(self.history.request({"operation": "dismiss", "id": identity}, SOURCE)["error"], "critical-retained")
        self.history.request({"operation": "dismiss-all"}, SOURCE)
        self.assertEqual(self.history.snapshot()["count"], 1)
        self.emit(priority="ordinary", ongoing=False, tag="recovery")
        self.assertEqual(self.history.request({"operation": "dismiss", "id": identity}, SOURCE)["state"], "dismissed")

    def test_critical_flood_is_bounded(self):
        for _ in range(module.MAX_EVENTS):
            self.emit(priority="critical", ongoing=True)
        self.assertEqual(self.history.emit({"summary": "overflow"}, SOURCE)["error"], "history-full")
        self.assertEqual(self.history.snapshot()["count"], module.MAX_EVENTS)

    def test_broker_socket_and_restart(self):
        with tempfile.TemporaryDirectory(prefix="k230-notifications-") as directory:
            root = Path(directory)
            path = root / "events.sock"
            command = [sys.executable, str(ROOT / "tools/notification_center.py"), "serve", "--socket", str(path)]
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            def wait_ready():
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail(process.stderr.read().decode())
                    try:
                        return module.call(path, {"operation": "history"})
                    except (OSError, ValueError):
                        time.sleep(.02)
                self.fail("broker did not become ready")
            try:
                self.assertEqual(wait_ready()["count"], 0)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                result = module.call(path, {"operation": "emit", "summary": "Socket example"})
                self.assertEqual(result["state"], "accepted")
                self.assertEqual(module.call(path, {"operation": "history"})["count"], 1)
                # An unfinished request must not stall other clients.
                with socket.socket(socket.AF_UNIX) as stalled:
                    stalled.connect(str(path))
                    stalled.sendall(b'{"operation":')
                    self.assertEqual(module.call(path, {"operation": "history"})["count"], 1)
                process.kill()
                process.wait(timeout=3)
                process.stderr.close()
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                self.assertEqual(wait_ready()["count"], 0)
            finally:
                process.terminate()
                process.wait(timeout=3)
                process.stderr.close()
            self.assertFalse(path.exists())


DELEGATE = {"id": "dbus", "name": "Applications", "icon": None, "delegate": True}
APP = {"id": "calc", "name": "Calculator"}


class AppNotices(unittest.TestCase):
    """The broker records why an app's event closed and keeps its actions."""

    def setUp(self):
        self.now = 100.0
        self.history = module.History(clock=lambda: self.now, wall=lambda: 1234)
        self.history.listeners = 1

    def emit(self, tag="dbus-1", app=APP, source=DELEGATE, **values):
        data = {"operation": "emit", "summary": "Done", "app": app, "tag": tag, **values}
        result = self.history.request(data, source)
        self.assertEqual(result["state"], "accepted")
        return result["id"]

    def drain(self):
        notices, self.history.outbox = self.history.outbox, []
        return notices

    def test_dismissal_is_reason_two_and_expiry_reason_one(self):
        first = self.emit("dbus-1")
        self.emit("dbus-2")
        self.assertEqual(self.history.request({"operation": "dismiss", "id": first}, SOURCE)["state"], "dismissed")
        self.assertEqual(self.drain(), [{"event": "closed", "tag": "dbus-1", "reason": 2}])
        self.now += 3600
        self.history.prune()
        self.assertEqual(self.drain(), [{"event": "closed", "tag": "dbus-2", "reason": 1}])

    def test_dismiss_all_tells_every_app_event_and_withdraw_tells_nobody(self):
        self.emit("dbus-1")
        self.emit("dbus-2")
        self.history.request({"operation": "emit", "summary": "Shell's own"}, SOURCE)
        self.history.request({"operation": "withdraw", "app": APP, "tag": "dbus-1"}, DELEGATE)
        self.assertEqual(self.drain(), [])  # the app closed it: the adaptor signals reason 3 itself
        self.history.request({"operation": "dismiss-all"}, SOURCE)
        self.assertEqual(self.drain(), [{"event": "closed", "tag": "dbus-2", "reason": 2}])

    def test_actions_are_kept_clamped_and_shown_as_labels(self):
        rows = [{"key": "open", "label": " Open  now "}, {"key": "", "label": "No key"},
                {"key": "snooze", "label": "Snooze"}, {"key": "third", "label": "Third"}, "junk"]
        self.emit(actions=rows)
        event = self.history.snapshot()["events"][0]
        self.assertEqual(event["actions"], ["Open now", "Snooze"])
        self.assertNotIn("open", json.dumps(event))  # keys stay in the broker
        # Only apps speak for actions; the shell's own events carry none.
        self.history.emit({"summary": "Own", "actions": rows}, SOURCE)
        self.assertEqual([row["actions"] for row in self.history.snapshot()["events"] if row["summary"] == "Own"], [[]])

    def test_invoke_sends_the_key_then_closes_as_dismissed(self):
        identity = self.emit(actions=[{"key": "open", "label": "Open"}, {"key": "snooze", "label": "Snooze"}])
        self.assertEqual(self.history.request({"operation": "invoke", "id": identity, "index": 1}, SOURCE)["state"], "invoked")
        self.assertEqual(self.drain(), [{"event": "action", "tag": "dbus-1", "key": "snooze"},
                                        {"event": "closed", "tag": "dbus-1", "reason": 2}])
        self.assertEqual(self.history.snapshot()["count"], 0)

    def test_invoke_refuses_a_bad_index_and_an_absent_app(self):
        identity = self.emit(actions=[{"key": "open", "label": "Open"}])
        for index in (1, -1, "0", None, True):
            self.assertEqual(self.history.request({"operation": "invoke", "id": identity, "index": index}, SOURCE)["error"],
                             "no-such-action")
        self.history.listeners = 0
        refused = self.history.request({"operation": "invoke", "id": identity, "index": 0}, SOURCE)
        self.assertEqual((refused["state"], refused["error"]), ("failed", "app-unavailable"))
        self.assertEqual((self.history.snapshot()["count"], self.drain()), (1, []))

    def test_subscription_over_the_socket_hears_dismissal_and_action(self):
        with tempfile.TemporaryDirectory(prefix="k230-notifications-") as directory:
            root = Path(directory)
            path = root / "events.sock"
            trusted = root / "trusted.json"
            trusted.write_text(json.dumps({f"{sys.executable} {Path(__file__).resolve()}": DELEGATE}))
            process = subprocess.Popen([sys.executable, str(ROOT / "tools/notification_center.py"), "serve",
                                        "--socket", str(path), "--trusted", str(trusted)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(150):
                    try:
                        module.call(path, {"operation": "history"})
                        break
                    except (OSError, ValueError):
                        time.sleep(.02)
                with socket.socket(socket.AF_UNIX) as listener:
                    listener.settimeout(3)
                    listener.connect(str(path))
                    listener.sendall(b'{"operation":"subscribe"}\n')
                    reader = listener.makefile("rb")
                    self.assertEqual(json.loads(reader.readline()), {"state": "subscribed"})
                    one = module.call(path, {"operation": "emit", "summary": "A", "app": APP, "tag": "dbus-1",
                                             "actions": [{"key": "open", "label": "Open"}]})["id"]
                    two = module.call(path, {"operation": "emit", "summary": "B", "app": APP, "tag": "dbus-2"})["id"]
                    self.assertEqual(module.call(path, {"operation": "invoke", "id": one, "index": 0})["state"], "invoked")
                    self.assertEqual(module.call(path, {"operation": "dismiss", "id": two})["state"], "dismissed")
                    self.assertEqual([json.loads(reader.readline()) for _ in range(3)],
                                     [{"event": "action", "tag": "dbus-1", "key": "open"},
                                      {"event": "closed", "tag": "dbus-1", "reason": 2},
                                      {"event": "closed", "tag": "dbus-2", "reason": 2}])
                    reader.close()
                # Without a subscriber an action is refused, not lost.
                # (the broker notices the hang-up on its next pass, so retry with fresh events)
                for number in range(3, 60):
                    fresh = module.call(path, {"operation": "emit", "summary": "C", "app": APP, "tag": f"dbus-{number}",
                                               "actions": [{"key": "open", "label": "Open"}]})["id"]
                    refused = module.call(path, {"operation": "invoke", "id": fresh, "index": 0})
                    if refused.get("error") == "app-unavailable":
                        break
                    time.sleep(.02)
                self.assertEqual(refused["error"], "app-unavailable")
            finally:
                process.terminate()
                process.wait(timeout=3)

    def test_only_the_delegate_may_subscribe(self):
        with tempfile.TemporaryDirectory(prefix="k230-notifications-") as directory:
            path = Path(directory) / "events.sock"
            process = subprocess.Popen([sys.executable, str(ROOT / "tools/notification_center.py"), "serve",
                                        "--socket", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(150):
                    try:
                        module.call(path, {"operation": "history"})
                        break
                    except (OSError, ValueError):
                        time.sleep(.02)
                self.assertEqual(module.call(path, {"operation": "subscribe"})["error"], "not-the-delegate")
            finally:
                process.terminate()
                process.wait(timeout=3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--sway", type=Path, default=os.environ.get("CARD_SHELL_SWAY"),
                        help="exact cross-built Sway executable for QEMU UI cases")
    parser.add_argument("--rust", type=Path, default=os.environ.get("K230_SHELL_RUST"),
                        help="exact cross-built Rust client for QEMU UI cases")
    args = parser.parse_args()
    groups = {"priority": ["test_priority"], "privacy": ["test_privacy"],
              "retention": ["test_retention_deduplication_and_expiry", "test_critical_flood_is_bounded"],
              "unknown-source": ["test_unknown_source", "test_broker_socket_and_restart"],
              "preview-timeout": ["test_preview_timeout_preserves_history"],
              "action-gone": ["test_action_gone_and_retry"],
              "critical": ["test_critical_retained_until_resolved"],
              "critical-retained": ["test_critical_retained_until_resolved"]}
    ui_cases = {"history-flick-stop", "swipe-cancel", "swipe-dismiss"}
    if any(case not in groups and case not in ui_cases for case in args.case):
        parser.error("unknown case")
    run_ui = any(case in ui_cases for case in args.case)
    if run_ui and (not args.sway or not args.rust):
        parser.error("QEMU UI cases require --sway and --rust (or CARD_SHELL_SWAY and K230_SHELL_RUST)")
    names = sorted({name for case in args.case for name in groups.get(case, [])})
    suite = (unittest.TestSuite(Notifications(name) for name in names) if args.case
             else unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Notifications),
                                    unittest.defaultTestLoader.loadTestsFromTestCase(AppNotices)]))
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise SystemExit(1)
    if run_ui:
        raise SystemExit(subprocess.call([
            sys.executable, str(ROOT / "tests/rust_notification_motion_qemu.py"),
            "--sway", str(args.sway), "--rust", str(args.rust),
        ]))

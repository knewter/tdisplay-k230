#!/usr/bin/env python3
"""Notifications adaptor and the broker's delegated-app trust rule (host only).

The D-Bus case runs a private session bus, the real broker and the real
adaptor, and needs dbus-daemon and jeepney; it is skipped without them. Nothing
here is evidence of a banner on the panel.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


broker = load("notification_center", "tools/notification_center.py")
adaptor = load("notification_dbus", "tools/notification_dbus.py")
DELEGATE = {"id": "dbus", "name": "Applications", "icon": None, "delegate": True}
SHELL = {"id": "shell", "name": "Shell", "icon": "applications-system"}


class Delegation(unittest.TestCase):
    def setUp(self):
        self.history = broker.History(clock=lambda: 100.0, wall=lambda: 1234, action=lambda t, execute=False: True)

    def emit(self, app, **values):
        data = {"operation": "emit", "summary": "Hello", "body": "secret body", "app": app, **values}
        self.assertEqual(self.history.request(data, DELEGATE)["state"], "accepted")
        return self.history.snapshot()

    def test_app_label_icon_and_privacy_defaults(self):
        state = self.emit({"id": "org.gnome.Calculator", "name": "Calculator", "icon": "calc-icon"})
        row = state["events"][0]
        self.assertEqual((row["source"], row["icon"]), ("Calculator", "calc-icon"))
        self.assertEqual(state["preview"]["summary"], "New notification")
        self.assertNotIn("secret", json.dumps(state["preview"]))
        self.assertIsNone(state["preview"]["icon"])

    def test_app_cannot_claim_shell_or_system(self):
        for claim in ("Shell", "  SYSTEM ", "S​hell", "sh-ell!", "System Update", "Unknown source", "Notification"):
            self.history = broker.History(clock=lambda: 100.0, wall=lambda: 1, action=lambda t, execute=False: True)
            row = self.emit({"id": "evil", "name": claim})["events"][0]
            self.assertEqual(row["source"], "Application", claim)
        self.assertNotEqual(self.history.events[1]["source_id"], "shell")
        self.assertTrue(self.history.events[1]["source_id"].startswith("app:"))

    def test_icon_must_be_a_theme_name(self):
        for icon in ("/etc/passwd", "../x", "a b", 5, None):
            self.history = broker.History(clock=lambda: 100.0, wall=lambda: 1, action=lambda t, execute=False: True)
            self.assertIsNone(self.emit({"id": "a", "name": "A", "icon": icon})["events"][0]["icon"])

    def test_app_is_clamped_to_important_and_cannot_target_or_pin(self):
        state = self.emit({"id": "a", "name": "A"}, priority="critical", ongoing=True, target=12, private=False)
        row = state["events"][0]
        self.assertEqual(row["priority"], "important")
        self.assertTrue(row["dismissible"])
        self.assertFalse(row["action_available"])
        # Even a delegate cannot opt an app's text out of preview redaction.
        self.assertEqual(state["preview"]["summary"], "New notification")

    def test_tags_are_per_app_and_withdraw_is_scoped(self):
        self.emit({"id": "a", "name": "A"}, tag="dbus-1")
        self.emit({"id": "b", "name": "B"}, tag="dbus-1")
        self.assertEqual(self.history.snapshot()["count"], 2)
        self.emit({"id": "a", "name": "A"}, tag="dbus-1", summary="Updated")
        self.assertEqual(self.history.snapshot()["count"], 2)
        withdraw = {"operation": "withdraw", "app": {"id": "a"}, "tag": "dbus-1"}
        self.assertEqual(self.history.request(withdraw, DELEGATE)["state"], "dismissed")
        self.assertEqual([row["source"] for row in self.history.snapshot()["events"]], ["B"])
        self.assertEqual(self.history.request(withdraw, DELEGATE)["error"], "event-gone")

    def test_only_the_delegate_may_withdraw_or_speak_for_apps(self):
        self.emit({"id": "a", "name": "A"}, tag="t")
        withdraw = {"operation": "withdraw", "app": {"id": "a"}, "tag": "t"}
        self.assertEqual(self.history.request(withdraw, SHELL)["error"], "event-gone")
        self.assertEqual(self.history.request(withdraw, None)["error"], "event-gone")
        # An unknown peer claiming an app is still unknown.
        self.history.request({"operation": "emit", "summary": "x", "app": {"id": "a", "name": "A"}}, None)
        self.assertEqual(self.history.snapshot()["events"][0]["source"], "Unknown source")

    def test_trusted_map_keys_resolve_and_match_scripts(self):
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / "real"
            real.write_text("")
            link = Path(directory) / "link"
            link.symlink_to(real)
            normalized = broker.normalize_trusted({f"{link} {link}": DELEGATE})
            self.assertEqual(list(normalized), [f"{real} {real}"])


class Adapting(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.adaptor = adaptor.Adaptor(lambda request: self.sent.append(request) or {"state": "accepted"})

    def notify(self, name="Calculator", replaces=0, icon="", summary="Done", body="<b>ok</b>", hints=None):
        return self.adaptor.notify(name, replaces, icon, summary, body, [], hints or {}, -1)[0]

    def test_urgency_maps_and_defaults_stay_with_the_broker(self):
        self.notify(hints={"urgency": ("y", 2)})
        self.notify(hints={"urgency": ("y", 1)})
        self.notify()
        self.assertEqual([r["priority"] for r in self.sent], ["important", "ordinary", "ordinary"])
        for request in self.sent:
            for forbidden in ("private", "ongoing", "target"):
                self.assertNotIn(forbidden, request)
        self.assertEqual(self.sent[0]["body"], "ok")

    def test_desktop_entry_names_the_app_and_icon(self):
        self.notify(name="", hints={"desktop-entry": ("s", "org.gnome.Calculator.desktop")})
        self.assertEqual(self.sent[0]["app"], {"id": "org.gnome.Calculator", "name": "Calculator", "icon": "org.gnome.Calculator"})

    def test_replace_keeps_id_only_for_the_same_app(self):
        first = self.notify(name="A")
        self.assertEqual(self.notify(name="A", replaces=first), first)
        self.assertEqual(self.sent[1]["tag"], self.sent[0]["tag"])
        other = self.notify(name="B", replaces=first)
        self.assertNotEqual(other, first)

    def test_close_withdraws_once(self):
        identity = self.notify()
        self.assertTrue(self.adaptor.close(identity))
        self.assertEqual(self.sent[-1], {"operation": "withdraw", "app": {"id": "Calculator"}, "tag": f"dbus-{identity}"})
        self.assertFalse(self.adaptor.close(identity))
        self.assertFalse(self.adaptor.close(9999))

    def test_actions_are_forwarded_as_key_label_rows(self):
        self.adaptor.notify("Calc", 0, "", "Done", "", ["default", "Body", "open", "Open", "snooze", "Snooze", "x", "Third"], {}, -1)
        self.assertEqual(self.sent[0]["actions"], [{"key": "open", "label": "Open"}, {"key": "snooze", "label": "Snooze"}])
        self.adaptor.notify("Calc", 0, "", "Done", "", ["odd"], {}, -1)
        self.assertNotIn("actions", self.sent[1])
        self.assertIn("actions", adaptor.CAPABILITIES)

    def test_broker_notices_become_the_specification_signals(self):
        identity = self.notify()
        self.assertEqual(self.adaptor.broker_notice({"event": "action", "tag": f"dbus-{identity}", "key": "open"}),
                         ("ActionInvoked", "us", (identity, "open")))
        self.assertEqual(self.adaptor.broker_notice({"event": "closed", "tag": f"dbus-{identity}", "reason": 2}),
                         ("NotificationClosed", "uu", (identity, 2)))
        # Said once; a later close from the app is then not a known id.
        self.assertIsNone(self.adaptor.broker_notice({"event": "closed", "tag": f"dbus-{identity}", "reason": 1}))
        self.assertFalse(self.adaptor.close(identity))
        other = self.notify()
        self.assertEqual(self.adaptor.broker_notice({"event": "closed", "tag": f"dbus-{other}", "reason": 1})[2], (other, 1))
        third = self.notify()
        for bad in ({"event": "closed", "tag": f"dbus-{third}", "reason": 3}, {"event": "x"}, {"tag": "timer"}, [], None,
                    {"event": "action", "tag": "dbus-999", "key": "a"}, {"event": "action", "tag": f"dbus-{third}", "key": 5}):
            self.assertIsNone(self.adaptor.broker_notice(bad), bad)

    def test_broker_down_still_returns_an_id(self):
        def down(request):
            raise ConnectionRefusedError()
        self.adaptor.forward = down
        self.assertEqual(self.notify(), 1)

    def test_known_ids_are_bounded(self):
        for _ in range(adaptor.MAX_KNOWN + 20):
            self.notify()
        self.assertEqual(len(self.adaptor.known), adaptor.MAX_KNOWN)


@unittest.skipUnless(shutil.which("dbus-daemon") and importlib.util.find_spec("jeepney"), "needs dbus-daemon and jeepney")
class Integration(unittest.TestCase):
    def test_notify_send_path_reaches_the_broker(self):
        from jeepney import DBusAddress, new_method_call
        from jeepney.io.blocking import open_dbus_connection
        with tempfile.TemporaryDirectory(prefix="k230-nd-") as directory:
            root = Path(directory)
            sock = root / "events.sock"
            trusted = root / "trusted.json"
            trusted.write_text(json.dumps({f"{sys.executable} {ROOT / 'tools/notification_dbus.py'}": DELEGATE}))
            procs = []
            try:
                bus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1", f"--address=unix:path={root}/bus"],
                                       stdout=subprocess.PIPE, text=True)
                procs.append(bus)
                address = bus.stdout.readline().strip()
                procs.append(subprocess.Popen([sys.executable, str(ROOT / "tools/notification_center.py"), "serve",
                                               "--socket", str(sock), "--trusted", str(trusted)]))
                procs.append(subprocess.Popen([sys.executable, str(ROOT / "tools/notification_dbus.py"),
                                               "--bus", address, "--socket", str(sock)]))
                for _ in range(100):
                    try:
                        broker.call(sock, {"operation": "history"})
                        break
                    except (OSError, ValueError):
                        time.sleep(.05)
                target = DBusAddress("/org/freedesktop/Notifications", "org.freedesktop.Notifications", "org.freedesktop.Notifications")
                deadline = time.monotonic() + 5
                client = None
                while time.monotonic() < deadline:
                    try:
                        client = open_dbus_connection(bus=address)
                        client.send_and_get_reply(new_method_call(target, "GetCapabilities"), timeout=1)
                        break
                    except Exception:
                        time.sleep(.05)
                else:
                    self.fail("adaptor did not own the name")
                notify = new_method_call(target, "Notify", "susssasa{sv}i",
                                         ("Timer Lab", 0, "", "Build finished", "body", [], {"urgency": ("y", 2)}, -1))
                identity = client.send_and_get_reply(notify, timeout=3).body[0]
                state = None
                for _ in range(100):
                    try:
                        state = broker.call(sock, {"operation": "history"})
                        if state["count"]:
                            break
                    except (OSError, ValueError):
                        pass
                    time.sleep(.05)
                row = state["events"][0]
                self.assertEqual((row["source"], row["priority"], row["summary"]), ("Timer Lab", "important", "Build finished"))
                self.assertEqual(state["preview"]["summary"], "New notification")
                client.send_and_get_reply(new_method_call(target, "CloseNotification", "u", (identity,)), timeout=3)
                self.assertEqual(broker.call(sock, {"operation": "history"})["count"], 0)
                # A bystander process is not the delegate: it stays unknown.
                result = subprocess.run([sys.executable, "-c",
                    "import sys; sys.path.insert(0, %r); import notification_center as n;"
                    "print(n.call(%r, {'operation':'emit','summary':'x','app':{'id':'a','name':'Shell'}}))" % (str(ROOT / "tools"), str(sock))],
                    capture_output=True, text=True)
                self.assertIn("accepted", result.stdout)
                self.assertEqual(broker.call(sock, {"operation": "history"})["events"][0]["source"], "Unknown source")
            finally:
                for process in reversed(procs):
                    process.terminate()
                    process.wait(timeout=3)
                    if process.stdout:
                        process.stdout.close()


@unittest.skipUnless(shutil.which("dbus-daemon") and importlib.util.find_spec("jeepney"), "needs dbus-daemon and jeepney")
class SignalIntegration(unittest.TestCase):
    """The app hears NotificationClosed (1, 2, 3) and ActionInvoked on a private bus."""

    def setUp(self):
        from jeepney import DBusAddress, MatchRule, message_bus, new_method_call
        from jeepney.io.blocking import open_dbus_connection
        self.new_method_call = new_method_call
        directory = tempfile.TemporaryDirectory(prefix="k230-nd-")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.sock = root / "events.sock"
        trusted = root / "trusted.json"
        trusted.write_text(json.dumps({f"{sys.executable} {ROOT / 'tools/notification_dbus.py'}": DELEGATE}))
        bus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1", f"--address=unix:path={root}/bus"],
                               stdout=subprocess.PIPE, text=True)
        self.addCleanup(self.stop, bus)
        address = bus.stdout.readline().strip()
        self.addCleanup(bus.stdout.close)
        center = subprocess.Popen([sys.executable, str(ROOT / "tools/notification_center.py"), "serve",
                                   "--socket", str(self.sock), "--trusted", str(trusted)])
        self.addCleanup(self.stop, center)
        for _ in range(100):
            try:
                broker.call(self.sock, {"operation": "history"})
                break
            except (OSError, ValueError):
                time.sleep(.05)
        self.addCleanup(self.stop, subprocess.Popen([sys.executable, str(ROOT / "tools/notification_dbus.py"),
                                                     "--bus", address, "--socket", str(self.sock)]))
        self.target = DBusAddress("/org/freedesktop/Notifications", "org.freedesktop.Notifications", "org.freedesktop.Notifications")
        deadline = time.monotonic() + 5
        while True:
            try:
                self.client = open_dbus_connection(bus=address)
                self.addCleanup(self.client.close)
                reply = self.client.send_and_get_reply(new_method_call(self.target, "GetCapabilities"), timeout=1)
                if reply.header.message_type.name == "method_return":
                    break
                self.client.close()
                raise OSError("name not owned yet")
            except Exception:
                if time.monotonic() > deadline:
                    self.fail("adaptor did not own the name")
                time.sleep(.05)
        self.client.send_and_get_reply(message_bus.AddMatch(MatchRule(type="signal", interface="org.freedesktop.Notifications")), timeout=3)
        # The adaptor subscribes to the broker on its own thread: wait until
        # an action is accepted, then discard the signals that probe made.
        for _ in range(100):
            self.notify(["k", "K"])
            row = self.newest()
            if broker.call(self.sock, {"operation": "invoke", "id": row["id"], "index": 0}).get("error") != "app-unavailable":
                break
            broker.call(self.sock, {"operation": "dismiss", "id": row["id"]})
            time.sleep(.05)
        try:
            while True:
                self.client.receive(timeout=.3)
        except TimeoutError:
            pass

    @staticmethod
    def stop(process):
        process.terminate()
        process.wait(timeout=3)

    def notify(self, actions):
        message = self.new_method_call(self.target, "Notify", "susssasa{sv}i", ("Calc", 0, "", "Done", "body", actions, {}, -1))
        return self.client.send_and_get_reply(message, timeout=3).body[0]

    def signal(self):
        while True:
            message = self.client.receive(timeout=3)
            if message.header.message_type.name == "signal":
                return message.header.fields[3], message.body

    def newest(self):
        return broker.call(self.sock, {"operation": "history"})["events"][0]

    def test_the_person_dismissing_is_reason_two(self):
        identity = self.notify([])
        self.assertEqual(broker.call(self.sock, {"operation": "dismiss", "id": self.newest()["id"]})["state"], "dismissed")
        self.assertEqual(self.signal(), ("NotificationClosed", (identity, 2)))

    def test_the_app_closing_it_is_reason_three_and_only_once(self):
        identity = self.notify([])
        self.client.send_and_get_reply(self.new_method_call(self.target, "CloseNotification", "u", (identity,)), timeout=3)
        self.assertEqual(self.signal(), ("NotificationClosed", (identity, 3)))
        self.assertEqual(broker.call(self.sock, {"operation": "history"})["count"], 0)

    def test_a_tapped_action_reaches_the_app_with_its_key(self):
        identity = self.notify(["default", "Body", "open", "Open", "snooze", "Snooze"])
        row = self.newest()
        self.assertEqual(row["actions"], ["Open", "Snooze"])
        self.assertEqual(broker.call(self.sock, {"operation": "invoke", "id": row["id"], "index": 1})["state"], "invoked")
        self.assertEqual(self.signal(), ("ActionInvoked", (identity, "snooze")))
        self.assertEqual(self.signal(), ("NotificationClosed", (identity, 2)))

    def test_the_server_advertises_actions(self):
        reply = self.client.send_and_get_reply(self.new_method_call(self.target, "GetCapabilities"), timeout=3)
        self.assertEqual(reply.body[0], ["body", "actions"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

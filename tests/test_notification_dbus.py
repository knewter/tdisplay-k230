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


if __name__ == "__main__":
    unittest.main(verbosity=2)

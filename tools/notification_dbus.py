#!/usr/bin/env python3
"""org.freedesktop.Notifications adaptor for the shell's notification broker.

Owns the well-known name on the session bus so `notify-send` and GTK/GLib
notifications reach the broker (tools/notification_center.py) instead of
nowhere. The process blocks in the bus read: no polling, no timers. One
thread holds a subscription to the broker, which pushes a notice when the
person dismisses an app's notification, when one expires, and when the person
taps an action the app offered; each becomes the matching signal.

The broker trusts this process (a delegate entry in its Nix-supplied map), not
the apps. Each app is forwarded as an unverified claim -- label, themed icon
name, id -- which the broker sanitises and namespaces. Privacy defaults are the
broker's: the adaptor never sends `private`, `ongoing` or `target`. Urgency
critical maps to important; the broker clamps delegated events to important
regardless.
"""
import argparse
import json
import os
import re
import socket
import sys
import threading
import time

NAME = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"
CAPABILITIES = ["body", "actions"]
MAX_ACTIONS = 2  # what the shade has room to draw; the broker clamps the same
KEY_LIMIT = 64
LABEL_LIMIT = 40
MAX_KNOWN = 256
REQUEST_LIMIT = 4096
TAGS = re.compile(r"</?(?:b|i|u|a|img)\b[^>]*>", re.IGNORECASE)
ICON = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
INTROSPECT = """<node><interface name="org.freedesktop.Notifications">
<method name="GetCapabilities"><arg direction="out" type="as"/></method>
<method name="Notify"><arg direction="in" type="s"/><arg direction="in" type="u"/><arg direction="in" type="s"/><arg direction="in" type="s"/><arg direction="in" type="s"/><arg direction="in" type="as"/><arg direction="in" type="a{sv}"/><arg direction="in" type="i"/><arg direction="out" type="u"/></method>
<method name="CloseNotification"><arg direction="in" type="u"/></method>
<method name="GetServerInformation"><arg direction="out" type="s"/><arg direction="out" type="s"/><arg direction="out" type="s"/><arg direction="out" type="s"/></method>
<signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal>
<signal name="ActionInvoked"><arg type="u"/><arg type="s"/></signal>
</interface></node>"""


def broker_call(path, request):
    payload = json.dumps(request, separators=(",", ":")).encode() + b"\n"
    if len(payload) > REQUEST_LIMIT:
        raise ValueError("request too large")
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(str(path))
        connection.sendall(payload)
        reply = b""
        while b"\n" not in reply:
            chunk = connection.recv(8192)
            if not chunk or len(reply) > 131072:
                raise ValueError("invalid broker response")
            reply += chunk
        return json.loads(reply)


def offered_actions(actions):
    """Notify's alternating key, label list as the broker's {key, label} rows.
    "default" is the body click, which the shade does not draw."""
    rows = []
    pairs = zip(actions[0::2], actions[1::2]) if isinstance(actions, (list, tuple)) else ()
    for key, label in pairs:
        if isinstance(key, str) and isinstance(label, str) and key and key != "default" and label.strip():
            rows.append({"key": key[:KEY_LIMIT], "label": label[:LABEL_LIMIT]})
    return rows[:MAX_ACTIONS]


def hint(hints, key):
    value = hints.get(key) if isinstance(hints, dict) else None
    # jeepney delivers a{sv} values as (signature, value).
    return value[1] if isinstance(value, (tuple, list)) and len(value) == 2 else value


class Adaptor:
    """Notify / CloseNotification -> broker emit / withdraw. Free of D-Bus."""

    def __init__(self, forward):
        self.forward = forward
        self.next_id = 0
        self.known = {}  # D-Bus id -> app id, bounded, oldest first
        self.lock = threading.Lock()  # the broker thread edits `known` too

    def allocate(self):
        self.next_id = self.next_id % 0xFFFFFFFF + 1
        return self.next_id

    def app_identity(self, app_name, icon, hints):
        entry = hint(hints, "desktop-entry")
        entry = entry if isinstance(entry, str) else ""
        entry = entry[:-8] if entry.endswith(".desktop") else entry
        app_id = entry or (app_name if isinstance(app_name, str) else "")
        app_id = re.sub(r"[^A-Za-z0-9._-]", "-", app_id)[:64].strip("-._") or "unknown"
        if isinstance(app_name, str) and app_name.strip():
            name = app_name
        else:
            name = entry.rsplit(".", 1)[-1] or "Application"
        icon = icon if isinstance(icon, str) and ICON.fullmatch(icon) else None
        if icon is None and ICON.fullmatch(entry):
            icon = entry
        return {"id": app_id, "name": name, "icon": icon}

    def notify(self, app_name, replaces_id, app_icon, summary, body, actions, hints, expire):
        app = self.app_identity(app_name, app_icon, hints)
        if replaces_id and self.known.get(replaces_id) == app["id"]:
            identity = replaces_id
        else:
            identity = self.allocate()
        request = {"operation": "emit", "app": app, "tag": f"dbus-{identity}",
                   "summary": TAGS.sub("", summary or ""), "body": TAGS.sub("", body or ""),
                   "priority": "important" if hint(hints, "urgency") == 2 else "ordinary"}
        offered = offered_actions(actions)
        if offered:
            request["actions"] = offered
        try:
            result = self.forward(request)
        except (OSError, ValueError):
            result = {"state": "unavailable"}
        # The app always gets an id; a down broker must not make it fail.
        with self.lock:
            self.known.pop(identity, None)
            self.known[identity] = app["id"]
            while len(self.known) > MAX_KNOWN:
                self.known.pop(next(iter(self.known)))
        return identity, result

    def broker_notice(self, notice):
        """A notice from the broker -> (signal name, signature, body) or None.
        Reasons are the specification's: 1 expired, 2 dismissed by the person."""
        tag = notice.get("tag") if isinstance(notice, dict) else None
        if not isinstance(tag, str) or not tag.startswith("dbus-") or not tag[5:].isdigit():
            return None
        identity = int(tag[5:])
        if notice.get("event") == "action":
            key = notice.get("key")
            with self.lock:
                known = identity in self.known
            return ("ActionInvoked", "us", (identity, key)) if known and isinstance(key, str) else None
        reason = notice.get("reason")
        if notice.get("event") != "closed" or reason not in (1, 2):
            return None
        with self.lock:
            if self.known.pop(identity, None) is None:
                return None  # already closed by the app, or not ours
        return ("NotificationClosed", "uu", (identity, reason))

    def close(self, identity):
        """Withdraw an id this adaptor issued; True when a close signal is due."""
        with self.lock:
            app_id = self.known.pop(identity, None)
        if app_id is None:
            return False
        try:
            self.forward({"operation": "withdraw", "app": {"id": app_id}, "tag": f"dbus-{identity}"})
        except (OSError, ValueError):
            pass
        return True


def listen_to_broker(path, adaptor, emit, retry=2.0, sleep=time.sleep):
    """Hold the broker subscription and hand each notice to `emit` as a signal.
    Reconnects after a broker restart; blocks in the read otherwise."""
    while True:
        try:
            with socket.socket(socket.AF_UNIX) as connection:
                connection.settimeout(3)
                connection.connect(str(path))
                connection.sendall(b'{"operation":"subscribe"}\n')
                connection.settimeout(None)
                for line in connection.makefile("rb"):
                    try:
                        notice = json.loads(line)
                    except ValueError:
                        continue
                    signal = adaptor.broker_notice(notice)
                    if signal is not None:
                        emit(*signal)
        except OSError:
            pass
        sleep(retry)


def handle(adaptor, message, api):
    """One method call -> (reply message, optional signal). `api` is jeepney's
    constructors, passed in so the logic is testable with plain stubs."""
    header = message.header
    member, interface = header.fields.get(3), header.fields.get(2)
    if interface == "org.freedesktop.DBus.Introspectable" and member == "Introspect":
        return api.method_return(message, "s", (INTROSPECT,)), None
    if interface == "org.freedesktop.DBus.Peer" and member == "Ping":
        return api.method_return(message), None
    if interface not in (NAME, None):
        return api.error(message, "org.freedesktop.DBus.Error.UnknownMethod"), None
    if member == "GetCapabilities":
        return api.method_return(message, "as", (CAPABILITIES,)), None
    if member == "GetServerInformation":
        return api.method_return(message, "ssss", ("k230-shell", "k230", "1", "1.2")), None
    if member == "Notify" and len(message.body) == 8:
        identity, _ = adaptor.notify(*message.body)
        return api.method_return(message, "u", (identity,)), None
    if member == "CloseNotification" and len(message.body) == 1:
        identity = message.body[0]
        signal = api.signal("NotificationClosed", "uu", (identity, 3)) if adaptor.close(identity) else None
        return api.method_return(message), signal
    return api.error(message, "org.freedesktop.DBus.Error.UnknownMethod"), None


def serve(bus, broker_path):
    from types import SimpleNamespace
    from jeepney import DBusAddress, new_error, new_method_return, new_signal
    from jeepney.bus_messages import message_bus
    from jeepney.io.blocking import open_dbus_connection
    connection = open_dbus_connection(bus=bus)
    reply = connection.send_and_get_reply(message_bus.RequestName(NAME, 4))  # DO_NOT_QUEUE
    if not reply.body or reply.body[0] != 1:
        print(f"{NAME} is already owned", file=sys.stderr)
        return 1
    emitter = DBusAddress(PATH, bus_name=NAME, interface=NAME)
    api = SimpleNamespace(method_return=new_method_return, error=new_error,
                          signal=lambda name, sig, body: new_signal(emitter, name, sig, body))
    adaptor = Adaptor(lambda request: broker_call(broker_path, request))
    sending = threading.Lock()  # the broker thread and this loop both send

    def emit(name, signature, body):
        with sending:
            connection.send(api.signal(name, signature, body))

    threading.Thread(target=listen_to_broker, args=(broker_path, adaptor, emit), daemon=True).start()
    while True:
        message = connection.receive()
        if message.header.message_type.name != "method_call":
            continue
        response, signal = handle(adaptor, message, api)
        with sending:
            connection.send(response)
            if signal is not None:
                connection.send(signal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bus", default=os.environ.get("DBUS_SESSION_BUS_ADDRESS", "SESSION"))
    parser.add_argument("--socket", default=os.environ.get("K230_NOTIFICATION_SOCKET", "/run/shell-notifications/events.sock"))
    args = parser.parse_args()
    return serve(args.bus, args.socket)


if __name__ == "__main__":
    sys.exit(main())

"""A probe app on the shell's session bus (pending-timers-survive-restarts-
and-apps-hear-dismissals task 3.2). It posts notifications through
org.freedesktop.Notifications and prints, with UTC timestamps, every
NotificationClosed and ActionInvoked signal the service sends.

    action_probe.py SECONDS SUMMARY[:KEY=LABEL,...] ...

Each SUMMARY becomes one notification. KEY=LABEL pairs become its actions.
A summary ending in `!close` is closed by the app itself after 5 s, which
should give reason 3. Run it with the adaptor's interpreter (it has jeepney)
and DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell-bus/bus.
"""
import sys
import time
from datetime import datetime, timezone

from jeepney import DBusAddress, MatchRule, new_method_call
from jeepney.io.blocking import open_dbus_connection

NOTIFY = DBusAddress("/org/freedesktop/Notifications", bus_name="org.freedesktop.Notifications",
                     interface="org.freedesktop.Notifications")


def stamp(*words):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z", *words, flush=True)


def main(argv):
    seconds, specs = float(argv[0]), argv[1:]
    conn = open_dbus_connection(bus="SESSION")
    for member in ("NotificationClosed", "ActionInvoked"):
        rule = MatchRule(type="signal", interface=NOTIFY.interface, member=member)
        conn.send_and_get_reply(new_method_call(
            DBusAddress("/org/freedesktop/DBus", bus_name="org.freedesktop.DBus",
                        interface="org.freedesktop.DBus"), "AddMatch", "s", (rule.serialise(),)))
    caps = conn.send_and_get_reply(new_method_call(NOTIFY, "GetCapabilities")).body[0]
    stamp("capabilities", ",".join(caps))
    to_close = []
    for spec in specs:
        summary, _, acts = spec.partition(":")
        close = summary.endswith("!close")
        summary = summary.removesuffix("!close")
        actions = []
        for pair in filter(None, acts.split(",")):
            key, _, label = pair.partition("=")
            actions += [key, label]
        reply = conn.send_and_get_reply(new_method_call(
            NOTIFY, "Notify", "susssasa{sv}i", ("Action probe", 0, "", summary, "probe body", actions, {}, -1)))
        nid = reply.body[0]
        stamp("posted", nid, repr(summary), "actions", actions)
        if close:
            to_close.append((time.monotonic() + 5, nid))
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for due, nid in list(to_close):
            if time.monotonic() >= due:
                conn.send_and_get_reply(new_method_call(NOTIFY, "CloseNotification", "u", (nid,)))
                stamp("app closed", nid)
                to_close.remove((due, nid))
        try:
            msg = conn.receive(timeout=1)
        except TimeoutError:
            continue
        member = msg.header.fields.get(3)
        if member in ("NotificationClosed", "ActionInvoked"):
            stamp("signal", member, *msg.body)


if __name__ == "__main__":
    main(sys.argv[1:])

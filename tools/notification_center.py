#!/usr/bin/env python3
"""Session notification history and non-focus-taking preview data.

One JSON request/response per Unix connection. The socket has no authority to
launch arbitrary commands. Trusted source metadata comes from peer credentials
and a Nix-supplied executable map, never an event's claimed source name.
"""
import argparse
from collections import OrderedDict
import fcntl
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import stat
import struct
import subprocess
import time

MAX_EVENTS = 64
MAX_REQUEST = 4096
MAX_RESPONSE = 128 * 1024
PRIORITIES = {"ordinary": 0, "important": 1, "critical": 2}


def text(value, limit):
    if not isinstance(value, str):
        return ""
    return "".join(char for char in value if char.isprintable())[:limit]


class History:
    def __init__(self, clock=time.monotonic, wall=time.time, action=None):
        self.clock, self.wall = clock, wall
        self.action = action or (lambda target, execute=False: False)
        self.events = OrderedDict()
        self.sequence = 0

    def prune(self):
        now = self.clock()
        for identity, event in list(self.events.items()):
            if not event["ongoing"] and now - event["received"] >= 3600:
                del self.events[identity]

    def emit(self, data, source):
        self.prune()
        trusted = source is not None
        priority = data.get("priority", "ordinary") if trusted else "ordinary"
        if priority not in PRIORITIES:
            return {"state": "failed", "error": "invalid-priority"}
        name = source["name"] if trusted else "Unknown source"
        key = source["id"] if trusted else "unknown"
        tag = text(data.get("tag"), 64)
        old = next((event for event in self.events.values()
                    if tag and event["source_id"] == key and event["tag"] == tag), None)
        if old:
            identity = old["id"]
        else:
            if len(self.events) >= MAX_EVENTS:
                disposable = next((identity for identity, event in self.events.items()
                                   if not event["ongoing"]), None)
                if disposable is None:
                    return {"state": "failed", "error": "history-full"}
                del self.events[disposable]
            self.sequence += 1
            identity = self.sequence
        target = data.get("target") if trusted else None
        if type(target) is not int or not 0 < target < 2**53:
            target = None
        event = {"id": identity, "source_id": key, "source": name,
                 "icon": source.get("icon") if trusted else None,
                 "summary": text(data.get("summary"), 160) or "New notification",
                 "body": text(data.get("body"), 512), "priority": priority,
                 "private": data.get("private", True) is not False or not trusted,
                 "ongoing": trusted and priority == "critical" and data.get("ongoing") is True,
                 "tag": tag, "target": target, "received": self.clock(),
                 "timestamp": int(self.wall()), "error": None}
        self.events[identity] = event
        self.events.move_to_end(identity)
        return {"state": "accepted", "id": identity}

    def public(self, event):
        result = {key: event[key] for key in
                  ("id", "source", "icon", "summary", "body", "priority", "timestamp", "error")}
        result["dismissible"] = not event["ongoing"]
        result["action_available"] = event["target"] is not None and self.action(event["target"])
        return result

    def snapshot(self):
        self.prune()
        rows = sorted(self.events.values(), key=lambda row: (PRIORITIES[row["priority"]], row["received"], row["id"]), reverse=True)
        previews = [row for row in rows if row["ongoing"] or self.clock() - row["received"] < 5]
        preview = None
        if previews:
            event = previews[0]
            preview = {"id": event["id"], "priority": event["priority"],
                       "source": "Notification" if event["private"] else event["source"],
                       "summary": "New notification" if event["private"] else event["summary"],
                       "icon": None if event["private"] else event["icon"],
                       "focus": False, "ongoing": event["ongoing"]}
        return {"schema": 1, "count": len(rows), "events": [self.public(row) for row in rows], "preview": preview}

    def request(self, data, source):
        if not isinstance(data, dict):
            return {"state": "failed", "error": "invalid-request"}
        operation = data.get("operation")
        if operation == "emit":
            return self.emit(data, source)
        if operation == "history":
            return self.snapshot()
        if operation == "dismiss-all":
            self.events = OrderedDict((key, row) for key, row in self.events.items() if row["ongoing"])
            return {"state": "dismissed", "remaining": len(self.events)}
        identity = data.get("id")
        if type(identity) is not int or identity not in self.events:
            return {"state": "failed", "error": "event-gone"}
        event = self.events[identity]
        if operation == "dismiss":
            if event["ongoing"]:
                return {"state": "failed", "error": "critical-retained"}
            del self.events[identity]
            return {"state": "dismissed"}
        if operation == "action":
            if event["target"] is None or not self.action(event["target"], execute=True):
                event["error"] = "Target unavailable"
                return {"state": "failed", "error": "target-unavailable", "retry": True}
            event["error"] = None
            return {"state": "requested"}
        return {"state": "failed", "error": "unknown-operation"}


class SwayActions:
    """Snapshot once per request, revalidate every action before focusing."""
    def __init__(self):
        self.ids = set()

    def refresh(self):
        self.ids = set()
        try:
            result = subprocess.run([os.environ.get("K230_SWAYMSG", "swaymsg"), "-r", "-t", "get_tree"],
                                    capture_output=True, timeout=1, check=True)
            if len(result.stdout) > 2 * 1024 * 1024:
                return
            pending = [json.loads(result.stdout)]
            count = 0
            while pending and count < 4096:
                row = pending.pop()
                count += 1
                if not isinstance(row, dict):
                    continue
                if row.get("type") == "con" and (row.get("app_id") or row.get("window")):
                    self.ids.add(row.get("id"))
                pending.extend(row.get("nodes", []))
                pending.extend(row.get("floating_nodes", []))
        except (OSError, ValueError, TypeError, subprocess.SubprocessError):
            self.ids = set()

    def __call__(self, target, execute=False):
        if execute:
            self.refresh()
        if target not in self.ids:
            return False
        if not execute:
            return True
        try:
            result = subprocess.run([os.environ.get("K230_SWAYMSG", "swaymsg"), "-r", f"[con_id={target}] focus"],
                                    capture_output=True, timeout=1, check=True)
            response = json.loads(result.stdout)
            return bool(response) and all(row.get("success") is True for row in response)
        except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
            return False


def peer_source(connection, trusted):
    pid, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid not in (0, os.getuid()):
        raise PermissionError("foreign peer")
    if uid == 0:
        return {"id": "system", "name": "System", "icon": None}
    try:
        executable = str(Path(f"/proc/{pid}/exe").resolve(strict=True))
    except OSError:
        return None
    return trusted.get(executable)


def serve(path, trusted):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("notification runtime must be private and owned by the session user")
    lock = os.fdopen(os.open(path.parent / "broker.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # The exclusive broker lock makes recovery of our stale socket safe even
    # after SIGKILL. An arbitrary existing file is never removed.
    if path.exists() or path.is_symlink():
        previous = path.lstat()
        if not stat.S_ISSOCK(previous.st_mode) or previous.st_uid != os.getuid():
            raise RuntimeError("foreign notification socket path")
        path.unlink()
    actions = SwayActions()
    history = History(action=actions)
    selector = selectors.DefaultSelector()
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(path))  # Never unlink another running broker's socket.
    path.chmod(0o600)
    listener.listen(8)
    listener.setblocking(False)
    selector.register(listener, selectors.EVENT_READ, None)
    clients = {}
    running = True

    def stop(signum, frame):
        nonlocal running
        running = False

    old_term = signal.signal(signal.SIGTERM, stop)

    def close(client):
        selector.unregister(client)
        clients.pop(client, None)
        client.close()

    try:
        while running:
            for key, _ in selector.select(0.1):
                if key.fileobj is listener:
                    client, _ = listener.accept()
                    if len(clients) >= 8:
                        client.close()
                        continue
                    client.setblocking(False)
                    clients[client] = {"data": b"", "deadline": time.monotonic() + 2, "response": None}
                    selector.register(client, selectors.EVENT_READ, clients[client])
                    continue
                client, state = key.fileobj, key.data
                try:
                    if state["response"] is not None:
                        written = client.send(state["response"])
                        state["response"] = state["response"][written:]
                        if not state["response"]:
                            close(client)
                        continue
                    chunk = client.recv(MAX_REQUEST + 1)
                    state["data"] += chunk
                    if len(state["data"]) > MAX_REQUEST or not chunk:
                        close(client)
                        continue
                    if b"\n" not in state["data"]:
                        continue
                    data = json.loads(state["data"].split(b"\n", 1)[0])
                    source = peer_source(client, trusted)
                    if (isinstance(data, dict) and data.get("operation") == "history"
                            and any(row["target"] for row in history.events.values())):
                        actions.refresh()
                    result = history.request(data, source)
                    state["response"] = json.dumps(result, separators=(",", ":")).encode() + b"\n"
                    selector.modify(client, selectors.EVENT_WRITE, state)
                except (OSError, ValueError, KeyError, TypeError):
                    close(client)
            for client, state in list(clients.items()):
                if time.monotonic() >= state["deadline"]:
                    close(client)
    finally:
        for client in list(clients):
            close(client)
        selector.close()
        listener.close()
        path.unlink(missing_ok=True)
        lock.close()
        signal.signal(signal.SIGTERM, old_term)


def call(path, request):
    payload = json.dumps(request).encode() + b"\n"
    if len(payload) > MAX_REQUEST:
        raise ValueError("notification request too large")
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(str(path))
        connection.sendall(payload)
        reply = b""
        while b"\n" not in reply:
            chunk = connection.recv(8192)
            if not chunk or len(reply) + len(chunk) > MAX_RESPONSE:
                raise ValueError("invalid notification response")
            reply += chunk
        return json.loads(reply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["serve", "history", "emit", "dismiss", "dismiss-all", "action"])
    parser.add_argument("id", nargs="?", type=int)
    parser.add_argument("--socket", type=Path, default=Path(os.environ.get("K230_NOTIFICATION_SOCKET", "/run/shell-notifications/events.sock")))
    parser.add_argument("--trusted", type=Path)
    parser.add_argument("--summary", default="New notification")
    parser.add_argument("--body", default="")
    parser.add_argument("--tag", default="")
    parser.add_argument("--priority", choices=PRIORITIES, default="ordinary")
    args = parser.parse_args()
    if args.operation == "serve":
        trusted = json.loads(args.trusted.read_text()) if args.trusted else {}
        serve(args.socket, trusted)
        return
    try:
        result = call(args.socket, {"operation": args.operation, "id": args.id,
                                   "summary": args.summary, "body": args.body,
                                   "tag": args.tag, "priority": args.priority})
    except (OSError, ValueError):
        result = {"state": "unavailable", "error": "notification-service-unavailable"}
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Headless QEMU pixels and real Wayland touch for the Rust service panels.

The settings command and notification broker are synthetic local fixtures.
In particular, no power command is ever passed to the device's real service.
"""

import argparse
from contextlib import closing, nullcontext
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import time

from PIL import Image, ImageChops


def wait_for(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("timed out waiting for headless service state")


class Broker:
    def __init__(self, path):
        self.path = path
        self.summary = "Private alpha"
        self.error = None
        self.operations = []
        self.lock = threading.Lock()
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(path))
        path.chmod(0o600)
        self.listener.listen(4)
        self.listener.settimeout(0.2)
        self.stop = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def history(self):
        with self.lock:
            summary, error = self.summary, self.error
        return {"schema": 1, "count": 1, "events": [{
            "id": 1, "source": "Terminal", "icon": None,
            "summary": summary, "body": "Private body",
            "priority": "important", "timestamp": 1700000000,
            "error": error, "dismissible": True, "action_available": True,
        }], "preview": {
            "id": 1, "source": "Notification", "icon": None,
            "summary": "New notification", "priority": "important",
            "focus": False, "ongoing": False,
        }}

    def run(self):
        while not self.stop:
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(2)
                line = bytearray()
                while len(line) < 4096 and not line.endswith(b"\n"):
                    chunk = connection.recv(4096 - len(line))
                    if not chunk:
                        break
                    line.extend(chunk)
                request = json.loads(line)
                operation = request["operation"]
                with self.lock:
                    self.operations.append(operation)
                    if operation == "action":
                        self.error = "target-unavailable"
                if operation == "history":
                    answer = self.history()
                elif operation == "action":
                    answer = {"state": "failed", "error": "target-unavailable", "retry": True}
                else:
                    answer = {"state": "failed", "error": "fixture-rejected"}
                connection.sendall(json.dumps(answer).encode() + b"\n")

    def count(self, operation):
        with self.lock:
            return self.operations.count(operation)

    def close(self):
        self.stop = True
        self.listener.close()
        self.thread.join(timeout=3)


SETTINGS_FIXTURE = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["K230_TEST_SETTINGS_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
token = "a" * 32
if args == ["status"]:
    answer = {"schema":1,"controls":{
      "network":{"state":"read-only","value":"link-up","label":"Network link available"},
      "brightness":{"state":"writable","value":45,"label":"Brightness","unit":"percent"},
      "keyboard":{"state":"action","value":None,"label":"Toggle keyboard","action":"keyboard-toggle"},
      "motion":{"state":"unavailable","value":None,"label":"Reduced motion"}}}
elif args[:1] == ["brightness"]:
    answer = {"state":"applied","requested":int(args[1]),"label":"Brightness changed"}
elif args == ["keyboard-toggle"]:
    answer = {"state":"requested","label":"Keyboard toggled"}
elif args[:1] == ["request"]:
    answer = {"state":"confirmation","token":token,"action":args[1],
              "expires_in_seconds":30,"label":"Confirm power action"}
elif args[:1] == ["cancel"]:
    answer = {"state":"cancelled","label":"Power action cancelled"}
elif args[:1] == ["confirm"]:
    answer = {"state":"failed","error":"fixture-power-blocked","retry":False}
else:
    answer = {"state":"failed","error":"fixture-rejected"}
print(json.dumps(answer))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sway", type=Path, required=True)
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--output", type=Path, help="keep synthetic screenshots and logs")
    args = parser.parse_args()
    if not args.sway.is_file() or not args.rust.is_file():
        parser.error("cross-built Sway and Rust executables must exist")

    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
    context = nullcontext(args.output) if args.output else tempfile.TemporaryDirectory(prefix="k230-service-qemu-")
    with context as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        config = root / "config"
        config.write_text("output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n")
        settings = root / "fake-settings"
        settings.write_text(SETTINGS_FIXTURE)
        settings.chmod(0o700)
        settings_log = root / "settings.jsonl"
        settings_log.touch()
        broker = Broker(root / "notifications.sock")
        env = dict(os.environ, XDG_RUNTIME_DIR=str(root), WLR_BACKENDS="headless",
                   WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
                   SWAY_K230_CARD_SHELL="1", SWAY_K230_CARD_TEST_INPUT="1",
                   K230_SETTINGS=str(settings),
                   K230_NOTIFICATION_SOCKET=str(broker.path),
                   K230_TEST_SETTINGS_LOG=str(settings_log))
        sway_log = (root / "sway.log").open("w")
        rust_log = (root / "rust.log").open("w")
        sway = subprocess.Popen([args.qemu, str(args.sway), "-c", str(config), "-d"],
                                env=env, stdout=sway_log, stderr=sway_log)
        rust = None
        try:
            wait_for(lambda: "Running compositor on wayland display" in (root / "sway.log").read_text(), 60)
            env["WAYLAND_DISPLAY"] = wait_for(lambda: next(
                (p.name for p in root.glob("wayland-*") if not p.name.endswith(".lock")), None))
            rust = subprocess.Popen([args.qemu, str(args.rust), "--serve"],
                                    env=env, stdout=rust_log, stderr=rust_log)
            wait_for(lambda: "ready-idle" in (root / "rust.log").read_text(), 30)

            def ipc(command):
                name = next(root.glob("sway-ipc.*.sock"))
                with closing(socket.socket(socket.AF_UNIX)) as stream:
                    stream.settimeout(10)
                    stream.connect(str(name))
                    payload = command.encode()
                    stream.sendall(b"i3-ipc" + struct.pack("=II", len(payload), 0) + payload)

                    def read(count):
                        data = b""
                        while len(data) < count:
                            chunk = stream.recv(count - len(data))
                            assert chunk, "Sway IPC closed"
                            data += chunk
                        return data

                    length, _ = struct.unpack("=II", read(14)[6:])
                    result = json.loads(read(length))
                    assert all(row["success"] for row in result), (command, result)

            def route(name):
                subprocess.run([args.qemu, str(args.rust), "--surface", name],
                               env=env, check=True, stdout=subprocess.DEVNULL)

            def capture(name):
                output = root / name
                subprocess.run(["grim", str(output)], env=env, check=True)
                with Image.open(output) as frame:
                    return frame.convert("RGB")

            def capture_until(name, predicate):
                def probe():
                    frame = capture(name)
                    return frame if predicate(frame) else None
                return wait_for(probe)

            def changed(first, second, box):
                return ImageChops.difference(first.crop(box), second.crop(box)).getbbox() is not None

            def commits():
                return sum(line.endswith(" commit") for line in (root / "rust.log").read_text().splitlines())

            contact = 1

            def tap(x, y):
                nonlocal contact
                ipc(f"card_shell test-touch down {contact} {x} {y}")
                ipc(f"card_shell test-touch up {contact}")
                contact += 1

            def swipe(x, start_y, end_y):
                nonlocal contact
                ipc(f"card_shell test-touch down {contact} {x} {start_y}")
                ipc(f"card_shell test-touch motion {contact} {x} {end_y}")
                ipc(f"card_shell test-touch up {contact}")
                contact += 1

            ipc("card_shell test-touch init")
            wallpaper = capture("wallpaper.png")
            route("shade")
            wait_for(lambda: broker.count("history") >= 1)
            wait_for(lambda: commits() >= 2)
            first = capture_until("shade-private-first.png", lambda frame:
                                  changed(wallpaper, frame, (24, 186, 544, 374)))
            with broker.lock:
                broker.summary = "Private beta"
            route("shade")
            wait_for(lambda: broker.count("history") >= 2)
            second = capture_until("shade-private-second.png", lambda frame:
                                   changed(first, frame, (24, 266, 544, 374)))
            assert ImageChops.difference(first.crop((24, 186, 544, 258)),
                                         second.crop((24, 186, 544, 258))).getbbox() is None, \
                "private history changed the already-redacted preview"
            assert ImageChops.difference(first.crop((24, 266, 544, 374)),
                                         second.crop((24, 266, 544, 374))).getbbox(), \
                "history did not show its new private summary"

            tap(284, 320)
            wait_for(lambda: broker.count("action") >= 1 and broker.count("history") >= 3)
            failure = capture_until("shade-action-error.png", lambda frame:
                                    changed(second, frame, (24, 350, 544, 395)))
            assert ImageChops.difference(second.crop((24, 350, 544, 395)),
                                         failure.crop((24, 350, 544, 395))).getbbox(), \
                "notification action error did not reach the visible row"

            before_unmap = (root / "rust.log").read_text().count(" unmap")
            swipe(284, 120, 20)  # Header/upward closure, outside history scrolling.
            wait_for(lambda: (root / "rust.log").read_text().count(" unmap") > before_unmap)
            closed = capture_until("shade-closed.png", lambda frame:
                                   not changed(wallpaper, frame, (24, 186, 544, 374)))
            route("shade")
            wait_for(lambda: broker.count("history") >= 4)
            capture_until("shade-reopened.png", lambda frame:
                          changed(closed, frame, (24, 186, 544, 374)))

            tap(510, 60)  # Shade Settings control; requires expanded input region.
            wait_for(lambda: len(settings_log.read_text().splitlines()) >= 1)
            settings_frame = capture_until("settings.png", lambda frame:
                                           changed(failure, frame, (24, 828, 544, 898)))
            assert ImageChops.difference(failure.crop((24, 828, 544, 898)),
                                         settings_frame.crop((24, 828, 544, 898))).getbbox(), \
                "Settings power controls are not visible below the former shade input region"
            tap(480, 365)
            wait_for(lambda: ["brightness", "55"] in [json.loads(line) for line in settings_log.read_text().splitlines()])
            tap(284, 500)
            wait_for(lambda: ["keyboard-toggle"] in [json.loads(line) for line in settings_log.read_text().splitlines()])
            tap(284, 780)
            wait_for(lambda: ["request", "reboot"] in [json.loads(line) for line in settings_log.read_text().splitlines()])
            confirm = capture_until("settings-confirm.png", lambda frame:
                                    changed(settings_frame, frame, (24, 940, 544, 1050)))
            assert ImageChops.difference(settings_frame.crop((24, 940, 544, 1050)),
                                         confirm.crop((24, 940, 544, 1050))).getbbox(), \
                "power confirmation not visible"
            tap(100, 985)
            wait_for(lambda: ["cancel", "a" * 32] in [json.loads(line) for line in settings_log.read_text().splitlines()])
            cancelled = capture_until("settings-cancelled.png", lambda frame:
                                      changed(confirm, frame, (24, 940, 544, 1050)))
            tap(284, 860)
            wait_for(lambda: ["request", "poweroff"] in [json.loads(line) for line in settings_log.read_text().splitlines()])
            capture_until("settings-poweroff-confirm.png", lambda frame:
                          changed(cancelled, frame, (24, 940, 544, 1050)))
            before_confirm_commits = commits()
            tap(440, 985)
            wait_for(lambda: ["confirm", "a" * 32] in [json.loads(line) for line in settings_log.read_text().splitlines()])
            wait_for(lambda: commits() > before_confirm_commits)
            working = capture("settings-power-working.png")
            wait_for(lambda: commits() > before_confirm_commits + 1)
            denied = capture("settings-fake-power-denied.png")
            assert changed(working, denied, (24, 1060, 544, 1120)), \
                "fake backend denial did not replace the pending message"
            assert rust.poll() is None and sway.poll() is None
            print(json.dumps({"evidence_class": "headless-qemu-injected-touch",
                              "passed": ["redacted-preview-vs-private-history",
                                         "notification-action-error-pixels",
                                         "header-swipe-closes-and-reopens-shade",
                                         "shade-to-settings-touch-region",
                                         "brightness-and-keyboard-controls",
                                         "fake-power-confirm-cancel-and-denial"],
                              "limits": ["synthetic settings and notifications",
                                         "no physical touch, panel, or power action"]}), flush=True)
        finally:
            if rust:
                rust.terminate()
                try:
                    rust.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    rust.kill()
                    rust.wait()
            sway.terminate()
            try:
                sway.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sway.kill()
                sway.wait()
            sway_log.close()
            rust_log.close()
            broker.close()


if __name__ == "__main__":
    main()

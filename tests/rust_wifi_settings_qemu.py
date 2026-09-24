#!/usr/bin/env python3
"""Paired Sway/Rust Wi-Fi Settings touch proof with a synthetic root broker.

Run under `unshare -Ur` so the fake socket is uid 0 inside the user namespace.
The production client's root-peer check stays enabled. No host or board radio
is opened, and the invented password is discarded without logging.
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


SETTINGS = '''#!/usr/bin/env python3
import json,os,sys
if sys.argv[1:] != ["status"]: raise SystemExit(2)
with open(os.environ["K230_TEST_SETTINGS_LOG"], "a") as log: log.write("status\\n")
print(json.dumps({"schema":1,"controls":{
  "network":{"state":"read-only","value":"link-up","label":"Wi-Fi available"},
  "brightness":{"state":"writable","value":45,"label":"Brightness","unit":"percent"},
  "keyboard":{"state":"action","value":None,"label":"Toggle keyboard","action":"keyboard-toggle"},
  "motion":{"state":"unavailable","value":None,"label":"Reduced motion"}}}))
'''

NAMES = ("Example Saved", "Example New", "Example Fail", "Example Guest")


def wait_for(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("timed out waiting for synthetic Wi-Fi UI state")


class Broker:
    def __init__(self, path):
        self.path = path
        self.listener = socket.socket(socket.AF_UNIX)
        self.listener.bind(str(path))
        path.chmod(0o600)
        self.listener.listen(8)
        self.listener.settimeout(0.2)
        self.lock = threading.Lock()
        self.operations = []  # operation names only; never a password or SSID
        self.saved = [NAMES[0]]
        self.current = None
        self.stop = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def count(self, name):
        with self.lock:
            return self.operations.count(name)

    def run(self):
        while not self.stop:
            try:
                connection, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(3)
                request = bytearray()
                try:
                    while not request.endswith(b"\n") and len(request) <= 4096:
                        chunk = connection.recv(4096 - len(request))
                        if not chunk:
                            break
                        request.extend(chunk)
                    value = json.loads(request)
                    operation = value["op"]
                    with self.lock:
                        self.operations.append(operation)
                    if operation == "scan":
                        time.sleep(0.45)  # expose loading before fake rows
                    with self.lock:
                        if operation == "connect-saved":
                            assert value["ssid"] == NAMES[0] and "password" not in value
                            self.current = NAMES[0]
                            answer = {"result": "selected", "ssid": NAMES[0]}
                        elif operation == "connect":
                            assert value["ssid"] in NAMES[1:3]
                            assert value["security"] == "wpa2-psk"
                            assert len(value["password"]) == 8  # invented touch keys
                            if value["ssid"] == NAMES[2]:
                                answer = {"state": "failed", "error": "authentication-failed"}
                            else:
                                self.current = NAMES[1]
                                if NAMES[1] not in self.saved:
                                    self.saved.append(NAMES[1])
                                answer = {"result": "saved", "ssid": NAMES[1]}
                        elif operation == "forget":
                            assert value["ssid"] == NAMES[0]
                            self.saved.remove(NAMES[0])
                            self.current = None
                            answer = {"result": "forgotten"}
                        elif operation in ("scan", "status"):
                            answer = {"current": self.current,
                                      "saved": [{"ssid": name, "security": "wpa2-psk"}
                                                for name in self.saved], "error": None}
                            if operation == "scan":
                                answer["networks"] = [
                                    {"ssid": name, "security": "open" if name == NAMES[3] else "wpa2-psk"}
                                    for name in NAMES]
                        else:
                            raise AssertionError("unexpected Wi-Fi operation")
                    answer = {"schema": 1, "state": "ok", **answer}
                    connection.sendall(json.dumps(answer).encode() + b"\n")
                except (OSError, ValueError, AssertionError):
                    # The synthetic fixture must fail visibly through operation
                    # counts; never print the request or its password.
                    pass
                finally:
                    request[:] = b"\0" * len(request)

    def close(self):
        self.stop = True
        self.listener.close()
        self.thread.join(timeout=3)


def theme(root, source, label):
    """Copy vetted code-native default tokens; a light synthetic swatch tests contrast."""
    appearance = json.loads((source / "default-appearance.json").read_text())
    report = json.loads((source / "default-report.json").read_text())
    generation = ("a" if label == "dark" else "b") * 24
    appearance["generation"] = report["generation"] = generation
    if label == "light":
        palette = report["palette"]
        palette.update({"background": "#eff1f5", "foreground": "#34384d",
                        "light_foreground": "#565a73", "accent": "#1e66f5",
                        "red": "#b11d41", "mode": "light"})
        for section_name, section in appearance["sections"].items():
            for key, token in section.items():
                if section_name == "controls" and key == "normal-fill-alpha":
                    token["value"] = 0.2
                if not isinstance(token, dict) or token.get("kind") != "brush":
                    continue
                if section_name == "controls" and key == "normal-color":
                    color = "#ff94b8ff"
                elif "text" in key or key in ("foreground", "active"):
                    color = "#ff34384d"
                elif "selected" in key:
                    color = "#ffd7e3fa"
                elif "border" in key:
                    color = "#ff9aa4b6"
                else:
                    color = "#ffeff1f5"
                for stop in token["stops"]:
                    stop["argb"] = color
    directory = root / f"theme-{label}" / generation
    directory.mkdir(parents=True)
    (directory / "appearance.json").write_text(json.dumps(appearance))
    (directory / "report.json").write_text(json.dumps(report))
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sway", type=Path, required=True)
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--theme-source", type=Path, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("run inside `unshare -Ur` for a synthetic uid-0 broker")
    if not args.sway.is_file() or not args.rust.is_file():
        parser.error("exact cross-built Sway and Rust executables must exist")
    context = nullcontext(args.output) if args.output else tempfile.TemporaryDirectory(prefix="k230-wifi-qemu-")
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
    with context as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        (root / "sway.conf").write_text("output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n")
        command = root / "fake-settings"
        command.write_text(SETTINGS)
        command.chmod(0o700)
        settings_log = root / "settings.log"
        settings_log.touch()
        broker = Broker(root / "wifi.sock")
        dark = theme(root, args.theme_source, "dark")
        light = theme(root, args.theme_source, "light")
        env = dict(os.environ, XDG_RUNTIME_DIR=str(root), WLR_BACKENDS="headless",
                   WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
                   SWAY_K230_CARD_SHELL="1", SWAY_K230_CARD_TEST_INPUT="1",
                   K230_SETTINGS=str(command), K230_WIFI_SOCKET=str(broker.path),
                   K230_TEST_SETTINGS_LOG=str(settings_log),
                   K230_KEYBOARD_TOUCH_GESTURES="1",  # synthetic capability render only
                   K230_THEME_STATE_ROOT=str(root / "theme-state"))
        sway_log = (root / "sway.log").open("w")
        sway = subprocess.Popen([args.qemu, str(args.sway), "-c", str(root / "sway.conf"), "-d"],
                                env=env, stdout=sway_log, stderr=sway_log)
        rust = None
        rust_log = None
        try:
            wait_for(lambda: "Running compositor on wayland display" in (root / "sway.log").read_text(), 60)
            env["WAYLAND_DISPLAY"] = wait_for(lambda: next(
                (p.name for p in root.glob("wayland-*") if not p.name.endswith(".lock")), None))

            def ipc(command_text):
                name = next(root.glob("sway-ipc.*.sock"))
                with closing(socket.socket(socket.AF_UNIX)) as stream:
                    stream.settimeout(10)
                    stream.connect(str(name))
                    payload = command_text.encode()
                    stream.sendall(b"i3-ipc" + struct.pack("=II", len(payload), 0) + payload)
                    def read(count):
                        data = b""
                        while len(data) < count:
                            chunk = stream.recv(count-len(data))
                            assert chunk
                            data += chunk
                        return data
                    length, _ = struct.unpack("=II", read(14)[6:])
                    assert all(item["success"] for item in json.loads(read(length)))

            def tap(x, y):
                nonlocal contact
                ipc(f"card_shell test-touch down {contact} {x} {y}")
                ipc(f"card_shell test-touch up {contact}")
                contact += 1

            def route(surface):
                subprocess.run([args.qemu, str(args.rust), "--surface", surface], env=env,
                               check=True, stdout=subprocess.DEVNULL)

            def capture(name):
                path = root / name
                subprocess.run(["grim", str(path)], env=env, check=True)
                with Image.open(path) as frame:
                    return frame.convert("RGB")

            def capture_until(name, predicate):
                return wait_for(lambda: (frame if predicate(frame) else None)
                                if (frame := capture(name)) else None)

            def capture_words(name, *required, absent=()):
                def probe():
                    frame = capture(name)
                    result = subprocess.run(["tesseract", str(root / name), "stdout"],
                                            check=True, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL)
                    words = " ".join(result.stdout.decode("utf-8", "replace").lower().split())
                    return frame if all(needle.lower() in words for needle in required) \
                        and not any(needle.lower() in words for needle in absent) else None
                return wait_for(probe)

            def changed(first, second, box):
                return ImageChops.difference(first.crop(box), second.crop(box)).getbbox() is not None

            def launch(default):
                nonlocal rust, rust_log
                env["K230_THEME_DEFAULT_GENERATION"] = str(default)
                rust_log = (root / "rust.log").open("a")
                rust = subprocess.Popen([args.qemu, str(args.rust), "--serve"], env=env,
                                        stdout=rust_log, stderr=rust_log)
                wait_for(lambda: "ready-idle" in (root / "rust.log").read_text() and rust.poll() is None, 30)

            contact = 1
            ipc("card_shell test-touch init")
            launch(dark)
            wallpaper = capture("wifi-wallpaper.png")
            route("settings")
            wait_for(lambda: "status" in settings_log.read_text())
            settings = capture_until("wifi-settings-dark.png", lambda frame:
                                     changed(wallpaper, frame, (24, 30, 280, 100))
                                     and frame.getpixel((45, 500)) != frame.getpixel((20, 500)))
            wait_for(lambda: "frame-done" in (root / "rust.log").read_text())
            time.sleep(0.2)  # let the committed input region reach Sway
            commits_before = (root / "rust.log").read_text().count(" commit")
            tap(284, 210)
            if not broker.count("scan"):
                time.sleep(0.35)
                if not broker.count("scan"):
                    tap(284, 210)
            wait_for(lambda: broker.count("scan") >= 1)
            loading = capture_until("wifi-loading-dark.png", lambda frame:
                                    changed(settings, frame, (24, 104, 544, 150)))
            scanned = capture_words("wifi-list-dark.png", "Saved and nearby", "Example Saved", "Example New")
            private_log_at = len((root / "rust.log").read_text())
            tap(284, 376)  # Saved row; no password should be transmitted.
            saved_entry = capture_words("wifi-saved-entry.png", "saved credential", "Stored securely")
            commits_before = (root / "rust.log").read_text().count(" commit")
            tap(420, 1160)
            wait_for(lambda: broker.count("connect-saved") == 1 and broker.count("status") >= 1)
            wait_for(lambda: (root / "rust.log").read_text().count(" commit") >= commits_before + 2)
            tap(284, 464)  # New WPA2 row.
            entry = capture_words("wifi-keyboard-dark.png", "Example New", "Tap keys to enter password")
            for index in range(8):
                tap(int(18 + (index + 0.5) * 53.2), 560)
            masked = capture_words("wifi-masked-dark.png", "Example New", "Cancel", "Connect",
                                   absent=("Tap keys to enter password",))
            commits_before = (root / "rust.log").read_text().count(" commit")
            tap(420, 1160)
            wait_for(lambda: broker.count("connect") == 1 and broker.count("status") >= 2)
            wait_for(lambda: (root / "rust.log").read_text().count(" commit") >= commits_before + 2)
            tap(284, 552)  # Synthetic authentication failure row.
            for index in range(8):
                tap(int(18 + (index + 0.5) * 53.2), 560)
            tap(420, 1160)
            wait_for(lambda: broker.count("connect") == 2)
            failure = capture_words("wifi-auth-error-dark.png", "Password was not accepted")
            tap(100, 1160)  # Cancel editor.
            tap(284, 376)   # Saved profile.
            tap(420, 440)   # Explicit Forget menu.
            confirm = capture_words("wifi-forget-confirm-dark.png", "Forget saved network?", "Keep")
            tap(100, 900)   # Keep, then confirm explicitly.
            assert broker.count("forget") == 0
            tap(420, 440)
            tap(420, 900)
            wait_for(lambda: broker.count("forget") == 1)
            capture_words("wifi-forgotten-dark.png", "Saved and nearby", "Example New")
            private_log = (root / "rust.log").read_text()[private_log_at:]
            assert "touch-down " not in private_log and "touch-move " not in private_log, \
                "Wi-Fi touch coordinates escaped into the shell log"

            rust.terminate(); rust.wait(timeout=5); rust_log.close(); rust = None
            (root / "rust.log").write_text("")
            settings_before = settings_log.read_text().count("status")
            launch(light)
            before_light = capture("wifi-before-light-settings.png")
            route("settings")
            wait_for(lambda: settings_log.read_text().count("status") > settings_before)
            light_settings = capture_until("wifi-settings-light.png", lambda frame:
                changed(before_light, frame, (24, 30, 280, 100))
                and frame.getpixel((45, 500)) != frame.getpixel((20, 500)))
            tap(284, 210)
            wait_for(lambda: broker.count("scan") >= 2)
            time.sleep(0.75)
            light_list = capture_words("wifi-list-light.png", "Saved and nearby", "Example New")
            assert changed(scanned, light_list, (24, 150, 544, 500)), "light tokens did not change Wi-Fi scene"
            rust.terminate(); rust.wait(timeout=5); rust_log.close(); rust = None
            (root / "rust.log").write_text("")
            env["K230_KEYBOARD_TOUCH_GESTURES"] = "0"
            launch(dark)
            before_disabled = capture("wifi-before-disabled-settings.png")
            route("settings")
            disabled = capture_until("wifi-keyboard-gesture-disabled-dark.png", lambda frame:
                changed(before_disabled, frame, (24, 30, 280, 100))
                and frame.getpixel((45, 500)) != frame.getpixel((20, 500)))
            assert changed(settings, disabled, (24, 515, 544, 562)), \
                "capability-off Settings still showed the gesture hint"
            assert rust.poll() is None and sway.poll() is None
            print(json.dumps({"evidence_class":"headless-qemu-injected-touch",
                              "passed":["scan/list", "saved-selection-no-password", "masked-keyboard",
                                        "synthetic-auth-error", "forget-keep-confirm", "dark-light-scenes",
                                        "private-touch-log", "keyboard-hint-capability-gate"],
                              "limits":["invented Wi-Fi broker and settings", "no physical radio/panel"]}), flush=True)
        finally:
            if rust:
                rust.terminate()
                try: rust.wait(timeout=5)
                except subprocess.TimeoutExpired: rust.kill(); rust.wait()
            sway.terminate()
            try: sway.wait(timeout=5)
            except subprocess.TimeoutExpired: sway.kill(); sway.wait()
            if rust_log:
                rust_log.close()
            sway_log.close()
            broker.close()


if __name__ == "__main__":
    main()

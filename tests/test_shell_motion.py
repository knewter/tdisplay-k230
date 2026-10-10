#!/usr/bin/env python3
"""Named coherent-shell integration cases against actual Sway/Wayland pixels.

The compositor runs under QEMU user emulation with native protocol clients and
injected wlroots touch. This is not a board, real-finger or latency proof.
Only implemented cases are accepted; missing cases never silently pass.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageChops
from card_shell_test_support import ROOT, binaries
from card_virtual_keyboard import Keyboard


CASES = ("live-gate", "private-no-icon", "close-refused")
CLASS = "headless-qemu-user-native-wayland-injected-touch"


def wait_for(predicate, label, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(.05)
    raise AssertionError(f"timeout: {label}")


class Scene:
    def __init__(self, root, sway, client, qemu):
        self.root, self.sway, self.client, self.qemu = root, sway, client, qemu
        self.processes, self.handles, self.apps = [], [], {}
        self.keyboard = None
        root.mkdir(mode=0o700)
        data = root / "data"
        apps = data / "applications"
        apps.mkdir(parents=True)
        # Distinct, otherwise unused colors make identifying-icon leakage a
        # pixel assertion. Both fixtures have different public names and icons.
        for app, color in (("one", (255, 255, 0)), ("two", (0, 255, 255))):
            icon = data / f"{app}.png"
            Image.new("RGB", (48, 48), color).save(icon)
            (apps / f"k230.card.{app}.desktop").write_text(
                "[Desktop Entry]\nType=Application\n"
                f"Name=Public identity {app}\nExec=/bin/true\nIcon={icon}\n")
        config = root / "sway.conf"
        config.write_text(
            "output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n"
            "focus_follows_mouse no\n"
            'for_window [app_id="^k230.card."] floating enable, border none, '
            "resize set 520 1040, move position 24 48\n")
        self.env = dict(os.environ, XDG_RUNTIME_DIR=str(root),
                        XDG_DATA_HOME=str(data), XDG_DATA_DIRS=str(data),
                        WLR_BACKENDS="headless", WLR_HEADLESS_OUTPUTS="1",
                        WLR_RENDERER="pixman", SWAY_K230_CARD_SHELL="1",
                        SWAY_K230_CARD_TOUCH_FIRST="1",
                        SWAY_K230_CARD_TEST_INPUT="1",
                        SWAY_K230_CARD_THEME_ROOT=str(root / "theme-state"))
        self.env.pop("SWAY_K230_CARD_THEME_DEFAULT", None)
        self.spawn("sway", [qemu, sway, "-c", str(config), "-d"])

    def spawn(self, name, argv):
        handle = (self.root / f"{name}.log").open("w")
        self.handles.append(handle)
        process = subprocess.Popen(argv, env=self.env, stdout=handle, stderr=handle)
        self.processes.append(process)
        return process

    def start(self):
        wait_for(lambda: list(self.root.glob("sway-ipc.*.sock")), "compositor IPC", 90)
        self.env["WAYLAND_DISPLAY"] = wait_for(
            lambda: next((p.name for p in self.root.glob("wayland-*")
                          if not p.name.endswith(".lock")), None), "Wayland socket")
        self.command("test-touch init")

    def ipc(self, command, kind=0):
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(10)
            peer.connect(str(next(self.root.glob("sway-ipc.*.sock"))))
            payload = command.encode()
            peer.sendall(b"i3-ipc" + struct.pack("=II", len(payload), kind) + payload)
            def read(count):
                data = bytearray()
                while len(data) < count:
                    chunk = peer.recv(count - len(data))
                    assert chunk, "IPC closed before complete reply"
                    data.extend(chunk)
                return data
            header = read(14)
            assert header[:6] == b"i3-ipc", "invalid IPC reply"
            length, _ = struct.unpack("=II", header[6:])
            assert length <= 8 * 1024 * 1024, "oversized IPC reply"
            result = json.loads(read(length))
            if kind == 0:
                assert all(row["success"] for row in result), (command, result)
            return result

    def command(self, command):
        return self.ipc("card_shell " + command)

    @staticmethod
    def nodes(tree):
        yield tree
        for node in tree.get("nodes", []) + tree.get("floating_nodes", []):
            yield from Scene.nodes(node)

    def mapped(self, app):
        return any(n.get("app_id") == app for n in self.nodes(self.ipc("", 4)))

    def focused(self):
        return next((n.get("app_id") for n in self.nodes(self.ipc("", 4))
                     if n.get("focused")), None)

    def client_start(self, app, refuse=False):
        prefix = [self.qemu] if Path(self.client).read_bytes()[18:20] == b"\xf3\x00" else []
        proc = self.spawn(app, prefix + [self.client, "--app-id", app]
                          + (["--refuse-close"] if refuse else []))
        self.apps[app] = proc
        wait_for(lambda: self.mapped(app), f"map {app}")
        return proc

    def record(self, app):
        lines = (self.root / f"{app}.log").read_text().splitlines()
        # A client can be writing the final row while the host reads it.
        rows = []
        for line in lines:
            if line.startswith("{"):
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-1] if rows else {}

    def capture(self, name):
        path = self.root / f"{name}.png"
        subprocess.run(["grim", str(path)], env=self.env, check=True, timeout=15)
        return Image.open(path).convert("RGB")

    def capture_when(self, name, predicate):
        def ready():
            image = self.capture(name)
            return image if predicate(image) else None
        return wait_for(ready, name)

    @staticmethod
    def color_count(image, color):
        return sum(count for count, value in image.getcolors(image.width * image.height)
                   if value == color)

    @staticmethod
    def neutral_placeholder(image):
        body = image.crop((150, 350, 410, 750))
        colors = body.getcolors(body.width * body.height)
        return (len(colors) == 1 and min(colors[0][1]) >= 8
                and colors[0][1] != image.getpixel((10, 700)))

    def close(self):
        if self.keyboard:
            self.keyboard.close()
        for proc in reversed(self.processes):
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        for handle in self.handles:
            handle.close()


def live_gate(scene):
    for app in ("k230.card.one", "k230.card.two"):
        scene.client_start(app)
    scene.ipc('[app_id="k230.card.one"] focus')
    scene.command("enter")
    before = scene.capture("live-start")
    scene.command("test-touch down 1 284 500")
    scene.command("test-touch motion 1 114 500")
    start = {app: scene.record(app) for app in scene.apps}
    fields = ("frames", "callbacks", "child_frames", "child_callbacks")
    assert all(all(field in row for field in fields) for row in start.values()), start
    wait_for(lambda: all(all(scene.record(app).get(field, 0) > row[field]
                            for field in fields) for app, row in start.items()),
             "both live roots and desynchronized subsurfaces advance during held drag")
    held = scene.capture_when("live-held", lambda im: ImageChops.difference(before, im).getbbox())
    assert Scene.color_count(held, (32, 112, 176)) > 100, "first app pixels absent"
    assert Scene.color_count(held, (144, 48, 128)) > 100, "neighbor app pixels absent"
    after = {app: {field: scene.record(app)[field] for field in fields} for app in scene.apps}
    scene.command("test-touch cancel")
    scene.command("back")
    scene.ipc('[app_id="k230.card.one"] focus')
    scene.command("enter")
    scene.ipc('[app_id="k230.card.one"] mark --add k230_card_unavailable')
    scene.capture_when("unavailable", lambda im:
                       Scene.color_count(im, (32, 112, 176)) == 0
                       and Scene.neutral_placeholder(im))
    assert scene.apps["k230.card.one"].poll() is None, "unavailable source was removed"
    scene.ipc('[app_id="k230.card.one"] unmark k230_card_unavailable')
    scene.capture_when("available-again", lambda im:
                       Scene.color_count(im, (32, 112, 176)) > 100)
    return {"before": {app: {field: row[field] for field in fields} for app, row in start.items()},
            "after": after, "live_pixels_visible": True,
            "unavailable_placeholder": True, "live_source_restored": True}


def private_no_icon(scene):
    private_frames = []
    public_counts = []
    for app, icon_color, content_color in (
            ("k230.card.one", (255, 255, 0), (32, 112, 176)),
            ("k230.card.two", (0, 255, 255), (144, 48, 128))):
        proc = scene.client_start(app)
        scene.command("enter")
        public = scene.capture_when(app + "-public", lambda im:
                                    Scene.color_count(im, icon_color) > 100
                                    and Scene.color_count(im, content_color) > 100)
        public_counts.append(Scene.color_count(public, icon_color))
        scene.ipc(f'[app_id="{app}"] mark --add k230_card_private')
        private = scene.capture_when(app + "-private", lambda im:
                                     Scene.color_count(im, icon_color) == 0
                                     and Scene.color_count(im, content_color) == 0
                                     and Scene.neutral_placeholder(im))
        private_frames.append(private)
        proc.terminate()
        proc.wait(timeout=10)
        wait_for(lambda: not scene.mapped(app), "private source unmaps")
    # Changing app/name/icon/content identity leaves exactly the same neutral
    # composed card. This also checks the identifying label, without OCR or a
    # source-string assertion. Each captured scene contains one private card.
    assert ImageChops.difference(*private_frames).getbbox() is None, \
        "private card pixels reveal differing application identity"
    return {"public_icon_pixels": public_counts, "private_icon_pixels": [0, 0],
            "private_content_pixels": [0, 0], "neutral_scenes_equal": True}


def close_refused(scene):
    app = "k230.card.one"
    proc = scene.client_start(app, refuse=True)
    scene.command("enter")
    scene.capture_when("before-close", lambda im: Scene.color_count(im, (32, 112, 176)) > 100)
    logs = lambda: (scene.root / "sway.log").read_text()
    requests = logs().count("K230_CARD_SHELL close-request")
    timeouts = logs().count("message=6")
    # Event timestamps determine the intentional throw, independently of
    # dispatch delay on a busy shared host. The real wlroots touch path runs.
    stamp = int(time.monotonic() * 1000) & 0xffffffff
    scene.command(f"test-touch down 7 284 600 {stamp}")
    scene.command(f"test-touch motion 7 284 450 {(stamp + 30) & 0xffffffff}")
    scene.command(f"test-touch motion 7 284 280 {(stamp + 60) & 0xffffffff}")
    scene.command(f"test-touch up 7 {(stamp + 70) & 0xffffffff}")
    wait_for(lambda: logs().count("K230_CARD_SHELL close-request") == requests + 1,
             "one graceful close request")
    wait_for(lambda: logs().count("message=6") > timeouts, "refused close reports timeout")
    assert proc.poll() is None and scene.mapped(app), "refusing app was removed"
    scene.capture_when("close-recovered", lambda im: Scene.color_count(im, (32, 112, 176)) > 100)
    scene.command("back")
    wait_for(lambda: scene.focused() == app, "focus recovers after close refusal")
    scene.keyboard = Keyboard(Path(scene.env["XDG_RUNTIME_DIR"]) / scene.env["WAYLAND_DISPLAY"])
    keys = scene.record(app).get("key_presses", 0)
    scene.keyboard.press()
    wait_for(lambda: scene.record(app).get("key_presses", 0) > keys,
             "keyboard reaches retained application")
    # The same scene also verifies an accepting client's actual XDG close,
    # unmap and focus return, rather than treating every close as a timeout.
    accepting = scene.client_start("k230.card.two")
    scene.command("enter")
    scene.capture_when("accepting-client", lambda im:
                       Scene.color_count(im, (144, 48, 128)) > 100)
    requests = logs().count("K230_CARD_SHELL close-request")
    stamp = int(time.monotonic() * 1000) & 0xffffffff
    scene.command(f"test-touch down 8 284 600 {stamp}")
    scene.command(f"test-touch motion 8 284 450 {(stamp + 30) & 0xffffffff}")
    scene.command(f"test-touch motion 8 284 280 {(stamp + 60) & 0xffffffff}")
    scene.command(f"test-touch up 8 {(stamp + 70) & 0xffffffff}")
    wait_for(lambda: logs().count("K230_CARD_SHELL close-request") == requests + 1,
             "one accepting close request")
    wait_for(lambda: accepting.poll() == 0 and not scene.mapped("k230.card.two"),
             "accepting app exits and unmaps gracefully")
    assert proc.poll() is None, "closing another app removed the refusing app"
    scene.command("back")
    wait_for(lambda: scene.focused() == app, "surviving app regains focus")
    return {"close_requests": 1, "timeout_reported": True, "app_retained": True,
            "focus_restored": True, "keyboard_delivered": True,
            "accepting_close_requests": 1, "accepting_app_exited": True,
            "survivor_focus_restored": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=CASES, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    args = parser.parse_args()
    sway, client = binaries()
    for path in (sway, client, args.qemu):
        assert Path(path).is_file(), f"required executable missing: {path}"
    temp = tempfile.TemporaryDirectory(prefix="shell-motion-") if args.output is None else None
    output = Path(temp.name) if temp else args.output
    if output.exists() and any(output.iterdir()):
        parser.error("--output must be new or empty")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.chmod(0o700)
    result = {"evidence_class": CLASS, "sway": sway, "client": client,
              "sway_sha256": hashlib.sha256(Path(sway).read_bytes()).hexdigest(),
              "client_sha256": hashlib.sha256(Path(client).read_bytes()).hexdigest(),
              "started_utc": datetime.now(timezone.utc).isoformat(), "cases": {}}
    try:
        for case in dict.fromkeys(args.case):
            scene = Scene(output / case, sway, client, args.qemu)
            try:
                scene.start()
                proof = {"live-gate": live_gate, "private-no-icon": private_no_icon,
                         "close-refused": close_refused}[case](scene)
                result["cases"][case] = {"result": "PASS", **proof}
                print(f"PASS {case}: {CLASS}", flush=True)
            finally:
                scene.close()
        result["result"] = "PASS"
    except Exception as error:
        result["result"] = "FAIL"
        result["failed_case"] = case
        result["failure_type"] = type(error).__name__
        raise
    finally:
        result["finished_utc"] = datetime.now(timezone.utc).isoformat()
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        if temp:
            temp.cleanup()


if __name__ == "__main__":
    main()

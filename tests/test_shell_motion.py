#!/usr/bin/env python3
"""Named coherent-shell integration cases against actual Sway/Wayland pixels.

The compositor runs under QEMU user emulation with native protocol clients and
injected wlroots touch. This is not a board, real-finger or latency proof.
Only implemented cases are accepted; missing cases never silently pass.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import socket
import struct
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageChops
from card_shell_test_support import ROOT, binaries
from card_virtual_keyboard import Keyboard
from rust_service_surface_qemu import SETTINGS_FIXTURE


SCENE_CASES = ("shrink-live", "drawer-rise", "shade-descend", "expand-live", "focus")
INTERRUPTION_CASES = ("reverse", "retarget", "unmap", "refusal", "private-no-flash")
CASES = ("live-gate", "private-no-icon", "close-refused") + SCENE_CASES + INTERRUPTION_CASES
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
    def __init__(self, root, sway, client, qemu, rust=None):
        self.root, self.sway, self.client, self.qemu = root, sway, client, qemu
        self.rust = rust
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
                        XDG_CONFIG_HOME=str(root / "config-home"),
                        XDG_CACHE_HOME=str(root.parent / "cache"),
                        WLR_BACKENDS="headless", WLR_HEADLESS_OUTPUTS="1",
                        WLR_RENDERER="pixman", SWAY_K230_CARD_SHELL="1",
                        SWAY_K230_CARD_TOUCH_FIRST="1",
                        SWAY_K230_CARD_TEST_INPUT="1",
                        SWAY_K230_CARD_THEME_ROOT=str(root / "theme-state"))
        self.env.pop("SWAY_K230_CARD_THEME_DEFAULT", None)
        if rust:
            settings = root / "fixture-settings"
            settings.write_text(SETTINGS_FIXTURE)
            settings.chmod(0o700)
            (root / "settings.jsonl").touch()
            swaymsg = Path(sway).with_name("swaymsg")
            assert swaymsg.is_file(), "selected Sway package lacks swaymsg"
            bridge = root / "fixture-swaymsg"
            bridge.write_text("#!/bin/sh\nexec " + shlex.join([qemu, str(swaymsg)]) + ' "$@"\n')
            bridge.chmod(0o700)
            self.env.update(SWAY_K230_CARD_REVEAL_STREAM="1",
                            SWAY_K230_CARD_SURFACE_SOCKET=str(root / "k230-shell-rust.sock"),
                            K230_SETTINGS=str(settings),
                            K230_TEST_SETTINGS_LOG=str(root / "settings.jsonl"),
                            K230_NOTIFICATION_SOCKET=str(root / "absent-notifications.sock"),
                            K230_SWAYMSG=str(bridge), K230_WPCTL="/bin/false",
                            K230_PW_DUMP="/bin/false", K230_PW_CLI="/bin/false")
        self.spawn("sway", [qemu, sway, "-c", str(config), "-d"])

    def spawn(self, name, argv):
        handle = (self.root / f"{name}.log").open("w")
        self.handles.append(handle)
        process = subprocess.Popen(argv, env=self.env, stdout=handle, stderr=handle)
        self.processes.append(process)
        return process

    def start(self):
        wait_for(lambda: "Running compositor on wayland display" in
                 (self.root / "sway.log").read_text(), "compositor dispatch ready", 90)
        wait_for(lambda: list(self.root.glob("sway-ipc.*.sock")), "compositor IPC", 90)
        self.env["WAYLAND_DISPLAY"] = wait_for(
            lambda: next((p.name for p in self.root.glob("wayland-*")
                          if not p.name.endswith(".lock")), None), "Wayland socket")
        self.command("test-touch init")
        self.env["SWAYSOCK"] = str(next(self.root.glob("sway-ipc.*.sock")))
        if self.rust:
            self.spawn("rust", [self.qemu, self.rust, "--serve"])
            wait_for(lambda: "ready-idle" in self.rust_log(), "Rust shell ready", 60)

    def rust_log(self):
        return (self.root / "rust.log").read_text()

    def state(self):
        text = self.command("debug-scene")[0]["error"]
        return dict(re.findall(r"\b(\w+)=([^ ]+)", text))

    def route(self, route):
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(5)
            peer.connect(str(self.root / "k230-shell-rust.sock"))
            peer.sendall((route + "\n").encode())
            assert peer.recv(64) == b"OK\n"

    def tap(self, ident, x, y):
        self.command(f"test-touch down {ident} {x} {y}")
        self.command(f"test-touch up {ident}")

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
        subprocess.run(["grim", str(path)],
                       env=self.env, check=True, timeout=15)
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

    @staticmethod
    def color_box(image, color=(32, 112, 176)):
        # The public probe animates alternating base/base-half bands.
        # Include both, otherwise the moving bands look like edge drift.
        masks = []
        for value in (color, tuple(v // 2 for v in color)):
            channels = ImageChops.difference(image, Image.new("RGB", image.size, value)).split()
            different = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
            masks.append(different.point(lambda v: 255 if v == 0 else 0))
        return ImageChops.lighter(*masks).getbbox()

    @staticmethod
    def assert_frame(image):
        assert image.size == (568, 1232), "output geometry changed"
        colors = image.getcolors(image.width * image.height)
        dark = sum(n for n, c in colors if max(c) < 12)
        assert dark < image.width * image.height * .10, "unowned black/blank frame"

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


def public_app(scene, app="k230.card.one"):
    scene.client_start(app)
    scene.ipc(f'[app_id="{app}"] focus')
    color = (32, 112, 176) if app.endswith("one") else (144, 48, 128)
    return scene.capture_when("app", lambda im: Scene.color_count(im, color) > 100
                              and max(im.getpixel((40, 1231))) >= 12)


def overview(scene):
    scene.command("enter")
    wait_for(lambda: scene.state().get("mode") == "1", "settled overview")
    return scene.capture_when("overview", lambda im:
                              (box := Scene.color_box(im)) and box[2] - box[0] < 500)


def panel_edge(image, baseline, surface, handle=None):
    if surface == "drawer":
        # Home and Drawer can use the same brush. Track the drawer's own
        # visible horizontal handle, learned from its actual settled frame,
        # rather than confusing identical backgrounds with absence.
        assert handle, "drawer reference not prepared"
        color, offset = handle
        changed = [y for y in range(1232)
                   if all(image.getpixel((x, y)) == color for x in (270, 284, 300))]
        return min(changed) - offset if changed else None
    else:
        # The tray and wallpaper can share a background color. Measure
        # the edge over the contrasting live root instead. Its alternating
        # blue/base-half bands share one dim factor; exclude only the
        # known 48px binary-counter header. The child starts to the right.
        x = 40
        bg, dim = baseline.getpixel((x, 1231)), image.getpixel((x, 1231))
        channel = max(range(3), key=lambda i: bg[i])
        assert bg[channel] >= 12, "invalid backdrop reference"
        factor = dim[channel] / bg[channel]
        box = Scene.color_box(baseline)
        assert box and box[0] < x < box[2], "missing live-root reference"
        bands = ((32, 112, 176), (16, 56, 88))
        changed = [y for y in range(box[1] + 48, box[3])
                   if all(max(abs(v - b * factor) for v, b in
                              zip(image.getpixel((x, y)), band)) > 6 for band in bands)]
    return (min(changed) if surface == "drawer" else max(changed) + 1) if changed else None


def await_panel(scene, name, baseline, surface, expected):
    last = None
    observed = set()
    def ready(im):
        nonlocal last
        last = panel_edge(im, baseline, surface, getattr(scene, "drawer_handle", None))
        observed.add(last)
        return last is not None and abs(last - expected) <= 2
    try:
        image = wait_for(lambda: (im if ready(im) else None)
                         if (im := scene.capture(name)) else None, name, 4)
    except AssertionError as error:
        if not str(error).startswith("timeout:"):
            raise
        raise AssertionError(f"{surface} edges {sorted(observed, key=str)}, expected {expected}±2") from error
    Scene.assert_frame(image)
    return image, last


def open_drawer(scene, ident=31):
    scene.command(f"test-touch down {ident} 284 1200")
    scene.command(f"test-touch motion {ident} 284 400")
    wait_for(lambda: scene.state().get("drawer_mapped") == "1", "drawer maps")
    scene.command(f"test-touch up {ident}")


def prepare_drawer_reference(scene):
    scene.route("drawer")
    reference = scene.capture_when("drawer-reference", lambda im:
                                    im.getpixel((284, 43)) != im.getpixel((284, 32)))
    color = reference.getpixel((284, 43))
    rows = [y for y in range(32, 54) if
            all(reference.getpixel((x, y)) == color for x in (270, 284, 300))]
    assert rows, "visible drawer handle missing from reference"
    scene.drawer_handle = (color, min(rows) - 32)
    unmaps = scene.rust_log().count(" unmap")
    scene.route("hide")
    wait_for(lambda: scene.rust_log().count(" unmap") > unmaps, "reference drawer hides")


def overview_to_home(scene, ident=30):
    # Accepted pinned-Home navigation supersedes the original direct
    # deck->drawer route (archived Home change, group 10).
    scene.command(f"test-touch down {ident} 284 1200")
    scene.command(f"test-touch motion {ident} 284 1000")
    wait_for(lambda: abs(float(scene.state()["home_offset"]) - 200) <= 1,
             "overview tracks upward Home transition")
    held = scene.capture("home-held")
    Scene.assert_frame(held)
    assert scene.state()["home_selected"] == "0", "Home selected before release"
    scene.command(f"test-touch up {ident}")
    wait_for(lambda: scene.state()["home_selected"] == "1" and
             scene.state()["home_settling"] == "0", "Home settles after overview")
    assert scene.focused() is None, "Home retained app focus"
    return scene.capture("home")


def shrink_live(scene):
    app = public_app(scene)
    first = Scene.color_box(app)
    scene.command("test-touch down 21 284 1200")
    samples = []
    for name, y in (("shrink-100", 1100), ("shrink-200", 1000)):
        scene.command(f"test-touch motion 21 284 {y}")
        previous = samples[-1]["box"] if samples else first
        image = scene.capture_when(name, lambda im:
                                   (box := Scene.color_box(im)) and
                                   box[2] - box[0] < previous[2] - previous[0] - 2)
        Scene.assert_frame(image)
        box = Scene.color_box(image)
        assert image.getpixel((box[0], box[3] - 1)) not in ((32, 112, 176), (16, 56, 88)), "card corner lacks clip"
        assert scene.state()["mode"] == "4", "held entry settled before release"
        assert scene.focused() == "k230.card.one", "entry changed app focus"
        samples.append({"finger_y": y, "box": box})
    counters = ("frames", "callbacks", "child_frames", "child_callbacks")
    before = {key: scene.record("k230.card.one")[key] for key in counters}
    wait_for(lambda: all(scene.record("k230.card.one")[key] > value
                         for key, value in before.items()), "live root and child during entry")
    held = scene.capture("shrink-held")
    Scene.assert_frame(held)
    assert Scene.color_box(held) == tuple(samples[-1]["box"]), "stationary entry drifted"
    scene.command("test-touch up 21")
    wait_for(lambda: scene.state()["mode"] == "1", "entry settles in overview")
    end = scene.capture_when("shrink-overview", lambda im: Scene.color_box(im) is not None)
    Scene.assert_frame(end)
    assert scene.mapped("k230.card.one"), "entry lost its source"
    return {"source_box": first, "held_samples": samples,
            "live_counters_before": before,
            "live_counters_after": {key: scene.record("k230.card.one")[key] for key in counters},
            "live_root_and_child_advanced": True, "held_geometry_stable": True,
            "rounded_clip": True, "destination": "overview"}


def drawer_rise(scene):
    public_app(scene)
    overview(scene)
    baseline = overview_to_home(scene)
    prepare_drawer_reference(scene)
    assert scene.mapped("k230.card.one"), "Home removed running app"
    scene.command("test-touch down 31 284 1200")
    samples = []
    for name, y, edge in (("drawer-100", 1100, 1132), ("drawer-300", 900, 932)):
        scene.command(f"test-touch motion 31 284 {y}")
        wait_for(lambda: scene.state()["drawer_mapped"] == "1", "drawer maps")
        image, actual = await_panel(scene, name, baseline, "drawer", edge)
        assert image.getpixel((284, 500)) == baseline.getpixel((284, 500)), "drawer moved underlying Home"
        assert "touch-down 31 " not in scene.rust_log(), "overlay stole the accepted stream"
        samples.append({"finger_y": y, "panel_top": actual})
    time.sleep(.15)
    _, edge = await_panel(scene, "drawer-held", baseline, "drawer", 932)
    scene.command("test-touch up 31")
    opened, end = await_panel(scene, "drawer-open", baseline, "drawer", 32)
    assert opened.getpixel((80, 150)) == (255, 255, 0) and baseline.getpixel((80, 150)) != (255, 255, 0), "drawer failed z-order"
    unmaps = scene.rust_log().count(" unmap")
    scene.route("hide")
    wait_for(lambda: scene.rust_log().count(" unmap") > unmaps, "drawer unmaps")
    recovered = scene.capture_when("drawer-restored", lambda im:
                                   Scene.color_count(im, (255, 255, 0)) == 0 and
                                   im.getpixel((284, 500)) == baseline.getpixel((284, 500)))
    Scene.assert_frame(recovered)
    assert scene.state()["home_selected"] == "1" and scene.focused() is None, "drawer return lost Home"
    assert scene.mapped("k230.card.one"), "drawer removed running app"
    return {"held_samples": samples, "held_top": edge, "settled_top": end,
            "route": "overview -> pinned Home -> drawer -> pinned Home",
            "underlying_home_stationary": True, "overlay_on_top": True,
            "accepted_stream_not_replayed": True, "running_app_retained": True}


def shade_descend(scene):
    baseline = public_app(scene)
    original = next(n["rect"] for n in Scene.nodes(scene.ipc("", 4))
                    if n.get("app_id") == "k230.card.one")
    scene.command("test-touch down 41 284 10")
    samples = []
    for name, y, edge in (("shade-100", 110, 100), ("shade-300", 310, 300)):
        scene.command(f"test-touch motion 41 284 {y}")
        wait_for(lambda: scene.state()["drawer_mapped"] == "1", "shade maps")
        image, actual = await_panel(scene, name, baseline, "shade", edge)
        assert image.getpixel((284, edge // 2)) != baseline.getpixel((284, edge // 2)), "shade below app"
        assert "touch-down 41 " not in scene.rust_log(), "shade stole the accepted stream"
        samples.append({"finger_y": y, "panel_bottom": actual})
    time.sleep(.15)
    _, held = await_panel(scene, "shade-held", baseline, "shade", 300)
    scene.command("test-touch motion 41 284 610")
    scene.command("test-touch up 41")
    shade, end = await_panel(scene, "shade-open", baseline, "shade", 801)
    assert scene.focused() == "k230.card.one", "nonmodal shade stole app focus"
    scene.tap(42, 510, 60)
    wait_for(lambda: '["status"]' in (scene.root / "settings.jsonl").read_text(), "Settings requested status")
    settings = scene.capture_when("shade-settings", lambda im:
                                  (bottom := panel_edge(im, baseline, "settings")) and bottom > 900)
    Scene.assert_frame(settings)
    assert ImageChops.difference(shade.crop((24, 24, 544, 780)),
                                 settings.crop((24, 24, 544, 780))).getbbox(), "Settings did not paint"
    bottom = panel_edge(settings, baseline, "settings")
    assert 900 < bottom < 1200, "Settings lost its content-sized top anchor"
    current = next(n["rect"] for n in Scene.nodes(scene.ipc("", 4))
                   if n.get("app_id") == "k230.card.one")
    assert current == original, "shade/Settings moved underlying app"
    unmaps = scene.rust_log().count(" unmap")
    scene.tap(43, 510, 60)  # Settings' actual Done target.
    wait_for(lambda: scene.rust_log().count(" unmap") > unmaps, "Settings Done unmaps")
    recovered = scene.capture_when("shade-restored", lambda im:
                                   Scene.color_box(im) == Scene.color_box(baseline))
    Scene.assert_frame(recovered)
    assert scene.focused() == "k230.card.one", "Settings return lost prior focus"
    assert all(json.loads(line) == ["status"] for line in
               (scene.root / "settings.jsonl").read_text().splitlines()), "unexpected settings action"
    return {"held_samples": samples, "held_bottom": held, "settled_bottom": end,
            "settings_bottom": bottom, "settings_opened_by_touch": True,
            "underlying_rect_preserved": True, "prior_focus_recovered": True,
            "settings_requests": "status only"}


def expand_live(scene):
    app = public_app(scene)
    full = Scene.color_box(app)
    deck = overview(scene)
    small = Scene.color_box(deck)
    scene.tap(51, 284, 500)
    samples = []
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        image = scene.capture(f"expand-{len(samples):02d}")
        Scene.assert_frame(image)
        box = Scene.color_box(image)
        assert box, "expansion lost live source pixels"
        samples.append({"box": box, "mode": scene.state()["mode"]})
        if scene.state()["mode"] == "0":
            break
    else:
        raise AssertionError("expansion did not settle")
    intermediate = [s for s in samples if small[2] - small[0] + 2 <
                    s["box"][2] - s["box"][0] < full[2] - full[0] - 2]
    assert intermediate, "only endpoints captured; intermediate expansion unproved"
    widths = [s["box"][2] - s["box"][0] for s in samples]
    assert all(b >= a - 2 for a, b in zip(widths, widths[1:])), "expansion geometry reversed"
    restored = scene.capture_when("expand-restored", lambda im: Scene.color_box(im) == full)
    Scene.assert_frame(restored)
    assert scene.focused() == "k230.card.one", "expanded app lacks focus"
    return {"card_box": small, "app_box": full, "samples": samples,
            "intermediate_live_geometry": True, "focus_restored": True}


def focus(scene):
    public_app(scene)
    public_app(scene, "k230.card.two")
    scene.ipc('[app_id="k230.card.one"] focus')
    scene.keyboard = Keyboard(scene.root / scene.env["WAYLAND_DISPLAY"])
    overview(scene)
    scene.command("next")
    wait_for(lambda: scene.state()["selected_app_id"] == "k230.card.two", "select neighboring card")
    assert scene.focused() != "k230.card.two", "browsing prematurely activated neighbor"
    scene.tap(61, 284, 500)
    wait_for(lambda: scene.state()["mode"] == "0" and scene.focused() == "k230.card.two", "expand commits neighbor focus")
    keys = {app: scene.record(app).get("key_presses", 0) for app in scene.apps}
    scene.keyboard.press()
    wait_for(lambda: scene.record("k230.card.two").get("key_presses", 0) > keys["k230.card.two"], "expanded neighbor receives key")
    assert scene.record("k230.card.one").get("key_presses", 0) == keys["k230.card.one"], "key reached wrong app"
    scene.command("enter")
    wait_for(lambda: scene.state()["mode"] == "1", "neighbor overview")
    baseline = overview_to_home(scene, 64)
    prepare_drawer_reference(scene)
    open_drawer(scene, 62)
    await_panel(scene, "focus-drawer", baseline, "drawer", 32)
    scene.tap(63, 284, 80)
    wait_for(lambda: "drawer-keyboard-focus-granted" in scene.rust_log(), "search owns keyboard focus")
    keys = {app: scene.record(app).get("key_presses", 0) for app in scene.apps}
    search = scene.capture("focus-search-before")
    scene.keyboard.press()
    typed = scene.capture_when("focus-search-typed", lambda im:
                               ImageChops.difference(search.crop((24, 55, 544, 110)),
                                                     im.crop((24, 55, 544, 110))).getbbox())
    Scene.assert_frame(typed)
    assert all(scene.record(app).get("key_presses", 0) == value for app, value in keys.items()), "search key leaked into app"
    search_keys = {app: scene.record(app).get("key_presses", 0) for app in scene.apps}
    unmaps = scene.rust_log().count(" unmap")
    scene.route("hide")
    wait_for(lambda: scene.rust_log().count(" unmap") > unmaps, "search drawer hides")
    assert scene.focused() is None and scene.state()["home_selected"] == "1", "search return lost Home focus"
    open_drawer(scene, 65)
    await_panel(scene, "focus-drawer-reopened", baseline, "drawer", 32)
    scene.tap(66, 216, 170)  # Public identity two, second catalog tile.
    wait_for(lambda: scene.focused() == "k230.card.two" and
             scene.state()["drawer_mapped"] == "0", "drawer activates existing chosen app")
    restored = scene.capture_when("focus-app-restored", lambda im:
                                   Scene.color_count(im, (144, 48, 128)) > 100 and
                                   Scene.color_count(im, (32, 112, 176)) == 0)
    Scene.assert_frame(restored)
    assert scene.state()["home_selected"] == "0", "app activation left Home selected"
    scene.keyboard.press()
    wait_for(lambda: scene.record("k230.card.two").get("key_presses", 0) > keys["k230.card.two"], "keyboard returns to selected app")
    assert scene.record("k230.card.one").get("key_presses", 0) == keys["k230.card.one"], "return focused wrong app"
    return {"neighbor_focus_committed_after_expand": True,
            "expanded_app_received_key": True, "search_received_key": True,
            "search_key_not_delivered_to_apps": True, "search_returned_to_home": True,
            "drawer_activated_existing_app": True, "selected_app_focus_recovered": True,
            "key_counts_during_search": search_keys,
            "key_counts_after_return": {app: scene.record(app).get("key_presses", 0) for app in scene.apps}}


def visible_app(scene, app, name):
    scene.ipc(f'[app_id="{app}"] focus')
    color = (32, 112, 176) if app.endswith("one") else (144, 48, 128)
    image = scene.capture_when(name, lambda im: Scene.color_count(im, color) > 100)
    Scene.assert_frame(image)
    return Scene.color_box(image, color)


def held_entry(scene, ident, y=900, x=284, name="entry-held"):
    scene.command(f"test-touch down {ident} 284 1200")
    scene.command(f"test-touch motion {ident} {x} {y}")
    image = scene.capture_when(name, lambda im:
                               (box := Scene.color_box(im)) and box[2] - box[0] < 500)
    Scene.assert_frame(image)
    assert scene.state()["mode"] == "4", "entry is not held"
    return Scene.color_box(image)


def recovery_frames(scene, name, mode, color=(32, 112, 176), forbidden=(), expected_width=None):
    samples = []
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        image = scene.capture(f"{name}-{len(samples):02d}")
        Scene.assert_frame(image)
        for denied in forbidden:
            assert Scene.color_count(image, denied) == 0, "retired/private source pixels returned"
        box = Scene.color_box(image, color)
        assert box, "recovery lost its reachable live source"
        state = scene.state()
        samples.append({"box": box, "mode": state["mode"],
                        "selected_app_id": state["selected_app_id"]})
        width = box[2] - box[0]
        # IPC can already report the final mode while this screencopy was
        # composed one frame earlier. Require the destination's actual pixels
        # as well, rather than pairing a stale transform with the new mode.
        final_pixels = (mode != 0 or width >= 518) and (
            expected_width is None or abs(width - expected_width) <= 2)
        if state["mode"] == str(mode) and final_pixels:
            return samples
    raise AssertionError(f"{name} did not settle in mode {mode}")


def expanding_frame(scene, name, interrupt, color=(32, 112, 176)):
    deck = overview(scene)
    small = Scene.color_box(deck, color)
    assert small, "selected expansion source absent"
    scene.tap(101, 284, 500)
    # Raw screencopy avoids PNG encoding/decoding inside the 160ms input
    # window. Inspect one row, deliver the real interruption and query its
    # state before encoding the same captured frame for the evidence file.
    def ready():
        raw = subprocess.run(["grim", "-t", "ppm", "-"], env=scene.env,
                             stdout=subprocess.PIPE, check=True, timeout=15)
        image = Image.open(io.BytesIO(raw.stdout)).convert("RGB")
        colors = (color, tuple(v // 2 for v in color))
        xs = [x for x in range(568) if image.getpixel((x, 600)) in colors]
        if not (xs and small[2] - small[0] + 2 < max(xs) - min(xs) + 1 < 518):
            return None
        interrupt()
        state = scene.state()
        image.save(scene.root / f"{name}.png")
        return image, state
    image, state = wait_for(ready, name)
    return small, image, state


def reverse(scene):
    full = Scene.color_box(public_app(scene))
    held = held_entry(scene, 81)
    scene.command("test-touch motion 81 284 1150")
    image = scene.capture_when("reverse-finger", lambda im:
                               (box := Scene.color_box(im)) and
                               held[2] - held[0] + 20 < box[2] - box[0] < full[2] - full[0])
    Scene.assert_frame(image)
    reversed_box = Scene.color_box(image)
    scene.command("test-touch up 81")
    finger = recovery_frames(scene, "reverse-release", 0)
    assert scene.focused() == "k230.card.one", "finger reversal activated another app"

    held = held_entry(scene, 82, name="back-entry-held")
    scene.command("back")
    assert scene.state()["mode"] == "4", "Back reset entry to the full app instead of reversing"
    back = recovery_frames(scene, "back-entry-reverse", 0)
    assert any(held[2] - held[0] < s["box"][2] - s["box"][0] < full[2] - full[0]
               for s in back), "Back entry reversal has no intermediate live geometry"
    scene.command("test-touch motion 82 400 700")
    scene.command("test-touch up 82")
    assert scene.focused() == "k230.card.one", "Back leaked the canceled stream"

    small, middle_image, interrupted = expanding_frame(
        scene, "back-expand-middle", lambda: scene.command("back"))
    assert interrupted["mode"] == "5", "Back reset unfinished expansion instead of reversing"
    Scene.assert_frame(middle_image)
    middle = Scene.color_box(middle_image)
    expansion = recovery_frames(scene, "back-expand-reverse", 1,
                                 expected_width=small[2] - small[0])
    assert expansion[-1]["box"][2] - expansion[-1]["box"][0] <= small[2] - small[0] + 2
    assert scene.focused() == "k230.card.one", "expansion reversal lost original focus"
    return {"finger_reversal_box": reversed_box, "finger_release_frames": finger,
            "back_entry_frames": back, "expansion_interrupted_box": middle,
            "back_expansion_frames": expansion, "owned_stream_drained": True}


def retarget(scene):
    full = Scene.color_box(public_app(scene))
    held = held_entry(scene, 91, name="second-contact-held")
    scene.command("test-touch down 92 350 650")
    assert scene.state()["mode"] == "4", "second contact reset entry geometry"
    second = recovery_frames(scene, "second-contact-reverse", 0)
    assert any(held[2] - held[0] < s["box"][2] - s["box"][0] < full[2] - full[0]
               for s in second), "second-contact reversal skipped intermediate geometry"
    scene.command("test-touch motion 91 100 600")
    scene.command("test-touch motion 92 350 300")
    scene.command("test-touch up 92")
    scene.command("test-touch up 91")
    assert scene.focused() == "k230.card.one" and scene.mapped("k230.card.one")

    # A new contact during expansion reverses the current live transform,
    # rather than activating the card or resetting its start keyframe.
    small, middle_image, interrupted = expanding_frame(
        scene, "new-contact-middle", lambda: scene.command("test-touch down 93 300 650"))
    assert interrupted["mode"] == "5", "new contact skipped current expansion geometry"
    Scene.assert_frame(middle_image)
    middle = Scene.color_box(middle_image)
    contact = recovery_frames(scene, "new-contact-reverse", 1,
                               expected_width=small[2] - small[0])
    assert contact[-1]["box"][2] - contact[-1]["box"][0] <= small[2] - small[0] + 2
    scene.command("test-touch motion 93 300 300")
    scene.command("test-touch up 93")
    assert scene.state()["mode"] == "1", "interrupting stream activated or closed a card"
    scene.tap(94, 284, 500)
    recovered = recovery_frames(scene, "retarget-expand-again", 0)
    assert scene.focused() == "k230.card.one", "fresh contact failed after stream drain"
    assert "K230_CARD_SHELL close-request" not in (scene.root / "sway.log").read_text()
    return {"second_contact_frames": second, "new_contact_interrupted_box": middle,
            "new_contact_frames": contact, "fresh_activation_frames": recovered,
            "no_accidental_close": True, "fresh_stream_recovers": True}


def unmap(scene):
    public_app(scene)
    scene.client_start("k230.card.two")
    visible_app(scene, "k230.card.one", "unmap-origin")
    held_entry(scene, 111, x=104, name="target-unmap-held")
    scene.apps["k230.card.two"].terminate()
    scene.apps["k230.card.two"].wait(timeout=10)
    wait_for(lambda: not scene.mapped("k230.card.two"), "held neighbor actually unmaps")
    target = scene.capture("target-unmap-remaining")
    Scene.assert_frame(target)
    assert Scene.color_count(target, (144, 48, 128)) == 0, "unmapped neighbor cache leaked"
    scene.command("test-touch up 111")
    target_frames = recovery_frames(scene, "target-unmap-recover", 0,
                                    forbidden=((144, 48, 128), (72, 24, 64)))
    assert scene.focused() == "k230.card.one", "vanished target substituted another app"

    scene.client_start("k230.card.two")
    visible_app(scene, "k230.card.one", "source-unmap-origin")
    held_entry(scene, 112, x=104, name="source-unmap-held")
    scene.apps["k230.card.one"].terminate()
    scene.apps["k230.card.one"].wait(timeout=10)
    wait_for(lambda: not scene.mapped("k230.card.one"), "entry source actually unmaps")
    source_frames = recovery_frames(scene, "source-unmap-recover", 0,
                                    (144, 48, 128), ((32, 112, 176), (16, 56, 88)))
    scene.command("test-touch up 112")
    assert scene.focused() == "k230.card.two", "source disappearance lost valid survivor focus"

    scene.client_start("k230.card.one")
    visible_app(scene, "k230.card.one", "expansion-unmap-origin")
    overview(scene)
    # The surviving two was mapped before the replacement one. Stable card
    # ordering therefore puts the target to its left, not its right.
    scene.command("previous")
    wait_for(lambda: scene.state()["selected_app_id"] == "k230.card.two", "unmap expansion target selected")
    small, middle_image, interrupted = expanding_frame(
        scene, "expansion-unmap-middle",
        lambda: scene.apps["k230.card.two"].terminate(), (144, 48, 128))
    scene.apps["k230.card.two"].wait(timeout=10)
    Scene.assert_frame(middle_image)
    middle = Scene.color_box(middle_image, (144, 48, 128))
    wait_for(lambda: not scene.mapped("k230.card.two"), "unfinished expansion source actually unmaps")
    expansion = recovery_frames(scene, "expansion-unmap-recover", 0,
                                 forbidden=((144, 48, 128), (72, 24, 64)))
    assert scene.focused() == "k230.card.one", "expansion exit focused a dead source"
    assert "K230_CARD_SHELL close-request" not in (scene.root / "sway.log").read_text()
    return {"target_exit_frames": target_frames, "entry_source_exit_frames": source_frames,
            "expansion_source_box": middle, "expansion_exit_frames": expansion,
            "no_retired_pixels": True, "valid_focus_recovered": True}


def refusal(scene):
    scene.client_start("k230.card.one", refuse=True)
    visible_app(scene, "k230.card.one", "refusal-origin")
    overview(scene)
    stamp = int(time.monotonic() * 1000) & 0xffffffff
    for command in (f"down 121 284 600 {stamp}",
                    f"motion 121 284 450 {(stamp + 30) & 0xffffffff}",
                    f"motion 121 284 280 {(stamp + 60) & 0xffffffff}",
                    f"up 121 {(stamp + 70) & 0xffffffff}"):
        scene.command("test-touch " + command)
    log = lambda: (scene.root / "sway.log").read_text()
    wait_for(lambda: log().count("K230_CARD_SHELL close-request") == 1, "one actual graceful close request")
    assert scene.state()["mode"] == "3", "pending close scene absent"
    pending = recovery_frames(scene, "refusal-pending", 1)
    assert any(s["mode"] == "3" for s in pending), "pending refusal has no composed sample"
    assert "message=6" in log(), "actual close timeout feedback missing"
    assert scene.apps["k230.card.one"].poll() is None and scene.mapped("k230.card.one")
    scene.command("back")
    recovery_frames(scene, "refusal-app-return", 0)
    assert scene.focused() == "k230.card.one"
    scene.keyboard = Keyboard(scene.root / scene.env["WAYLAND_DISPLAY"])
    keys = scene.record("k230.card.one").get("key_presses", 0)
    scene.keyboard.press()
    wait_for(lambda: scene.record("k230.card.one").get("key_presses", 0) > keys, "refused app receives key")
    # A new accepted gesture remains possible after timeout recovery.
    held_entry(scene, 122, name="refusal-fresh-entry")
    scene.command("test-touch up 122")
    recovery_frames(scene, "refusal-deck-return", 1)
    return {"pending_and_timeout_frames": pending, "close_requests": 1,
            "timeout_feedback": True, "app_retained": True,
            "keyboard_recovered": True, "fresh_gesture_recovered": True}


def private_no_flash(scene):
    public_app(scene)
    scene.client_start("k230.card.two")
    visible_app(scene, "k230.card.one", "privacy-origin")
    held_entry(scene, 131, x=104, name="privacy-public-neighbor")
    public = scene.capture_when("privacy-public-control", lambda im:
                                Scene.color_count(im, (144, 48, 128)) > 100)
    public_count = Scene.color_count(public, (144, 48, 128))
    scene.ipc('[app_id="k230.card.two"] mark --add k230_card_private')
    samples = []
    for number, (x, y) in enumerate(((104, 900), (54, 850), (154, 1000), (104, 900))):
        scene.command(f"test-touch motion 131 {x} {y}")
        image = scene.capture(f"privacy-transition-{number:02d}")
        Scene.assert_frame(image)
        assert Scene.color_count(image, (32, 112, 176)) > 100, "eligible source disappeared"
        for color in ((144, 48, 128), (72, 24, 64), (0, 255, 255)):
            assert Scene.color_count(image, color) == 0, "private neighbor flashed content or icon"
        samples.append({"finger": [x, y], "mode": scene.state()["mode"], "private_content_pixels": 0, "private_icon_pixels": 0})
    scene.command("test-touch motion 131 284 900")
    scene.command("test-touch up 131")
    recovery = recovery_frames(scene, "privacy-settle", 1,
                                forbidden=((144, 48, 128), (72, 24, 64), (0, 255, 255)))
    scene.command("next")
    private = scene.capture_when("privacy-selected-placeholder", Scene.neutral_placeholder)
    Scene.assert_frame(private)
    assert scene.state()["selected_app_id"] == "k230.card.two", "private placeholder target changed"
    for color in ((144, 48, 128), (72, 24, 64), (0, 255, 255)):
        assert Scene.color_count(private, color) == 0, "private selected card leaked identity"
    assert scene.mapped("k230.card.two"), "privacy hid the application by removing it"
    return {"public_control_pixels": public_count, "held_transition_samples": samples,
            "settle_frames": recovery, "visible_neutral_private_card": True,
            "private_content_and_icon_absent": True, "application_retained": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=CASES, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    args = parser.parse_args()
    sway, client = binaries()
    rust = os.environ.get("K230_SHELL_RUST")
    if any(case in SCENE_CASES + INTERRUPTION_CASES for case in args.case):
        assert rust and Path(rust).is_file(), "set K230_SHELL_RUST to the selected cross-built executable"
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
    if any(case in SCENE_CASES + INTERRUPTION_CASES for case in args.case):
        result.update(rust=rust, rust_sha256=hashlib.sha256(Path(rust).read_bytes()).hexdigest(),
                      service_inputs="synthetic status-only Settings and unavailable notification/audio services")
    try:
        for case in dict.fromkeys(args.case):
            scene = Scene(output / case, sway, client, args.qemu,
                          rust if case in SCENE_CASES + INTERRUPTION_CASES else None)
            try:
                scene.start()
                proof = {"live-gate": live_gate, "private-no-icon": private_no_icon,
                         "close-refused": close_refused, "shrink-live": shrink_live,
                         "drawer-rise": drawer_rise, "shade-descend": shade_descend,
                         "expand-live": expand_live, "focus": focus,
                         "reverse": reverse, "retarget": retarget, "unmap": unmap,
                         "refusal": refusal, "private-no-flash": private_no_flash}[case](scene)
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

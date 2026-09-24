#!/usr/bin/env python3
"""Exercise a real Sway/Rust appearance fanout under headless QEMU.

This is synthetic input and compositor output, never a panel or finger test.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from theme_transaction import TransactionError, activate_generation, exchange


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("sway", "rust", "client", "output"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--check-restart", action="store_true")
    return parser.parse_args()


def main():
    args = arguments()
    out = Path(args.output)
    out.mkdir(mode=0o700, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    state = out / "state"
    state.mkdir()
    default_id = "20f2d477bb758593d831e427"
    default = out / "default/generations" / default_id
    default.mkdir(parents=True)
    initial_report = json.loads((root / "nix/handheld-theme-default/default-report.json").read_text())
    initial_appearance = json.loads((root / "nix/handheld-theme-default/default-appearance.json").read_text())
    (default / "report.json").write_text(json.dumps(initial_report))
    (default / "appearance.json").write_text(json.dumps(initial_appearance))

    def generation(identity, top, bottom, canvas, drawer):
        path = state / "generations" / identity
        assets = path / "theme/backgrounds"
        assets.mkdir(parents=True)
        image = Image.new("RGBA", (568, 1232), top)
        ImageDraw.Draw(image).rectangle((0, 616, 567, 1231), fill=bottom)
        image.save(assets / "fixture.png")
        report = json.loads(json.dumps(initial_report))
        appearance = json.loads(json.dumps(initial_appearance))
        report.update(generation=identity, backgrounds=["backgrounds/fixture.png"],
                      selected_background="backgrounds/fixture.png")
        appearance.update(generation=identity, background="background")
        appearance["sections"]["card"] = {
            "canvas": {"kind": "brush", "stops": [{"argb": canvas, "offset": 0}],
                       "angle_degrees": 0, "alpha": 0.20}}
        appearance["sections"]["launcher"] = {
            "background": {"kind": "brush", "stops": [{"argb": drawer, "offset": 0}],
                           "angle_degrees": 0, "alpha": 1}}
        (path / "report.json").write_text(json.dumps(report))
        (path / "appearance.json").write_text(json.dumps(appearance))
        return path

    first = generation("111111111111111111111111", (240, 20, 20), (20, 20, 240),
                       "#00000000", "#ff22aa22")
    second = generation("222222222222222222222222", (240, 20, 240), (240, 180, 20),
                        "#00000000", "#ffaa22aa")
    config = out / "sway.conf"
    config.write_text("output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n"
                      "focus_follows_mouse no\n"
                      'for_window [app_id="^k230.card."] floating enable, border none, '
                      "resize set 520 1040, move position 24 48\n")
    catalog = out / "data/applications"
    catalog.mkdir(parents=True)
    for index in range(4):
        (catalog / f"fixture-{index}.desktop").write_text(
            "[Desktop Entry]\nType=Application\n"
            f"Name=Public Fixture {index}\nExec=/bin/true\n")
    env = dict(os.environ, XDG_RUNTIME_DIR=str(out), WLR_BACKENDS="headless",
               WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
               XDG_DATA_HOME=str(out / "data"), XDG_DATA_DIRS=str(out / "data"),
               SWAY_K230_CARD_SHELL="1", SWAY_K230_CARD_TOUCH_FIRST="1",
               SWAY_K230_CARD_APPEARANCE_SOCKET=str(out / "card-appearance.sock"),
               SWAY_K230_CARD_THEME_STATE_ROOT=str(state),
               SWAY_K230_CARD_THEME_DEFAULT=str(default),
               K230_THEME_STATE_ROOT=str(state),
               K230_THEME_DEFAULT_GENERATION=str(default))
    logs = {}
    processes = []

    def spawn(name, argv):
        log = (out / (name + ".log")).open("w")
        logs[name] = log
        process = subprocess.Popen(argv, env=env, stdout=log, stderr=log)
        processes.append(process)
        return process

    def log(name):
        return (out / (name + ".log")).read_text()

    def wait(predicate, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(0.05)
        raise AssertionError("timed out")

    def ipc(command, kind=0):
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(5)
            peer.connect(str(next(out.glob("sway-ipc.*.sock"))))
            payload = command.encode()
            peer.sendall(b"i3-ipc" + struct.pack("=II", len(payload), kind) + payload)

            def read(count):
                chunks = bytearray()
                while len(chunks) < count:
                    part = peer.recv(count - len(chunks))
                    assert part, "IPC closed"
                    chunks.extend(part)
                return chunks

            header = read(14)
            length, _ = struct.unpack("=II", header[6:])
            reply = json.loads(read(length))
            if kind == 0:
                assert all(item["success"] for item in reply), (command, reply)
            return reply

    def capture(name):
        subprocess.run(["grim", str(out / name)], env=env, check=True)
        return Image.open(out / name).convert("RGB")

    rust_endpoint = out / "k230-shell-rust-appearance.sock"
    card_endpoint = out / "card-appearance.sock"
    try:
        spawn("sway", [args.qemu, args.sway, "-c", str(config), "-d"])
        wait(lambda: "Running compositor on wayland display" in log("sway"), 60)
        env["WAYLAND_DISPLAY"] = next(path.name for path in out.glob("wayland-*")
                                       if not path.name.endswith(".lock"))
        env["SWAYSOCK"] = str(next(out.glob("sway-ipc.*.sock")))
        wait(card_endpoint.exists)
        rust_process = spawn("rust", [args.qemu, args.rust, "--serve"])
        wait(lambda: "wallpaper-commit" in log("rust") and rust_endpoint.exists(), 30)
        spawn("client", [args.client, "--app-id", "k230.card.one"])
        wait(lambda: "k230.card.one" in json.dumps(ipc("", 4)))
        app_before = capture("app-before.png")
        ipc("card_shell enter")
        wait(lambda: "K230_CARD_SHELL mirror id=" in log("sway"))
        baseline = capture("baseline.png")

        endpoints = (card_endpoint, rust_endpoint)
        result = activate_generation(first, state_root=state, endpoint=card_endpoint,
                                     endpoints=endpoints, app_sync=lambda *a, **k: None)
        assert result["state"] == "applied", result
        wait(lambda: "wallpaper-commit" in log("rust") and log("rust").count("wallpaper-commit") >= 2)
        time.sleep(0.3)
        themed_deck = capture("themed-deck.png")
        # The outside-card canvas is transparent, exposing two distinct image regions.
        upper = themed_deck.getpixel((10, 300))
        lower = themed_deck.getpixel((10, 900))
        assert upper[0] > 150 and upper[2] < 80, upper
        assert lower[2] > 150 and lower[0] < 80, lower
        assert upper != baseline.getpixel((10, 300))
        assert lower != baseline.getpixel((10, 900))

        ipc("card_shell back")
        # The app expansion settles over several compositor frames; wait for
        # the actual live pixel instead of assuming a timer means presented.
        def expanded_app():
            image = capture("app-after.png")
            return image if image.getpixel((284, 500)) == app_before.getpixel((284, 500)) else None

        app_after = wait(expanded_app, 5)
        assert app_after.getpixel((284, 500)) == app_before.getpixel((284, 500)), \
            "persistent input-empty wallpaper obscured the live app"
        ipc("card_shell enter")
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(3)
            peer.connect(str(out / "k230-shell-rust.sock"))
            peer.sendall(b"drawer\n")
            assert peer.recv(64) == b"OK\n"
        wait(lambda: "map-request" in log("rust"))
        wait(lambda: any(line.endswith(" commit") for line in log("rust").splitlines()), 8)
        time.sleep(0.2)
        drawer = capture("themed-drawer.png")
        # Drawer interior uses the authored launcher brush; the live deck is behind it.
        drawer_pixel = drawer.getpixel((10, 500))
        assert drawer_pixel[1] > drawer_pixel[0] and drawer_pixel[1] > drawer_pixel[2], drawer_pixel

        def fail_second_commit(endpoint, phase, generation):
            if endpoint == rust_endpoint and phase == "commit":
                raise TransactionError("injected Rust commit failure")
            exchange(endpoint, phase, generation)

        try:
            activate_generation(second, state_root=state, endpoint=card_endpoint,
                                endpoints=endpoints, transport=fail_second_commit,
                                app_sync=lambda *a, **k: None)
            raise AssertionError("injected failure did not abort")
        except TransactionError as error:
            assert "previous generation restored" in str(error), str(error)
        assert (state / "active").resolve() == first
        time.sleep(0.3)
        rollback = capture("rollback.png")
        assert rollback.getpixel((10, 500)) == drawer_pixel
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(3)
            peer.connect(str(out / "k230-shell-rust.sock"))
            peer.sendall(b"hide\n")
            assert peer.recv(64) == b"OK\n"
        wait(lambda: "unmap" in log("rust"))
        time.sleep(0.2)
        rollback_deck = capture("rollback-deck.png")
        assert rollback_deck.getpixel((10, 300)) == themed_deck.getpixel((10, 300))
        assert rollback_deck.getpixel((10, 900)) == themed_deck.getpixel((10, 900))
        if args.check_restart:
            rust_process.terminate()
            rust_process.wait(timeout=3)
            rust_process = spawn("rust-restarted", [args.qemu, args.rust, "--serve"])
            wait(lambda: "wallpaper-commit" in log("rust-restarted"), 30)
            wait(lambda: (image := capture("restarted-deck.png")).getpixel((10, 300)) ==
                 themed_deck.getpixel((10, 300)) and image.getpixel((10, 900)) ==
                 themed_deck.getpixel((10, 900)), 5)
            with socket.socket(socket.AF_UNIX) as peer:
                peer.settimeout(3)
                peer.connect(str(out / "k230-shell-rust.sock"))
                peer.sendall(b"drawer\n")
                assert peer.recv(64) == b"OK\n"
            wait(lambda: any(line.endswith(" commit") for line in log("rust-restarted").splitlines()), 8)
            reopened = capture("restarted-drawer.png")
            assert reopened.getpixel((10, 500)) == drawer_pixel
        summary = {"result": "PASS", "class": "headless-qemu-paired-appearance",
                   "sway": args.sway, "rust": args.rust,
                   "wallpaper_upper": upper, "wallpaper_lower": lower,
                   "drawer": drawer_pixel, "rollback_pointer": first.name,
                   "background_did_not_obscure_app": True,
                   "injected_failure_rolled_back_both": True,
                   "restart_preserved_selected_generation": args.check_restart}
        (out / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary, indent=2))
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        for handle in logs.values():
            handle.close()


if __name__ == "__main__":
    main()

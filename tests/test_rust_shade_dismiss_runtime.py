#!/usr/bin/env python3
"""Headless QEMU regression for Rust shade release, cancel, and second touch.

Only synthetic touch and public client pixels are used; no physical claim.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time

from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("sway", "rust", "client", "output"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(mode=0o700, exist_ok=False)
    config = out / "sway.conf"
    config.write_text("output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n"
                      "focus_follows_mouse no\n"
                      'for_window [app_id="^k230.card."] floating enable, border none, '
                      "resize set 520 1040, move position 24 48\n")
    catalog = out / "data/applications"
    catalog.mkdir(parents=True)
    (catalog / "public-fixture.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Public Fixture\nExec=/bin/true\n")
    env = dict(os.environ, XDG_RUNTIME_DIR=str(out), XDG_DATA_HOME=str(out / "data"),
               XDG_DATA_DIRS=str(out / "data"), WLR_BACKENDS="headless",
               WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
               SWAY_K230_CARD_SHELL="1", SWAY_K230_CARD_TOUCH_FIRST="1",
               SWAY_K230_CARD_TEST_INPUT="1")
    logs = {}
    processes = []

    def spawn(name, argv):
        handle = (out / (name + ".log")).open("w")
        logs[name] = handle
        process = subprocess.Popen(argv, env=env, stdout=handle, stderr=handle)
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

            def read(length):
                data = bytearray()
                while len(data) < length:
                    chunk = peer.recv(length - len(data))
                    assert chunk, "IPC closed"
                    data.extend(chunk)
                return data

            header = read(14)
            length, _ = struct.unpack("=II", header[6:])
            response = json.loads(read(length))
            if kind == 0:
                assert all(item["success"] for item in response), (command, response)
            return response

    def touch(command):
        return ipc("card_shell test-touch " + command)

    def route(surface):
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(3)
            peer.connect(str(out / "k230-shell-rust.sock"))
            peer.sendall((surface + "\n").encode())
            assert peer.recv(64) == b"OK\n"

    def capture(name):
        subprocess.run(["grim", str(out / name)], env=env, check=True)
        return Image.open(out / name).convert("RGB")

    try:
        spawn("sway", [args.qemu, args.sway, "-c", str(config), "-d"])
        wait(lambda: "Running compositor on wayland display" in log("sway"), 60)
        env["WAYLAND_DISPLAY"] = next(path.name for path in out.glob("wayland-*")
                                       if not path.name.endswith(".lock"))
        env["SWAYSOCK"] = str(next(out.glob("sway-ipc.*.sock")))
        spawn("rust", [args.qemu, args.rust, "--serve"])
        wait(lambda: "ready-idle" in log("rust"))
        spawn("client", [args.client, "--app-id", "k230.card.one"])
        wait(lambda: "k230.card.one" in json.dumps(ipc("", 4)))
        touch("init")
        ipc("card_shell enter")
        wait(lambda: "K230_CARD_SHELL mirror id=" in log("sway"))
        deck = capture("deck.png")
        route("shade")
        wait(lambda: any(line.endswith(" commit") for line in log("rust").splitlines()), 8)
        shade = capture("shade-open.png")
        assert shade.getpixel((10, 400)) != deck.getpixel((10, 400))
        assert "unmap" not in log("rust")

        # Cancellation after a qualifying movement must preserve the shade.
        touch("down 1 284 700")
        wait(lambda: "touch-down 1" in log("rust"))
        touch("motion 1 284 420")
        touch("cancel")
        wait(lambda: "touch-cancel" in log("rust"))
        time.sleep(0.1)
        assert "unmap" not in log("rust")
        cancelled = capture("shade-cancelled.png")
        assert cancelled.getpixel((10, 400)) == shade.getpixel((10, 400))

        # Competing contact cancels ownership even when the first moves up.
        touch("down 2 284 700")
        wait(lambda: "touch-down 2" in log("rust"))
        touch("down 3 300 680")
        wait(lambda: "touch-second-cancel" in log("rust"))
        touch("motion 2 284 420")
        touch("up 2")
        touch("up 3")
        time.sleep(0.1)
        assert "unmap" not in log("rust")
        competing = capture("shade-multitouch.png")
        assert competing.getpixel((10, 400)) == shade.getpixel((10, 400))

        # A sole upward release owns dismissal and reveals the existing deck.
        touch("down 4 284 700")
        wait(lambda: "touch-down 4" in log("rust"))
        touch("motion 4 284 420")
        touch("up 4")
        wait(lambda: "unmap" in log("rust"), 5)
        uncovered = capture("deck-restored.png")
        assert uncovered.getpixel((10, 400)) == deck.getpixel((10, 400))

        # Reopening over the ordinary app must restore that app, not Home.
        ipc("card_shell back")
        def app_ready():
            image = capture("app-before-shade.png")
            return image if image.getpixel((284, 500)) == (32, 112, 176) else None
        app = wait(app_ready, 5)
        route("shade")
        wait(lambda: sum(line.endswith(" commit") for line in log("rust").splitlines()) >= 2, 8)
        app_shade = capture("app-shade.png")
        assert app_shade.getpixel((10, 400)) != app.getpixel((10, 400))
        touch("down 5 284 700")
        wait(lambda: "touch-down 5" in log("rust"))
        touch("motion 5 284 420")
        touch("up 5")
        wait(lambda: log("rust").count("unmap") >= 2, 5)
        app_restored = wait(lambda: (image if image.getpixel((284, 500)) ==
                                    app.getpixel((284, 500)) else None)
                            if (image := capture("app-restored.png")) else None, 5)
        assert app_restored.getpixel((284, 500)) == app.getpixel((284, 500))
        assert "k230.card.one" in json.dumps(ipc("", 4))
        result = {"result": "PASS", "class": "headless-qemu-native-touch",
                  "sway": args.sway, "rust": args.rust,
                  "cancel_kept_shade": True, "second_contact_kept_shade": True,
                  "upward_release_unmapped": True,
                  "underlying_deck_restored": True, "underlying_app_restored": True}
        (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
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

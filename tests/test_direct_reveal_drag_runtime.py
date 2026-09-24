#!/usr/bin/env python3
"""Headless QEMU pixel proof of 1:1 drawer and shade contact motion.

Synthetic touch can establish composed pixels, not real finger/panel timing.
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


WIDTH, HEIGHT = 568, 1232


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("sway", "rust", "client", "output"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(mode=0o700, exist_ok=False)
    config = out / "sway.conf"
    config.write_text(f"output HEADLESS-1 mode {WIDTH}x{HEIGHT}\nseat seat0 fallback true\n"
                      "focus_follows_mouse no\n"
                      'for_window [app_id="^k230.card."] floating enable, border none, '
                      "resize set 520 1040, move position 24 48\n")
    catalog = out / "data/applications"
    catalog.mkdir(parents=True)
    (catalog / "fixture.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Public Fixture\nExec=/bin/true\n")
    env = dict(os.environ, XDG_RUNTIME_DIR=str(out), XDG_DATA_HOME=str(out / "data"),
               XDG_DATA_DIRS=str(out / "data"), WLR_BACKENDS="headless",
               WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
               SWAY_K230_CARD_SHELL="1", SWAY_K230_CARD_TOUCH_FIRST="1",
               SWAY_K230_CARD_TEST_INPUT="1", SWAY_K230_CARD_REVEAL_STREAM="1",
               SWAY_K230_CARD_SURFACE_SOCKET=str(out / "k230-shell-rust.sock"))
    logs, processes = {}, []

    def spawn(name, argv):
        handle = (out / f"{name}.log").open("w")
        logs[name] = handle
        process = subprocess.Popen(argv, env=env, stdout=handle, stderr=handle)
        processes.append(process)
        return process

    def log(name):
        return (out / f"{name}.log").read_text()

    def wait(predicate, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(0.03)
        raise AssertionError("timed out")

    def ipc(command, kind=0):
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(5)
            peer.connect(str(next(out.glob("sway-ipc.*.sock"))))
            payload = command.encode()
            peer.sendall(b"i3-ipc" + struct.pack("=II", len(payload), kind) + payload)

            def read(count):
                data = bytearray()
                while len(data) < count:
                    chunk = peer.recv(count - len(data))
                    assert chunk, "IPC closed"
                    data.extend(chunk)
                return data

            header = read(14)
            length, _ = struct.unpack("=II", header[6:])
            reply = json.loads(read(length))
            if kind == 0:
                assert all(row["success"] for row in reply), (command, reply)
            return reply

    def touch(action):
        return ipc("card_shell test-touch " + action)

    def capture(name):
        subprocess.run(["grim", str(out / name)], env=env, check=True)
        return Image.open(out / name).convert("RGB")

    def edge(image, baseline, surface):
        changed = [y for y in range(HEIGHT)
                   if image.getpixel((10, y)) != baseline.getpixel((10, y))]
        if not changed:
            return None
        return min(changed) if surface == "drawer" else max(changed) + 1

    def await_edge(name, baseline, surface, expected, tolerance=2):
        last = None
        def measured():
            nonlocal last
            last = edge(capture(name), baseline, surface)
            return last if last is not None and abs(last - expected) <= tolerance else None
        try:
            value = wait(measured, 5)
        except AssertionError as error:
            raise AssertionError(f"{surface} edge {last}, expected {expected}±{tolerance}") from error
        return value

    def route(surface):
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(3)
            peer.connect(str(out / "k230-shell-rust.sock"))
            peer.sendall((surface + "\n").encode())
            assert peer.recv(64) == b"OK\n"

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
        baseline = capture("deck.png")
        result = {}
        for surface, down, movement, reverse, moved_edge, reverse_edge, full_edge in (
            ("drawer", 1200, 1100, 1140, HEIGHT - 100, HEIGHT - 60, round(HEIGHT * 0.19)),
            ("shade", 10, 110, 70, 100, 60, round(HEIGHT * 0.65)),
        ):
            ident = 10 if surface == "drawer" else 20
            maps = log("rust").count("map-request")
            unmaps = log("rust").count("unmap")
            touch(f"down {ident} 284 {down}")
            wait(lambda: log("rust").count("map-request") > maps)
            touch(f"motion {ident} 284 {movement}")
            first = await_edge(f"{surface}-100.png", baseline, surface, moved_edge)
            touch(f"motion {ident} 384 {movement}")
            lateral = await_edge(f"{surface}-lateral.png", baseline, surface, moved_edge)
            touch(f"motion {ident} 284 {movement}")
            assert abs(lateral - first) <= 2, (surface, first, lateral)
            time.sleep(0.25)
            held = edge(capture(f"{surface}-held.png"), baseline, surface)
            assert held is not None and abs(held - first) <= 1, (surface, first, held)
            touch(f"motion {ident} 284 {reverse}")
            reversed_edge = await_edge(f"{surface}-reversed.png", baseline, surface, reverse_edge)
            assert abs(first - reversed_edge) in range(38, 43)
            touch(f"up {ident}")
            wait(lambda: log("rust").count("unmap") > unmaps)
            restored = capture(f"{surface}-cancelled.png")
            assert restored.getpixel((10, 100 if surface == "shade" else 1200)) == \
                baseline.getpixel((10, 100 if surface == "shade" else 1200))

            maps = log("rust").count("map-request")
            touch(f"down {ident + 1} 284 {down}")
            wait(lambda: log("rust").count("map-request") > maps)
            touch(f"motion {ident + 1} 284 {400 if surface == 'drawer' else 610}")
            touch(f"up {ident + 1}")
            settled = await_edge(f"{surface}-settled.png", baseline, surface, full_edge)
            route("hide")
            wait(lambda: log("rust").count("unmap") > unmaps + 1)
            result[surface] = {"after_100px": first, "lateral_at_same_y": lateral,
                               "held": held,
                               "after_reverse_40px": reversed_edge, "settled": settled}
        result.update({"result": "PASS", "class": "headless-qemu-native-touch",
                       "sway": args.sway, "rust": args.rust})
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

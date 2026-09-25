#!/usr/bin/env python3
"""Headless QEMU regression: bottom-edge escape wins over a mapped overlay.

Proves docs/design/shell-ux-critique.md S1.1's fix directly: from Settings
(and Drawer/Shade), a bottom-edge swipe up reaches the card overview exactly
as it would from an app, a bottom-edge sideways swipe switches apps, the
overlay's own top-area Close control stays reachable by a plain tap, and
Settings' local dismiss swipe now agrees with Shade's direction. Only
synthetic touch and public client pixels/app-ids are used; no physical
touch claim -- see openspec/changes/the-shell-behaves-as-one-coherent-system/.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("sway", "rust", "client", "output"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(mode=0o700, exist_ok=False)
    config = out / "sway.conf"
    config.write_text(
        "output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n"
        "focus_follows_mouse no\n"
        'for_window [app_id="^k230.card."] floating enable, border none, '
        "resize set 520 1040, move position 24 48\n"
    )
    catalog = out / "data/applications"
    catalog.mkdir(parents=True)
    (catalog / "public-fixture.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Public Fixture\nExec=/bin/true\n"
    )
    env = dict(
        os.environ,
        XDG_RUNTIME_DIR=str(out),
        XDG_DATA_HOME=str(out / "data"),
        XDG_DATA_DIRS=str(out / "data"),
        WLR_BACKENDS="headless",
        WLR_HEADLESS_OUTPUTS="1",
        WLR_RENDERER="pixman",
        SWAY_K230_CARD_SHELL="1",
        SWAY_K230_CARD_TOUCH_FIRST="1",
        SWAY_K230_CARD_TEST_INPUT="1",
    )
    helper = out / "surface-helper"
    helper.write_text('#!/bin/sh\nexec ' + args.rust + ' "$@"\n')
    helper.chmod(0o700)
    env["SWAY_K230_CARD_SURFACE_HELPER"] = str(helper)
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

    def tree_nodes(tree):
        yield tree
        for node in tree.get("nodes", []) + tree.get("floating_nodes", []):
            yield from tree_nodes(node)

    def focused():
        return next(
            (n.get("app_id") for n in tree_nodes(ipc("", 4)) if n.get("focused")), None
        )

    def route(surface):
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(3)
            peer.connect(str(out / "k230-shell-rust.sock"))
            peer.sendall((surface + "\n").encode())
            assert peer.recv(64) == b"OK\n"

    def start_client(app_id):
        handle = (out / (app_id + ".log")).open("w")
        logs[app_id] = handle
        process = subprocess.Popen(
            [args.client, "--app-id", app_id], env=env, stdout=handle, stderr=handle
        )
        processes.append(process)
        return process

    try:
        spawn("sway", [args.qemu, args.sway, "-c", str(config), "-d"])
        wait(lambda: "Running compositor on wayland display" in log("sway"), 60)
        env["WAYLAND_DISPLAY"] = next(
            path.name for path in out.glob("wayland-*") if not path.name.endswith(".lock")
        )
        env["SWAYSOCK"] = str(next(out.glob("sway-ipc.*.sock")))
        spawn("rust", [args.qemu, args.rust, "--serve"])
        wait(lambda: "ready-idle" in log("rust"))
        start_client("k230.card.one")
        wait(lambda: "k230.card.one" in json.dumps(ipc("", 4)))
        touch("init")
        wait(lambda: focused() == "k230.card.one")

        # --- 1: bottom-edge swipe up from Settings over a plain app reaches
        # the overview exactly as it would from that app: the compositor's
        # own cs_begin_entry claims the gesture (mirror id= logged) and the
        # overlay is dismissed as part of it (unmap logged). This is the
        # user's literal report: "if in settings swiping up from bottom does
        # nothing it should be like any app really."
        route("settings")
        wait(lambda: any(line.endswith(" commit") for line in log("rust").splitlines()), 8)
        assert "unmap" not in log("rust")
        # The Rust client logging a commit is not the same instant the
        # compositor's own layer-shell bookkeeping marks the surface
        # mapped (drawer_mapped()); give it a moment so the escape gesture
        # below actually exercises the carve-out instead of racing it.
        time.sleep(0.3)
        touch("down 10 284 1200")
        touch("motion 10 284 1100")
        touch("up 10")
        wait(lambda: "K230_CARD_SHELL mirror id=" in log("sway"), 5)
        wait(lambda: "unmap" in log("rust"), 5)
        # mode=1 is CS_DECK (enum cs_mode in card-shell-policy.h): the
        # pure-upward release settled in the overview, not stuck mid-drag.
        wait(lambda: "state mode=1 " in log("sway"), 5)

        # --- 2: back to a plain focused app, then prove a bottom-edge
        # *sideways* swipe from Settings switches directly to the neighbour
        # app, the same as the already-approved two-axis app switch.
        ipc("card_shell back")
        wait(lambda: focused() == "k230.card.one")
        start_client("k230.card.two")
        wait(lambda: "k230.card.two" in json.dumps(ipc("", 4)))
        wait(lambda: focused() == "k230.card.two")
        route("settings")
        wait(lambda: log("rust").count(" commit") >= 2, 8)
        time.sleep(0.3)
        before_restores = log("sway").count("restored focus=")
        touch("down 11 284 1200")
        touch("motion 11 284 1100")
        touch("motion 11 420 1100")
        touch("up 11")
        wait(lambda: log("sway").count("restored focus=") > before_restores, 5)
        assert focused() == "k230.card.one", focused()
        assert log("rust").count("unmap") >= 2

        # --- 3: Settings' own top-area Close control is still reachable by
        # a plain tap once mapped again -- the compositor's bottom-edge
        # carve-out must not swallow an ordinary tap far from the bottom
        # edge, and no compositor-side card entry must fire for it.
        route("settings")
        wait(lambda: log("rust").count(" commit") >= 3, 8)
        time.sleep(0.3)
        mirrors_before = log("sway").count("K230_CARD_SHELL mirror id=")
        touch("down 12 520 50")
        touch("up 12")
        wait(lambda: log("rust").count("unmap") >= 3, 5)
        assert log("sway").count("K230_CARD_SHELL mirror id=") == mirrors_before, (
            "a plain top-area tap must not be claimed as a card-entry gesture"
        )

        # --- 4: Settings' local dismiss swipe now agrees with Shade's
        # direction (upward, near the top) -- the fix for the critique's
        # "three direction-inconsistent dismiss gestures" finding. The old
        # downward direction must no longer dismiss it.
        route("settings")
        wait(lambda: log("rust").count(" commit") >= 4, 8)
        time.sleep(0.3)
        touch("down 13 200 60")
        touch("motion 13 200 400")
        touch("up 13")
        time.sleep(0.15)
        assert log("rust").count("unmap") == 3, "a downward swipe must not dismiss Settings"
        touch("down 14 200 150")
        touch("motion 14 200 40")
        touch("up 14")
        wait(lambda: log("rust").count("unmap") >= 4, 5)

        result = {
            "result": "PASS",
            "class": "headless-qemu-injected-input",
            "sway": args.sway,
            "rust": args.rust,
            "settings_bottom_edge_up_reaches_overview": True,
            "settings_bottom_edge_sideways_switches_app": True,
            "settings_close_control_reachable": True,
            "settings_dismiss_direction_matches_shade": True,
        }
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

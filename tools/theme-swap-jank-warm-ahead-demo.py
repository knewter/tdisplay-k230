#!/usr/bin/env python3
"""A/B tap-to-visible measurement: cold Apply vs. Apply after a browse-ahead
warm-up (tasks 3.1b/3.2), against the real Sway/Rust stack under headless
QEMU with a `cpulimit` throttle -- same harness shape as
`tests/test_theme_commit_under_occlusion_runtime.py`, but isolating just the
`activate` call's own wall time (the "tap to visible" window) in each case.

This is host + headless-QEMU-under-`qemu-riscv64-static`, never a board or
panel result -- see docs/evidence/omarchy-themes/instant-theme-swap/README.md
for the exact reproduction command and measured numbers this tool produced.
"""
import argparse
import json
import os
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("root", "sway", "rust", "client", "theme-bundle", "icons", "tools", "output"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--throttle", default="60")
    parser.add_argument("--theme-a", default="gruvbox", help="cold, never warmed")
    parser.add_argument("--theme-b", default="nord", help="warmed ahead, then activated")
    return parser.parse_args()


def main():
    args = arguments()
    root = Path(args.root)
    out = Path(args.output)
    out.mkdir(mode=0o700, exist_ok=False)
    state = out / "state"
    state.mkdir()
    bundle = Path(args.theme_bundle).resolve(strict=True)
    bundled = json.loads((root / "nix/handheld-theme-default/bundled-report.json").read_text())
    default = bundle / "generations" / bundled["generation"]

    config = out / "sway.conf"
    config.write_text(
        "output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n"
        "focus_follows_mouse no\nfloating_maximum_size -1 x -1\n"
        "default_floating_border none\n"
        'for_window [tiling app_id="^k230.card."] card_shell ordinary, '
        "floating enable, resize set 100 ppt 100 ppt, move position 0 0\n"
    )
    (out / "data/applications").mkdir(parents=True)
    env = dict(os.environ, XDG_RUNTIME_DIR=str(out), WLR_BACKENDS="headless",
               WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
               XDG_DATA_HOME=str(out / "data"),
               XDG_DATA_DIRS=str(Path(args.icons) / "share") + ":" + str(out / "data"),
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

    def log_text(name):
        return (out / (name + ".log")).read_text()

    def wait(predicate, seconds=30):
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
                    assert part
                    chunks.extend(part)
                return chunks
            header = read(14)
            length, _ = struct.unpack("=II", header[6:])
            reply = json.loads(read(length))
            if kind == 0:
                assert all(item["success"] for item in reply), (command, reply)
            return reply

    rust_endpoint = out / "k230-shell-rust-appearance.sock"
    card_endpoint = out / "card-appearance.sock"
    common = ["--tools", args.tools, "--builtins", str(bundle / "share/omarchy/themes"),
              "--state-root", str(state),
              "--rust-socket", str(rust_endpoint), "--deck-socket", str(card_endpoint),
              "--keyboard-runtime-dir", str(out), "--pkill", "/usr/bin/pkill"]

    def theme_cli(*cli_args):
        started = time.monotonic()
        result = subprocess.run(
            [sys.executable, str(root / "tools/theme_catalog.py")] + common + list(cli_args),
            capture_output=True, text=True, timeout=60)
        elapsed_ms = (time.monotonic() - started) * 1000
        return result, elapsed_ms

    results = {}
    try:
        spawn("sway", [args.qemu, args.sway, "-c", str(config), "-d"])
        wait(lambda: "Running compositor on wayland display" in log_text("sway"), 60)
        env["WAYLAND_DISPLAY"] = next(path.name for path in out.glob("wayland-*")
                                       if not path.name.endswith(".lock"))
        env["SWAYSOCK"] = str(next(out.glob("sway-ipc.*.sock")))
        wait(card_endpoint.exists)

        rust_argv = [args.qemu, args.rust, "--serve"]
        if args.throttle:
            rust_argv = ["/nix/store/n6g5nn5c2cjz02cc0j2mkgad736y43s0-cpulimit-0.2/bin/cpulimit",
                         "-l", args.throttle, "-i", "-z", "--"] + rust_argv
        spawn("rust", rust_argv)
        wait(lambda: "wallpaper-commit" in log_text("rust") and rust_endpoint.exists(), 30)

        spawn("client", [args.client, "--app-id", "k230.card.one"])
        wait(lambda: "k230.card.one" in json.dumps(ipc("", 4)))
        wait(lambda: "map-request" in log_text("rust"), 10)

        def listing():
            call, _ = theme_cli("list", "--json")
            assert call.returncode == 0, call.stderr
            return json.loads(call.stdout)["themes"]

        themes = {row["name"]: row for row in listing()}

        # --- Scenario A: cold Apply, no browse-ahead (today's baseline for
        # any theme the person taps without first dwelling on it, still true
        # even after 3.1a/3.1b/3.2 land, since nothing warmed it). ---
        entry_a = themes[args.theme_a]
        preview_call, _ = theme_cli("preview", entry_a["id"], "--json")
        assert preview_call.returncode == 0, preview_call.stderr
        generation_a = json.loads(preview_call.stdout)["generation"]
        rust_before = len(log_text("rust").splitlines())
        activate_a, cold_ms = theme_cli(
            "activate", entry_a["id"], "--expected-generation", generation_a, "--json")
        assert activate_a.returncode == 0, activate_a.stderr
        assert json.loads(activate_a.stdout)["activated"] is True
        wait(lambda: log_text("rust").count("appearance-commit-accepted") >= 1)
        rust_lines_a = log_text("rust").splitlines()[rust_before:]
        results["cold_apply_ms"] = cold_ms
        results["cold_apply_rust_events"] = rust_lines_a

        # --- Scenario B: browse-ahead warm-up (task 3.2's own call shape),
        # a dwell, THEN Apply -- only the Apply call's own wall time counts
        # as "tap to visible", since the warm-up itself ran during idle
        # browsing time before the tap. ---
        entry_b = themes[args.theme_b]
        warm_call, warm_ms = theme_cli("preview", entry_b["id"], "--json")
        assert warm_call.returncode == 0, warm_call.stderr
        generation_b = json.loads(warm_call.stdout)["generation"]
        time.sleep(0.4)  # simulated dwell, comfortably past the 220ms debounce
        rust_before = len(log_text("rust").splitlines())
        activate_b, warm_apply_ms = theme_cli(
            "activate", entry_b["id"], "--expected-generation", generation_b, "--json")
        assert activate_b.returncode == 0, activate_b.stderr
        assert json.loads(activate_b.stdout)["activated"] is True
        wait(lambda: log_text("rust").count("appearance-commit-accepted") >= 2)
        rust_lines_b = log_text("rust").splitlines()[rust_before:]
        results["warm_up_preview_ms"] = warm_ms
        results["warm_apply_ms"] = warm_apply_ms
        results["warm_apply_rust_events"] = rust_lines_b

        results["sway_gradient_events"] = [
            line for line in log_text("sway").splitlines() if "appearance-canvas-gradient" in line]
        print(json.dumps(results, indent=2))
        (out / "result.json").write_text(json.dumps(results, indent=2) + "\n")
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

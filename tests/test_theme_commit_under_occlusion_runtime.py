#!/usr/bin/env python3
"""Real paired Sway/Rust regression for a board activation failure.

`k230-theme activate` on the board returned {"error": "commit failed and
fanout rollback was not acknowledged"} on the very first activation (no
active theme pointer yet, so a rollback resolves to the packaged default),
with an ordinary maximized opaque app already mapped -- fully occluding the
Rust shell's background-layer wallpaper surface. The Rust journal showed no
appearance-commit-rejected line, so main.rs's deferred `pending_appearance`
completion was silently timing out: `draw_wallpaper()` refused to draw at all
while `wallpaper.frame_pending` was still true, and a compositor is not
obligated to keep sending frame-done callbacks for a surface nothing is
compositing, so that flag could stay stuck indefinitely with no client-visible
damage. This starved the transaction of the free double-buffer slot the pool
already tracks independently, so the deferred commit/rollback ack always
timed out.

This is synthetic input and compositor output, never a panel or finger test.
It uses a CPU throttle (cpulimit) on the Rust shell process, which is what
made the stuck-callback window wide enough to matter under headless QEMU;
without it, the failure is timing-dependent and may not reproduce.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from theme_transaction import TransactionError, activate_generation, exchange  # noqa: E402


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("sway", "rust", "client", "output", "theme-bundle", "icons", "tools"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--throttle", default="20",
                        help="cpulimit percent for the rust process (default reproduces the bug)")
    parser.add_argument("--theme", default="catppuccin")
    return parser.parse_args()


def main():
    args = arguments()
    out = Path(args.output)
    out.mkdir(mode=0o700, exist_ok=False)
    state = out / "state"
    state.mkdir()
    bundle = Path(args.theme_bundle).resolve(strict=True)
    bundled = json.loads((ROOT / "nix/handheld-theme-default/bundled-report.json").read_text())
    default = bundle / "generations" / bundled["generation"]
    assert default.is_dir()

    config = out / "sway.conf"
    config.write_text(
        "output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n"
        "focus_follows_mouse no\nfloating_maximum_size -1 x -1\n"
        "default_floating_border none\n"
        # "ordinary" maximizes the app opaque and full-screen, fully
        # occluding the shell's own background-layer wallpaper surface --
        # the exact condition the board hit.
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

    def log(name):
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
                    assert part, "IPC closed"
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
    try:
        spawn("sway", [args.qemu, args.sway, "-c", str(config), "-d"])
        wait(lambda: "Running compositor on wayland display" in log("sway"), 60)
        env["WAYLAND_DISPLAY"] = next(path.name for path in out.glob("wayland-*")
                                       if not path.name.endswith(".lock"))
        env["SWAYSOCK"] = str(next(out.glob("sway-ipc.*.sock")))
        wait(card_endpoint.exists)

        rust_argv = [args.qemu, args.rust, "--serve"]
        if args.throttle:
            rust_argv = ["/nix/store/n6g5nn5c2cjz02cc0j2mkgad736y43s0-cpulimit-0.2/bin/cpulimit",
                         "-l", args.throttle, "-i", "-z", "--"] + rust_argv
        spawn("rust", rust_argv)
        wait(lambda: "wallpaper-commit" in log("rust") and rust_endpoint.exists(), 30)

        # An ordinary, maximized, opaque app -- fully occluding the shell's
        # wallpaper -- is already mapped *before* the very first activation,
        # exactly like the board's failing sequence.
        spawn("client", [args.client, "--app-id", "k230.card.one"])
        wait(lambda: "k230.card.one" in json.dumps(ipc("", 4)))
        wait(lambda: "map-request" in log("rust"), 10)

        # Both scenarios below must run against the *same* `state` root the
        # running rust/card-shell processes were started with
        # (K230_THEME_STATE_ROOT=state / SWAY_K230_CARD_THEME_STATE_ROOT=
        # state): the receiver validates every generation path against the
        # bound it was given at startup, so a mismatched root fails prepare
        # outright rather than exercising the commit/rollback path this test
        # targets.

        # Scenario B runs first, while `state` still has no active pointer:
        # force a commit failure on this very first activation and confirm
        # the fanout rollback to the packaged default (previous=None) is
        # acknowledged rather than rejected the same way the real commit was.
        assert (state / "active").exists() is False
        from theme_activate import prepare as prepare_theme
        generation_b, _ = prepare_theme(
            args.theme, source=bundle / "share/omarchy/themes" / args.theme,
            state_root=state, user_themes=out / "empty-user-themes", builtins=None,
            tools=Path(args.tools))

        def fail_rust_commit(endpoint, phase, generation):
            if endpoint == rust_endpoint and phase == "commit":
                raise TransactionError("injected Rust commit failure")
            exchange(endpoint, phase, generation)

        try:
            activate_generation(generation_b, state_root=state, endpoint=card_endpoint,
                                endpoints=(rust_endpoint, card_endpoint),
                                transport=fail_rust_commit, app_sync=lambda *a, **k: None)
            raise AssertionError("injected commit failure did not abort activation")
        except TransactionError as error:
            assert "previous generation restored" in str(error), (
                "rollback to the packaged default (previous=None) was rejected: " + str(error))
        assert (state / "active").exists() is False, "no pointer should exist after rollback to None"
        print("Scenario B (rollback to packaged default with previous=None) PASS", file=sys.stderr)

        # Scenario A: the real `k230-theme` CLI flow (preview, then activate
        # with the previewed generation) must succeed on this, the still
        # first real activation (Scenario B's injected failure left no
        # active pointer), with the same occluding app still mapped.
        common = ["--tools", args.tools, "--builtins", str(bundle / "share/omarchy/themes"),
                  "--state-root", str(state),
                  "--rust-socket", str(rust_endpoint), "--deck-socket", str(card_endpoint),
                  "--keyboard-runtime-dir", str(out), "--pkill", "/usr/bin/pkill"]

        def theme_cli(*cli_args):
            return subprocess.run(
                [sys.executable, str(ROOT / "tools/theme_catalog.py")] + common + list(cli_args),
                capture_output=True, text=True, timeout=60)

        listing = theme_cli("list", "--json")
        assert listing.returncode == 0, listing.stderr
        entry = next(item for item in json.loads(listing.stdout)["themes"]
                     if item["name"] == args.theme)

        preview = theme_cli("preview", entry["id"], "--json")
        assert preview.returncode == 0, preview.stderr
        generation = json.loads(preview.stdout)["generation"]

        activate = theme_cli("activate", entry["id"], "--expected-generation", generation, "--json")
        assert activate.returncode == 0, (
            "activation under occlusion+throttle was rejected: " + activate.stderr
            + "\nrust.log tail:\n" + "\n".join(log("rust").splitlines()[-20:]))
        assert json.loads(activate.stdout)["activated"] is True
        assert (state / "active").resolve().name == generation
        print("Scenario A (commit under occlusion) PASS", file=sys.stderr)
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

#!/usr/bin/env python3
"""Exercise pinned Catppuccin/Latte Sway-Rust appearance under headless QEMU.

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

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from theme_transaction import TransactionError, activate_generation, exchange
from theme_activate import prepare


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("sway", "rust", "client", "output", "theme-bundle", "icons"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--check-restart", action="store_true")
    parser.add_argument("--deck-visual-states", action="store_true",
                        help="capture private and empty deck states after the paired transaction")
    parser.add_argument("--wallpaper-cache-tool", type=Path,
                        help="k230-shell-rust binary (any arch: this only runs host-side) to "
                             "precompute background.cache for the prepared generations, so this "
                             "run exercises BackgroundCache's cache-hit path (background_decode.rs) "
                             "instead of only the full-decode path a bare `prepare()` takes")
    return parser.parse_args()


def main():
    args = arguments()
    out = Path(args.output)
    out.mkdir(mode=0o700, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    state = out / "state"
    state.mkdir()
    bundle = Path(args.theme_bundle).resolve(strict=True)
    bundled = json.loads((root / "nix/handheld-theme-default/bundled-report.json").read_text())
    default = bundle / "generations" / bundled["generation"]
    assert default.is_dir() and json.loads((default / "report.json").read_text()) == bundled
    source_root = bundle / "share/omarchy/themes"
    latte, latte_report = prepare(
        "catppuccin-latte", source=source_root / "catppuccin-latte",
        state_root=state, user_themes=out / "empty-user-themes", builtins=None,
        tools=root / "nix/omarchy-theme-tools/upstream",
        wallpaper_cache_tool=args.wallpaper_cache_tool)
    dark, dark_report = prepare(
        "catppuccin", source=source_root / "catppuccin",
        state_root=state, user_themes=out / "empty-user-themes", builtins=None,
        tools=root / "nix/omarchy-theme-tools/upstream",
        wallpaper_cache_tool=args.wallpaper_cache_tool)
    if args.wallpaper_cache_tool is not None:
        # Prove this run actually exercises BackgroundCache's cache-hit path
        # (background_decode.rs's load_cached), not only the full-decode
        # fallback every other invocation of this test takes: a bare
        # `prepare()` call above already ran `--write-wallpaper-cache` for
        # each generation whose background is a still image, exactly as
        # `handheld-theme-command.nix` does on the real board (see
        # `tools/theme_activate.py`'s `build_wallpaper_cache`).
        for generation, report in ((latte, latte_report), (dark, dark_report)):
            selected = report["selected_background"]
            if selected and Path(selected).suffix.lower() != ".mp4":
                cache_file = generation / "background.cache"
                assert cache_file.is_file() and cache_file.stat().st_size > 0, \
                    f"{generation.name}: --wallpaper-cache-tool did not produce background.cache"
    assert latte_report["icon_theme"] == "Yaru-blue"
    assert dark_report["icon_theme"] == "Yaru-purple"

    def selected_image(generation):
        report = json.loads((generation / "report.json").read_text())
        selected = report["selected_background"]
        assert selected and selected in report["backgrounds"]
        return generation / "theme" / selected

    def expected_wallpaper(generation, point):
        image = Image.open(selected_image(generation)).convert("RGB")
        source_width, source_height = image.size
        width, height = 568, 1232
        if source_width * height > source_height * width:
            crop_width, crop_height = source_height * width // height, source_height
        else:
            crop_width, crop_height = source_width, source_width * height // width
        left, top = (source_width - crop_width) // 2, (source_height - crop_height) // 2
        image = image.crop((left, top, left + crop_width, top + crop_height))
        return image.resize((width, height), Image.Resampling.BILINEAR).getpixel(point)

    def close(actual, expected, tolerance=12):
        return max(abs(a - b) for a, b in zip(actual, expected)) <= tolerance
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
               XDG_DATA_HOME=str(out / "data"), XDG_DATA_DIRS=str(Path(args.icons) / "share") + ":" + str(out / "data"),
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
        client_process = spawn("client", [args.client, "--app-id", "k230.card.one"])
        wait(lambda: "k230.card.one" in json.dumps(ipc("", 4)))
        app_before = capture("app-before.png")
        ipc("card_shell enter")
        wait(lambda: "K230_CARD_SHELL mirror id=" in log("sway"))
        baseline_point = (10, 700)
        baseline_expected = expected_wallpaper(default, baseline_point)
        wait(lambda: close(capture("default-deck.png").getpixel(baseline_point),
                           baseline_expected), 8)
        baseline = capture("default-deck.png")
        assert close(baseline.getpixel(baseline_point), baseline_expected), \
            (baseline.getpixel(baseline_point), baseline_expected)

        endpoints = (card_endpoint, rust_endpoint)
        result = activate_generation(latte, state_root=state, endpoint=card_endpoint,
                                     endpoints=endpoints, app_sync=lambda *a, **k: None)
        assert result["state"] == "applied", result
        wait(lambda: "wallpaper-commit" in log("rust") and log("rust").count("wallpaper-commit") >= 2)
        upper_point, lower_point = (10, 300), (10, 700)
        upper_expected = expected_wallpaper(latte, upper_point)
        lower_expected = expected_wallpaper(latte, lower_point)
        wait(lambda: close(capture("latte-deck.png").getpixel(lower_point), lower_expected), 8)
        themed_deck = capture("latte-deck.png")
        upper = themed_deck.getpixel(upper_point)
        lower = themed_deck.getpixel(lower_point)
        assert close(upper, upper_expected), (upper, upper_expected)
        assert close(lower, lower_expected), (lower, lower_expected)
        assert lower != baseline.getpixel(lower_point)

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
        drawer = capture("latte-drawer.png")
        # Drawer interior uses the real authored Latte launcher brush.
        drawer_pixel = drawer.getpixel((10, 500))
        appearance = json.loads((latte / "appearance.json").read_text())
        brush = appearance["sections"]["launcher"]["background"]["stops"][0]["argb"]
        expected_panel = tuple(bytes.fromhex(brush[3:]))
        assert close(drawer_pixel, expected_panel, 20), (drawer_pixel, expected_panel)

        def fail_second_commit(endpoint, phase, generation):
            if endpoint == rust_endpoint and phase == "commit":
                raise TransactionError("injected Rust commit failure")
            exchange(endpoint, phase, generation)

        try:
            activate_generation(dark, state_root=state, endpoint=card_endpoint,
                                endpoints=endpoints, transport=fail_second_commit,
                                app_sync=lambda *a, **k: None)
            raise AssertionError("injected failure did not abort")
        except TransactionError as error:
            assert "previous generation restored" in str(error), str(error)
        assert (state / "active").resolve() == latte
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
            with socket.socket(socket.AF_UNIX) as peer:
                peer.settimeout(3)
                peer.connect(str(out / "k230-shell-rust.sock"))
                peer.sendall(b"hide\n")
                assert peer.recv(64) == b"OK\n"
            wait(lambda: "unmap" in log("rust-restarted"))
        if args.deck_visual_states:
            ipc('[app_id="k230.card.one"] mark --add k230_card_private')
            time.sleep(0.25)
            private = capture("private-deck.png")
            # The recognizable blue live probe is forbidden inside a private
            # card; only its neutral placeholder and short state copy remain.
            assert not any(r < 55 and 70 < b < 180 and b > g * 1.3
                           for r, g, b in private.crop((120, 220, 450, 800)).getdata())
            client_process.terminate()
            client_process.wait(timeout=5)
            wait(lambda: "k230.card.one" not in json.dumps(ipc("", 4)))
            time.sleep(0.25)
            empty = capture("empty-deck.png")
            assert private.size == empty.size == (568, 1232)
        summary = {"result": "PASS", "class": "headless-qemu-paired-appearance",
                   "sway": args.sway, "rust": args.rust,
                   "wallpaper_cache_exercised": args.wallpaper_cache_tool is not None,
                   "default_generation": default.name,
                   "default_background": bundled["selected_background"],
                   "default_wallpaper_sample": baseline.getpixel(baseline_point),
                   "default_wallpaper_expected": baseline_expected,
                   "latte_generation": latte.name,
                   "latte_background": latte_report["selected_background"],
                   "latte_wallpaper_upper": upper, "latte_wallpaper_lower": lower,
                   "latte_wallpaper_expected_upper": upper_expected,
                   "latte_wallpaper_expected_lower": lower_expected,
                   "latte_drawer": drawer_pixel, "rollback_pointer": latte.name,
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

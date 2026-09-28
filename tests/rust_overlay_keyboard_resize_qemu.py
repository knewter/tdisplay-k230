#!/usr/bin/env python3
"""Paired Sway/Rust proof that the overlay surface never resizes -- and so
never non-uniformly stretches its content -- when the real `wvkbd` shows.

Board regression (2026-09-28, /tmp/coherent-settings.png): the Wi-Fi
Settings page squashed to about 0.66x height the instant wvkbd appeared,
because the overlay's `Layer::Overlay` surface requested `exclusive_zone(0)`
(anchored to all four edges), which wlr-layer-shell's own `arrange_layers`
treats as "may be resized to avoid occluding a positive exclusive zone" --
exactly what wvkbd's own real, positive exclusive zone triggered. The fix
(`ensure_layer`/`ensure_home`/`ensure_wallpaper` requesting
`exclusive_zone(-1)`, plus `configure_preserves_aspect` in `src/lib.rs` as a
second, independent guard) is proven here by:

- launching the real, production `wvkbd-mobintl` (cross-built for riscv64,
  run under `qemu-riscv64-static`, not a synthetic stand-in) and showing it
  through the exact production signal path (a copy of
  `nix/shell.nix`'s `k230-keyboard-gesture-signal`: `pkill -USR2 -u "$(id
  -u)" -x wvkbd-mobintl`), the same helper `ShellClient::sync_wifi_keyboard`
  invokes for `K230_KEYBOARD_SIGNAL`;
- asserting every `configure <W>x<H>` line the Rust log ever records for
  this surface says exactly `568x1232` -- the compositor never proposed a
  smaller size, not merely that a smaller one would have been handled
  correctly;
- asserting the header/password-field region (which the Wi-Fi page's own
  keyboard-aware reflow never touches -- only Cancel/Connect move,
  `wifi_ui::entry_buttons_rect`) is pixel-identical before wvkbd shows and
  after, which a non-uniform vertical squash could not produce.

Run under `unshare -Ur` so the fake Wi-Fi broker socket is uid 0 inside the
user namespace, matching `tests/rust_wifi_settings_qemu.py` (whose Broker/
theme/SETTINGS fixtures this file reuses verbatim to reach the WPA2 password
Entry page -- the reported page -- rather than duplicating them).
"""

import argparse
from contextlib import closing, nullcontext
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

sys.path.insert(0, os.path.dirname(__file__))
import rust_wifi_settings_qemu as wifi_qemu

# Matches `nix/shell.nix`'s real `k230-keyboard-gesture-signal` with one
# deliberate difference: `-f` (full command line), not `-x` (exact `comm`).
# On the board wvkbd runs natively, so its `comm` really is `wvkbd-mobintl`
# and `-x` is correct and exact. Under `qemu-riscv64-static` here, the
# process the kernel sees is the *emulator*  --  `comm` is `qemu-riscv64-st`
# (confirmed with `/proc/<pid>/comm`), only its argv still names the guest
# binary  --  so `-x wvkbd-mobintl` matches nothing and silently never
# signals it. This is a test-harness-only concession to running wvkbd under
# emulation at all; it is not a change this fix makes to the production
# script.
KEYBOARD_SIGNAL = """#!/bin/sh
set -eu
case "${1:-}" in
  show) signal=USR2 ;;
  hide) signal=USR1 ;;
  *) exit 2 ;;
esac
exec pkill -"$signal" -u "$(id -u)" -f wvkbd-mobintl
"""


def wait_for(predicate, seconds=20):
    return wifi_qemu.wait_for(predicate, seconds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sway", type=Path, required=True)
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--wvkbd", type=Path, required=True)
    parser.add_argument("--theme-source", type=Path, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("run inside `unshare -Ur` for a synthetic uid-0 broker")
    for path in (args.sway, args.rust, args.wvkbd):
        if not path.is_file():
            parser.error(f"exact cross-built executable must exist: {path}")
    context = nullcontext(args.output) if args.output else tempfile.TemporaryDirectory(
        prefix="k230-overlay-resize-qemu-")
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
    with context as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        (root / "sway.conf").write_text("output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n")
        command = root / "fake-settings"
        command.write_text(wifi_qemu.SETTINGS)
        command.chmod(0o700)
        settings_log = root / "settings.log"
        settings_log.touch()
        broker = wifi_qemu.Broker(root / "wifi.sock")
        dark = wifi_qemu.theme(root, args.theme_source, "dark")
        signal_script = root / "keyboard-signal"
        signal_script.write_text(KEYBOARD_SIGNAL)
        signal_script.chmod(0o700)
        env = dict(os.environ, XDG_RUNTIME_DIR=str(root), WLR_BACKENDS="headless",
                   WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
                   SWAY_K230_CARD_SHELL="1", SWAY_K230_CARD_TEST_INPUT="1",
                   K230_SETTINGS=str(command), K230_WIFI_SOCKET=str(broker.path),
                   K230_TEST_SETTINGS_LOG=str(settings_log),
                   K230_KEYBOARD_TOUCH_GESTURES="1",
                   K230_KEYBOARD_SIGNAL=str(signal_script),
                   K230_KEYBOARD_HEIGHT="400",
                   K230_THEME_STATE_ROOT=str(root / "theme-state"))
        sway_log = (root / "sway.log").open("w")
        sway = subprocess.Popen([args.qemu, str(args.sway), "-c", str(root / "sway.conf"), "-d"],
                                env=env, stdout=sway_log, stderr=sway_log)
        rust = None
        rust_log = None
        wvkbd = None
        wvkbd_log = None
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
                            chunk = stream.recv(count - len(data))
                            assert chunk
                            data += chunk
                        return data
                    length, _ = struct.unpack("=II", read(14)[6:])
                    assert all(item["success"] for item in json.loads(read(length)))

            contact = 1

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

            def identical(first, second, box):
                return ImageChops.difference(first.crop(box), second.crop(box)).getbbox() is None

            def changed(first, second, box):
                return not identical(first, second, box)

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

            ipc("card_shell test-touch init")
            env["K230_THEME_DEFAULT_GENERATION"] = str(dark)
            rust_log = (root / "rust.log").open("a")
            rust = subprocess.Popen([args.qemu, str(args.rust), "--serve"], env=env,
                                    stdout=rust_log, stderr=rust_log)
            wait_for(lambda: "ready-idle" in (root / "rust.log").read_text() and rust.poll() is None, 30)

            # wvkbd starts hidden, exactly like the production
            # `k230-supervised-keyboard` service -- it must already be a
            # running process for the signal script (`pkill -x
            # wvkbd-mobintl`) to find, matching how the board actually
            # works (a signal toggles an always-running process, it does
            # not start/stop one per show/hide).
            wvkbd_log = (root / "wvkbd.log").open("w")
            wvkbd = subprocess.Popen(
                [args.qemu, str(args.wvkbd), "-H", "400", "--hidden"],
                env=env, stdout=wvkbd_log, stderr=wvkbd_log)

            wallpaper = capture("resize-wallpaper.png")
            route("settings")
            wait_for(lambda: "status" in settings_log.read_text())
            settings = capture_until("resize-settings-dark.png", lambda frame:
                                     changed(wallpaper, frame, (24, 30, 280, 100))
                                     and frame.getpixel((45, 500)) != frame.getpixel((20, 500)))
            tap(284, 210)  # Wi-Fi row: opens the Network list.
            if not broker.count("scan"):
                time.sleep(0.35)
                if not broker.count("scan"):
                    tap(284, 210)
            wait_for(lambda: broker.count("scan") >= 1)
            capture_words("resize-list-dark.png", "Saved and nearby", "Example Saved", "Example New")
            tap(284, 464)  # New WPA2 row (an unsaved WPA2-Personal network).
            before = capture_words("resize-entry-before-keyboard.png", "Example New", "Type the password")

            configures_before = (root / "rust.log").read_text().count("configure ")
            wait_for(lambda: (root / "rust.log").read_text().count(
                "wifi-keyboard-focus-granted") >= 1)
            # Give wlroots' own arrange_layers a moment to react to wvkbd's
            # now-real exclusive zone and, pre-fix, propose a smaller
            # configure -- a plain sleep here (not a `wait_for` on a specific
            # log line) is deliberate: the buggy behaviour this proves the
            # absence of is exactly an *unwanted* configure event, which has
            # no positive signal to wait for.
            time.sleep(1.0)
            after = capture_words("resize-entry-after-keyboard.png", "Example New", "Type the password")

            log_text = (root / "rust.log").read_text()
            new_configures = log_text.count("configure ") - configures_before
            # The real assertion: every `configure <W>x<H>` line for the
            # overlay (the third, un-prefixed branch of
            # `LayerShellHandler::configure` -- the only one this test's
            # page ever reaches) says exactly 568x1232, whether or not a
            # fresh one was even sent.
            overlay_configures = [
                line for line in log_text.splitlines()
                if " configure " in line and "wallpaper-configure" not in line
                and "home-configure" not in line
            ]
            assert overlay_configures, "no overlay configure was ever logged to check"
            for line in overlay_configures:
                assert line.rstrip().endswith("configure 568x1232"), (
                    f"overlay was reconfigured away from the full panel size: {line!r}")

            # The header/password-field region never participates in the
            # Wi-Fi page's own keyboard-aware reflow (only Cancel/Connect
            # move); if the whole surface had been squashed instead, this
            # region could not be pixel-identical.
            assert identical(before, after, (0, 0, 568, 410)), (
                "header/password-field region moved or resized when the "
                "keyboard appeared -- the overlay surface was resized "
                "(the reported real-glass squash bug)")

            assert wvkbd.poll() is None and rust.poll() is None and sway.poll() is None
            print(json.dumps({
                "evidence_class": "headless-qemu-real-wvkbd-overlay-resize",
                "passed": ["overlay-configure-stays-568x1232", "header-pixel-identical-with-keyboard-shown"],
                "new_configures_after_keyboard_shown": new_configures,
                "limits": ["invented Wi-Fi broker and settings", "no physical radio/panel",
                           "headless output, not the real panel"],
            }), flush=True)
        finally:
            for proc, log in ((rust, rust_log), (wvkbd, wvkbd_log)):
                if proc:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                if log:
                    log.close()
            sway.terminate()
            try:
                sway.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sway.kill()
                sway.wait()
            sway_log.close()
            broker.close()


if __name__ == "__main__":
    main()

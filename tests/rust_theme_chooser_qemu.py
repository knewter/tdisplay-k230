#!/usr/bin/env python3
"""Paired Sway/Rust theme carousel touch proof with a synthetic theme command.

The fixture never calls the real theme transaction or modifies user themes.
Synthetic Wayland touch and headless screenshots are not physical panel proof.
"""

import argparse
from contextlib import closing, nullcontext
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time

from PIL import Image, ImageChops


THEME_COMMAND = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["K230_TEST_THEME_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
generation = "b" * 24
# Every row points at the same real fixture PNG (K230_TEST_THEME_PREVIEW),
# matching Omarchy's per-theme preview.png convention closely enough to
# prove the carousel's own slice imagery actually decodes and paints real
# pixels, not just that the field round-trips.
preview_path = os.environ["K230_TEST_THEME_PREVIEW"]
themes = [{"id": f"{i:024x}", "name": f"Fixture {i:02d}",
           "label": f"Fixture {i:02d}", "origin": "builtin",
           "preview_path": preview_path}
          for i in range(18)]
if args == ["list"]:
    answer = {"schema": 1, "themes": themes,
              "active": {"id": themes[0]["id"], "generation": generation}}
else:
    assert args[0] in ("preview", "activate") and args[1] in {row["id"] for row in themes}
    if args[0] == "activate":
        assert args[args.index("--expected-generation") + 1] == generation
    selected = args[args.index("--background") + 1] if "--background" in args else "c" * 24
    assert selected in ("c" * 24, "d" * 24)
    directory = Path(os.environ["K230_TEST_THEME_GENERATION"]) / generation
    answer = {"schema": 1, "theme": next(row for row in themes if row["id"] == args[1]),
              "generation": generation, "appearance_path": str(directory / "appearance.json"),
              "palette": {"background": "#101820", "foreground": "#f1f4f5",
                          "accent": "#69ccbc"}, "icon_theme": "hicolor",
              "backgrounds": [
                  {"id": "c" * 24, "label": "Fixture still one", "kind": "image",
                   "path": str(directory / "theme/backgrounds/one.png"),
                   "selected": selected == "c" * 24, "decode_status": "unverified"},
                  {"id": "d" * 24, "label": "Fixture still two", "kind": "image",
                   "path": str(directory / "theme/backgrounds/two.png"),
                   "selected": selected == "d" * 24, "decode_status": "unverified"},
              ],
              "compatibility": {"applied": ["launcher"], "unavailable": [], "unknown": []},
              "activated": args[0] == "activate"}
    if args[0] == "activate":
        answer["app_appearance"] = {"state": "applied", "generation": generation,
                                    "error": None, "kind": None}
print(json.dumps(answer))
'''


# Mirrors nix/rust-shell-client/src/theme_carousel.rs's geometry constants
# exactly, so this black-box test can derive exact tap points (always well
# inside a slice's skewed shape) instead of guessing coordinates. The
# skewed-hit-test edge cases themselves are covered by that module's own
# unit tests; this only needs "some point solidly inside slice N".
EXPANDED_W, EXPANDED_H = 300.0, 186.0
SLICE_W, SLICE_H = 42.0, 169.0
SPACING = -12.0
ITEM_STEP = SLICE_W + SPACING
THEME_TOP = 204.0
BACKGROUND_TOP = 662.0
PREVIEW_FOOTER_Y = BACKGROUND_TOP + EXPANDED_H + 104.0


def slice_center(selected, index, center_x, top_y):
    """The exact center of carousel slice `index`'s rect when `selected` is
    centered -- theme_carousel::exact_layout, transcribed for the test."""
    relative = index - selected
    preview_x = center_x - EXPANDED_W / 2.0
    if relative == 0:
        return center_x, top_y + EXPANDED_H / 2.0
    x = (preview_x + relative * ITEM_STEP if relative < 0
         else preview_x + EXPANDED_W + SPACING + (relative - 1) * ITEM_STEP)
    y = top_y + (EXPANDED_H - SLICE_H) / 2.0
    return x + SLICE_W / 2.0, y + SLICE_H / 2.0


def wait_for(predicate, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.05)
    raise AssertionError("timed out waiting for theme chooser state")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sway", type=Path, required=True)
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--output", type=Path, help="keep synthetic images and logs")
    args = parser.parse_args()
    if not args.sway.is_file() or not args.rust.is_file():
        parser.error("exact cross-built Sway and Rust executables must exist")
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
    context = nullcontext(args.output) if args.output else tempfile.TemporaryDirectory(prefix="k230-theme-ui-qemu-")
    with context as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        config = root / "sway.conf"
        config.write_text("output HEADLESS-1 mode 568x1232\nseat seat0 fallback true\n")
        command = root / "synthetic-k230-theme"
        command.write_text(THEME_COMMAND)
        command.chmod(0o700)
        log = root / "theme-commands.jsonl"
        log.touch()
        # Real, decodable fixture art: a shared per-theme preview thumbnail,
        # and two distinguishable backgrounds staged at the exact generation
        # path the synthetic command reports. Nothing here is upstream art;
        # it exists only to prove the chooser's own decode/paint path.
        preview = root / "fixture-preview.png"
        Image.new("RGB", (48, 48), (214, 64, 24)).save(preview)
        generation_dir = root / "generations" / ("b" * 24) / "theme" / "backgrounds"
        generation_dir.mkdir(parents=True)
        Image.new("RGB", (64, 128), (32, 96, 214)).save(generation_dir / "one.png")
        Image.new("RGB", (64, 128), (214, 176, 32)).save(generation_dir / "two.png")
        env = dict(os.environ, XDG_RUNTIME_DIR=str(root), WLR_BACKENDS="headless",
                   WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
                   SWAY_K230_CARD_SHELL="1", SWAY_K230_CARD_TEST_INPUT="1",
                   K230_THEME_COMMAND=str(command), K230_TEST_THEME_LOG=str(log),
                   K230_TEST_THEME_GENERATION=str(root / "generations"),
                   K230_TEST_THEME_PREVIEW=str(preview))
        sway_log = (root / "sway.log").open("w")
        rust_log = (root / "rust.log").open("w")
        sway = subprocess.Popen([args.qemu, str(args.sway), "-c", str(config), "-d"],
                                env=env, stdout=sway_log, stderr=sway_log)
        rust = None
        try:
            wait_for(lambda: "Running compositor on wayland display" in (root / "sway.log").read_text(), 60)
            env["WAYLAND_DISPLAY"] = wait_for(lambda: next(
                (path.name for path in root.glob("wayland-*") if not path.name.endswith(".lock")), None))
            rust = subprocess.Popen([args.qemu, str(args.rust), "--serve"],
                                    env=env, stdout=rust_log, stderr=rust_log)
            wait_for(lambda: "ready-idle" in (root / "rust.log").read_text(), 30)

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
                            assert chunk, "Sway IPC closed"
                            data += chunk
                        return data
                    length, _ = struct.unpack("=II", read(14)[6:])
                    answer = json.loads(read(length))
                    assert all(row["success"] for row in answer), (command_text, answer)

            def calls():
                return [json.loads(line) for line in log.read_text().splitlines()]

            def commits():
                return sum(line.endswith(" commit") for line in (root / "rust.log").read_text().splitlines())

            def capture(name, timeout=8.0, stable_frames=3, interval=0.1):
                """Grabs the settled frame at `name`: an async theme-command
                reply, a thumbnail decode, or the carousel's own drag/settle
                animation can each still be landing when the *triggering*
                action's own log line or commit already happened, so this
                re-captures until several consecutive frames are pixel
                identical rather than trusting any single timing signal."""
                path = root / name
                previous = None
                stable = 0
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    subprocess.run(["grim", str(path)], env=env, check=True)
                    with Image.open(path) as image:
                        current = image.convert("RGB")
                    if previous is not None and ImageChops.difference(current, previous).getbbox() is None:
                        stable += 1
                        if stable >= stable_frames:
                            return current
                    else:
                        stable = 0
                    previous = current
                    time.sleep(interval)
                raise AssertionError(f"display never stabilized before capturing {name}")

            contact = 1

            def tap(x, y):
                nonlocal contact
                ipc(f"card_shell test-touch down {contact} {x} {y}")
                ipc(f"card_shell test-touch up {contact}")
                contact += 1

            def drag(x1, x2, y):
                """A deliberate drag: several real motion steps toward x2,
                then two "hold still" steps at x2 before release, so the
                recorded release velocity is near zero and the carousel
                settles immediately onto the nearest slot rather than
                coasting an unpredictable distance -- the touch-panel analog
                of theme_carousel.rs's own
                `slow_release_settles_immediately_to_nearest` unit test."""
                nonlocal contact
                this_contact = contact
                contact += 1
                ipc(f"card_shell test-touch down {this_contact} {x1} {y}")
                steps = 6
                for step in range(1, steps + 1):
                    x = x1 + (x2 - x1) * step / steps
                    ipc(f"card_shell test-touch motion {this_contact} {x:.1f} {y}")
                    time.sleep(0.03)
                for _ in range(3):
                    ipc(f"card_shell test-touch motion {this_contact} {x2} {y}")
                    time.sleep(0.03)
                ipc(f"card_shell test-touch up {this_contact}")

            ipc("card_shell test-touch init")
            subprocess.run([args.qemu, str(args.rust), "--surface", "settings"],
                           env=env, check=True, stdout=subprocess.DEVNULL)
            wait_for(lambda: commits() >= 1)
            controls = capture("settings.png")

            # --- Open the theme carousel, centered on the active theme. ---
            tap(475, 130)
            wait_for(lambda: calls() == [["list"]])
            # The list reply, its thumbnail decodes, and the carousel's own
            # first paint are each a separate repaint; wait for all of them
            # to finish landing rather than assuming a fixed commit count.
            listing = capture("theme-list.png")
            assert ImageChops.difference(controls, listing).getbbox(), "carousel was not painted"
            assert all(row[0] != "activate" for row in calls())

            # --- Browse by drag: 1:1, no side effect, no confirm. ---
            center_x = 284.0
            theme_center = slice_center(0, 0, center_x, THEME_TOP)
            drag(theme_center[0] + 60.0, theme_center[0] - 120.0, theme_center[1])  # -6 slots
            dragged = capture("theme-list-dragged.png")
            # Every fixture theme shares one solid-color preview image, so
            # two different *centered* indices can render pixel-identical
            # carousel slices in the middle of the range (same count of
            # neighbors either side, same imagery); extend the band to
            # include the name label below the carousel, which always
            # differs between two different centered themes.
            band = (20, int(THEME_TOP), 548, int(THEME_TOP + EXPANDED_H) + 70)
            assert ImageChops.difference(listing.crop(band), dragged.crop(band)).getbbox(), \
                "drag did not move the theme carousel"
            assert calls() == [["list"]], "browsing must never itself request a preview"

            # --- Browse by tap: a side slice recenters, still no confirm. ---
            # The exact slot the preceding drag settled on is a timing
            # detail of this synthetic IPC-injected touch harness (each
            # motion/up is its own round trip, unlike a real continuous
            # touch stream), not something this test should hardcode; "two
            # slices to the right of roughly where the drag left off" is
            # enough to land on a different slice than the drag alone did.
            side = slice_center(6, 8, center_x, THEME_TOP)
            tap(*side)
            recentered = capture("theme-list-recentered.png")
            assert ImageChops.difference(dragged.crop(band), recentered.crop(band)).getbbox(), \
                "tapping a side slice did not bring it to the centre"
            assert calls() == [["list"]], "a side-slice tap must only browse, never confirm"

            # --- Confirm: tap the now-centered slice. ---
            tap(*theme_center)  # slice_center's (0,0) case is centre-independent of `selected`
            wait_for(lambda: any(row[0] == "preview" for row in calls()))
            preview_capture = capture("theme-preview.png")
            assert ImageChops.difference(recentered, preview_capture).getbbox(), "preview was not painted"
            assert all(row[0] != "activate" for row in calls())
            preview_calls = [row for row in calls() if row[0] == "preview"]
            assert len(preview_calls) == 1, "browsing must never queue an extra preview request"
            selected_theme = preview_calls[-1][1]
            assert selected_theme != f"{0:024x}", \
                "confirming after browsing away from the active theme must select a different one"

            # --- Background carousel: browse by drag, then confirm. ---
            bg_center = slice_center(0, 0, center_x, BACKGROUND_TOP)
            drag(bg_center[0], bg_center[0] - ITEM_STEP, bg_center[1])  # one slot: still 0 -> still 1
            bg_dragged = capture("theme-background-dragged.png")
            bg_band = (20, int(BACKGROUND_TOP), 548, int(BACKGROUND_TOP + EXPANDED_H))
            assert ImageChops.difference(preview_capture.crop(bg_band), bg_dragged.crop(bg_band)).getbbox(), \
                "drag did not move the background carousel"
            assert all(row[0] != "activate" for row in calls())
            tap(*bg_center)
            wait_for(lambda: any(row[:2] == ["preview", selected_theme] and "--background" in row
                                 for row in calls()), 20)
            selected = capture("theme-background-selected.png")
            assert ImageChops.difference(bg_dragged, selected).getbbox(), \
                "confirming a different background did not update the preview"
            background_call = [row for row in calls() if row[0] == "preview" and "--background" in row][-1]
            assert background_call[background_call.index("--background") + 1] == "d" * 24
            assert all(row[0] != "activate" for row in calls())

            # --- Cancel returns to the carousel without activating. ---
            tap(120, PREVIEW_FOOTER_Y + 25.0)
            wait_for(lambda: calls()[-1] == ["list"])
            capture("_after-cancel.png")  # only for its stabilization wait
            assert all(row[0] != "activate" for row in calls())

            # --- Re-confirm and Apply: only this explicit action activates. ---
            tap(*theme_center)
            wait_for(lambda: calls()[-1][0] == "preview")
            capture("_before-apply.png")  # only for its stabilization wait
            tap(430, PREVIEW_FOOTER_Y + 25.0)
            wait_for(lambda: any(row[0] == "activate" for row in calls()))
            activation = [row for row in calls() if row[0] == "activate"]
            assert len(activation) == 1 and "--expected-generation" in activation[0]
            assert activation[0][activation[0].index("--expected-generation") + 1] == "b" * 24
            print("PASS paired Sway/Rust theme carousel QEMU touch, synthetic backend; no physical touch")
        finally:
            if rust is not None:
                rust.terminate()
                try: rust.wait(timeout=5)
                except subprocess.TimeoutExpired: rust.kill(); rust.wait(timeout=5)
            sway.terminate()
            try: sway.wait(timeout=5)
            except subprocess.TimeoutExpired: sway.kill(); sway.wait(timeout=5)
            rust_log.close()
            sway_log.close()


if __name__ == "__main__":
    main()

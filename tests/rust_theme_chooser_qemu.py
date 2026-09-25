#!/usr/bin/env python3
"""Paired Sway/Rust theme carousel touch proof with a synthetic theme command.

Task: tap-to-apply (2026-09-25, user decision: "tap theme in the theme
picker, apply immediately, so i can compare them easily"). There is no
longer a separate Preview page or Apply/Cancel footer: tapping the
already-centred slice of either carousel applies it right away, through
the same "preview" (learn the generation)/"activate" pair the old
Apply button used to send, chained automatically.

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
import json, os, sys, time
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["K230_TEST_THEME_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
# Rapid-tap coalescing proof (task: tap-to-apply, 2026-09-25): a "preview"
# call naming this theme id (env var, unset by default) sleeps before
# replying, giving the test a reliable window to tap a *different* theme
# while this one is still in flight -- the Rust client's own `Desired`
# coalescing must discard this reply once it lands late, never activate
# it, and move straight on to whatever was tapped in the meantime.
slow_id = os.environ.get("K230_TEST_THEME_SLOW_ID")
if args and args[0] == "preview" and len(args) > 1 and args[1] == slow_id:
    time.sleep(1.5)
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
#
# Two geometries now, matching theme_carousel::{THEME_GEOMETRY,
# BACKGROUND_GEOMETRY}: the Themes page's hero carousel is deliberately
# larger (and a portrait-cropped aspect) than the Preview page's background
# carousel, which has far less spare vertical budget on that page. See that
# module's own doc for why.
THEME_GEOMETRY = {"expanded_w": 480.0, "expanded_h": 640.0, "slice_w": 68.0,
                  "slice_h": 582.0, "spacing": -19.0}
BACKGROUND_GEOMETRY = {"expanded_w": 420.0, "expanded_h": 260.0, "slice_w": 59.0,
                       "slice_h": 237.0, "spacing": -16.0}
# Task: tap-to-apply (2026-09-25) put both carousels on one page; these
# mirror theme_ui.rs's own `THEME_CAROUSEL_TOP`/`BACKGROUND_CAROUSEL_TOP`
# exactly (204.0/662.0 were the old, separate-page values).
THEME_TOP = 132.0
BACKGROUND_TOP = THEME_TOP + THEME_GEOMETRY["expanded_h"] + 100.0


def item_step(geometry):
    return geometry["slice_w"] + geometry["spacing"]


def slice_center(geometry, selected, index, center_x, top_y):
    """The exact center of carousel slice `index`'s rect when `selected` is
    centered -- theme_carousel::exact_layout, transcribed for the test."""
    relative = index - selected
    expanded_w = geometry["expanded_w"]
    expanded_h = geometry["expanded_h"]
    slice_w = geometry["slice_w"]
    slice_h = geometry["slice_h"]
    spacing = geometry["spacing"]
    step = item_step(geometry)
    preview_x = center_x - expanded_w / 2.0
    if relative == 0:
        return center_x, top_y + expanded_h / 2.0
    x = (preview_x + relative * step if relative < 0
         else preview_x + expanded_w + spacing + (relative - 1) * step)
    y = top_y + (expanded_h - slice_h) / 2.0
    return x + slice_w / 2.0, y + slice_h / 2.0


def browse_calls_are_safe(rows):
    """Task 3.2: once a theme has been the carousel's centred item, at
    rest, for its debounce interval, browsing alone may now itself trigger
    a background warm-up "preview" call (no `--background` flag, since
    that only ever accompanies an explicit background selection on the
    Preview page) -- see `theme_ui.rs`'s `poll_prepare_ahead`. That call's
    reply is discarded before it can reach `ThemeView::accept` (proven by
    this test's own screenshot diffs never showing a navigation at these
    call sites, not by the log alone), so "browsing must never activate or
    select a background" is still the real invariant, not "browsing must
    never call preview at all"."""
    return all(row[0] == "list" or (row[0] == "preview" and "--background" not in row)
               for row in rows)


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
        # Rapid-tap coalescing (task: tap-to-apply, 2026-09-25): theme 8's
        # own "preview" call is made to sleep before replying (see
        # THEME_COMMAND above), giving a reliable window to tap a
        # *different* theme while it is still in flight.
        slow_theme_id = f"{8:024x}"
        env = dict(os.environ, XDG_RUNTIME_DIR=str(root), WLR_BACKENDS="headless",
                   WLR_HEADLESS_OUTPUTS="1", WLR_RENDERER="pixman",
                   SWAY_K230_CARD_SHELL="1", SWAY_K230_CARD_TEST_INPUT="1",
                   K230_THEME_COMMAND=str(command), K230_TEST_THEME_LOG=str(log),
                   K230_TEST_THEME_GENERATION=str(root / "generations"),
                   K230_TEST_THEME_PREVIEW=str(preview),
                   K230_TEST_THEME_SLOW_ID=slow_theme_id)
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

            active_theme_id = f"{0:024x}"

            # --- Open the theme carousel, centered on the active theme. ---
            tap(475, 130)
            wait_for(lambda: any(row == ["list"] for row in calls()))
            # Task: tap-to-apply (2026-09-25): the active theme's own detail
            # (feeding the background carousel below the theme carousel)
            # loads itself automatically once the list arrives -- no tap
            # needed, see `ThemeView::accept`'s own `already_active` doc.
            wait_for(lambda: any(row[:2] == ["preview", active_theme_id] and "--background" not in row
                                 for row in calls()))
            # The list reply, its thumbnail decodes, the active theme's own
            # auto-loaded detail, and the carousel's own first paint are
            # each a separate repaint; wait for all of them to finish
            # landing rather than assuming a fixed commit count.
            listing = capture("theme-list.png")
            assert ImageChops.difference(controls, listing).getbbox(), "carousel was not painted"
            assert all(row[0] != "activate" for row in calls())

            # --- Browse by drag: 1:1, no side effect, no confirm. ---
            center_x = 284.0
            theme_step = item_step(THEME_GEOMETRY)
            theme_center = slice_center(THEME_GEOMETRY, 0, 0, center_x, THEME_TOP)
            drag(theme_center[0] + 2 * theme_step, theme_center[0] - 4 * theme_step,
                 theme_center[1])  # -6 slots
            dragged = capture("theme-list-dragged.png")
            # Every fixture theme shares one solid-color preview image, so
            # two different *centered* indices can render pixel-identical
            # carousel slices in the middle of the range (same count of
            # neighbors either side, same imagery); extend the band to
            # include the name label below the carousel, which always
            # differs between two different centered themes.
            band = (20, int(THEME_TOP), 548, int(THEME_TOP + THEME_GEOMETRY["expanded_h"]) + 90)
            assert ImageChops.difference(listing.crop(band), dragged.crop(band)).getbbox(), \
                "drag did not move the theme carousel"
            assert browse_calls_are_safe(calls()), \
                "browsing must never select a background or activate"

            # --- Browse by tap: a side slice recenters, still no confirm. ---
            # The exact slot the preceding drag settled on is a timing
            # detail of this synthetic IPC-injected touch harness (each
            # motion/up is its own round trip, unlike a real continuous
            # touch stream), not something this test should hardcode; "one
            # slice to the right of roughly where the drag left off" is
            # enough to land on a different slice than the drag alone did,
            # and (unlike the previous, much wider-margined geometry) is as
            # far from center as this hero carousel's tight side margin
            # keeps on-panel at all -- see theme_carousel.rs's own doc for
            # why this carousel's neighbors barely peek in from the edge.
            side = slice_center(THEME_GEOMETRY, 6, 7, center_x, THEME_TOP)
            # A tap sent immediately after the preceding drag's own release
            # occasionally (observed empirically, not explained by
            # theme_carousel.rs's own logic -- its hit_test/visible_slices
            # were independently checked against these exact coordinates
            # and resolve correctly) has no visible effect, most likely a
            # touch-injection/IPC timing artifact of this synthetic harness
            # rather than the carousel itself; retry the tap once after a
            # short real pause before treating it as a genuine failure.
            for attempt in range(2):
                if attempt:
                    time.sleep(0.3)
                tap(*side)
                recentered = capture("theme-list-recentered.png")
                if ImageChops.difference(dragged.crop(band), recentered.crop(band)).getbbox():
                    break
            else:
                raise AssertionError("tapping a side slice did not bring it to the centre")
            assert browse_calls_are_safe(calls()), \
                "a side-slice tap must only browse, never confirm or activate"
            # Task 3.2 proof: two settle-and-dwell cycles have now each sat
            # comfortably past the debounce interval during `capture`'s own
            # multi-frame stabilization wait, so at least one non-active
            # theme should already have been warmed in the background --
            # not merely "browsing didn't break", but "browsing actually
            # warms a candidate ahead of Apply", the behavior this task adds.
            assert any(row[0] == "preview" and "--background" not in row and row[1] != active_theme_id
                       for row in calls()), \
                "browsing should have warmed at least one non-active theme by now (task 3.2)"

            # --- Tap-to-apply: tapping the now-centred slice applies it
            # immediately -- no separate Preview page, no Apply/Cancel
            # footer (task: tap-to-apply, 2026-09-25, user decision: "tap
            # theme in the theme picker, apply immediately"). ---
            theme7_id = f"{7:024x}"
            tap(*theme_center)  # slice_center's (0,0) case is centre-independent of `selected`
            wait_for(lambda: any(row[0] == "activate" and row[1] == theme7_id for row in calls()), 20)
            tapped = capture("theme-tap-apply.png")
            assert ImageChops.difference(recentered, tapped).getbbox(), \
                "tapping the centred slice must apply it (and repaint) immediately"
            activation = [row for row in calls() if row[0] == "activate"]
            assert len(activation) == 1 and activation[0][1] == theme7_id
            assert "--expected-generation" in activation[0]
            assert activation[0][activation[0].index("--expected-generation") + 1] == "b" * 24
            assert theme7_id != active_theme_id, \
                "confirming after browsing away from the active theme must apply a different one"

            # --- Background carousel: below the theme carousel on this
            # same page (not a separate page reached by confirming a
            # theme); browse by drag, then tap-to-apply directly. ---
            bg_step = item_step(BACKGROUND_GEOMETRY)
            bg_center = slice_center(BACKGROUND_GEOMETRY, 0, 0, center_x, BACKGROUND_TOP)
            drag(bg_center[0], bg_center[0] - bg_step, bg_center[1])  # one slot: still 0 -> still 1
            bg_dragged = capture("theme-background-dragged.png")
            bg_band = (20, int(BACKGROUND_TOP), 548,
                       int(BACKGROUND_TOP + BACKGROUND_GEOMETRY["expanded_h"]))
            assert ImageChops.difference(tapped.crop(bg_band), bg_dragged.crop(bg_band)).getbbox(), \
                "drag did not move the background carousel"
            assert all(row[0] != "activate" or row[1] != theme7_id or "--background" not in row
                       for row in calls())
            tap(*bg_center)
            wait_for(lambda: any(row[0] == "activate" and row[1] == theme7_id and "--background" in row
                                 for row in calls()), 20)
            bg_selected = capture("theme-background-selected.png")
            assert ImageChops.difference(bg_dragged, bg_selected).getbbox(), \
                "applying a different background did not repaint"
            background_activation = [row for row in calls()
                                     if row[0] == "activate" and row[1] == theme7_id and "--background" in row]
            assert len(background_activation) == 1
            call = background_activation[0]
            assert call[call.index("--background") + 1] == "d" * 24
            # A background tap already knows its own theme's generation (it
            # was loaded right alongside the backgrounds themselves), so it
            # applies straight through `Activate` -- no `Preview` round trip
            # first, unlike a theme tap targeting a never-loaded generation.
            assert not any(row[0] == "preview" and "--background" in row for row in calls()), \
                "a background tap-apply must never need its own Preview step"

            # --- Rapid taps across themes coalesce onto the last one: no
            # queue of stale activations, and an in-flight apply (theme 8,
            # whose own "preview" reply is made to sleep -- see
            # THEME_COMMAND above) is superseded safely by theme 9. ---
            theme9_id = f"{9:024x}"
            drag(center_x, center_x - theme_step, theme_center[1])  # one slot: 7 -> 8
            tap(*theme_center)  # confirm theme 8; its own reply is in flight (slow)
            wait_for(lambda: any(row[:2] == ["preview", slow_theme_id] for row in calls()))
            drag(center_x, center_x - theme_step, theme_center[1])  # one slot: 8 -> 9, while theme 8 is pending
            tap(*theme_center)  # confirm theme 9 before theme 8's own reply lands
            wait_for(lambda: any(row[0] == "activate" and row[1] == theme9_id for row in calls()), 20)
            coalesced = capture("theme-rapid-tap-coalesced.png")
            assert ImageChops.difference(bg_selected, coalesced).getbbox(), \
                "the superseding tap (theme 9) must still repaint once it settles"
            assert not any(row[0] == "activate" and row[1] == slow_theme_id for row in calls()), \
                "a superseded in-flight apply (theme 8) must never itself activate"
            assert any(row[:2] == ["preview", slow_theme_id] for row in calls()), \
                "the superseded tap's own request must still have been sent, not silently skipped"
            activations = [row for row in calls() if row[0] == "activate"]
            assert [row[1] for row in activations] == [theme7_id, theme7_id, theme9_id], \
                "exactly one activation per genuinely-settled apply, no stale queue"

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

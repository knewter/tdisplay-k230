#!/usr/bin/env python3
"""Headless QEMU proof of the pinned Home screen: page swipe, dock tap
launch, long-press pin from the drawer, rearrange/remove, and persistence
across a restart -- captured under a dark and a light theme.

Synthetic touch injection (card_shell test-touch), a private desktop
catalog, and a pre-staged layout file; never physical panel evidence. This
proves wiring/layout under QEMU's headless Pixman backend, not real-glass
touch feel, contrast, or panel readability -- see
openspec/changes/the-shell-presents-a-pinned-home-screen/tasks.md's
board-acceptance task for what remains open.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time

from PIL import Image, ImageChops

# Mirrors home_grid.rs's own constants exactly, so this black-box test can
# derive exact tap points instead of guessing coordinates. The layout math
# itself is covered by that module's own unit tests; this only needs
# "some point solidly inside slot N" and "the dock/Done/Remove bands".
COLUMNS = 4
DOCK_SLOTS = 4
SIDE_MARGIN = 20.0
TILE_GAP = 10.0
ROW_HEIGHT = 138.0
GRID_TOP = 72.0
DOTS_HEIGHT = 40.0
DOCK_HEIGHT = 148.0
WIDTH = 568
HEIGHT = 1232


def tile_rect(slot):
    tile_width = (WIDTH - 2 * SIDE_MARGIN - (COLUMNS - 1) * TILE_GAP) / COLUMNS
    column = slot % COLUMNS
    row = slot // COLUMNS
    return (
        SIDE_MARGIN + column * (tile_width + TILE_GAP),
        GRID_TOP + row * ROW_HEIGHT,
        tile_width,
        ROW_HEIGHT - TILE_GAP,
    )


def tile_center(slot):
    x, y, w, h = tile_rect(slot)
    return (x + w / 2.0, y + h / 2.0)


# A page swipe only needs to cross half the panel width to settle onto the
# neighboring page (see home_pager.rs's own round-to-nearest-page settle);
# this stays well short of that but far enough on either side of it that a
# drag started and released near one edge never asks for an off-panel
# touch coordinate.
SWIPE_DISTANCE = 380.0
SWIPE_MARGIN = 40.0


def swipe_y():
    return tile_center(0)[1]


def apps_per_page():
    """Mirrors home_grid.rs's rows_per_page/apps_per_page exactly."""
    grid_bottom = (HEIGHT - DOCK_HEIGHT) - DOTS_HEIGHT
    available = max(grid_bottom - GRID_TOP, 0.0)
    rows = max(int(available // ROW_HEIGHT), 1)
    return COLUMNS * rows


def dock_top():
    return HEIGHT - DOCK_HEIGHT


def dock_center(slot):
    tile_width = (WIDTH - 2 * SIDE_MARGIN - (DOCK_SLOTS - 1) * TILE_GAP) / DOCK_SLOTS
    x = SIDE_MARGIN + slot * (tile_width + TILE_GAP)
    y = dock_top() + 18.0
    h = DOCK_HEIGHT - 36.0
    return (x + tile_width / 2.0, y + h / 2.0)


def drawer_tile_center(index):
    """Mirrors navigation.rs's own drawer tile geometry exactly (COLUMNS=3,
    24px side margin, 12px gap, 160px row pitch, 148px tile height,
    list_top = height*0.19 + 181.0), so this test derives the same
    coordinates that module's own unit tests already verify."""
    side_margin, gap, columns, row_height, tile_height = 24.0, 12.0, 3, 160.0, 148.0
    list_top = HEIGHT * 0.19 + 181.0
    tile_width = (WIDTH - 2 * side_margin - (columns - 1) * gap) / columns
    column = index % columns
    row = index // columns
    x = side_margin + column * (tile_width + gap)
    y = list_top + row * row_height
    return (x + tile_width / 2.0, y + tile_height / 2.0)


def done_button_point():
    w = 108.0
    return (WIDTH - SIDE_MARGIN - w + w / 2.0, 16.0 + (GRID_TOP - 28.0) / 2.0)


def remove_target_point():
    w = 108.0
    return (SIDE_MARGIN + w / 2.0, 16.0 + (GRID_TOP - 28.0) / 2.0)


def theme_generation(root, source, label):
    """Copies the repo's own vetted default appearance/report tokens,
    darkening or lightening the palette -- the same fixture shape
    tests/rust_wifi_settings_qemu.py's own theme() helper already
    establishes for this test suite, so a themed capture here is
    comparable to every other themed QEMU capture in this repo."""
    appearance = json.loads((source / "default-appearance.json").read_text())
    report = json.loads((source / "default-report.json").read_text())
    generation = ("a" if label == "dark" else "b") * 24
    appearance["generation"] = report["generation"] = generation
    # The loaded appearance's own icon_theme (normally "Yaru-purple", the
    # default's real icon set) overrides whatever K230_ICON_THEME the
    # process started with (appearance.rs applies each snapshot's own
    # icon_theme to the shared IconCache) -- point both appearance.json and
    # report.json at this test's private fixture theme instead (they must
    # agree, or the whole snapshot is rejected as a mismatch), so Home/
    # drawer icon painting actually exercises a real decoded icon.
    appearance["icon_theme"] = report["icon_theme"] = "fixture"
    if label == "light":
        palette = report["palette"]
        palette.update({"background": "#eff1f5", "foreground": "#34384d",
                        "light_foreground": "#565a73", "accent": "#1e66f5",
                        "mode": "light"})
        for section in appearance["sections"].values():
            for key, token in section.items():
                if not isinstance(token, dict) or token.get("kind") != "brush":
                    continue
                if "text" in key or key in ("foreground", "active"):
                    color = "#ff34384d"
                elif "selected" in key:
                    color = "#ffd7e3fa"
                elif "border" in key:
                    color = "#ff9aa4b6"
                else:
                    color = "#ffeff1f5"
                for stop in token["stops"]:
                    stop["argb"] = color
    directory = root / f"theme-{label}" / generation
    directory.mkdir(parents=True)
    (directory / "appearance.json").write_text(json.dumps(appearance))
    (directory / "report.json").write_text(json.dumps(report))
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("sway", "swaymsg", "rust"):
        parser.add_argument("--" + field, required=True, type=Path)
    parser.add_argument("--theme-source", required=True, type=Path)
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.sway, args.swaymsg, args.rust):
        if not path.is_file():
            parser.error(f"exact cross-built executable must exist: {path}")
    root = args.output
    root.mkdir(mode=0o700, exist_ok=False)
    qemu = str(args.qemu)

    config = root / "sway.conf"
    config.write_text(f"output HEADLESS-1 mode {WIDTH}x{HEIGHT}\nseat seat0 fallback true\n")
    swaymsg_wrapper = root / "swaymsg"
    swaymsg_wrapper.write_text(f"#!/bin/sh\nexec {qemu} {args.swaymsg} \"$@\"\n")
    swaymsg_wrapper.chmod(0o700)

    # A real, decodable fixture icon (not the initial-letter fallback) for
    # one app, staged under a private icon theme -- exactly icon.rs's own
    # test fixture shape, proving Home really resolves and paints an
    # installed app's icon rather than only ever falling back.
    data_home = root / "data"
    icons_dir = data_home / "icons/fixture/scalable/apps"
    icons_dir.mkdir(parents=True)
    (data_home / "icons/fixture/index.theme").write_text(
        "[Icon Theme]\nName=fixture\nDirectories=scalable/apps\n"
        "[scalable/apps]\nSize=48\nType=Scalable\nMinSize=16\nMaxSize=128\n"
    )
    (icons_dir / "fixture-terminal.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48">'
        '<rect width="48" height="48" fill="#78d7cb"/></svg>'
    )

    apps_dir = data_home / "applications"
    apps_dir.mkdir(parents=True)
    marker = root / "launch-marker"
    launch_script = root / "launch"
    launch_script.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$1" >> "$XDG_RUNTIME_DIR/launch-marker"\n'
    )
    launch_script.chmod(0o700)
    # Carries the real SVG icon staged above, and is placed in the
    # pre-staged layout's dock slot 0 (below) -- proving Home paints and
    # taps a real decoded icon, not just an initial-letter fallback.
    (apps_dir / "k230-fixture-terminal.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Fixture Terminal\n"
        f"Exec={launch_script} terminal\nIcon=fixture-terminal\n"
    )
    # "Fixture Extra" matches no curated default keyword, so a fresh Home
    # never shows it until it is explicitly pinned from the drawer.
    (apps_dir / "k230-fixture-extra.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Fixture Extra\n"
        f"Exec={launch_script} extra\n"
    )
    # A second page's sole occupant, staged directly into the layout file
    # below rather than by pinning 28+ filler apps to fill page 0 -- this
    # test proves paging/rendering across pages, not how many real icons a
    # 4-column grid holds before it needs a second page (home_grid.rs's own
    # unit tests already cover that layout math exactly).
    (apps_dir / "k230-fixture-page-two.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Fixture Page Two\n"
        f"Exec={launch_script} page-two\n"
    )

    state_home = root / "state"
    home_json = state_home / "k230-shell/home.json"
    home_json.parent.mkdir(parents=True)
    # A pre-staged layout, not a fresh-install seed: this test's own
    # dock/page contents are fixture data for exercising paging/tap/pin/
    # rearrange, not a demonstration of home_state::seed_default (which
    # home_state.rs's own host unit tests -- seed_default_fills_dock_
    # before_grid, curated_defaults_skip_missing_categories_and_dedupe --
    # already cover directly).
    home_json.write_text(json.dumps({
        "schema": 1,
        "pages": [
            [None, None, None, None],
            ["k230-fixture-page-two.desktop", None, None, None],
        ],
        "dock": ["k230-fixture-terminal.desktop", None, None, None],
    }))

    dark = theme_generation(root, args.theme_source, "dark")
    light = theme_generation(root, args.theme_source, "light")

    env = dict(
        os.environ,
        XDG_RUNTIME_DIR=str(root),
        XDG_DATA_HOME=str(data_home),
        XDG_DATA_DIRS=str(data_home),
        XDG_STATE_HOME=str(state_home),
        K230_ICON_THEME="fixture",
        WLR_BACKENDS="headless",
        WLR_HEADLESS_OUTPUTS="1",
        WLR_RENDERER="pixman",
        SWAY_K230_CARD_SHELL="1",
        SWAY_K230_CARD_TOUCH_FIRST="1",
        SWAY_K230_CARD_TEST_INPUT="1",
        K230_SWAYMSG=str(swaymsg_wrapper),
    )

    logs = {}
    processes = []

    def spawn(name, argv, extra_env=None):
        log = (root / f"{name}.log").open("a")
        logs[name] = log
        run_env = dict(env, **(extra_env or {}))
        process = subprocess.Popen(argv, env=run_env, stdout=log, stderr=log)
        processes.append(process)
        return process

    def text(name):
        return (root / f"{name}.log").read_text()

    def wait_for(predicate, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = predicate()
            if value:
                return value
            time.sleep(0.05)
        raise AssertionError("timed out waiting for home-screen QEMU state")

    def ipc(command):
        with socket.socket(socket.AF_UNIX) as stream:
            stream.settimeout(10)
            stream.connect(str(next(root.glob("sway-ipc.*.sock"))))
            payload = command.encode()
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
            assert all(row["success"] for row in answer), (command, answer)

    contact = 1

    def tap(x, y):
        nonlocal contact
        ipc(f"card_shell test-touch down {contact} {x} {y}")
        ipc(f"card_shell test-touch up {contact}")
        contact += 1

    def long_press(x, y, hold_seconds=0.65):
        """Held in place past home_pager::LONG_PRESS_MS/navigation::LONG_PRESS_MS
        (500ms) without exceeding TAP_SLOP, then released."""
        nonlocal contact
        this_contact = contact
        contact += 1
        ipc(f"card_shell test-touch down {this_contact} {x} {y}")
        time.sleep(hold_seconds)
        ipc(f"card_shell test-touch up {this_contact}")

    def drag_steps(x1, x2, y, steps=6):
        """Horizontal-only drag (constant y) -- page swipes."""
        return drag_steps_2d((x1, y), (x2, y), steps)

    def drag_steps_2d(start, end, steps=6):
        """General 2D drag, for a rearrange-mode icon drag to a target that
        is not on the same horizontal line as the lifted icon (e.g. the
        Done/Remove band in the top inset, well above the grid)."""
        nonlocal contact
        this_contact = contact
        contact += 1
        ipc(f"card_shell test-touch down {this_contact} {start[0]} {start[1]}")
        for step in range(1, steps + 1):
            x = start[0] + (end[0] - start[0]) * step / steps
            y = start[1] + (end[1] - start[1]) * step / steps
            ipc(f"card_shell test-touch motion {this_contact} {x:.1f} {y:.1f}")
            time.sleep(0.03)
        return this_contact

    def settle_and_release(this_contact, x2, y):
        for _ in range(3):
            ipc(f"card_shell test-touch motion {this_contact} {x2} {y}")
            time.sleep(0.03)
        ipc(f"card_shell test-touch up {this_contact}")

    def route(surface):
        subprocess.run([qemu, str(args.rust), "--surface", surface], env=env,
                        check=True, stdout=subprocess.DEVNULL)

    def capture(name, timeout=8.0, stable_frames=3, interval=0.1):
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

    def start_pass(generation, prefix, rust_log_mode="w"):
        (root / f"{prefix}-rust.log").touch()
        return spawn(prefix + "-rust", [qemu, str(args.rust), "--serve"],
                     {"K230_THEME_DEFAULT_GENERATION": str(generation)})

    checks = {}
    try:
        spawn("sway", [qemu, str(args.sway), "-c", str(config), "-d"])
        wait_for(lambda: "Running compositor on wayland display" in text("sway"), 60)
        env["WAYLAND_DISPLAY"] = next(
            path.name for path in root.glob("wayland-*") if not path.name.endswith(".lock")
        )
        env["SWAYSOCK"] = str(next(root.glob("sway-ipc.*.sock")))
        ipc("card_shell test-touch init")

        # --- Dark pass: full sequence. ---
        rust = start_pass(dark, "dark")
        wait_for(lambda: "ready-idle" in text("dark-rust"), 30)

        page1 = capture("home-dark-page1.png")

        # A leftward drag from near the right edge, well past the 50%
        # settle threshold but never past the left edge, captured partway
        # through (a genuine "mid-swipe" frame while the touch is still
        # down) and then completed and released, so release reliably
        # rounds forward to page 1 rather than snapping back to page 0.
        drag_y = swipe_y()
        start_x = WIDTH - SWIPE_MARGIN
        end_x = start_x - SWIPE_DISTANCE
        contact_id = contact
        contact += 1
        ipc(f"card_shell test-touch down {contact_id} {start_x} {drag_y}")
        for fraction in (0.2, 0.35, 0.5):
            step_x = start_x - SWIPE_DISTANCE * fraction
            ipc(f"card_shell test-touch motion {contact_id} {step_x:.1f} {drag_y}")
            time.sleep(0.03)
        mid_swipe = capture("home-dark-mid-swipe.png", timeout=1.5, stable_frames=1)
        checks["mid_swipe_differs_from_page1"] = bool(
            ImageChops.difference(page1, mid_swipe).getbbox()
        )
        for fraction in (0.7, 0.9, 1.0):
            step_x = start_x - SWIPE_DISTANCE * fraction
            ipc(f"card_shell test-touch motion {contact_id} {step_x:.1f} {drag_y}")
            time.sleep(0.03)
        settle_and_release(contact_id, end_x, drag_y)
        page2 = capture("home-dark-page2.png")
        checks["page2_differs_from_page1"] = bool(ImageChops.difference(page1, page2).getbbox())

        tap(*dock_center(0))
        wait_for(lambda: "app-launch-requested" in text("dark-rust")
                 or "app-launch-failed" in text("dark-rust"), 8)
        checks["dock_tap_launched"] = "app-launch-requested" in text("dark-rust")
        wait_for(lambda: marker.exists() and "terminal" in marker.read_text())

        # --- Back to page 1, then the pin flow via the drawer. ---
        back_y = swipe_y()
        back_start_x = SWIPE_MARGIN
        back_end_x = back_start_x + SWIPE_DISTANCE
        drag_id = drag_steps(back_start_x, back_end_x, back_y)
        settle_and_release(drag_id, back_end_x, back_y)
        capture("home-dark-back-to-page1.png")

        route("drawer")
        drawer_open = capture("home-dark-drawer.png")
        checks["drawer_opened"] = bool(ImageChops.difference(page1, drawer_open).getbbox())
        # "Fixture Extra" is the second alphabetical entry after "Fixture
        # Page Two"/"Fixture Terminal" -- locate it by row 0..N; the
        # drawer's own tile geometry is navigation.rs's, not home_grid.rs's,
        # so this taps the first row's first column, which fixture naming
        # ("Fixture Extra" sorts before "Fixture Page Two"/"Fixture
        # Terminal") places "Fixture Extra" at.
        long_press(*drawer_tile_center(0))
        wait_for(lambda: "home-pinned" in text("dark-rust"), 5)
        checks["drawer_long_press_pinned"] = True
        route("hide")

        pinned = capture("home-dark-pin-flow.png")
        checks["pinned_icon_visible"] = bool(ImageChops.difference(page1, pinned).getbbox())

        # --- Rearrange mode: long-press the newly pinned icon, drag to Remove. ---
        # `long_press` holds in place past LONG_PRESS_MS then releases; the
        # release itself is what `HomeScreen::up` sees as a rearrange-mode
        # drop (of nothing yet moved), so entering rearrange mode is
        # already complete by the time this call returns.
        long_press(*tile_center(0))
        rearranging = capture("home-dark-rearrange.png")
        checks["rearrange_mode_shows_done_and_remove"] = bool(
            ImageChops.difference(pinned, rearranging).getbbox()
        )
        # A fresh press-and-drag on the same (now-lifted-mode) icon, over to
        # the Remove target -- a real diagonal drag, not a same-row one.
        remove_id = drag_steps_2d(tile_center(0), remove_target_point())
        remove_x, remove_y = remove_target_point()
        settle_and_release(remove_id, remove_x, remove_y)
        capture("home-dark-removed.png")
        # The authoritative check for the remove flow is the persisted
        # layout file itself, read after the restart below
        # ("removed_from_saved_layout") -- a visual diff here would be
        # fragile (the removed icon's former slot is simply empty grid
        # space, which can look identical to other empty slots).

        # --- Restart proves persistence. ---
        rust.terminate()
        try:
            rust.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rust.kill()
        layout_after_removal = json.loads(home_json.read_text())
        checks["removed_from_saved_layout"] = "k230-fixture-extra.desktop" not in json.dumps(
            layout_after_removal
        )
        checks["dock_survives_the_removal"] = (
            "k230-fixture-terminal.desktop" in json.dumps(layout_after_removal)
        )

        restarted = start_pass(dark, "dark-restarted")
        wait_for(lambda: "ready-idle" in text("dark-restarted-rust"), 30)
        after_restart = capture("home-dark-after-restart.png")
        checks["stable_after_restart"] = not bool(
            ImageChops.difference(page1, after_restart).getbbox()
        )
        restarted.terminate()
        try:
            restarted.wait(timeout=5)
        except subprocess.TimeoutExpired:
            restarted.kill()

        # --- Light pass: headline captures only. ---
        light_rust = start_pass(light, "light")
        wait_for(lambda: "ready-idle" in text("light-rust"), 30)
        light_page1 = capture("home-light-page1.png")
        light_y = swipe_y()
        light_start_x = WIDTH - SWIPE_MARGIN
        light_end_x = light_start_x - SWIPE_DISTANCE
        light_id = drag_steps(light_start_x, light_end_x, light_y)
        settle_and_release(light_id, light_end_x, light_y)
        light_page2 = capture("home-light-page2.png")
        checks["light_page2_differs_from_page1"] = bool(
            ImageChops.difference(light_page1, light_page2).getbbox()
        )
        checks["light_differs_from_dark"] = bool(
            ImageChops.difference(light_page1, page1).getbbox()
        )
        light_rust.terminate()
        try:
            light_rust.wait(timeout=5)
        except subprocess.TimeoutExpired:
            light_rust.kill()

        # --- Showcase pass: a believable, fully-populated fresh Home, for
        # visual evidence rather than interaction coverage (the sparse
        # 2-3-app fixture above is deliberately minimal for the
        # paging/tap/pin/rearrange checks; this is what a real Home with a
        # handful of pinned apps actually looks like). ---
        showcase_data = root / "showcase-data"
        showcase_apps = showcase_data / "applications"
        showcase_apps.mkdir(parents=True)
        showcase_icons = showcase_data / "icons/fixture/scalable/apps"
        showcase_icons.mkdir(parents=True)
        (showcase_data / "icons/fixture/index.theme").write_text(
            "[Icon Theme]\nName=fixture\nDirectories=scalable/apps\n"
            "[scalable/apps]\nSize=48\nType=Scalable\nMinSize=16\nMaxSize=128\n"
        )
        showcase_layout = {
            "terminal": ("Terminal", "#78d7cb"),
            "files": ("Files", "#f9c96e"),
            "editor": ("Text Editor", "#89b4fa"),
            "monitor": ("System Monitor", "#cba6f7"),
            "video": ("Video Player", "#f38ba8"),
            "settings": ("Settings", "#a6e3a1"),
            "browser": ("Browser", "#f6a35e"),
            "notes": ("Notes", "#94e2d5"),
        }
        for app_id, (label, hex_color) in showcase_layout.items():
            (showcase_icons / f"{app_id}.svg").write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48">'
                f'<rect width="48" height="48" rx="10" fill="{hex_color}"/></svg>'
            )
            (showcase_apps / f"k230-showcase-{app_id}.desktop").write_text(
                "[Desktop Entry]\nType=Application\n"
                f"Name={label}\nExec=/bin/true {app_id}\nIcon={app_id}\n"
            )
        showcase_state = root / "showcase-state"
        showcase_json = showcase_state / "k230-shell/home.json"
        showcase_json.parent.mkdir(parents=True)
        ids = [f"k230-showcase-{app_id}.desktop" for app_id in showcase_layout]
        per_page = apps_per_page()
        page0 = ids[4:8] + [None] * (per_page - 4)
        showcase_json.write_text(json.dumps({
            "schema": 1,
            "pages": [page0],
            "dock": ids[0:4],
        }))
        showcase_env = dict(env, XDG_DATA_HOME=str(showcase_data), XDG_DATA_DIRS=str(showcase_data),
                             XDG_STATE_HOME=str(showcase_state))

        def start_showcase(generation, prefix):
            (root / f"{prefix}-rust.log").touch()
            run_env = dict(showcase_env, K230_THEME_DEFAULT_GENERATION=str(generation))
            log = (root / f"{prefix}-rust.log").open("a")
            logs[prefix + "-rust"] = log
            process = subprocess.Popen([qemu, str(args.rust), "--serve"], env=run_env,
                                        stdout=log, stderr=log)
            processes.append(process)
            return process

        def wait_for_first_paint(prefix):
            # `ready-idle` logs before the compositor has necessarily
            # painted a first real frame; without another IPC round-trip
            # first (as every other pass above already has, incidentally,
            # by the time it takes its own first capture), a capture taken
            # immediately after can race a still-uninitialized black
            # headless output and "stabilize" on that instead.
            wait_for(lambda: "wallpaper-commit" in text(prefix)
                     and "home-configure" in text(prefix), 15)
            time.sleep(0.3)

        showcase_dark = start_showcase(dark, "showcase-dark")
        wait_for(lambda: "ready-idle" in text("showcase-dark-rust"), 30)
        wait_for_first_paint("showcase-dark-rust")
        capture("home-dark-showcase.png")
        showcase_dark.terminate()
        try:
            showcase_dark.wait(timeout=5)
        except subprocess.TimeoutExpired:
            showcase_dark.kill()

        showcase_light = start_showcase(light, "showcase-light")
        wait_for(lambda: "ready-idle" in text("showcase-light-rust"), 30)
        wait_for_first_paint("showcase-light-rust")
        capture("home-light-showcase.png")
        showcase_light.terminate()
        try:
            showcase_light.wait(timeout=5)
        except subprocess.TimeoutExpired:
            showcase_light.kill()

        failed = [name for name, ok in checks.items() if not ok]
        assert not failed, f"failed checks: {failed}"
        result = {"result": "PASS", "class": "headless-qemu-native-touch",
                  "checks": checks, "sway": str(args.sway), "rust": str(args.rust)}
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        print("PASS paired Sway/Rust Home screen QEMU touch, synthetic backend; no physical touch")
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for log in logs.values():
            log.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Headless QEMU proof of the polished pinned Home screen: page swipe, dock
tap launch, long-press pin from the drawer, rearrange (both the drag-to-
Remove-pill flow and the per-icon remove-badge tap), and persistence across
a restart -- captured under a dark and a light theme, each with a real
Omarchy wallpaper, a real bundled icon theme, and (for the interactive
scenarios) desktop entries whose Name/Icon exactly match this image's own
real ones (`nix/handheld-desktop-entries.nix`).

Synthetic touch injection (card_shell test-touch) and a private desktop
catalog; never physical panel evidence. This proves wiring/layout under
QEMU's headless Pixman backend, not real-glass touch feel, contrast, or
panel readability -- see
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
import sys
import time

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from theme_activate import prepare  # noqa: E402

# Mirrors home_grid.rs's own constants exactly, so this black-box test can
# derive exact tap points instead of guessing coordinates. The layout math
# itself is covered by that module's own unit tests; this only needs
# "some point solidly inside slot N" and "the dock/Done/Remove/badge bands".
COLUMNS = 4
DOCK_SLOTS = 4
SIDE_MARGIN = 22.0
TILE_GAP = 18.0
ROW_HEIGHT = 184.0
# The compositor's own top-edge "pull down for shade" gesture band
# (card-shell-policy.c's default edge_band=48): a fresh tap with y<48 never
# reaches this client at all under SWAY_K230_CARD_TOUCH_FIRST=1 (set for
# every real session). Rearrange mode's Done/Remove pills sit just below it.
EDGE_BAND = 48.0
PILL_TOP = EDGE_BAND + 4.0
PILL_HEIGHT = 56.0
GRID_TOP = PILL_TOP + PILL_HEIGHT + 12.0
DOTS_HEIGHT = 34.0
ICON_PLATE_SIZE = 108.0
ICON_LABEL_GAP = 8.0
LABEL_HEIGHT = 20.0
DOCK_PLATE_SIZE = 108.0
DOCK_HEIGHT = 156.0
REMOVE_BADGE_HIT_RADIUS = 22.0
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


def tile_plate_corner(slot):
    """The grid icon plate's top-left corner -- where its remove badge sits
    while rearranging (home_grid.rs's `tile_content`/`plate_top_left`)."""
    x, y, w, h = tile_rect(slot)
    content_h = ICON_PLATE_SIZE + ICON_LABEL_GAP + LABEL_HEIGHT
    top = y + max((h - content_h) / 2.0, 0.0)
    plate_x = x + (w - ICON_PLATE_SIZE) / 2.0
    return (plate_x, top)


def dock_plate_corner(slot):
    x, y, w, h = dock_rect(slot)
    plate_x = x + (w - DOCK_PLATE_SIZE) / 2.0
    plate_y = y + (h - DOCK_PLATE_SIZE) / 2.0
    return (plate_x, plate_y)


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


def dock_rect(slot):
    tile_width = (WIDTH - 2 * SIDE_MARGIN - (DOCK_SLOTS - 1) * TILE_GAP) / DOCK_SLOTS
    x = SIDE_MARGIN + slot * (tile_width + TILE_GAP)
    return (x, dock_top(), tile_width, DOCK_HEIGHT)


def dock_center(slot):
    x, y, w, h = dock_rect(slot)
    return (x + w / 2.0, y + h / 2.0)


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
    w = 128.0
    return (WIDTH - SIDE_MARGIN - w + w / 2.0, PILL_TOP + PILL_HEIGHT / 2.0)


def remove_target_point():
    w = 128.0
    return (SIDE_MARGIN + w / 2.0, PILL_TOP + PILL_HEIGHT / 2.0)


def real_dark_generation(bundle):
    """The bundled default itself: a real Catppuccin palette, real icon
    theme selection (Yaru-purple), and a real Omarchy wallpaper
    (backgrounds/2-waves.webp, with its background.cache already built) --
    this is the exact generation the real image ships as its fresh-install
    default (`nix/handheld-theme-default/bundled-report.json`), not a
    palette-only/backgroundless fixture."""
    bundled = json.loads((ROOT / "nix/handheld-theme-default/bundled-report.json").read_text())
    generation = bundle / "generations" / bundled["generation"]
    assert generation.is_dir(), f"missing bundled generation: {generation}"
    on_disk = json.loads((generation / "report.json").read_text())
    assert on_disk == bundled, "the built bundle's default generation drifted from the committed report"
    assert on_disk["backgrounds"] and on_disk["selected_background"], \
        "the bundled default must carry a real wallpaper, not the palette-only fixture"
    return generation, bundled


def real_light_generation(bundle, state_root, scratch):
    """A freshly prepared real Omarchy theme (Catppuccin Latte) from the
    same bundle's pinned upstream source tree, using the repository's own
    theme-activation pipeline (`tools/theme_activate.prepare`) -- the exact
    code path a real theme swap runs, not a hand-mutated palette fixture."""
    source_root = bundle / "share/omarchy/themes"
    generation, report = prepare(
        "catppuccin-latte",
        source=source_root / "catppuccin-latte",
        state_root=state_root,
        user_themes=scratch / "empty-user-themes",
        builtins=None,
        tools=ROOT / "nix/omarchy-theme-tools/upstream",
    )
    assert report["backgrounds"] and report["selected_background"], \
        "catppuccin-latte must carry a real wallpaper"
    return generation, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("sway", "swaymsg", "rust"):
        parser.add_argument("--" + field, required=True, type=Path)
    parser.add_argument("--theme-bundle", required=True, type=Path,
                        help="built nix/handheld-theme-default store path")
    parser.add_argument("--icons", required=True, type=Path,
                        help="built nix/handheld-theme-icons store path")
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.sway, args.swaymsg, args.rust):
        if not path.is_file():
            parser.error(f"exact cross-built executable must exist: {path}")
    bundle = args.theme_bundle.resolve(strict=True)
    icons_share = args.icons.resolve(strict=True) / "share"
    if not icons_share.is_dir():
        parser.error(f"--icons has no share/ directory: {icons_share}")
    root = args.output
    root.mkdir(mode=0o700, exist_ok=False)
    qemu = str(args.qemu)

    config = root / "sway.conf"
    config.write_text(f"output HEADLESS-1 mode {WIDTH}x{HEIGHT}\nseat seat0 fallback true\n")
    swaymsg_wrapper = root / "swaymsg"
    swaymsg_wrapper.write_text(f"#!/bin/sh\nexec {qemu} {args.swaymsg} \"$@\"\n")
    swaymsg_wrapper.chmod(0o700)

    # --- Interactive-fixture desktop entries: Name/Icon match this image's
    # own real entries exactly (nix/handheld-desktop-entries.nix), so icon
    # resolution below exercises the real bundled icon theme with the real
    # production names, not a private fixture theme. `Exec` is swapped for
    # a controllable marker script -- spawning the real foot/htop/nnn
    # binaries as live Wayland clients inside this headless compositor is
    # out of scope here; this test proves Home's own wiring, which reference
    # launcher already covers separately. Real "foot" has no bundled icon
    # in Yaru either (confirmed against the built icon theme), so "Terminal"
    # is expected to show the initial-letter fallback plate here exactly as
    # it would on the real image today. ---
    data_home = root / "data"
    apps_dir = data_home / "applications"
    apps_dir.mkdir(parents=True)
    marker = root / "launch-marker"
    launch_script = root / "launch"
    launch_script.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$1" >> "$XDG_RUNTIME_DIR/launch-marker"\n'
    )
    launch_script.chmod(0o700)
    (apps_dir / "k230-fixture-terminal.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Terminal\n"
        f"Exec={launch_script} terminal\nIcon=foot\n"
    )
    # Pre-pinned at page 0 slot 0 from boot, so this test can exercise the
    # per-icon remove *badge* tap on an icon that was never dragged, kept
    # distinct from "Fixture Extra" below (pinned live via the drawer, then
    # removed via the older drag-to-Remove-pill flow) so both removal paths
    # are proven in the same rearrange session without interfering.
    (apps_dir / "k230-fixture-badge.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Fixture Badge\n"
        f"Exec={launch_script} badge\nIcon=htop\n"
    )
    # Matches no curated default keyword, so a fresh Home never shows it
    # until it is explicitly pinned from the drawer. No Icon=, proving the
    # initial-letter fallback plate still renders correctly at the new,
    # larger tile size.
    (apps_dir / "k230-fixture-extra.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Fixture Extra\n"
        f"Exec={launch_script} extra\n"
    )
    # A second page's sole occupant, staged directly into the layout file
    # below rather than by pinning 20+ filler apps to fill page 0 -- this
    # test proves paging/rendering across pages, not how many real icons a
    # 4-column grid holds before it needs a second page (home_grid.rs's own
    # unit tests already cover that layout math exactly). Icon=folder
    # matches the real Files entry's own icon name.
    (apps_dir / "k230-fixture-page-two.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Fixture Page Two\n"
        f"Exec={launch_script} page-two\nIcon=folder\n"
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
            ["k230-fixture-badge.desktop", None, None, None],
            ["k230-fixture-page-two.desktop", None, None, None],
        ],
        "dock": ["k230-fixture-terminal.desktop", None, None, None],
    }))

    theme_state = root / "theme-state"
    theme_state.mkdir()
    dark, dark_report = real_dark_generation(bundle)
    light, light_report = real_light_generation(bundle, theme_state, root)

    env = dict(
        os.environ,
        XDG_RUNTIME_DIR=str(root),
        XDG_DATA_HOME=str(data_home),
        XDG_DATA_DIRS=f"{icons_share}:{data_home}",
        XDG_STATE_HOME=str(state_home),
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

    def capture(name, timeout=8.0, stable_frames=6, interval=0.1):
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

    def start_pass(generation, prefix):
        (root / f"{prefix}-rust.log").touch()
        return spawn(prefix + "-rust", [qemu, str(args.rust), "--serve"],
                     {"K230_THEME_DEFAULT_GENERATION": str(generation)})

    def wait_for_ready(prefix):
        # `ready-idle` logs before the compositor has necessarily painted a
        # first real frame; a capture taken immediately after can race a
        # still-uninitialized headless output and "stabilize" on a
        # transient black frame instead of the real one.
        wait_for(lambda: "ready-idle" in text(prefix), 30)
        wait_for(lambda: "wallpaper-commit" in text(prefix) and "home-configure" in text(prefix), 15)
        time.sleep(0.3)

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
        wait_for_ready("dark-rust")

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
        # The drawer lists every desktop entry regardless of Home pin state
        # (sorted case-insensitively by name): "Fixture Badge", "Fixture
        # Extra", "Fixture Page Two", "Terminal" -- so index 1 is "Fixture
        # Extra", the one deliberately left unpinned so this long-press
        # actually adds a new icon (pinning an already-pinned app, like
        # "Fixture Badge" at index 0, is defined as a no-op). The drawer's
        # own tile geometry is navigation.rs's, not home_grid.rs's.
        long_press(*drawer_tile_center(1))
        wait_for(lambda: "home-pinned" in text("dark-rust"), 5)
        checks["drawer_long_press_pinned"] = True
        route("hide")

        pinned = capture("home-dark-pin-flow.png")
        checks["pinned_icon_visible"] = bool(ImageChops.difference(page1, pinned).getbbox())

        # --- Rearrange mode: long-press "Fixture Extra" (now at slot 1;
        # slot 0 holds the pre-pinned "Fixture Badge"). ---
        long_press(*tile_center(1))
        rearranging = capture("home-dark-rearrange.png")
        checks["rearrange_mode_shows_done_remove_and_badges"] = bool(
            ImageChops.difference(pinned, rearranging).getbbox()
        )

        # --- Remove-badge tap: "Fixture Badge" (slot 0) is removed by a
        # single tap on its badge, with no drag at all -- the newer,
        # more-discoverable removal affordance, distinct from the
        # drag-to-Remove-pill flow exercised next. ---
        tap(*tile_plate_corner(0))
        badge_removed = capture("home-dark-badge-removed.png")
        checks["remove_badge_tap_changed_the_screen"] = bool(
            ImageChops.difference(rearranging, badge_removed).getbbox()
        )
        checks["still_rearranging_after_badge_removal"] = bool(
            ImageChops.difference(badge_removed, rearranging).getbbox()
        )

        # --- Drag-to-Remove-pill: "Fixture Extra" is still at slot 1 (badge
        # removal above did not compact slots). A fresh press-and-drag
        # grabs it (already-rearranging jiggle-mode pickup), paused
        # mid-drag over an ordinary empty slot to capture the visible
        # drop-target highlight, then continued onto Remove and released. ---
        drag_id = drag_steps_2d(tile_center(1), tile_center(2))
        drop_target_frame = capture("home-dark-drop-target.png", timeout=1.5, stable_frames=1)
        checks["drop_target_highlight_visible"] = bool(
            ImageChops.difference(badge_removed, drop_target_frame).getbbox()
        )
        remove_x, remove_y = remove_target_point()
        settle_and_release(drag_id, remove_x, remove_y)
        capture("home-dark-removed.png")
        # The authoritative check for both remove flows is the persisted
        # layout file itself, read after the restart below
        # ("removed_from_saved_layout") -- a visual diff here would be
        # fragile (a removed icon's former slot is simply empty grid
        # space, which can look identical to other empty slots).

        # Done exits rearrange mode (a tap on any non-icon point does, per
        # home_screen.rs's own "tap elsewhere stops jiggling" behavior; the
        # Done pill is simply the obvious, labeled place to do it) -- this
        # settled, non-rearranging frame, not `page1` (which still shows the
        # now-removed "Fixture Badge"), is the correct baseline for the
        # restart-stability check below, since both icons removed above are
        # gone from the persisted layout for good.
        tap(*done_button_point())
        settled_after_removals = capture("home-dark-rearrange-done.png")

        # --- Restart proves persistence. ---
        rust.terminate()
        try:
            rust.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rust.kill()
        layout_after_removal = json.dumps(json.loads(home_json.read_text()))
        checks["badge_removed_from_saved_layout"] = "k230-fixture-badge.desktop" not in layout_after_removal
        checks["drag_removed_from_saved_layout"] = "k230-fixture-extra.desktop" not in layout_after_removal
        checks["dock_survives_the_removal"] = "k230-fixture-terminal.desktop" in layout_after_removal

        restarted = start_pass(dark, "dark-restarted")
        wait_for_ready("dark-restarted-rust")
        after_restart = capture("home-dark-after-restart.png")
        checks["stable_after_restart"] = not bool(
            ImageChops.difference(settled_after_removals, after_restart).getbbox()
        )
        restarted.terminate()
        try:
            restarted.wait(timeout=5)
        except subprocess.TimeoutExpired:
            restarted.kill()

        # --- Light pass: headline captures only. ---
        light_rust = start_pass(light, "light")
        wait_for_ready("light-rust")
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

        # --- Showcase pass: a believable, fully-populated Home (not the
        # sparse interactive fixture above), for visual evidence rather than
        # interaction coverage. Every icon here resolves against the real
        # bundled icon theme (`--icons`); the four dock entries' Name/Icon
        # match this image's own real desktop entries plus Settings.
        # Twenty distinct grid apps exactly fill one page
        # (apps_per_page() == 20 at this panel's reference height), so this
        # is what a fully pinned, single-page Home actually looks like, not
        # a half-empty one. ---
        showcase_data = root / "showcase-data"
        showcase_apps = showcase_data / "applications"
        showcase_apps.mkdir(parents=True)
        dock_apps = {
            "terminal": ("Terminal", "foot"),
            "monitor": ("Monitor", "htop"),
            "files": ("Files", "folder"),
            "settings": ("Settings", "gnome-control-center"),
        }
        grid_apps = {
            "editor": ("Text Editor", "accessories-text-editor"),
            "browser": ("Browser", "internet-web-browser"),
            "video": ("Video", "multimedia-video-player"),
            "calculator": ("Calculator", "gnome-calculator"),
            "calendar": ("Calendar", "gnome-calendar"),
            "weather": ("Weather", "gnome-weather"),
            "music": ("Music", "gnome-music"),
            "photos": ("Photos", "gnome-photos"),
            "maps": ("Maps", "gnome-maps"),
            "clocks": ("Clocks", "gnome-clocks"),
            "contacts": ("Contacts", "gnome-contacts"),
            "characters": ("Characters", "gnome-characters"),
            "screenshot": ("Screenshot", "gnome-screenshot"),
            "disks": ("Disks", "gnome-disks"),
            "help": ("Help", "gnome-help"),
            "logs": ("Logs", "gnome-logs"),
            "books": ("Books", "gnome-books"),
            "sysmon": ("System Monitor", "gnome-system-monitor"),
            "filebrowser": ("File Browser", "nautilus"),
            "console": ("Console", "gnome-terminal"),
        }
        assert len(grid_apps) == apps_per_page(), "the showcase page must exactly fill one page"
        for app_id, (label, icon_name) in {**dock_apps, **grid_apps}.items():
            (showcase_apps / f"k230-showcase-{app_id}.desktop").write_text(
                "[Desktop Entry]\nType=Application\n"
                f"Name={label}\nExec=/bin/true {app_id}\nIcon={icon_name}\n"
            )
        showcase_state = root / "showcase-state"
        showcase_json = showcase_state / "k230-shell/home.json"
        showcase_json.parent.mkdir(parents=True)
        showcase_json.write_text(json.dumps({
            "schema": 1,
            "pages": [[f"k230-showcase-{app_id}.desktop" for app_id in grid_apps]],
            "dock": [f"k230-showcase-{app_id}.desktop" for app_id in dock_apps],
        }))
        showcase_env = dict(env, XDG_DATA_HOME=str(showcase_data),
                             XDG_DATA_DIRS=f"{icons_share}:{showcase_data}",
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

        # The showcase catalog decodes 24 real icons on first paint (vs. the
        # interactive fixture's 1-2) -- under qemu-riscv64-static emulation
        # that decode can outlast `wait_for_ready`'s ordinary settle time,
        # so a still-decoding (near-blank) frame can itself sit stable long
        # enough to fool `capture`'s stability heuristic. A previous run of
        # this exact scenario captured a solid black frame this way; this
        # extra settle is deliberately generous rather than tightly tuned.
        showcase_dark = start_showcase(dark, "showcase-dark")
        wait_for_ready("showcase-dark-rust")
        time.sleep(1.5)
        showcase_dark_image = capture("home-dark-showcase.png")
        # A guard against exactly the blank/black-frame race described
        # above ever recurring silently (these captures are otherwise never
        # diffed against anything).
        checks["showcase_dark_is_not_a_blank_frame"] = bool(
            ImageChops.difference(showcase_dark_image, Image.new("RGB", showcase_dark_image.size)).getbbox()
        )
        showcase_dark.terminate()
        try:
            showcase_dark.wait(timeout=5)
        except subprocess.TimeoutExpired:
            showcase_dark.kill()

        showcase_light = start_showcase(light, "showcase-light")
        wait_for_ready("showcase-light-rust")
        time.sleep(1.5)
        showcase_light_image = capture("home-light-showcase.png")
        checks["showcase_light_is_not_a_blank_frame"] = bool(
            ImageChops.difference(showcase_light_image, Image.new("RGB", showcase_light_image.size)).getbbox()
        )
        showcase_light.terminate()
        try:
            showcase_light.wait(timeout=5)
        except subprocess.TimeoutExpired:
            showcase_light.kill()

        failed = [name for name, ok in checks.items() if not ok]
        assert not failed, f"failed checks: {failed}"
        result = {"result": "PASS", "class": "headless-qemu-native-touch",
                  "checks": checks, "sway": str(args.sway), "rust": str(args.rust),
                  "theme_bundle": str(bundle), "icons": str(args.icons),
                  "dark_generation": dark_report["generation"],
                  "dark_selected_background": dark_report["selected_background"],
                  "light_generation": light_report["generation"],
                  "light_selected_background": light_report["selected_background"]}
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

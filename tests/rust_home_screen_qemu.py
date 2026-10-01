#!/usr/bin/env python3
"""Headless QEMU proof of the pinned Home screen, updated to the drag-to-
place contract (`openspec/changes/the-home-screen-has-widgets-and-folders`):
page swipe, dock tap launch, long-press-*drag* from the drawer (not the old
instant pin -- a genuine held-then-dragged-then-released placement, with a
captured mid-drag frame), folder creation (drag an app onto another app, in
the grid and in the dock), opening a folder and launching a member from it,
the widget-picker sheet (long-press empty Home space; Widgets page; a
long-press-drag placing a Clock widget), rearrange (the drag-to-Remove-pill
flow and the per-icon remove-badge tap), and persistence across a restart --
captured under a dark and a light theme, each with a real Omarchy wallpaper,
a real bundled icon theme, and (for the interactive scenarios) desktop
entries whose Name/Icon exactly match this image's own real ones
(`nix/handheld-desktop-entries.nix`). Also proves folder rename through a
real `zwp_virtual_keyboard_v1` connection (the same technique `tests/
rust_wifi_settings_qemu.py` already uses for the Wi-Fi password field,
`RenameKeyboard` below -- a minimal fixed keymap, not the full on-screen
layout); with `--wvkbd`, the real cross-built `wvkbd-mobintl` is *also*
shown through `k230-keyboard-gesture-signal` (the same helper
`ShellClient::sync_home_keyboard` invokes for `K230_KEYBOARD_SIGNAL`) so
that signal path is exercised too, not just the key input.

Synthetic touch injection (card_shell test-touch) and a private desktop
catalog; never physical panel evidence. This proves wiring/layout under
QEMU's headless Pixman backend, not real-glass touch feel, contrast, or
panel readability -- see
openspec/changes/the-home-screen-has-widgets-and-folders/tasks.md's
board-acceptance task for what remains open.
"""
import argparse
import array
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


class RenameKeyboard:
    """A real `zwp_virtual_keyboard_v1` connection, the same technique
    `tests/card_virtual_keyboard.py::Keyboard` already uses for the Wi-Fi
    password field, extended with a second mapped key (Return, so a rename
    can actually be *committed* -- task 2: "Enter commits") -- kept local to
    this script rather than changing that shared, already-used-elsewhere
    utility's fixed single-key keymap."""

    def __init__(self, path):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(10)
        self.socket.connect(str(path))
        self.serial = 2
        self.globals = {}
        self.send(1, 1, struct.pack('=I', 2))  # wl_display.get_registry
        self.roundtrip()
        self.bind('zwp_virtual_keyboard_manager_v1', 4)
        self.bind('wl_seat', 5)
        self.send(4, 0, struct.pack('=II', 5, 6))
        self.serial = 6
        # xkb keycode = evdev keycode + 8. <AC01>=38 ('a', evdev 30) and
        # <RTRN>=36 (Return, evdev 28) are the only two keys this probe ever
        # sends -- enough to type a distinguishable rename and commit it.
        keymap = b'''xkb_keymap {
xkb_keycodes "probe" { minimum=8; maximum=255; <AC01>=38; <RTRN>=36; <BKSP>=22; };
xkb_types "probe" { type "ONE_LEVEL" { modifiers=None; map[None]=Level1; level_name[Level1]="Any"; }; };
xkb_compatibility "probe" {};
xkb_symbols "probe" { key <AC01> { type="ONE_LEVEL", [ a ] }; key <RTRN> { type="ONE_LEVEL", [ Return ] }; key <BKSP> { type="ONE_LEVEL", [ BackSpace ] }; };
};\0'''
        fd = os.memfd_create('home-test-keymap', os.MFD_CLOEXEC)
        try:
            os.write(fd, keymap)
            self.send(6, 0, struct.pack('=II', 1, len(keymap)), fd)
        finally:
            os.close(fd)
        self.roundtrip()

    def send(self, obj, opcode, payload=b'', fd=None):
        message = struct.pack('=II', obj, ((len(payload) + 8) << 16) | opcode) + payload
        if fd is None:
            self.socket.sendall(message)
        else:
            sent = self.socket.sendmsg([message], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))])
            assert sent == len(message)

    def read(self, n):
        data = b''
        while len(data) < n:
            chunk = self.socket.recv(n - len(data))
            assert chunk, 'Wayland test connection closed'
            data += chunk
        return data

    def roundtrip(self):
        self.serial += 1
        callback = self.serial
        self.send(1, 0, struct.pack('=I', callback))
        while True:
            obj, size_op = struct.unpack('=II', self.read(8))
            size, opcode = size_op >> 16, size_op & 0xffff
            payload = self.read(size - 8)
            assert not (obj == 1 and opcode == 0), ('Wayland protocol error', payload)
            if obj == 2 and opcode == 0:
                name, length = struct.unpack('=II', payload[:8])
                interface = payload[8:8 + length - 1].decode()
                self.globals[interface] = name
            if obj == callback and opcode == 0:
                return

    def bind(self, interface, obj):
        encoded = interface.encode() + b'\0'
        padded = encoded + b'\0' * ((-len(encoded)) % 4)
        self.send(2, 0, struct.pack('=II', self.globals[interface], len(encoded)) + padded + struct.pack('=II', 1, obj))

    def press(self, evdev_keycode=30):
        stamp = int(time.monotonic() * 1000) & 0xffffffff
        self.send(6, 1, struct.pack('=III', stamp, evdev_keycode, 1))
        self.send(6, 1, struct.pack('=III', stamp, evdev_keycode, 0))
        self.roundtrip()

    def press_a(self):
        self.press(30)

    def press_enter(self):
        self.press(28)

    def close(self):
        self.socket.close()

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


# Mirrors home_grid.rs's own folder-overlay/widget-picker geometry exactly
# (both share one centered card region, `folder_overlay_rect`/`picker_rect`)
# -- these are the same formulas `home_grid.rs`'s own unit tests already
# verify, re-derived here only so this black-box script can compute exact
# tap points.
CARD_SIDE_MARGIN = SIDE_MARGIN * 1.5
FOLDER_NAME_HEIGHT = 56.0
PICKER_ROW_HEIGHT = 92.0
PICKER_ROW_GAP = 14.0
PICKER_TOP_PAD = 20.0


def overlay_card_rect():
    """home_grid::folder_overlay_rect / picker_rect -- the one centered card
    region an open folder and the widget-picker sheet both use (never shown
    at once)."""
    x = CARD_SIDE_MARGIN
    y = GRID_TOP
    w = WIDTH - 2 * x
    h = HEIGHT - y - DOCK_HEIGHT - DOTS_HEIGHT
    return (x, y, w, h)


def folder_name_rect():
    x, y, w, _ = overlay_card_rect()
    return (x, y, w, FOLDER_NAME_HEIGHT)


def folder_name_center():
    x, y, w, h = folder_name_rect()
    return (x + w / 2.0, y + h / 2.0)


def folder_app_rect(index):
    card_x, card_y, card_w, _ = overlay_card_rect()
    grid_top = card_y + FOLDER_NAME_HEIGHT + 12.0
    column = index % COLUMNS
    row = index // COLUMNS
    w = (card_w - 2 * TILE_GAP) / COLUMNS - TILE_GAP
    x = card_x + TILE_GAP + column * (w + TILE_GAP)
    return (x, grid_top + row * ROW_HEIGHT, w, ROW_HEIGHT - TILE_GAP)


def folder_app_center(index):
    x, y, w, h = folder_app_rect(index)
    return (x + w / 2.0, y + h / 2.0)


def picker_row_rect(index):
    x, y, w, _ = overlay_card_rect()
    return (x + 16.0, y + PICKER_TOP_PAD + index * (PICKER_ROW_HEIGHT + PICKER_ROW_GAP), w - 32.0, PICKER_ROW_HEIGHT)


def picker_row_center(index):
    x, y, w, h = picker_row_rect(index)
    return (x + w / 2.0, y + h / 2.0)


def empty_home_space_point():
    """A point that resolves to an addressable-but-empty Home grid cell
    (task: "long-press empty Home space") which, released with zero motion
    (this script's own `long_press` helper), does *not* also coincide with
    any widget-picker Menu row once the sheet opens there -- the picker's 3
    Menu rows all sit within the grid's own first row band, so this
    deliberately picks a much lower row (row 4 of 5) to stay clear of them."""
    return tile_center(4 * COLUMNS)


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
    """Mirrors navigation.rs's own *current* drawer tile geometry exactly
    (`docs/design/app-drawer-review.md`'s redesign: COLUMNS=4, a 24px side
    margin and 24px tile gap -- deliberately equal -- a 110px row/tile
    pitch, and `list_top = panel_top(32) + TOP_CHROME_HEIGHT(86) = 118`).
    This function's own previous formula (COLUMNS=3, a 160px row pitch, and
    `list_top = height*0.19 + 181`) was stale against that redesign --
    confirmed live via `K230_DEBUG_LONG_PRESS` diagnostic logging added
    while developing task 1's drag contract, where it resolved to no tile
    at all (`tile_at` returning `None`) even though the touch itself
    reached the drawer correctly."""
    side_margin, gap, columns, row_height = 24.0, 24.0, 4, 110.0
    list_top = 32.0 + 86.0
    tile_width = (WIDTH - 2 * side_margin - (columns - 1) * gap) / columns
    column = index % columns
    row = index // columns
    x = side_margin + column * (tile_width + gap)
    y = list_top + row * row_height
    return (x + tile_width / 2.0, y + row_height / 2.0)


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
    parser.add_argument("--rename-client", type=Path, help="keep a normal app behind Home during keyboard rename")
    parser.add_argument("--rename-only", action="store_true", help="stop after keyboard rename over an ordinary app")
    parser.add_argument("--fluid-only", action="store_true", help="only live cross-page and widget-layout scenarios")
    parser.add_argument("--actions-only", action="store_true", help="right-click actions, existing-window focus and preserved touch grabs")
    for field in ("sway", "swaymsg", "rust"):
        parser.add_argument("--" + field, required=True, type=Path)
    parser.add_argument("--theme-bundle", required=True, type=Path,
                        help="built nix/handheld-theme-default store path")
    parser.add_argument("--icons", required=True, type=Path,
                        help="built nix/handheld-theme-icons store path")
    parser.add_argument("--client", type=Path, help="native Wayland probe; enables running-app navigation checks")
    parser.add_argument("--wvkbd", type=Path,
                        help="cross-built wvkbd-mobintl; enables the folder-rename real-keyboard scenario")
    parser.add_argument("--qemu", default="/usr/bin/qemu-riscv64-static")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.actions_only and (not args.client or args.fluid_only or args.rename_only):
        parser.error("--actions-only requires --client and cannot combine with other restricted passes")
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
    config.write_text(f"output HEADLESS-1 mode {WIDTH}x{HEIGHT}\nseat seat0 fallback true\n"
                      'for_window [app_id="^k230.card."] card_shell ordinary, floating enable, border none, resize set 100 ppt 100 ppt, move position 0 0\n')
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
        f"Exec={launch_script} terminal\nIcon=foot\nStartupWMClass=k230.card.one\n"
    )
    if args.actions_only:
        with (apps_dir / "k230-fixture-terminal.desktop").open("a") as desktop:
            desktop.write(
                "Actions=new-window;preferences;\n"
                "[Desktop Action new-window]\nName=New Window\n"
                f"Exec={args.client} --app-id k230.card.one\n"
                "[Desktop Action preferences]\nName=Preferences\n"
                f"Exec={launch_script} preferences\n"
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

    # Matches `nix/shell.nix`'s real `k230-keyboard-gesture-signal` with one
    # deliberate difference: `-f` (full command line), not `-x` (exact
    # `comm`) -- under `qemu-riscv64-static` the process the kernel sees is
    # the *emulator*, `comm` is `qemu-riscv64-st`, not `wvkbd-mobintl`, only
    # its argv still names the guest binary. Harmless (a no-op `pkill`) when
    # no such process exists, which is every pass except the optional
    # `--wvkbd` one at the very end -- `sync_home_keyboard`'s own signal
    # spawn is fire-and-forget and does not gate the key-input scenario on
    # this script actually finding anything to signal.
    signal_script = root / "keyboard-signal"
    signal_script.write_text(
        "#!/bin/sh\nset -eu\ncase \"${1:-}\" in\n"
        "  show) signal=USR2 ;;\n  hide) signal=USR1 ;;\n  *) exit 2 ;;\nesac\n"
        "exec pkill -\"$signal\" -u \"$(id -u)\" -f wvkbd-mobintl\n"
    )
    signal_script.chmod(0o700)

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
        K230_KEYBOARD_SIGNAL=str(signal_script),
        K230_KEYBOARD_HEIGHT="400",
    )

    helper = root / "surface-helper"
    helper.write_text(f'#!/bin/sh\nexec {qemu} {args.rust} "$@"\n')
    helper.chmod(0o700)
    env["SWAY_K230_CARD_SURFACE_HELPER"] = str(helper)
    env["SWAY_K230_CARD_REVEAL_STREAM"] = "1"

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

    def count_log(name, needle):
        return text(name).count(needle)

    def wait_for_new_log_line(name, needle, baseline, seconds=15):
        """Several drag/drop actions in this script reuse the same
        `needle` (e.g. "home-layout-changed") against the same long-running
        process's log more than once -- a plain `needle in text(...)` would
        trivially already be true from an *earlier* action. This instead
        waits for the *count* of occurrences to rise past whatever it was
        (`baseline`, sampled by the caller right before the action)."""
        wait_for(lambda: count_log(name, needle) > baseline, seconds)

    def ipc(command, kind=0):
        with socket.socket(socket.AF_UNIX) as stream:
            stream.settimeout(10)
            stream.connect(str(next(root.glob("sway-ipc.*.sock"))))
            payload = command.encode()
            stream.sendall(b"i3-ipc" + struct.pack("=II", len(payload), kind) + payload)

            def read(count):
                data = b""
                while len(data) < count:
                    chunk = stream.recv(count - len(data))
                    assert chunk, "Sway IPC closed"
                    data += chunk
                return data

            length, _ = struct.unpack("=II", read(14)[6:])
            answer = json.loads(read(length))
            if kind == 0:
                assert all(row["success"] for row in answer), (command, answer)
            return answer

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

    def long_press_drag(start, end, hold_seconds=0.65, steps=6):
        """Task 1/task 3's own drag-to-place contract: holds in place at
        `start` past LONG_PRESS_MS (arming a live drag -- `navigation::
        DrawerNavigation::take_long_press_drag` for a drawer tile,
        `HomeScreen::tick`'s own long-press timer for an on-Home icon, an
        open folder's member, or a widget-picker preview row), *then*
        drags to `end` -- never releasing in between, unlike `long_press`
        (a tap-length hold) followed by a separate `drag_steps_2d` (which
        would release and re-press, missing the live-drag window
        entirely). Returns the live contact id for the caller's own
        `settle_and_release`."""
        nonlocal contact
        this_contact = contact
        contact += 1
        ipc(f"card_shell test-touch down {this_contact} {start[0]} {start[1]}")
        time.sleep(hold_seconds)
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
            if stable_frames == 0:
                return current
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

        if not args.fluid_only:
            # --- Dark pass: full sequence. ---
            rust = start_pass(dark, "dark")
            wait_for_ready("dark-rust")

            page1 = capture("home-dark-page1.png")
            if args.actions_only:
                from home_app_actions_scenario import exercise_actions
                checks.update(exercise_actions(args.client, spawn, ipc, wait_for,
                              tap, capture, route, dock_center, tile_center,
                              drawer_tile_center, long_press_drag, settle_and_release,
                              done_button_point, home_json, marker, lambda: text("dark-rust")))
                assert all(checks.values()), checks
                result = {"result": "PASS", "class": "headless-qemu-injected-touch-and-pointer",
                          "checks": checks, "sway": str(args.sway), "rust": str(args.rust),
                          "theme_bundle": str(bundle), "icons": str(args.icons)}
                (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result, indent=2))
                return
            if args.client:
                from home_navigation_scenario import exercise_navigation
                checks.update(exercise_navigation(args.client, spawn, ipc, wait_for,
                              drag_steps_2d, settle_and_release, tap, capture, route, dock_center))

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
            # Extra", the one deliberately left unpinned so this drag actually
            # adds a new icon. The drawer's own tile geometry is
            # navigation.rs's, not home_grid.rs's.
            #
            # Task 1's drag-to-place contract, not the old instant pin: holding
            # past LONG_PRESS_MS arms a live drag (`navigation::
            # DrawerNavigation::take_long_press_drag`, tick-driven) and reveals
            # Home underneath; a mid-drag frame is captured here, over an
            # ordinary empty Home cell, before the touch is dragged the rest of
            # the way to slot 1 and released.
            drag_target = tile_center(1)
            drag_id = long_press_drag(drawer_tile_center(1), drag_target)
            wait_for(lambda: "home-drag-begin" in text("dark-rust"), 5)
            mid_drag = capture("home-dark-mid-drag.png", timeout=2.0, stable_frames=1)
            checks["mid_drag_differs_from_drawer"] = bool(
                ImageChops.difference(drawer_open, mid_drag).getbbox()
            )
            settle_and_release(drag_id, *drag_target)
            wait_for(lambda: "home-drag-placed" in text("dark-rust"), 5)
            checks["drawer_long_press_dragged_and_placed"] = True

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

            # --- New scenarios, on this same restarted process: folder
            # creation (drag onto an existing app, in the grid and in the
            # dock), opening a folder, renaming it through a real virtual
            # keyboard, launching a member from it, and the widget-picker
            # sheet. Kept *after* the restart-persistence checks above so
            # none of this touches what those checks assert about the badge/
            # extra/terminal entries. ---
            wl_socket = root / env["WAYLAND_DISPLAY"]

            def open_drawer_and_settle(prefix, reopen=False):
                """`route("drawer")` alone only *requests* the route change; the
                very first drag scenario above reached a settled drawer by
                following it with a `capture()` (which waits for visual
                stability). This does the equivalent without a screenshot, for
                spots that do not need one -- waiting for a fresh
                `"commit"` line plus a short grace period, so a
                long-press-drag's own `down` is never injected before the
                drawer's input region is actually live (confirmed live:
                without this, an immediate drag after `route("drawer")`
                silently reached Home's own surface instead, the same bug
                class `panel_input_rect`'s own fix just above addressed).

                `reopen=True` additionally waits for the drawer's *previous*
                instance to actually `unmap` first: after a successful
                drag-and-drop, `end_drawer_home_drag` starts an animated close
                (`begin_animated_close`) rather than unmapping synchronously,
                and re-requesting the "drawer" route while `self.layer` still
                exists is a no-op (`ensure_layer`'s own early return) -- it
                produces no new frame at all for the plain check above to wait
                on, so a caller re-opening the drawer after a prior drop must
                wait for that close to actually finish first.

                The settle signal itself is a fresh `"commit"` line, not
                `K230_DRAWER_FRAME`: `main.rs`'s own `K230_DRAWER_FRAME` sample
                is deliberately rate-limited to one line per
                `DRAWER_FRAME_LOG_INTERVAL` (500ms) of *wall-clock* time, not
                per route-enter -- a close-then-reopen cycle that lands inside
                that window (routine here: the prior drag's own live-follow
                redraws the drawer at up to 60Hz right up until the drop, so
                `drawer_frame_log_at` is already recent when the very next
                open's first frame renders) can suppress the reopen's
                `K230_DRAWER_FRAME` line forever, since nothing else forces a
                further redraw once the drawer is sitting idle. `"commit"` has
                no such gate -- `ShellClient::draw()` logs it unconditionally
                on every call, for every route -- and `show()` itself calls
                `draw()` synchronously before the route request's `OK` reply
                is even written, so a fresh `"commit"` line is guaranteed the
                moment the request lands, independent of the frame-timing
                sample's own throttling."""
                if reopen:
                    unmap_baseline = count_log(prefix, "unmap")
                    wait_for_new_log_line(prefix, "unmap", unmap_baseline, seconds=15)
                baseline = count_log(prefix, "commit")
                route("drawer")
                wait_for_new_log_line(prefix, "commit", baseline, seconds=15)
                time.sleep(0.4)

            # "Fixture Badge" (drawer) onto an empty page-1 cell.
            open_drawer_and_settle("dark-restarted-rust")
            badge_target = tile_center(0)
            baseline = count_log("dark-restarted-rust", "home-drag-placed")
            begin_baseline = count_log("dark-restarted-rust", "home-drag-begin")
            badge_drag = long_press_drag(drawer_tile_center(0), badge_target)
            wait_for_new_log_line("dark-restarted-rust", "home-drag-begin", begin_baseline)
            settle_and_release(badge_drag, *badge_target)
            wait_for_new_log_line("dark-restarted-rust", "home-drag-placed", baseline)

            # "Fixture Extra" (drawer) dragged directly onto that same cell --
            # task: "Dropping on an existing app creates a folder."
            open_drawer_and_settle("dark-restarted-rust", reopen=True)
            baseline = count_log("dark-restarted-rust", "home-drag-begin")
            extra_drag = long_press_drag(drawer_tile_center(1), badge_target)
            wait_for_new_log_line("dark-restarted-rust", "home-drag-begin", baseline)
            mid_folder_drag = capture("home-dark-folder-mid-drag.png", timeout=2.0, stable_frames=1)
            baseline = count_log("dark-restarted-rust", "home-drag-placed")
            settle_and_release(extra_drag, *badge_target)
            wait_for_new_log_line("dark-restarted-rust", "home-drag-placed", baseline)
            folder_created = capture("home-dark-folder-created.png")
            checks["dragging_onto_an_app_created_a_folder"] = bool(
                ImageChops.difference(mid_folder_drag, folder_created).getbbox()
            )

            # Open the folder (folder.apps == [existing "Fixture Badge",
            # dragged "Fixture Extra"] -- merge_two's own order, home_screen.rs).
            tap(*badge_target)
            folder_open = capture("home-dark-folder-open.png")
            checks["folder_opened"] = bool(
                ImageChops.difference(folder_created, folder_open).getbbox()
            )

            # Rename it through a real virtual-keyboard-v1 connection (task 2):
            # tap the name, wait for focus, type, press Enter, and read the
            # committed name back from the persisted layout.
            # A headless seat has no keyboard capability until this client binds
            # its virtual keyboard. Create it before requesting/waiting for focus;
            # otherwise the harness waits for an enter event that cannot exist.
            rename_background = None
            if args.rename_client:
                rename_background = spawn("rename-background-app", [str(args.rename_client), "--app-id", "k230.card.one"])
                def has_background(node):
                    return (node.get("app_id") == "k230.card.one" or
                            any(has_background(child) for child in node.get("nodes", []) + node.get("floating_nodes", [])))
                wait_for(lambda: has_background(ipc("", 4)))
                ipc("card_shell home")
                time.sleep(0.3)
            rename_keyboard = RenameKeyboard(wl_socket)
            wait_for(lambda: "keyboard-capability" in text("dark-restarted-rust"), 5)
            tap(*folder_name_center())
            wait_for(lambda: "home-keyboard-focus-granted" in text("dark-restarted-rust"), 5)
            renaming = capture("home-dark-folder-rename.png", timeout=2.0, stable_frames=1)
            checks["folder_rename_keyboard_focus_granted"] = True
            try:
                for _ in range(len("Folder")):
                    rename_keyboard.press(14)
                for _ in range(4):
                    rename_keyboard.press_a()
                baseline = count_log("dark-restarted-rust", "home-layout-changed")
                rename_keyboard.press_enter()
            finally:
                rename_keyboard.close()
            wait_for_new_log_line("dark-restarted-rust", "home-layout-changed", baseline)
            renamed_layout = json.loads(home_json.read_text())
            renamed_folder_name = next(
                (item.get("name") for page in renamed_layout["pages"] for item in page
                 if item and item.get("kind") == "folder"),
                None,
            )
            checks["folder_renamed_via_real_keyboard"] = renamed_folder_name == "aaaa"
            if rename_background:
                checks["home_remains_selected_after_keyboard_rename_over_app"] = (
                    "home_selected=1 " in ipc("card_shell debug-scene")[0]["error"])
                rename_background.terminate()
                rename_background.wait(timeout=5)
            after_rename = capture("home-dark-folder-renamed.png")
            if args.rename_only:
                assert args.rename_client, "--rename-only requires --rename-client"
                assert all(checks.values()), checks
                result = {"result": "PASS", "class": "headless-qemu-real-wayland-app-and-virtual-keyboard",
                          "checks": checks, "sway": str(args.sway), "rust": str(args.rust),
                          "rename_client": str(args.rename_client)}
                (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result, indent=2))
                return
            checks["folder_rename_visible"] = bool(
                ImageChops.difference(renaming, after_rename).getbbox()
            )

            # Drag one member out of the open folder onto an empty Home cell.
            # The persisted layout, rather than image differences, proves the
            # member moved and the remaining one-item folder was unwrapped.
            baseline = count_log("dark-restarted-rust", "home-layout-changed")
            member_drag = long_press_drag(folder_app_center(1), tile_center(4))
            settle_and_release(member_drag, *tile_center(4))
            wait_for_new_log_line("dark-restarted-rust", "home-layout-changed", baseline)
            extracted = json.loads(home_json.read_text())
            checks["folder_member_dragged_out"] = (
                extracted["pages"][0][4] == {"kind": "app", "id": "k230-fixture-extra.desktop"}
            )
            capture("home-dark-folder-member-extracted.png")

            # Recreate/open a folder so the following launch scenario remains
            # about a member of an open folder, rather than a bare Home icon.
            baseline = count_log("dark-restarted-rust", "home-layout-changed")
            recreate = long_press_drag(tile_center(4), badge_target)
            settle_and_release(recreate, *badge_target)
            wait_for_new_log_line("dark-restarted-rust", "home-layout-changed", baseline)
            tap(*done_button_point())
            tap(*badge_target)
            capture("home-dark-folder-reopened.png")

            # Tap "Fixture Badge" (member 0) to launch it; the overlay closes.
            tap(*folder_app_center(0))
            wait_for(lambda: "app-launch-requested" in text("dark-restarted-rust")
                     or "app-launch-failed" in text("dark-restarted-rust"), 8)
            checks["folder_member_launch_requested"] = "app-launch-requested" in text("dark-restarted-rust")

            # --- Dock folder: swipe to page 2, drag "Fixture Page Two" onto
            # the dock's own "Terminal" slot -- task: "I can have folders in
            # the dock bar in theory." ---
            swipe_y_pos = swipe_y()
            page2_start_x = WIDTH - SWIPE_MARGIN
            page2_end_x = page2_start_x - SWIPE_DISTANCE
            swipe_id = drag_steps(page2_start_x, page2_end_x, swipe_y_pos)
            settle_and_release(swipe_id, page2_end_x, swipe_y_pos)
            page_two = capture("home-dark-page-two-restarted.png")

            dock_target = dock_center(0)
            baseline = count_log("dark-restarted-rust", "home-layout-changed")
            dock_drag = long_press_drag(tile_center(0), dock_target)
            settle_and_release(dock_drag, *dock_target)
            wait_for_new_log_line("dark-restarted-rust", "home-layout-changed", baseline)
            dock_folder = capture("home-dark-dock-folder.png")
            checks["dock_folder_created"] = bool(
                ImageChops.difference(page_two, dock_folder).getbbox()
            )

            # --- Widget picker: swipe back to page 1, long-press empty Home
            # space, navigate to Widgets, long-press-drag a Clock widget onto
            # an empty cell. ---
            back_id = drag_steps(page2_end_x, page2_start_x, swipe_y_pos)
            settle_and_release(back_id, page2_start_x, swipe_y_pos)
            capture("home-dark-back-to-page-one-restarted.png")

            empty_point = empty_home_space_point()
            long_press(*empty_point)
            picker_menu = capture("home-dark-picker-menu.png")
            checks["widget_picker_menu_opened"] = bool(
                ImageChops.difference(dock_folder, picker_menu).getbbox()
            )
            tap(*picker_row_center(0))  # "Widgets"
            picker_widgets = capture("home-dark-picker-widgets.png")
            checks["widget_picker_widgets_page_differs_from_menu"] = bool(
                ImageChops.difference(picker_menu, picker_widgets).getbbox()
            )
            widget_target = tile_center(2 * COLUMNS)  # row 2: two clear rows for the 4x2 Clock
            baseline = count_log("dark-restarted-rust", "home-layout-changed")
            widget_drag = long_press_drag(picker_row_center(1), widget_target)  # row 1 == Clock
            settle_and_release(widget_drag, *widget_target)
            wait_for_new_log_line("dark-restarted-rust", "home-layout-changed", baseline)
            clock_placed = capture("home-dark-clock-widget-placed.png")
            checks["clock_widget_placed"] = bool(
                ImageChops.difference(picker_widgets, clock_placed).getbbox()
            )

            restarted.terminate()
            try:
                restarted.wait(timeout=5)
            except subprocess.TimeoutExpired:
                restarted.kill()

            if args.wvkbd:
                # Bonus, not load-bearing for any `checks` entry above: proves
                # the real cross-built wvkbd-mobintl actually shows through
                # `k230-keyboard-gesture-signal` while Home's own rename field
                # holds keyboard focus, exactly like `sync_wifi_keyboard`
                # already does for the Wi-Fi password field (`tests/
                # rust_overlay_keyboard_resize_qemu.py`). Starts against the
                # same persisted `home.json` the scenario above just left
                # behind (a real folder, "aaaa", already at page-1 slot 0), so
                # this only needs to reopen it -- no fresh drag/folder-create
                # needed to reach the same rename field.
                wvkbd_pass = start_pass(dark, "wvkbd-dark")
                wait_for_ready("wvkbd-dark-rust")
                wvkbd_target = tile_center(0)
                tap(*wvkbd_target)
                tap(*folder_name_center())
                wait_for(lambda: "home-keyboard-focus-granted" in text("wvkbd-dark-rust"), 5)
                keyboard_hidden = capture("home-dark-wvkbd-hidden.png", timeout=2.0, stable_frames=1)
                wvkbd_log = (root / "wvkbd.log").open("w")
                wvkbd_process = subprocess.Popen(
                    [qemu, str(args.wvkbd), "-H", "400"], env=env,
                    stdout=wvkbd_log, stderr=wvkbd_log)
                processes.append(wvkbd_process)
                time.sleep(1.0)
                keyboard_shown = capture("home-dark-wvkbd-shown.png", timeout=3.0, stable_frames=1)
                checks["wvkbd_shown_alongside_home_rename"] = bool(
                    ImageChops.difference(keyboard_hidden, keyboard_shown).getbbox()
                )
                wvkbd_process.terminate()
                try:
                    wvkbd_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    wvkbd_process.kill()
                wvkbd_pass.terminate()
                try:
                    wvkbd_pass.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    wvkbd_pass.kill()

            # --- Light pass: headline captures only. ---
            # Moving the sole page-2 app into the dock prunes the empty second
            # page. Restore a real second page before testing light-theme paging.
            light_layout = json.loads(home_json.read_text())
            light_layout["pages"].append([
                {"kind": "app", "id": "k230-fixture-page-two.desktop"}
            ] + [None] * 19)
            home_json.write_text(json.dumps(light_layout))
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

        # A fresh, isolated layout exercises the live cross-page driver.
        # Holding one contact proves repeat turns and last-edge page creation;
        # a separate fast motion ending outside the edge band proves fling.
        def fluid_layout():
            pages = [[None] * 20 for _ in range(3)]
            pages[0][0] = {"kind": "app", "id": "k230-fixture-badge.desktop"}
            pages[0][8] = {"kind": "widget", "widget": "clock"}
            pages[1][8] = {"kind": "widget", "widget": "clock_minimal"}
            pages[2][8] = {"kind": "widget", "widget": "clock_dot_matrix"}
            pages[2][0] = {"kind": "widget", "widget": "clock_analog"}
            pages[2][2] = {"kind": "widget", "widget": "weather"}
            return {"schema": 2, "columns": 4, "pages": pages, "dock": [None] * 4}

        home_json.write_text(json.dumps(fluid_layout()))
        fluid = start_pass(dark, "fluid-dwell")
        wait_for_ready("fluid-dwell-rust")
        capture("home-fluid-clock-bubble.png")
        edge_drag = long_press_drag(tile_center(0), (WIDTH - 10, tile_center(0)[1]), steps=1)
        # Native compositor captures are taken with the same contact held.
        time.sleep(0.15)
        capture("home-fluid-edge-indicator.png", stable_frames=0)
        time.sleep(1.6)
        capture("home-fluid-last-edge-new-page.png", stable_frames=0)
        ipc(f"card_shell test-touch motion {edge_drag} {tile_center(4)[0]} {tile_center(4)[1]}")
        time.sleep(0.1)
        baseline = count_log("fluid-dwell-rust", "home-layout-changed")
        settle_and_release(edge_drag, *tile_center(4))
        wait_for_new_log_line("fluid-dwell-rust", "home-layout-changed", baseline)
        paged = json.loads(home_json.read_text())
        badge_page = next(i for i, page in enumerate(paged["pages"])
                          if {"kind": "app", "id": "k230-fixture-badge.desktop"} in page)
        checks["edge_dwell_repeats_and_creates_a_new_page"] = badge_page >= 3
        checks["cross_page_release_keeps_the_item_on_the_visible_page"] = badge_page >= 3
        capture("home-fluid-new-page-drop.png")
        fluid.terminate(); fluid.wait(timeout=5)

        home_json.write_text(json.dumps(fluid_layout()))
        fluid = start_pass(dark, "fluid-fling")
        wait_for_ready("fluid-fling-rust")
        # One fast displacement remains well outside the 40px edge band.
        fling = long_press_drag(tile_center(0), (400, tile_center(0)[1]), steps=1)
        time.sleep(0.25)
        ipc(f"card_shell test-touch motion {fling} {tile_center(4)[0]} {tile_center(4)[1]}")
        baseline = count_log("fluid-fling-rust", "home-layout-changed")
        settle_and_release(fling, *tile_center(4))
        wait_for_new_log_line("fluid-fling-rust", "home-layout-changed", baseline)
        flung = json.loads(home_json.read_text())
        checks["fling_pages_without_an_edge_dwell"] = (
            {"kind": "app", "id": "k230-fixture-badge.desktop"} in flung["pages"][1])
        capture("home-fluid-clock-thin-fling.png")
        fluid.terminate(); fluid.wait(timeout=5)
        # Start the runtime on the widget-rich page explicitly. A screenshot
        # immediately after a swipe is not a reliable assertion of which
        # persisted page supplied the widgets; this fixture makes that exact.
        widget_layout = fluid_layout()
        widget_layout["pages"] = [widget_layout["pages"][2]]
        home_json.write_text(json.dumps(widget_layout))
        fluid = start_pass(dark, "fluid-widget-layout")
        wait_for_ready("fluid-widget-layout-rust")
        capture("home-fluid-analog-dot-matrix-weather.png")
        fluid.terminate(); fluid.wait(timeout=5)

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
        result = {"result": "PASS", "class": "headless-qemu-native-touch-and-virtual-keyboard",
                  "checks": checks, "sway": str(args.sway), "rust": str(args.rust),
                  "theme_bundle": str(bundle), "icons": str(args.icons),
                  "wvkbd": str(args.wvkbd) if args.wvkbd else None,
                  "dark_generation": dark_report["generation"],
                  "dark_selected_background": dark_report["selected_background"],
                  "light_generation": light_report["generation"],
                  "light_selected_background": light_report["selected_background"]}
        (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        print("PASS paired Sway/Rust Home screen QEMU touch (drag-to-place, folders, "
              "widget picker) plus a real virtual-keyboard folder rename; synthetic "
              "backend, no physical touch")
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

## 1. Persistence: `HomeItem`, schema 2, migration

- [x] 1.1 Replace `HomeLayout`'s bare `Option<String>` cells with
  `HomeItem` (App/Folder/Widget), bump `SCHEMA` to 2, and migrate a schema-1
  file on load without rewriting it until the next save; verify with
  `cargo test --offline -p k230-shell-rust home_state`. Done: 20 unit
  tests, including round-trip and schema-1 migration.
- [x] 1.2 Span-aware occupancy (`covered_slots`/`occupied`/`fits`) so a
  multi-cell widget blocks every cell of its own footprint, and
  `HomeLayout::anchor_at` resolves any covered cell back to its widget's
  anchor; verify with the same `home_state` test run (widget-placement and
  `anchor_at` cases included above).
- [x] 1.3 Fresh-install seeding places one Clock widget alongside the
  existing curated app defaults; verify with
  `cargo test --offline -p k230-shell-rust seed_default`.

## 2. Drop resolution: folders, dock, swap-or-revert

- [x] 2.1 `home_screen::merge_two` (two apps merge into a folder, an app
  joins a folder, a folder absorbs a lone app) and the shared
  `move_existing`/`place_new` drop paths for both an on-Home rearrange and
  a drawer-origin drag; verify with
  `cargo test --offline -p k230-shell-rust home_screen`. Done: covers
  folder-create, folder-join, dock placement (including a dock folder),
  same-span swap fallback, widget span-aware move, and empty-page pruning.
- [x] 2.2 Folder overlay data/gesture model: open on tap, close on an
  outside tap, tap-app-to-launch, tap-name arms rename
  (`push_folder_name_char`/`backspace_folder_name`/`apply_folder_rename`);
  verify with the same `home_screen` test run.

## 3. Widget content

- [x] 3.1 `home_widgets::battery` -- injectable-root `/sys/class/
  power_supply` scan, absent/present states, 30s `POLL_INTERVAL`; verify
  with `cargo test --offline -p k230-shell-rust home_widgets::battery`.
  Done: 7 unit tests including the absent-hardware case this board
  actually has today.
- [x] 3.2 `home_widgets::weather` -- disk cache, 30-minute
  `REFRESH_INTERVAL`/`should_fetch`, wttr.in `%C|%t` parsing, offline
  fallback to the last cache; verify with
  `cargo test --offline -p k230-shell-rust home_widgets::weather`. Done: 9
  unit tests including an injected-binary-failure "offline" case.
- [x] 3.3 `home_widgets::clock` -- `libc::localtime_r`-backed formatting and
  minute-aligned redraw scheduling; verify with
  `cargo test --offline -p k230-shell-rust home_widgets::clock`.

## 4. Drawer long-press-drag hand-off

- [x] 4.1 `navigation::DrawerNavigation::take_long_press_drag`: tick-armed
  (not release-detected), consumes the touch on firing; remove the old
  release-time `DrawerAction::LongPress`/instant-pin path entirely; verify
  with `cargo test --offline -p k230-shell-rust navigation`.
- [x] 4.2 Wire `main.rs`: `drawer_home_drag: Option<i32>` bound to the
  armed touch id, forwarding motion/release into `HomeScreen`'s external-
  drag API and bypassing the drawer's ordinary scroll/close-drag/search
  dispatch for that touch; the drawer's own `draw()` paints only a Cancel
  band while live (`RendererCache::draw_drawer_drag`), letting Home's
  already-live rendering (lifted icon, drop-target highlight) show
  through; verify with `cargo build --offline -p k230-shell-rust` and
  `cargo test --offline -p k230-shell-rust`. Done: 353 lib/bin tests + 60
  integration tests pass; `cargo clippy --offline --all-targets` reports no
  new warnings (pre-existing, untouched warnings elsewhere unaffected).

## 5. Widget/folder rendering

- [x] 5.1 `render.rs`: `paint_widget_card` (Clock/Battery/Weather content),
  `paint_item_plate` generalized for App/Folder (2x2 mini-icon preview),
  `paint_open_folder` (scrim, card, member grid, name label); verify with
  `cargo test --offline -p k230-shell-rust render`.
- [ ] 5.2 Widget picker sheet (long-press empty Home space -> Widgets/
  Wallpaper & style/Home settings, preview list, drag-to-place) and its own
  QEMU/host coverage. Deferred -- see `design.md`'s Deferred section; not
  started.
- [ ] 5.3 Live system-keyboard grab for folder rename, matching the Wi-Fi
  password field's keyboard-interactivity request. Deferred; the rename
  data model (task 2.2) is ready for this to call into.
- [ ] 5.4 Drag an app out of an *open* folder onto Home. Deferred; needs
  the overlay's own touch dispatch to arm a drag mid-overlay, which does
  not exist yet.
- [ ] 5.5 Cached-layer/dirty-rect rendering and prebuilding the drawer's
  grid cache at idle (task 7's "if you can" items). Deferred; both are
  separable follow-on work with no data-model dependency on this change.

## 6. Build and evidence

- [x] 6.1 `cargo test --offline` (full workspace) and
  `cargo clippy --offline --all-targets`; verify their exit codes directly.
  Done: all tests pass, no new clippy warnings.
- [ ] 6.2 Build the updated Rust client; verify with
  `nix build .#handheld-shell-rust --max-jobs 1 --cores 6 --no-link --print-out-paths`.
- [ ] 6.3 Confirm the coherent-shell system closure still builds; verify
  with `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`.
- [ ] 6.4 A paired Sway/Rust QEMU injected-touch trial (styled on
  `tests/rust_home_screen_qemu.py`) exercising: Home with each widget
  placed, an open folder, a dock folder, and a drag mid-flight (drawer ->
  Home reveal, or an on-Home rearrange over a folder-creating drop);
  capture screenshots under `docs/evidence/home-widgets-folders/` with
  blob-inventory rows; verify with the harness invocation and
  `python3 tools/blob-scan.py` exiting 0. This is QEMU proof of wiring and
  layout, not of real-glass feel or daylight readability.

## 7. Board acceptance (explicitly out of scope for this pass)

- [ ] 7.1 **Hardware, not claimed by this change.** Real-finger drag-to-
  place from the drawer, folder create/join/open/rename, widget placement
  and live values (including a real battery device, once the keyboard base
  is connected), photographed on the physical AMOLED. Left open per the
  coordinator's explicit instruction that this implementation does not
  touch the board or `/dev/ttyACM0`.

## 8. Proposal validation

- [x] 8.1 Validate this change; verify with
  `openspec validate the-home-screen-has-widgets-and-folders --strict`.

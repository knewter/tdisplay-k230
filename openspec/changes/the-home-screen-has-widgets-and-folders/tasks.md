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
- [x] 5.2 Widget picker sheet (long-press empty Home space -> Widgets/
  Wallpaper & style/Home settings, preview list, drag-to-place). Done:
  `WidgetPicker`/`WidgetPickerPage` in `home_screen.rs`,
  `picker_row_rect`/`picker_row_at` in `home_grid.rs`, `paint_widget_picker`
  in `render.rs`, all covered by unit tests (menu navigation, a Widgets-row
  long-press-drag placing Clock via `place_first_fit`). "Wallpaper & style"
  navigates to the existing theme/background chooser
  (`OpenWallpaperAndStyle` -> `ThemeIntent::Open`) without touching any
  theme-picker file. QEMU coverage: see task 6.4 -- attempted, not
  obtained this pass.
- [x] 5.3 Live system-keyboard grab for folder rename, matching the Wi-Fi
  password field's keyboard-interactivity request. Done:
  `sync_home_keyboard`/`forget_home_keyboard`/`handle_home_key` in
  `main.rs` mirror `sync_wifi_keyboard` exactly against
  `home_surface.layer` (`KeyboardInteractivity::Exclusive` while
  `open_folder.editing_name`), Enter commits
  (`apply_folder_rename`)/Escape cancels (`cancel_folder_rename`). QEMU
  coverage: see task 6.4 -- attempted every way described there, not
  obtained this pass; the code path is exercised only by `cargo test`
  today.
- [x] 5.4 Drag an app out of an *open* folder onto Home or the dock.
  Done: `DragSource::FromFolder { folder, app_id }` unifies through the
  same `drop_dragged_item` engine as every other drag source; releasing
  back onto the folder's own icon cancels (distinct from releasing
  anywhere else on the open card). Covered by
  `dragging_a_member_out_of_an_open_folder_onto_home_removes_and_places_it`
  and neighbouring unit tests. QEMU coverage: see task 6.4 -- not attempted
  this pass (sequenced after the rename scenario that would not complete).
- [x] 5.5 Cached-layer/dirty-rect rendering and prebuilding the drawer's
  grid cache at idle. Done: `RendererCache::prebuild_drawer_grid` wired
  after startup, after a catalog rescan, and after a theme
  commit/rollback; `RendererCache::draw_drawer_reveal` (ease-out-cubic
  slide+fade of a captured snapshot) replaces an instant vanish on
  long-press hand-off, kept cheap (translate a cached image, not a
  re-render). Board-measured baseline this fixes:
  `K230_DRAWER_FRAME ms=549.89` on first open vs `1.04` afterward
  (`docs/design/app-drawer-review.md`'s own performance section).

## 6. Build and evidence

- [x] 6.1 `cargo test --offline` (full workspace) and
  `cargo clippy --offline --all-targets`; verify their exit codes directly.
  Done: all tests pass, no new clippy warnings.
- [x] 6.2 Build the updated Rust client; verify with
  `nix build .#handheld-shell-rust --max-jobs 1 --cores 6 --no-link --print-out-paths`.
  Done: `/nix/store/xyh2paw8j216zda8ad8fqwpz58v2l59r-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
- [x] 6.3 Confirm the coherent-shell system closure still builds; verify
  with `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel --max-jobs 1 --cores 6 --no-link --print-out-paths`.
  Done: `/nix/store/z23fr90qkv8azcawzvi75kh143fp0ggg-nixos-system-nixos-26.11.20260919.20b1ddd`
  (a host cross-build proof only -- not deployed to the board or booted).
- [x] 6.4 Completed paired Sway/Rust native QEMU folder rename, member extraction, dock, widget-picker and drag scenarios, with committed captures and blob inventory: `docs/evidence/home-widgets-folders/closeout-2026-10-01/qemu/README.md`. Additional mapped-app rename regression passes in its `rename-over-app/` subdirectory. The previously stalled rename was a keyboard/focus bug, now fixed; historical failed attempts remain in the earlier report.

## 7. Board acceptance (explicitly out of scope for this pass)

- [x] 7.1 User-authorized board self-verification complete: real system-keyboard rename, folder create/join/open/member extraction/dock movement, picker placement and restart persistence, recorded in `docs/evidence/home-widgets-folders/closeout-2026-10-01/board/README.md`. Prior operator finger acceptance and new injected board checks are distinguished explicitly. The user delegated acceptance in place of the former repeat manual/photo sequence. Attached-battery acceptance is conditional and not applicable because no battery is present.

## 8. Proposal validation

- [x] 8.1 Validate this change; verify with
  `openspec validate the-home-screen-has-widgets-and-folders --strict`.

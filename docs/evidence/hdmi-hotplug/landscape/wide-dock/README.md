# The dock grows on wide screens (task 7.3)

Operator design answer, 2026-10-14: "More slots when wide" -- the dock grows
past 4 slots on wide screens, and the extra slots stay empty until apps are
pinned.

## Rule

`home_grid::dock_slots(width, height)`: one slot per grid column, but no more
than the icon budget leaves after one full page (`icon.rs` `CACHE_LIMIT` = 24,
so a full page plus its dock stays resident), and never fewer than the panel's
4.

| Surface | Columns | Page | Dock |
| --- | ---: | ---: | ---: |
| 568x1232 (portrait panel) | 4 | 20 | 4 |
| 1280x800 (HDMI) | 9 | 18 | 6 |
| 1280x720 (HDMI) | 9 | 18 | 6 |
| 1232x568 (landscape panel) | 9 | 18 | 6 |
| 1920x1080 (HDMI) | 14 | 42 | 4 (page alone is over budget) |

`HomeLayout::fit_dock` sizes the stored dock when the surface changes. Wider
surfaces add empty slots at the end. Narrower ones never hide a pinned item:
an item past the new end moves into the first empty slot that remains, or
onto the grid when the dock is full.

## Host evidence (host render, 2026-10-16)

`home-1280x800.png` and `home-1232x568.png` come from
`cargo run --offline --example render_responsive_evidence -- <dir>`, which
fills the dock with synthetic apps. Each shows six dock slots. The portrait
`home-568x1232.png` from the same run is byte-identical to
`docs/evidence/shell-responsive/home-568x1232.png`.

`cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml
--no-fail-fast` passed: 547 lib tests (2 ignored) plus every integration
target, 0 failures. The new tests are:

- `home_grid::a_wide_dock_grows_within_the_icon_budget`: slot counts, no
  overlap, inside the surface, and a centre tap hits each slot.
- `home_state::fit_dock_grows_empty_and_shrinks_without_hiding_an_item`.

The older wide Home renders under `shell-responsive/`,
`hdmi-hotplug/landscape/host-renders/` and `panel-landscape/host/` record the
4-slot dock as it was before this change, and are left as history.

## On the board (2026-10-16, ~00:44–00:48 CDT)

Evidence class: **injected pointer events plus native `grim` captures**. No
real glass and no camera. Build `3f6eca48`
(`.#kernelMainlineDrmShellLandscapeHdmiBootFiles`), system
`zqy2i8w0h672f69jw7843w1l0mqz4wv5`, deployed live with
`switch-to-configuration test` and the boot profile set. HDMI-A-1 at
1280x800. Pointer input is `tools/board-pointer.py`, a uinput mouse.

1. `board-six-slots-1280x800-grim.png`: after the deploy, Home's dock shows
   six slots. The user's four pinned apps fill slots 1–4, and slots 5–6 are
   empty, as the operator asked.
2. A long press on the Video app in the grid, then a drag to the sixth slot
   (`hold 640 190 900`, 12 moves to 1162,720, `up`). The shell logged
   `home-layout-changed`. The saved `home.json` dock then read
   `[foot, Nautilus, editor, htop, null, k230-video]`: six entries, persisted.
   `board-video-dropped-in-slot-6-1280x800-grim.png` shows the result while
   still in rearrange mode.
3. `click 1194 80` (Done), then `click 1162 720` on the sixth slot. The shell
   logged `app-launch-requested` and `app-launch-mapped`, so the new slot's
   hit area launches its app. `board-video-in-slot-6-1280x800-grim.png` shows
   Home with Video in slot 6, out of rearrange mode, before the launch.
4. Cleanup: the Video window was closed, and Video was dragged back to its
   grid cell. `home.json` again matches the operator's layout (Video in grid
   slot 4, slots 5–6 empty).

Limits:

- Shrinking the dock (unplugging HDMI back to the portrait panel) with an
  item in slot 5 or 6 was not exercised on the board; it is covered only by
  `fit_dock_grows_empty_and_shrinks_without_hiding_an_item`.
- The 1232x568 landscape panel dock is host-render evidence only.
- The first drag-back attempt did not take: the press landed in rearrange
  mode without a drag. A second attempt with a 1.2 s hold worked.

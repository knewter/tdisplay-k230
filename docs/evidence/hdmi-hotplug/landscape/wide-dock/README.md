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

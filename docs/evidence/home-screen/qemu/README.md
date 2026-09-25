# Pinned Home screen: headless QEMU injected-touch acceptance

Observed 2026-09-25 03:05 UTC, source `cf034d0a` (branch
`feat/home-screen-impl`, rebased onto `origin/master`'s `fa1f54e6`;
proposal `openspec/changes/the-shell-presents-a-pinned-home-screen/`). This
ran the cross-built Sway with the card-shell patch
(`/nix/store/3fnyjj7zi1h78aqhfg4q1iy6k5rjm6qn-k230-card-shell`, unwrapped
binary `/nix/store/cwpfizab7mz285vcyha1kci64ij2m511-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`)
and the Rust shell client
(`/nix/store/8bifbbv1z8qhkzqkmpwisvhbyw9b5nwi-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`)
under `qemu-riscv64-static` with a 568x1232 headless Pixman output. The
compositor's native `card_shell test-touch` route supplied synthetic Wayland
touch events (`SWAY_K230_CARD_SHELL=1 SWAY_K230_CARD_TOUCH_FIRST=1
SWAY_K230_CARD_TEST_INPUT=1`, matching the real integrated session). A
private XDG data directory held a small synthetic desktop-entry/icon
catalog; the client's `swaymsg` calls went through a QEMU-wrapper script.

Reproduce with the committed runner and exact executables:

```sh
python3 tests/rust_home_screen_qemu.py \
  --sway /nix/store/cwpfizab7mz285vcyha1kci64ij2m511-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --swaymsg /nix/store/cwpfizab7mz285vcyha1kci64ij2m511-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/swaymsg \
  --rust /nix/store/8bifbbv1z8qhkzqkmpwisvhbyw9b5nwi-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --theme-source nix/handheld-theme-default \
  --output /tmp/k230-hs-N
```

PASS: all twelve checks in [result.json](result.json) are `true` --
`mid_swipe_differs_from_page1`, `page2_differs_from_page1`,
`dock_tap_launched`, `drawer_opened`, `drawer_long_press_pinned`,
`pinned_icon_visible`, `rearrange_mode_shows_done_and_remove`,
`removed_from_saved_layout`, `dock_survives_the_removal`,
`stable_after_restart`, `light_page2_differs_from_page1`,
`light_differs_from_dark`.

## What each capture shows

Sparse (2-3 app) interactive fixture, dark theme:

- [home-dark-page1.png](home-dark-page1.png) -- fresh Home at rest: page 1,
  one page dot lit, "Fixture Terminal"'s real staged SVG icon in the dock
  (not an initial-letter fallback), no card-overview chrome over it (nothing
  is focused and the overview is not active, per decision 2 of the
  proposal's design.md).
- [home-dark-mid-swipe.png](home-dark-mid-swipe.png) -- captured with the
  touch still down, partway through a leftward drag: the grid has moved
  with the finger, 1:1, before release.
- [home-dark-page2.png](home-dark-page2.png) -- after release past the
  settle threshold: page 2, the second dot now lit, "Fixture Page Two"
  visible (pre-staged there to prove paging/rendering without needing 28+
  filler apps to fill a real page -- `home_grid.rs`'s own unit tests cover
  that capacity math).
- [home-dark-back-to-page1.png](home-dark-back-to-page1.png) -- a rightward
  drag back to page 1, after the dock tap below.
- [home-dark-drawer.png](home-dark-drawer.png) -- the existing "All apps"
  drawer, reached here via the `--surface drawer` shortcut (the swipe-up
  gesture from Home into the drawer is existing, unchanged code, already
  covered by other tests); "Fixture Extra" and "Fixture Page Two" show the
  expected initial-letter fallback (they have no `Icon=`), "Fixture
  Terminal" shows its real icon.
- [home-dark-pin-flow.png](home-dark-pin-flow.png) -- after a long-press
  (650ms, past `LONG_PRESS_MS`) on "Fixture Extra"'s drawer tile and
  dismissing the drawer: it now appears on Home's first free grid slot,
  pinned directly with no confirmation dialog (design.md decision 5).
- [home-dark-rearrange.png](home-dark-rearrange.png) -- a long-press on the
  newly pinned icon entered rearrange mode: the contextual "Done" and
  "Remove" pills appear in the top inset band, non-permanent chrome.
- [home-dark-removed.png](home-dark-removed.png) -- after a second,
  ordinary (non-long-press) drag of the same icon onto "Remove": it leaves
  Home. The authoritative check is [result.json](result.json)'s
  `removed_from_saved_layout`/`dock_survives_the_removal`, read from the
  persisted layout file directly, not a pixel diff (an emptied slot looks
  like any other empty slot).
- [home-dark-after-restart.png](home-dark-after-restart.png) -- the Rust
  process was killed and restarted against the same
  `$XDG_STATE_HOME/k230-shell/home.json`; this is pixel-identical to
  `home-dark-page1.png`, since the net effect of pinning then removing
  "Fixture Extra" restored the original layout exactly.

Same fixture, light theme:

- [home-light-page1.png](home-light-page1.png),
  [home-light-page2.png](home-light-page2.png) -- the light generation's
  palette (`#eff1f5` background, dark text) applies to Home's dots, dock
  plate and labels exactly as it does to the drawer/shade/settings surfaces;
  `light_differs_from_dark` confirms the two are not pixel-identical.

Showcase pass -- a believable, fully-populated fresh Home (not the
interactive fixture's deliberately sparse 2-3 apps), captured at rest only:

- [home-dark-showcase.png](home-dark-showcase.png),
  [home-light-showcase.png](home-light-showcase.png) -- eight synthetic
  apps (Terminal, Files, Text Editor, System Monitor, Video Player,
  Settings, Browser, Notes), each with a distinct colored rounded-square
  icon, four pinned to the dock and four on the first grid page. This is
  what the design is meant to look like day-to-day; the sparse fixture
  above exists for precise interaction assertions, not visual review.

## Limits retained

This proves headless QEMU compositor/client wiring, layout, and theming with
injected touch and a synthetic desktop/icon catalog. It does not prove a
real finger, panel optics, daylight readability, physical long-press timing
feel, or the complete coherent image. Real-finger board acceptance is
explicitly out of scope for this implementation pass (the coordinator owns
`/dev/ttyACM0`); it remains an open task in
`openspec/changes/the-shell-presents-a-pinned-home-screen/tasks.md`.

A prior run of this same fixture found icon painting always fell back to an
initial-letter plate: the loaded appearance snapshot's own `icon_theme`
field (normally "Yaru-purple", the real default theme's icon set) overrides
whatever `K230_ICON_THEME` the process started with, so the fixture's
private "fixture" icon theme was silently replaced the moment the staged
appearance/report generation loaded. Both `appearance.json` and
`report.json` must declare the same `icon_theme` (a mismatch is rejected
outright), so `theme_generation()` now sets both. A second prior run also
showed the old rollback-session "Cards" button drawn over Home, from
omitting `SWAY_K230_CARD_TOUCH_FIRST=1`. A third prior run (after rebasing
onto a newer `origin/master`) intermittently captured a solid black frame
for a pass's very first screenshot: `ready-idle` only proves the process
logged its own startup line, not that the compositor painted a first real
frame. All three are fixed in the committed test and reflected in every
capture above; the harness was rerun three times after the last fix with
no recurrence.

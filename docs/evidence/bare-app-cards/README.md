# Bare app cards: plate/letterbox fix

User report from real glass (568x1232 portrait, `swaymsg card_shell enter`,
one foot terminal open): "when i swipe up to see active windows the cards
have some background behind them, that's no good, they should just be cards
right". The board capture showed each card as a fixed coloured plate
(~437x720) with the live scaled snapshot centred inside it at only ~302px
wide, leaving wide coloured bands on both sides, plus a label strip
overlapping the bottom of the snapshot.

## What changed

`nix/card-shell/adapter.c`'s `sync_card`/`card_background`: the deck slot
(`cs_card_rect`, unchanged -- policy config, pitch and gesture thresholds are
untouched) now only positions the card; what's drawn is a small rounded,
bordered plate sized from the app's own aspect ratio and the slot's
available height (`CARD_PLATE_PAD`/`CARD_PLATE_RADIUS` in adapter.c), with
the live mirror filling it edge-to-edge minus the pad. The app name + icon
badge moved from an overlay strip at the bottom of the snapshot to a caption
below the card, on the wallpaper. Selection reads as a brighter/thicker
plate rim (`CARD_PLATE_STROKE_SELECTED` vs `_UNSELECTED`), not a different
full-bleed colour. Private/unavailable cards get the same aspect-fit
treatment (view geometry still exists even when its content is denied), so
they read as a small themed card, not a letterboxed rectangle. New shared
rendering helper: `card_plate_scene()` in `nix/card-shell/render.c` (a
rounded-rect cairo fill + optional stroked rim, reused by both the gradient
and default/solid card brush).

`nix/card-composition-probe-client/card-composition-probe-client.c` gained a
third accepted `--app-id k230.card.three` (distinct fill colour) purely for
this 3-card capture; the existing `one`/`two` composition/gesture/recovery
test suites are unaffected.

**Rejected alternative**: also shrinking `card-shell-policy`'s
`cs_default_config` `card_width`/`gap` (the deck pitch) to match the new
visual card width. Not done: the pitch/hit-test slot only needs to *contain*
the visual card, not equal it, and the in-deck `select_fraction` threshold
is expressed as a fraction of that pitch, so touching it risks the
already-approved drag/throw/app-switch feel for no visual benefit. The 29
`tests/card_shell_policy_driver.c` cases and the runtime QEMU suites below
were re-run against the *unmodified* policy code and pass, confirming no
gesture regression.

## Verification

- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#card-shell`
  -> `/nix/store/crbf9r271vh9gj2icf9n3d5zs3qcl2c0-k230-card-shell` (final,
  after the plate-pad fix).
- `nix eval .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel.drvPath`
  -> `/nix/store/kvdrgch1ikm6g914mxwv0jssfxkd2cmv-nixos-system-nixos-26.11.20260919.20b1ddd.drv`
- `python3 tests/test_card_shell_state.py` -- 29/29 C policy-driver cases
  pass (policy untouched by this change).
- `python3 tests/test_card_shell_composition.py`,
  `test_card_shell_recovery.py`, `test_card_shell_two_axis_runtime.py`,
  `test_card_shell_touch_first_runtime.py`,
  `test_card_shell_scaled_cache_runtime.py`,
  `test_card_shell_deck_title.py`, `test_card_shell_chrome.py` -- pass, using
  the `sway-unwrapped-*/bin/sway` named by
  `nix-store -qR /nix/store/crbf9r271vh9gj2icf9n3d5zs3qcl2c0-k230-card-shell`
  under `qemu-riscv64-static` (`headless-qemu-injected-input`, no board).
  `test_card_shell_gestures.py` failed once on an unrelated, pre-existing
  frame-liveness timing assertion (both apps' committed-frame counters must
  strictly increase over a fixed 2s window) and passed on immediate retry
  with the identical binaries; this is a scheduling-load flake in
  `tests/card_shell_runtime.py`, not a card-plate regression.
- `python3 tools/blob-scan.py` -- exit 0 ("every binary is accounted for").
- `python3 tools/capture-bare-app-cards.py --sway <unwrapped sway>
  --client <card-composition-probe-client> --output /tmp/k230-bc-N` --
  produced the six PNGs in this directory: `{1,2,3}-apps-{dark,light}.png`.
  Dark uses the bundled default (Catppuccin-Mocha-derived) theme; light
  authors a Catppuccin-Latte-like palette through the same real
  report.json/appearance.json palette-synthesis path in
  `nix/card-shell/appearance.c` (no bundled light theme exists in-tree to
  capture verbatim, so the hex values are supplied, not the palette-driven
  synthesis code). This is headless-QEMU evidence
  (`WLR_BACKENDS=headless`, synthetic striped test-pattern clients), not a
  board/panel/touch observation -- glass acceptance and gesture feel remain
  the coordinator's real-touch check.

## Reading the captures

Each PNG shows the card as the striped test-client snapshot at its own
aspect (no coloured bands to the sides), a thin rounded rim around it, and
"<letter-badge> <app name>: <status>" captioned below the card on the
wallpaper. In the 2- and 3-app captures the unselected neighbour(s) peek in
at the slot edges as thin unrounded-looking slivers (only the near edge of
their own rounded plate is in frame) in a different fill colour, confirming
per-card theming and that the wallpaper (not a backdrop plate) fills the
gap between cards.

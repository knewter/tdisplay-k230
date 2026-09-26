One slice: a bounded C-compositor geometry/rendering change, fully
implemented and host/QEMU-proved in this change. The board task at the end
is the only open item.

## A. Geometry: Android-recents-sized card

- [x] A.1 Change `cs_default_config`'s `card_width`/`card_height` from
  `.5*width`/`.6*height` to `.8*width`/`.8*height` (`nix/card-shell-policy/card-shell-policy.c`),
  matching the panel's own aspect ratio. Reduce `title_height` from 100 to
  70 to fit the taller card within the existing `valid_config` bounds
  (`inset`, `footer_height` unchanged, both already at their declared
  minimums). Recompute `card_top_offset` for the new numbers, keeping the
  same centering formula.
- [x] A.2 Mirror the same fractions in `nix/card-shell/adapter.c`'s runtime
  config recompute (the real per-output path, distinct from the test-only
  `cs_default_config` defaults), which already reads `title_height` from
  the shared `cs_default_config` call so no separate edit was needed there.
- [x] A.3 Update `card-shell-policy.h`'s field comment describing
  `card_width`/`card_height` to record the new sizing and supersede the
  prior "webOS-fan, 55-65%" comment, per this repo's "record what was
  rejected and why" convention.
- [x] A.4 Update `tests/card_shell_policy_driver.c`'s `overview_geometry`
  case: width/height fractions (75-85% band), neighbour-peek assertion
  (now a thin ≤15%-of-card-width sliver, not ≥30%), third-card assertion
  (now fully off-screen, not merely `<15%`). Recompute the entry-target
  independence assertions (unchanged formula, still checked exactly).
- [x] A.5 Recalibrate the horizontal-drag/flick fixtures that hardcoded
  absolute pixel distances tuned to the old, narrower pitch
  (`horizontal`, `scroll_catch_mid_coast`, `stream_cancel`,
  `stream_cancel_multitouch`: `180`px → `pitch*.6`; `scroll_fling_multi_card`:
  recalibrated two-sample velocity so a fast flick still projects past two
  cards at the new pitch; `scroll_end_clamp_soft`: the "land on the last
  card" drag rewritten as a two-sample flick, since a single drag's raw
  reach is capped at `2*width` regardless of pitch and no longer alone
  spans a 4-card deck at the new, wider pitch). See `design.md` decision 7.
- **Proof:** `cc -std=c11 -Wall -Wextra -Werror -pedantic -g
  -fsanitize=address,undefined -fno-omit-frame-pointer -I
  nix/card-shell-policy tests/card_shell_policy_driver.c
  nix/card-shell-policy/card-shell-policy.c -lm -o /tmp/policy-test`, then
  every case in `tests/test_card_shell_state.py`'s `CASES` list run against
  that binary, and `python3 -m pytest tests/test_card_shell_state.py -q`:
  36 passed. **Host build proof**, no board.

## B. Corner radius: no plate, corner-mask patches over live content

Revised after coordinator review of the first pass's screenshots, which
kept a padded plate behind live content — exactly what the operator had
separately rejected ("the cards have some background behind them ...
they should just be cards"). See `design.md` decisions 3-5.

- [x] B.1 Drop the live-card plate and its pad entirely: `sync_card`'s
  content box (`box_x/box_y/box_width/box_height`) is now exactly the
  mirrored content's own aspect-fit rect within the card slot, with no
  inset margin. `CARD_PLATE_PAD` is removed; `CARD_PLATE_RADIUS` is
  renamed `CARD_CORNER_RADIUS` (26.0, unchanged value) since it is no
  longer plate-specific.
- [x] B.2 Add `card_corner_mask_scene` (`nix/card-shell/render.c`/`render.h`):
  one small (`size`×`size`) cached Cairo rasterization per corner
  orientation, opaque in the deck's backdrop colour outside a quarter-circle
  arc curving toward the card's centre, fully transparent inside it.
- [x] B.3 Add `card_corners_sync` (`nix/card-shell/adapter.c`): for live
  cards, builds/positions four of these patches on top of the mirrored
  content (`wlr_scene_node_place_above`), rebuilding all four only when
  this card's own quantised (whole-pixel) radius or the canvas's
  representative colour (`canvas_solid_color`, factored out of
  `appearance_canvas_refresh` so both share one definition of "the backdrop
  colour") changes. Non-live (private/unavailable) cards keep the existing
  `card_background`/`card_plate_scene` plate, unchanged in kind, since they
  have no live pixels to protect from a background.
- [x] B.4 Gate the radius interpolation on `card_shown_large(c)` (already
  defined in this file) rather than the mode-wide `entering` flag, and stop
  hiding the card's rounding during the transition: only the card(s)
  actually growing/shrinking between full screen and deck size get
  `CARD_CORNER_RADIUS * progress`; every other card always uses the full
  radius. This also fixes a latent gap in this change's first pass, where
  the interpolated radius was computed but fed to a plate unconditionally
  hidden for the whole transition, so it was never actually visible.
- **Proof:** same host build as slice A (this code is compiled as part of
  `nix build .#card-shell` in task C.1, not the standalone policy test
  binary); no dedicated unit test targets `card_corners_sync` in isolation,
  so this task's proof is the successful build plus the headless-QEMU
  capture in task D below, which shows rounded live-card corners with no
  visible background/border, in both themes, across scroll/close/open.

## C. Full build proof

- [x] C.1 `nix build .#card-shell --max-jobs 1 --cores 6` — succeeds,
  producing `/nix/store/j3idplp3kbmbp36cn7ik13z4q46yq0qy-k230-card-shell`.
- [x] C.2 `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel
  --max-jobs 1 --cores 6 --no-link --print-out-paths` — succeeds, producing
  `/nix/store/aklc0jcyiddgbg4h2b0dnnsdkns36wyv-nixos-system-nixos-26.11.20260919.20b1ddd`.
  **Host build proof.**

## D. Headless-QEMU capture

- [x] D.1 Re-run `tools/capture-webos-fan-switcher.py` against this
  branch's built card-shell (unwrapped riscv64 Sway from `nix-store -qR` of
  the task C.1 output path, a host-arch build of
  `nix/card-composition-probe-client`, and a `symlinkJoin` of `pkgs.foot`,
  `pkgs.htop`, `nix/handheld-theme-icons` for real icon resolution), both
  themes, all five stages. Commit the result plus one copy of the prior
  (pre-change) `dark-01-overview.png` for direct comparison under
  `docs/evidence/card-shell/android-sized-cards/`, with matching
  `docs/blob-inventory.md` MANIFEST rows. Re-run again after the slice B
  revision and replace the `after-*` files with the plate-free capture.
- [x] D.2 `python3 tools/blob-scan.py` — exits 0.
- **Proof:** `docs/evidence/card-shell/android-sized-cards/README.md`.
  **Headless-QEMU proof** (real cross-built compositor code, real IPC, real
  synthetic touch) — explicitly not board/panel/real-finger proof, per that
  README's own "what this does not show" section.

## E. Board/real-finger acceptance — open

- [ ] E.1 On the physical board, flick through a multi-card deck at the new
  80%/80% size and confirm the fan-switch gesture (flick past one or more
  cards, flick-up to close, tap to open) still feels responsive and
  intentional, not heavier or laggier, at the new card size. Confirm the
  radius transition (open/close) reads as a smooth morph, not a pop, to a
  real eye. Record a camera or injected-touch-on-board capture under
  `docs/evidence/card-shell/android-sized-cards/` alongside this change's
  existing headless-QEMU evidence, distinguishing the evidence class per
  `AGENTS.md`. Operator command, once a board/serial reservation is held:
  flash this branch's system closure, then `python3
  tools/card-shell-board-session.py` (or the equivalent board capture tool
  already used for `docs/evidence/card-shell/webos-fan-switcher/`'s own
  board-facing companions) against `/dev/ttyACM0`.

**Narrow command for this whole change, once E.1 lands:**
`openspec validate the-overview-shows-large-rounded-cards --strict`.

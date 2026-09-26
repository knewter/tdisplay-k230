# Android-recents-sized, rounded overview cards: headless-QEMU evidence

Evidence for the operator's explicit ask ("i think the cards should have a
border radius and fill a lot of the screen not be tiny idk more like
android does") and `docs/design/shell-polish-review-2026-09.md` §6:
resizing the overview's focused card from the prior webOS-fan pass (50% of
the panel's width, 60% of its height) to an Android-recents proportion (80%
of both), and giving it a visibly rounded 26px corner radius with **no
background or border behind the live content** -- the card IS the app
content, scaled.

**Revised once after coordinator review.** A first pass kept the existing
content plate (a themed, filled, stroked rounded rect behind the mirrored
content, inset by a growing pad so its rounded corner peeked out around the
square content) and only raised its radius (8px->26px) and pad (10px->32px).
The coordinator reviewed that pass's `after-*` screenshots and identified
that a 32px padded plate is exactly the visible background the operator had
separately, explicitly rejected: "when i swipe up to see active windows the
cards have some background behind them that's no good they should just be
cards." The `after-*` files below are the **second**, plate-free pass: live
cards have no plate at all; rounding comes from four small corner-mask
patches (`card_corner_mask_scene`) painted over the mirrored content's own
square corners in the deck's backdrop colour. See
`openspec/changes/the-overview-shows-large-rounded-cards/design.md`
decisions 3-5 for the full technique and cost discussion.

## Method

Same harness and method as
`docs/evidence/card-shell/webos-fan-switcher/README.md`, run against
`nix build .#card-shell` from this branch (`feat/android-sized-cards`): the
real cross-built riscv64 Sway under `qemu-riscv64-static` user-mode
emulation, real `.desktop`/icon resolution
(`nix/handheld-desktop-entries.nix`-equivalent fixtures, Yaru icon theme),
and the real `card_shell test-touch` IPC path driving the production
`cs_down/cs_motion/cs_up` policy code, at the real panel size (568x1232).
This is headless-QEMU proof (real cross-built compositor code, real IPC,
real synthetic touch), not board/panel/real-finger touch proof. No board or
`/dev/ttyACM0` access was used.

## Files

- `before-dark-01-overview.png` -- the original webOS-fan overview (before
  either pass of this change), copied unchanged from
  `docs/evidence/card-shell/webos-fan-switcher/dark-01-overview.png` (same
  file, same hash) for a direct side-by-side without re-deriving it. Card:
  50% panel width, 60% panel height, an 8px radius on a padded plate, ~46.5%
  neighbour peek.
- `after-dark-*.png` / `after-light-*.png` -- the same five-stage sequence
  (`01-overview`, `02-scrolling`, `03-scrolled-settled`, `04-after-close`,
  `05-opened`), both themes, captured from this branch's built card-shell
  **after** the plate-free revision. Card: 80% panel width, 80% panel height
  (matching the panel's own aspect ratio), content filling the entire slot
  with no plate/pad, a 26px corner-mask radius, ~10% neighbour peek at the
  screen edges (Android-recents proportions, not a webOS multi-card fan).

## What the after-sequence shows

1. `01-overview` -- the focused card now fills most of the panel, its
   content touching the card's own edges with no visible border or fill
   behind it, and all four corners show a clean 26px rounded cut painted in
   the surrounding backdrop colour -- compare directly against
   `before-dark-01-overview.png`'s much smaller card, which additionally
   shows a visible bordered plate around a smaller live thumbnail. Confirmed
   in both dark and light themes (`after-light-01-overview.png`): the
   corner-mask colour tracks the active theme's own canvas colour, not a
   fixed value.
2. `04-after-close` -- checked at pixel level (`docs/evidence/` capture
   cropped and zoomed for this review) to confirm all four corners round
   correctly, not just the two nearest the panel's own edges -- a coarse
   thumbnail view can make a correctly-rounded corner look square next to a
   card-header icon; the zoomed crop confirms the arc is present and
   correctly oriented at all four corners.
3. `02-scrolling` / `03-scrolled-settled` -- the same fling-projects-the-
   resting-card physics as before (unchanged `cs_up`/`cs_tick` code), now
   recalibrated in `tests/card_shell_policy_driver.c` for the wider pitch
   (see that file's `horizontal`/`scroll_fling_multi_card`/
   `scroll_end_clamp_soft`/`stream_cancel*` comments): the fan still flicks
   through multiple cards and settles centered, just at the new size.
4. `04-after-close` -- flick-up-to-close still works at the new card size;
   the remaining cards re-flow with no overlap artifact, still rounded.
5. `05-opened` -- tap-to-expand still reaches a clean, full-bleed,
   square-cornered single-app frame (an ordinary maximized Sway view is not
   part of the card deck and is never corner-masked), confirming the
   compositor still leaves `CS_DECK` correctly.

## What this does not show

- Real board/finger touch, optical legibility, or panel colour rendering
  (UNVERIFIED; no board access was used).
- The corner-radius *interpolation* during entry/expand: this capture's
  tool takes single still frames at named stages, not a mid-transition
  frame, so the 0->26px radius morph itself is not visually proven here --
  it is proven by direct code read (`nix/card-shell/adapter.c`'s
  `sync_card`, the `card_shown_large`-gated `radius_progress`/
  `corner_radius` computation feeding `card_corners_sync`) and by the
  existing `card_shell_policy_driver.c`/`test_card_shell_state.py` suite
  passing (36/36) after the geometry change, not by a dedicated screenshot.
  Unlike this change's first pass, the corner masks are not hidden during
  the transition, so a future mid-drag capture (a card-composition-probe
  fixture driving a live two-axis entry drag and grabbing an intermediate
  frame) could show this directly -- not attempted here.
- Real-finger flick-through-multiple-cards feel at the new, much larger
  card size, or the felt smoothness of the radius morph -- this is exactly
  the kind of "does it still feel right" question `AGENTS.md` reserves for
  a real-glass pass; the recalibrated drag/flick distances in the policy
  test suite are a physics-formula proof (same formulas, same thresholds,
  resized inputs), not a felt-motion proof.
- A gradient-canvas theme's local colour at the corners: the corner mask
  uses the canvas's *representative solid* colour
  (`canvas_solid_color`/`card_brush_solid_color`) rather than sampling the
  true per-pixel gradient, and a fully transparent canvas (a live wallpaper
  reveal) skips corner masking entirely rather than paint a wrong patch --
  neither fixture used for this capture exercises either case.

## Commands

```
nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths
SWAYBIN=$(nix-store -qR <that path> | grep -m1 sway-unwrapped-riscv64)/bin/sway
python3 tools/capture-webos-fan-switcher.py --sway "$SWAYBIN" \
  --client <host-arch nix/card-composition-probe-client build> \
  --icon-roots <symlinkJoin of pkgs.foot, pkgs.htop, nix/handheld-theme-icons> \
  --output /tmp/k230-fs-after
```

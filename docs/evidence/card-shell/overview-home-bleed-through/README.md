# Overview/Home bleed-through: root cause, fix, and before/after evidence

Follows the coordinator's report from real glass (installed system, master
`db5b0584`, 568x1232): "in webos/card overview mode i see black /
glitching", and the native capture that confirmed the Rust Home screen's
always-mapped `Layer::Bottom` surface painting through the card overview.
Branch `fix/overview-glitch`, worktree `../k230-overview-glitch`, base
revision `db5b0584`.

Headless-QEMU-injected-input evidence only, via the real cross-built
`nix/card-shell` compositor (`.#card-shell`) and a native touch device
(`SWAY_K230_CARD_TEST_INPUT=1`); no physical touch or panel proof. See
"Board re-check" below for the outstanding hardware evidence gate.

## Root cause

`nix/card-shell/adapter.c` maps the whole card-overview UI tree
(`shell.ui`/`shell.deck`/`shell.canvas`) under `root->layers.shell_overlay`
-- above every output layer, including `output->layers.shell_bottom`, the
Home screen's own `Layer::Bottom` surface
(`nix/rust-shell-client/src/main.rs`'s `HomeSurface`, from
`the-shell-presents-a-pinned-home-screen`). Two independent gaps in that
overlay let Home show through it:

1. **The deck's title-bar strip.** The chrome title bar reserves a band
   above `shell.canvas` (`cs_content_rect`'s `top_reserved`) that the chrome
   itself does not paint an opaque background into -- only text and the
   "Back" pill are drawn there. This band is empty scene space regardless of
   theme configuration, so Home showed through it unconditionally whenever
   the overview was open.
2. **A themed, intentionally transparent canvas.** When a theme configures
   an unauthored/no canvas colour, `shell.canvas`'s alpha is deliberately 0
   so a person sees their wallpaper behind the cards
   (`wallpaper_cover_publish`'s `opaque_deck` logic). Before Home existed,
   that transparency only ever revealed the plain wallpaper layer beneath
   it; with Home now occupying the layer directly above the wallpaper, the
   same transparency reveals Home's grid tile and dock instead -- the
   coordinator's "Video" tile beside the Monitor card and the dock over
   "Swipe up for apps".

Neither gap is limited to the settled, static overview a native capture
shows: `cs_begin_entry` (`nix/card-shell-policy/card-shell-policy.c`) calls
`cs_enter` internally and returns its `CS_SHRINK` action even though it then
immediately overwrites the policy mode to `CS_ENTERING`, so
`nix/card-shell/adapter.c`'s `handle_result` sets `shell.active = true` --
and enables the deck/canvas -- at the very first touch-down of the
finger-driven bottom-edge entry gesture, before any visible drag distance.
Home was therefore bleeding through for the whole entry animation and the
whole settled overview, not only a single steady-state frame, which matches
a person describing it as "glitching" rather than a static defect.

## Fix

`nix/card-shell/adapter.c`: a new `home_layer_sync(struct sway_output
*output)` disables `output->layers.shell_bottom` (Home's only occupant --
confirmed by grep, no other client uses `Layer::Bottom` in this shell)
whenever `shell.active`, and re-enables it otherwise. It is called at the
same two points that already toggle `shell.ordinary_backdrop` for the
mirror-image reason (`ordinary_backdrop_sync`'s own comment): the `CS_SHRINK`
branch of `handle_result` (entering the overview, from either the direct
`cs_enter` IPC path or the finger-driven `cs_begin_entry` path) and
`restore()` (leaving it). Both call sites do the toggle before the deck's
own scene changes take visible effect, so no frame renders with both the
deck and Home visible. `card_shell debug-scene` now reports a
`home_enabled` field so this invariant is directly assertable, not only
inferred from pixels.

This is a compositor-side scene-visibility fix only: no gesture recognizer,
threshold, or state machine in `nix/card-shell-policy/` changed
(`tests/test_card_shell_state.py`'s 29 cases pass unmodified), and the Home
surface's own Rust rendering/layout/persistence/input code is untouched.

## Reproduction and regression test

`tests/card_shell_home_layer.c`: a native fixture mapping a `Layer::Bottom`
surface, full output size, filled with opaque green (`0xFF00FF00`) -- a
colour no other surface in this shell's test suite uses -- standing in for
the real Home surface without pulling in the Rust client's Wayland stack or
on-disk state.

`tests/card_shell_runtime.py --home-layer-client <fixture>` (new flag) maps
it before the two-axis touch sequence runs, then:

- asserts `home_enabled` in `card_shell debug-scene` before the gesture
  (Home mapped, app fullscreen already occludes it by ordinary opaque
  stacking);
- asserts `not home_enabled` at the instant of first touch-down, and no
  fixture pixel in either that frame or the following capture
  (`assert_no_home_bleed`);
- sweeps every frame the existing two-axis sequence already captures --
  entry, drag, bend, quick-switch, private-neighbor, close, settle -- for
  the fixture's colour, and separately for any frame with a large near-black
  region (`assert_no_black_flash`, an independent check for the
  coordinator's "black" report against every animated path this sequence
  exercises: entry, drag/throw, quick switch, close);
- asserts `home_enabled` again once a card is refocused (Home occluded by
  the app, not by the fix);
- closes every card and asserts Home is both `home_enabled` **and**
  genuinely visible in a captured frame, so this test cannot pass by
  permanently disabling `shell_bottom` instead of toggling it.

`tests/test_card_shell_home_bleed.py` wires this into the suite (builds the
fixture, invokes the runtime with `--native-touch --touch-first --two-axis
--home-layer-client`).

Confirmed both directions against the real compiled `.#card-shell`:

- **Before the fix** (`nix/card-shell/adapter.c` at `db5b0584`, no
  `home_layer_sync`): `test_card_shell_home_bleed.py` fails --
  `debug-scene` has no `home_enabled` field at all, and (see below) the
  overview's title-bar gap shows the fixture's green immediately.
- **After the fix**: `test_card_shell_home_bleed.py` passes, and
  `tests/test_card_shell_two_axis_runtime.py`'s existing 29+1 assertions and
  `tests/test_card_shell_state.py`'s 29 C-policy-driver cases still pass
  unmodified.

Narrow proof commands:

```
nix build .#card-shell --max-jobs 1 --cores 6
python3 -m unittest test_card_shell_home_bleed test_card_shell_two_axis_runtime test_card_shell_state   # run from tests/
python3 tools/blob-scan.py   # check exit code
nix eval .#nixosConfigurations.k230.config.system.build.toplevel
```

## Before/after screenshots

One ordinary (fullscreen) app focused, `card_shell enter` issued directly by
IPC, headless QEMU, no theme configured (`appearance_enabled=0` -- the
title-bar gap reproduces even with the plainest, unauthored deck canvas):

- `before-app-focused.png`: baseline, app fullscreen, nothing else visible.
- `before-overview-home-bleeds-through.png` (unfixed `adapter.c` at
  `db5b0584`): the green Home fixture fills the whole title-bar strip above
  "Cards" -- `debug-scene` at capture: `active=1 deck_enabled=1 canvas
  enabled=1 ... rgba=0.067,0.094,0.153,1.000 ... ordinary_maximized_cards=1`
  (no `home_enabled` field existed yet).
- `after-overview-home-hidden.png` (fixed `adapter.c`): the same title-bar
  strip is black (the wallpaper layer beneath Home, unconfigured in this
  harness) -- `debug-scene` at capture: `active=1 deck_enabled=1 canvas
  enabled=1 ... home_enabled=0`.

The real, finger-driven touch-first two-axis entry gesture, fixed
`adapter.c`, captured by `tests/card_shell_runtime.py
--home-layer-client`:

- `entry-00-origin.png`: before the gesture, app focused, Home occluded by
  ordinary opaque stacking (not by the fix).
- `entry-01-touch-down.png`: the instant of first touch-down -- no green,
  confirming `home_layer_sync` fires at gesture start, not gesture end.
- `entry-02-mid-drag.png`: mid-drag, still no green.
- `entry-03-home-idle-reveal.png`: every card closed -- solid green, Home
  correctly reappears once nothing occludes it. This is the same idle state
  a real device without a wallpaper background would show; on the board,
  Home's own icons/dock render in place of this fixture's flat colour.

## Limits and what remains open

- This rules out the Home-bleed-through class of bleed for the exercised
  sequence (bottom-edge two-axis entry, drag, bend, quick switch, close,
  settle) but is not an exhaustive sweep of every animated path the
  coordinator listed (e.g. this sequence does not drive a not-yet-drawn
  scaled-cache mirror or a card whose bare-cards plate/pad is still
  interpolating into place while blank). `assert_no_black_flash` found no
  large near-black region anywhere in this sequence's frames either way,
  which is evidence against those other suspects in this exact sequence,
  not a proof they cannot occur elsewhere.
- **Board re-check remains the outstanding evidence gate.** The same native
  capture the coordinator used to confirm the original bug
  (`swaymsg card_shell enter`, a real focused app, real wallpaper/theme
  configured) should be repeated on the installed system once this change
  lands, to confirm the fix holds with a real theme's canvas transparency
  (not just this harness's unauthored/opaque-by-default canvas and the
  unconditional title-bar gap) and with real finger input rather than
  injected touch. This task was scoped to QEMU evidence only (no board or
  `/dev/ttyACM0` access); it does not claim that board check.

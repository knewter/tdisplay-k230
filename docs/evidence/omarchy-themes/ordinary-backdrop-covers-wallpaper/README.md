# Root cause: `ordinary_backdrop` covers the wallpaper in the deck overview

Filed against the coordinator's board reproduction: on installed
`vj4qzpjq…` (`master` `b9d892c7`), a real Terminal card was ordinarily
maximized, then `swaymsg card_shell enter` (native, 4 s wait, `grim`) showed
a flat uniform dark backdrop, `(24,29,27)` everywhere outside the cards,
with the active generation (`f2a0ead03dffb1b396801f0e`) and its
`background.cache` both confirmed correct. This is a **host + headless-QEMU
(`qemu-riscv64-static`)** result for the fix and regression test; the
board's own capture (above) is the reproduction evidence, gathered by the
coordinator, not this pass. Run 2026-09-24, worktree
`fix/wallpaper-visible-swap-jank`, base `master` `b9f81d47`.

## Root cause

`nix/card-shell/adapter.c`'s `ordinary_backdrop_sync()` enables an opaque,
output-sized `wlr_scene_rect` in `output->layers.tiling` whenever *any* live
card has `card_shell_ordinary_maximized` set -- with no check for whether
the deck/card overview (`shell.active`) is the thing actually being shown.
`layers.tiling` sits above `layers.shell_background` (the wallpaper's own
layer-shell surface) in Sway's fixed scene order
(`include/sway/tree/root.h`'s `struct sway_root::layers` field order,
confirmed from the pinned Sway source tree). The deck's own canvas
(`shell.canvas`, in `root->layers.shell_overlay`, higher still) correctly
goes transparent to reveal the wallpaper when the active theme authors no
`[card]` override -- but that transparency only matters if nothing *between*
the wallpaper and the deck is itself opaque. `ordinary_backdrop` is exactly
that: designed to fill the margin behind a single ordinary-maximized app
while its own resize catches up (see its own comment in `ensure_ui`), it
was never gated on whether the deck was currently showing, and a card
stays flagged `card_shell_ordinary_maximized` while the person opens the
overview to look around -- the flag describes the app's own UX state
("this is someone's one full-screen app"), not "not currently being viewed
in overview". Card overview with any ordinarily-maximized app present
therefore always lost the wallpaper to this rect, regardless of the active
theme, its `appearance.wallpaper` flag, or `canvas_authored` -- explaining
why the earlier investigation
(`docs/evidence/omarchy-themes/wallpaper-visibility-board-report/README.md`)
could not reproduce it: that QEMU fixture never mapped an ordinarily-
maximized app, only a card-sized floating probe.

Confirmed by reverting only the fix's `!shell.active` guard (keeping the
diagnostic and the two explicit re-sync call sites) and rerunning the new
regression test: `still_themed.getpixel(upper_point)` came back
`(227, 228, 232)` against an expected `(254, 238, 221)` -- the same
"present but not the image" symptom the board showed, not `#eff1f5`-style
flat colour this time because the deck canvas's own colour differs by
theme/generation; the mechanism (an opaque rect above the wallpaper, below
the deck) is what actually matters, not which exact colour it happens to
paint. `latte-deck-with-ordinary-buggy.png` (this directory) is that
failing capture; `latte-deck-with-ordinary-fixed.png` is the same scene
with the fix restored, pixel-correct.

## Fix

`nix/card-shell/adapter.c`:

- `ordinary_backdrop_sync()`'s `any` computation now only runs `if
  (!shell.active)` -- while the deck overview is showing, the backdrop is
  never a candidate to enable, full stop; the deck's own canvas is what
  decides whether to reveal the wallpaper there, exactly as it already does
  for every other case.
- `restore()` (overview exit) and `handle_result()`'s `CS_SHRINK` branch
  (overview entry) each now call `ordinary_backdrop_sync(shell.output)`
  immediately after flipping `shell.active`, so the backdrop's visibility
  updates the moment overview is entered or left, rather than waiting for
  an unrelated usable-area-changed event to happen to re-run it.

## Board-side diagnostic

Part of the coordinator's ask: a self-evident, read-only probe. Added
`swaymsg -- card_shell debug-scene`, a new IPC subcommand alongside the
existing `enter`/`back`/`ordinary`/etc (`nix/card-shell/adapter.c`'s
`cmd_card_shell`). It reads back the exact facts this bug turns on --
never mutates scene state -- and both logs the line (`journalctl`-visible)
and returns it as the command's own IPC reply text:

```
K230_CARD_SHELL_DEBUG_SCENE active=<0|1> deck_enabled=<0|1|-1>
  canvas enabled=<0|1> pos=X,Y size=WxH rgba=R,G,B,A
  canvas_gradient enabled=<0|1|-1>
  ordinary_backdrop enabled=<0|1> pos=X,Y size=WxH rgba=R,G,B,A
  ordinary_maximized_cards=<N>
  appearance_enabled=<0|1> appearance_wallpaper=<0|1|-1>
  appearance_canvas_authored=<0|1|-1>
```

(`-1` for a field means "not yet initialized", e.g. before `ensure_ui` or
before any `appearance_apply`.) On this bug, the self-evident line is
`ordinary_maximized_cards` non-zero while `active=1` and
`ordinary_backdrop enabled=1`.

### Exact board commands

Read-only, safe to run at any time; does not require the fix to be
installed to be useful as a diagnostic:

```sh
./tools/console.py /dev/ttyACM0 --wait=3 "swaymsg -- card_shell debug-scene"
```

Reading the same fact from already-emitted logs instead (note **UTC**: the
board's local console time is not what `journalctl --since` expects):

```sh
./tools/console.py /dev/ttyACM0 --wait=3 \
  "journalctl -u shell --since '2026-09-24 23:00:00 UTC' | grep K230_CARD_SHELL_DEBUG_SCENE"
```

To reproduce the exact board sequence that triggered this (an ordinary
maximized app, then entering the deck), per the coordinator's request:

```sh
# with a Terminal (or any ordinary app) focused and full-output floating,
# matching the real Sway config's own for_window rule for it:
swaymsg -- floating enable, resize set 100 ppt 100 ppt, move position 0 0
swaymsg -- card_shell ordinary
swaymsg -- card_shell debug-scene   # before this fix: ordinary_backdrop enabled=1, active=0
swaymsg card_shell enter
swaymsg -- card_shell debug-scene   # before this fix: still enabled=1, active=1 -- the bug
                                    # after this fix: enabled=0 while active=1
```

## QEMU regression

`tests/test_real_theme_paired_runtime.py` now marks the existing live probe
card `card_shell ordinary` while the deck overview is showing (mid-test,
after the Latte activation's own deck/drawer assertions already pass), and
checks:

- the wallpaper sample points (`(10,300)`/`(10,700)`) still match the
  expected crop of Latte's real background with the ordinary flag set and
  the overview active (`latte-deck-with-ordinary.png`);
- `card_shell debug-scene`'s own reply shows `ordinary_backdrop enabled=0`
  while `active=1`, and `enabled=1` after `card_shell back` (`active=0`).

This marks the already-live card in place rather than mapping a second
window mid-overview: `ordinary_backdrop_sync`'s enable decision never
depended on the flagged card's own size or position, only on the flag and
`shell.active`, so this exercises the identical code path the board's real,
full-output ordinary window does, without engaging card-shell's
overview-snapshot machinery with a card added while already active (which
this investigation found is not a supported transition -- see "What did not
work" below).

Verified both directions on real riscv64 builds under `qemu-riscv64-static`:
reverting just the `!shell.active` guard reproduces the failure
(`(227, 228, 232)` vs expected `(254, 238, 221)`, this directory's
`-buggy.png`); with the guard, the assertions pass
(this directory's `-fixed.png`). The test's later,
already-known-and-documented, host-load-dependent flake at
`wait(expanded_app, 5)` (see
`docs/evidence/omarchy-themes/background-decode-cache-qemu/README.md`) is
unrelated: the unmodified pre-this-change test fails at the exact same line
under the same host load, independent of this fix.

## What did not work

Initially tried spawning a *second* live card (`k230.card.two`, sized
`100 ppt` per the coordinator's literal ask) and marking it ordinary while
already inside the deck overview. That destabilized `shell.active` itself
(the debug-scene snapshot showed `active=0` moments after entering, an
apparent state-machine reaction to a new card appearing mid-overview that
this investigation did not chase further, since it is a pre-existing
card-shell policy question, not this bug) and produced a real but harder-to-
interpret failure. Marking the *existing* card in place reproduces the
exact same `ordinary_backdrop_sync` code path with none of that
instability, and is what the committed test does.

## Reproduce

```sh
nix build --no-link --print-out-paths --max-jobs 1 --cores 6 \
  .#handheld-shell-rust .#card-shell .#card-composition-probe \
  .#handheld-theme-default .#handheld-theme-icons

python3 tests/test_real_theme_paired_runtime.py \
  --sway "$(nix-store -qR $(nix build --no-link --print-out-paths .#card-shell) | grep sway-unwrapped-riscv64)/bin/sway" \
  --rust "$(nix build --no-link --print-out-paths .#handheld-shell-rust)/bin/k230-shell-rust" \
  --client "$(nix build --no-link --print-out-paths .#card-composition-probe)/bin/card-composition-probe-client" \
  --theme-bundle "$(nix build --no-link --print-out-paths .#handheld-theme-default)" \
  --icons "$(nix build --no-link --print-out-paths .#handheld-theme-icons)" \
  --output /tmp/k230-wj-ordinary-repro
```

## Why

After compositor-repaint, the keyboard's show settle was the last keyboard
phase over budget: a 16 ms render against the 12 ms allowance, presenting
every second refresh (38.3 ms). A per-frame profile on CLOCK_MONOTONIC puts
the time in Pixman's RVV `over_8888_0565`. Every keyboard frame blends three
ARGB surfaces OVER the RGB565 output:

- the Foot window, which is opaque;
- the keyboard, opaque because wvkbd's colours carry no alpha;
- wvkbd's key-preview popup, fully transparent unless a key is held.

OVER reads and blends the destination for every one of those pixels anyway.

## What Changes

- A Pixman patch adds two exact shortcuts to RVV `over_8888_0565`. A vector
  chunk whose source alpha is all 0xff is converted and stored; a chunk that
  is all zero is skipped. Once a chunk is neither, the rest of its row is
  blended without further tests, so translucent surfaces such as the drawer
  sheet pay one test per row.
- `nix/card-shell.nix` gives only the compositor (sway and its wlroots) the
  patched Pixman. The rest of the closure keeps the shared one and is not
  rebuilt.
- Non-goals:
  - opaque regions on sliding surfaces, excluded by the operator on
    2026-10-22. Nothing below a surface is culled;
  - any change to what is drawn. Output is byte-identical by construction and
    by test.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a performance change within `runtime/shell`'s existing
requirement "Keyboard motion follows contact and settles continuously". Its
quantitative measurement was transferred to
the-shell-profiles-reported-interaction-jank, which recorded the miss.

## Impact

`nix/card-shell.nix` and the new patch, in the compositor build only.
Evidence is in `docs/evidence/interaction-jank/keyboard-blend/`. Proof needs
the physical board: RVV, injected keyboard gestures, and grim captures.

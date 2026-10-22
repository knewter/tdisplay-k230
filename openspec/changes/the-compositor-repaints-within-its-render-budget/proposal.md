## Why

After the drawer client fix, drawer scroll presents every 38.3 ms, which is two
refreshes of the 52.19 Hz panel. The compositor benchmark shows sway's own
repaint takes a median of 18.4 ms, over its 12 ms allowance. Keyboard motion
renders in 22–42 ms and presents at 38–77 ms intervals
(`docs/evidence/interaction-jank/drawer-profile/README.md`,
`docs/evidence/interaction-jank/keyboard/README.md`).

Board CPU profiles put sway's time in three places:

- blending ARGB surfaces into the RGB565 frame (`rvv_composite_over_8888_0565`,
  28–35%);
- the quarter-turn copy to the portrait scanout (`k230_turn_copy_rect`,
  18–29%);
- XRGB→RGB565 conversion (`k230_rgb565_blit`, 8–16%).

On 2026-10-22 the operator asked for iterations until the gains became
minimal, starting with sway's `-d` debug log.

## What Changes

- Run sway without `-d` (`k230.shell.debugLog` off in the board image).
- The drawer declares the opaque rows of its sheet as its opaque region when
  the sheet pixels are fully opaque. sway then copies the drawer instead of
  blending it, and skips the layers beneath.
- Patch the on-screen keyboard (wvkbd) to declare its surface opaque when its
  key and background colours are opaque.
- Further iterations, each measured on the board with the same drawer and
  keyboard workloads, until one stops giving a meaningful gain. Candidates
  include a faster quarter-turn and a cheaper keyboard rearrangement.
- Non-goals:
  - visual changes;
  - a translucent theme losing its translucency (opacity is declared only
    when the pixels prove it);
  - the vector kernel trial.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: a compositor repaint budget for drawer scroll and keyboard
  motion, judged from installed-board benchmark measurements.

## Impact

`flake.nix`, `nix/shell.nix`, `nix/patches/wvkbd-k230-opaque-region.patch` and
`nix/rust-shell-client`, plus any further compositor patches. Proof is
board-only: injected native touch, landscape. Each step is test-activated
before the final build is promoted.

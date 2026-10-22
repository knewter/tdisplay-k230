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
- Let sway take the `SCHED_RR` priority it already requests
  (`LimitRTPRIO=1` on `shell.service`). On the one CPU its repaint was
  otherwise preempted by the clients it composites.
- Iterations were measured on the board with the same drawer and keyboard
  workloads until the remaining levers were small or rejected. Three were
  tried and not kept:
  - a drawer opaque region: no gain, because the active theme's sheet is
    translucent;
  - an RVV quarter-turn: faster in isolation, no faster into the scanout
    buffer;
  - a wvkbd opaque region: rejected by the operator on 2026-10-22, because an
    opaque keyboard while it slides looks wrong.
- Non-goals:
  - visual changes;
  - opaque regions on sliding surfaces;
  - the vector kernel trial.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: a compositor repaint budget for drawer scroll and keyboard
  motion, judged from installed-board benchmark measurements.

## Impact

`flake.nix` and `nix/shell.nix`; evidence in
`docs/evidence/interaction-jank/compositor-repaint/`. Proof is
board-only: injected native touch, landscape. Each step is test-activated
before the final build is promoted.

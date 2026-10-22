## Context

The image composes in a landscape RGB565 buffer and turns the damaged region
into the portrait scanout (`nix/card-shell/quarter-turn.h`,
`rgb565-blit.h`). Opaque XRGB/ARGB-SRC sources already have a fast conversion
path. Blended ARGB sources go through pixman's OVER, and every layer under a
damaged region is drawn.

## Goals / Non-Goals

- Goal: bring sway's repaint for drawer scroll and keyboard motion under its
  12 ms allowance, so frames land on consecutive refreshes.
- Goal: measure each step on the board against the same baseline, and stop
  when gains become minimal.
- Non-goal: changing what any surface looks like.

## Decisions

- **Debug log off.** INFO-level card-shell telemetry still reaches the journal
  with `-V`, so the benchmark keeps working.
- **sway runs `SCHED_RR` 1.**
  - Profiles showed about 7.5 ms of sway CPU per drawer frame against a
    14.7 ms repaint wall time. The difference was time lost to clients on the
    single CPU.
  - sway already requests `SCHED_RR` at the minimum priority, and resets the
    children it forks to `SCHED_OTHER` (`sway/realtime.c`). The unit only
    needed `LimitRTPRIO=1`.
  - Kernel 7.3's fair server keeps 50 ms per second for ordinary tasks, so a
    runaway compositor cannot starve SSH entirely.
- **No opaque regions.**
  - The drawer's sheet is translucent in the active theme, so a pixel-derived
    region never applied.
  - The keyboard's region improved renders but looked wrong while the keyboard
    slid, and the operator rejected it.
- **The quarter-turn stays scalar.** An RVV version was pixel-identical and
  2.3x faster into heap memory, but no faster into the scanout buffer.
- **Measurement.** Each candidate is test-activated and measured with the same
  harness: the 30 s drawer scroll with `card_shell benchmark injected` armed,
  then 8 keyboard cycles with the benchmark. Results are presented interval,
  render wall time and damage. CPU profiles from `tools/board-profile.py`
  choose the next step.

## Risks / Trade-offs

- A realtime compositor that spins could starve ordinary tasks. The fair
  server bounds this, and sway's event loop sleeps between frames.
- Keyboard show settle still misses (16 ms repaint, 38 ms interval). Fixing it
  needs either a cheaper ARGB blend or an operator decision on opacity.

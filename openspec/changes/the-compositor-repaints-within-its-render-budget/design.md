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
- **Opacity is declared from pixels, not assumed.** The drawer scans its
  cached sheet once per theme and size. wvkbd declares opacity only when every
  colour it draws with SOURCE is fully opaque.
- **Measurement.** Each candidate is test-activated and measured with the same
  harness: the 30 s drawer scroll with `card_shell benchmark injected` armed,
  then 8 keyboard cycles with the benchmark. Results are presented interval,
  render wall time and damage. CPU profiles from `tools/board-profile.py`
  choose the next step.

## Risks / Trade-offs

- A wrongly declared opaque region would show stale pixels beneath. Both
  declarations come from the actual pixels or colours, and a unit test covers
  the drawer.

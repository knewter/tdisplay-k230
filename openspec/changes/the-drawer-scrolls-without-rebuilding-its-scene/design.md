## Context

Drawer scroll on the installed board renders at about 39 ms per frame. The
opt-in recorder showed a full `scene_rebuild` per scroll frame, but not why
each rebuild cost so much. A 30 s `perf` capture with DWARF unwinding filled
that gap. It used `cpu-clock` at 199 Hz with a 64 KiB stack copy, against
`shell-ui` and `shell`. Stock nixpkgs libraries keep `.symtab`, so the stacks
resolve from `_start` through Rust, pango, cairo and pixman with no debug
packages.

## Goals / Non-Goals

Goals:

- Remove the measured client costs.
- Make the flamegraph capture a repeatable, documented tool that can show
  before/after evidence.

Non-goals:

- New drawer visuals.
- Compositor optimizations.
- Declaring the ~20 ms target met without a board measurement.

## Decisions

- **Memoize text measurement, not layout.** `wrapped_line_count` and
  `measured_text_width` are pure in (text, pixel size, width, weight) for the
  fixed font family. A bounded thread-local map (cleared at 1,024 entries)
  removes the reshaping without changing every layout caller. Skipping
  `chooser_layout` in `draw` would cover only one caller.
- **Whole-pixel grid offset with `Filter::Fast`.** The grid cache is rendered
  at output scale, so rounding the offset moves the content by under half a
  pixel and lets pixman copy rows. A unit test checks that the band repaint
  matches a full rebuild at fractional scrolls.
- **Band repaint inside the existing cache.** `RendererCache` already repaints
  clipped rows for the theme picker. A drawer scroll with the same route and
  size, no pending picker rows and no pressed tile now repaints only the rows
  from `list_top` to the viewport bottom, in place. A pressed tile's ring can
  reach past the band, so it still takes a full rebuild.
- **Log the first move of each contact.** The drawer QEMU test waits for
  `touch-move N`, so the line stays, once per contact.
- **Profiling tool.** It runs `perf record -p` on each unit's main PID under
  the board lock, alongside a sleep-paced workload. It checks for unit
  restarts and runs `perf script` on the board. On the host it renders with the
  flake-pinned FlameGraph. Raw text is kept gzipped for speedscope's
  time-ordered view.

## Risks / Trade-offs

- Sampling at 199 Hz with 64 KiB DWARF copies costs CPU on a one-CPU board.
  Profiled runs show where time goes. Timing claims come from separate,
  unprofiled runs.
- The measurement cache keeps up to 1,024 short strings per map.

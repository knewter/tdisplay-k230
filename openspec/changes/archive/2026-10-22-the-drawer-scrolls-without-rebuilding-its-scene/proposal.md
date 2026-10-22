## Why

The measured drawer scroll (`docs/evidence/interaction-jank/drawer-scroll/README.md`)
renders a frame in about 39 ms, presents about 8 frames per second and rebuilds
the whole scene on every scroll frame. That is well past the ~20 ms target. A
sampled CPU profile of the same workload shows where the client's time goes.
About 37% goes to bilinear resampling of the cached grid at fractional scroll
offsets. About 35% goes to shaping the theme chooser's text, which every draw
re-measures even when the chooser is not shown. Review §6 of
`docs/design/app-drawer-review.md` proposed this follow-up, and the operator
asked for it on 2026-10-22, together with a way to capture flamegraphs on the
board.

## What Changes

- Cache the shell's text line-count and width measurements, so per-draw layout
  code stops reshaping unchanged strings.
- Blit the drawer's cached grid at whole-pixel offsets with a nearest filter.
- On a drawer scroll, repaint only the grid band of the cached frame instead of
  rebuilding the whole scene.
- Journal only the first `touch-move` of each contact, not every sample.
- Draw drawer motion that arrives while a frame is pending on the next frame
  callback, instead of rendering every touch sample.
- Cache the drawer sheet (its vision backdrop and themed background brush) per
  theme and size.
- Report only the repainted band as surface damage on a scroll frame.
- Add `tools/board-profile.py`. It samples DWARF-unwound CPU stacks of named
  units on the board during a workload, and renders a folded file, a flamegraph
  SVG, speedscope-readable `perf script` text and a summary on the host.
- Non-goals:
  - scroll-direction blitting (shifting the previous frame), unless the new
    measurement still misses the target;
  - compositor-side cost such as sway's RGB565 conversion and rotation copy,
    which the profile also shows;
  - turning off sway's `-d` debug logging, which is not approved.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell`: a drawer scroll repaints only the scrolled band, and an
  operator can capture a sampled CPU flamegraph of an installed-board workload.

## Impact

- Code: `nix/rust-shell-client` (`render.rs`, `main.rs`) and the new
  `tools/board-profile.py`, plus `docs/runtime-tracing.md`.
- Proof: injected native touch on the installed board, landscape only. No
  kernel, boot or compositor change.

## Context

The parent change landed its tools: `tools/theme-swap-jank.py`,
`tools/analyze-theme-swap-jank.py`, `tools/theme-picker-profile.py`, the
default-off runtime trace (parent 15.1) and the `runtime-perf` package. A
partial physical CPU profile exists. In it, 648 of 697 samples have unknown
callers, and compositor stage spans and scheduler correlation are missing.
The user deferred the tap-to-visible re-run. This change keeps those
obligations visible without holding the parent open.

## Goals / Non-Goals

Goals: run the four carried measurements on the reserved board and commit
reviewed reports with exact commands, runtime identities, observer cost and
coverage gaps. Non-goals: changing picker behavior, or claiming a target was
met from host, QEMU or injected-only evidence.

## Decisions

- Jank before/after (parent 2.3): "before" means a system without
  `theme-helper.service`. If no such installed system can be restored safely,
  record that gate rather than substituting a QEMU baseline.
- Tap-to-visible (parent 3.4): report against the ~100 ms target. A miss stays
  a miss.
- Compositor profile (parents 15.2 and 15.3): sampled CPU stacks and elapsed
  spans stay separate artifacts. Do not label spans as CPU samples. If perf
  cannot unwind the compositor on this kernel, document the precise
  unsupported gate.

## Risks / Trade-offs

Observer cost can distort small timings, so the tracing-off and tracing-on
runs are paired. The board has a single operator. Every run takes the board
lock and restores the selected generation.

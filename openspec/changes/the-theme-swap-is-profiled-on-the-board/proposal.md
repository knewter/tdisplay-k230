## Why

`the-shell-swaps-themes-without-a-python-stall` built the persistent theme
helper, prepare-ahead, optimistic apply, tap-to-apply, finger tracking and the
runtime trace. Four of its measurement tasks have no board result: the
before/after jank capture (parent 2.3), the tap-to-visible re-run against the
~100 ms target (parent 3.4, deferred by the user), and the compositor-stage
profile and flamegraph (parents 15.2 and 15.3). The operator authorized
splitting them out on 2026-10-12 so the parent can close its remaining
motion, cost-attribution and finger-acceptance work. This change preserves
those four tasks unchanged. It records no result.

## What Changes

- Carry parent task 2.3 verbatim: before/after `tools/theme-swap-jank.py`
  captures for a dark, a light and a community theme on the reserved board.
- Carry parent task 3.4 verbatim: re-run the tap-to-visible metric of
  `tools/analyze-theme-swap-jank.py` and report it against the ~100 ms target.
- Carry parent task 15.2 verbatim: extend the verified trace through
  compositor render/commit/present and scheduling, and produce a CPU
  flamegraph with matching symbols or document the exact unsupported gate.
- Carry parent task 15.3 verbatim: capture matched picker runs with tracing
  off, tracing on and sampling, plus one other interaction.
- Non-goals: new picker behavior, motion tuning, or treating the parent's
  partial CPU profile (`docs/evidence/theme-picker/cpu-profile/README.md`)
  as a complete compositor profile.
- Board dependency: every task needs the reserved physical board. Host tests
  and planning do not establish any hardware number.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell-themes`: board measurements of swap latency and runtime CPU
  cost stay pending until this change records them.

## Impact

Evidence goes under `docs/evidence/omarchy-themes/theme-swap-jank/` and
`docs/evidence/theme-picker/`. No source change is planned unless a
measurement justifies one, and that would be its own change.

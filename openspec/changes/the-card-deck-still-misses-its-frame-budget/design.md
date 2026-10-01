## Context

Ten-plus board rounds, spanning repaint-stage profiling, source-timestamp
fixes, a throw-fixture-race fix, a scaled-cache mirror path (on and off), and
an RVV comparison, have all measured the same tracking-presentation p95 of
~57.47-57.49ms against a 33.334ms (2x a ~19.2ms nominal interval at the
panel's advertised ~52.19Hz mode) budget. See
`docs/evidence/card-shell/{board-cost/long-trace,touch-timestamps/board,
throw-sampling,repaint-stages,throw-fixture-sync,scaled-cache-board}/README.md`.

## Goals / Non-Goals

**Goal:** resolve task 4.2's open budget decision deliberately -- either with
a genuine fix, or a recorded, reviewed acceptance, rather than another
open-ended board round repeating the same measurement.

**Non-Goal:** re-opening the GPU/VGLite decision without new evidence.

## Decisions

Not yet made -- this is exactly the open decision this successor exists to
make deliberately. The one thing already decided (inherited from the parent):
whatever is chosen, it must preserve live visual cards, finger-following,
deck selection, tap-to-expand, and recoverable throw-close; a reduced-refresh
path that breaks any of those is rejected regardless of its budget numbers.

Update, 2026-09-28 (authorized implementation): the board vblank capture
(`docs/evidence/card-shell/frame-budget/board-result-2026-09-28.md`) and a
follow-on host cost measurement
(`docs/evidence/card-shell/frame-budget/host-cost-table.md`,
`commit-pipelining-assessment.md`) together narrow this to a genuine
two-way choice, not three: every CPU/damage-side lever this change's own
task list named was already implemented or measured net-negative, and the
one remaining code-level lever (kernel commit pipelining) already has a
known, unresolved boot-panic risk from a prior attempt. The decision is
still the coordinator's; this update states what is no longer open (further
Pixman-path tuning without a new, currently-unknown target) rather than
choosing for them.

## Suggested first step

Before another `tools/card-shell-benchmark.py --board` round with a new
independent variable, measure the panel's actual output/vblank cadence
directly (e.g. DRM `vblank` timestamps or an equivalent kernel-level trace)
rather than continuing to infer it from the advertised mode. If the measured
cadence itself is ~57ms-ish, no CPU-side change to card-shell can close this
gate, and the decision becomes (b) or (c) in the proposal rather than more
Pixman tuning.

## Risks / Trade-offs

- [Another board round repeats the same non-result] -> measure cadence
  directly first, per the suggested first step, rather than varying another
  CPU-side knob.
- [Accepting the miss silently becomes "accepted"] -> the parent's own
  requirement text already forbids this ("it SHALL NOT be archived as
  accepted card-shell behavior" without a recorded decision); this successor
  exists specifically so that recording happens deliberately.

## Migration Plan

Board-gated from the outset. No host-only path closes this task.

## Ownership after functional archive (2026-10-01)

The operator explicitly approved the functional parent's archive. This change
now solely owns its original budget task 4.2 and dependent image/non-fixture
QEMU task 5.1. Criteria and proof commands remain unchanged and unchecked.
See `docs/evidence/proposal-closeout/2026-10-01/live-card-ui.md`. Functional acceptance is not budget acceptance.

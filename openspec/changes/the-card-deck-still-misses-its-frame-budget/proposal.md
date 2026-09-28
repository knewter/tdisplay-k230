## Why

`the-shell-manages-apps-as-cards` declared an explicit card-interaction
budget (task 4.1, done) and has measured the default Pixman composition path
against it on hardware more than ten times since
(`docs/evidence/card-shell/{board-cost/long-trace,touch-timestamps/board,
throw-sampling,repaint-stages,throw-fixture-sync,scaled-cache-board}/README.md`,
plus `kernel-rvv/card-cost/README.md`). Every round fails the same two
numbers: frame-update CPU p95 (borderline for one card, clearly over for two),
and, more strikingly, the **tracking-presentation interval p95 sits at
~57.47-57.49ms against a 33.334ms budget in literally every run**, unchanged
by repaint-stage instrumentation, RVV auto-vectorization, a scaled-cache
mirror path (on or off), or a touch-timestamp/fixture-race fix. That
invariance across every independently tested variable is itself informative:
it does not look like a CPU cost a code change will fix so much as a fixed
structural interval (an output-commit/vblank cadence this project has not
yet measured directly). `docs/evidence/card-shell/renderer-decision.md`
already declined the optional GPU/VGLite path as unjustified by current
evidence.

The parent's own requirement text says exactly what to do here: "If it
cannot [preserve the required behavior within budget], the change SHALL
remain open or move to an explicitly authorized successor; it SHALL NOT be
archived as accepted card-shell behavior." This is that successor, per
`AGENTS.md`'s "close deliberately" rule -- staged so the question (accept the
1.7x-over-budget tracking cadence with a recorded decision, investigate the
panel/vblank cadence directly, or continue optimizing the Pixman path) is a
deliberate coordinator choice rather than an unresolved task sitting
indefinitely in an otherwise-closeable change.

**Status: staged, not authorized.** The parent (`the-shell-manages-apps-as-cards`)
keeps task 4.2 (and the dependent task 5.1, which `docs/research/
card-shell-qemu-smoke.md` explicitly blocks on 4.2's budget passing) until
the coordinator authorizes this split.

## What Changes

- Either (a) investigate whether the ~57.48ms tracking interval is
  CPU-addressable at all -- e.g. measure the panel's actual output/vblank
  cadence directly rather than inferring it from the advertised ~52.19Hz
  mode, since every CPU-side change tried so far has left this number
  identical to five significant figures; or (b) record an explicit,
  reviewed decision to accept the current cadence (with its cost to
  perceived smoothness stated plainly) and close this requirement as
  "measured and accepted, not silently passed"; or (c) continue targeted
  Pixman-path optimization if (a) identifies a real, addressable cost.
  Which of these is right is a product decision for the coordinator, not
  predetermined by this proposal.
- Once resolved, unblock the parent's task 5.1 (image integration + non-fixture
  QEMU smoke), which is otherwise ready.

## Non-goals

- Reopening the GPU/VGLite decision (`the-shell-manages-apps-as-cards` task
  4.3, already recorded as declined) without new evidence that changes its
  premise.
- Any change to card interaction behavior (live cards, finger-following, deck
  selection, tap-to-expand, recoverable throw-close) -- the requirement is
  explicit that a reduced-refresh or optimized path is only acceptable if it
  preserves all of these.
- The parent's other open tasks (5.3, real-finger acceptance), which stay
  there and are unaffected by this split.

## Board need

Task (a) above (measuring actual vblank/output cadence) and any further
Pixman-path measurement both need the reserved board; this is board-gated
work from the outset, unlike the other two successors staged in this
closeout pass.

## Capabilities

### Modified Capabilities

- `runtime/card-shell`: carries the parent's "Card interaction has an
  explicit measured budget decision" requirement forward, unchanged, since
  the parent's own delta for this capability is not yet archived.

## Impact

Userspace performance investigation only (`nix/card-shell/`,
`nix/card-shell-policy/`, `tools/card-shell-benchmark.py`) and, if cadence
turns out to be the issue, possibly kernel/DRM timing investigation on the
panel driver (`display/panel`) -- scoped once (a) above is attempted, not
predetermined here. No stage 1 change.

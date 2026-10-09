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

**Status: authorized.** The user approved this split and its implementation
2026-09-28 ("frame budget go"). Board evidence committed the same day
(`docs/evidence/card-shell/frame-budget/board-result-2026-09-28.md`,
`analysis.md`) answered the "suggested first step" above directly: raw
hardware vblank stays a clean 19.16ms grid even while the deck animates
(idle p50/p95 19.161/19.162ms; drag-window p50/p95 19.161/19.163ms). The
~57ms presentation intervals are therefore the compositor's own commit
cadence missing vblank slots (H1: render or commit overrun, rounded up to
the next whole vblank by `canaan_crtc_atomic_flush`'s synchronous commit),
not a panel or VO refresh limit; H4 (vblank IRQ at 1/3 rate) is refuted.
This authorizes option (c): reduce per-frame card-deck render/commit cost
and/or pipeline commits so an overrun costs one slot instead of serializing
the next. On 2026-10-01 the user explicitly authorized archiving the functional parent
and transferring sole ownership of its original task 4.2 and dependent task
5.1 to this existing successor. See
`docs/evidence/proposal-closeout/2026-10-01/live-card-ui.md`. Neither budget
acceptance nor the unperformed full-image/non-fixture QEMU gate is waived.

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
- Once resolved, unblock this successor's retained task 5.1 (image integration + non-fixture
  QEMU smoke), which is otherwise ready.

## Non-goals

- Reopening the GPU/VGLite decision (`the-shell-manages-apps-as-cards` task
  4.3, already recorded as declined) without new evidence that changes its
  premise.
- Any change to card interaction behavior (live cards, finger-following, deck
  selection, tap-to-expand, recoverable throw-close) -- the requirement is
  explicit that a reduced-refresh or optimized path is only acceptable if it
  preserves all of these.
- Requiring another camera trial for the accepted functional UI. The parent
  records the operator's physical acceptance and explicit capture waiver; this
  does not replace the instrumented performance proof required here.

## Board need

Task (a) above (measuring actual vblank/output cadence) and any further
Pixman-path measurement both need the reserved board; this is board-gated
work from the outset, unlike the other two successors staged in this
closeout pass.

## Capabilities

### Modified Capabilities

- `runtime/card-shell`: carries the parent's "Card interaction has an
  explicit measured budget decision" requirement forward, unchanged, with
  the parent's functional archive leaving budget acceptance UNVERIFIED.

## Impact

Userspace performance investigation only (`nix/card-shell/`,
`nix/card-shell-policy/`, `tools/card-shell-benchmark.py`) and, if cadence
turns out to be the issue, possibly kernel/DRM timing investigation on the
panel driver (`display/panel`) -- scoped once (a) above is attempted, not
predetermined here. No stage 1 change.

## Accepted performance decision — 2026-10-09

The operator explicitly accepts the current card Overview performance and
authorizes closure and landing. The exact permission is retained in
`docs/evidence/card-shell/frame-budget/acceptance-2026-10-09/README.md`.
This selects option (b), retaining the historical overrun/CPU misses and
the distinction between measured old candidates and current observed feel.
A new benchmark is unnecessary for this chosen acceptance; no numeric pass
is inferred. Remaining work is the selected system/QEMU integration proof
and archive, not another performance or kernel experiment.

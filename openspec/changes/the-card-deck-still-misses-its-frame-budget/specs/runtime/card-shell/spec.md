## MODIFIED Requirements

### Requirement: Card interaction has an explicit measured budget decision

*Grounding: historical board cost/presentation measurements remain in
`docs/evidence/card-shell/board-cost/long-trace/README.md` and later board
cadence proof in `docs/evidence/card-shell/frame-budget/board-result-2026-09-28.md`.
Explicit current-performance acceptance and exact operator permission are in
`docs/evidence/card-shell/frame-budget/acceptance-2026-10-09/README.md`.
The historical numerical misses are accepted as costs, not rewritten as
budget passes or presented as new timings of the current candidate.*
The card shell SHALL record input-to-visible-update latency, frame/update cost,
and incremental memory use at the panel's native portrait mode on the default
Pixman path. If a declared interaction budget is missed, the implementation
SHALL record the result, including a direct measurement of the panel's actual
output/vblank cadence where a CPU-side change cannot account for the miss. A
reduced-refresh or optimized path is acceptable only when it still preserves
live visual cards, finger-following, deck selection, tap-to-expand, and
recoverable throw-close. If it cannot, the change SHALL remain open or move
to a further authorized successor; it SHALL NOT be archived as accepted
card-shell behavior.

#### Scenario: A card workload misses its declared budget

- **WHEN** a measured card interaction exceeds its declared frame, input, or
  memory budget
- **THEN** the evidence records the workload and measured result, including
  whether the cost is CPU/render/commit overrun or the panel cadence; every
  accepted mitigation retains the required core card interactions, otherwise
  work stays open or moves to an authorized successor, and unmet numbers
  are not relabelled as passing

#### Scenario: A budget miss is explicitly accepted

- **WHEN** the operator or coordinator reviews the recorded budget miss and
  explicitly accepts the current observed card performance
- **THEN** the decision to accept it is recorded in committed evidence, naming
  the historical measured cadence, its cost to perceived smoothness and
  current-candidate measurement limits, while retaining the numerical miss

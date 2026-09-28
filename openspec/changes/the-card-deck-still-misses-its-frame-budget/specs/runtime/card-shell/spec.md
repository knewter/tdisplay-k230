## MODIFIED Requirements

### Requirement: Card interaction has an explicit measured budget decision

<!-- Board measurements are recorded and FAIL the declared CPU and tracking budgets across more than ten rounds: docs/evidence/card-shell/board-cost/long-trace/README.md through docs/evidence/card-shell/scaled-cache-board/README.md. The tracking-presentation p95 (~57.47-57.49ms against a 33.334ms budget) is invariant across every tested CPU-side variable, suggesting a structural output-cadence cause rather than an addressable CPU cost. Carried into this successor per the parent's own requirement text. UNVERIFIED: an accepted budget decision. -->
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
- **THEN** the result is recorded honestly, including whether the cause is a
  CPU-side cost or the panel's own presentation cadence, and card-shell
  behavior is not accepted as passing on unmet numbers

#### Scenario: A budget miss is explicitly accepted

- **WHEN** the coordinator reviews a persistent, cadence-attributable budget
  miss that no further CPU-side change addresses
- **THEN** the decision to accept it is recorded in committed evidence, naming
  the measured cadence and its cost to perceived smoothness, rather than the
  requirement being silently marked passing

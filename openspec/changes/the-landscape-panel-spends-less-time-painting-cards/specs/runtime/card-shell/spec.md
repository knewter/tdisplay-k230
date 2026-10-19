## ADDED Requirements

### Requirement: Landscape card repainting preserves live content within measured budgets

<!-- UNVERIFIED: existing board evidence in docs/evidence/coherent-shell/motion-2026-10-19/camera/README.md measures about26Hz and timing failures. No optimization is implemented or accepted by this proposal. -->
The userspace landscape card shell SHALL preserve live client updates,
orientation, rounded clipping, opacity, card selection and client callbacks
while reducing the measured scene-build/paint cost on the native panel.
A candidate SHALL be enabled only after pixel/lifetime checks and paired
same-workload board measurements show a cost improvement without hidden work
or a visual/input regression. Acceptance SHALL retain the motion tool's
frozen input/frame p95/p99 and memory budgets, and target p95 build CPU within
one nominal52.19Hz panel interval (19.161ms). A miss SHALL remain an explicit
miss; this change SHALL stay open until its gates pass or an explicit new
operator decision is recorded. The earlier performance acceptance does not
waive this change's new gate.

#### Scenario: Live pixels change while cards are moving
- **WHEN** an application updates its content during a landscape card swipe
- **THEN** the card reflects those updates with correct rounded edges and
  orientation, and callbacks/buffer lifetime remain correct

#### Scenario: A candidate is compared with the installed baseline
- **WHEN** the reserved board repeats the same full/reduced gesture workload
  against baseline and candidate builds
- **THEN** committed evidence names both installed identities, cost and
  latency/frame/memory results, camera-visible movement and sampling limits,
  and an optimization is not accepted merely because it builds or looks faster

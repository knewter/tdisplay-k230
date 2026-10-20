## MODIFIED Requirements

### Requirement: Landscape card repainting preserves live content within measured budgets

*Grounding: exact-source board results in `docs/evidence/panel-paint/candidate-scene-coalescing/README.md` and current camera observations in `docs/evidence/panel-paint/candidate-scene-coalescing/camera/README.md`; `docs/evidence/panel-paint/candidate-scene-coalescing/camera/qualified-selection.json` and `docs/evidence/panel-paint/candidate-scene-coalescing/camera/qualified-normal-check.json` record matching running/persistent selection and normal/Home cleanup. Native pixel/lifetime, live-client callbacks/releases, bounded cost profiling and three paired full/reduced PASS results retain their distinct evidence classes. The 30fps camera and broad clock bounds do not prove optical input latency or every 52Hz refresh; no cold boot is claimed.*
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

## Purpose

Provide reproducible, opt-in Qt Quick and Quickshell trials so toolkit choices for the handheld are based on observable rendering, input, cost and recovery evidence.

## ADDED Requirements

### Requirement: The Qt Quick trial identifies what actually ran

<!-- UNVERIFIED -->
The system SHALL offer an opt-in Qt Quick Wayland probe with software rendering, basic touch UI and exact package/runtime identity reporting. It SHALL distinguish cross-build success, host rendering and physical rendering; unsupported effects MUST be identifiable rather than silently accepted.

#### Scenario: A software-rendered app is trialed
- **WHEN** the operator starts the pinned probe on the reserved board
- **THEN** the evidence identifies the actual Qt backend, Wayland buffer route, system and package revisions and observed pixels, or records the unresolved identity as incomplete

#### Scenario: A shader effect cannot render
- **WHEN** the negative-control scene exercises an unsupported effect
- **THEN** the report records that limitation and separately verifies the software-safe scene instead of claiming the effect worked

### Requirement: Toolkit cost is measured against a comparable baseline

<!-- UNVERIFIED -->
The trial SHALL preserve per-run startup, client and compositor CPU, session memory, presentation/input timing, closure size and workload identities for matched baseline and candidate runs. Budgets and repeat count MUST be fixed before execution. Missing samples, changed identities or untrustworthy baselines SHALL remain incomplete; existing card budgets MUST NOT be relaxed to certify the toolkit.

#### Scenario: A client renders but costs too much
- **WHEN** its pixels are correct but a declared cost gate fails
- **THEN** functional rendering is reported separately from the failed suitability gate, with the failed measurement retained

#### Scenario: Only submitted frames are observed
- **WHEN** instrumentation records submission without presentation or optical timing
- **THEN** the result names that measurement boundary and does not claim input-to-photon latency

### Requirement: Quickshell has its own conditional compatibility trial

<!-- UNVERIFIED -->
The system SHALL permit a minimal Quickshell layer-shell trial only after the declared Qt prerequisite passes. The trial SHALL verify its software renderer, focus, input regions, repeated visibility changes and coexistence with the keyboard and shell gestures. It MUST NOT imply that a panel is a compositor, or that a full Omarchy configuration is supported.

#### Scenario: A panel shares the running shell
- **WHEN** the operator opens, interacts with and dismisses the candidate panel
- **THEN** its declared input region and focus behavior are observed and ordinary apps, keyboard and shell gestures regain control after dismissal

#### Scenario: Qt prerequisites fail
- **WHEN** the Qt trial fails a prerequisite or lacks required evidence
- **THEN** the Quickshell trial is reported as not run and its tasks remain open

### Requirement: Every physical trial restores the normal session

<!-- UNVERIFIED -->
The trial SHALL run within an independently bounded lifetime, preserve the known normal session, and record its restoration after success, failure or cancellation. Real finger observations, injected inputs, native captures and host checks MUST remain distinct evidence classes. Final recommendations SHALL separately assess Qt Quick apps and Quickshell shell surfaces with remaining limitations.

#### Scenario: The probe becomes unresponsive
- **WHEN** the probe times out or its controller disappears
- **THEN** an independent cleanup path removes its processes/surfaces and the operator verifies the original shell and recovery controls remain usable

#### Scenario: A recommendation is published
- **WHEN** the trial results are reviewed
- **THEN** the committed report links the exact evidence for each recommendation and identifies all unperformed physical checks without presenting the probe as a shipped shell

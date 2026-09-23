## Purpose

This capability gives the handheld a single, reviewable UX contract across boot, discovery, touch navigation, application states, and recovery, while preserving evidence boundaries between host checks, injected input, native captures, and real-finger observations.

## ADDED Requirements

### Requirement: The project SHALL maintain an evidence-labelled UX plan

*Grounding: docs/research/handheld-ux/evidence-index.md and evidence-review.md link the reviewed source, native, injected and physical observations; unsupported observations remain explicit.*

The plan SHALL describe the person-facing journey from boot to a recoverable application state and SHALL identify the owning layer or successor proposal for each issue. Every observation SHALL name its source artifact and SHALL distinguish host/native/injected evidence from physical-finger or optical evidence; unsupported current behavior SHALL be marked `UNVERIFIED`.

#### Scenario: Reviewer separates evidence classes
- **WHEN** a reviewer reads a claim about boot, touch, readability, motion, or orientation
- **THEN** the plan points to a repository artifact and states whether the claim is host, native, injected, camera, or real-finger evidence, or marks it `UNVERIFIED`

#### Scenario: Review finds an issue without an implementation owner
- **WHEN** an issue spans launcher, shell bar, keyboard, video, or boot layers
- **THEN** the plan names the responsible existing or successor proposal and does not silently assign the work to an unrelated component

### Requirement: The shell UX plan SHALL cover first use and discovery

*Grounding: docs/research/handheld-ux/flow-matrix.md records boot, discovery, keyboard, media and recovery journeys with their owners, evidence and open gates.*

The plan SHALL define an observable first-use path: boot feedback into the portrait shell, a clear initial action, Apps discovery through desktop entries, Help or equivalent orientation, and a recoverable empty/error state. It SHALL preserve existing working bar controls while proposing consistent labels and focus behavior.

#### Scenario: New user reaches an application
- **WHEN** a person follows the documented first-use flow from a completed boot
- **THEN** the plan records whether they can identify the primary action, open Apps, distinguish labels from controls, and return through Back or Home, with explicit unknowns where observation is absent

#### Scenario: Catalog or app launch is unavailable
- **WHEN** the catalog is empty, stale, or an application fails to launch
- **THEN** the plan records the current visible feedback and specifies a recovery path such as Back, Home, Help, or a retained system control

### Requirement: The plan SHALL define a coherent portrait visual and touch system

*Grounding: docs/research/handheld-ux/interaction-contract.md, three annotated SVG sheets and design-review.md establish measurable planning criteria; physical readability and reachability remain UNVERIFIED.*

The plan SHALL provide measurable guidance for hierarchy, type, spacing, color contrast, touch target geometry, reachability, keyboard-visible layout, and focus indication at the 568x1232 portrait panel. It SHALL treat rotation as unsupported until a source or board observation proves it, and SHALL not infer readability or reachability from injected input alone.

#### Scenario: Reviewer evaluates a screen
- **WHEN** a screen or card is reviewed at the panel's target geometry
- **THEN** the review records text roles, spacing and target bounds, contrast/readability observations, keyboard occlusion, and whether the evidence is optical or only native/injected

#### Scenario: Person touches a control near an edge
- **WHEN** a real-finger acceptance capture exercises a primary control with and without the keyboard visible
- **THEN** the audit records whether the control was reachable without an accidental neighboring action and provided visible feedback, with panel orientation, camera limitations, and unresolved findings

### Requirement: Navigation and transient states SHALL have consistent recovery semantics

*Grounding: docs/research/handheld-ux/interaction-contract.md and flow-matrix.md define visible routes and state ownership; runtime completion remains gated by the respective changes.*

The plan SHALL define how Apps, Windows/overview, cards, Back, Home, Keyboard, System, and video controls compose; how focus changes; and how loading, empty, network failure, EOF, cancellation, and cleanup are exposed. Existing card proposals own card state and gesture mechanics; this capability owns cross-surface consistency and acceptance.

#### Scenario: Person leaves an application
- **WHEN** a person uses Back or Home while an ordinary application is running
- **THEN** the plan preserves the app/card according to the existing multitasking contract, keeps the shell bar available, and records the resulting focus surface

#### Scenario: Person explicitly stops owned work
- **WHEN** a person uses Stop or closes an owned video/session surface
- **THEN** that owner cleans up its resources, the shell bar remains available, and focus returns to a predictable usable surface

#### Scenario: Person encounters a delayed or failed operation
- **WHEN** loading stalls, a network source fails, media reaches EOF, or a catalog/window becomes empty
- **THEN** the plan evaluates the visible feedback and recovery, records any orphaned or blocked surface, and specifies a bounded recovery contract without requiring a hidden keyboard command

### Requirement: The plan SHALL define measurable acceptance and an ordered successor backlog

*Grounding: docs/research/handheld-ux/issue-ledger.md maps P0/P1 findings to the two published successors and existing card/video owners; audit and proposals were pushed through master 7e4cc02.*

The plan SHALL maintain a severity-ranked issue ledger, user-flow/task matrix, P0/P1 successor proposals, dependencies, and parallel ownership. Each successor SHALL have host and board gates where applicable, and all resulting proposals SHALL be validated, merged and pushed to master before implementation is treated as integrated.

#### Scenario: Team schedules parallel work
- **WHEN** the team selects the next UX issue
- **THEN** the ledger identifies severity, evidence gap, owner, dependency, narrow proof command, and whether work can proceed host-only or requires the board

#### Scenario: Team claims UX completion
- **WHEN** a successor proposal is reviewed as complete
- **THEN** its acceptance cites measurable checks for the affected flow and retains explicit open markers for unperformed physical, optical, accessibility, or orientation tests

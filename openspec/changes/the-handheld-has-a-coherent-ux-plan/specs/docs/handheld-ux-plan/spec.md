## Purpose

This capability gives the handheld a single, reviewable UX contract across boot, discovery, touch navigation, application states, and recovery, while preserving evidence boundaries between host checks, injected input, native captures, and real-finger observations.

## ADDED Requirements

### Requirement: The project SHALL maintain an evidence-labelled UX plan

The plan SHALL describe the person-facing journey from boot to a recoverable application state and SHALL identify the owning layer or successor proposal for each issue. Every observation SHALL name its source artifact and SHALL distinguish host/native/injected evidence from physical-finger or optical evidence; unsupported current behavior SHALL be marked `UNVERIFIED`.

#### Scenario: Reviewer separates evidence classes
- **WHEN** a reviewer reads a claim about boot, touch, readability, motion, or orientation
- **THEN** the plan points to a repository artifact and states whether the claim is host, native, injected, camera, or real-finger evidence, or marks it `UNVERIFIED`

#### Scenario: Review finds an issue without an implementation owner
- **WHEN** an issue spans launcher, shell bar, keyboard, video, or boot layers
- **THEN** the plan names the responsible existing or successor proposal and does not silently assign the work to an unrelated component

### Requirement: The shell UX plan SHALL cover first use and discovery

The plan SHALL define an observable first-use path: boot feedback into the portrait shell, a clear initial action, Apps discovery through desktop entries, Help or equivalent orientation, and a recoverable empty/error state. It SHALL preserve existing working bar controls while proposing consistent labels and focus behavior.

#### Scenario: New user reaches an application
- **WHEN** a person follows the documented first-use flow from a completed boot
- **THEN** they can identify the shell's primary action, open Apps, distinguish app labels from controls, and return through Back or Home without losing the usable shell

#### Scenario: Catalog or app launch is unavailable
- **WHEN** the catalog is empty, stale, or an application fails to launch
- **THEN** the visible state explains what happened and offers a usable recovery path such as Back, Home, Help, or a retained system control

### Requirement: The plan SHALL define a coherent portrait visual and touch system

The plan SHALL provide measurable guidance for hierarchy, type, spacing, color contrast, touch target geometry, reachability, keyboard-visible layout, and focus indication at the 568x1232 portrait panel. It SHALL treat rotation as unsupported until a source or board observation proves it, and SHALL not infer readability or reachability from injected input alone.

#### Scenario: Reviewer evaluates a screen
- **WHEN** a screen or card is reviewed at the panel's target geometry
- **THEN** the review records text roles, spacing and target bounds, contrast/readability observations, keyboard occlusion, and whether the evidence is optical or only native/injected

#### Scenario: Person touches a control near an edge
- **WHEN** a real-finger acceptance capture exercises a primary control with and without the keyboard visible
- **THEN** the control is reachable without an accidental neighboring action, provides visible focus/pressed feedback, and the result records panel orientation and camera limitations

### Requirement: Navigation and transient states SHALL have consistent recovery semantics

The plan SHALL define how Apps, Windows/overview, cards, Back, Home, Keyboard, System, and video controls compose; how focus changes; and how loading, empty, network failure, EOF, cancellation, and cleanup are exposed. Existing card proposals own card state and gesture mechanics; this capability owns cross-surface consistency and acceptance.

#### Scenario: Person leaves an application
- **WHEN** a person uses Back, Home, or an explicit Stop from a running app or video session
- **THEN** the app's owned resources are cleaned up, the shell bar remains available, and focus returns to a predictable usable surface

#### Scenario: Person encounters a delayed or failed operation
- **WHEN** loading stalls, a network source fails, media reaches EOF, or a catalog/window becomes empty
- **THEN** the UI communicates the state, avoids an orphaned or indefinitely blocked surface, and offers a bounded recovery action without requiring a hidden keyboard command

### Requirement: The plan SHALL define measurable acceptance and an ordered successor backlog

The plan SHALL maintain a severity-ranked issue ledger, user-flow/task matrix, P0/P1 successor proposals, dependencies, and parallel ownership. Each successor SHALL have host and board gates where applicable, and all proposals SHALL be intended to land on master before implementation is treated as integrated.

#### Scenario: Team schedules parallel work
- **WHEN** the team selects the next UX issue
- **THEN** the ledger identifies severity, evidence gap, owner, dependency, narrow proof command, and whether work can proceed host-only or requires the board

#### Scenario: Team claims UX completion
- **WHEN** a successor proposal is reviewed as complete
- **THEN** its acceptance cites measurable checks for the affected flow and retains explicit open markers for unperformed physical, optical, accessibility, or orientation tests

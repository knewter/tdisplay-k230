## Purpose

Defines the evidence gates and safe ownership boundaries for an opt-in visual
application-card composition experiment in the handheld shell.

## ADDED Requirements

### Requirement: Card composition has a source-grounded architecture decision
The system SHALL retain one Sway-owned DRM/KMS presentation path while a card experiment is active. Before a visual-card implementation is selected, the project SHALL compare existing client/protocol and narrow compositor routes using pinned source evidence for application-surface composition, touch routing, focus return, frame completion, and presentation reporting. A client-only metadata overlay SHALL NOT be represented as live application-card composition.

<!-- UNVERIFIED: the required source audit and live compositor experiment have not run. -->

#### Scenario: A route is selected
- **WHEN** the project selects an implementation route
- **THEN** the recorded decision names the compared boundaries, selected or rejected route, one DRM owner, Pixman/default-session fallback, and unresolved limits

### Requirement: A visual-card prototype proves the complete two-app interaction
If the architecture decision establishes a viable route, an opt-in prototype SHALL prove two simultaneously running application surfaces visually represented in a single card scene, continuous finger tracking, adjacent-card selection and expansion, and a dismissal request with an explicit close-refusal outcome. It SHALL preserve keyboard focus and the existing usable Pixman session on failure. A grounded negative decision SHALL state that product delivery is blocked, not call the capability delivered.

<!-- UNVERIFIED: no compositor-owned visual-card scene has been built or run on the board. -->

#### Scenario: A card interaction is exercised
- **WHEN** an operator enters the card scene with two eligible applications
- **THEN** evidence distinguishes app shrink, drag, adjacent selection/expansion, dismissal request, refusal or exit, and restored focus

### Requirement: Card evidence measures composition boundaries
The prototype SHALL record CPU, memory, frame/presentation evidence, pixel format, buffer lifetime, and synchronization observations separately from host models. It SHALL not claim GPU acceleration, zero-copy, or full card UX acceptance unless those observations demonstrate them.

<!-- UNVERIFIED: no live two-app composition measurement exists. -->

#### Scenario: A board prototype completes
- **WHEN** the board prototype exits or falls back
- **THEN** its record identifies the active renderer, format, buffer ownership, completion evidence, resource deltas, and whether the normal shell remained usable

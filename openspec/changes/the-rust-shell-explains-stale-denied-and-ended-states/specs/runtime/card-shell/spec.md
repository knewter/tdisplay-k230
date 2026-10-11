## ADDED Requirements
### Requirement: Window-list states SHALL name a recovery action
<!-- UNVERIFIED: no Rust-shell implementation or board observation yet. -->
The card shell SHALL show short person-facing copy and a visible Back, Apps, or Home action while the window list is loading, empty, or stale. It SHALL NOT render raw filesystem paths, helper diagnostics, or secrets in that copy.

#### Scenario: The window list is empty or stale
- **WHEN** no current selectable window remains
- **THEN** the surface says so and keeps Apps, Back, or Home available without focusing a different window

#### Scenario: The window list is loading
- **WHEN** the list has not yet been received
- **THEN** the surface says it is loading and offers Back

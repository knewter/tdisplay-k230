## ADDED Requirements
### Requirement: Window-list states SHALL name a recovery action
<!-- UNVERIFIED: implemented and host-tested (cargo test, tests/test_video_session.py) and installed on the board 2026-10-11 (docs/evidence/recovery-routes/installed-2026-10-11/); no glass observation of this state. Real-finger capture is task 3.1 of the-shell-proves-recovery-states-by-touch. -->
The card shell SHALL show short person-facing copy and a visible Back, Apps, or Home action while the window list is loading, empty, or stale. It SHALL NOT render raw filesystem paths, helper diagnostics, or secrets in that copy.

#### Scenario: The window list is empty or stale
- **WHEN** no current selectable window remains
- **THEN** the surface says so and keeps Apps, Back, or Home available without focusing a different window

#### Scenario: The window list is loading
- **WHEN** the list has not yet been received
- **THEN** the surface says it is loading and offers Back

## ADDED Requirements
### Requirement: A denied system action SHALL explain itself
<!-- UNVERIFIED: implemented and host-tested (cargo test, tests/test_video_session.py) and installed on the board 2026-10-11 (docs/evidence/recovery-routes/installed-2026-10-11/); no glass observation of this state. Real-finger capture is task 3.1 of the-shell-proves-recovery-states-by-touch. -->
When a system action is refused, the shell SHALL show short person-facing copy and a visible Back or Retry action, and SHALL NOT render raw paths, helper output, or secrets.

#### Scenario: An action is denied
- **WHEN** a person requests a system action the system refuses
- **THEN** the surface says the action was not allowed and shows Back

## ADDED Requirements
### Requirement: Ended video states SHALL name a recovery action
<!-- UNVERIFIED: implemented and host-tested (cargo test, tests/test_video_session.py) and installed on the board 2026-10-11 (docs/evidence/recovery-routes/installed-2026-10-11/); no glass observation of this state. Real-finger capture is task 3.1 of the-shell-proves-recovery-states-by-touch. -->
After video Stop, end-of-file, or cancellation, the shell SHALL show short copy for that state and a visible Back, Apps, or Home action, without raw paths or diagnostics.

#### Scenario: Playback reaches end of file
- **WHEN** a video finishes
- **THEN** the surface says it ended and offers Back or Apps

#### Scenario: Playback is cancelled
- **WHEN** a person cancels loading or playback
- **THEN** the surface says it was cancelled and offers Back

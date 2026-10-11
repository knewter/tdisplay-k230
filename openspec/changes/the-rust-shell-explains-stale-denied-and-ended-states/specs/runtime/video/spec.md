## ADDED Requirements
### Requirement: Ended video states SHALL name a recovery action
<!-- UNVERIFIED: no Rust-shell implementation or board observation yet. -->
After video Stop, end-of-file, or cancellation, the shell SHALL show short copy for that state and a visible Back, Apps, or Home action, without raw paths or diagnostics.

#### Scenario: Playback reaches end of file
- **WHEN** a video finishes
- **THEN** the surface says it ended and offers Back or Apps

#### Scenario: Playback is cancelled
- **WHEN** a person cancels loading or playback
- **THEN** the surface says it was cancelled and offers Back

## ADDED Requirements

### Requirement: A finger on the glass drives the shell under the mainline kernel
On the mainline full shell, a deliberate finger tap or drag on the panel SHALL
reach sway and change what the shell shows, as it does under the vendor kernel.

#### Scenario: Tap opens something visible
- **WHEN** a person taps a Home target on the mainline full shell while the camera records
- **THEN** the panel changes as it does for the same tap on the vendor-kernel shell, and sway's input log records the touch
<!-- UNVERIFIED: touch proven only via evtest on the console image (2026-10-06) -->

#### Scenario: Touch capture completes without a timeout
- **WHEN** the trial controller captures a long touch session
- **THEN** it reports a complete contact summary instead of an unverified retrieval

## ADDED Requirements

### Requirement: The coherent shell boots the selected system with matching boot artifacts

*Grounding: `docs/evidence/boot-verification/2026-10-01/README.md` records the mismatch between working runtime, booted kernel, persistent profile and explicit boot init, and the failed matching-current-kernel trial. The corrected deployment behavior remains UNVERIFIED.*

<!-- UNVERIFIED --> The system SHALL provide matching kernel, initrd, board device tree and explicit boot init for the selected coherent-shell configuration. After ordinary boot the person SHALL see a usable shell on the panel and the serial console SHALL report that exact selected system, rather than an older boot generation.

#### Scenario: A qualified shell update is rebooted
- **WHEN** a qualified coherent-shell bundle is installed and the device boots normally
- **THEN** the panel shows the usable shell, navigation responds, and serial identities match the selected system and its boot artifacts

#### Scenario: A runtime activation has not installed matching boot files
- **WHEN** an updated shell runs after test activation but persistent boot still selects an older generation
- **THEN** its published status identifies runtime-only deployment and does not claim the new system survives reboot

### Requirement: A failed coherent-shell boot remains recoverable

*Grounding: the same committed physical trial restored unchanged normal boot artifacts and photographed Home. Persistent bundle install/rollback is not yet qualified.*

<!-- UNVERIFIED --> The system update procedure SHALL retain a usable normal boot backup and serial recovery before selection. A failed candidate SHALL remain unaccepted until the normal system is restored and its visible shell and protected identities are observed.

#### Scenario: The candidate starts services but the panel is black
- **WHEN** a candidate reaches serial login and active services but fails visible shell acceptance
- **THEN** it is recorded as a failed display trial, the normal system is restored, and the failed candidate is not selected as the persistent default

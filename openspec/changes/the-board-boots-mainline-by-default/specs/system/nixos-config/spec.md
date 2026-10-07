## ADDED Requirements

### Requirement: The installed daily system is the mainline coherent shell
The system profile and `/boot` mutable files SHALL select the mainline coherent
shell built from this repository, with stage 1 and the DT selector files
unchanged, and the board-side trial tooling SHALL treat that installed system as
the protected normal it verifies before and after every trial.

#### Scenario: Installed identities are recorded
- **WHEN** installation completes
- **THEN** the recorded installer journal lists the new system, the four replaced boot files with hashes, the unchanged protected files, and the retained rollback roots
<!-- UNVERIFIED -->

#### Scenario: Trials guard the new normal
- **WHEN** a guarded mainline trial runs after installation
- **THEN** its preflight and recovery checks expect the installed mainline identities, not the vendor 6.6 ones
<!-- UNVERIFIED -->

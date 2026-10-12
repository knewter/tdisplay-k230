## ADDED Requirements

### Requirement: The board accepts key-only SSH alongside the console
<!-- UNVERIFIED: proposed 2026-10-11; a runtime-only sshd under /run was used on the board that day, but the image does not yet enable SSH. -->
The system SHALL run an SSH server reachable over the board's network
connection, admitting root by public key only. It SHALL refuse password,
keyboard-interactive and empty-password logins. The serial console SHALL stay
available as the recovery path.

#### Scenario: The operator logs in with the dedicated key
- **WHEN** the operator connects as root with the dedicated key after an ordinary boot
- **THEN** a root shell opens without any password prompt

#### Scenario: A password login is refused
- **WHEN** a client offers only password or keyboard-interactive authentication
- **THEN** the server refuses the login

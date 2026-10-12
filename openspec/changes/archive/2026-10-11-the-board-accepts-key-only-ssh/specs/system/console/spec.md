## ADDED Requirements

### Requirement: The board accepts key-only SSH alongside the console
*Grounding: `docs/evidence/console/ssh-installed-2026-10-11/README.md`: after an ordinary autoboot of system `c6qjs04y` (boot `8050d551`), root logged in with the dedicated key, and a password/keyboard-interactive-only client was refused with `Permission denied (publickey).` The serial console stayed in use throughout the install.*
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

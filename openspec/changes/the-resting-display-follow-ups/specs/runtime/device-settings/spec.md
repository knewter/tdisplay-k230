## ADDED Requirements

### Requirement: Settings chooses the idle timeout

<!-- UNVERIFIED: not built; the current timeout is a fixed 30 s dim and 60 s off, read from `shell-idle.service` on the board (docs/evidence/idle-dim/). -->
Settings SHALL offer Off, 1 minute and 5 minutes for when the display turns
off when idle. The choice SHALL persist across reboots beside the other
shell preferences. The idle service SHALL apply it from its next start.
Dimming SHALL come at half the chosen time. Off SHALL disable both steps.

#### Scenario: Five minutes chosen
- **WHEN** the person picks 5 minutes and leaves the board with no input
- **THEN** the panel dims at 2.5 minutes and turns off at 5 minutes

#### Scenario: Off chosen
- **WHEN** the person picks Off
- **THEN** the panel neither dims nor turns off on its own

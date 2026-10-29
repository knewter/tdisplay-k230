## ADDED Requirements

### Requirement: Settings chooses the idle timeout

*Grounding (2026-10-28): board, build `q8k8w3mb…`. An injected tap on Idle timeout wrote `5m` and restarted the idle service with 150 s and 300 s. Unattended, 5 min dimmed at 146–152 s and turned the output off at 298–303 s, and Off did neither in 366 s (docs/evidence/resting-display-follow-ups/README.md).*
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

### Requirement: Settings tunes the clock screen

*Grounding (2026-10-28): board, build `q8k8w3mb…`, idle path on the charger. Clock brightness Full, Half and Dim held the panel at 148, 74 and 37 of 148 with the card up. Clock effects Off gave no `ttfx` in 360 s against one at +11 s with 5 min. Clock limit None did not close the card in that time; the 2 h and 8 h caps are host tests only (docs/evidence/resting-display-follow-ups/README.md).*
Settings SHALL offer three rows for the clock screen shown while idle on the
charger. Clock brightness SHALL offer Dim, Half and Full, which run the
panel at 25%, 50% and 100% of the saved brightness while the clock screen is
up; Dim is the default. Clock effects SHALL offer 5 min, 15 min and Off for
how often a text effect plays; 5 min is the default. Clock limit SHALL offer
2 h, 8 h and None for how long the clock screen stays up before it closes
itself; 2 h is the default. Each choice SHALL persist across reboots beside
the other shell preferences, and an unreadable or unrecognised value SHALL
mean the default. The brightness SHALL apply the next time the clock screen
opens, and the effect interval and limit the next time the clock screen
starts.

#### Scenario: Full brightness chosen
- **WHEN** the person picks Full and the board goes idle on the charger
- **THEN** the clock screen opens at the brightness the panel had before it dimmed, and waking restores that same value

#### Scenario: Effects off and no limit chosen
- **WHEN** the person picks Off for Clock effects and None for Clock limit
- **THEN** the clock screen plays no effect and stays up until input or the charger is removed

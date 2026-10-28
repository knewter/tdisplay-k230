## ADDED Requirements

### Requirement: Settings chooses what an idle display does on the charger

*Grounding: the preference sits beside Do Not Disturb as a one-word file under `/var/lib/k230-shell-prefs`; no board observation of this row exists.*
<!-- UNVERIFIED: the row has not been built or seen on the board. -->
Settings SHALL list an "Idle on charger" row with the values Clock and Sleep whose hit region meets the shell's 99 px floor. A tap SHALL switch between them and store the choice so it survives a shell restart and a reboot. A missing or unreadable stored choice SHALL mean Clock.

#### Scenario: Choose Sleep

- **WHEN** a person taps the row until it reads Sleep and leaves the device idle on the charger
- **THEN** the display dims and turns off as on battery

#### Scenario: Fresh home

- **WHEN** no choice has ever been stored
- **THEN** the row reads Clock

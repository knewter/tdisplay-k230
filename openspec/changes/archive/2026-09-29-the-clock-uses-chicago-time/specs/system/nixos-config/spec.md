## ADDED Requirements

### Requirement: Chicago local time is the image default

The system SHALL use `America/Chicago` as its local timezone, providing Central local time to applications without restoring home-directory state. This is owned by the NixOS system; it does not change the UTC hardware-clock or synchronization policy.

*Grounding: `docs/evidence/chicago-clock/runtime.json` records the physical board reporting `Timezone=America/Chicago` and a local CDT offset after the requested runtime setting. The repository configuration and installed profile are verified separately in the same evidence directory.*

#### Scenario: Default configuration is built

- **WHEN** the board configuration is evaluated and built
- **THEN** its timezone is America/Chicago and its generated localtime link selects that zone

#### Scenario: Profile is activated

- **WHEN** the configured profile is activated on the board
- **THEN** `timedatectl` reports America/Chicago and ordinary local-time output uses the zone's current offset

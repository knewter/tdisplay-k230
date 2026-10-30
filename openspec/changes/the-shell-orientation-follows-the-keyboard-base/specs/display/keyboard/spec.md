## ADDED Requirements

### Requirement: The system reports whether the keyboard base is attached while running

*Grounding: the chips and their addresses are grounded by `docs/evidence/keyboard-base/probe/` (hardware I2C4, attached case). That Linux does not bind the keypad on a late attach, and the base-absent and hot attach or detach behaviour, are <!-- UNVERIFIED: not observed on the board. -->*

The system SHALL determine, at boot and continuously afterwards, whether the keyboard base is attached from a read-only probe of the base's chips on hardware I2C4, and SHALL expose the result to the rest of the system as a state that changes on attach and detach, including an attach after boot. The probe SHALL NOT write a register of any base chip and SHALL NOT depend on the keypad's input device existing. The system owns this requirement; stage 1's own probe belongs to the boot text-effects change.

#### Scenario: Attached after boot

- **WHEN** the board boots without the base and is then clipped in
- **THEN** the reported state changes to attached without a reboot, even though the keypad's input device may not appear

#### Scenario: Detached after boot

- **WHEN** the board boots in the base and is then removed
- **THEN** the reported state changes to detached, even if the keypad's input device is still registered

#### Scenario: No console noise

- **WHEN** the base is absent for a long period
- **THEN** the console shows no repeated bus errors from the probe

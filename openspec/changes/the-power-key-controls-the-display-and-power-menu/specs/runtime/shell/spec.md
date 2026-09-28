## ADDED Requirements

### Requirement: The physical power key opens a touch power sheet

<!-- UNVERIFIED: the existing Settings power confirmation and shell overlay are source-grounded; physical power-key entry needs on-board proof. -->
The shell SHALL present a readable, touch-operated power sheet above the current app when the physical power key is held. It SHALL offer Cancel, Power off and Restart. Tapping outside or using the shell dismissal gesture SHALL close the sheet without a system action. The sheet SHALL not strand a user when an action is unavailable.

#### Scenario: Open and dismiss

- **WHEN** the person holds the power key and then taps Cancel or dismisses the sheet
- **THEN** the prior app remains available and no shutdown or restart is requested

#### Scenario: An action is unavailable

- **WHEN** the system denies or cannot perform a power action
- **THEN** the shell reports the failure visibly and retains a route back to the app

### Requirement: Destructive power actions require explicit confirmation

The shell SHALL require a second touch confirmation naming Power off or Restart before invoking it. Opening the power sheet or merely holding the key SHALL never confirm an action. Confirmation SHALL use the same bounded system authority as the existing Settings power controls.

#### Scenario: Select Power off

- **WHEN** the person selects Power off in the sheet
- **THEN** a distinct confirmation with Cancel appears, and no power command runs until the person confirms

#### Scenario: Select Restart and cancel

- **WHEN** the person selects Restart and then Cancel
- **THEN** the running app and shell remain available without a restart

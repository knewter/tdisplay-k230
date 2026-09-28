## Purpose

Lets the physical power key control the handheld display and request explicit system power actions without losing the running session on an ordinary tap.

## ADDED Requirements

### Requirement: The system reports the physical power key

<!-- UNVERIFIED: PMU INT0 events require the candidate kernel and physical button proof. The vendor K230 PMU driver patch 0064 is source grounding, not board acceptance. -->
The system SHALL expose press and release of the identified physical PMU power key to Linux as input events. An ordinary press SHALL NOT directly reset or shut down the running system. The system SHALL leave any separately wired hardware RESET button outside this policy.

#### Scenario: Short physical press

- **WHEN** a person presses and releases the identified power key briefly on the running board
- **THEN** Linux records one press and one release and the system remains running

#### Scenario: A separate reset button

- **WHEN** the board has a distinct hardware RESET button
- **THEN** this capability makes no claim to intercept its electrical reset path

### Requirement: Short press controls the display

<!-- UNVERIFIED: exact PMU input and on-glass display behavior require board proof. The current backlight spec grounds DPMS off/on brightness restoration only. -->
A short physical power-key press SHALL turn the panel off when lit and turn it on when off, while preserving the running applications and selected brightness. Waking the panel SHALL consume that key gesture without activating an application or power action.

#### Scenario: Screen goes dark without losing the session

- **WHEN** the display is lit and the person briefly presses the power key
- **THEN** the panel turns off, the system remains running and its application state is preserved

#### Scenario: Screen wakes

- **WHEN** the display is off and the person briefly presses the power key
- **THEN** the panel returns at the prior brightness, without an app tap or restart

### Requirement: Holds do not directly request a destructive action

<!-- UNVERIFIED: power-key hold timing and hardware override require physical board proof. -->
The system SHALL distinguish a deliberate hold from a short press. A hold SHALL open the shell's power sheet once and SHALL NOT also toggle the panel on release. A hold alone SHALL NOT reboot or power off the system.

#### Scenario: Hold the power key

- **WHEN** the person holds the physical key through the configured long-press threshold and then releases it
- **THEN** one power sheet is shown and the running system remains available

#### Scenario: Release before threshold

- **WHEN** the person releases the key before the long-press threshold
- **THEN** only the short-press display action occurs

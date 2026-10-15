# system/power Specification

## Purpose
Lets the physical power key control the handheld display and request explicit system power actions without losing the running session on an ordinary tap.

## Requirements

### Requirement: The system reports the physical power key

*Grounding: The mainline `k230-pmu-pwrkey` driver logs INT0 press and release for the top-right button (SW2), and evemu recorded one KEY_POWER press and release per tap with the board still running (docs/evidence/power-key/identity/, docs/evidence/power-key/mainline-events/). The separate RESET button is outside this driver.*
The system SHALL expose press and release of the identified physical PMU power key to Linux as input events. An ordinary press SHALL NOT directly reset or shut down the running system. The system SHALL leave any separately wired hardware RESET button outside this policy.

#### Scenario: Short physical press

- **WHEN** a person presses and releases the identified power key briefly on the running board
- **THEN** Linux records one press and one release and the system remains running

#### Scenario: A separate reset button

- **WHEN** the board has a distinct hardware RESET button
- **THEN** this capability makes no claim to intercept its electrical reset path

### Requirement: Short press controls the display

*Grounding: Board-read and operator 2026-10-14: taps darkened and woke the panel in the same session (DSI-1 power false/true), and with HDMI connected the same taps sent `output * power off/on` and blanked and woke the monitor (docs/evidence/power-key/display/).*
A short physical power-key press SHALL turn the display in effect (the panel, or the HDMI monitor while it is the output) off when lit and on when off, keeping that state across an HDMI hotplug, while preserving the running applications and selected brightness. Waking the panel SHALL consume that key gesture without activating an application or power action.

#### Scenario: Screen goes dark without losing the session

- **WHEN** the display is lit and the person briefly presses the power key
- **THEN** the display turns off, the system remains running and its application state is preserved

#### Scenario: Screen wakes

- **WHEN** the display is off and the person briefly presses the power key
- **THEN** the display returns at the prior brightness, without an app tap or restart

### Requirement: Holds do not directly request a destructive action

*Grounding: On the board 2026-10-14, a 1.15 s hold opened one sheet with the system still running (journal INT0 press, map-request, INT0 release; docs/evidence/power-key/sheet/); the 0.7 s threshold and no toggle after a hold are host tests (`tests/test_power_keyd.py`). The PMU's own long-press power-off is not exercised.*
The system SHALL distinguish a deliberate hold from a short press. A hold SHALL open the shell's power sheet once and SHALL NOT also toggle the panel on release. A hold alone SHALL NOT reboot or power off the system.

#### Scenario: Hold the power key

- **WHEN** the person holds the physical key through the configured long-press threshold and then releases it
- **THEN** one power sheet is shown and the running system remains available

#### Scenario: Release before threshold

- **WHEN** the person releases the key before the long-press threshold
- **THEN** only the short-press display action occurs

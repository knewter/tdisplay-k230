# system/battery Specification

## Purpose
Report the keyboard base's battery and charger truthfully to Linux and the shell, and stop the system cleanly before the battery browns it out.

## Requirements

### Requirement: The battery and charger are Linux power-supply devices

<!-- The gauge at 0x55 and charger at 0x6B answered read-only i2cget on 2026-10-13 (docs/evidence/keyboard-base/probe/). Board-read 2026-10-14: the forward-ported `bq27xxx` BQ27220 entry and `bq25890_charger` (polled, no INT line; operator closed the INT search) report capacity, status, voltage, current and `online` with the cable in, out and in Hi-Z (docs/evidence/keyboard-base/charger/). -->
With the keyboard base attached, the system SHALL expose a battery `power_supply` device that reports state of charge, voltage, current and charging status from the fuel gauge, and a charger `power_supply` device that reports whether external power is present. Readings SHALL come from the chips, not from an estimate.

#### Scenario: Reading the battery

- **WHEN** an operator reads `/sys/class/power_supply/*/capacity` and `status` on the board with the base attached
- **THEN** a battery device reports a percentage and a status, and its voltage agrees within 50 mV with the charger's battery-voltage reading taken at the same time

#### Scenario: Plugging in

- **WHEN** a charging cable is connected to the base and then removed
- **THEN** the charger device reports external power present and then absent, and the battery status changes between Charging and Discharging accordingly

### Requirement: Binding the charger driver does not change how the battery charges

<!-- The live BQ25896 registers read 704 mA charge current, 4288 mV regulation voltage and the watchdog disabled on 2026-10-13, matching LILYGO (docs/evidence/keyboard-base/probe/). Board-read 2026-10-14: binding changed only REG02 CONV_RATE (docs/evidence/keyboard-base/charger/registers-bound-2026-10-14.log). UNVERIFIED: whether these hold from a cold start; the base's battery kept the charger powered after LILYGO's firmware had run on it. -->
The system SHALL configure the charger driver with the charge current, regulation voltage, termination and precharge values the charger already holds on this board, as read by the read-only probe. Any register the driver would write to a different value SHALL be named in committed evidence before that image boots on the board.

#### Scenario: Charger registers before and after

- **WHEN** the charger's configuration registers are read before the driver is bound and again after boot with it bound
- **THEN** the charge-current and regulation-voltage fields are unchanged, or the difference is the one named in evidence

### Requirement: A low battery warns, and a critical battery shuts down cleanly

<!-- Board-read 2026-10-14: a real ~400 mA discharge with raised thresholds produced the warnings, the countdown, a cancel on charge, and a poweroff that cut power (docs/evidence/keyboard-base/battery-policy/); the operator saw it go dark. Real 15/5/3 % thresholds have not been reached on a full discharge. -->
While discharging, the system SHALL notify the person once when the charge reaches 15% and again at 5%. At 3%, after two consecutive readings at or below that level, it SHALL show a 60-second shutdown warning and then request a clean poweroff. Connecting power during the warning SHALL cancel it. The levels SHALL be image options, and the shutdown SHALL be possible to disable.

#### Scenario: Low battery

- **WHEN** the battery discharges past 15%
- **THEN** one notification appears in the shell, and it is not repeated at 14%

#### Scenario: Critical battery

- **WHEN** the battery discharges to 3% with no power connected
- **THEN** a shutdown warning appears and, 60 seconds later, the system powers off cleanly, with the journal showing an ordinary shutdown

#### Scenario: Rescued by a cable

- **WHEN** power is connected during the shutdown warning
- **THEN** the warning closes and the system keeps running

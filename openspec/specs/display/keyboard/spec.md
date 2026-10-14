# display/keyboard Specification

## Purpose
Make the keyboard base's physical keys, Caps Lock light and key backlight usable from Linux and the shell, with a layout that matches the printed legends.

## Requirements

### Requirement: The system finds the keyboard base without writing to it

<!-- Grounded for the attached case: tools/keyboard-base-probe.sh on 2026-10-13 found 0x20, 0x34, 0x38, 0x55 and 0x6B on hardware I2C4 (IO46/IO47) with reads only (docs/evidence/keyboard-base/probe/). UNVERIFIED: the base-absent scenario has not been booted. -->
The system SHALL establish which keyboard-base chips answer, at which I2C address and over which bus, by a read-only probe recorded before any driver is bound to them. The probe SHALL NOT write a register of any keyboard-base chip. The system owns this requirement; stage 1 is unchanged.

#### Scenario: The base is attached

- **WHEN** an operator runs the recorded probe command on a board clipped into the keyboard base
- **THEN** the evidence lists each answering address and the bus used, and no chip register was written

#### Scenario: The base is absent

- **WHEN** the same image boots on a board without the keyboard base
- **THEN** the system and shell start normally and report no keyboard base, with no repeated bus errors on the console

### Requirement: The base's keys type into the focused application

<!-- The legend and Shift tables come from LILYGO `ui_hardware.c` `tca8418_key_name()` and `extension_keyboard_shift_symbol_for_code()`. Board-read evtest and evemu recordings, and the operator typing on the base 2026-10-13/14 (docs/evidence/keyboard-base/keys/); the operator waived a per-key recording. -->
Pressing a key on the base SHALL deliver the character or action printed on it to the focused application through the shell's normal keyboard path. Shift SHALL produce the symbol the vendor layout assigns to that key. Holding a key SHALL repeat it. A USB or Bluetooth keyboard attached at the same time SHALL keep its own layout.

#### Scenario: Typing a command

- **WHEN** a person types `ls -la` on the base into the terminal and presses Enter
- **THEN** the command runs and its output appears on the panel, in a native capture and a camera frame

#### Scenario: Punctuation on Shift

- **WHEN** a person types Shift with a letter key whose vendor Shift symbol is punctuation
- **THEN** that punctuation character, not an uppercase letter, appears in the focused application

#### Scenario: Caps Lock

- **WHEN** a person presses Caps then types letters
- **THEN** the letters are uppercase and the Caps Lock LED is lit, and pressing Caps again turns both off

### Requirement: The key backlight is a controllable light

<!-- IO52/PWM4 comes from LILYGO `HARDWARE_PINMAP.md` and `ui_hardware.c`. Board 2026-10-14: the ported K230 PWM driver dims it; the operator saw the levels dim and 0 go dark (docs/evidence/keyboard-base/backlight/). -->
The system SHALL expose the key backlight as a Linux LED device named with the `kbd_backlight` suffix. The shell SHALL turn it on when a key is pressed, turn it off after a configurable idle period without key presses, and keep it off while the panel is off. A person SHALL be able to choose its level, or turn it off entirely, in Settings. Without a PWM driver the only levels SHALL be on and off; with the K230 PWM driver the LED SHALL dim.

#### Scenario: Typing in the dark

- **WHEN** the backlight setting is on and a person presses a key
- **THEN** the key legends light within one press, as a camera frame shows

#### Scenario: Idle

- **WHEN** no key is pressed for the configured idle period
- **THEN** the key backlight turns off, and the next key press turns it on again

#### Scenario: The panel goes off

- **WHEN** the panel is turned off
- **THEN** the key backlight is off until the panel is on again and a key is pressed

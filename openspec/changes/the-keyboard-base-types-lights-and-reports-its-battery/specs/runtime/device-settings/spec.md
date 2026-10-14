## ADDED Requirements

### Requirement: Settings offers a keyboard backlight control only when the base has one

<!-- Board 2026-10-14: Settings shows the Key backlight row on the base and an injected tap toggles it (docs/evidence/keyboard-base/shell/board/); host renders show it hidden without the LED and showing the level with it. The PWM LED has 255 steps (docs/evidence/keyboard-base/backlight/); the levels are 8 %, 30 % and 100 % of it in `keyboard_based.py`. -->
When a `kbd_backlight` LED device exists, Settings SHALL offer a keyboard backlight control: an on/off switch while the device has one brightness step, and a choice of levels once it has more (Off, Low, Medium and High; each tap steps to the next). The choice SHALL persist across reboots in system state, not in a home directory. When no such device exists, Settings SHALL NOT show the control.

#### Scenario: Turning the key backlight off

- **WHEN** a person turns the keyboard backlight off in Settings and then types
- **THEN** the key legends stay dark, and stay dark after a reboot

#### Scenario: No keyboard base

- **WHEN** a person opens Settings on a board without the keyboard base
- **THEN** no keyboard backlight control appears

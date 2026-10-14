## ADDED Requirements

### Requirement: Settings offers a keyboard backlight control only when the base has one

<!-- Board 2026-10-14: Settings shows the Key backlight row on the base and an injected tap toggles it (docs/evidence/keyboard-base/shell/board/); host renders show it hidden without the LED and, with it, a four-detent slider (Off, Low, Medium, High). The PWM LED has 255 steps (docs/evidence/keyboard-base/backlight/); Low, Medium and High are 8 %, 30 % and 100 % of it in `keyboard_based.py`. Board 2026-10-14: the slider on the glass previews each level live (operator) and the LED reads 20/76/255 within 0.5 s of each stored level (docs/evidence/keyboard-base/backlight/). -->
When a `kbd_backlight` LED device exists, Settings SHALL offer a keyboard backlight control: an on/off switch while the device has one brightness step, and a level slider once it has more. The choice SHALL persist across reboots in system state, not in a home directory. Moving the slider to a lit level SHALL light the keys at that level within a fraction of a second, for a short preview, without a key press; outside that preview the keys stay lit only while typing. When no such device exists, Settings SHALL NOT show the control.

#### Scenario: Turning the key backlight off

- **WHEN** a person turns the keyboard backlight off in Settings and then types
- **THEN** the key legends stay dark, and stay dark after a reboot

#### Scenario: Choosing a level shows it live

- **WHEN** a person drags the keyboard backlight slider from Low to High
- **THEN** the key legends light at each level as the slider reaches it, and go dark again a few seconds after the drag if nobody types

#### Scenario: No keyboard base

- **WHEN** a person opens Settings on a board without the keyboard base
- **THEN** no keyboard backlight control appears

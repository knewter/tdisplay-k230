## ADDED Requirements

### Requirement: The display dims and then turns off when idle

*Grounding (2026-10-27/28): read on the board over SSH. Brightness 148 dimmed to 37 at 30 s, and power was `false` at 60 s with apps intact. Glass wakes by finger, keyboard base and power key each restored 148, and after the power-key wake the panel re-dimmed at +32 s. A brightness set while dim survived the wake (docs/evidence/idle-dim/README.md).*
After 30 s without input the system SHALL lower the panel backlight to 25% of
its current value, never raising it, and after 60 s without input it SHALL turn
the display off with the same Sway `output * power off` command the power key
uses. Any input SHALL restore the display to on at the exact prior brightness,
unless the brightness was changed meanwhile, in which case the new value stays.
The power key's next short press SHALL still toggle from the actual display
state, and waking with the power key SHALL restore idle dimming.

#### Scenario: Idle dims and then blanks

- **WHEN** a lit panel at a set brightness receives no input for 30 s, then for 60 s in total
- **THEN** at 30 s the backlight is a quarter of the prior value, at 60 s `swaymsg -t get_outputs` reports power false, and the session is still running

#### Scenario: Input restores the exact brightness

- **WHEN** the panel is dim or off from idling and a person provides input or presses the power key
- **THEN** the display is on and the backlight reads the exact value it had before dimming

#### Scenario: Brightness changed while dim

- **WHEN** the backlight is changed away from the dimmed value while the panel is dim
- **THEN** restoring on input leaves the changed value in place

#### Scenario: Power key after an idle blank

- **WHEN** the display was turned off by the idle timer and the person presses the power key briefly
- **THEN** the display turns on at the prior brightness and the next short press turns it off

### Requirement: Timer and video keep the display lit

*Grounding (2026-10-27): injected board runs. A focused Timer held 148 for 103 s and a focused Video for about 98 s. At Home with video playing behind, the panel dimmed at 30 s and turned off at 60 s (docs/evidence/idle-dim/README.md).*
While the Timer or a video player is the focused app card, the system SHALL NOT
dim or blank the display for idleness. Other apps and the Home wallpaper video
SHALL NOT hold the display lit.

#### Scenario: A video plays without input

- **WHEN** a video player is the focused card and no input arrives for over 60 s
- **THEN** the display stays on at full brightness

#### Scenario: Leaving the video card

- **WHEN** the person returns Home and provides no further input
- **THEN** the display dims 30 s and turns off 60 s after the last input

### Requirement: Touch on a dark display wakes it and is consumed

*Grounding (2026-10-27/28): headless Sway showed the waking touch sequence delivering 0 events to a probe, with a positive control (docs/evidence/idle-dim/headless/). On the board, an injected tap on a dark panel over Home's Video icon woke it without launching Video, and a glass finger woke it. The glass tap's no-delivery was not separately observed.*
A touch that lands while the display is off SHALL turn the display on and SHALL
be consumed with every contact that joins it until all of them lift, so the app
beneath receives no down, motion or up from it. A touch that began while the
display was lit SHALL NOT be swallowed. A key from the keyboard base wakes the
display through Sway and MAY reach the focused app.

#### Scenario: Tapping a dark panel over an app

- **WHEN** the display is off and a person taps where an app has a button
- **THEN** the display lights and the button is not activated

#### Scenario: Second finger joins a wake touch

- **WHEN** a second finger lands before the wake touch lifts
- **THEN** neither contact reaches an app, and the next touch after both lift behaves normally

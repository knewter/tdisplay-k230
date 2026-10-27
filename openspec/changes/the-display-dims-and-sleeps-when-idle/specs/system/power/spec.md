## ADDED Requirements

### Requirement: The display dims and then turns off when idle

<!-- UNVERIFIED: host tests cover the dim/restore state logic and the touch gate rules; no board run has timed it, read get_outputs, or driven real input. -->
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

<!-- UNVERIFIED: the Sway inhibit rules and their interaction with card focus are untested on the board. -->
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

<!-- UNVERIFIED: the gate rules are host-tested; the compositor path is not built or run, and delivery of touch to Sway on an off output is not shown. -->
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

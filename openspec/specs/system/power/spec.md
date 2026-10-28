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

*Grounding: Board-read and operator 2026-10-14: taps darkened and woke the panel in the same session (DSI-1 power false/true), and with HDMI connected the same taps sent `output * power off/on` and blanked and woke the monitor (docs/evidence/power-key/display/). Board 2026-10-16 14:04, operator cable and key: a blank on HDMI stayed dark, unplugging lit the panel one second after HPD, and the next press darkened it (docs/evidence/power-key/hdmi-unplug-wake/board-2026-10-16.md).*
A short physical power-key press SHALL turn the display in effect (the panel, or the HDMI monitor while it is the output) off when lit and on when off, while preserving the running applications and selected brightness. Waking the panel SHALL consume that key gesture without activating an application or power action. Unplugging HDMI SHALL turn the panel on, even when the display was off, so the person can see that the unplug worked; the next short press then turns it off.

#### Scenario: Screen goes dark without losing the session

- **WHEN** the display is lit and the person briefly presses the power key
- **THEN** the display turns off, the system remains running and its application state is preserved

#### Scenario: Screen wakes

- **WHEN** the display is off and the person briefly presses the power key
- **THEN** the display returns at the prior brightness, without an app tap or restart

#### Scenario: HDMI is unplugged while the display is off

- **WHEN** the person turns the display off with a short press while HDMI is the output, then unplugs the HDMI cable
- **THEN** the panel lights with direct touch, and the next short press turns it off

### Requirement: Holds do not directly request a destructive action

*Grounding: On the board 2026-10-14, a 1.15 s hold opened one sheet with the system still running (journal INT0 press, map-request, INT0 release; docs/evidence/power-key/sheet/); the 0.7 s threshold and no toggle after a hold are host tests (`tests/test_power_keyd.py`). The PMU's own long-press power-off is not exercised.*
The system SHALL distinguish a deliberate hold from a short press. A hold SHALL open the shell's power sheet once and SHALL NOT also toggle the panel on release. A hold alone SHALL NOT reboot or power off the system.

#### Scenario: Hold the power key

- **WHEN** the person holds the physical key through the configured long-press threshold and then releases it
- **THEN** one power sheet is shown and the running system remains available

#### Scenario: Release before threshold

- **WHEN** the person releases the key before the long-press threshold
- **THEN** only the short-press display action occurs

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

### Requirement: An idle display on the charger shows an exhibition clock

*Grounding: injected board runs on build `3vk5qy3a…` (docs/evidence/clock-display/board/README.md). `bq25890-charger-0` (type USB) reads `online` 1 when docked and 0 on battery. Docked idle opens the clock at 70 s with the display on. On battery, or with the preference set to Sleep, it dims and turns off at 60 s with no card. Unplugging blanks the display in 9–11.5 s. The clock-only phase adds no measurable CPU over a no-card baseline. The idle steps are board-read (docs/evidence/idle-dim/).*
While the charger is connected and the preference "Idle on charger" is Clock (the default), the system SHALL, after 30 s without input, dim the panel as it does on battery and show a full-screen exhibition of the time and date, and SHALL NOT turn the display off at 60 s. With the preference Sleep, or with no charger, the idle steps SHALL behave as on battery. The exhibition SHALL redraw its clock at most once a minute, SHALL change the clock's position at each redraw within a bounded range, and about every five minutes SHALL play one text effect over the text K230 for at most 20 s before the clock returns.

#### Scenario: Docked and idle

- **WHEN** the charger is connected, the preference is Clock and no input arrives for 60 s
- **THEN** the panel is dim, a clock and date are shown, and `swaymsg -t get_outputs` still reports power true

#### Scenario: On battery

- **WHEN** no charger is connected and no input arrives for 60 s
- **THEN** the panel is dim at 30 s and off at 60 s, and no exhibition card exists

#### Scenario: Preference Sleep

- **WHEN** the charger is connected, the preference is Sleep and no input arrives for 60 s
- **THEN** the display dims and turns off as on battery

#### Scenario: The clock moves

- **WHEN** two consecutive minutes pass in the exhibition
- **THEN** the clock's position differs between them and stays entirely on the panel

### Requirement: Input leaves the exhibition without reaching an app

*Grounding: on the board, an injected tap and an injected key over Files closed the card without reaching Files, and Files (the prior card) returned in front. The operator's glass report agrees. Unplugging closed the card and turned the display off (docs/evidence/clock-display/board/README.md).*
<!-- UNVERIFIED: the two-hour cap is not run on the board; the keyboard-base key and the power key rest on operator reports. -->
A touch or key that arrives while the exhibition is shown SHALL be consumed by the exhibition, with the release of a touch, and SHALL close it, restore the prior brightness, and return to the card or Home that was in front. No application beneath it SHALL receive the touch or key. When the charger is disconnected, or after the exhibition has been up two hours, it SHALL close and the display SHALL turn off with the idle step's own command.

#### Scenario: Tap over an app button

- **WHEN** the exhibition is shown over an app and a person taps where that app has a button
- **THEN** the exhibition closes, the brightness is the prior value, and the button is not activated

#### Scenario: Unplugged while exhibiting

- **WHEN** the charger is disconnected while the exhibition is shown
- **THEN** the exhibition closes and the display turns off within 15 s

#### Scenario: Woken from dark

- **WHEN** the display was turned off with the power key while the exhibition was shown and is turned on again
- **THEN** the exhibition is not shown and the prior card or Home is

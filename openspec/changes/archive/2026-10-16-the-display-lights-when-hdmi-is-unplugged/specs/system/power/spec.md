## MODIFIED Requirements

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

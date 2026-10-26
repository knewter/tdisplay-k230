## ADDED Requirements

### Requirement: Clock, Timer and Weather are full-screen touch apps

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

<!-- UNVERIFIED: injected-touch grim captures only; the operator's on-glass check (task 9.2) is pending. -->
Clock SHALL show the time in large digits centred on the output with the date beneath. Timer SHALL show its remaining time in large digits with tappable controls to start or pause, add or remove a minute, and reset. Weather SHALL show current conditions and the coming hours from the same wttr.in data as the Home Weather widget. All three SHALL follow the terminal's theme colours.

#### Scenario: Timer by touch
- **WHEN** a person taps Start in Timer
- **THEN** the countdown starts, and a tap on Pause stops it

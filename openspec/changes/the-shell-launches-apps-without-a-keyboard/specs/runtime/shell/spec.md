## ADDED Requirements

### Requirement: Apps is a recognisable touch launcher

<!-- UNVERIFIED: source and protocol tests can establish the menu contract;
real-glass use requires coordinator capture. -->

The persistent Apps control SHALL open a visually distinct launcher page with
at least 56-pixel-high, touch-sized targets for Terminal, Monitor, New
terminal, and Back. Terminal and Monitor SHALL focus their existing window
when present or start it when absent. New terminal SHALL start a separate
terminal window. The launcher SHALL remain available without a physical
keyboard and SHALL not remove Keyboard, Windows/Home, or System controls.

#### Scenario: A user opens an application

- **WHEN** the user taps Apps and then Terminal or Monitor
- **THEN** the selected running application is focused, or a new one starts
  when no matching window is running

#### Scenario: A user starts another terminal

- **WHEN** the user taps Apps and then New terminal
- **THEN** a separate readable terminal window starts without requiring a
  physical keyboard

#### Scenario: A user leaves the launcher

- **WHEN** the user taps Back on the Apps page
- **THEN** the persistent home controls return with Keyboard, Windows/Home, and
  System still available

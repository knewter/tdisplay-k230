## ADDED Requirements

### Requirement: Apps opens a portrait touch launcher

<!-- UNVERIFIED: source/package tests establish the client contract; real-glass
use requires coordinator capture. -->

The persistent Apps control SHALL open a native Wayland portrait launcher while
Keyboard, Windows/Home, and System remain available through the persistent
bar. The launcher SHALL present a visible title and touch-sized, high-contrast
Terminal, Monitor, New terminal, and Back targets. Terminal and Monitor SHALL
focus their existing window when present or start it when absent. New terminal
SHALL start a separate terminal window. Back SHALL close the launcher without
requiring a physical keyboard.

#### Scenario: A user opens an application

- **WHEN** the user taps Apps and then Terminal or Monitor
- **THEN** the launcher action focuses the selected running application, or
  starts it when no matching window is running

#### Scenario: A user starts another terminal

- **WHEN** the user taps Apps and then New terminal
- **THEN** a separate readable terminal window starts without requiring a
  physical keyboard

#### Scenario: A user leaves the launcher

- **WHEN** the user taps Back on the Apps surface
- **THEN** the launcher closes and the persistent bar retains Apps, Keyboard,
  Windows/Home, and System controls

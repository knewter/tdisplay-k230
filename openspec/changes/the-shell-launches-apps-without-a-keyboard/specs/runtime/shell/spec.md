## Purpose

Provides the handheld Sway shell with keyboard-free application discovery and launch.

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

### Requirement: Apps discovers installed desktop applications

<!-- UNVERIFIED: GLib fixture tests and cross-build pass; physical discovery,
launch and refresh captures are in progress. -->

The system's Apps surface SHALL list visible application desktop entries from
the user's XDG data directories and Nix profile data directories, applying
user-over-system precedence and desktop visibility rules. Reopening Apps SHALL
reflect entries added or removed since the previous open. The surface SHALL
provide readable application names and touch-accessible pages when the list
exceeds the portrait display. Launching an entry SHALL preserve desktop-entry
argument expansion and working-directory semantics. Terminal applications SHALL
open in the configured terminal. A launch error SHALL leave a visible explanation
and a usable Back control.

#### Scenario: An installed application becomes available

- **WHEN** a visible application desktop entry is installed in a session data
  directory and the user reopens Apps
- **THEN** its name appears in the application list and can be selected by touch

#### Scenario: An application is removed or hidden

- **WHEN** an application entry is removed or hidden by a user override and the
  user reopens Apps
- **THEN** that application is absent from the list

#### Scenario: An application needs a terminal

- **WHEN** the user selects an installed application with Terminal=true
- **THEN** its expanded argument list runs in the readable terminal profile
  with the desktop entry's configured working directory

#### Scenario: A launch fails

- **WHEN** the selected application cannot be launched
- **THEN** the launcher reports the failure and lets the user return or choose
  another action without a physical keyboard

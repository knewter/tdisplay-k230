## ADDED Requirements

### Requirement: The panel orientation follows the keyboard base

*Grounding: the existing landscape transform and its touch and render behaviour are grounded by `docs/evidence/panel-landscape/`. The follow-the-base behaviour itself is <!-- UNVERIFIED: no base-absent boot, no live transform change and no attach or detach has been done on this shell. -->*

When the panel orientation is set to follow the keyboard base, the shell SHALL be in portrait (568x1232, Sway `transform normal`) while no keyboard base is present and in the keyboard-case landscape (1232x568, Sway `transform 270`) while one is, and SHALL change between them at run time when the base is attached or detached. A build with a fixed orientation SHALL behave exactly as before. The system owns this requirement; stage 1 is unchanged.

#### Scenario: Boot without the base

- **WHEN** the board boots following the base with no keyboard base attached
- **THEN** the first frame the shell draws is portrait and no rotation happens afterwards

#### Scenario: Boot with the base

- **WHEN** the board boots following the base while clipped into the keyboard base
- **THEN** the first frame the shell draws is landscape, upright for a person at the keyboard

#### Scenario: The base is attached while the shell runs

- **WHEN** the board is clipped into the base while showing portrait
- **THEN** within a few seconds the shell rotates to landscape and every surface fills the new output

#### Scenario: The base is detached while the shell runs

- **WHEN** the board is taken out of the base while showing landscape
- **THEN** after a short delay the shell rotates to portrait and every surface fills the new output

#### Scenario: A fixed profile is unchanged

- **WHEN** a profile sets the panel orientation to a fixed value
- **THEN** it never rotates and attaching the base changes nothing about the display

### Requirement: Rotation does not lose running apps or shell state

*Grounding: <!-- UNVERIFIED: no live rotation has been done; the expectations come from the compositor's configure path and `update_output` in the Rust client. -->*

A rotation SHALL leave every running application running with a window that fills the new output, and SHALL keep the shell's own state (open Home page, card overview, Settings position) across the change. Shell surfaces SHALL be laid out for the new geometry with no overlapping, off-screen or unreachable controls, as in the fixed landscape and portrait profiles. An application MAY re-flow or redraw; the shell SHALL NOT close, restart or move it to another workspace to rotate.

#### Scenario: A terminal is open during a rotation

- **WHEN** Foot is running with output on screen and the shell rotates
- **THEN** Foot is still running, its window fills the new output and its content is intact apart from re-flow

#### Scenario: The drawer is open during a rotation

- **WHEN** the app drawer is open and the shell rotates
- **THEN** the drawer is laid out for the new geometry and its controls respond where they are drawn

### Requirement: Orientation changes are debounced

*Grounding: <!-- UNVERIFIED: the connector's attach and detach bounce has not been observed; the thresholds are a starting point. -->*

The shell SHALL NOT rotate on a single probe result. It SHALL require a run of consecutive agreeing probes before rotating (more for detach than for attach), SHALL hold the current orientation when the probe gives a partial result, SHALL enforce a minimum interval between rotations, and SHALL defer a rotation, for a bounded time, while a touch contact is down.

#### Scenario: A flaky connector

- **WHEN** the base's chips answer and stop answering repeatedly for a few seconds
- **THEN** the shell does not rotate for each change and ends in the orientation that matches the last stable state

#### Scenario: A finger is down

- **WHEN** a rotation becomes due while a finger is on the glass
- **THEN** the rotation happens after the finger lifts, or after the bounded delay if it does not

#### Scenario: A probe failure at boot

- **WHEN** the base probe cannot run at all when the shell starts
- **THEN** the shell starts in portrait and the failure is logged once

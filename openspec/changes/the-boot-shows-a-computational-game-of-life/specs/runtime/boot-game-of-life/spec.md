## Purpose

Provides a deterministic computational boot animation that can hand a bounded
simulation state from stage 1 to Linux and optionally continue in the shell.

## ADDED Requirements

### Requirement: The boot animation has a shared deterministic simulation

Stage 1 and Linux SHALL use the same portable C simulation rules and a versioned
state layout. A fresh boot SHALL render the same default pattern for the same
build and seed. Transient state MAY be carried between owners during one boot,
but the system SHALL NOT store the simulation or seed in a home directory or
use it as a cross-boot backup.

#### Scenario: A fresh image starts the animation

- **WHEN** the image boots with no valid carried state
- **THEN** stage 1 renders the deterministic default pattern and records the
  state-layout version and last-frame metadata

#### Scenario: Linux receives valid state

- **WHEN** Linux finds a valid versioned state from the same boot
- **THEN** it can render the recorded state or continue the simulation using the
  shared rules without depending on a second CPU core

### Requirement: The animation depends on a repaired static handoff

The Game of Life feature SHALL remain disabled or non-accepted until the known
static splash-to-Linux handoff has correct physical geometry and colors. The
feature SHALL document that U-Boot-to-Linux ownership can include a visible
pause while Linux initializes; it SHALL NOT promise uninterrupted motion during
kernel boot.

#### Scenario: The prerequisite is still broken

- **WHEN** the static handoff still wraps or swaps colors on the physical panel
- **THEN** the Game of Life change is not marked complete and no animation
  continuity claim is made

#### Scenario: Linux takes over after a pause

- **WHEN** Linux starts rendering after stage 1 has stopped updating
- **THEN** the panel may show a documented pause, followed by a valid frame or
  valid shell continuation without claiming frame-perfect continuity

### Requirement: Linux touch can add a glider

After Linux owns a working touch-enabled renderer, a touch at a valid board
location SHALL add a glider or equivalent documented pattern and SHALL leave the
simulation usable when the touch device is absent. Physical touch proof is
UNVERIFIED until recorded on the board.

#### Scenario: A user drops a glider

- **WHEN** the user taps the running Linux animation at a valid location
- **THEN** a glider appears at that location and subsequent generations use the
  shared deterministic rules

#### Scenario: Touch is unavailable

- **WHEN** Linux has no usable touch device
- **THEN** the animation still renders its default pattern and remains
  keyboard/console recoverable without claiming touch support

### Requirement: Optional U-Boot touch remains bounded

U-Boot MAY accept touch input through a separately investigated port or
adaptation of the source-built vendor-derived U-Boot Goodix support, only as an
explicit optional path. It SHALL not be required for the shared state contract,
Linux handoff, or acceptance of the default animation. <!-- UNVERIFIED: a
U-Boot Goodix port and physical touch behavior are not proven. -->

#### Scenario: U-Boot touch is not available

- **WHEN** the U-Boot touch port is absent, unsupported, or fails to probe
- **THEN** the default animation and Linux handoff continue without touch input

### Requirement: Wayland continuation is optional and shell-safe

A Wayland continuation MAY animate the simulation after Sway starts, but it
SHALL use the existing shell ownership and SHALL not hide Apps, Keyboard,
Windows/Home, System, or recovery controls. The continuation SHALL be
independently labelled from stage-1 and early-Linux evidence.

#### Scenario: The shell starts

- **WHEN** Sway takes display ownership after the boot animation
- **THEN** the shell remains usable and any continuation either renders valid
  frames or exits without removing persistent controls

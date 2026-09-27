## Purpose

Provides the handheld's default graphical editor for local text and Markdown,
accessible through existing Home pins and the installed-application drawer.

## ADDED Requirements

### Requirement: The graphical editor opens Omawrite

<!-- Verified: docs/evidence/omawrite/README.md; source build, physical-board injected input/native captures, and normal reboot. Not new real-finger acceptance. -->

The system SHALL include source-built Omawrite and make the existing Editor
entry open it with its application icon. Existing Editor Home pins SHALL remain
valid. Plain-text and Markdown graphical file associations SHALL use that entry.

#### Scenario: Existing Editor pin

- **WHEN** the user taps the existing Editor Home pin
- **THEN** Omawrite opens as an ordinary shell window
- **AND** the drawer does not show duplicate visible editor entries

#### Scenario: Opening a Markdown file

- **WHEN** a local Markdown file is opened with the default graphical handler
- **THEN** Omawrite opens that file

### Requirement: Local writing is usable on the portrait screen

<!-- Verified: docs/evidence/omawrite/README.md; source build, physical-board injected input/native captures, and normal reboot. Not new real-finger acceptance. -->

Omawrite SHALL display its writing area and reachable Open/Save controls at the
handheld's portrait size, render without a GPU, accept keyboard input, and save
and reopen local text without loss. It SHALL remain an ordinary window that
can return through Overview and Home. Its palette SHALL follow the active
Omarchy theme where the upstream application supports those palette fields.

#### Scenario: Edit and reopen

- **WHEN** the user types into a scratch document, saves it and reopens it
- **THEN** the saved text is present and the editor remains responsive

#### Scenario: Portrait file chooser

- **WHEN** Open or Save As is requested on the handheld
- **THEN** the user can choose a local file with reachable controls
- **AND** cancelling the chooser returns to the document without discarding edits

#### Scenario: Keyboard and shell navigation

- **WHEN** the on-screen keyboard is shown and hidden, and the app is switched
  through Overview or reopened from Home
- **THEN** editing remains usable and the existing document/window is retained

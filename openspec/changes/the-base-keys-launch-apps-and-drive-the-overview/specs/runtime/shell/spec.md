## MODIFIED Requirements

### Requirement: Shell navigation works from the base's keys

*Grounding: Operator and board-read 2026-10-14: LILYGO opens the drawer, LILYGO+Tab the overview, Fn+LILYGO saves a screenshot (docs/evidence/keyboard-base/keys/README.md). The key roles come from LILYGO `ui_hardware.c`.*

<!-- UNVERIFIED: the drawer's key search and the overview's keys await board proof (the-base-keys-launch-apps-and-drive-the-overview tasks 2.1-2.3). -->

The LILYGO key SHALL open the app drawer with its search taking the base's keys and the on-screen keyboard left down. Typing SHALL filter the drawer, the first match SHALL be marked, Enter SHALL launch it, and Esc SHALL clear the query or, when it is empty, close the drawer. LILYGO with Tab SHALL open the card overview. While the overview is shown, Left and Right SHALL choose a card, Enter SHALL open it, Esc SHALL go back and Backspace SHALL close it; those keys SHALL reach applications unchanged once the overview has closed. Fn with LILYGO SHALL take a screenshot of the panel. Esc SHALL perform the shell's back action when no application has keyboard focus, and SHALL reach the application unchanged otherwise.

#### Scenario: Launching an app without touching the glass

- **WHEN** a person presses LILYGO, types part of an app's name, and presses Enter
- **THEN** the drawer opens with its search filtered, the on-screen keyboard stays down, and the first match launches

#### Scenario: Choosing a card from the keys

- **WHEN** a person presses LILYGO with Tab, then Right, then Enter
- **THEN** the overview opens, the next card is chosen, and that app comes to the front

#### Scenario: Plain keys after the overview

- **WHEN** the overview has closed and a terminal has focus
- **THEN** arrows, Enter, Esc and Backspace reach the terminal

#### Scenario: Esc in an app

- **WHEN** a terminal has focus and a person presses Esc
- **THEN** the terminal receives Esc and the shell does not navigate

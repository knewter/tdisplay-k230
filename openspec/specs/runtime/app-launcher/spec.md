# runtime/app-launcher Specification

## Purpose
Provide a refreshable portrait Apps catalog whose cards explain the action a person will take.

## Requirements

### Requirement: The Apps catalog SHALL explain launch actions
The shell SHALL present useful desktop applications with an action-oriented name and short description, and SHALL hide or demote known implementation endpoints that do not represent an independent person-facing task. It SHALL retain the existing built-in Terminal, Monitor, New terminal, and Help actions.

*Grounding: observed on hardware 2026-10-08 (`docs/evidence/launcher-curation/operator-board-2026-10-08.md`): the coherent shell's drawer omits Foot Client/Foot Server and shows Foot as Terminal and Htop as Monitor (native capture plus operator report); the bar-session `touch-launcher` policy is host-tested (`docs/evidence/launcher-curation/host.md`).*
<!-- UNVERIFIED: the coherent shell's drawer tiles show names only; the "short description" clause is met only by the bar-session launcher. -->

#### Scenario: A catalog includes internal Foot endpoints
- **WHEN** Apps refreshes entries including Foot Client or Foot Server
- **THEN** the visible page does not present those endpoints as unexplained peer applications

#### Scenario: An ordinary discovered application is available
- **WHEN** a non-internal desktop entry is visible
- **THEN** it remains launchable through the existing GLib catalog path

### Requirement: Curation SHALL preserve recovery and touch geometry
The catalog SHALL preserve page bounds, 56px-or-larger actionable targets, and visible Back/Apps recovery when a launch fails.

*Grounding: observed on hardware 2026-10-08 (`docs/evidence/launcher-curation/operator-board-2026-10-08.md`): a deliberately failing entry took the shell's failure path (`app-launch-process-exited`) and the operator confirmed human text and Back recovery.*

#### Scenario: A curated application fails to launch
- **WHEN** launch reports an error
- **THEN** short user-facing text and Back remain visible without exposing a raw path

### Requirement: The drawer sheet covers the output and its chrome is consistent

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

<!-- Grounding: injected-touch grim captures in docs/evidence/shell-design-review/README.md, and the operator's on-glass acceptance of build 1r8zfd5s on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
The drawer sheet SHALL cover the output from its top edge, so no application content shows above the sheet's handle. The Help control SHALL be drawn as the same themed control as the search field, at its height, with its label centred. Tile labels SHALL NOT use a bold weight.

#### Scenario: Drawer over an app
- **WHEN** the drawer is opened over a running application
- **THEN** no pixel of that application is visible above the sheet

### Requirement: Every drawer entry opens a window with its own identity

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

<!-- Grounding: injected-touch grim captures in docs/evidence/shell-design-review/README.md, and the operator's on-glass acceptance of build 1r8zfd5s on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
Every application the drawer lists SHALL open a window when launched, including on this image without Xwayland, and SHALL open at a size it accepts. Each game, Clock and Timer SHALL show an icon no other drawer entry uses. An application launched in a terminal SHALL run under its own app id so its card shows its own name and icon.

#### Scenario: Viewnior opens
- **WHEN** Viewnior is launched from the drawer
- **THEN** its window maps

#### Scenario: btop fits
- **WHEN** btop is launched from the drawer in landscape
- **THEN** it shows its monitor, not a terminal-size error

#### Scenario: Distinct game icons
- **WHEN** the drawer lists 2048, Fifteen, Net, NetHack, Same Game, Sixteen, Clock and Timer
- **THEN** no two of those entries show the same icon

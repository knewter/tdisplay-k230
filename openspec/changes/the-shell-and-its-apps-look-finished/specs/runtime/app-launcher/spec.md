## ADDED Requirements

### Requirement: The drawer sheet covers the output and its chrome is consistent

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md).*

<!-- UNVERIFIED: awaits board captures of the fixed build (tasks group 9). -->
The drawer sheet SHALL cover the output from its top edge, so no application content shows above the sheet's handle. The Help control SHALL be drawn as the same themed control as the search field, at its height, with its label centred. Tile labels SHALL NOT use a bold weight.

#### Scenario: Drawer over an app
- **WHEN** the drawer is opened over a running application
- **THEN** no pixel of that application is visible above the sheet

### Requirement: Every drawer entry opens a window with its own identity

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md).*

<!-- UNVERIFIED: awaits board captures of the fixed build (tasks group 9). -->
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

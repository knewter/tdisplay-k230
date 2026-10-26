## ADDED Requirements

### Requirement: Overview cards show their app and the footer cue's tap goes Home

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md).*

<!-- UNVERIFIED: awaits board captures of the fixed build (tasks group 9). -->
The compositor SHALL resolve card names and icons from the same desktop entries the launcher uses. A plain tap on the overview's bottom band that hits no card SHALL go Home.

#### Scenario: Terminal card
- **WHEN** the overview shows the Terminal's card
- **THEN** the card header shows the Terminal's icon, not a letter badge

#### Scenario: Tapping the cue
- **WHEN** a person taps "Home · tap or swipe up" anywhere along the cue
- **THEN** Home opens

## ADDED Requirements

### Requirement: GTK3 applications follow the active theme

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md).*

<!-- UNVERIFIED: awaits board captures of the fixed build (tasks group 9). -->
The appearance adapter SHALL give GTK3 applications the active theme's colours, a touch-readable font size and controls at least 44 px tall, from files it generates per theme generation and links into the shell user's GTK3 configuration. It SHALL NOT overwrite GTK3 configuration it did not write. GTK3 and GTK4 applications SHALL show a close button only.

#### Scenario: A puzzle after a theme change
- **WHEN** a theme is applied and Same Game is then launched
- **THEN** its window uses the theme's background, text and accent colours

### Requirement: The theme chooser's carousels end softly at their column edges

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md).*

<!-- UNVERIFIED: awaits board captures of the fixed build (tasks group 9). -->
Neighbouring items in the theme and background carousels SHALL fade out at their column edge rather than be cut off at the output edge.

#### Scenario: Background carousel edge
- **WHEN** the background carousel shows items to the right of the centred one
- **THEN** the item nearest the output edge fades out instead of ending in a hard cut

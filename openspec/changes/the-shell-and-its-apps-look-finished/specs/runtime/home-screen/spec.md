## ADDED Requirements

### Requirement: Home's dock and widgets lay out cleanly

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md).*

<!-- UNVERIFIED: awaits board captures of the fixed build (tasks group 9). -->
While no drag is in progress, a dock with free slots SHALL centre its occupied icons without changing the saved layout. Battery – Details SHALL omit current, power and cycle readings the gauge reports as zero while the battery is full and idle, and SHALL state "On charger" when external power is present. The Weather widget's temperature SHALL NOT overlap its condition glyph.

#### Scenario: Four apps in a six-slot dock
- **WHEN** the dock holds four apps in slots 1 to 4 of six
- **THEN** the four icons are centred across the dock

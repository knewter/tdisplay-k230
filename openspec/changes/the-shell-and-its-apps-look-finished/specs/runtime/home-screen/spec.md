## ADDED Requirements

### Requirement: Home's dock and widgets lay out cleanly

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

<!-- Grounding: injected-touch grim captures in docs/evidence/shell-design-review/README.md, and the operator's on-glass acceptance of build 1r8zfd5s on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
A dock whose icons are packed against its start with two or more free slots after them SHALL be centred once, by splitting the free slots between both ends: when Home seeds a new layout, and once for a layout saved before this requirement. After that the person's own arrangement stands, and a dock with a gap inside its run is left alone. Battery – Details SHALL omit current and power readings the gauge reports as zero while the battery is idle, SHALL omit a cycle count of zero, and SHALL state "On charger" when external power is present and the battery is idle. Readings SHALL be joined with " · ". The Weather widget's temperature SHALL NOT overlap its condition glyph.

#### Scenario: Four apps in a six-slot dock
- **WHEN** Home loads a layout whose dock holds four apps in slots 1 to 4 of six
- **THEN** the four apps move to slots 2 to 5, and later loads leave them where the person puts them

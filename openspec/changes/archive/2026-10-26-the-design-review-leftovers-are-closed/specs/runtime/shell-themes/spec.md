## MODIFIED Requirements

### Requirement: The theme chooser's carousels end softly at their column edges

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

<!-- Grounding: injected-touch grim captures in docs/evidence/design-review-leftovers/README.md, and the operator's on-glass acceptance of build qh3i7b3f on 2026-10-26 (docs/evidence/design-review-leftovers/operator-report.md). -->
Neighbouring items in the theme and background carousels SHALL fade out at their column edge rather than be cut off at the output edge. Every carousel item SHALL carry a thin frame in ink that contrasts with the page, so a narrow slice of a pale image still reads as the edge of an item.

#### Scenario: Background carousel edge
- **WHEN** the background carousel shows items to the right of the centred one
- **THEN** the item nearest the output edge fades out instead of ending in a hard cut

#### Scenario: A pale neighbour slice
- **WHEN** the background beside the centred one is mostly the page's own colour
- **THEN** its slice shows a frame along its outline, not loose glyphs

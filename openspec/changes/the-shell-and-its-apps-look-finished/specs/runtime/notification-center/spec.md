## ADDED Requirements

### Requirement: The shade states each fact once

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

<!-- Grounding: injected-touch grim captures in docs/evidence/shell-design-review/README.md, and the operator's on-glass acceptance of build 1r8zfd5s on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
The shade SHALL draw its notification count only when there is at least one notification, SHALL centre its empty state in the list column, and SHALL format battery state as "<percent>% · <state>". The keyboard tile SHALL describe its action rather than repeat its title.

#### Scenario: Empty shade
- **WHEN** the shade opens with no notifications
- **THEN** it shows one empty-state message, centred in the list column, and no "0 notifications" line

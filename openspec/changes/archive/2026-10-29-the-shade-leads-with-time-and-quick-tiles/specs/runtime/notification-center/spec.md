## MODIFIED Requirements

### Requirement: The shade states each fact once

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

*Grounding (2026-10-29, wide layout): board grim captures with injected touch in `docs/evidence/shade-pass/board/`, the operator's glass check of build `37g1magg…` on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`), and an ordinary boot of `2867v7pm…` (`docs/evidence/shade-pass/board/ordinary-boot/README.md`).*

<!-- Grounding: injected-touch grim captures in docs/evidence/shell-design-review/README.md, and the operator's on-glass acceptance of build 1r8zfd5s on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
The shade SHALL draw its notification count only when there is at least one notification, SHALL centre its empty state in the list column, and SHALL format battery state as "<percent>% · <state>". The keyboard tile SHALL describe its action rather than repeat its title. On the wide (landscape) layout, the controls column SHALL lead with the time and date, then one status line, then quick tiles for Wi-Fi and Keyboard, plus Location and Cellular once the modem has answered, then the brightness and volume sliders. The "Notifications" heading SHALL title the list column.

#### Scenario: Empty shade
- **WHEN** the shade opens with no notifications
- **THEN** it shows one empty-state message, centred in the list column, and no "0 notifications" line

#### Scenario: Landscape shade at a glance
- **WHEN** the shade opens on the landscape panel
- **THEN** the time and date head the left column, "Notifications" heads the list, and Wi-Fi and Keyboard are one tap away as tiles

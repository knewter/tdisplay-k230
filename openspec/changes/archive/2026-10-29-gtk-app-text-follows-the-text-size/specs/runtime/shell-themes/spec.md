## MODIFIED Requirements

### Requirement: GTK3 applications follow the active theme

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

*Grounding (2026-10-29): the operator reported Files' text "mostly unreadable" on glass (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`). The board's `~/.config/gtk-4.0/settings.ini` held only `gtk-decoration-layout`, so GTK4 apps had no font size from the adapter.*

*Grounding (2026-10-29): host probes under a headless Wayland Sway with GTK 4.22.4 and 3.24.52, and native grim captures of Files and Net at 100% and 200% on the board with injected touch (`docs/evidence/gtk-text-size/README.md`). Files' labels went from 10 to 14 px ink at 100%. A step change reached new launches without a restart.*

*Grounding (2026-10-29): the operator read Files at 100% on glass on build `2867v7pm…`: "works great." (`docs/evidence/gtk-text-size/README.md`).*

The appearance adapter SHALL give GTK3 applications the active theme's colours, a touch-readable font size and controls at least 44 px tall, from files it generates per theme generation and links into the shell user's GTK3 configuration. It SHALL give GTK3 and GTK4 applications the same base text size, matching the shell's body text at the 100% text step, and SHALL multiply that size by the Settings text-size step (100%, 130%, 160% or 200%). A GTK application started after the step changes SHALL use the new size. It SHALL NOT overwrite GTK3 or GTK4 configuration it did not write. GTK3 and GTK4 applications SHALL show a close button only.

#### Scenario: A puzzle after a theme change
- **WHEN** a theme is applied and Same Game is then launched
- **THEN** its window uses the theme's background, text and accent colours

#### Scenario: Files at the default text step
- **WHEN** Files is opened with the text step at 100%
- **THEN** its sidebar rows, path bar and icon captions are drawn at the shell's body text size, not the toolkit's smaller default

#### Scenario: Files after a larger text step
- **WHEN** a person sets the text size to 200% in Settings and then opens Files
- **THEN** Files' text is twice its 100% size, and the window still fits the panel

#### Scenario: An app left open across a step change
- **WHEN** Net is open while the person changes the text size
- **THEN** Net keeps its current text size until it is closed and opened again

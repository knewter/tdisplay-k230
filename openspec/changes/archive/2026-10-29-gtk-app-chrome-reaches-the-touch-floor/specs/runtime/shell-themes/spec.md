## MODIFIED Requirements

### Requirement: GTK3 applications follow the active theme

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md); fixed-build captures in `docs/evidence/shell-design-review/README.md`.*

*Grounding (2026-10-29): the operator reported Files' text "mostly unreadable" on glass (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`). The board's `~/.config/gtk-4.0/settings.ini` held only `gtk-decoration-layout`, so GTK4 apps had no font size from the adapter.*

*Grounding (2026-10-29): host probes under a headless Wayland Sway with GTK 4.22.4 and 3.24.52, and native grim captures of Files and Net at 100% and 200% on the board with injected touch (`docs/evidence/gtk-text-size/README.md`). Files' labels went from 10 to 14 px ink at 100%. A step change reached new launches without a restart.*

*Grounding (2026-10-29): the operator read Files at 100% on glass on build `2867v7pm…`: "works great." (`docs/evidence/gtk-text-size/README.md`).*

*Grounding (2026-10-27, board, injected): Net's menu bar and toolbar measured 72 px, and Files' path-bar button 88 px and sidebar row 84 px, in grim captures on builds `dhmp8mdi…` and `kllh24ww…` (`docs/evidence/gtk-touch-floor/`). On glass, 2026-10-29, build `ql630glm…`, the operator tapped Net's menus and Files' header: "it all worked" (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

The appearance adapter SHALL give GTK3 applications the active theme's colours, a touch-readable font size and controls whose hit areas are at least 72 px tall for menu bar rows, buttons, entries and tabs and at least 76 px for popup menu items, from files it generates per theme generation and links into the shell user's GTK3 configuration. It SHALL give GTK4 applications a generated `gtk-4.0/gtk.css` of the same intent, with header buttons at least 64 px and buttons, menu items and list rows at least 72 px, and no colours. It SHALL give GTK3 and GTK4 applications the same base text size, matching the shell's body text at the 100% text step, and SHALL multiply that size by the Settings text-size step (100%, 130%, 160% or 200%). A GTK application started after the step changes SHALL use the new size. It SHALL NOT overwrite GTK3 or GTK4 configuration it did not write. GTK3 and GTK4 applications SHALL show a close button only.

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

#### Scenario: A menu bar under a thumb
- **WHEN** Net is launched
- **THEN** its menu bar rows are at least 72 px tall

#### Scenario: Files' header
- **WHEN** Files (Nautilus) is launched
- **THEN** its header buttons are at least 64 px square

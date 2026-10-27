## MODIFIED Requirements

### Requirement: GTK3 applications follow the active theme

*Grounding: the 2026-10-26 design review of native grim captures on the board (`the-shell-and-its-apps-look-finished` design.md): Net's menu bar measured about 44 px and Files' header buttons about 30 px.*

<!-- UNVERIFIED: the enlarged sizes are measured on the host under Xvfb only; no board capture or on-glass check yet. -->
The appearance adapter SHALL give GTK3 applications the active theme's colours, a touch-readable font size and controls whose hit areas are at least 72 px tall for menu bar rows, buttons, entries and tabs and at least 76 px for popup menu items, from files it generates per theme generation and links into the shell user's GTK3 configuration. It SHALL give GTK4 applications a generated `gtk-4.0/gtk.css` of the same intent, with header buttons at least 64 px and buttons, menu items and list rows at least 72 px, and no colours. It SHALL NOT overwrite GTK3 or GTK4 configuration it did not write. GTK3 and GTK4 applications SHALL show a close button only.

#### Scenario: A puzzle after a theme change
- **WHEN** a theme is applied and Same Game is then launched
- **THEN** its window uses the theme's background, text and accent colours

#### Scenario: A menu bar under a thumb
- **WHEN** Net is launched
- **THEN** its menu bar rows are at least 72 px tall

#### Scenario: Files' header
- **WHEN** Files (Nautilus) is launched
- **THEN** its header buttons are at least 64 px square

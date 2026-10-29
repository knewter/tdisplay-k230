## Why

The shell holds every touch target to about 99 px (48 dp at this panel's
density). GTK apps do not. A review of the 2026-10-26 grim captures found
Net's menu bar about 44 px tall and Files' (Nautilus, GTK4) header buttons
about 30 px; the GTK3 stylesheet asks for 44 px buttons and a 24 px menu row
plus padding. A thumb on 331 ppi glass misses a 30 px button, and every GTK
app is a place where the shell's own touch standard stops applying.
This is gap 6 of the shell UX review.

## What Changes

- **GTK3 apps:** menu bar rows are 72 px, popup menu items 76 px, buttons,
  entries and spin buttons 74 px or more, tabs 72 px, check and radio rows
  60 px, switches 44 px, scale handles 48 px and scrollbar handles 36 px
  wide.
- **GTK4/libadwaita apps (Nautilus, Portfolio):** the adapter also writes
  `gtk-4.0/gtk.css`, sizes only and no colour, and links it into the shell
  user's GTK4 configuration. Header buttons are 64 px in an 80 px header;
  buttons, entries, menu items and list rows are 72 px.
- The pinned default generation ships the same GTK4 file, so a fresh home
  has it before any theme is activated.

Non-goals:

- Recolouring GTK4/libadwaita apps (they still get only the light/dark and
  icon switch).
- Changing app layouts beyond control sizes, or scaling apps.
- Reaching the full 99 px: 72-80 px is the sensible ceiling on a 568 px
  tall screen, where a header, a menu bar and one row already take about
  a third of the height.

Needs the physical board: only the proof that it looks right on glass.
The stylesheets parse and size controls under Xvfb on the host.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell-themes`: GTK applications follow the active theme at
  touch size.

## Impact

`tools/theme_gtk.py`, `tools/app_appearance.py`,
`nix/handheld-theme-default` (regenerated `gtk-3.0/gtk.css`, new
`gtk-4.0/gtk.css`, `default.nix`), and their tests.

## Why

The operator cannot read Files. On 2026-10-29 they reported: "text on files
is mostly unreadable" (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).

The cause is that GTK4 apps get no font size from the shell. The GTK4
`settings.ini` the shell writes sets only the close-button layout. Nautilus
therefore uses the toolkit's own default. On this 331 ppi panel, its icon
captions and sidebar rows are about 13 px tall. The shell's own body text is
17-18 px.

GTK apps also ignore the Settings text size. A person who picks 160% or 200%
gets larger shell text, while every GTK window stays at its fixed size.

## What Changes

- **A base size for every GTK app:** GTK3 and GTK4 apps get the same base
  text size, matching the shell's body text at 100%. GTK4 (Nautilus and
  other libadwaita apps) gets it through its settings file. GTK3 gets it
  through its generated stylesheet: its `settings.ini` already asked for
  DejaVu Sans 13, but on Wayland GTK3 takes its font from GSettings instead,
  so that line never took effect.
- **GTK text follows the Settings step:** GTK text scales with the Settings
  text-size step (100%, 130%, 160%, 200%). Changing the step re-prepares the
  active theme generation, as it already does for the shell. Apps started
  afterwards use the new size.
- **Changes reach new launches without a restart:** a theme or text-size
  change now reaches GTK apps launched afterwards. Before, the config links
  followed only after a shell restart or a terminal launch.
- Captures at 100% and 200% show whether Files and Net stay usable on the
  1232x568 panel.

Non-goals:

- **Running apps:** windows already open keep their size until relaunched.
  GTK has no live font reload without a settings daemon or portal, and adding
  one is out of scope.
- **Scaling app layouts or icons:** whole-app stretching was rejected
  2026-09-28.
- **Non-GTK apps:** foot, Omawrite and the Rust shell are unchanged.
- **Colours:** recolouring libadwaita apps is not part of this change.

The change needs the physical board only for the captures and the operator's
reading on glass. The generated files and their font sizes can be tested on
the host, under Xvfb.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/shell-themes`: GTK applications, including GTK4, get a
  touch-readable text size that follows the Settings text-size step.

## Impact

- `tools/theme_gtk.py`: the settings renderers take the text step.
- `tools/app_appearance.py`: reads the saved vision choice when it prepares
  a generation.
- `nix/handheld-theme-default`: the regenerated GTK3 and GTK4
  `settings.ini`.
- Tests: `tests/test_theme_gtk.py`, `tests/test_handheld_app_themes.py` and
  `tests/test_handheld_theme_default.py`.
- Board evidence: `docs/evidence/gtk-text-size/`.

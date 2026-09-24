# Read-only generation preparation checkpoint

Observed 2026-09-23. `tools/theme_activate.py --prepare-only` is a host-side
preparation command. It accepts a direct unchanged theme directory, a built-in
collection member, or a familiar user-theme name; it does **not** activate the
generation or publish a normal image service. No shell receiver currently
acknowledges these generations, so OpenSpec tasks 2.1 and 2.2 remain unchecked.

The coordinator calls only the byte-verified pinned color, legacy-palette and
template helpers. It copies recognized data into a disposable stage, converts
legacy Alacritty colors in scratch, supplies explicit staging paths, and
restricts generated outputs to `shell.toml` and `foot.ini`. It refuses
symlinks, malformed palettes, oversized entries and unresolved templates. It
retains icon theme selection, full raw/resolved palette, section overrides and
background candidates, and reports unknown/unavailable input. A generation ID
binds source content **and path**, trusted helper/template content and adapter
source; a removed or updated checkout cannot overwrite a previous generation.
The theme checkout is never written. Source inspection caps are recorded in
[`source-fixtures.md`](source-fixtures.md).

```text
python3 tests/test_omarchy_theme_activation.py
  PASS: 5 host tests: unchanged direct source, curated outputs, legacy scratch
  conversion, path/symlink/size/palette rejection, old-generation retention,
  source edit/clone path and trusted helper update invalidation.
python3 tools/theme_activate.py fuchsblau --source /tmp/k230-omarchy-theme-fixtures/community --state-root /tmp/k230-theme-prep-final --prepare-only
  PASS: 58 resolved palette keys, 3 background candidates, Yaru-blue selector.
python3 tools/theme_activate.py catppuccin --source /tmp/k230-omarchy-theme-fixtures/builtins --state-root /tmp/k230-theme-prep-final --prepare-only
  PASS: 56 resolved palette keys, 4 background candidates, Yaru-purple selector.
python3 tools/theme_activate.py catppuccin-latte --source /tmp/k230-omarchy-theme-fixtures/builtins --state-root /tmp/k230-theme-prep-final --prepare-only
  PASS: 56 resolved palette keys, 2 background candidates, Yaru-blue selector.
```

These counts are host parse/preparation results, not claims that wallpapers,
icons, gradients, applications or touch surfaces rendered. The next source
boundary is a bounded shell-side prepare/commit/rollback acknowledgement,
followed by a compatible `omarchy-theme-set NAME` wrapper and Nix service.
Until then the command has an explicit `--prepare-only` flag and cannot change
the active shell. Card/drawer, Settings, notifications, keyboard and wallpaper
consumers remain separate implementation tasks and need their named gates.

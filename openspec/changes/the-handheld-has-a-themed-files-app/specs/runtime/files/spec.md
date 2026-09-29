## ADDED Requirements

### Requirement: Two off-the-shelf touch-capable file managers are the handheld's only "Files" entries, installed by default

*Grounding: `docs/research/omarchy-quattro-theme-compatibility.md`'s pinned
Omarchy revision and this change's `install/omarchy-base.packages` read
confirm Nautilus is Omarchy's own shipped file manager. Portfolio
(`portfolio-filemanager`) is read directly from this flake's locked
nixpkgs `package.nix`. Cross-build feasibility is grounded in
`nix build --file nix/files-app-probe.nix ... --dry-run` output recorded
under `docs/evidence/files-app/`, not assumed. The decision to keep both by
default and remove nnn's old entry outright is an operator decision
recorded in this change's `design.md`/`tasks.md`, not a board measurement.*

The system SHALL make Nautilus and Portfolio available as distinct
installed-application drawer entries, each cross-built for the board's
riscv64 target, installed and visible by default
(`k230.shell.filesAppNautilus` defaults to `true`), and SHALL NOT ship
nnn's previous terminal "Files" entry, its package, or any launcher/
card-title wiring for it.

#### Scenario: Both candidates appear in the drawer, nnn's old entry does not

- **WHEN** the installed-application drawer is opened on a default
  `coherentShell` build
- **THEN** "Files (Nautilus)" and "Files (Portfolio)" are both present and
  distinct, and no "Files" entry backed by nnn is present

### Requirement: Neither GTK4 candidate attempts a GL scene renderer

*Grounding: this board has no Mesa/EGL/GL driver
(`nix/shell.nix`'s comment above `zathuraApp`; `AGENTS.md`'s hardware
description). GTK4's default GSK renderer requires GL/Vulkan; `cairo` is
its documented software fallback.*

Each candidate's drawer entry SHALL launch through a wrapper that sets
`GSK_RENDERER=cairo` before executing the application.

#### Scenario: Launcher wrapper forces the software renderer

- **WHEN** either "Files (Nautilus)" or "Files (Portfolio)" is launched
- **THEN** the process that execs the application binary has
  `GSK_RENDERER=cairo` set in its environment

### Requirement: Each candidate's launcher wrapper is self-contained for Wayland and icon resolution

*Grounding: operator report of board behavior (not reproduced by this
worktree; a repository board re-check remains open, `tasks.md` 5.3): both
apps were missing icons on the board without `GDK_BACKEND=wayland` and
without `adwaita-icon-theme`/`hicolor-icon-theme` on `XDG_DATA_DIRS`. The
fix is recorded in `nix/shell.nix`'s `mkFilesAppLauncher`, not as hand-made
files under `/home/shell`, so a fresh home reproduces it without manual
board setup.*

Each candidate's launcher wrapper SHALL set `GDK_BACKEND=wayland` and SHALL
include the launched application's own `share` directory,
`adwaita-icon-theme`'s `share` directory, and `hicolor-icon-theme`'s
`share` directory on `XDG_DATA_DIRS`, entirely from the Nix configuration.

#### Scenario: Launcher wrapper environment is fully self-contained

- **WHEN** either "Files (Nautilus)" or "Files (Portfolio)" is launched
- **THEN** the process that execs the application binary has
  `GDK_BACKEND=wayland` set, and `XDG_DATA_DIRS` includes that
  application's own `share`, `adwaita-icon-theme`'s `share`, and
  `hicolor-icon-theme`'s `share`, without relying on any file outside the
  Nix store under the launching user's home directory

<!-- UNVERIFIED: this requirement encodes an operator-reported board
observation into the Nix configuration; no host, QEMU or board check in
this change independently reproduces "icons were missing without these
variables" or confirms the fix resolves it on the physical panel. -->

### Requirement: Both candidates render the active Omarchy theme's dark/light mode and icon variant

*Grounding: `bin/omarchy-theme-set-gnome` (pinned upstream revision) is the
reference behavior being matched — dark/light `color-scheme` plus an
icon-theme switch, no accent-color recolor. `tests/test_theme_gtk.py` and
`tests/test_handheld_app_themes.py` are the host-side proof; no on-panel
rendering claim is made by this requirement.*

The system SHALL derive `org.gnome.desktop.interface` `color-scheme` and
`icon-theme` from the same resolved theme generation the existing Foot
appearance adapter reads (`tools/app_appearance.py`), publish them as a
GSettings keyfile-backend file inside that generation's `app-appearance`
directory, and re-link each candidate's GSettings keyfile-backend
configuration to that file (or, before any theme has been explicitly
activated, to a pinned default) immediately before every launch.

#### Scenario: A generation's GTK settings match its resolved mode and icon theme

- **WHEN** an acknowledged theme generation resolves to `mode = "dark"` and
  `icon_theme = "Yaru-purple"`
- **THEN** that generation's `gtk-settings.keyfile` contains
  `color-scheme='prefer-dark'` and `icon-theme='Yaru-purple'`

#### Scenario: A freshly launched candidate reflects the currently active theme

- **WHEN** a theme has been activated and acknowledged, and "Files
  (Nautilus)" or "Files (Portfolio)" is then launched
- **THEN** `~/.config/glib-2.0/settings/keyfile` resolves to that theme
  generation's `gtk-settings.keyfile`, not to any earlier generation's file
  or to the pinned default

#### Scenario: A fresh home has correct GTK appearance before any theme is ever activated

- **WHEN** the handheld boots on a fresh home directory, before any theme
  has been explicitly activated, and a GTK4 candidate is launched
- **THEN** `~/.config/glib-2.0/settings/keyfile` resolves to the pinned
  default generation's `gtk-settings.keyfile`, matching the pinned bundled
  theme's `mode`/`icon_theme`

#### Scenario: An already-open window picking up a later theme change is unverified

<!-- UNVERIFIED: the GSettings keyfile backend watches its file for
changes, so live pickup by an already-running process is architecturally
plausible, but no host, QEMU or board observation in this change exercises
"a GTK4 candidate stays open across a real theme switch." Only the
next-launch behavior above is verified. -->

- **WHEN** "Files (Nautilus)" or "Files (Portfolio)" is already open and the
  active theme then changes
- **THEN** whether that open window's appearance updates without a restart
  is not established by this change

### Requirement: The GTK appearance adapter never crashes on missing input and never accepts unsafe values

*Grounding: `tests/test_theme_gtk.py`'s injection-surface and bound tests;
`tests/test_handheld_app_themes.py`'s cache-tamper test.*

The GTK appearance adapter SHALL reject an unrecognized `mode`, an
icon-theme selector containing characters outside
`[A-Za-z0-9._+-]`, an empty selector, or a selector over 160 characters,
and SHALL fall back to `Yaru-blue` when no icon theme is selected at all,
matching `omarchy-theme-set-gnome`'s own fallback.

#### Scenario: An invalid icon theme selector is rejected, not smuggled into the keyfile

- **WHEN** a generation's resolved `icon_theme` contains a character outside
  the allowed set (for example a newline or a `[`)
- **THEN** rendering that generation's GTK settings raises an error instead
  of producing a keyfile

#### Scenario: A generation with no icon theme selector still gets valid GTK settings

- **WHEN** a generation's `icon_theme` is absent
- **THEN** its `gtk-settings.keyfile` sets `icon-theme='Yaru-blue'`

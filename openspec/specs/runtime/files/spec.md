# runtime/files Specification

## Purpose
Provide two installed touchscreen file managers with reproducible software
rendering, icon resolution and theme appearance from the handheld's Nix image.

## Requirements

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

*Grounding: `docs/evidence/files-app/board-2026-09-30/README.md` records
actual desktop-wrapper launches on the installed board, application process
checks for Wayland and application/adwaita/hicolor shares, original native
captures showing resolved icons, and operator acceptance of both apps' icons
and scrolling. The configuration is in `nix/shell.nix`'s `mkFilesAppLauncher`,
not hand-made files under `/home/shell`.*

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

### Requirement: Nautilus is the handheld's one Files entry; Portfolio stays installed

*Grounding: `docs/research/omarchy-quattro-theme-compatibility.md`'s pinned
Omarchy revision and this change's `install/omarchy-base.packages` read
confirm Nautilus is Omarchy's own shipped file manager. Portfolio
(`portfolio-filemanager`) is read directly from this flake's locked
nixpkgs `package.nix`. Cross-build feasibility is grounded in
`nix build --file nix/files-app-probe.nix ... --dry-run` output recorded
under `docs/evidence/files-app/`, not assumed. The decision to keep both by
default and remove nnn's old entry outright is an operator decision
recorded in this change's `design.md`/`tasks.md`, not a board measurement.
Showing only Nautilus in the drawer is the operator's 2026-10-26 decision
(`the-shell-and-its-apps-look-finished`).*

<!-- Grounding: the board drawer capture docs/evidence/shell-design-review/build-9kam3kq9/r2-drawer.png shows one "Files" entry; the operator accepted the build on glass on 2026-10-26 (docs/evidence/shell-design-review/operator-report.md). -->
The system SHALL install Nautilus and Portfolio, each cross-built for the
board's riscv64 target (`k230.shell.filesAppNautilus` defaults to `true`).
The drawer SHALL list Nautilus as the one "Files" entry; Portfolio SHALL
stay installed and launchable but SHALL NOT be listed. The system SHALL NOT
ship nnn's previous terminal "Files" entry, its package, or any launcher/
card-title wiring for it.

#### Scenario: One Files entry, nnn's old entry absent

- **WHEN** the installed-application drawer is opened on a default
  `coherentShell` build
- **THEN** exactly one "Files" entry is present, backed by Nautilus, and no
  "Files" entry backed by nnn or Portfolio is present

### Requirement: Files finishes loading a folder while it is on screen

*Grounding (2026-10-29): on build `2867v7pm…`, Files showed "Loading…" for more than 300 s on a four-entry home folder while visible, and finished once hidden (`docs/evidence/files-app/slow-load/README.md`).*

*Grounding (2026-10-29, patched build `1lpsniwg…`): opened from the drawer with injected touch, Files went idle within 10 s and showed the home folder, also after an ordinary boot. The operator reported on the glass: "opened fast, folder showed" (`docs/evidence/files-app/slow-load/README.md`).*

When Files opens a local folder of a few entries on the panel, it SHALL show
the folder's contents while its window stays visible, without the person
hiding or switching away from the window. Once the folder has loaded, its
main thread SHALL go idle.

#### Scenario: Opening the home folder from the drawer

- **WHEN** a person opens Files from the drawer and it shows the home folder
- **THEN** the folder's entries appear while the window stays on screen, and
  the "Loading…" bar goes away

#### Scenario: Files at rest

- **WHEN** a folder has finished loading and nothing on screen is animating
- **THEN** Files uses no measurable CPU

### Requirement: An animating GTK4 window repaints only what changed

*Grounding (2026-10-29): `WAYLAND_DEBUG` showed every frame of a lone `AdwSpinner` window damaging the whole 1282×618 buffer while sway alternated two buffers. The cause was read in GTK 4.22.4 `gdk/wayland/gdkcairocontext-wayland.c` (`docs/evidence/files-app/slow-load/README.md`).*

*Grounding (2026-10-29, patched GTK4 `44233ral…`): the lone `AdwSpinner` window sent 2 full-buffer damages in 794 commits, the rest about 25×26 px at the spinner (`docs/evidence/files-app/slow-load/README.md`).*

A GTK4 app on the board, drawing with the software renderer, SHALL report
damage to the compositor only for the parts of its window that changed in
that frame, also when the compositor keeps its previous buffer until the
next commit.

#### Scenario: A spinner turns in an otherwise still window

- **WHEN** a GTK4 window shows only a turning spinner
- **THEN** after its first frames, each frame's damage covers the spinner's
  area rather than the whole window

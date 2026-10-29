## Context

All of this work is in userspace: the Python appearance adapter and its Nix
packaging. Nothing changes in the kernel, the device tree or the compositor.

For each theme generation, `tools/app_appearance.py prepare` writes three
things:

- **GTK3:** `settings.ini` and `gtk.css`. The `settings.ini` sets
  `gtk-font-name=DejaVu Sans 13`.
- **GTK4:** `settings.ini` and `gtk.css`. The `settings.ini` holds only
  `gtk-decoration-layout`, and the `gtk.css` sets control sizes only.
- **A GSettings keyfile (`gtk-settings.keyfile`):** it sets `color-scheme`
  and `icon-theme`.

GTK4 and libadwaita apps read that keyfile through the keyfile backend,
because no xdg-desktop-portal runs on this image (`nix/shell.nix`, launcher
comment). No file gives GTK4 a font, so Nautilus draws at the toolkit
default.

The Settings text step is saved by `theme_vision`. `theme_catalog
apply_vision` already re-prepares and re-activates the active theme
generation, so anything `prepare` derives from the step reaches new app
launches without new plumbing.

## Goals / Non-Goals

**Goals:**

- GTK3 and GTK4 apps share one base text size, the shell's body text at
  100%.
- That size is multiplied by the saved text step.
- The prepared generation's identity changes with the step, so the cache
  never serves a stale size.

**Non-Goals:**

- Updating windows that are already open.
- Starting a settings daemon or a portal.
- Per-app font overrides.

## Decisions

### GTK4 takes its size from `gtk-4.0/settings.ini`

The adapter writes `gtk-font-name=DejaVu Sans <13 × step>` into the GTK4
`settings.ini` it already generates, the same face and size as GTK3.

The first plan was the GSettings keyfile (`font-name` and
`text-scaling-factor` in `org.gnome.desktop.interface`), which already feeds
GTK4 apps their colour scheme. Task 1.1 measured it under GTK 4.22.4 and
libadwaita 1.9.3 on Wayland with no portal. GTK4 ignored both keys and
honoured `settings.ini` (`docs/evidence/gtk-text-size/README.md`). Without
either, it falls back to "Sans 10", which is what Files shows on the board
today.

### GTK3 takes its size from the generated `gtk.css`

GTK3 gets `window, tooltip { font-family: "DejaVu Sans"; font-size: <13 ×
step>pt; }` in the `gtk-3.0/gtk.css` the adapter already generates. Every
widget inherits it, and relative rules keep their ratio.

The plan was `gtk-font-name` in `gtk-3.0/settings.ini`. On the board, Net
kept the same text at 26 pt. A host probe then showed that GTK 3.24 on
Wayland takes the font from GSettings whenever the schema is installed,
which nixpkgs' wrapper always arranges. The `settings.ini` line is kept
because it is harmless and applies where no schema is found.

The rejected alternatives were:

- **Writing the font into dconf:** this would add a runtime write to the
  user database, beside generated files.
- **A session-wide `GSETTINGS_BACKEND=keyfile`:** an app writing a setting
  would replace the linked keyfile with a private copy.
- **`GDK_DPI_SCALE`:** a launch-time environment variable that every
  launcher would have to carry.

### `~/.config` links go through the adapter's `active` pointer

The theme transaction's deferred sync only moves
`app-appearance/active`. The GTK config links used to point at a concrete
generation, so they followed only after a CLI `sync`, which runs at shell
start and at each terminal launch.

The links now go through `active`. One pointer move retargets GTK3, GTK4
and Foot together, and the transaction never writes into `~/.config` (so
tests of it cannot touch a developer's home either).

### Rejected: scaling whole apps

Whole-app scaling, by `GDK_SCALE` or compositor stretch, was tried and
undone on 2026-09-28. It enlarges icons and chrome and costs panel space.
This change scales text only.

### The step is part of the generation identity

`prepare` already hashes everything it renders into the generation id. With
the step folded into the rendered files, a step change produces a new
generation, and the cached-generation checks stay correct.

## Risks / Trade-offs

- **[Risk] Nautilus at 200% may crowd the 568 px panel height:** the header,
  the path bar and one row of icons may take most of it. → Capture Files at
  200% in task 3. If it cannot show any content, record that rather than
  shrinking text.
- **[Risk] Some libadwaita styles fix their own sizes:** the `.caption` and
  `.title-*` classes do. → They are relative (em or percent) in libadwaita,
  so they follow the base font. Task 1.1 measures a caption.
- **[Trade-off] Running apps keep the old size:** this is stated in the
  spec scenario.

## Migration Plan

The pinned default generation (`nix/handheld-theme-default`) is regenerated
with the 100% size, so a fresh home gets readable GTK4 text before any theme
is activated.

To roll back, revert the commit and activate any theme. `sync` relinks the
previous files.

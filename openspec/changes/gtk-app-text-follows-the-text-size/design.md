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

### GTK4 takes its size from the GSettings keyfile

GTK4 on Wayland reads its font settings from the portal or, failing that,
from `org.gnome.desktop.interface` in GSettings. The adapter's keyfile
already feeds that schema to every GTK4 app this shell launches. The keyfile
will set:

- `font-name='DejaVu Sans 13'`, the same face and size as GTK3;
- `text-scaling-factor`, set to the step.

The alternative was `gtk-font-name` in `gtk-4.0/settings.ini`. GTK4 may
ignore that file for fonts while a GSettings source exists. Task 1.1
measures both on the host and keeps whichever GTK 4.22 and libadwaita
actually honour. If only `settings.ini` works, the step is folded into its
point size instead.

### GTK3 multiplies the point size

GTK3 takes the scaled size in `gtk-font-name`: 13 pt × the step, rounded to
a whole point (13, 17, 21, 26).

The rejected alternatives were:

- **`GDK_DPI_SCALE`:** an environment variable fixed at each launch, which
  would have to be threaded through every launcher.
- **`gtk-xft-dpi`:** under GTK3 on Wayland it is not reliably honoured.

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

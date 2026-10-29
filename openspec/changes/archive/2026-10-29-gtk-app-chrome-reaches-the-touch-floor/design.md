## Context

`tools/theme_gtk.py` renders the GTK3 stylesheet; `tools/app_appearance.py`
writes it per theme generation and symlinks it into `~/.config/gtk-3.0`.
GTK4 got only `settings.ini`. `tools/generate_default_gtk.py` regenerates the
committed defaults under `nix/handheld-theme-default`, which `default.nix`
installs into the pinned generations.

## Decisions

- **Sizes, measured.** The values were chosen by laying controls out under
  Xvfb with the generated CSS. GTK3 `min-height` is the content box, so
  padding and border add: menu bar item 48 + 24 = 72, button 56 + 16 + 2 =
  74. GTK4 `min-height` is the whole box: button 72.
- **72 px, not 99.** A 568 px tall screen cannot afford 99 px rows in a
  window with a header, a menu bar and content. 72-80 px is about 0.75 of
  the floor and 2.4 times the old Files buttons.
- **GTK4 gets sizes only.** The adapter deliberately does not recolour
  libadwaita (matching Omarchy), so the new file carries no colour and
  needs no palette.
- **Same marker and link rules.** `link_gtk3` already refuses to replace a
  file it did not write; `gtk-4.0/gtk.css` joins its list.
- **Specificity.** libadwaita may use more specific selectors than ours;
  user-priority CSS still outranks theme CSS, but that was checked only
  with plain GTK 4 on the host. <!-- UNVERIFIED: libadwaita on the image -->

## Risks

- A window sized for 30 px buttons may now overflow 568 px. Net's and
  Nautilus's real layouts are not measured on the host.
  <!-- UNVERIFIED: no board capture yet -->

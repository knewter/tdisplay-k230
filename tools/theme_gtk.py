"""Render a GSettings keyfile-backend snippet for GTK4/libadwaita apps.

Mirrors Omarchy's own `bin/omarchy-theme-set-gnome` (see
docs/research/omarchy-quattro-theme-compatibility.md and the pinned checkout
under nix/omarchy-theme-tools/upstream): dark/light `color-scheme` plus a
Yaru icon-theme variant. Omarchy itself does not recolor GTK/libadwaita with
the resolved accent palette either -- it only flips GNOME's stock light/dark
Adwaita and switches the icon theme -- so matching that behavior here is
feature parity with the reference implementation, not a shortfall.

This module only formats already-validated, already-resolved strings; it
never reads a theme checkout or executes anything.
"""

import re

# Same bound `theme_activate.ICON_NAME` enforces on a theme's `icons.theme`
# selector, applied again here so a caller that skips that validation (or a
# stale/foreign report.json) still cannot smuggle a keyfile-breaking value
# into `[org/gnome/desktop/interface] icon-theme=`.
ICON_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,159}\Z")
DEFAULT_ICON_THEME = "Yaru-blue"
MODES = {
    "dark": ("prefer-dark", "Adwaita-dark"),
    "light": ("prefer-light", "Adwaita"),
}


class GtkAppearanceError(ValueError):
    pass


def _quote(value: str) -> str:
    """GLib keyfile string syntax: single-quoted, GVariant text format."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def render(mode: str, icon_theme: str | None) -> str:
    """Return GSettings keyfile-backend text for org.gnome.desktop.interface.

    `mode` is the resolved theme's `dark`/`light` classification (already
    computed by the upstream `omarchy-theme-color` resolver); `icon_theme`
    is the theme's selected icon selector, or None to fall back the same way
    upstream's `omarchy-theme-set-gnome` falls back to "Yaru-blue".
    """
    if mode not in MODES:
        raise GtkAppearanceError(f"unknown appearance mode: {mode!r}")
    if icon_theme is not None and not ICON_NAME.fullmatch(icon_theme):
        raise GtkAppearanceError(f"invalid icon theme selector: {icon_theme!r}")
    color_scheme, gtk_theme = MODES[mode]
    icon = icon_theme or DEFAULT_ICON_THEME
    lines = [
        "[org/gnome/desktop/interface]",
        f"color-scheme={_quote(color_scheme)}",
        f"gtk-theme={_quote(gtk_theme)}",
        f"icon-theme={_quote(icon)}",
    ]
    return "\n".join(lines) + "\n"

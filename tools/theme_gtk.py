"""Render a GSettings keyfile-backend snippet for GTK4/libadwaita apps.

Mirrors Omarchy's own `bin/omarchy-theme-set-gnome` (see
docs/research/omarchy-quattro-theme-compatibility.md and the pinned checkout
under nix/omarchy-theme-tools/upstream): dark/light `color-scheme` plus a
Yaru icon-theme variant. Omarchy itself does not recolor GTK/libadwaita with
the resolved accent palette either -- it only flips GNOME's stock light/dark
Adwaita and switches the icon theme -- so matching that behavior here is
feature parity with the reference implementation, not a shortfall.

GTK3 apps (the puzzles, galculator, viewnior) ignore GSettings keyfiles'
theme, so `render_gtk3_settings`/`render_gtk3_css` additionally produce the
`gtk-3.0/settings.ini` and `gtk.css` GTK3 reads from its config directory:
touch-sized controls and the generation's palette over stock Adwaita.

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
COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
# First line of every file this adapter writes under ~/.config/gtk-3.0; the
# link step refuses to replace a file that does not start with it.
GTK3_CSS_MARKER = "/* Written by k230-app-appearance; edits are replaced. */"
GTK3_INI_MARKER = "# Written by k230-app-appearance; edits are replaced."
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
    lines += ["", "[org/gnome/desktop/wm/preferences]",
              # No minimise/maximise in a card shell; keep only close.
              f"button-layout={_quote(':close')}"]
    return "\n".join(lines) + "\n"


def _rgb(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not COLOR.fullmatch(value):
        raise GtkAppearanceError(f"invalid color: {value!r}")
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def mix(first: str, second: str, amount: float) -> str:
    """sRGB blend: `amount` of `second` over `first`, as #rrggbb."""
    a, b = _rgb(first), _rgb(second)
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b))


def _luminance(value: str) -> float:
    def linear(channel: int) -> float:
        c = channel / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(c) for c in _rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def readable_on(base: str, first: str, second: str) -> str:
    """Whichever of `first`/`second` contrasts more against `base`."""
    def contrast(other: str) -> float:
        hi, lo = sorted((_luminance(base), _luminance(other)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)
    return first if contrast(first) >= contrast(second) else second


def render_gtk3_settings(mode: str, icon_theme: str | None) -> str:
    """GTK3 `settings.ini` for touch: bigger font, close-only decorations."""
    if mode not in MODES:
        raise GtkAppearanceError(f"unknown appearance mode: {mode!r}")
    if icon_theme is not None and not ICON_NAME.fullmatch(icon_theme):
        raise GtkAppearanceError(f"invalid icon theme selector: {icon_theme!r}")
    return "\n".join([
        GTK3_INI_MARKER,
        "[Settings]",
        f"gtk-application-prefer-dark-theme={'true' if mode == 'dark' else 'false'}",
        f"gtk-icon-theme-name={icon_theme or DEFAULT_ICON_THEME}",
        "gtk-font-name=DejaVu Sans 13",
        "gtk-decoration-layout=:close",
        # A finger tap on a slider trough should select, not page-step.
        "gtk-primary-button-warps-slider=false",
        # Overlay scrollbars vanish and are untouchable; keep them drawn.
        "gtk-overlay-scrolling=false",
        ""])


def render_gtk3_css(colors: dict[str, str], mode: str) -> str:
    """GTK3 `gtk.css` over Adwaita from the generation's validated colors.

    `colors` needs `background`, `foreground` and `accent`. Plain widget
    rules only: GtkDrawingArea canvases (the puzzles' boards) are left alone.
    """
    if mode not in MODES:
        raise GtkAppearanceError(f"unknown appearance mode: {mode!r}")
    bg, fg, accent = (colors.get(key) for key in ("background", "foreground", "accent"))
    _rgb(bg), _rgb(fg), _rgb(accent)
    bar = mix(bg, fg, 0.06)
    card = mix(bg, fg, 0.12)
    border = mix(bg, fg, 0.22)
    hover = mix(card, accent, 0.30)
    dim = mix(bg, fg, 0.55)
    on_accent = readable_on(accent, bg, fg)
    css = f"""{GTK3_CSS_MARKER}
@define-color theme_bg_color {bg};
@define-color theme_fg_color {fg};
@define-color theme_base_color {bg};
@define-color theme_text_color {fg};
@define-color theme_selected_bg_color {accent};
@define-color theme_selected_fg_color {on_accent};
@define-color theme_unfocused_bg_color {bg};
@define-color theme_unfocused_fg_color {fg};
@define-color theme_unfocused_base_color {bg};
@define-color theme_unfocused_text_color {fg};
@define-color theme_unfocused_selected_bg_color {accent};
@define-color theme_unfocused_selected_fg_color {on_accent};
@define-color insensitive_bg_color {bar};
@define-color insensitive_fg_color {dim};
@define-color borders {border};
@define-color unfocused_borders {border};
@define-color k230_bar {bar};
@define-color k230_card {card};
@define-color k230_hover {hover};
@define-color k230_accent {accent};
@define-color k230_on_accent {on_accent};

window, dialog, .background {{ background-color: {bg}; color: {fg}; }}
.view, textview text, iconview, treeview.view {{ background-color: {bg}; color: {fg}; }}
headerbar, .titlebar, menubar, toolbar, .toolbar, statusbar, actionbar {{
  background-image: none; background-color: {bar}; color: {fg};
  border-color: {border}; box-shadow: none; }}
menubar > menuitem {{ padding: 10px 14px; font-size: 115%; min-height: 24px; }}
menubar > menuitem:hover, menubar > menuitem:checked {{ background-color: {hover}; }}
menu, .menu, .popup, popover, popover.background {{
  background-color: {bar}; color: {fg}; border-color: {border}; }}
menu menuitem, .menu menuitem {{ padding: 10px 14px; min-height: 24px; }}
menuitem:hover, modelbutton:hover {{ background-color: {hover}; }}

button, button.text-button, button.image-button {{
  min-height: 44px; min-width: 44px; padding: 6px 14px; border-radius: 10px;
  background-image: none; background-color: {card}; color: {fg};
  border: 1px solid {border}; box-shadow: none; text-shadow: none; }}
button:hover {{ background-color: {hover}; }}
button:active, button:checked {{ background-color: {accent}; color: {on_accent}; }}
button:disabled {{ background-color: {bar}; color: {dim}; }}
headerbar button, toolbar button {{ margin: 2px; }}

entry, spinbutton, combobox button {{
  min-height: 44px; padding: 4px 10px; border-radius: 10px;
  background-image: none; background-color: {card}; color: {fg};
  border: 1px solid {border}; box-shadow: none; }}
entry:focus, spinbutton:focus {{ border-color: {accent}; }}
spinbutton button {{ min-height: 36px; border-radius: 0; }}

scale trough, progressbar trough, levelbar trough {{
  background-image: none; background-color: {card}; border: 1px solid {border};
  min-height: 8px; min-width: 8px; }}
scale highlight, progressbar progress, levelbar block.filled {{
  background-image: none; background-color: {accent}; border-color: {accent}; }}
scale slider {{ min-width: 28px; min-height: 28px; background-image: none;
  background-color: {fg}; border: 1px solid {border}; }}
switch {{ min-height: 32px; min-width: 60px; background-color: {card}; border-color: {border}; }}
switch:checked {{ background-color: {accent}; }}
check, radio {{ min-width: 24px; min-height: 24px; }}

selection, *:selected, row:selected, treeview.view:selected, textview text selection {{
  background-color: {accent}; color: {on_accent}; }}
notebook > header > tabs > tab {{ min-height: 40px; padding: 4px 14px; }}
notebook > header > tabs > tab:checked {{ background-color: {card}; }}

scrollbar {{ background-color: {bg}; }}
scrollbar slider {{ min-width: 18px; min-height: 18px; border-radius: 9px;
  background-color: {mix(bg, fg, 0.40)}; border: 2px solid {bg}; }}
scrollbar slider:hover, scrollbar slider:active {{ background-color: {accent}; }}
"""
    return css

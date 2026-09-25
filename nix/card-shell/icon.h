#ifndef CARD_SHELL_ICON_H
#define CARD_SHELL_ICON_H
#include <cairo.h>
#include <stdbool.h>
/* Real .desktop Icon= -> installed icon theme resolution and a bounded
 * decode cache, for the card overview header (docs/design/shell-ux-critique.md
 * #1.2 / the-handheld-presents-a-coherent-shell task 1.4): the compositor
 * previously drew only a letter badge derived from the window title.
 *
 * Deliberately PNG-only, no SVG/gdk-pixbuf/gio: this compositor already
 * avoids linking gio for .desktop parsing (see adapter.c's
 * desktop_identity_name), and every icon this image actually ships (Yaru's
 * apps/places PNGs, foot's own hicolor PNG) already has a usable fixed-size
 * PNG, so adding a rasterizer dependency is not needed to make real icons
 * render here. An icon with only an SVG representation in its theme falls
 * back to the existing letter badge, same as an unresolved name would. */
/* Looks up `icon_name` (a freedesktop Icon= value: a bare themed icon name,
 * or an absolute path) in the active icon theme, decodes it at `size` px
 * square (letterboxed to preserve aspect), and paints it at (x, y) in `cr`
 * via cairo_paint. Returns false (and paints nothing) if no PNG
 * representation resolves. Decoded surfaces are cached by (theme, name,
 * size); repeated calls for the same icon are cheap. */
bool card_icon_paint(cairo_t *cr, const char *icon_name, int size, double x, double y);
/* Sets the active icon theme (K230_ICON_THEME, default "hicolor" -- same
 * default and env var name as nix/rust-shell-client/src/icon.rs, though the
 * two caches are independent processes and do not share memory). Clears the
 * decode cache when the theme actually changes. Rejects a theme name with a
 * path separator or "..", falling back to "hicolor". */
void card_icon_set_theme(const char *theme);
#endif

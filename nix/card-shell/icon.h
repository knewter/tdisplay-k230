#ifndef CARD_SHELL_ICON_H
#define CARD_SHELL_ICON_H
#include <cairo.h>
#include <stdbool.h>
/* Real .desktop Icon= -> installed icon theme resolution and a bounded
 * decode cache, for the card overview header (docs/design/shell-ux-critique.md
 * #1.2 / the-handheld-presents-a-coherent-shell task 1.4): the compositor
 * previously drew only a letter badge derived from the window title.
 *
 * Resolves both PNG (Cairo's own decoder) and SVG (librsvg, already a build
 * input of this compositor's sway-unwrapped derivation) representations,
 * following the same freedesktop icon-theme algorithm (and preferring the
 * same two librsvg calls) as nix/rust-shell-client/src/icon.rs, so a themed
 * icon that only ships as SVG -- confirmed on a real board against a real
 * installed theme, see docs/evidence/card-shell/webos-fan-switcher/ -- still
 * renders instead of falling back to the letter badge. Does not link
 * gio/gdk-pixbuf: only librsvg's own C headers/library, used directly
 * (rsvg_handle_new_from_file/rsvg_handle_render_document into a Cairo
 * context), not through a GdkPixbuf loader path. An icon with no PNG or SVG
 * representation in its theme falls back to the existing letter badge, same
 * as an unresolved name would. */
/* Looks up `icon_name` (a freedesktop Icon= value: a bare themed icon name,
 * or an absolute path) in the active icon theme, decodes it at `size` px
 * square (letterboxed to preserve aspect), and paints it at (x, y) in `cr`
 * via cairo_paint. Returns false (and paints nothing) if no PNG or SVG
 * representation resolves. Decoded surfaces are cached by (theme, name,
 * size); repeated calls for the same icon are cheap. */
bool card_icon_paint(cairo_t *cr, const char *icon_name, int size, double x, double y);
/* Sets the active icon theme: explicitly (the active theme's own
 * icon_theme field, via adapter.c's appearance_apply -- see
 * appearance.h's card_appearance.icon_theme), or implicitly on first use
 * from K230_ICON_THEME (default "hicolor" -- same env var/default as
 * nix/rust-shell-client/src/icon.rs, though the two caches are independent
 * processes and do not share memory). Clears the decode cache when the
 * theme actually changes. Rejects a theme name with a path separator or
 * "..", falling back to "hicolor". */
void card_icon_set_theme(const char *theme);
#endif

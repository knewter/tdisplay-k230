#pragma once

#include <cairo.h>
#include <gio/gio.h>

/* Fixed artwork sizes; text labels remain the identifying route. */
enum k230_icon_use {
  K230_ICON_DRAWER,
  K230_ICON_CARD,
  K230_ICON_NOTIFICATION,
  K230_ICON_PRIVATE_CARD,
  K230_ICON_PRIVATE_NOTIFICATION,
};

/* Returns true only when an image decoded. Other cases draw a neutral glyph.
 * Private uses never inspect icon or retain an identity in the cache. */
gboolean k230_icon_draw(cairo_t *cr, GIcon *icon, enum k230_icon_use use,
                        double x, double y);
void k230_icon_cache_invalidate(void);
guint k230_icon_cache_count(void);
guint k230_icon_decode_count(void);

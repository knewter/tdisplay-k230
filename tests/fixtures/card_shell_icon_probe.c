#include "sway/card_shell_icon.h"
#include <cairo.h>
#include <stdint.h>
#include <stdio.h>

static uint32_t paint(const char *name) {
	cairo_surface_t *surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, 32, 32);
	cairo_t *cr = cairo_create(surface);
	if (!card_icon_paint(cr, name, 32, 0, 0)) {
		cairo_destroy(cr);
		cairo_surface_destroy(surface);
		return 0;
	}
	cairo_surface_flush(surface);
	uint32_t pixel = *(uint32_t *)(cairo_image_surface_get_data(surface) +
		16 * cairo_image_surface_get_stride(surface) + 16 * 4);
	cairo_destroy(cr);
	cairo_surface_destroy(surface);
	return pixel;
}

int main(void) {
	card_icon_set_theme("ThemeA");
	if (paint("marker") != 0xff20b050) return 1;
	if (paint("inherited-marker") != 0xffdd4422) return 2;
	card_icon_set_theme("ThemeB");
	if (paint("marker") != 0xff2850e0) return 3;
	puts("PASS: card icon theme selection resolves local and inherited assets across a theme switch");
	return 0;
}

#include "sway/card_shell_render.h"
#include "sway/card_shell_appearance.h"
#include "sway/card_shell_icon.h"
#include "sway/card_shell_scaled_cache.h"
#include <cairo.h>
#include <drm_fourcc.h>
#include <math.h>
#include <pango/pangocairo.h>
#include <stdlib.h>
#include <wlr/interfaces/wlr_buffer.h>
#include <wlr/util/transform.h>
struct label_buffer {
	struct wlr_buffer base;
	cairo_surface_t *surface;
	size_t gradient_bytes;
};
static size_t gradient_bytes;
#define GRADIENT_BYTES_LIMIT (24u * 1024u * 1024u)
/* Bound all live cached pixels, including buffers still held by a scene node. */
#define SCALED_CACHE_LIMIT (8u * 1024u * 1024u)
struct scaled_buffer {
	struct wlr_buffer base;
	uint8_t *pixels;
	size_t bytes, stride;
};
static size_t scaled_bytes;
static void scaled_destroy(struct wlr_buffer *base) {
	struct scaled_buffer *b = wl_container_of(base, b, base);
	wlr_buffer_finish(base);
	scaled_bytes -= b->bytes;
	free(b->pixels);
	free(b);
}
static bool scaled_access(struct wlr_buffer *base, uint32_t flags, void **data,
		uint32_t *format, size_t *stride) {
	if (flags & WLR_BUFFER_DATA_PTR_ACCESS_WRITE) return false;
	struct scaled_buffer *b = wl_container_of(base, b, base);
	*data = b->pixels;
	*format = DRM_FORMAT_RGB565;
	*stride = b->stride;
	return true;
}
static void scaled_end(struct wlr_buffer *base) {}
static const struct wlr_buffer_impl scaled_impl = {
	.destroy = scaled_destroy, .begin_data_ptr_access = scaled_access, .end_data_ptr_access = scaled_end};
size_t card_scaled_buffer_bytes(void) { return scaled_bytes; }
struct wlr_buffer *card_scaled_buffer_create(struct wlr_buffer *source, int width, int height,
		bool fast) {
	if (!source || width <= 0 || height <= 0 || width > 4096 || height > 4096)
		return NULL;
	size_t stride = ((size_t)width * 2 + 3) & ~(size_t)3;
	size_t bytes = stride * (size_t)height;
	if (bytes > SCALED_CACHE_LIMIT - scaled_bytes)
		return NULL;
	struct scaled_buffer *b = calloc(1, sizeof(*b));
	if (!b) return NULL;
	b->pixels = calloc(1, bytes);
	if (!b->pixels) { free(b); return NULL; }
	void *data;
	uint32_t format;
	size_t source_stride;
	if (!wlr_buffer_begin_data_ptr_access(source, WLR_BUFFER_DATA_PTR_ACCESS_READ,
			&data, &format, &source_stride)) {
		free(b->pixels); free(b); return NULL;
	}
	bool okay = card_scale_rgb565(b->pixels, stride, width, height, data, source_stride,
		source->width, source->height, format, fast);
	wlr_buffer_end_data_ptr_access(source);
	if (!okay) { free(b->pixels); free(b); return NULL; }
	b->stride = stride;
	b->bytes = bytes;
	wlr_buffer_init(&b->base, &scaled_impl, width, height);
	scaled_bytes += bytes;
	return &b->base;
}
static void destroy(struct wlr_buffer *base) {
	struct label_buffer *b = wl_container_of(base, b, base);
	gradient_bytes -= b->gradient_bytes;
	cairo_surface_destroy(b->surface);
	free(b);
}
static bool access(struct wlr_buffer *base, uint32_t flags, void **data, uint32_t *format,
				   size_t *stride) {
	struct label_buffer *b = wl_container_of(base, b, base);
	if (flags & WLR_BUFFER_DATA_PTR_ACCESS_WRITE)
		return false;
	*data = cairo_image_surface_get_data(b->surface);
	*format = DRM_FORMAT_ARGB8888;
	*stride = cairo_image_surface_get_stride(b->surface);
	return true;
}
static void end(struct wlr_buffer *base) {}
static const struct wlr_buffer_impl impl = {
	.destroy = destroy, .begin_data_ptr_access = access, .end_data_ptr_access = end};
struct wlr_scene_buffer *card_label_weight(struct wlr_scene_tree *tree, const char *text,
		int width, int height, int size, uint32_t argb, enum card_label_weight weight) {
	struct label_buffer *b = calloc(1, sizeof(*b));
	if (!b)
		return NULL;
	b->surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height);
	if (cairo_surface_status(b->surface) != CAIRO_STATUS_SUCCESS) {
		cairo_surface_destroy(b->surface);
		free(b);
		return NULL;
	}
	cairo_t *cr = cairo_create(b->surface);
	if (cairo_status(cr) != CAIRO_STATUS_SUCCESS) {
		cairo_destroy(cr);
		cairo_surface_destroy(b->surface);
		free(b);
		return NULL;
	}
	PangoLayout *layout = pango_cairo_create_layout(cr);
	PangoFontDescription *font = pango_font_description_new();
	pango_font_description_set_family(font, CARD_SHELL_FONT_FAMILY);
	pango_font_description_set_absolute_size(font, size * PANGO_SCALE);
	pango_font_description_set_weight(font, weight == CARD_LABEL_BOLD ? PANGO_WEIGHT_BOLD :
		weight == CARD_LABEL_MEDIUM ? PANGO_WEIGHT_MEDIUM : PANGO_WEIGHT_NORMAL);
	pango_layout_set_font_description(layout, font);
	pango_layout_set_text(layout, text, -1);
	pango_layout_set_width(layout, width * PANGO_SCALE);
	pango_layout_set_height(layout, height * PANGO_SCALE);
	pango_layout_set_ellipsize(layout, PANGO_ELLIPSIZE_END);
	cairo_set_source_rgba(cr, ((argb >> 16) & 255) / 255.0,
		((argb >> 8) & 255) / 255.0, (argb & 255) / 255.0,
		((argb >> 24) & 255) / 255.0);
	pango_cairo_show_layout(cr, layout);
	g_object_unref(layout);
	pango_font_description_free(font);
	cairo_destroy(cr);
	cairo_surface_flush(b->surface);
	wlr_buffer_init(&b->base, &impl, width, height);
	struct wlr_scene_buffer *node = wlr_scene_buffer_create(tree, &b->base);
	wlr_buffer_drop(&b->base);
	return node;
}
struct wlr_scene_buffer *card_label_color(struct wlr_scene_tree *tree, const char *text,
		int width, int height, int size, uint32_t argb) {
	return card_label_weight(tree, text, width, height, size, argb, CARD_LABEL_REGULAR);
}
struct wlr_scene_buffer *card_label(struct wlr_scene_tree *tree, const char *text, int width,
		int height, int size) {
	return card_label_color(tree, text, width, height, size, 0xfff7faff);
}
/* Avoid M_PI: not guaranteed under the strict C standard flags this file
 * builds with (see card_brush_scene's own literal below). */
static void paint_badge_glyph(cairo_t *cr, int size, char letter, uint32_t bg_argb,
		uint32_t fg_argb) {
	const double pi = 3.14159265358979323846;
	double r = size * 0.28;
	cairo_new_sub_path(cr);
	cairo_arc(cr, size - r, r, r, -pi / 2, 0);
	cairo_arc(cr, size - r, size - r, r, 0, pi / 2);
	cairo_arc(cr, r, size - r, r, pi / 2, pi);
	cairo_arc(cr, r, r, r, pi, 3 * pi / 2);
	cairo_close_path(cr);
	cairo_set_source_rgba(cr, ((bg_argb >> 16) & 255) / 255.0, ((bg_argb >> 8) & 255) / 255.0,
		(bg_argb & 255) / 255.0, ((bg_argb >> 24) & 255) / 255.0);
	cairo_fill(cr);
	PangoLayout *layout = pango_cairo_create_layout(cr);
	PangoFontDescription *font = pango_font_description_new();
	pango_font_description_set_family(font, CARD_SHELL_FONT_FAMILY);
	pango_font_description_set_absolute_size(font, (size * 0.5) * PANGO_SCALE);
	pango_font_description_set_weight(font, PANGO_WEIGHT_BOLD);
	pango_layout_set_font_description(layout, font);
	char text[2] = {letter, 0};
	pango_layout_set_text(layout, text, -1);
	int tw, th;
	pango_layout_get_pixel_size(layout, &tw, &th);
	cairo_set_source_rgba(cr, ((fg_argb >> 16) & 255) / 255.0, ((fg_argb >> 8) & 255) / 255.0,
		(fg_argb & 255) / 255.0, ((fg_argb >> 24) & 255) / 255.0);
	cairo_move_to(cr, (size - tw) / 2.0, (size - th) / 2.0);
	pango_cairo_show_layout(cr, layout);
	g_object_unref(layout);
	pango_font_description_free(font);
}
struct wlr_scene_buffer *card_icon_badge(struct wlr_scene_tree *tree, char letter, int size,
		uint32_t bg_argb, uint32_t fg_argb) {
	struct label_buffer *b = calloc(1, sizeof(*b));
	if (!b)
		return NULL;
	b->surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, size, size);
	if (cairo_surface_status(b->surface) != CAIRO_STATUS_SUCCESS) {
		cairo_surface_destroy(b->surface);
		free(b);
		return NULL;
	}
	cairo_t *cr = cairo_create(b->surface);
	if (cairo_status(cr) != CAIRO_STATUS_SUCCESS) {
		cairo_destroy(cr);
		cairo_surface_destroy(b->surface);
		free(b);
		return NULL;
	}
	paint_badge_glyph(cr, size, letter, bg_argb, fg_argb);
	cairo_destroy(cr);
	cairo_surface_flush(b->surface);
	wlr_buffer_init(&b->base, &impl, size, size);
	struct wlr_scene_buffer *node = wlr_scene_buffer_create(tree, &b->base);
	wlr_buffer_drop(&b->base);
	return node;
}
/* The card header's icon (docs/design/shell-ux-critique.md #1.2, task 1.4 of
 * the-handheld-presents-a-coherent-shell): resolves the app's real
 * .desktop Icon= through the installed icon theme (card_icon_paint, backed
 * by nix/card-shell/icon.c) and falls back to the same letter badge
 * card_icon_badge already drew when no themed icon resolves, so a card
 * never regresses to a blank header. `icon_name` may be NULL (content
 * classes other than a live app, or a card with no resolved Icon=). */
struct wlr_scene_buffer *card_icon_header(struct wlr_scene_tree *tree, const char *icon_name,
		char fallback_letter, int size, uint32_t bg_argb, uint32_t fg_argb) {
	struct label_buffer *b = calloc(1, sizeof(*b));
	if (!b)
		return NULL;
	b->surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, size, size);
	if (cairo_surface_status(b->surface) != CAIRO_STATUS_SUCCESS) {
		cairo_surface_destroy(b->surface);
		free(b);
		return NULL;
	}
	cairo_t *cr = cairo_create(b->surface);
	if (cairo_status(cr) != CAIRO_STATUS_SUCCESS) {
		cairo_destroy(cr);
		cairo_surface_destroy(b->surface);
		free(b);
		return NULL;
	}
	if (!icon_name || !card_icon_paint(cr, icon_name, size, 0, 0))
		paint_badge_glyph(cr, size, fallback_letter, bg_argb, fg_argb);
	cairo_destroy(cr);
	cairo_surface_flush(b->surface);
	wlr_buffer_init(&b->base, &impl, size, size);
	struct wlr_scene_buffer *node = wlr_scene_buffer_create(tree, &b->base);
	wlr_buffer_drop(&b->base);
	return node;
}
void card_brush_solid_color(const struct card_brush *brush, float out[4]) {
	uint32_t color = brush->stops[0].argb;
	out[0] = ((color >> 16) & 255) / 255.0f;
	out[1] = ((color >> 8) & 255) / 255.0f;
	out[2] = (color & 255) / 255.0f;
	out[3] = ((color >> 24) & 255) / 255.0f * (float)brush->alpha;
}
/* Paints brush's linear gradient (or flat colour, for a one-stop brush) into
 * the current cairo path/clip. Shared by the plain gradient buffer and the
 * rounded card plate below so the two never drift in how a brush renders. */
static bool paint_brush_pattern(cairo_t *cr, const struct card_brush *brush,
		int width, int height) {
	/* CSS-like angle: zero points up and 90 degrees points right. */
	double radians = brush->angle_degrees * 3.14159265358979323846 / 180.0;
	double dx = sin(radians), dy = -cos(radians);
	double span = fabs(dx) * width + fabs(dy) * height;
	double cx = width / 2.0, cy = height / 2.0;
	cairo_pattern_t *pattern = cairo_pattern_create_linear(
		cx - dx * span / 2, cy - dy * span / 2,
		cx + dx * span / 2, cy + dy * span / 2);
	if (cairo_pattern_status(pattern) != CAIRO_STATUS_SUCCESS) {
		cairo_pattern_destroy(pattern);
		return false;
	}
	for (size_t i = 0; i < brush->count; ++i) {
		uint32_t color = brush->stops[i].argb;
		cairo_pattern_add_color_stop_rgba(pattern, brush->stops[i].offset,
			((color >> 16) & 255) / 255.0, ((color >> 8) & 255) / 255.0,
			(color & 255) / 255.0,
			((color >> 24) & 255) / 255.0 * brush->alpha);
	}
	cairo_set_source(cr, pattern);
	cairo_paint(cr);
	bool painted = cairo_status(cr) == CAIRO_STATUS_SUCCESS;
	cairo_pattern_destroy(pattern);
	return painted;
}
/* Outer-corner rounded rectangle path, radius clamped to half the shorter
 * side so a small plate never self-intersects. */
static void rounded_rect_path(cairo_t *cr, double width, double height, double radius) {
	const double pi = 3.14159265358979323846;
	double r = radius;
	if (r * 2 > width) r = width / 2.0;
	if (r * 2 > height) r = height / 2.0;
	if (r < 0) r = 0;
	cairo_new_sub_path(cr);
	cairo_arc(cr, width - r, r, r, -pi / 2, 0);
	cairo_arc(cr, width - r, height - r, r, 0, pi / 2);
	cairo_arc(cr, r, height - r, r, pi / 2, pi);
	cairo_arc(cr, r, r, r, pi, 3 * pi / 2);
	cairo_close_path(cr);
}
struct wlr_scene_buffer *card_brush_scene(struct wlr_scene_tree *tree,
		const struct card_brush *brush, int width, int height) {
	if (!tree || !brush || !brush->count || width <= 0 || height <= 0 ||
		width > 4096 || height > 4096 || (size_t)width * height > 4u * 1024u * 1024u)
		return NULL;
	size_t bytes = (size_t)width * (size_t)height * 4;
	if (bytes > GRADIENT_BYTES_LIMIT - gradient_bytes) return NULL;
	struct label_buffer *b = calloc(1, sizeof(*b));
	if (!b) return NULL;
	b->surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height);
	if (cairo_surface_status(b->surface) != CAIRO_STATUS_SUCCESS) {
		cairo_surface_destroy(b->surface); free(b); return NULL;
	}
	cairo_t *cr = cairo_create(b->surface);
	if (cairo_status(cr) != CAIRO_STATUS_SUCCESS) {
		cairo_destroy(cr); cairo_surface_destroy(b->surface); free(b); return NULL;
	}
	bool painted = paint_brush_pattern(cr, brush, width, height);
	cairo_destroy(cr);
	if (!painted) { cairo_surface_destroy(b->surface); free(b); return NULL; }
	cairo_surface_flush(b->surface);
	b->gradient_bytes = bytes;
	wlr_buffer_init(&b->base, &impl, width, height);
	gradient_bytes += bytes;
	struct wlr_scene_buffer *node = wlr_scene_buffer_create(tree, &b->base);
	wlr_buffer_drop(&b->base);
	return node;
}
struct wlr_scene_buffer *card_plate_scene(struct wlr_scene_tree *tree,
		const struct card_brush *brush, int width, int height, double radius,
		const float stroke_rgba[4], double stroke_width) {
	if (!tree || !brush || !brush->count || width <= 0 || height <= 0 ||
		width > 4096 || height > 4096 || (size_t)width * height > 4u * 1024u * 1024u)
		return NULL;
	size_t bytes = (size_t)width * (size_t)height * 4;
	if (bytes > GRADIENT_BYTES_LIMIT - gradient_bytes) return NULL;
	struct label_buffer *b = calloc(1, sizeof(*b));
	if (!b) return NULL;
	b->surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, width, height);
	if (cairo_surface_status(b->surface) != CAIRO_STATUS_SUCCESS) {
		cairo_surface_destroy(b->surface); free(b); return NULL;
	}
	cairo_t *cr = cairo_create(b->surface);
	if (cairo_status(cr) != CAIRO_STATUS_SUCCESS) {
		cairo_destroy(cr); cairo_surface_destroy(b->surface); free(b); return NULL;
	}
	cairo_save(cr);
	rounded_rect_path(cr, width, height, radius);
	cairo_clip(cr);
	bool painted = paint_brush_pattern(cr, brush, width, height);
	cairo_restore(cr);
	/* Stroked on the same path with double the visible width: cairo centers
	 * a stroke on its path, so only the inner half lands inside the buffer
	 * and the outer half is clipped away by the surface edge, leaving a
	 * clean inset rim rather than a hard-edged ring. */
	if (painted && stroke_width > 0 && stroke_rgba && stroke_rgba[3] > 0) {
		rounded_rect_path(cr, width, height, radius);
		cairo_set_line_width(cr, stroke_width * 2);
		cairo_set_source_rgba(cr, stroke_rgba[0], stroke_rgba[1], stroke_rgba[2], stroke_rgba[3]);
		cairo_stroke(cr);
		painted = cairo_status(cr) == CAIRO_STATUS_SUCCESS;
	}
	cairo_destroy(cr);
	if (!painted) { cairo_surface_destroy(b->surface); free(b); return NULL; }
	cairo_surface_flush(b->surface);
	b->gradient_bytes = bytes;
	wlr_buffer_init(&b->base, &impl, width, height);
	gradient_bytes += bytes;
	struct wlr_scene_buffer *node = wlr_scene_buffer_create(tree, &b->base);
	wlr_buffer_drop(&b->base);
	return node;
}
/* Clip the transformed source in output space, then return to buffer space.
 * The clip is shared by every card descendant, including desynced children. */
void card_clip_buffer(struct wlr_scene_buffer *copy, struct wlr_scene_buffer *source, double scale,
					  int x, int y, int parent_x, int parent_y, struct wlr_box clip) {
	int width = source->dst_width ? source->dst_width : source->buffer->width;
	int height = source->dst_height ? source->dst_height : source->buffer->height;
	int left = lround(x * scale), top = lround(y * scale);
	int right = lround((x + width) * scale), bottom = lround((y + height) * scale);
	int ax = parent_x + left, ay = parent_y + top;
	int bx = parent_x + right, by = parent_y + bottom;
	int cx = ax > clip.x ? ax : clip.x, cy = ay > clip.y ? ay : clip.y;
	int dx = bx < clip.x + clip.width ? bx : clip.x + clip.width;
	int dy = by < clip.y + clip.height ? by : clip.y + clip.height;
	if (dx <= cx || dy <= cy || right <= left || bottom <= top) {
		wlr_scene_node_set_enabled(&copy->node, false);
		return;
	}
	struct wlr_fbox src = source->src_box;
	if (src.width == 0 || src.height == 0)
		src = (struct wlr_fbox){0, 0, source->buffer->width, source->buffer->height};
	int bw = source->buffer->width, bh = source->buffer->height;
	wlr_fbox_transform(&src, &src, source->transform, bw, bh);
	wlr_output_transform_coords(source->transform, &bw, &bh);
	double sx = src.width / (right - left), sy = src.height / (bottom - top);
	src.x += (cx - ax) * sx;
	src.y += (cy - ay) * sy;
	src.width = (dx - cx) * sx;
	src.height = (dy - cy) * sy;
	wlr_fbox_transform(&src, &src, wlr_output_transform_invert(source->transform), bw, bh);
	wlr_scene_buffer_set_source_box(copy, &src);
	wlr_scene_buffer_set_dest_size(copy, dx - cx, dy - cy);
	wlr_scene_buffer_set_transform(copy, source->transform);
	wlr_scene_node_set_position(&copy->node, cx - parent_x, cy - parent_y);
	wlr_scene_node_set_enabled(&copy->node, true);
}

#include "sway/card_shell_render.h"
#include "sway/card_shell_appearance.h"
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
struct wlr_buffer *card_scaled_buffer_create(struct wlr_buffer *source, int width, int height) {
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
		source->width, source->height, format);
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
struct wlr_scene_buffer *card_label_color(struct wlr_scene_tree *tree, const char *text,
		int width, int height, int size, uint32_t argb) {
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
	PangoFontDescription *font = pango_font_description_from_string("sans");
	pango_font_description_set_absolute_size(font, size * PANGO_SCALE);
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
struct wlr_scene_buffer *card_label(struct wlr_scene_tree *tree, const char *text, int width,
		int height, int size) {
	return card_label_color(tree, text, width, height, size, 0xfff7faff);
}
void card_brush_solid_color(const struct card_brush *brush, float out[4]) {
	uint32_t color = brush->stops[0].argb;
	out[0] = ((color >> 16) & 255) / 255.0f;
	out[1] = ((color >> 8) & 255) / 255.0f;
	out[2] = (color & 255) / 255.0f;
	out[3] = ((color >> 24) & 255) / 255.0f * (float)brush->alpha;
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
	/* CSS-like angle: zero points up and 90 degrees points right. */
	double radians = brush->angle_degrees * M_PI / 180.0;
	double dx = sin(radians), dy = -cos(radians);
	double span = fabs(dx) * width + fabs(dy) * height;
	double cx = width / 2.0, cy = height / 2.0;
	cairo_pattern_t *pattern = cairo_pattern_create_linear(
		cx - dx * span / 2, cy - dy * span / 2,
		cx + dx * span / 2, cy + dy * span / 2);
	for (size_t i = 0; i < brush->count; ++i) {
		uint32_t color = brush->stops[i].argb;
		cairo_pattern_add_color_stop_rgba(pattern, brush->stops[i].offset,
			((color >> 16) & 255) / 255.0, ((color >> 8) & 255) / 255.0,
			(color & 255) / 255.0,
			((color >> 24) & 255) / 255.0 * brush->alpha);
	}
	cairo_set_source(cr, pattern);
	cairo_paint(cr);
	cairo_pattern_destroy(pattern);
	cairo_destroy(cr);
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

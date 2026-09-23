#include "sway/card_shell_render.h"
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
};
static void destroy(struct wlr_buffer *base) {
	struct label_buffer *b = wl_container_of(base, b, base);
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
struct wlr_scene_buffer *card_label(struct wlr_scene_tree *tree, const char *text, int width,
									int height, int size) {
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
	cairo_set_source_rgba(cr, .97, .98, 1, 1);
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

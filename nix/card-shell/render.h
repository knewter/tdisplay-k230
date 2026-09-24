#ifndef CARD_SHELL_RENDER_H
#define CARD_SHELL_RENDER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <wlr/types/wlr_scene.h>
struct card_brush;
struct wlr_scene_buffer *card_label(struct wlr_scene_tree *tree, const char *text, int width,
									int height, int size);
struct wlr_scene_buffer *card_label_color(struct wlr_scene_tree *tree, const char *text,
		int width, int height, int size, uint32_t argb);
struct wlr_scene_buffer *card_brush_scene(struct wlr_scene_tree *tree,
		const struct card_brush *brush, int width, int height);
void card_brush_solid_color(const struct card_brush *brush, float out[4]);
struct wlr_buffer *card_scaled_buffer_create(struct wlr_buffer *source, int width, int height);
size_t card_scaled_buffer_bytes(void);
void card_clip_buffer(struct wlr_scene_buffer *copy, struct wlr_scene_buffer *source, double scale,
					  int x, int y, int parent_x, int parent_y, struct wlr_box clip);
#endif

#ifndef CARD_SHELL_RENDER_H
#define CARD_SHELL_RENDER_H
#include <stdbool.h>
#include <wlr/types/wlr_scene.h>
struct wlr_scene_buffer *card_label(struct wlr_scene_tree *tree, const char *text, int width,
									int height, int size);
void card_clip_buffer(struct wlr_scene_buffer *copy, struct wlr_scene_buffer *source, double scale,
					  int x, int y, int parent_x, int parent_y, struct wlr_box clip);
#endif

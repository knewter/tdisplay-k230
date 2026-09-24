/* Opt-in product adapter: Sway alone owns surfaces, input and presentation. */
#include "log.h"
#include "sway/card-shell-policy.h"
#include "sway/card_shell.h"
#include "sway/card_shell_render.h"
#include "sway/card_shell_telemetry.h"
#include "sway/card_shell_test_input.h"
#include "sway/commands.h"
#include "sway/config.h"
#include "sway/desktop/transaction.h"
#include "sway/input/cursor.h"
#include "sway/input/input-manager.h"
#include "sway/input/seat.h"
#include "sway/layers.h"
#include "sway/output.h"
#include "sway/server.h"
#include "sway/tree/root.h"
#include "sway/tree/view.h"
#include "sway/tree/workspace.h"
#include <drm_fourcc.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <wlr/render/pixman.h>
#include <wlr/types/wlr_buffer.h>
#include <wlr/types/wlr_compositor.h>
#include <wlr/types/wlr_output.h>
#include <wlr/types/wlr_scene.h>
#include <wlr/types/wlr_touch.h>
struct card;
struct mirror {
	struct wl_list link;
	struct card *card;
	struct wlr_scene_buffer *source, *copy;
	struct wl_listener source_destroy, copy_destroy, commit, sample;
	bool seen;
	struct wlr_buffer *scaled;
	uint64_t generation, scaled_generation;
	int scaled_width, scaled_height;
};
struct card {
	struct wl_list link, mirrors;
	struct sway_view *view;
	uint64_t id;
	enum cs_content content;
	struct wlr_scene_tree *tree, *pixels;
	struct wlr_scene_rect *background;
	struct wlr_scene_buffer *label;
	char *label_text;
	bool hidden, original_enabled;
	double scale;
	int x, y, pixel_x, pixel_y;
};
static struct {
	struct wl_list cards;
	struct cs_policy policy;
	bool initialized, active, preparing, injecting;
	uint64_t gesture_seq;
	enum cs_message chrome_message;
	bool chrome_active, chrome_valid;
	int chrome_pressed, chrome_x, chrome_y;
	double chrome_w, chrome_h, chrome_top, chrome_bottom, chrome_footer;
	struct sway_output *output;
	struct sway_seat *seat;
	struct wl_listener output_destroy, seat_destroy;
	struct wlr_scene_tree *ui, *deck, *chrome, *button;
	struct wlr_scene_rect *canvas;
	struct wl_event_source *timer;
	char *status_text;
	struct wlr_scene_buffer *status;
	unsigned commits, samples, frames, presents, ticks;
	uint64_t cache_hits, cache_misses, cache_fallbacks;
	int button_contact, pressed_button;
	bool button_down;
	double button_x, button_y;
} shell;
static const float backdrop[4] = {.067, .094, .153, 1};
static const float card_color[4] = {.141, .286, .353, 1};
static const float selected_color[4] = {.184, .420, .310, 1};
static uint64_t now_ms(void) {
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return (uint64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
/* wlroots timestamps are monotonic milliseconds modulo 2^32. Recover the
 * nearest epoch to dispatch without replacing device cadence with render time.
 * Events older than half the 49.7-day wrap period are outside this contract. */
static uint64_t event_time_ms(uint32_t time_msec) {
	uint64_t dispatch = now_ms();
	int64_t delta = (int64_t)time_msec - (int64_t)(uint32_t)dispatch;
	if (delta > INT32_MAX)
		delta -= INT64_C(4294967296);
	else if (delta < INT32_MIN)
		delta += INT64_C(4294967296);
	if (delta < 0 && (uint64_t)(-delta) > dispatch)
		return 0;
	return delta < 0 ? dispatch - (uint64_t)(-delta) : dispatch + (uint64_t)delta;
}
static bool enabled(void) {
	const char *s = getenv("SWAY_K230_CARD_SHELL");
	return s && strcmp(s, "1") == 0;
}
static bool scaled_cache_enabled(void) {
	const char *s = getenv("SWAY_K230_CARD_SCALED_CACHE");
	return s && strcmp(s, "1") == 0;
}
static void scaled_cache_log(void) {
	if (scaled_cache_enabled())
		sway_log(SWAY_INFO,
			"K230_CARD_SHELL scaled-cache hits=%" PRIu64 " misses=%" PRIu64
			" fallbacks=%" PRIu64 " bytes=%zu",
			shell.cache_hits, shell.cache_misses, shell.cache_fallbacks,
			card_scaled_buffer_bytes());
}
static bool live(struct sway_view *v) {
	return v && v->surface && v->surface->mapped && v->container && !v->container->node.destroying;
}
static struct card *find(uint64_t id) {
	struct card *c;
	wl_list_for_each(c, &shell.cards, link) if (c->id == id) return c;
	return NULL;
}
static void restore(struct cs_result result);
static bool sync_scene(void);
static void handle_result(struct cs_result result);
static bool snapshot(void);
static void free_mirror(struct mirror *m) {
	wl_list_remove(&m->source_destroy.link);
	wl_list_remove(&m->commit.link);
	if (m->copy) {
		wl_list_remove(&m->copy_destroy.link);
		wl_list_remove(&m->sample.link);
		wlr_scene_node_destroy(&m->copy->node);
	}
	if (m->scaled)
		wlr_buffer_drop(m->scaled);
	wl_list_remove(&m->link);
	sway_log(SWAY_DEBUG, "K230_CARD_SHELL mirror-release id=%" PRIu64, m->card->id);
	free(m);
}
static void source_destroy(struct wl_listener *l, void *data) {
	struct mirror *m = wl_container_of(l, m, source_destroy);
	free_mirror(m);
}
static void copy_destroy(struct wl_listener *l, void *data) {
	struct mirror *m = wl_container_of(l, m, copy_destroy);
	wl_list_remove(&m->copy_destroy.link);
	wl_list_remove(&m->sample.link);
	m->copy = NULL;
}
static void commit(struct wl_listener *l, void *data) {
	struct mirror *m = wl_container_of(l, m, commit);
	m->generation++;
	shell.commits++;
}
static void sample(struct wl_listener *l, void *data) {
	struct wlr_scene_output_sample_event *e = data;
	if (shell.active && shell.output && e->output == shell.output->scene_output)
		shell.samples++;
}
static void clear_card(struct card *c) {
	struct mirror *m, *tmp;
	wl_list_for_each_safe(m, tmp, &c->mirrors, link) free_mirror(m);
	if (c->tree)
		wlr_scene_node_destroy(&c->tree->node);
	c->tree = NULL;
	c->pixels = NULL;
	c->label = NULL;
	c->background = NULL;
	free(c->label_text);
	c->label_text = NULL;
	if (c->hidden && live(c->view))
		wlr_scene_node_set_enabled(&c->view->scene_tree->node, c->original_enabled);
	c->hidden = false;
}
static bool supported_surface(struct wlr_surface *surface) {
	if (!surface->buffer)
		return false;
	struct wlr_buffer *b = surface->buffer->source;
	struct wlr_shm_attributes a;
	return b && wlr_buffer_get_shm(b, &a) &&
		   (a.format == DRM_FORMAT_XRGB8888 || a.format == DRM_FORMAT_ARGB8888 ||
			a.format == DRM_FORMAT_RGB565);
}
static bool supported_node(struct wlr_scene_node *node) {
	if (!node->enabled)
		return true;
	if (node->type == WLR_SCENE_NODE_TREE) {
		struct wlr_scene_node *n;
		struct wlr_scene_tree *t = wlr_scene_tree_from_node(node);
		wl_list_for_each(n, &t->children, link) if (!supported_node(n)) return false;
		return true;
	}
	if (node->type != WLR_SCENE_NODE_BUFFER)
		return false;
	struct wlr_scene_buffer *b = wlr_scene_buffer_from_node(node);
	if (!b->buffer)
		return true;
	struct wlr_scene_surface *s = wlr_scene_surface_try_from_buffer(b);
	return s && supported_surface(s->surface);
}
static bool marked(struct card *c, const char *mark) {
	list_t *m = c->view->container->marks;
	for (int i = 0; i < m->length; i++)
		if (strcmp(m->items[i], mark) == 0)
			return true;
	return false;
}
static bool private_id(const char *id) {
	const char *list = getenv("SWAY_K230_CARD_PRIVATE_APP_IDS");
	if (!list || !id)
		return false;
	size_t len = strlen(id);
	while (*list) {
		const char *end = strchr(list, ':');
		size_t n = end ? (size_t)(end - list) : strlen(list);
		if (n == len && memcmp(list, id, len) == 0)
			return true;
		if (!end)
			break;
		list = end + 1;
	}
	return false;
}
static enum cs_content classify(struct card *c) {
	if (!live(c->view))
		return CS_UNAVAILABLE;
	if (marked(c, "k230_card_private") || private_id(view_get_app_id(c->view)))
		return CS_PRIVATE;
	if (marked(c, "k230_card_unavailable") || !c->view->container->pending.workspace ||
		!supported_surface(c->view->surface))
		return CS_UNAVAILABLE;
	return supported_node(&c->view->content_tree->node) ? CS_LIVE : CS_UNAVAILABLE;
}
static bool snapshot(void) {
	size_t count = wl_list_length(&shell.cards), i = 0;
	struct cs_card *cards = count ? calloc(count, sizeof(*cards)) : NULL;
	if (count && !cards) {
		handle_result(cs_leave(&shell.policy));
		return false;
	}
	struct card *c;
	bool changed = count != shell.policy.count;
	wl_list_for_each(c, &shell.cards, link) {
		enum cs_content content = classify(c);
		if (c->content != content) {
			clear_card(c);
			c->content = content;
			changed = true;
		}
		cards[i] = (struct cs_card){.id = c->id,
									.content = content,
									.focusable = live(c->view),
									.closeable = live(c->view) && content == CS_LIVE};
		if (i >= shell.policy.count || shell.policy.cards[i].id != c->id)
			changed = true;
		i++;
	}
	if (changed)
		handle_result(cs_set_cards(&shell.policy, cards, count));
	free(cards);
	return true;
}
static bool no_input(struct wlr_scene_buffer *b, double *x, double *y) { return false; }
static struct mirror *mirror(struct card *c, struct wlr_scene_buffer *source) {
	struct mirror *m;
	wl_list_for_each(m, &c->mirrors, link) if (m->source == source) return m;
	struct wlr_scene_surface *s = wlr_scene_surface_try_from_buffer(source);
	if (!s)
		return NULL;
	m = calloc(1, sizeof(*m));
	if (!m)
		return NULL;
	struct wlr_scene_surface *copy = wlr_scene_surface_create(c->pixels, s->surface);
	if (!copy) {
		free(m);
		return NULL;
	}
	m->card = c;
	m->source = source;
	m->copy = copy->buffer;
	m->copy->point_accepts_input = no_input;
	m->source_destroy.notify = source_destroy;
	wl_signal_add(&source->node.events.destroy, &m->source_destroy);
	m->copy_destroy.notify = copy_destroy;
	wl_signal_add(&m->copy->node.events.destroy, &m->copy_destroy);
	m->commit.notify = commit;
	wl_signal_add(&s->surface->events.commit, &m->commit);
	m->sample.notify = sample;
	wl_signal_add(&m->copy->events.output_sample, &m->sample);
	wl_list_insert(c->mirrors.prev, &m->link);
	struct wlr_shm_attributes a;
	if (s->surface->buffer && s->surface->buffer->source &&
		wlr_buffer_get_shm(s->surface->buffer->source, &a))
		sway_log(SWAY_INFO,
				 "K230_CARD_SHELL mirror id=%" PRIu64 " format=%08x width=%d height=%d stride=%d",
				 c->id, a.format, a.width, a.height, a.stride);
	return m;
}
static struct wlr_box clip_box(void) {
	struct cs_config *cfg = &shell.policy.config;
	return (struct wlr_box){shell.output->lx,
							shell.output->ly + cfg->top_reserved + cfg->title_height, cfg->width,
							cfg->height - cfg->top_reserved - cfg->bottom_reserved -
								cfg->title_height - cfg->footer_height};
}
/* Mirror traversal follows source paint order. Place each node immediately
 * after its predecessor instead of cycling every node through the top. The
 * wlroots operations are no-ops when sibling order is already correct. */
static void order_mirror(struct wlr_scene_node **previous, struct wlr_scene_buffer *copy) {
	if (*previous)
		wlr_scene_node_place_above(&copy->node, *previous);
	else
		wlr_scene_node_lower_to_bottom(&copy->node);
	*previous = &copy->node;
}
/* Only a fully visible, opaque, untransformed SHM surface is pixel-equivalent
 * to a pre-scaled RGB565 buffer. Keep the wlroots scene-surface node itself:
 * it still owns live commits, frame callbacks, and presentation sampling. */
static bool scaled_mirror(struct mirror *m, struct wlr_scene_buffer *source, double scale,
		int x, int y, int parent_x, int parent_y, struct wlr_box clip) {
	struct wlr_output *output = shell.output->wlr_output;
	if (!scaled_cache_enabled() || output->render_format != DRM_FORMAT_RGB565 ||
		output->scale != 1 || output->transform != WL_OUTPUT_TRANSFORM_NORMAL ||
		shell.output->color_transform || source->opacity != 1 ||
		source->transform != WL_OUTPUT_TRANSFORM_NORMAL ||
		!((source->src_box.x == 0 && source->src_box.y == 0 &&
			source->src_box.width == 0 && source->src_box.height == 0) ||
			(source->src_box.x == 0 && source->src_box.y == 0 &&
			source->src_box.width == source->buffer->width &&
			source->src_box.height == source->buffer->height)) ||
		(source->dst_width && source->dst_width != source->buffer->width) ||
		(source->dst_height && source->dst_height != source->buffer->height) ||
		source->primaries != WLR_COLOR_NAMED_PRIMARIES_SRGB ||
		source->color_encoding || source->color_range ||
		source->transfer_function != WLR_COLOR_TRANSFER_FUNCTION_GAMMA22)
		return false;
	struct wlr_shm_attributes shm;
	if (!wlr_buffer_get_shm(source->buffer, &shm) ||
		(shm.format != DRM_FORMAT_XRGB8888 && shm.format != DRM_FORMAT_RGB565))
		return false;
	int left = lround(x * scale), top = lround(y * scale);
	int right = lround((x + source->buffer->width) * scale);
	int bottom = lround((y + source->buffer->height) * scale);
	int width = right - left, height = bottom - top;
	int ax = parent_x + left, ay = parent_y + top;
	if (width <= 0 || height <= 0 || ax < clip.x || ay < clip.y ||
		ax + width > clip.x + clip.width || ay + height > clip.y + clip.height)
		return false;
	if (!m->scaled || m->scaled_generation != m->generation ||
		m->scaled_width != width || m->scaled_height != height) {
		if (m->scaled) { wlr_buffer_drop(m->scaled); m->scaled = NULL; }
		m->scaled = card_scaled_buffer_create(source->buffer, width, height);
		shell.cache_misses++;
		if (!m->scaled) return false;
		m->scaled_generation = m->generation;
		m->scaled_width = width;
		m->scaled_height = height;
	} else {
		shell.cache_hits++;
	}
	struct wlr_scene_buffer *copy = m->copy;
	if (copy->buffer != m->scaled)
		wlr_scene_buffer_set_buffer(copy, m->scaled);
	wlr_scene_buffer_set_source_box(copy, NULL);
	wlr_scene_buffer_set_dest_size(copy, width, height);
	wlr_scene_buffer_set_transform(copy, WL_OUTPUT_TRANSFORM_NORMAL);
	wlr_scene_node_set_position(&copy->node, left, top);
	wlr_scene_node_set_enabled(&copy->node, true);
	return true;
}
static bool sync_node(struct card *c, struct wlr_scene_node *node, int x, int y,
		struct wlr_scene_node **previous) {
	if (!node->enabled)
		return true;
	x += node->x;
	y += node->y;
	if (node->type == WLR_SCENE_NODE_TREE) {
		struct wlr_scene_node *n;
		struct wlr_scene_tree *t = wlr_scene_tree_from_node(node);
		wl_list_for_each(n, &t->children, link) if (!sync_node(c, n, x, y, previous)) return false;
		return true;
	}
	if (node->type != WLR_SCENE_NODE_BUFFER)
		return false;
	struct wlr_scene_buffer *source = wlr_scene_buffer_from_node(node);
	if (!source->buffer)
		return true;
	struct mirror *m = mirror(c, source);
	if (!m || !m->copy)
		return false;
	m->seen = true;
	struct wlr_scene_buffer *copy = m->copy;
	wlr_scene_buffer_set_opacity(copy, source->opacity);
	wlr_scene_buffer_set_filter_mode(copy, WLR_SCALE_FILTER_BILINEAR);
	wlr_scene_buffer_set_transfer_function(copy, source->transfer_function);
	wlr_scene_buffer_set_primaries(copy, source->primaries);
	wlr_scene_buffer_set_color_encoding(copy, source->color_encoding);
	wlr_scene_buffer_set_color_range(copy, source->color_range);
	pixman_region32_t empty;
	pixman_region32_init(&empty);
	wlr_scene_buffer_set_opaque_region(copy, &empty);
	pixman_region32_fini(&empty);
	if (!scaled_mirror(m, source, c->scale, x, y, c->x + c->pixel_x, c->y + c->pixel_y,
					clip_box())) {
		if (scaled_cache_enabled()) shell.cache_fallbacks++;
		if (copy->buffer != source->buffer)
			wlr_scene_buffer_set_buffer(copy, source->buffer);
		card_clip_buffer(copy, source, c->scale, x, y, c->x + c->pixel_x, c->y + c->pixel_y,
					 clip_box());
	}
	order_mirror(previous, copy);
	return true;
}
static bool label_update(struct wlr_scene_tree *parent, struct wlr_scene_buffer **node,
						 char **saved, const char *text, int width, int height, int size) {
	if (*node && *saved && strcmp(*saved, text) == 0 && (*node)->buffer->width == width &&
		(*node)->buffer->height == height)
		return true;
	struct wlr_scene_buffer *next = card_label(parent, text, width, height, size);
	char *copy = strdup(text);
	if (!next || !copy) {
		if (next)
			wlr_scene_node_destroy(&next->node);
		free(copy);
		return false;
	}
	if (*node)
		wlr_scene_node_destroy(&(*node)->node);
	free(*saved);
	*saved = copy;
	*node = next;
	return true;
}
static void label_clip(struct wlr_scene_buffer *label, int x, int y, int px, int py,
					   struct wlr_box clip) {
	struct wlr_scene_buffer source = *label;
	source.src_box = (struct wlr_fbox){0};
	source.dst_width = source.buffer->width;
	source.dst_height = source.buffer->height;
	source.transform = WL_OUTPUT_TRANSFORM_NORMAL;
	card_clip_buffer(label, &source, 1, x, y, px, py, clip);
}
static void rect_clip(struct wlr_scene_rect *rect, struct wlr_box box, int px, int py,
					  struct wlr_box clip) {
	int x = box.x > clip.x ? box.x : clip.x, y = box.y > clip.y ? box.y : clip.y;
	int right = box.x + box.width < clip.x + clip.width ? box.x + box.width : clip.x + clip.width;
	int bottom =
		box.y + box.height < clip.y + clip.height ? box.y + box.height : clip.y + clip.height;
	wlr_scene_node_set_enabled(&rect->node, right > x && bottom > y);
	if (right > x && bottom > y) {
		wlr_scene_rect_set_size(rect, right - x, bottom - y);
		wlr_scene_node_set_position(&rect->node, x - px, y - py);
	}
}
static bool sync_card(struct card *c, size_t index) {
	struct cs_rect r = cs_card_rect(&shell.policy, index);
	c->x = shell.output->lx + lround(r.x);
	c->y = shell.output->ly + lround(r.y);
	if (!c->tree) {
		c->tree = wlr_scene_tree_create(shell.deck);
		if (!c->tree)
			return false;
		c->background =
			wlr_scene_rect_create(c->tree, lround(r.width), lround(r.height), card_color);
		c->pixels = wlr_scene_tree_create(c->tree);
		if (!c->background || !c->pixels)
			return false;
	}
	wlr_scene_node_set_position(&c->tree->node, c->x, c->y);
	wlr_scene_rect_set_color(c->background,
							 index == shell.policy.selected ? selected_color : card_color);
	rect_clip(c->background, (struct wlr_box){c->x, c->y, lround(r.width), lround(r.height)}, c->x,
			  c->y, clip_box());
	const char *title = c->content == CS_LIVE ? view_get_title(c->view) : cs_card_text(c->content);
	if (!title || !*title)
		title = "Application";
	char text[512];
	snprintf(text, sizeof(text), "%s%s", index == shell.policy.selected ? "Selected: " : "", title);
	if (!label_update(c->tree, &c->label, &c->label_text, text, lround(r.width) - 24, 56, 32))
		return false;
	label_clip(c->label, 12, lround(r.height) - 60, c->x, c->y, clip_box());
	if (cs_can_mirror(&shell.policy, c->id)) {
		int width = c->view->geometry.width, height = c->view->geometry.height;
		if (width <= 0 || height <= 0)
			return false;
		c->scale = fmin(r.width / width, (r.height - 64) / height);
		c->pixel_x = lround((r.width - width * c->scale) / 2);
		c->pixel_y = lround((r.height - 64 - height * c->scale) / 2);
		wlr_scene_node_set_position(&c->pixels->node, c->pixel_x, c->pixel_y);
		struct mirror *m, *tmp;
		wl_list_for_each(m, &c->mirrors, link) m->seen = false;
		struct wlr_scene_node *previous = NULL;
		struct wlr_scene_node *n;
		wl_list_for_each(n, &c->view->content_tree->children,
						 link) if (!sync_node(c, n, 0, 0, &previous)) return false;
		wl_list_for_each_safe(m, tmp, &c->mirrors, link) if (!m->seen) free_mirror(m);
		if (wl_list_empty(&c->mirrors))
			return false;
	} else {
		/* Denied classes never call the mirror helper or inspect private title text. */
		if (!wl_list_empty(&c->mirrors))
			return false;
	}
	return true;
}
static bool button(struct wlr_scene_tree *parent, int x, int y, int width, const char *text,
				   bool pressed) {
	struct wlr_scene_rect *rect =
		wlr_scene_rect_create(parent, width, 56, pressed ? card_color : selected_color);
	struct wlr_scene_buffer *label = card_label(parent, text, width - 16, 48, 26);
	if (!rect || !label)
		return false;
	wlr_scene_node_set_position(&rect->node, x, y);
	wlr_scene_node_set_position(&label->node, x + 8, y + 9);
	return true;
}
static bool rebuild_chrome(void) {
	struct cs_config *cfg = &shell.policy.config;
	if (shell.chrome)
		wlr_scene_node_destroy(&shell.chrome->node);
	shell.chrome = wlr_scene_tree_create(shell.ui);
	shell.status = NULL;
	free(shell.status_text);
	shell.status_text = NULL;
	if (!shell.chrome)
		return false;
	int x = shell.output->lx, y = shell.output->ly + cfg->top_reserved;
	if (!button(shell.chrome, x + cfg->width - 152, y + 8, 128, shell.active ? "Back" : "Cards",
				shell.button_down && shell.pressed_button == 1))
		return false;
	if (!shell.active)
		return true;
	struct wlr_scene_buffer *title = card_label(shell.chrome, "Cards", 250, 56, 42);
	if (!title)
		return false;
	wlr_scene_node_set_position(&title->node, x + 24, y + 8);
	const char *text = cs_message_text(shell.policy.message);
	if (!text || !*text)
		text = "Drag to browse. Tap to resume.";
	if (!label_update(shell.chrome, &shell.status, &shell.status_text, text, cfg->width - 48, 56,
					  21))
		return false;
	wlr_scene_node_set_position(&shell.status->node, x + 24, y + 72);
	int footer = shell.output->ly + cfg->height - cfg->bottom_reserved - cfg->footer_height;
	return button(shell.chrome, x + 24, footer, 152, "Previous",
				  shell.button_down && shell.pressed_button == 2) &&
		   button(shell.chrome, x + 208, footer, 152, "Next",
				  shell.button_down && shell.pressed_button == 3) &&
		   button(shell.chrome, x + 392, footer, 152, "Close",
				  shell.button_down && shell.pressed_button == 4);
}
/* Only a complete tree is reusable. Layout and feedback changes invalidate it;
 * card motion alone does not recreate labels or buttons. */
static bool chrome(void) {
	struct cs_config *cfg = &shell.policy.config;
	int pressed = shell.button_down ? shell.pressed_button : 0;
	if (shell.chrome_valid && shell.chrome && shell.chrome_message == shell.policy.message &&
		shell.chrome_active == shell.active && shell.chrome_pressed == pressed &&
		shell.chrome_x == shell.output->lx && shell.chrome_y == shell.output->ly &&
		shell.chrome_w == cfg->width && shell.chrome_h == cfg->height &&
		shell.chrome_top == cfg->top_reserved && shell.chrome_bottom == cfg->bottom_reserved &&
		shell.chrome_footer == cfg->footer_height)
		return true;
	shell.chrome_valid = false;
	if (!rebuild_chrome())
		return false;
	shell.chrome_message = shell.policy.message;
	shell.chrome_active = shell.active;
	shell.chrome_pressed = pressed;
	shell.chrome_x = shell.output->lx;
	shell.chrome_y = shell.output->ly;
	shell.chrome_w = cfg->width;
	shell.chrome_h = cfg->height;
	shell.chrome_top = cfg->top_reserved;
	shell.chrome_bottom = cfg->bottom_reserved;
	shell.chrome_footer = cfg->footer_height;
	shell.chrome_valid = true;
	return true;
}
static bool sync_scene(void) {
	if (!shell.active)
		return true;
	struct cs_config *cfg = &shell.policy.config;
	wlr_scene_node_set_position(&shell.canvas->node, shell.output->lx,
								shell.output->ly + cfg->top_reserved);
	wlr_scene_rect_set_size(shell.canvas, cfg->width,
							cfg->height - cfg->top_reserved - cfg->bottom_reserved);
	size_t i = 0;
	struct card *c;
	wl_list_for_each(c, &shell.cards, link) if (!sync_card(c, i++)) return false;
	/* Every complete card and placeholder exists before hiding originals. */
	wl_list_for_each(c, &shell.cards, link) {
		if (!c->hidden) {
			c->original_enabled = c->view->scene_tree->node.enabled;
			c->hidden = true;
		}
		wlr_scene_node_set_enabled(&c->view->scene_tree->node, false);
	}
	wlr_scene_node_set_enabled(&shell.deck->node, true);
	return true;
}
static uint64_t focus_id(struct sway_seat *seat) {
	struct sway_container *c = seat_get_focused_container(seat);
	return c && c->view ? c->node.id : 0;
}
static void restore(struct cs_result result) {
	shell.active = false;
	struct card *c;
	wl_list_for_each(c, &shell.cards, link) clear_card(c);
	scaled_cache_log();
	if (shell.deck)
		wlr_scene_node_set_enabled(&shell.deck->node, false);
	if (shell.seat && !server.session_lock.lock) {
		c = find(result.focus_id);
		if (c && live(c->view))
			seat_set_focus_container(shell.seat, c->view->container);
		else if (shell.output && shell.output->current.active_workspace)
			seat_set_focus_workspace(shell.seat, shell.output->current.active_workspace);
		transaction_commit_dirty();
	}
	if (shell.seat) {
		wl_list_remove(&shell.seat_destroy.link);
		shell.seat = NULL;
	}
	sway_log(SWAY_INFO, "K230_CARD_SHELL restored focus=%" PRIu64 " message=%d", result.focus_id,
			 result.message);
	if (shell.ui)
		chrome();
}
static void handle_result(struct cs_result r) {
	if (r.actions & CS_RESTORE) {
		restore(r);
		return;
	}
	if (r.source_gone_id)
		sway_log(SWAY_INFO, "K230_CARD_SHELL source-gone id=%" PRIu64, r.source_gone_id);
	if (r.actions & CS_SHRINK) {
		shell.active = true;
		card_bench_phase(true, shell.policy.count);
		wlr_scene_node_set_enabled(&shell.deck->node, false);
	}
	if (r.actions & CS_CLOSE) {
		/* Gesture recognition uses device time, but give the client its full
		 * response interval starting when we actually dispatch the close. */
		uint64_t dispatch = now_ms(), timeout = shell.policy.config.close_timeout_ms;
		shell.policy.close_deadline_ms = dispatch > UINT64_MAX - timeout ?
			UINT64_MAX : dispatch + timeout;
		struct card *c = find(r.close_id);
		if (c && live(c->view) && c->content == CS_LIVE) {
			view_close(c->view);
			sway_log(SWAY_INFO, "K230_CARD_SHELL close-request id=%" PRIu64, r.close_id);
		} else {
			handle_result(cs_close_result(&shell.policy, r.close_id, false));
			return;
		}
	}
	if (shell.active && (r.actions & (CS_REDRAW | CS_RECONCILE | CS_SHRINK))) {
		if (!sync_scene() || !chrome()) {
			struct cs_result leave = cs_leave(&shell.policy);
			leave.message = CS_MESSAGE_FAILED;
			restore(leave);
		}
	}
	if (r.actions)
		sway_log(SWAY_DEBUG, "K230_CARD_SHELL state mode=%d actions=%u message=%d cards=%zu",
				 shell.policy.mode, r.actions, r.message, shell.policy.count);
}
static void handle_seat_destroy(struct wl_listener *l, void *data) {
	wl_list_remove(&shell.seat_destroy.link);
	shell.seat = NULL;
	cs_stream_cancel(&shell.policy);
	shell.button_down = false;
	handle_result(cs_leave(&shell.policy));
}
static void handle_output_destroy(struct wl_listener *l, void *data) {
	cs_stream_cancel(&shell.policy);
	shell.button_down = false;
	handle_result(cs_leave(&shell.policy));
	wl_list_remove(&shell.output_destroy.link);
	card_bench_stop();
	shell.output = NULL;
	if (shell.timer) {
		wl_event_source_remove(shell.timer);
		shell.timer = NULL;
	}
	if (shell.ui)
		wlr_scene_node_destroy(&shell.ui->node);
	shell.ui = NULL;
	shell.deck = NULL;
	shell.chrome = NULL;
	shell.canvas = NULL;
	shell.status = NULL;
	free(shell.status_text);
	shell.status_text = NULL;
}
/* Disable runs before Sway evacuates workspaces; the destroy signal is too late
 * to restore a saved workspace safely, and a disabled output stops rendering. */
void card_shell_output_disable(struct sway_output *output) {
	if (shell.output == output)
		handle_output_destroy(NULL, NULL);
}
static int tick_impl(void *data) {
	if (!shell.output)
		return 0;
	card_shell_prepare(shell.output);
	card_bench_resource(shell.active);
	if (shell.output && shell.timer) {
		if (shell.active)
			handle_result(cs_tick(&shell.policy, now_ms()));
		if (shell.active && ++shell.ticks % 60 == 0)
			sway_log(SWAY_INFO,
					 "K230_CARD_SHELL live cards=%zu commits=%u sampled=%u frame-done=%u "
					 "output-presented=%u",
					 shell.policy.count, shell.commits, shell.samples, shell.frames,
					 shell.presents);
		if (shell.active && shell.ticks % 60 == 0)
			scaled_cache_log();
		if (shell.active)
			wlr_output_schedule_frame(shell.output->wlr_output);
		wl_event_source_timer_update(shell.timer, 16);
	}
	return 0;
}
static int tick(void *data) {
	card_bench_work_begin();
	int result = tick_impl(data);
	card_bench_work_end();
	return result;
}
static bool ensure_ui(struct sway_output *output) {
	if (!enabled() || !wlr_renderer_is_pixman(server.renderer) || root->outputs->length != 1)
		return false;
	if (!shell.initialized) {
		wl_list_init(&shell.cards);
		struct cs_config c = cs_default_config(output->width, output->height);
		if (!cs_init(&shell.policy, &c))
			return false;
		shell.initialized = true;
	}
	if (shell.ui)
		return shell.output == output;
	shell.output = output;
	shell.output_destroy.notify = handle_output_destroy;
	wl_signal_add(&output->node.events.destroy, &shell.output_destroy);
	shell.ui = wlr_scene_tree_create(root->layers.shell_overlay);
	if (shell.ui)
		shell.deck = wlr_scene_tree_create(shell.ui);
	if (shell.deck)
		shell.canvas = wlr_scene_rect_create(shell.deck, output->width, output->height, backdrop);
	if (shell.deck)
		wlr_scene_node_set_enabled(&shell.deck->node, false);
	shell.timer = wl_event_loop_add_timer(server.wl_event_loop, tick, NULL);
	if (!shell.ui || !shell.deck || !shell.canvas || !shell.timer || !chrome()) {
		handle_output_destroy(NULL, NULL);
		return false;
	}
	wl_event_source_timer_update(shell.timer, 16);
	return true;
}
/* XDG/IME popups are a separate Sway root layer, not a view descendant.
 * Until that boundary has complete composition support, return to normal
 * before rendering any popup above a scaled or private card. */
static bool visible_popup_node(struct wlr_scene_node *node) {
	if (!node->enabled)
		return false;
	if (node->type == WLR_SCENE_NODE_BUFFER)
		return wlr_scene_buffer_from_node(node)->buffer != NULL;
	if (node->type == WLR_SCENE_NODE_TREE) {
		struct wlr_scene_node *child;
		struct wlr_scene_tree *tree = wlr_scene_tree_from_node(node);
		wl_list_for_each(child, &tree->children, link) if (visible_popup_node(child)) return true;
	}
	return false;
}
static bool popup_mapped(void) { return visible_popup_node(&root->layers.popup->node); }
static bool launcher_mapped(void) {
	struct sway_layer_surface *layer;
	wl_list_for_each(layer, &shell.output->layer_surfaces, link) {
		if (layer->mapped && layer->layer_surface->namespace &&
			strcmp(layer->layer_surface->namespace, "k230-launcher") == 0)
			return true;
	}
	return false;
}
static void prepare_impl(struct sway_output *output) {
	if (shell.preparing || !ensure_ui(output))
		return;
	shell.preparing = true;
	bool blocked =
		server.session_lock.lock || !output->enabled || launcher_mapped() || popup_mapped();
	if (blocked) {
		if (shell.active)
			handle_result(cs_leave(&shell.policy));
		wlr_scene_node_set_enabled(&shell.ui->node, false);
		shell.preparing = false;
		return;
	}
	wlr_scene_node_set_enabled(&shell.ui->node, true);
	struct cs_config cfg = cs_default_config(output->width, output->height);
	cfg.top_reserved = fmax(56, output->usable_area.y);
	cfg.bottom_reserved =
		fmax(0, output->height - output->usable_area.y - output->usable_area.height);
	cfg.card_height = .72 * (cfg.height - cfg.top_reserved - cfg.bottom_reserved -
							 cfg.title_height - cfg.footer_height - 2 * cfg.inset);
	cfg.reduced_motion = getenv("SWAY_K230_CARD_REDUCED_MOTION") &&
						 strcmp(getenv("SWAY_K230_CARD_REDUCED_MOTION"), "1") == 0;
	if (cfg.width != shell.policy.config.width || cfg.height != shell.policy.config.height ||
		cfg.top_reserved != shell.policy.config.top_reserved ||
		cfg.bottom_reserved != shell.policy.config.bottom_reserved ||
		cfg.reduced_motion != shell.policy.config.reduced_motion) {
		handle_result(cs_set_config(&shell.policy, &cfg));
		chrome();
	}
	snapshot();
	if (shell.active && !sync_scene()) {
		struct cs_result r = cs_leave(&shell.policy);
		r.message = CS_MESSAGE_FAILED;
		restore(r);
	}
	shell.preparing = false;
}
void card_shell_prepare(struct sway_output *output) {
	card_bench_work_begin();
	prepare_impl(output);
	card_bench_work_end();
}
void card_shell_observe(struct sway_view *view) {
	if (!enabled() || !live(view) || root->outputs->length != 1 ||
		!ensure_ui(root->outputs->items[0]))
		return;
	if (find(view->container->node.id))
		return;
	struct card *c = calloc(1, sizeof(*c));
	if (!c) {
		handle_result(cs_leave(&shell.policy));
		return;
	}
	c->view = view;
	c->id = view->container->node.id;
	c->content = CS_UNAVAILABLE;
	wl_list_init(&c->mirrors);
	wl_list_insert(shell.cards.prev, &c->link);
	snapshot();
	sway_log(SWAY_INFO, "K230_CARD_SHELL map id=%" PRIu64 " class=%d", c->id, c->content);
}
void card_shell_unmap(struct sway_view *view) {
	if (!shell.initialized || !view->container)
		return;
	struct card *c = find(view->container->node.id);
	if (!c)
		return;
	uint64_t id = c->id;
	clear_card(c);
	wl_list_remove(&c->link);
	free(c);
	snapshot();
	sway_log(SWAY_INFO, "K230_CARD_SHELL unmap id=%" PRIu64, id);
	if (shell.active && shell.seat &&
		(!seat_get_focused_container(shell.seat) ||
		 seat_get_focused_container(shell.seat) == view->container)) {
		struct card *next =
			shell.policy.count ? find(shell.policy.cards[shell.policy.selected].id) : NULL;
		if (next && live(next->view))
			seat_set_focus_container(shell.seat, next->view->container);
		else if (shell.output->current.active_workspace)
			seat_set_focus_workspace(shell.seat, shell.output->current.active_workspace);
		transaction_commit_dirty();
	}
}
void card_shell_frame(struct wlr_scene_buffer *buffer) {
	if (!shell.active)
		return;
	struct card *c;
	wl_list_for_each(c, &shell.cards, link) {
		struct mirror *m;
		wl_list_for_each(m, &c->mirrors, link) if (m->copy == buffer) shell.frames++;
	}
}
void card_shell_present(struct sway_output *output, bool presented) {
	if (shell.active && output == shell.output && presented)
		shell.presents++;
}
static bool select_seat(struct sway_seat *seat) {
	if (shell.seat)
		return shell.seat == seat;
	shell.seat = seat;
	shell.seat_destroy.notify = handle_seat_destroy;
	wl_signal_add(&seat->wlr_seat->events.destroy, &shell.seat_destroy);
	return true;
}
static bool enter(struct sway_seat *seat) {
	if (!enabled() || !shell.output || server.session_lock.lock || launcher_mapped() ||
		popup_mapped() || wlr_seat_touch_num_points(seat->wlr_seat) > 0 ||
		seat->cursor->simulating_pointer_from_touch)
		return false;
	if (!snapshot() || !select_seat(seat))
		return false;
	handle_result(cs_enter(&shell.policy, focus_id(seat)));
	return shell.active;
}
static int hit_button(double x, double y) {
	struct cs_config *c = &shell.policy.config;
	if (x >= c->width - 152 && x < c->width - 24 && y >= c->top_reserved + 8 &&
		y < c->top_reserved + 64)
		return 1;
	if (!shell.active)
		return 0;
	double footer = c->height - c->bottom_reserved - c->footer_height;
	if (y < footer || y >= footer + 56)
		return 0;
	if (x >= 24 && x < 176)
		return 2;
	if (x >= 208 && x < 360)
		return 3;
	if (x >= 392 && x < 544)
		return 4;
	return 0;
}
static bool input_down(struct sway_seat *seat, int32_t id, double x, double y, uint64_t event_ms) {
	if (!enabled() || !shell.output || server.session_lock.lock)
		return false;
	x -= shell.output->lx;
	y -= shell.output->ly;
	if (shell.policy.blocked_until_up) {
		struct cs_result r = cs_down(&shell.policy, id, x, y, event_ms);
		handle_result(r);
		return r.consumed;
	}
	if (shell.button_down) {
		shell.button_down = false;
		handle_result(cs_cancel(&shell.policy));
		shell.policy.blocked_until_up = true;
		shell.policy.blocked_contacts = 2;
		chrome();
		return true;
	}
	/* A second contact belongs to the already-owned card stream regardless of
	 * coordinates. Never forward its down then consume an unrelated up. */
	if (shell.policy.contact || shell.policy.edge.tracking) {
		struct cs_result r = cs_down(&shell.policy, id, x, y, event_ms);
		handle_result(r);
		return r.consumed;
	}
	/* New ownership cannot steal a launcher/keyboard/application sequence. */
	if (!shell.ui || !shell.ui->node.enabled || launcher_mapped() || popup_mapped() ||
		wlr_seat_touch_num_points(seat->wlr_seat) > 0 ||
		seat->cursor->simulating_pointer_from_touch)
		return false;
	if (shell.active && seat != shell.seat) {
		handle_result(cs_leave(&shell.policy));
		return false;
	}
	/* Existing bar and keyboard routes stay authoritative. The top bar restores
	 * normal app routing before its Apps/Windows/Keyboard/System command runs. */
	if (y < shell.policy.config.top_reserved) {
		if (shell.active)
			handle_result(cs_leave(&shell.policy));
		return false;
	}
	if (y >= shell.policy.config.height - shell.policy.config.bottom_reserved)
		return false;
	int button = hit_button(x, y);
	if (button) {
		if (shell.policy.contact || shell.policy.edge.tracking) {
			handle_result(cs_cancel(&shell.policy));
			shell.policy.blocked_until_up = true;
			shell.policy.blocked_contacts = 2;
			return true;
		}
		shell.button_down = true;
		shell.button_contact = id;
		shell.pressed_button = button;
		shell.button_x = x;
		shell.button_y = y;
		chrome();
		return true;
	}
	if (shell.active) {
		struct cs_result r = cs_down(&shell.policy, id, x, y, event_ms);
		handle_result(r);
		return r.consumed;
	}
	if (wlr_seat_touch_num_points(seat->wlr_seat) > 0 ||
		seat->cursor->simulating_pointer_from_touch)
		return false;
	struct cs_result r = cs_edge_down(&shell.policy, id, x, y, event_ms);
	if (r.consumed)
		select_seat(seat);
	handle_result(r);
	return r.consumed;
}
static bool input_motion(struct sway_seat *seat, int32_t id, double x, double y, uint64_t event_ms) {
	if (!shell.initialized || !shell.output)
		return false;
	x -= shell.output->lx;
	y -= shell.output->ly;
	if (shell.button_down) {
		if (id == shell.button_contact &&
			hypot(x - shell.button_x, y - shell.button_y) > shell.policy.config.tap_slop)
			shell.pressed_button = 0;
		chrome();
		return true;
	}
	struct cs_result r = shell.policy.mode == CS_NORMAL
							 ? cs_edge_motion(&shell.policy, id, x, y, event_ms, focus_id(seat))
							 : cs_motion(&shell.policy, id, x, y, event_ms);
	handle_result(r);
	return r.consumed;
}
static bool input_up(struct sway_seat *seat, int32_t id, uint64_t event_ms) {
	if (!shell.initialized)
		return false;
	if (shell.button_down) {
		if (id != shell.button_contact)
			return true;
		int action = shell.pressed_button;
		shell.button_down = false;
		shell.pressed_button = 0;
		if (action == 1) {
			if (shell.active)
				handle_result(cs_leave(&shell.policy));
			else
				enter(seat);
		} else if (action == 2 || action == 3)
			handle_result(cs_step(&shell.policy, action == 2 ? -1 : 1));
		else if (action == 4 && shell.policy.count)
			handle_result(cs_request_close(&shell.policy,
										   shell.policy.cards[shell.policy.selected].id, now_ms()));
		chrome();
		return true;
	}
	struct cs_result r = shell.policy.mode == CS_NORMAL && !shell.policy.blocked_until_up
							 ? cs_edge_up(&shell.policy, id)
							 : cs_up(&shell.policy, id, event_ms);
	handle_result(r);
	if (!shell.active && !shell.policy.edge.tracking && shell.seat) {
		wl_list_remove(&shell.seat_destroy.link);
		shell.seat = NULL;
	}
	return r.consumed;
}
bool card_shell_cancel(struct sway_seat *seat) {
	if (!shell.initialized)
		return false;
	bool consumed = shell.button_down || shell.policy.contact || shell.policy.edge.tracking ||
					shell.policy.blocked_until_up;
	shell.button_down = false;
	shell.pressed_button = 0;
	handle_result(cs_stream_cancel(&shell.policy));
	if (shell.ui)
		chrome();
	return consumed;
}
bool card_shell_down(struct sway_seat *seat, struct wlr_touch *touch, int32_t id, double x, double y, uint32_t time_msec) {
	bool consumed = input_down(seat, id, x, y, event_time_ms(time_msec));
	if (consumed)
		shell.gesture_seq++;
	return consumed;
}
/* Device identity is per event, independent of the benchmark's declared source.
 * The board harness additionally verifies the exact named device is uinput via
 * its virtual sysfs path. This label alone never attests a real finger. */
static bool injected_touch(const struct wlr_touch *touch) {
	const char *name = touch ? touch->base.name : NULL;
	return shell.injecting || (name &&
		(!strcmp(name, "K230 injected touchscreen") ||
		 !strcmp(name, "Card shell headless fixture")));
}
bool card_shell_motion(struct sway_seat *seat, struct wlr_touch *touch, int32_t id, double x, double y, uint32_t time_msec) {
	bool active = shell.active;
	card_bench_input_begin(shell.gesture_seq, "motion", injected_touch(touch));
	bool consumed = input_motion(seat, id, x, y, event_time_ms(time_msec));
	card_bench_input_end(consumed && (active || shell.active), false);
	return consumed;
}
bool card_shell_up(struct sway_seat *seat, struct wlr_touch *touch, int32_t id, uint32_t time_msec) {
	bool active = shell.active;
	card_bench_input_begin(shell.gesture_seq, "release", injected_touch(touch));
	bool consumed = input_up(seat, id, event_time_ms(time_msec));
	card_bench_input_end(consumed && (active || shell.active), shell.policy.mode != CS_DRAGGING);
	return consumed;
}
struct cmd_results *cmd_card_shell(int argc, char **argv) {
	if (!enabled() || config->reading)
		return cmd_results_new(CMD_FAILURE, "card shell is disabled");
	if (root->outputs->length != 1 || !ensure_ui(root->outputs->items[0]))
		return cmd_results_new(CMD_FAILURE, "card shell requires one Pixman output");
	struct sway_seat *seat = config->handler_context.seat;
	bool accepted = false;
	if (argc >= 2 && strcmp(argv[0], "test-touch") == 0) {
		accepted = card_shell_test_input(shell.output, argc - 1, argv + 1);
	} else if (argc == 2 && strcmp(argv[0], "benchmark") == 0 && !shell.active) {
		snapshot();
		accepted = card_bench_arm(shell.output, argv[1], shell.policy.count);
	} else if (argc == 1 && strcmp(argv[0], "benchmark-stop") == 0) {
		card_bench_stop();
		accepted = true;
	} else if (argc == 1 && strcmp(argv[0], "enter") == 0)
		accepted = enter(seat);
	else if (argc == 1 && strcmp(argv[0], "back") == 0) {
		handle_result(cs_leave(&shell.policy));
		accepted = true;
	} else if (argc == 1 && strcmp(argv[0], "cancel") == 0)
		accepted = card_shell_cancel(seat);
	else if (argc == 1 && (strcmp(argv[0], "previous") == 0 || strcmp(argv[0], "next") == 0)) {
		handle_result(cs_step(&shell.policy, strcmp(argv[0], "previous") == 0 ? -1 : 1));
		accepted = true;
	} else if (argc == 1 && strcmp(argv[0], "close") == 0 && shell.policy.count) {
		handle_result(cs_request_close(&shell.policy, shell.policy.cards[shell.policy.selected].id,
									   now_ms()));
		accepted = true;
	} else if (argc == 2 && strcmp(argv[0], "up") == 0) {
		char *end;
		long id = strtol(argv[1], &end, 10);
		if (*end || id < 0 || id > INT32_MAX)
			return cmd_results_new(CMD_INVALID, "invalid contact");
		shell.injecting = true;
		accepted = card_shell_up(seat, NULL, id, (uint32_t)now_ms());
		shell.injecting = false;
	} else if (argc == 4 && (strcmp(argv[0], "down") == 0 || strcmp(argv[0], "motion") == 0)) {
		char *end;
		long id = strtol(argv[1], &end, 10);
		if (*end || id < 0 || id > INT32_MAX)
			return cmd_results_new(CMD_INVALID, "invalid contact");
		double x = strtod(argv[2], &end);
		if (*end || !isfinite(x))
			return cmd_results_new(CMD_INVALID, "invalid x");
		double y = strtod(argv[3], &end);
		if (*end || !isfinite(y))
			return cmd_results_new(CMD_INVALID, "invalid y");
		shell.injecting = true;
		accepted = strcmp(argv[0], "down") == 0 ? card_shell_down(seat, NULL, id, x, y, (uint32_t)now_ms())
												: card_shell_motion(seat, NULL, id, x, y, (uint32_t)now_ms());
		shell.injecting = false;
	} else
		return cmd_results_new(
			CMD_INVALID,
			"expected enter|back|previous|next|close|cancel|down ID X Y|motion ID X Y|up ID");
	sway_log(SWAY_INFO, "K230_CARD_SHELL input=injected operation=%s accepted=%d", argv[0],
			 accepted);
	return cmd_results_new(accepted ? CMD_SUCCESS : CMD_FAILURE,
						   accepted ? NULL : "card event rejected");
}

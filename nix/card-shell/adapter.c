/* Opt-in product adapter: Sway alone owns surfaces, input and presentation. */
#include "log.h"
#include "sway/card-shell-policy.h"
#include "sway/card-keyboard-gesture.h"
#include "sway/card_shell_appearance.h"
#include "sway/card_shell.h"
#include "sway/card_shell_render.h"
#include "sway/card_shell_route.h"
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
#include "sway/tree/arrange.h"
#include "sway/tree/container.h"
#include "sway/tree/view.h"
#include "sway/tree/workspace.h"
#include <drm_fourcc.h>
#include <dirent.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <math.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <wlr/render/pixman.h>
#include <wlr/types/wlr_buffer.h>
#include <wlr/types/wlr_compositor.h>
#include <wlr/types/wlr_output.h>
#include <wlr/types/wlr_scene.h>
#include <wlr/types/wlr_touch.h>
#include <wlr/util/box.h>
extern char **environ;
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
	/* The card's own rounded, bordered bezel: tight to the live content's
	 * aspect-fit box, never the full deck slot (finding: bare-app-cards --
	 * a full-slot coloured plate read as letterboxing around the snapshot). */
	struct wlr_scene_buffer *plate;
	struct card_brush plate_brush;
	int plate_width, plate_height;
	struct wlr_scene_buffer *label;
	char *label_text;
	struct wlr_scene_buffer *label_icon;
	char label_icon_letter;
	/* NULL when the header icon is currently the fallback badge; otherwise
	 * the resolved Icon= name it was last built from, so a card whose
	 * .desktop identity resolves to a different icon (or stops resolving
	 * one) rebuilds label_icon instead of keeping a stale image. */
	char *label_icon_key;
	bool label_selected;
	bool hidden, original_enabled;
	double scale;
	int x, y, pixel_x, pixel_y;
	/* The plate: the content's aspect-fit box padded out by CARD_PLATE_PAD on
	 * every side, so the rounded/bordered plate is never fully hidden behind
	 * the (square-cornered) live pixels it sits under. box_x/box_y is its
	 * origin, box_width/box_height its size; pixel_x/pixel_y (the mirror
	 * origin) sits CARD_PLATE_PAD inside it. */
	int box_x, box_y, box_width, box_height;
	bool source_valid;
	int source_x, source_y;
	bool expand_start_valid;
	int last_width, last_height;
	double expand_x, expand_y, expand_width, expand_height;
	/* True while this card is being rendered at the entry gesture's shared
	 * full-panel frame (cs_entry_visual_rect's common_full_frame case, set
	 * in sync_card) -- i.e. it, not only the outgoing entry_id card, is
	 * drawn as a full-screen adjacent strip rather than a small deck card.
	 * card_clip_box() reads this so the incoming neighbour's mirrored
	 * content is never clipped to the small deck viewport mid-drag. */
	bool full_clip;
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
	struct wlr_box ordinary_usable;
	bool ordinary_usable_valid;
	struct sway_seat *seat;
	struct wl_listener output_destroy, seat_destroy;
	struct wlr_scene_tree *ui, *deck, *chrome, *button;
	struct wlr_scene_rect *canvas;
	struct wlr_scene_buffer *canvas_gradient;
	struct card_brush canvas_brush;
	int canvas_width, canvas_height;
	/* Task 3.1b: a deck gradient built ahead of commit, at prepare time, for
	 * a *candidate* generation -- see appearance_prepare's doc. Strictly
	 * advisory, like background.cache: a missing, stale, or
	 * dimension-mismatched entry falls back to appearance_canvas_refresh's
	 * own inline build, so it can only cost time, never correctness. */
	struct wlr_scene_buffer *prepared_canvas_gradient;
	struct card_brush prepared_canvas_brush;
	char prepared_canvas_generation[25];
	int prepared_canvas_width, prepared_canvas_height;
	struct card_appearance appearance;
	bool appearance_enabled;
	struct wl_event_source *timer;
	char *status_text;
	struct wlr_scene_buffer *status;
	unsigned commits, samples, frames, presents, ticks;
	uint64_t cache_hits, cache_misses, cache_fallbacks;
	int button_contact, pressed_button;
	bool button_down;
	double button_x, button_y;
	/* A bottom-edge escape gesture claimed while a Rust overlay (Drawer,
	 * Shade, Settings and its sub-pages) was still mapped: see input_down's
	 * drawer_mapped() bottom-edge carve-out. Sends the overlay a "hide"
	 * request and keeps tracking the same entry/edge gesture an app would
	 * use, but the overlay's own unmap is asynchronous, so it can still be
	 * drawer_mapped() on the very next prepare_impl(). This flag tells that
	 * function's defensive cancel-on-remap cleanup that the active
	 * contact/edge tracking is this deliberate escape, not stale state left
	 * over from before the overlay mapped, so it must not be cancelled out
	 * from under the gesture. Cleared once the overlay actually unmaps. */
	bool overlay_escaping;
	struct card_shell_drawer_gesture drawer_gesture;
	struct card_shell_drawer_gesture shade_gesture;
	struct card_shell_reveal_stream reveal;
	struct kg_policy keyboard;
	struct wlr_scene_rect *keyboard_grip, *keyboard_grip_line;
	struct wlr_scene_rect *ordinary_backdrop;
} shell;
static const float backdrop[4] = {.067, .094, .153, 1};
static const float card_color[4] = {.141, .286, .353, 1};
static const float selected_color[4] = {.184, .420, .310, 1};
/* webOS-style card plate: a small rounded, bordered bezel hugging the live
 * snapshot's own aspect-fit box, not a full-bleed rectangle behind it. The
 * radius stays a couple of px under the pad any caller leaves around the
 * mirrored content, so the bezel's rounded corner never cuts into the
 * (square-cornered) live pixels sitting on top of it. */
#define CARD_PLATE_RADIUS 8.0
#define CARD_PLATE_STROKE_UNSELECTED 1.5
#define CARD_PLATE_STROKE_SELECTED 3.0
/* Per-side margin between the live snapshot and the plate's outer edge.
 * Must stay >= CARD_PLATE_RADIUS: the plate's rounded corner is cut within
 * this margin, so the (square) live content inset by this much never pokes
 * out past the rounded silhouette, and the stroked rim always has room to
 * show. */
#define CARD_PLATE_PAD 10.0
static uint32_t argb_from_float(const float rgba[4]) {
	uint32_t a = (uint32_t)lround(rgba[3] * 255.0f) & 0xff;
	uint32_t r = (uint32_t)lround(rgba[0] * 255.0f) & 0xff;
	uint32_t g = (uint32_t)lround(rgba[1] * 255.0f) & 0xff;
	uint32_t b = (uint32_t)lround(rgba[2] * 255.0f) & 0xff;
	return (a << 24) | (r << 16) | (g << 8) | b;
}
/* A themed card/selected brush already differs by colour; the unthemed
 * default becomes a one-stop brush of the same fixed colours so every card
 * plate -- themed or not -- draws through the one card_plate_scene path. */
static const struct card_brush *card_brush_for(bool selected) {
	static struct card_brush fallback_card, fallback_selected;
	static bool ready;
	if (!ready) {
		fallback_card = (struct card_brush){.count = 1, .alpha = 1,
			.stops = {{.argb = argb_from_float(card_color), .offset = 0}}};
		fallback_selected = (struct card_brush){.count = 1, .alpha = 1,
			.stops = {{.argb = argb_from_float(selected_color), .offset = 0}}};
		ready = true;
	}
	if (shell.appearance_enabled)
		return selected ? &shell.appearance.selected : &shell.appearance.card;
	return selected ? &fallback_selected : &fallback_card;
}
/* A subtle, always-visible rim around the plate: blended toward white rather
 * than reusing the fill colour outright, since a themed fill can be fully
 * opaque (identical fill/rim would vanish) or translucent by design. Selected
 * cards get a stronger, brighter rim instead of a differently coloured plate. */
static void plate_stroke_color(const float fill[4], bool selected, float out[4]) {
	float mix = selected ? 0.5f : 0.22f;
	out[0] = fill[0] * (1 - mix) + mix;
	out[1] = fill[1] * (1 - mix) + mix;
	out[2] = fill[2] * (1 - mix) + mix;
	out[3] = 1.0f;
}
static uint32_t appearance_text(bool selected) {
	return shell.appearance_enabled ?
		(selected ? shell.appearance.selected_text : shell.appearance.text) : 0xfff7faff;
}
/* card_appearance carries no separate muted/secondary tone; approximate one
 * with a fixed alpha reduction rather than plumbing a new theme token, so
 * the gesture-hint cue below can match the Rust side's muted, de-emphasized
 * treatment (finding P1-2) without a cross-cutting appearance.c/token change. */
static uint32_t appearance_text_muted(bool selected) {
	return (appearance_text(selected) & 0x00ffffff) | 0xb3000000;
}
static uint64_t now_ms(void) {
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return (uint64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}

/* Only wlroots-certified opaque pixels ABOVE the wallpaper can pause its
 * decoder. Geometry-only Sway IPC would misclassify translucent apps. This
 * deliberately undercounts transformed/cropped buffers rather than claiming
 * coverage from a region whose coordinates we cannot prove equivalent. */
struct wallpaper_cover {
	struct sway_output *output;
	pixman_region32_t opaque;
};
static bool wallpaper_above(struct sway_output *output, struct wlr_scene_node *node) {
	for (; node; node = node->parent ? &node->parent->node : NULL) {
		if (node == &output->layers.shell_background->node ||
			node == &output->layers.shell_bottom->node) return false;
		if (node == &output->layers.tiling->node ||
			node == &output->layers.fullscreen->node ||
			node == &output->layers.shell_top->node ||
			node == &output->layers.shell_overlay->node) return true;
	}
	return false;
}
static void wallpaper_opaque_buffer(struct wlr_scene_buffer *buffer, int x, int y, void *data) {
	struct wallpaper_cover *cover = data;
	if (!wallpaper_above(cover->output, &buffer->node) || !buffer->buffer ||
		buffer->opacity != 1 || buffer->transform != WL_OUTPUT_TRANSFORM_NORMAL ||
		buffer->src_box.width > 0 || buffer->src_box.height > 0 ||
		buffer->dst_width <= 0 || buffer->dst_height <= 0) return;
	pixman_region32_t opaque;
	pixman_region32_init(&opaque);
	if (wlr_buffer_is_opaque(buffer->buffer))
		pixman_region32_union_rect(&opaque, &opaque, x, y,
			buffer->dst_width, buffer->dst_height);
	else {
		pixman_region32_copy(&opaque, &buffer->opaque_region);
		pixman_region32_intersect_rect(&opaque, &opaque, 0, 0,
			buffer->dst_width, buffer->dst_height);
		pixman_region32_translate(&opaque, x, y);
	}
	pixman_region32_union(&cover->opaque, &cover->opaque, &opaque);
	pixman_region32_fini(&opaque);
}
static void wallpaper_cover_publish(void) {
	static uint64_t previous;
	uint64_t now = now_ms();
	if (!shell.output || !shell.output->scene_output || now - previous < 500) return;
	previous = now;
	const char *path = getenv("SWAY_K230_WALLPAPER_COVER_PATH");
	if (!path || strncmp(path, "/run/shell/", 11) || strlen(path) > 200 ||
		strstr(path, "..")) return;
	struct wallpaper_cover cover = {.output = shell.output};
	pixman_region32_init(&cover.opaque);
	wlr_scene_output_for_each_buffer(shell.output->scene_output,
		wallpaper_opaque_buffer, &cover);
	pixman_box32_t frame = {.x1 = shell.output->lx, .y1 = shell.output->ly,
		.x2 = shell.output->lx + shell.output->width,
		.y2 = shell.output->ly + shell.output->height};
	bool opaque_deck = false;
	const struct cs_config *cfg = &shell.policy.config;
	if (shell.active && shell.deck && shell.canvas &&
		cfg->top_reserved == 0 && cfg->bottom_reserved == 0 &&
		shell.canvas->node.enabled &&
		(!shell.canvas_gradient || !shell.canvas_gradient->node.enabled)) {
		float color[4];
		if (shell.appearance_enabled)
			card_brush_solid_color(&shell.appearance.canvas, color);
		else memcpy(color, backdrop, sizeof(color));
		opaque_deck = color[3] == 1 &&
		(!shell.appearance_enabled || !shell.appearance.wallpaper ||
			shell.appearance.canvas_authored);
	}
	bool covered = opaque_deck || (shell.output->width > 0 && shell.output->height > 0 &&
		pixman_region32_contains_rectangle(&cover.opaque, &frame) == PIXMAN_REGION_IN);
	pixman_region32_fini(&cover.opaque);
	char temporary[256];
	int length = snprintf(temporary, sizeof(temporary), "%s.tmp.%ld.%" PRIu64,
		path, (long)getpid(), now);
	if (length <= 0 || (size_t)length >= sizeof(temporary)) return;
	int fd = open(temporary, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
	if (fd < 0) return;
	char payload[160];
	length = snprintf(payload, sizeof(payload),
		"{\"schema\":1,\"covered\":%s,\"monotonic_ms\":%" PRIu64
		",\"width\":%d,\"height\":%d}\n", covered ? "true" : "false", now,
		shell.output->width, shell.output->height);
	bool okay = length > 0 && (size_t)length < sizeof(payload) &&
		write(fd, payload, (size_t)length) == length && fsync(fd) == 0;
	close(fd);
	if (okay) okay = rename(temporary, path) == 0;
	if (!okay) unlink(temporary);
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
static bool touch_first(void) {
	const char *s = getenv("SWAY_K230_CARD_TOUCH_FIRST");
	return s && strcmp(s, "1") == 0;
}
static bool keyboard_gestures_enabled(void) {
	const char *s = getenv("SWAY_K230_KEYBOARD_GESTURES");
	return touch_first() && s && strcmp(s, "1") == 0;
}
static double keyboard_height(void) {
	const char *s = getenv("SWAY_K230_KEYBOARD_HEIGHT");
	if (!s || !*s) return 420;
	char *end = NULL;
	long n = strtol(s, &end, 10);
	return *end || n < 128 || n > 1000 ? 420 : (double)n;
}
static bool keyboard_signal(const char *action) {
	const char *path = getenv("SWAY_K230_KEYBOARD_SIGNAL");
	if (!path || path[0] != '/' || !path[1]) return false;
	char *const argv[] = {(char *)path, (char *)action, NULL};
	pid_t pid;
	return posix_spawn(&pid, path, NULL, NULL, argv, environ) == 0;
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
static bool chrome(void);
static void keyboard_refresh(void);
static void ordinary_backdrop_sync(struct sway_output *output);
static void home_layer_sync(struct sway_output *output);
static struct sway_layer_surface *keyboard_layer(struct sway_output *output);
/* Task 3.1b: drop any gradient built ahead of commit for a candidate that
 * was superseded (a newer prepare, a rollback, or a live geometry change)
 * before it was ever adopted. It was never attached anywhere but `shell.deck`
 * itself and never enabled, so destroying it here cannot affect anything
 * currently visible. */
static void prepared_canvas_gradient_drop(void) {
	if (shell.prepared_canvas_gradient)
		wlr_scene_node_destroy(&shell.prepared_canvas_gradient->node);
	shell.prepared_canvas_gradient = NULL;
	shell.prepared_canvas_generation[0] = 0;
}
/* Registered as `card_appearance_start`'s advisory `prepare` callback.
 * Pre-builds the deck's gradient scene buffer for a *candidate* theme while
 * it is only prepared, not committed, so `appearance_canvas_refresh` can
 * later adopt an already-painted buffer instead of running Cairo's
 * linear-gradient paint over the full deck canvas inside the commit path.
 * The built node is created disabled and is never reachable from
 * `shell.canvas`/`shell.canvas_gradient` until a matching commit promotes
 * it, so a candidate that is superseded or never committed only wastes the
 * one buffer -- never touches anything live. Bounded to the same single
 * slot as `shell.canvas_gradient` itself (mirroring background_decode.rs's
 * `BackgroundCache`), since only the most recently prepared candidate can
 * plausibly be the next Apply. */
static void appearance_prepare(const struct card_appearance *candidate, void *data) {
	(void)data;
	if (!shell.canvas || !shell.deck || !shell.output || candidate->canvas.count <= 1)
		return; // nothing to warm: no scene yet, or this candidate has no gradient to build
	const struct cs_config *cfg = &shell.policy.config;
	int width = cfg->width;
	int height = cfg->height - cfg->top_reserved - cfg->bottom_reserved;
	if (width <= 0 || height <= 0) return;
	if (shell.prepared_canvas_gradient &&
		!strcmp(shell.prepared_canvas_generation, candidate->generation) &&
		shell.prepared_canvas_width == width && shell.prepared_canvas_height == height &&
		!memcmp(&shell.prepared_canvas_brush, &candidate->canvas, sizeof(candidate->canvas)))
		return; // already warm for this exact candidate/geometry -- e.g. a
			// browsed-ahead theme (task 3.2) re-prepared by Apply's own
			// internal prepare immediately before commit
	prepared_canvas_gradient_drop();
	struct wlr_scene_buffer *built = card_brush_scene(shell.deck, &candidate->canvas, width, height);
	if (!built) return; // advisory: appearance_canvas_refresh falls back to its own inline build
	wlr_scene_node_place_above(&built->node, &shell.canvas->node);
	wlr_scene_node_set_enabled(&built->node, false);
	wlr_scene_node_set_position(&built->node, shell.output->lx, shell.output->ly + cfg->top_reserved);
	shell.prepared_canvas_gradient = built;
	shell.prepared_canvas_brush = candidate->canvas;
	strcpy(shell.prepared_canvas_generation, candidate->generation);
	shell.prepared_canvas_width = width;
	shell.prepared_canvas_height = height;
}
static bool appearance_canvas_refresh(void) {
	if (!shell.canvas || !shell.deck || !shell.output) return true;
	const struct cs_config *cfg = &shell.policy.config;
	int width = cfg->width;
	int height = cfg->height - cfg->top_reserved - cfg->bottom_reserved;
	if (width <= 0 || height <= 0) return false;
	const struct card_brush *brush = &shell.appearance.canvas;
	bool gradient = shell.appearance_enabled && brush->count > 1;
	if (gradient && shell.prepared_canvas_gradient &&
		!strcmp(shell.prepared_canvas_generation, shell.appearance.generation) &&
		shell.prepared_canvas_width == width && shell.prepared_canvas_height == height &&
		!memcmp(&shell.prepared_canvas_brush, brush, sizeof(*brush))) {
		/* Task 3.1b: this exact candidate was already warmed at prepare
		 * time -- adopt it instead of repainting. Commit becomes a pointer
		 * swap plus the enable/position calls below, not a Cairo paint. */
		if (shell.canvas_gradient) wlr_scene_node_destroy(&shell.canvas_gradient->node);
		shell.canvas_gradient = shell.prepared_canvas_gradient;
		shell.canvas_brush = *brush;
		shell.canvas_width = width;
		shell.canvas_height = height;
		shell.prepared_canvas_gradient = NULL;
		shell.prepared_canvas_generation[0] = 0;
		/* Named stage marker (task 1): tools/theme-swap-jank.py's merged
		 * timeline picks this up via its K230_CARD_SHELL journal parsing,
		 * so a before/after board capture can show the Cairo paint moving
		 * off the commit path once task 3.2's browse-ahead has run. */
		sway_log(SWAY_INFO, "K230_CARD_SHELL appearance-canvas-gradient-adopted generation=%s",
			shell.appearance.generation);
	} else if (gradient && (!shell.canvas_gradient ||
		memcmp(&shell.canvas_brush, brush, sizeof(*brush)) != 0 ||
		shell.canvas_width != width || shell.canvas_height != height)) {
		struct wlr_scene_buffer *replacement = card_brush_scene(shell.deck, brush, width, height);
		if (!replacement) return false;
		wlr_scene_node_place_above(&replacement->node, &shell.canvas->node);
		if (shell.canvas_gradient)
			wlr_scene_node_destroy(&shell.canvas_gradient->node);
		shell.canvas_gradient = replacement;
		shell.canvas_brush = *brush;
		shell.canvas_width = width;
		shell.canvas_height = height;
		if (gradient)
			sway_log(SWAY_INFO,
				"K230_CARD_SHELL appearance-canvas-gradient-built generation=%s",
				shell.appearance.generation);
	}
	if (shell.canvas_gradient) {
		wlr_scene_node_set_enabled(&shell.canvas_gradient->node, gradient);
		wlr_scene_node_set_position(&shell.canvas_gradient->node,
			shell.output->lx, shell.output->ly + cfg->top_reserved);
	}
	float rgba[4];
	if (shell.appearance_enabled) card_brush_solid_color(brush, rgba);
	else memcpy(rgba, backdrop, sizeof(rgba));
	if (shell.appearance_enabled && shell.appearance.wallpaper &&
		!shell.appearance.canvas_authored) rgba[3] = 0;
	wlr_scene_rect_set_color(shell.canvas, rgba);
	wlr_scene_node_set_enabled(&shell.canvas->node, !gradient);
	wlr_scene_rect_set_size(shell.canvas, width, height);
	wlr_scene_node_set_position(&shell.canvas->node,
		shell.output->lx, shell.output->ly + cfg->top_reserved);
	return true;
}
static bool appearance_apply(const struct card_appearance *next, void *data) {
	(void)data;
	shell.appearance = *next;
	shell.appearance_enabled = true;
	if (shell.keyboard_grip && shell.keyboard_grip_line) {
		float bg[4], line[4];
		card_brush_solid_color(&next->card, bg);
		/* The selected card fill can be nearly identical to card background.
		 * Use the authored foreground role for a readable touch handle. */
		line[0] = ((next->text >> 16) & 255) / 255.0f;
		line[1] = ((next->text >> 8) & 255) / 255.0f;
		line[2] = (next->text & 255) / 255.0f;
		line[3] = 1.0f;
		wlr_scene_rect_set_color(shell.keyboard_grip, bg);
		wlr_scene_rect_set_color(shell.keyboard_grip_line, line);
	}
	if (!appearance_canvas_refresh()) return false;
	struct card *c;
	wl_list_for_each(c, &shell.cards, link) {
		if (c->label) wlr_scene_node_destroy(&c->label->node);
		c->label = NULL;
		free(c->label_text);
		c->label_text = NULL;
		if (c->label_icon) wlr_scene_node_destroy(&c->label_icon->node);
		c->label_icon = NULL;
		c->label_icon_letter = 0;
		free(c->label_icon_key);
		c->label_icon_key = NULL;
	}
	shell.chrome_valid = false;
	return (!shell.active || sync_scene()) && chrome();
}
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
	c->label_icon = NULL;
	c->label_icon_letter = 0;
	free(c->label_icon_key);
	c->label_icon_key = NULL;
	c->plate = NULL;
	free(c->label_text);
	c->label_text = NULL;
	if (c->hidden && live(c->view))
		wlr_scene_node_set_enabled(&c->view->scene_tree->node, c->original_enabled);
	c->hidden = false;
	c->source_valid = false;
	c->expand_start_valid = false;
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
/* Card header identity (finding P0-1): resolve a running window's app_id to
 * its shipped .desktop entry's Name=, the same freedesktop mechanism the
 * drawer's own catalog uses (task 1.4 of the-handheld-presents-a-coherent-shell),
 * instead of a 3-entry strcmp allowlist that silently regressed to the raw,
 * live-changing window title for anything else. StartupWMClass=<app_id> is
 * the standard field for exactly this window-to-entry mapping; falling back
 * to the file's own basename covers entries (like nnn.desktop) that already
 * happen to match. This is a dependency-free scan, not GDesktopAppInfo/gio:
 * gio is not linked into this compositor today, and adding it is a bigger
 * build-surface change than a rendering/label fix warrants. */
#define DESKTOP_IDENTITY_CACHE_MAX 16
struct desktop_identity_entry {
	char *app_id;
	char *name;
	/* The raw Icon= value (a themed icon name or an absolute path), resolved
	 * through the installed icon theme by nix/card-shell/icon.c at draw
	 * time -- never a decoded image here, matching the drawer's own
	 * separation of "find the desktop entry" from "resolve the icon file"
	 * (nix/rust-shell-client/src/icon.rs). NULL when the entry has none. */
	char *icon;
};
static struct desktop_identity_entry desktop_identity_cache[DESKTOP_IDENTITY_CACHE_MAX];
static size_t desktop_identity_cache_count;
static bool desktop_entry_group_line(bool *in_entry, const char *line) {
	if (line[0] == '[') {
		*in_entry = strcmp(line, "[Desktop Entry]") == 0;
		return true;
	}
	return false;
}
static bool desktop_file_matches(const char *path, const char *app_id) {
	FILE *f = fopen(path, "r");
	if (!f)
		return false;
	char line[512];
	bool in_entry = false, has_class = false, matched = false;
	while (fgets(line, sizeof(line), f)) {
		size_t len = strlen(line);
		while (len && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = 0;
		bool header = line[0] == '[';
		if (header) { in_entry = strcmp(line, "[Desktop Entry]") == 0; continue; }
		if (!in_entry) continue;
		if (strncmp(line, "StartupWMClass=", 15) == 0) {
			has_class = true;
			matched = strcmp(line + 15, app_id) == 0;
			break;
		}
	}
	fclose(f);
	if (has_class)
		return matched;
	const char *base = strrchr(path, '/');
	base = base ? base + 1 : path;
	size_t blen = strlen(base);
	if (blen > 8 && strcmp(base + blen - 8, ".desktop") == 0)
		blen -= 8;
	return strlen(app_id) == blen && strncmp(base, app_id, blen) == 0;
}
/* Single pass over the matched .desktop file for both Name= and Icon=, so
 * resolving a card's header identity never scans the file twice. Either
 * out-param may be left NULL by the caller to skip that field; each is set
 * at most once, from the file's first [Desktop Entry] group, matching
 * freedesktop's own "first Name/Icon key in the main group wins" reading. */
static void parse_desktop_entry(const char *path, char **name_out, char **icon_out) {
	FILE *f = fopen(path, "r");
	if (!f)
		return;
	char line[512];
	bool in_entry = false;
	while (fgets(line, sizeof(line), f) &&
			!((!name_out || *name_out) && (!icon_out || *icon_out))) {
		size_t len = strlen(line);
		while (len && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = 0;
		if (desktop_entry_group_line(&in_entry, line))
			continue;
		if (!in_entry)
			continue;
		if (name_out && !*name_out && strncmp(line, "Name=", 5) == 0 && line[5])
			*name_out = strdup(line + 5);
		else if (icon_out && !*icon_out && strncmp(line, "Icon=", 5) == 0 && line[5])
			*icon_out = strdup(line + 5);
	}
	fclose(f);
}
/* GCC's -Wformat-truncation cannot see that `dir` (one XDG_DATA_DIRS
 * segment) and `entry->d_name` (bounded by struct dirent) never actually
 * approach PATH_MAX together; the explicit length checks below are the real
 * truncation guard; this pragma only silences the compiler's own worst-case
 * static estimate, which treats every source buffer as if fully populated
 * out to its declared size. */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wformat-truncation"
static void resolve_desktop_entry(const char *app_id, char **name_out, char **icon_out) {
	const char *xdg = getenv("XDG_DATA_DIRS");
	if (!xdg || !*xdg)
		xdg = "/run/current-system/sw/share:/usr/local/share:/usr/share";
	char *dirs = strdup(xdg);
	if (!dirs)
		return;
	bool done = false;
	for (char *dir = strtok(dirs, ":"); dir && !done; dir = strtok(NULL, ":")) {
		char appdir[PATH_MAX];
		if (strlen(dir) + strlen("/applications") >= sizeof(appdir))
			continue;
		snprintf(appdir, sizeof(appdir), "%s/applications", dir);
		DIR *d = opendir(appdir);
		if (!d)
			continue;
		struct dirent *entry;
		while (!done && (entry = readdir(d))) {
			size_t len = strlen(entry->d_name);
			if (len < 9 || strcmp(entry->d_name + len - 8, ".desktop") != 0)
				continue;
			char path[PATH_MAX];
			if (strlen(appdir) + 1 + len >= sizeof(path))
				continue;
			snprintf(path, sizeof(path), "%s/%s", appdir, entry->d_name);
			if (desktop_file_matches(path, app_id)) {
				parse_desktop_entry(path, name_out, icon_out);
				done = true;
			}
		}
		closedir(d);
	}
	free(dirs);
}
#pragma GCC diagnostic pop
/* Desktop entries are static after boot; a bounded per-app_id cache avoids
 * re-scanning every applications/ directory on every card redraw. Returns
 * the cache entry itself (name/icon may each individually be NULL when the
 * matched .desktop file lacks that key, or no entry matched at all) so a
 * single lookup serves both the card header's name and its icon. */
static const struct desktop_identity_entry *desktop_identity(const char *app_id) {
	if (!app_id || !*app_id)
		return NULL;
	for (size_t i = 0; i < desktop_identity_cache_count; i++)
		if (strcmp(desktop_identity_cache[i].app_id, app_id) == 0)
			return &desktop_identity_cache[i];
	char *name = NULL, *icon = NULL;
	resolve_desktop_entry(app_id, &name, &icon);
	if (desktop_identity_cache_count < DESKTOP_IDENTITY_CACHE_MAX) {
		struct desktop_identity_entry *e = &desktop_identity_cache[desktop_identity_cache_count++];
		e->app_id = strdup(app_id);
		e->name = name;
		e->icon = icon;
		return e;
	}
	free(name);
	free(icon);
	return NULL;
}
static const char *desktop_identity_name(const char *app_id) {
	const struct desktop_identity_entry *e = desktop_identity(app_id);
	return e ? e->name : NULL;
}
/* The resolved Icon= value for app_id (a themed icon name or absolute path,
 * not yet decoded), or NULL if the matched entry has none or none matched.
 * card_icon_header (render.c, backed by icon.c) resolves this through the
 * installed icon theme at draw time. */
static const char *desktop_identity_icon(const char *app_id) {
	const struct desktop_identity_entry *e = desktop_identity(app_id);
	return e ? e->icon : NULL;
}
/* The badge glyph is the resolved title's own first letter, matching the
 * drawer's fallback-initial treatment when no icon image is available
 * (finding P0-1) -- ASCII only, since every shipped app name is ASCII; a
 * non-ASCII first byte falls back to '?' rather than a mis-decoded glyph. */
static char card_badge_letter(const char *title) {
	if (!title || !*title)
		return '?';
	unsigned char c = (unsigned char)title[0];
	if (c >= 'a' && c <= 'z')
		return (char)(c - 32);
	if ((c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9'))
		return (char)c;
	return '?';
}
static const char *card_display_title(enum cs_content content, const char *title,
		const char *app_id, bool compact, char *name_buf, size_t name_buf_len) {
	if (content != CS_LIVE)
		return cs_card_text(content);
	if (app_id) {
		const char *name = desktop_identity_name(app_id);
		if (name && *name) {
			snprintf(name_buf, name_buf_len, "%s", name);
			return name_buf;
		}
		/* Safety net for the three shipped apps if XDG_DATA_DIRS is not set
		 * up as expected (a sandboxed test build, say): preserved from
		 * before desktop-entry resolution existed, and only reachable in
		 * the rollback (non-touch-first) chrome, which predates it. */
		if (compact) {
			if (strcmp(app_id, "k230-terminal") == 0) return "Terminal";
			if (strcmp(app_id, "k230-monitor") == 0) return "Monitor";
			if (strcmp(app_id, "nnn") == 0) return "Files";
		}
	}
	/* Arbitrary third-party titles, including document and mail names with
	 * @, are preserved as-is when no desktop entry claims this app_id. */
	return title && *title ? title : "Application";
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
static struct wlr_box card_clip_box(struct card *c) {
	/* c->full_clip mirrors the entry_id special case for every card sharing
	 * the entry gesture's common full-panel frame (see sync_card): the
	 * incoming neighbour is drawn full-screen right alongside the outgoing
	 * app during a direct app-switch drag, so its mirrored content must not
	 * be clipped down to the small deck viewport either. This box is always
	 * a superset of clip_box(), so once a card has actually shrunk into the
	 * deck grid (entry_progress near 1) the wider clip is a no-op. */
	if ((shell.policy.mode == CS_ENTERING && (c->id == shell.policy.entry_id || c->full_clip)) ||
		(shell.policy.mode == CS_EXPANDING && c->id == shell.policy.expand_id))
		return (struct wlr_box){shell.output->lx, shell.output->ly,
			shell.policy.config.width, shell.policy.config.height};
	return clip_box();
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
					card_clip_box(c))) {
		if (scaled_cache_enabled()) shell.cache_fallbacks++;
		if (copy->buffer != source->buffer)
			wlr_scene_buffer_set_buffer(copy, source->buffer);
		card_clip_buffer(copy, source, c->scale, x, y, c->x + c->pixel_x, c->y + c->pixel_y,
					 card_clip_box(c));
	}
	order_mirror(previous, copy);
	return true;
}
static bool label_update(struct wlr_scene_tree *parent, struct wlr_scene_buffer **node,
						 char **saved, const char *text, int width, int height, int size,
						 uint32_t argb) {
	if (*node && *saved && strcmp(*saved, text) == 0 && (*node)->buffer->width == width &&
		(*node)->buffer->height == height)
		return true;
	struct wlr_scene_buffer *next = card_label_color(parent, text, width, height, size, argb);
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
/* The card IS the live snapshot: a small rounded, bordered plate sized to
 * c->box_width/box_height (the content's own aspect-fit box, set by the
 * caller before this runs), positioned at c->pixel_x/pixel_y within the
 * card's tree -- never the full deck slot. A themed or default brush colours
 * the plate/rim; `selected` picks the brush and rim already used to
 * distinguish the current card, so selection reads as an outline change,
 * not a differently coloured full-bleed plate. */
static bool card_background(struct card *c, bool selected, bool hidden) {
	const struct card_brush *brush = card_brush_for(selected);
	int width = c->box_width, height = c->box_height;
	bool show = !hidden && width > 0 && height > 0;
	if (show && (!c->plate || memcmp(&c->plate_brush, brush, sizeof(*brush)) != 0 ||
			c->plate_width != width || c->plate_height != height)) {
		float fill[4], stroke[4];
		card_brush_solid_color(brush, fill);
		plate_stroke_color(fill, selected, stroke);
		double stroke_width =
			selected ? CARD_PLATE_STROKE_SELECTED : CARD_PLATE_STROKE_UNSELECTED;
		struct wlr_scene_buffer *next = card_plate_scene(c->tree, brush, width, height,
			CARD_PLATE_RADIUS, stroke, stroke_width);
		if (!next) return false;
		wlr_scene_node_place_below(&next->node, &c->pixels->node);
		if (c->plate) wlr_scene_node_destroy(&c->plate->node);
		c->plate = next;
		c->plate_brush = *brush;
		c->plate_width = width;
		c->plate_height = height;
	}
	if (c->plate) {
		wlr_scene_node_set_enabled(&c->plate->node, show);
		if (show) label_clip(c->plate, c->box_x, c->box_y, c->x, c->y, clip_box());
	}
	return true;
}
static bool sync_card(struct card *c, size_t index) {
	struct cs_rect r = cs_card_rect(&shell.policy, index);
	int source_x, source_y;
	if (!c->hidden && wlr_scene_node_coords(&c->view->content_tree->node,
			&source_x, &source_y)) {
		c->source_x = source_x;
		c->source_y = source_y;
		c->source_valid = true;
	}
	bool entering = shell.policy.mode == CS_ENTERING;
	bool expanding = shell.policy.mode == CS_EXPANDING && c->id == shell.policy.expand_id;
	c->full_clip = false;
	if (entering) {
		if (!c->source_valid)
			return false;
		if (c->id == shell.policy.entry_id) {
			/* The direct-switch entry gesture anchors against its own
			 * fixed target slot (cs_entry_target_rect), never the
			 * overview's own (possibly much smaller) webOS-fan card_rect --
			 * see card-shell-policy.h's cs_config comment on
			 * entry_card_width/entry_card_height. */
			struct cs_rect entry_target = cs_entry_target_rect(&shell.policy);
			if (!cs_entry_set_geometry(&shell.policy,
					c->source_x - shell.output->lx, c->source_y - shell.output->ly,
					c->view->geometry.width, c->view->geometry.height,
					entry_target.x - shell.policy.entry_dx, entry_target.y,
					entry_target.width, entry_target.height))
				return false;
		}
		struct card *origin = find(shell.policy.entry_id);
		bool common_full_frame = origin && origin->view->container &&
			origin->view->container->card_shell_ordinary_maximized &&
			c->view->container && c->view->container->card_shell_ordinary_maximized;
		c->full_clip = common_full_frame;
		r = cs_entry_visual_rect(&shell.policy, index, (struct cs_rect){
			c->source_x - shell.output->lx, c->source_y - shell.output->ly,
			c->view->geometry.width, c->view->geometry.height}, common_full_frame);
	}
	if (expanding) {
		if (!c->source_valid || !c->expand_start_valid)
			return false;
		double progress = shell.policy.expand_progress;
		r.x = (c->expand_x - shell.output->lx) * (1 - progress) +
			(c->source_x - shell.output->lx) * progress;
		r.y = (c->expand_y - shell.output->ly) * (1 - progress) +
			(c->source_y - shell.output->ly) * progress;
		r.width = c->expand_width * (1 - progress) + c->view->geometry.width * progress;
		r.height = c->expand_height * (1 - progress) + c->view->geometry.height * progress;
	}
	c->x = shell.output->lx + lround(r.x);
	c->y = shell.output->ly + lround(r.y);
	c->last_width = lround(r.width);
	c->last_height = lround(r.height);
	if (!c->tree) {
		c->tree = wlr_scene_tree_create(shell.deck);
		if (!c->tree)
			return false;
		c->pixels = wlr_scene_tree_create(c->tree);
		if (!c->pixels)
			return false;
	}
	wlr_scene_node_set_position(&c->tree->node, c->x, c->y);
	/* The content's own aspect-fit box within this frame's slot -- the whole
	 * point of the fix: size the card from the app's aspect and the
	 * available slot, not a full-bleed plate. Every content class (live,
	 * private, unavailable) uses the view's real geometry, so a denied card
	 * gets the same sensible card shape as a live one; geometry.width/height
	 * is 0 only in a degenerate case, and then the slot itself stands in.
	 *
	 * The plate's pad is interpolated by the same entry/expand progress used
	 * for r itself (matching label_space's old treatment below, before it
	 * moved outside the card): at progress 0 -- the source view's own exact
	 * geometry -- pad must be exactly 0, or the mirrored content starts life
	 * a few px smaller than the real window it is shrinking from/growing
	 * into, breaking the direct 1:1 finger-tracked scene the two-axis entry
	 * gesture depends on (test_card_shell_two_axis_runtime.py measures the
	 * tracked content's edge against the drag distance in raw pixels). Only
	 * once the card has fully settled into the steady deck does it get the
	 * full pad. */
	{
		int content_w = c->view->geometry.width, content_h = c->view->geometry.height;
		if (content_w <= 0 || content_h <= 0) {
			content_w = lround(r.width);
			content_h = lround(r.height);
		}
		double pad = entering ? CARD_PLATE_PAD * shell.policy.entry_progress :
			expanding ? CARD_PLATE_PAD * (1 - shell.policy.expand_progress) : CARD_PLATE_PAD;
		double fit_w = r.width - 2 * pad, fit_h = r.height - 2 * pad;
		if (fit_w < 1) fit_w = r.width;
		if (fit_h < 1) fit_h = r.height;
		c->scale = fmin(fit_w / content_w, fit_h / content_h);
		double scaled_w = content_w * c->scale, scaled_h = content_h * c->scale;
		c->pixel_x = lround((r.width - scaled_w) / 2);
		c->pixel_y = lround((r.height - scaled_h) / 2);
		wlr_scene_node_set_position(&c->pixels->node, c->pixel_x, c->pixel_y);
		c->box_x = c->pixel_x - (int)lround(pad);
		c->box_y = c->pixel_y - (int)lround(pad);
		c->box_width = lround(scaled_w) + 2 * (int)lround(pad);
		c->box_height = lround(scaled_h) + 2 * (int)lround(pad);
	}
	if (!card_background(c, index == shell.policy.selected, entering || expanding))
		return false;
	bool compact = touch_first();
	const char *app_id = c->content == CS_LIVE ? view_get_app_id(c->view) : NULL;
	char name_buf[128];
	const char *display_title = c->content == CS_LIVE ?
		card_display_title(c->content, view_get_title(c->view),
			app_id, compact, name_buf, sizeof(name_buf)) :
		card_display_title(c->content, NULL, NULL, compact, name_buf, sizeof(name_buf));
	const char *title = display_title;
	char rollback_title[512];
	if (!compact) {
		snprintf(rollback_title, sizeof(rollback_title), "%s%s",
			index == shell.policy.selected ? "Selected: " : "", title);
		title = rollback_title;
	}
	bool selected = index == shell.policy.selected;
	if (c->label && c->label_selected != selected) {
		wlr_scene_node_destroy(&c->label->node);
		c->label = NULL;
		free(c->label_text);
		c->label_text = NULL;
	}
	/* The card header: a real resolved icon (task 1.4 of
	 * the-handheld-presents-a-coherent-shell; docs/design/shell-ux-critique.md
	 * #1.2) plus the app's real .desktop Name= (never the raw, live-changing
	 * window title), drawn ABOVE each card -- the user's chosen webOS-fan
	 * overview, like webOS/Android's recents always pairing an identity
	 * badge with a card regardless of the live screenshot's own content --
	 * instead of the old below-the-card caption. Not shown for the
	 * placeholder text cs_card_text() returns for non-live content. */
	bool show_icon = c->content == CS_LIVE;
	int icon_size = compact ? 28 : 32;
	int header_h = compact ? 34 : 40;
	int header_gap = compact ? 8 : 10;
	int header_top = c->box_y - header_gap - header_h;
	int header_x = c->box_x;
	int text_x = header_x;
	int text_w = c->box_width;
	if (show_icon) {
		text_x += icon_size + (compact ? 6 : 8);
		text_w -= icon_size + (compact ? 6 : 8);
	}
	if (text_w < 0) text_w = 0;
	int text_size = compact ? 14 : 16;
	if (!label_update(c->tree, &c->label, &c->label_text, title,
			text_w, header_h, text_size,
			appearance_text(selected)))
		return false;
	c->label_selected = selected;
	int text_y = header_top + (header_h - (text_size + 6)) / 2;
	label_clip(c->label, text_x, text_y, c->x, c->y, clip_box());
	wlr_scene_node_set_enabled(&c->label->node, !entering && !expanding);
	char letter = show_icon ? card_badge_letter(display_title) : 0;
	const char *icon_name = show_icon ? desktop_identity_icon(app_id) : NULL;
	if (!show_icon) {
		if (c->label_icon) wlr_scene_node_destroy(&c->label_icon->node);
		c->label_icon = NULL;
		c->label_icon_letter = 0;
		free(c->label_icon_key);
		c->label_icon_key = NULL;
	} else {
		bool key_changed = (icon_name != NULL) != (c->label_icon_key != NULL) ||
			(icon_name && c->label_icon_key && strcmp(icon_name, c->label_icon_key) != 0);
		if (!c->label_icon || c->label_icon->buffer->width != icon_size ||
				c->label_icon_letter != letter || key_changed) {
			if (c->label_icon) wlr_scene_node_destroy(&c->label_icon->node);
			uint32_t fg = appearance_text(selected);
			uint32_t bg = (fg & 0x00ffffff) | 0x2e000000;
			c->label_icon = card_icon_header(c->tree, icon_name, letter, icon_size, bg, fg);
			c->label_icon_letter = letter;
			free(c->label_icon_key);
			c->label_icon_key = icon_name ? strdup(icon_name) : NULL;
		}
		if (c->label_icon) {
			int icon_y = header_top + (header_h - icon_size) / 2;
			label_clip(c->label_icon, header_x, icon_y, c->x, c->y, clip_box());
			wlr_scene_node_set_enabled(&c->label_icon->node, !entering && !expanding);
		}
	}
	if (cs_can_mirror(&shell.policy, c->id)) {
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
	struct wlr_scene_buffer *label = card_label_color(parent, text, width - 16, 48, 26,
		appearance_text(false));
	if (!rect || !label)
		return false;
	wlr_scene_node_set_position(&rect->node, x, y);
	wlr_scene_node_set_position(&label->node, x + 8, y + 9);
	return true;
}
static const char *touch_deck_status(enum cs_message message) {
	switch (message) {
	case CS_MESSAGE_EMPTY: return "No running apps";
	/* These states already have neutral text inside their card frame. */
	case CS_MESSAGE_PRIVATE:
	case CS_MESSAGE_UNAVAILABLE: return NULL;
	case CS_MESSAGE_CLOSING: return "Closing app";
	case CS_MESSAGE_CLOSE_REFUSED: return "App stayed open";
	case CS_MESSAGE_CLOSE_TIMEOUT: return "App is still open";
	case CS_MESSAGE_CLOSE_FAILED: return "Could not close app";
	case CS_MESSAGE_CANCELLED: return "Gesture cancelled";
	case CS_MESSAGE_SOURCE_GONE: return "App closed";
	case CS_MESSAGE_FAILED: return "Cards unavailable";
	case CS_MESSAGE_NONE: return NULL;
	}
	return "Cards unavailable";
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
	/* The integrated shell routes by gesture. Keep the old controls available
	 * only in the opt-in card trial's rollback mode. */
	if (touch_first()) {
		if (!shell.active)
			return true;
		/* Retitled from "Home" now that the Rust client's own pinned-icon
		 * Home screen (nix/rust-shell-client/src/home_screen.rs) is the
		 * literal Home; this remains the live app-card overview/switcher,
		 * entered the same way it always was. See
		 * openspec/changes/the-shell-presents-a-pinned-home-screen/design.md
		 * decision 2. */
		struct wlr_scene_buffer *title = card_label_color(shell.chrome, "Overview", 176, 40, 24,
			appearance_text(false));
		if (!title)
			return false;
		wlr_scene_node_set_position(&title->node, x + 24, y + 16);
		const char *text = touch_deck_status(shell.policy.message);
		if (text) {
			int status_y = shell.policy.message == CS_MESSAGE_EMPTY ? y + 210 : y + 64;
			if (!label_update(shell.chrome, &shell.status, &shell.status_text, text,
					cfg->width - 48, 44, 21, appearance_text(false)))
				return false;
			wlr_scene_node_set_position(&shell.status->node, x + 24, status_y);
		}
		/* One gesture-hint typography across the deck footer and the Rust
		 * drawer/shade hints (finding P1-2): sentence case (already was),
		 * muted rather than full-strength text color, and size 14 to match
		 * `render.rs`'s own converged hint size. */
		struct wlr_scene_buffer *cue = card_label_color(shell.chrome,
			"Swipe up for apps", cfg->width - 48, 24, 14, appearance_text_muted(false));
		if (!cue)
			return false;
		wlr_scene_node_set_position(&cue->node, x + 24,
			y + cfg->height - cfg->top_reserved - cfg->bottom_reserved - 40);
		return true;
	}
	if (!button(shell.chrome, x + cfg->width - 152, y + 8, 128, shell.active ? "Back" : "Cards",
				shell.button_down && shell.pressed_button == 1))
		return false;
	if (!shell.active)
		return true;
	struct wlr_scene_buffer *title = card_label_color(shell.chrome, "Cards", 250, 56, 42,
		appearance_text(false));
	if (!title)
		return false;
	wlr_scene_node_set_position(&title->node, x + 24, y + 8);
	const char *text = cs_message_text(shell.policy.message);
	if (!text || !*text)
		text = "Drag to browse. Tap to resume.";
	if (!label_update(shell.chrome, &shell.status, &shell.status_text, text, cfg->width - 48, 56,
					  21, appearance_text(false)))
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
static bool chrome_impl(void) {
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
static bool chrome(void) {
	uint64_t start = card_bench_input_stage_begin();
	bool ok = chrome_impl();
	if (ok && shell.chrome)
		wlr_scene_node_set_enabled(&shell.chrome->node,
			shell.policy.mode != CS_ENTERING && shell.policy.mode != CS_EXPANDING);
	card_bench_input_stage_end(CARD_BENCH_CHROME, start);
	return ok;
}
static bool sync_scene_impl(void) {
	if (!shell.active)
		return true;
	if (!appearance_canvas_refresh()) return false;
	if (shell.policy.mode == CS_ENTERING && shell.policy.entry_travel <= 0) {
		struct card *source = find(shell.policy.entry_id);
		int sx, sy;
		if (!source || !wlr_scene_node_coords(&source->view->content_tree->node, &sx, &sy))
			return false;
		source->source_x = sx; source->source_y = sy; source->source_valid = true;
		size_t index = shell.policy.count;
		for (size_t j = 0; j < shell.policy.count; ++j)
			if (shell.policy.cards[j].id == source->id) { index = j; break; }
		if (index == shell.policy.count) return false;
		/* See sync_card's identical note: the entry target is its own
		 * fixed slot, decoupled from the overview's card_rect. */
		struct cs_rect card = cs_entry_target_rect(&shell.policy);
		if (!cs_entry_set_geometry(&shell.policy, sx - shell.output->lx,
				sy - shell.output->ly, source->view->geometry.width,
				source->view->geometry.height, card.x - shell.policy.entry_dx,
				card.y, card.width, card.height)) return false;
	}
	size_t i = 0;
	struct card *c;
	if (shell.policy.mode != CS_EXPANDING)
		wl_list_for_each(c, &shell.cards, link) c->expand_start_valid = false;
	wl_list_for_each(c, &shell.cards, link) if (!sync_card(c, i++)) return false;
	if (shell.policy.mode == CS_ENTERING || shell.policy.mode == CS_EXPANDING) {
		c = find(shell.policy.mode == CS_ENTERING ? shell.policy.entry_id :
			shell.policy.expand_id);
		if (c && c->tree)
			wlr_scene_node_raise_to_top(&c->tree->node);
	}
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
static bool sync_scene(void) {
	uint64_t start = card_bench_input_stage_begin();
	bool ok = sync_scene_impl();
	card_bench_input_stage_end(CARD_BENCH_SCENE, start);
	return ok;
}
static uint64_t focus_id(struct sway_seat *seat) {
	struct sway_container *c = seat_get_focused_container(seat);
	return c && c->view ? c->node.id : 0;
}
static void restore(struct cs_result result) {
	shell.active = false;
	shell.overlay_escaping = false;
	struct card *c;
	wl_list_for_each(c, &shell.cards, link) clear_card(c);
	scaled_cache_log();
	if (shell.deck)
		wlr_scene_node_set_enabled(&shell.deck->node, false);
	/* Re-admit the ordinary-maximized backdrop now that the deck (whose
	 * own canvas made the wallpaper-reveal decision while active) is
	 * gone; see ordinary_backdrop_sync's comment. Home comes back for the
	 * same reason -- see home_layer_sync's comment. */
	if (shell.output) {
		ordinary_backdrop_sync(shell.output);
		home_layer_sync(shell.output);
	}
	if (shell.seat && !server.session_lock.lock) {
		c = find(result.focus_id);
		if (c && live(c->view)) {
			seat_set_focus_container(shell.seat, c->view->container);
			/* Focus alone does not put a floating view above its siblings.
			 * Keep the visible window in sync with the selected card. */
			container_raise_floating(c->view->container);
		} else if (shell.output && shell.output->current.active_workspace)
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
	if (shell.policy.mode == CS_EXPANDING && shell.policy.expand_progress == 0) {
		struct card *c = find(shell.policy.expand_id);
		if (c && !c->expand_start_valid && c->tree) {
			c->expand_x = c->x;
			c->expand_y = c->y;
			c->expand_width = c->last_width;
			c->expand_height = c->last_height;
			c->expand_start_valid = true;
		}
	}
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
		/* Withdraw the ordinary-maximized backdrop now that the deck is
		 * taking over the wallpaper-reveal decision; see
		 * ordinary_backdrop_sync's comment. Home is withdrawn for the same
		 * reason -- see home_layer_sync's comment -- before the deck's
		 * transparent canvas goes back up a few lines down in sync_scene(),
		 * so no frame renders with both the deck and Home visible. */
		if (shell.output) {
			ordinary_backdrop_sync(shell.output);
			home_layer_sync(shell.output);
		}
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
	unsigned keyboard_end = kg_end_stream(&shell.keyboard,
		keyboard_layer(shell.output) != NULL);
	if (keyboard_end & KG_HIDE) keyboard_signal("hide");
	if (keyboard_end & KG_DIRTY) keyboard_refresh();
	wl_list_remove(&shell.seat_destroy.link);
	shell.seat = NULL;
	cs_stream_cancel(&shell.policy);
	shell.button_down = false;
	handle_result(cs_leave(&shell.policy));
}
static void handle_output_destroy(struct wl_listener *l, void *data) {
	kg_end_stream(&shell.keyboard, false);
	card_appearance_stop();
	card_shell_reveal_abort(&shell.reveal);
	cs_stream_cancel(&shell.policy);
	shell.button_down = false;
	handle_result(cs_leave(&shell.policy));
	wl_list_remove(&shell.output_destroy.link);
	card_bench_stop();
	shell.output = NULL;
	shell.ordinary_usable_valid = false;
	if (shell.timer) {
		wl_event_source_remove(shell.timer);
		shell.timer = NULL;
	}
	if (shell.ui)
		wlr_scene_node_destroy(&shell.ui->node);
	if (shell.keyboard_grip) wlr_scene_node_destroy(&shell.keyboard_grip->node);
	if (shell.keyboard_grip_line) wlr_scene_node_destroy(&shell.keyboard_grip_line->node);
	shell.keyboard_grip = shell.keyboard_grip_line = NULL;
	if (shell.ordinary_backdrop) wlr_scene_node_destroy(&shell.ordinary_backdrop->node);
	shell.ordinary_backdrop = NULL;
	shell.ui = NULL;
	shell.deck = NULL;
	shell.chrome = NULL;
	shell.canvas = NULL;
	shell.canvas_gradient = NULL;
	/* Recursively destroyed with `shell.ui` above (it was always just a
	 * disabled child of `shell.deck`, same as `shell.canvas_gradient`);
	 * drop the now-dangling pointer so a later `appearance_prepare` never
	 * touches or re-destroys freed scene-graph memory. */
	shell.prepared_canvas_gradient = NULL;
	shell.prepared_canvas_generation[0] = 0;
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
	wallpaper_cover_publish();
	card_appearance_poll();
	unsigned keyboard_tick = kg_tick(&shell.keyboard, now_ms());
	if ((keyboard_tick & KG_HIDE) && !keyboard_signal("hide")) {
		/* A failed lifecycle helper must not strand an invisible keyboard
		 * while every new touch remains captured in WAIT_UNMAP. */
		shell.keyboard.mode=KG_SHOWN;
		shell.keyboard.progress=1;
		shell.keyboard.velocity=0;
		keyboard_tick |= KG_DIRTY;
	}
	if (keyboard_tick & KG_DIRTY) keyboard_refresh();
	if (shell.reveal.active && !card_shell_reveal_pump(&shell.reveal)) {
		card_shell_drawer_cancel(&shell.drawer_gesture);
		card_shell_drawer_cancel(&shell.shade_gesture);
		sway_log(SWAY_INFO, "K230_CARD_SHELL reveal stream closed; scene retained");
	}
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
	kg_init(&shell.keyboard, keyboard_height(),
		getenv("SWAY_K230_CARD_REDUCED_MOTION") &&
		strcmp(getenv("SWAY_K230_CARD_REDUCED_MOTION"), "1") == 0);
	shell.ordinary_usable_valid = false;
	shell.output_destroy.notify = handle_output_destroy;
	wl_signal_add(&output->node.events.destroy, &shell.output_destroy);
	shell.ui = wlr_scene_tree_create(root->layers.shell_overlay);
	if (shell.ui)
		shell.deck = wlr_scene_tree_create(shell.ui);
	if (shell.deck)
		shell.canvas = wlr_scene_rect_create(shell.deck, output->width, output->height, backdrop);
	if (shell.deck)
		wlr_scene_node_set_enabled(&shell.deck->node, false);
	/* A single ordinary-maximized app is a real Sway floating container in
	 * output->layers.tiling, not shell.deck (which is disabled outside the
	 * card overview). Its exclusive-zone reservation tracks the keyboard
	 * gesture continuously (card_shell_keyboard_adjust_usable), and a real
	 * client can be too slow to redraw at each new size before Sway's
	 * transaction timeout forces the new geometry through anyway -- the
	 * still-old-sized buffer then leaves a margin with nothing painted in
	 * it. This backdrop sits directly behind ordinary cards in that same
	 * layer (see ordinary_backdrop_sync) so that margin shows the card
	 * backdrop colour instead of the desktop wallpaper underneath. */
	shell.ordinary_backdrop = wlr_scene_rect_create(output->layers.tiling,
		output->width, output->height, card_color);
	if (shell.ordinary_backdrop)
		wlr_scene_node_set_enabled(&shell.ordinary_backdrop->node, false);
	if (keyboard_gestures_enabled()) {
		const float grip_bg[4] = {.10f, .14f, .19f, .95f};
		const float grip_line[4] = {.60f, .78f, .80f, 1.f};
		shell.keyboard_grip = wlr_scene_rect_create(output->layers.shell_overlay,
			output->width, 56, grip_bg);
		shell.keyboard_grip_line = wlr_scene_rect_create(output->layers.shell_overlay,
			96, 7, grip_line);
		if (shell.keyboard_grip) wlr_scene_node_set_enabled(&shell.keyboard_grip->node, false);
		if (shell.keyboard_grip_line) wlr_scene_node_set_enabled(&shell.keyboard_grip_line->node, false);
	}
	shell.timer = wl_event_loop_add_timer(server.wl_event_loop, tick, NULL);
	if (!shell.ui || !shell.deck || !shell.canvas || !shell.ordinary_backdrop ||
		!shell.timer || !chrome()) {
		handle_output_destroy(NULL, NULL);
		return false;
	}
	const char *appearance_socket = getenv("SWAY_K230_CARD_APPEARANCE_SOCKET");
	if (appearance_socket && *appearance_socket &&
		!card_appearance_start(appearance_socket,
			getenv("SWAY_K230_CARD_THEME_STATE_ROOT"),
			getenv("SWAY_K230_CARD_THEME_DEFAULT"), appearance_apply,
			appearance_prepare, NULL))
		sway_log(SWAY_ERROR, "K230_CARD_SHELL appearance receiver unavailable");
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
static bool popup_at(double x, double y) {
	/* A keyboard's own text popup may be mapped elsewhere on the output.
	 * Preserve popup ownership only at the contact, including over the grip. */
	return wlr_scene_node_at(&root->layers.popup->node,
		shell.output->lx + x, shell.output->ly + y, NULL, NULL) != NULL;
}
static bool launcher_mapped(void) {
	struct sway_layer_surface *layer;
	wl_list_for_each(layer, &shell.output->layer_surfaces, link) {
		if (layer->mapped && layer->layer_surface->namespace &&
			strcmp(layer->layer_surface->namespace, "k230-launcher") == 0)
			return true;
	}
	return false;
}
static bool drawer_mapped(void) {
	if (!shell.output)
		return false;
	struct sway_layer_surface *layer;
	wl_list_for_each(layer, &shell.output->layer_surfaces, link) {
		if (layer->mapped && layer->layer_surface->namespace &&
			strcmp(layer->layer_surface->namespace, "k230-shell-drawer") == 0)
			return true;
	}
	return false;
}
static struct sway_layer_surface *keyboard_layer(struct sway_output *output) {
	if (!output) return NULL;
	struct sway_layer_surface *layer;
	wl_list_for_each(layer, &output->layer_surfaces, link) {
		if (layer->mapped && layer->layer_surface->namespace &&
			strcmp(layer->layer_surface->namespace, "wvkbd") == 0)
			return layer;
	}
	return NULL;
}
/* Called after wlroots has configured the real layer surface. Only the
 * pinned wvkbd geometry qualifies; an unrelated keyboard stays untouched. */
void card_shell_keyboard_adjust_usable(struct sway_output *output, struct wlr_box *usable) {
	if (!keyboard_gestures_enabled() || !shell.initialized || shell.output != output)
		return;
	struct sway_layer_surface *layer = keyboard_layer(output);
	bool valid = layer && layer->layer_surface->current.exclusive_zone == (int)shell.keyboard.height &&
		layer->layer_surface->current.desired_height == (uint32_t)shell.keyboard.height &&
		layer->layer_surface->current.layer == ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY;
	if (!valid) {
		if (!layer) kg_surface(&shell.keyboard, false);
		if (shell.keyboard_grip) wlr_scene_node_set_enabled(&shell.keyboard_grip->node, false);
		if (shell.keyboard_grip_line) wlr_scene_node_set_enabled(&shell.keyboard_grip_line->node, false);
		return;
	}
	kg_surface(&shell.keyboard, true);
	double progress = shell.keyboard.progress;
	int hidden = (int)lround((shell.keyboard.height + 56) * (1 - progress));
	int grip = (int)lround(56 * progress);
	int allocation = (int)lround(shell.keyboard.height * (1 - progress)) - grip;
	if (usable->height + allocation > 0)
		usable->height += allocation;
	wlr_scene_node_set_position(&layer->scene->tree->node,
		layer->scene->tree->node.x, layer->scene->tree->node.y + hidden);
	if (shell.keyboard_grip && shell.keyboard_grip_line) {
		int top = output->height - (int)lround((shell.keyboard.height + 56) * progress);
		wlr_scene_node_set_position(&shell.keyboard_grip->node, output->lx, output->ly + top);
		wlr_scene_node_set_position(&shell.keyboard_grip_line->node,
			output->lx + (output->width - 96) / 2, output->ly + top + 24);
		wlr_scene_node_place_above(&shell.keyboard_grip->node, &layer->scene->tree->node);
		wlr_scene_node_place_above(&shell.keyboard_grip_line->node, &shell.keyboard_grip->node);
		wlr_scene_node_set_enabled(&shell.keyboard_grip->node, progress > 0.01);
		wlr_scene_node_set_enabled(&shell.keyboard_grip_line->node, progress > 0.01);
	}
}
static void keyboard_refresh(void) {
	if (shell.output) {
		arrange_layers(shell.output);
		wlr_output_schedule_frame(shell.output->wlr_output);
	}
}
static bool keyboard_apply_action(unsigned action) {
	if (!(action & KG_CONSUME)) return false;
	if (action & KG_CANCEL_CARD) {
		card_shell_reveal_cancel(&shell.reveal);
		memset(&shell.drawer_gesture, 0, sizeof(shell.drawer_gesture));
		memset(&shell.shade_gesture, 0, sizeof(shell.shade_gesture));
		handle_result(cs_stream_cancel(&shell.policy));
	}
	if ((action & KG_SHOW) && !keyboard_signal("show")) {
		sway_log(SWAY_INFO, "K230_KEYBOARD show helper unavailable");
		kg_cancel(&shell.keyboard);
	}
	if ((action & KG_HIDE) && !keyboard_signal("hide"))
		sway_log(SWAY_INFO, "K230_KEYBOARD hide helper unavailable");
	if (action & KG_DIRTY) keyboard_refresh();
	return true;
}
/* The Sway config marks only ordinary full-panel app containers. Floating
 * geometry otherwise ignores a layer-shell keyboard's usable-area height,
 * leaving the focused prompt beneath the keyboard. Never resize dialogs,
 * video windows, scratchpads or fullscreen views here. */
static bool ordinary_resize(struct sway_view *view, struct sway_output *output) {
	if (!view || !view->container || !output)
		return false;
	struct sway_container *con = view->container;
	if (!con->card_shell_ordinary_maximized || !container_is_floating(con) ||
		con->pending.parent || con->scratchpad || con->pending.fullscreen_mode ||
		!con->pending.workspace || con->pending.workspace->output != output)
		return false;
	struct wlr_box *usable = &output->usable_area;
	if (usable->width <= 0 || usable->height <= 0)
		return false;
	int x = output->lx + usable->x, y = output->ly + usable->y;
	if (con->pending.x == x && con->pending.y == y &&
		con->pending.width == usable->width && con->pending.height == usable->height)
		return false;
	con->pending.x = x;
	con->pending.y = y;
	con->pending.width = usable->width;
	con->pending.height = usable->height;
	arrange_container(con);
	return true;
}
/* The colour an ordinary card would show if it had no themed appearance of
 * its own; matches card_background()'s unthemed/themed choice so the
 * backdrop reads as "this card's surface", not an unrelated void. */
static void ordinary_backdrop_color(float rgba[4]) {
	if (shell.appearance_enabled) card_brush_solid_color(&shell.appearance.card, rgba);
	else memcpy(rgba, card_color, sizeof(float) * 4);
}
/* Keeps a card-coloured rect exactly at the output's current usable area,
 * directly behind ordinary cards in output->layers.tiling. A scene rect
 * resize is a pure compositor-side operation with no client round trip, so
 * unlike the ordinary card's own resize (ordinary_resize, gated on a
 * Wayland configure/ack) it never lags the animated keyboard exclusive
 * zone. It closes the gap described in ensure_ui's ordinary_backdrop
 * comment: whatever margin a slow client hasn't painted yet shows this
 * backdrop instead of the desktop wallpaper underneath. */
static void ordinary_backdrop_sync(struct sway_output *output) {
	if (!shell.ordinary_backdrop)
		return;
	bool any = false;
	/* This rect lives in output->layers.tiling, which sits above
	 * layers.shell_background (the wallpaper) in Sway's fixed scene
	 * order -- see include/sway/tree/root.h's layer list. It is meant
	 * to fill the margin behind a single ordinary-maximized app while
	 * its own resize catches up (ensure_ui's comment), never to cover
	 * the desktop generally. An ordinarily-maximized card stays flagged
	 * that way while the deck/card overview is open to look at it (the
	 * flag is per-container UX state, not "not currently being viewed
	 * in overview"), so without this gate the overview's own
	 * deck/canvas -- which does the real, appearance-aware decision
	 * about whether to reveal the wallpaper -- would always lose to
	 * this opaque rect sitting below it but still above the wallpaper.
	 * That is exactly the flat, wallpaper-less card overview reported
	 * on the board with a real maximized Terminal card. */
	if (!shell.active) {
		struct card *card;
		wl_list_for_each(card, &shell.cards, link) {
			struct sway_view *view = card->view;
			if (live(view) && view->container &&
				view->container->card_shell_ordinary_maximized &&
				container_is_floating(view->container) &&
				!view->container->scratchpad &&
				view->container->pending.workspace &&
				view->container->pending.workspace->output == output) {
				any = true;
				break;
			}
		}
	}
	wlr_scene_node_set_enabled(&shell.ordinary_backdrop->node, any);
	if (!any)
		return;
	float rgba[4];
	ordinary_backdrop_color(rgba);
	wlr_scene_rect_set_color(shell.ordinary_backdrop, rgba);
	struct wlr_box *usable = &output->usable_area;
	wlr_scene_rect_set_size(shell.ordinary_backdrop,
		usable->width > 0 ? usable->width : output->width,
		usable->height > 0 ? usable->height : output->height);
	wlr_scene_node_set_position(&shell.ordinary_backdrop->node,
		output->lx + usable->x, output->ly + usable->y);
	wlr_scene_node_lower_to_bottom(&shell.ordinary_backdrop->node);
}
/* The Home screen (the Rust client's always-mapped Layer::Bottom surface,
 * see nix/rust-shell-client/src/main.rs's HomeSurface) sits directly above
 * layers.shell_background (the wallpaper) and directly below
 * layers.tiling/fullscreen in Sway's fixed scene order -- the same shelf
 * ordinary_backdrop_sync describes. The overview's own canvas
 * (shell.canvas, in root->layers.shell_overlay, above every output layer)
 * is deliberately transparent so a person sees their wallpaper behind the
 * cards; before Home existed that transparency only ever revealed the
 * wallpaper. Now it also reveals Home, whose grid tiles and dock paint over
 * the deck and the "Swipe up for apps" hint -- the bleed-through fixed by
 * openspec/changes/fix-overview-home-bleed-through. Hide the whole
 * shell_bottom layer while the overview is active (mirrors this file's own
 * shell.deck/ordinary_backdrop enable pairing) and restore it once
 * restore() hands the screen back; a fullscreen application already
 * occludes Home by ordinary opaque stacking, so this only needs to handle
 * the overview's transparent case. Disabling the layer tree, rather than
 * asking the Rust client to unmap or repaint transparently, costs nothing
 * more than a scene-graph flag flip with no client round trip, no buffer
 * churn, and no risk of a black frame from a freshly reattached surface. */
static void home_layer_sync(struct sway_output *output) {
	if (!output || !output->layers.shell_bottom)
		return;
	wlr_scene_node_set_enabled(&output->layers.shell_bottom->node, !shell.active);
}
static void ordinary_sync_usable(struct sway_output *output, bool commit) {
	ordinary_backdrop_sync(output);
	if (shell.ordinary_usable_valid &&
		wlr_box_equal(&shell.ordinary_usable, &output->usable_area))
		return;
	shell.ordinary_usable = output->usable_area;
	shell.ordinary_usable_valid = true;
	bool changed = false;
	struct card *card;
	wl_list_for_each(card, &shell.cards, link)
		changed |= ordinary_resize(card->view, output);
	if (changed && commit)
		transaction_commit_dirty();
}
void card_shell_usable_area_changed(struct sway_output *output) {
	if (shell.initialized && shell.output == output)
		ordinary_sync_usable(output, false);
}
static void prepare_impl(struct sway_output *output) {
	if (shell.preparing || !ensure_ui(output))
		return;
	shell.preparing = true;
	ordinary_sync_usable(output, true);
	bool blocked =
		server.session_lock.lock || !output->enabled || launcher_mapped() || popup_mapped();
	if (blocked) {
		card_shell_reveal_cancel(&shell.reveal);
		if (shell.drawer_gesture.contacts)
			card_shell_drawer_cancel(&shell.drawer_gesture);
		if (shell.shade_gesture.contacts)
			card_shell_drawer_cancel(&shell.shade_gesture);
		if (shell.active)
			handle_result(cs_leave(&shell.policy));
		wlr_scene_node_set_enabled(&shell.ui->node, false);
		shell.preparing = false;
		return;
	}
	/* The new drawer overlays live cards. It takes new touches, while an
	 * already owned card gesture drains through its up without reaching it. */
	if (drawer_mapped()) {
		/* Both are children of root->layers.shell_overlay. The card tree is
		 * created later, so without this the drawer would paint underneath it. */
		wlr_scene_node_place_above(&output->layers.shell_overlay->node,
			&shell.ui->node);
		/* Do not cancel a bottom-edge escape gesture input_down just claimed
		 * on our behalf: the overlay's own unmap (requested via the "hide"
		 * route) is asynchronous, so drawer_mapped() can still read true for
		 * a frame or two after that gesture legitimately started. Only a
		 * contact/edge that predates the overlay mapping -- the actual stale
		 * state this cleanup exists for -- gets cancelled here. */
		if (!shell.overlay_escaping &&
			(shell.policy.contact || shell.policy.edge.tracking ||
			(shell.policy.mode == CS_EXPANDING && !shell.policy.expand_reversing)))
			handle_result(cs_cancel(&shell.policy));
		if (shell.drawer_gesture.contacts && !shell.reveal.active)
			card_shell_drawer_cancel(&shell.drawer_gesture);
		if (shell.shade_gesture.contacts && !shell.reveal.active)
			card_shell_drawer_cancel(&shell.shade_gesture);
	} else {
		shell.overlay_escaping = false;
	}
	wlr_scene_node_set_enabled(&shell.ui->node, true);
	struct cs_config cfg = cs_default_config(output->width, output->height);
	cfg.top_reserved = touch_first() ? fmax(0, output->usable_area.y) :
		fmax(56, output->usable_area.y);
	cfg.bottom_reserved =
		fmax(0, output->height - output->usable_area.y - output->usable_area.height);
	cfg.card_height = .72 * (cfg.height - cfg.top_reserved - cfg.bottom_reserved -
							 cfg.title_height - cfg.footer_height - 2 * cfg.inset);
	cfg.reduced_motion = getenv("SWAY_K230_CARD_REDUCED_MOTION") &&
						 strcmp(getenv("SWAY_K230_CARD_REDUCED_MOTION"), "1") == 0;
	cfg.touch_first_motion = touch_first();
	if (cfg.width != shell.policy.config.width || cfg.height != shell.policy.config.height ||
		cfg.top_reserved != shell.policy.config.top_reserved ||
		cfg.bottom_reserved != shell.policy.config.bottom_reserved ||
		cfg.reduced_motion != shell.policy.config.reduced_motion ||
		cfg.touch_first_motion != shell.policy.config.touch_first_motion) {
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
	card_shell_commit(view);
	snapshot();
	sway_log(SWAY_INFO, "K230_CARD_SHELL map id=%" PRIu64 " class=%d", c->id, c->content);
}
/* Sway's xdg_shell handle_commit runs card_shell_observe (above) once, at
 * registration, and then -- on the SAME commit and on every commit after --
 * its own view_update_size(): a client's own natural, pre-configure surface
 * geometry (whatever it committed on the mapping commit, before it has
 * reacted to any compositor-driven resize) is taken at face value and
 * written straight into a still-floating container's pending size. That
 * happens even when this file's `resize set 100 ppt 100 ppt` for_window
 * command already resized the container to the output's full usable area
 * moments earlier in the very same view_map(): the client's stale geometry
 * simply overwrites it again. A card that is not currently the one being
 * shown never earns a client repaint (wlr_scene only sends frame-done to
 * surfaces it actually composites), so it never commits again at its real
 * size and stays wrongly sized forever -- see docs/evidence/card-shell/
 * app-switch-swipe-frame-capture/README.md, "Finding 2". Re-asserting the
 * ordinary-maximized geometry after every commit, not only once at map
 * time, closes that race unconditionally: whatever the client's own commit
 * just did to the container's pending size, an ordinary-maximized card is
 * put back to the output's usable area before the next frame renders. */
void card_shell_commit(struct sway_view *view) {
	if (!enabled() || !live(view) || root->outputs->length != 1 ||
		!ensure_ui(root->outputs->items[0]))
		return;
	if (ordinary_resize(view, shell.output))
		transaction_commit_dirty();
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
		if (next && live(next->view)) {
			seat_set_focus_container(shell.seat, next->view->container);
			container_raise_floating(next->view->container);
		} else if (shell.output->current.active_workspace)
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
		drawer_mapped() ||
		popup_mapped() || wlr_seat_touch_num_points(seat->wlr_seat) > 0 ||
		seat->cursor->simulating_pointer_from_touch)
		return false;
	if (!snapshot() || !select_seat(seat))
		return false;
	handle_result(cs_enter(&shell.policy, focus_id(seat)));
	return shell.active;
}
static int hit_button(double x, double y) {
	if (touch_first())
		return 0;
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
	if (keyboard_gestures_enabled()) {
		unsigned action = kg_down(&shell.keyboard, id, x, y, event_ms,
			shell.output->height, keyboard_layer(shell.output) != NULL,
			shell.policy.mode == CS_DRAGGING,
			launcher_mapped() || drawer_mapped() || popup_at(x, y));
		if (keyboard_apply_action(action)) return true;
	}
	if (shell.policy.blocked_until_up) {
		struct cs_result r = cs_down(&shell.policy, id, x, y, event_ms);
		handle_result(r);
		return r.consumed;
	}
	if (shell.drawer_gesture.contacts) {
		card_shell_drawer_down(&shell.drawer_gesture, id, x, y);
		if (shell.drawer_gesture.cancelled)
			card_shell_reveal_cancel(&shell.reveal);
		return true;
	}
	if (shell.shade_gesture.contacts) {
		card_shell_drawer_down(&shell.shade_gesture, id, x, y);
		if (shell.shade_gesture.cancelled)
			card_shell_reveal_cancel(&shell.reveal);
		return true;
	}
	if (drawer_mapped()) {
		/* A bottom-edge swipe wins over any mapped Rust overlay -- Drawer,
		 * Shade, Settings and any of its sub-pages (theme chooser, Wi-Fi,
		 * password entry) alike, since drawer_mapped() does not distinguish
		 * which route the overlay is currently showing. This is the fix for
		 * "swiping up from the bottom of Settings does nothing": without
		 * it, every touch is ceded to the overlay before this compositor's
		 * own bottom-edge recognizer (cs_begin_entry/cs_edge_down, or the
		 * deck's own drawer-reveal below) ever runs. Claiming the same
		 * qualified zone with the same calls an app would use gives Home
		 * and the lateral quick-switch identical thresholds and feel
		 * whether an overlay is showing or not. Any other touch --
		 * including the overlay's own top-edge Close/Back controls -- is
		 * still ceded to the client exactly as before. */
		bool bottom_edge = shell.policy.config.bottom_reserved <= 0 &&
			y >= shell.policy.config.height - shell.policy.config.edge_band &&
			!shell.button_down && !shell.policy.contact && !shell.policy.edge.tracking &&
			wlr_seat_touch_num_points(seat->wlr_seat) == 0 &&
			!seat->cursor->simulating_pointer_from_touch;
		if (bottom_edge && touch_first() && shell.active) {
			/* Same as the deck's own "continue pulling up reveals the
			 * drawer" gesture a few lines below: card shell is already
			 * engaged (an app or the deck itself is under the overlay), so
			 * the bottom edge continues into the drawer, not a fresh app
			 * entry. */
			if (shell.policy.mode == CS_EXPANDING)
				handle_result(cs_cancel(&shell.policy));
			card_shell_drawer_down(&shell.drawer_gesture, id, x, y);
			shell.overlay_escaping = true;
			if (!card_shell_launch_surface("hide"))
				sway_log(SWAY_INFO, "K230_CARD_SHELL overlay hide helper unavailable");
			if (card_shell_reveal_enabled() &&
				!card_shell_reveal_begin(&shell.reveal, "drawer"))
				sway_log(SWAY_INFO, "K230_CARD_SHELL drawer reveal unavailable; deck retained");
			return true;
		}
		if (bottom_edge && !shell.active) {
			struct cs_result r = touch_first() ?
				cs_begin_entry(&shell.policy, id, x, y, event_ms, focus_id(seat)) :
				cs_edge_down(&shell.policy, id, x, y, event_ms);
			if (r.consumed) {
				shell.overlay_escaping = true;
				if (!card_shell_launch_surface("hide"))
					sway_log(SWAY_INFO, "K230_CARD_SHELL overlay hide helper unavailable");
				select_seat(seat);
				handle_result(r);
				return true;
			}
		}
		return false;
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
	if (touch_first() && y >= 0 && y < shell.policy.config.edge_band) {
		if (shell.policy.mode == CS_EXPANDING)
			handle_result(cs_cancel(&shell.policy));
		card_shell_drawer_down(&shell.shade_gesture, id, x, y);
		if (card_shell_reveal_enabled() &&
			!card_shell_reveal_begin(&shell.reveal, "shade"))
			sway_log(SWAY_INFO, "K230_CARD_SHELL shade reveal unavailable; scene retained");
		return true;
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
	if (touch_first() && shell.active &&
		y >= shell.policy.config.height - shell.policy.config.bottom_reserved -
			shell.policy.config.footer_height) {
		if (shell.policy.mode == CS_EXPANDING)
			handle_result(cs_cancel(&shell.policy));
		card_shell_drawer_down(&shell.drawer_gesture, id, x, y);
		if (card_shell_reveal_enabled() &&
			!card_shell_reveal_begin(&shell.reveal, "drawer"))
			sway_log(SWAY_INFO, "K230_CARD_SHELL drawer reveal unavailable; deck retained");
		return true;
	}
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
	struct cs_result r = touch_first() ?
		cs_begin_entry(&shell.policy, id, x, y, event_ms, focus_id(seat)) :
		cs_edge_down(&shell.policy, id, x, y, event_ms);
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
	if (keyboard_gestures_enabled() &&
		keyboard_apply_action(kg_motion(&shell.keyboard, id, x, y, event_ms)))
		return true;
	/* Reveal progress spans the actual Rust panel travel (drawer 81%, shade
	 * 65%). The separate entry_distance is only a release decision threshold;
	 * using a shorter travel here amplifies movement under the finger. */
	if (shell.drawer_gesture.contacts) {
		card_shell_drawer_motion(&shell.drawer_gesture, id, x, y,
			shell.policy.config.entry_distance);
		if (id == shell.drawer_gesture.owner && shell.reveal.active)
			card_shell_reveal_update(&shell.reveal,
				card_shell_reveal_progress(&shell.drawer_gesture, x, y,
					shell.policy.config.height * .81, false));
		return true;
	}
	if (shell.shade_gesture.contacts) {
		card_shell_shade_motion(&shell.shade_gesture, id, x, y,
			shell.policy.config.entry_distance);
		if (id == shell.shade_gesture.owner && shell.reveal.active)
			card_shell_reveal_update(&shell.reveal,
				card_shell_reveal_progress(&shell.shade_gesture, x, y,
					shell.policy.config.height * .65, true));
		return true;
	}
	if (shell.button_down) {
		if (id == shell.button_contact &&
			hypot(x - shell.button_x, y - shell.button_y) > shell.policy.config.tap_slop)
			shell.pressed_button = 0;
		chrome();
		return true;
	}
	uint64_t policy_start = card_bench_input_stage_begin();
	struct cs_result r = shell.policy.mode == CS_ENTERING
							 ? cs_entry_motion(&shell.policy, id, x, y, event_ms) :
							 shell.policy.mode == CS_NORMAL
							 ? cs_edge_motion(&shell.policy, id, x, y, event_ms, focus_id(seat))
							 : cs_motion(&shell.policy, id, x, y, event_ms);
	card_bench_input_stage_end(CARD_BENCH_POLICY, policy_start);
	handle_result(r);
	return r.consumed;
}
static bool input_up(struct sway_seat *seat, int32_t id, uint64_t event_ms) {
	if (!shell.initialized)
		return false;
	if (keyboard_gestures_enabled() &&
		keyboard_apply_action(kg_up(&shell.keyboard, id, event_ms)))
		return true;
	if (shell.drawer_gesture.contacts) {
		bool launch = card_shell_drawer_up(&shell.drawer_gesture, id);
		if (card_shell_reveal_enabled()) {
			if (shell.reveal.active && !card_shell_reveal_finish(&shell.reveal, launch))
				sway_log(SWAY_INFO, "K230_CARD_SHELL drawer reveal failed; deck retained");
		} else if (launch && !drawer_mapped() && !card_shell_launch_surface("drawer"))
			sway_log(SWAY_INFO, "K230_CARD_SHELL drawer helper unavailable; deck retained");
		return true;
	}
	if (shell.shade_gesture.contacts) {
		bool launch = card_shell_drawer_up(&shell.shade_gesture, id);
		if (card_shell_reveal_enabled()) {
			if (shell.reveal.active && !card_shell_reveal_finish(&shell.reveal, launch))
				sway_log(SWAY_INFO, "K230_CARD_SHELL shade reveal failed; scene retained");
		} else if (launch && !drawer_mapped() && !card_shell_launch_surface("shade"))
			sway_log(SWAY_INFO, "K230_CARD_SHELL shade helper unavailable; scene retained");
		return true;
	}
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
	struct cs_result r = shell.policy.mode == CS_ENTERING ?
							 cs_entry_up_at(&shell.policy, id, event_ms) :
							 shell.policy.mode == CS_NORMAL && !shell.policy.blocked_until_up
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
	card_shell_reveal_cancel(&shell.reveal);
	bool keyboard_owned = shell.keyboard.owned_count || shell.keyboard.overflow_contacts;
	unsigned keyboard_cancel = kg_end_stream(&shell.keyboard,
		keyboard_layer(shell.output) != NULL);
	if (keyboard_cancel & KG_HIDE) keyboard_signal("hide");
	if (keyboard_cancel & KG_DIRTY) keyboard_refresh();
	bool consumed = shell.button_down || shell.drawer_gesture.contacts || shell.shade_gesture.contacts ||
			keyboard_cancel != KG_NONE || keyboard_owned ||
			shell.policy.contact || shell.policy.edge.tracking ||
					shell.policy.blocked_until_up || shell.policy.mode == CS_EXPANDING ||
					shell.policy.mode == CS_ENTERING;
	memset(&shell.drawer_gesture, 0, sizeof(shell.drawer_gesture));
	memset(&shell.shade_gesture, 0, sizeof(shell.shade_gesture));
	shell.button_down = false;
	shell.pressed_button = 0;
	shell.overlay_escaping = false;
	handle_result(cs_stream_cancel(&shell.policy));
	if (shell.ui)
		chrome();
	return consumed;
}
bool card_shell_down(struct sway_seat *seat, struct wlr_touch *touch, int32_t id, double x, double y, uint32_t time_msec) {
	bool consumed = input_down(seat, id, x, y, event_time_ms(time_msec));
	/* An edge contact forwarded to an app cannot later be recaptured by the
	 * keyboard chord. Only card/drawer-owned first contacts are eligible. */
	if (!consumed && shell.keyboard.mode == KG_CHORD && shell.keyboard.first == id)
		kg_cancel(&shell.keyboard);
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
/* Self-evident diagnosis for "the wallpaper is not visible": lists every
 * scene node this file itself creates that can sit at or above the
 * wallpaper's own background layer (layers.shell_background), with the
 * facts that decide whether each one currently covers it. `journalctl -u
 * shell` shows the resulting K230_CARD_SHELL_DEBUG_SCENE line; the IPC
 * reply carries the same text for a synchronous read over `swaymsg`. Never
 * reads or writes anything outside this process's own scene-graph state --
 * a read-only probe, not a scene mutation. */
static void rect_summary(char *out, size_t cap, const char *name, struct wlr_scene_rect *rect) {
	if (!rect) {
		snprintf(out, cap, "%s=absent", name);
		return;
	}
	snprintf(out, cap,
		"%s enabled=%d pos=%d,%d size=%dx%d rgba=%.3f,%.3f,%.3f,%.3f",
		name, rect->node.enabled, rect->node.x, rect->node.y, rect->width, rect->height,
		(double)rect->color[0], (double)rect->color[1], (double)rect->color[2],
		(double)rect->color[3]);
}
static char *debug_scene_text(void) {
	char canvas[160], ordinary[160], gradient[96];
	rect_summary(canvas, sizeof(canvas), "canvas", shell.canvas);
	rect_summary(ordinary, sizeof(ordinary), "ordinary_backdrop", shell.ordinary_backdrop);
	snprintf(gradient, sizeof(gradient), "canvas_gradient enabled=%d",
		shell.canvas_gradient ? shell.canvas_gradient->node.enabled : -1);
	unsigned ordinary_maximized_cards = 0;
	struct card *c;
	wl_list_for_each(c, &shell.cards, link)
		if (c->view && c->view->container && c->view->container->card_shell_ordinary_maximized)
			ordinary_maximized_cards++;
	size_t capacity = 512;
	char *text = malloc(capacity);
	if (!text)
		return NULL;
	int home_enabled = shell.output && shell.output->layers.shell_bottom ?
		shell.output->layers.shell_bottom->node.enabled : -1;
	int written = snprintf(text, capacity,
		"K230_CARD_SHELL_DEBUG_SCENE active=%d deck_enabled=%d %s %s %s "
		"ordinary_maximized_cards=%u appearance_enabled=%d appearance_wallpaper=%d "
		"appearance_canvas_authored=%d home_enabled=%d",
		shell.active, shell.deck ? shell.deck->node.enabled : -1,
		canvas, gradient, ordinary,
		ordinary_maximized_cards, shell.appearance_enabled,
		shell.appearance_enabled ? shell.appearance.wallpaper : -1,
		shell.appearance_enabled ? shell.appearance.canvas_authored : -1,
		home_enabled);
	if (written < 0) {
		free(text);
		return NULL;
	}
	return text;
}
struct cmd_results *cmd_card_shell(int argc, char **argv) {
	if (!enabled() || config->reading)
		return cmd_results_new(CMD_FAILURE, "card shell is disabled");
	if (argc == 1 && strcmp(argv[0], "debug-scene") == 0) {
		char *text = debug_scene_text();
		if (!text)
			return cmd_results_new(CMD_FAILURE, "debug-scene formatting failed");
		sway_log(SWAY_INFO, "%s", text);
		struct cmd_results *result = cmd_results_new(CMD_SUCCESS, "%s", text);
		free(text);
		return result;
	}
	if (argc == 1 && strcmp(argv[0], "ordinary") == 0) {
		struct sway_container *con = config->handler_context.container;
		if (!con || !con->view)
			return cmd_results_new(CMD_INVALID, "ordinary requires an app container");
		const char *app_id = view_get_app_id(con->view);
		if (!app_id || strcmp(app_id, "k230-video-software") == 0 ||
			strcmp(app_id, "k230-video-mvx") == 0 ||
			(con->view->impl->wants_floating &&
			con->view->impl->wants_floating(con->view)))
			return cmd_results_new(CMD_FAILURE, "video and transient views stay unmarked");
		con->card_shell_ordinary_maximized = true;
		return cmd_results_new(CMD_SUCCESS, NULL);
	}
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

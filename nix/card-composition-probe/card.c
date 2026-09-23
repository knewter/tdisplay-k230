/* Opt-in, two-app capability probe. Not part of normal Sway policy.
 *
 * Each mirror is a real wlr_scene_surface, not a raw saved buffer: wlroots
 * owns every surface commit, acquire/release synchronization, buffer lock,
 * damage, frame pacing and presentation sample. The original content scene
 * supplies clipping, stacking and geometry. All mirrors are scaled together
 * before rendering. A 16ms discovery timer handles newly created subsurfaces
 * even when their original disabled scene does not schedule an output frame.
 */
#include "log.h"
#include "sway/commands.h"
#include "sway/desktop/transaction.h"
#include "sway/input/cursor.h"
#include "sway/input/input-manager.h"
#include "sway/input/seat.h"
#include "sway/k230_card.h"
#include "sway/k230_card_model.h"
#include "sway/output.h"
#include "sway/server.h"
#include "sway/tree/root.h"
#include "sway/tree/view.h"
#include "sway/tree/workspace.h"
#include <drm_fourcc.h>
#include <inttypes.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <wlr/render/pixman.h>
#include <wlr/types/wlr_buffer.h>
#include <wlr/types/wlr_compositor.h>
#include <wlr/types/wlr_output.h>
#include <wlr/types/wlr_scene.h>

struct card;
struct mirror {
	struct wl_list link;
	struct card *card;
	struct wlr_scene_buffer *source, *copy;
	struct wl_listener source_destroy, copy_destroy, sample, commit;
	uint32_t seq;
	bool seen, format_valid;
};
struct card {
	struct sway_view *view;
	struct wlr_scene_tree *tree;
	struct wl_list mirrors;
	bool original_enabled;
	double scale, x, y, width, height;
};
static struct {
	struct card cards[2];
	struct wlr_scene_tree *tree;
	struct sway_output *output;
	struct sway_seat *seat;
	struct sway_node *focus;
	struct wl_listener focus_destroy, output_destroy, seat_destroy;
	struct wl_event_source *timer;
	struct card_gesture gesture;
	bool initialized, active, preparing;
	unsigned held; /* swallowed contacts remain swallowed after abort */
	int closing, fail_mirror_after;
	int64_t close_deadline;
	unsigned commits, samples, frames, presentations, ticks;
} probe;

static int64_t milliseconds(void) {
	struct timespec now;
	clock_gettime(CLOCK_MONOTONIC, &now);
	return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}
static bool live(struct sway_view *v) {
	return v && v->surface && v->surface->mapped && v->container && !v->container->node.destroying;
}
static void focus_destroy(struct wl_listener *listener, void *data) {
	wl_list_remove(&probe.focus_destroy.link);
	probe.focus = NULL;
}
static void mirror_free(struct mirror *m) {
	wl_list_remove(&m->source_destroy.link);
	wl_list_remove(&m->commit.link);
	if (m->copy) {
		wl_list_remove(&m->sample.link);
		wl_list_remove(&m->copy_destroy.link);
		wlr_scene_node_destroy(&m->copy->node);
	}
	wl_list_remove(&m->link);
	sway_log(SWAY_INFO, "K230_CARD mirror-release card=%ld", m->card - probe.cards);
	free(m);
}
static void source_destroy(struct wl_listener *listener, void *data) {
	struct mirror *m = wl_container_of(listener, m, source_destroy);
	mirror_free(m);
}
static void copy_destroy(struct wl_listener *listener, void *data) {
	struct mirror *m = wl_container_of(listener, m, copy_destroy);
	wl_list_remove(&m->sample.link);
	wl_list_remove(&m->copy_destroy.link);
	m->copy = NULL;
}
static bool observe_format(struct wlr_surface *surface, int card, bool log);
static void mirror_commit(struct wl_listener *listener, void *data) {
	struct mirror *m = wl_container_of(listener, m, commit);
	struct wlr_surface *surface = data;
	m->seq = surface->current.seq;
	m->format_valid = observe_format(surface, m->card - probe.cards, false);
	probe.commits++;
}
static void mirror_sample(struct wl_listener *listener, void *data) {
	struct mirror *m = wl_container_of(listener, m, sample);
	struct wlr_scene_output_sample_event *event = data;
	/* wlroots' own listener records actual textured/scanned-out feedback. */
	if (probe.active && event->output == probe.output->scene_output && m->copy) {
		probe.samples++;
	}
}
static void restore_focus(struct sway_view *selected) {
	if (!probe.seat || server.session_lock.lock)
		return;
	if (live(selected)) {
		seat_set_focus_container(probe.seat, selected->container);
	} else if (probe.focus && !probe.focus->destroying) {
		seat_set_focus(probe.seat, probe.focus);
	} else {
		struct sway_view *v = live(probe.cards[0].view) ? probe.cards[0].view : probe.cards[1].view;
		if (live(v))
			seat_set_focus_container(probe.seat, v->container);
		else if (probe.output && probe.output->current.active_workspace) {
			seat_set_focus_workspace(probe.seat, probe.output->current.active_workspace);
		}
	}
	transaction_commit_dirty();
	sway_log(SWAY_INFO, "K230_CARD focus-restored keyboard=seat-path");
}
static void leave(const char *reason, struct sway_view *selected) {
	if (!probe.active && !probe.tree)
		return;
	probe.active = false;
	probe.gesture.down = false;
	probe.closing = -1;
	if (probe.timer) {
		wl_event_source_remove(probe.timer);
		probe.timer = NULL;
	}
	for (int i = 0; i < 2; i++) {
		struct card *c = &probe.cards[i];
		struct mirror *m, *tmp;
		wl_list_for_each_safe(m, tmp, &c->mirrors, link) mirror_free(m);
		if (live(c->view))
			wlr_scene_node_set_enabled(&c->view->scene_tree->node, c->original_enabled);
		c->tree = NULL;
	}
	if (probe.tree) {
		wlr_scene_node_destroy(&probe.tree->node);
		probe.tree = NULL;
	}
	restore_focus(selected);
	if (probe.focus) {
		wl_list_remove(&probe.focus_destroy.link);
		probe.focus = NULL;
	}
	if (probe.seat) {
		wl_list_remove(&probe.seat_destroy.link);
		probe.seat = NULL;
	}
	if (probe.output) {
		wl_list_remove(&probe.output_destroy.link);
		probe.output = NULL;
	}
	sway_log(SWAY_INFO,
			 "K230_CARD restored reason=%s commits=%u samples=%u frame-done=%u output-presented=%u",
			 reason, probe.commits, probe.samples, probe.frames, probe.presentations);
}
static void card_seat_destroy(struct wl_listener *listener, void *data) {
	wl_list_remove(&probe.seat_destroy.link);
	probe.seat = NULL;
	probe.held = 0;
	leave("seat-destroy", NULL);
}
static void card_output_destroy(struct wl_listener *listener, void *data) {
	leave("output-leave", NULL);
}
static bool accepts_no_input(struct wlr_scene_buffer *buffer, double *x, double *y) {
	return false; /* Input belongs to the compositor's card handler. */
}
static bool observe_format(struct wlr_surface *surface, int card, bool log) {
	if (!surface->buffer)
		return true;
	struct wlr_buffer *source = surface->buffer->source;
	struct wlr_shm_attributes attr;
	if (!source || !wlr_buffer_get_shm(source, &attr)) {
		sway_log(SWAY_ERROR, "K230_CARD unsupported-buffer card=%d expected=shm", card);
		return false;
	}
	if (attr.format != DRM_FORMAT_XRGB8888 && attr.format != DRM_FORMAT_ARGB8888 &&
		attr.format != DRM_FORMAT_RGB565) {
		sway_log(SWAY_ERROR, "K230_CARD unsupported-format card=%d fourcc=%08x", card, attr.format);
		return false;
	}
	if (log)
		sway_log(SWAY_INFO,
				 "K230_CARD buffer-reference card=%d format=%08x width=%d height=%d stride=%d "
				 "owner=wlroots-scene-surface",
				 card, attr.format, attr.width, attr.height, attr.stride);
	return true;
}
static struct mirror *get_mirror(struct card *c, struct wlr_scene_buffer *source) {
	struct mirror *m;
	wl_list_for_each(m, &c->mirrors, link) if (m->source == source) return m;
	struct wlr_scene_surface *surface = wlr_scene_surface_try_from_buffer(source);
	if (!surface || !observe_format(surface->surface, c - probe.cards, false))
		return NULL;
	if (probe.fail_mirror_after == 0) {
		probe.fail_mirror_after = -1;
		return NULL;
	}
	if (probe.fail_mirror_after > 0)
		probe.fail_mirror_after--;
	m = calloc(1, sizeof(*m));
	if (!m)
		return NULL;
	struct wlr_scene_surface *copy = wlr_scene_surface_create(c->tree, surface->surface);
	if (!copy) {
		free(m);
		return NULL;
	}
	observe_format(surface->surface, c - probe.cards, true);
	m->format_valid = true;
	m->card = c;
	m->source = source;
	m->copy = copy->buffer;
	m->copy->point_accepts_input = accepts_no_input;
	m->source_destroy.notify = source_destroy;
	wl_signal_add(&source->node.events.destroy, &m->source_destroy);
	m->copy_destroy.notify = copy_destroy;
	wl_signal_add(&m->copy->node.events.destroy, &m->copy_destroy);
	m->sample.notify = mirror_sample;
	wl_signal_add(&m->copy->events.output_sample, &m->sample);
	m->commit.notify = mirror_commit;
	wl_signal_add(&surface->surface->events.commit, &m->commit);
	wl_list_insert(c->mirrors.prev, &m->link);
	return m;
}
static bool sync_node(struct card *c, struct wlr_scene_node *node, int x, int y) {
	if (!node->enabled)
		return true;
	x += node->x;
	y += node->y;
	if (node->type == WLR_SCENE_NODE_TREE) {
		struct wlr_scene_tree *tree = wlr_scene_tree_from_node(node);
		struct wlr_scene_node *child;
		wl_list_for_each(child, &tree->children, link) if (!sync_node(c, child, x, y)) return false;
		return true;
	}
	/* content_tree consists of surface buffers; reject unfamiliar node types. */
	if (node->type != WLR_SCENE_NODE_BUFFER)
		return false;
	struct wlr_scene_buffer *source = wlr_scene_buffer_from_node(node);
	if (!source->buffer)
		return true;
	struct mirror *m = get_mirror(c, source);
	if (!m || !m->copy || !m->format_valid)
		return false;
	m->seen = true;
	struct wlr_scene_buffer *copy = m->copy;
	int width = source->dst_width, height = source->dst_height;
	if (!width || !height)
		return false;
	int left = lround(x * c->scale), top = lround(y * c->scale);
	int right = lround((x + width) * c->scale), bottom = lround((y + height) * c->scale);
	if (right <= left || bottom <= top)
		return false;
	wlr_scene_buffer_set_source_box(copy, &source->src_box);
	wlr_scene_buffer_set_dest_size(copy, right - left, bottom - top);
	wlr_scene_buffer_set_transform(copy, source->transform);
	wlr_scene_buffer_set_opacity(copy, source->opacity);
	wlr_scene_buffer_set_filter_mode(copy, WLR_SCALE_FILTER_BILINEAR);
	wlr_scene_buffer_set_transfer_function(copy, source->transfer_function);
	wlr_scene_buffer_set_primaries(copy, source->primaries);
	wlr_scene_buffer_set_color_encoding(copy, source->color_encoding);
	wlr_scene_buffer_set_color_range(copy, source->color_range);
	/* Conservative empty opacity region avoids unscaled occlusion claims. */
	pixman_region32_t empty;
	pixman_region32_init(&empty);
	wlr_scene_buffer_set_opaque_region(copy, &empty);
	pixman_region32_fini(&empty);
	wlr_scene_node_set_position(&copy->node, left, top);
	wlr_scene_node_raise_to_top(&copy->node);
	return true;
}
static bool sync_cards(void) {
	for (int i = 0; i < 2; i++) {
		struct card *c = &probe.cards[i];
		if (!live(c->view) || card_allowlist(view_get_app_id(c->view)) != i ||
			c->view->container->current.workspace != probe.output->current.active_workspace)
			return false;
		int width = c->view->geometry.width, height = c->view->geometry.height;
		if (width <= 0 || height <= 0)
			return false;
		c->scale =
			fmin((probe.output->width - 48.0) / width, (probe.output->height * .38) / height);
		c->width = width * c->scale;
		c->height = height * c->scale;
		c->x = probe.output->lx + (probe.output->width - c->width) / 2;
		c->y = probe.output->ly + 48 + i * probe.output->height * .44;
		struct mirror *m, *tmp;
		wl_list_for_each(m, &c->mirrors, link) m->seen = false;
		struct wlr_scene_node *child;
		wl_list_for_each(child, &c->view->content_tree->children, link) {
			if (!sync_node(c, child, 0, 0))
				return false;
		}
		wl_list_for_each_safe(m, tmp, &c->mirrors, link) if (!m->seen) mirror_free(m);
		if (wl_list_empty(&c->mirrors))
			return false;
		double dx = 0, dy = 0;
		if (probe.gesture.down && probe.gesture.selected == i) {
			dx = probe.gesture.dx;
			dy = probe.gesture.dy;
		}
		wlr_scene_node_set_position(&c->tree->node, lround(c->x + dx), lround(c->y + dy));
	}
	return true;
}
void k230_card_prepare(struct sway_output *output) {
	if (!probe.active || probe.preparing || output != probe.output)
		return;
	probe.preparing = true;
	if (server.session_lock.lock || root->outputs->length != 1 || !output->enabled ||
		!sync_cards()) {
		leave("unsafe-scene-or-allocation", NULL);
	} else {
		for (int i = 0; i < 2; i++)
			wlr_scene_node_set_enabled(&probe.cards[i].view->scene_tree->node, false);
	}
	probe.preparing = false;
}
static int tick(void *data) {
	if (!probe.active)
		return 0;
	k230_card_prepare(probe.output);
	if (!probe.active)
		return 0;
	if (probe.closing >= 0 && milliseconds() >= probe.close_deadline) {
		sway_log(SWAY_INFO, "K230_CARD close-refused card=%d basis=still-mapped-after-1500ms",
				 probe.closing);
		leave("close-refused", NULL);
		return 0;
	}
	if (++probe.ticks % 60 == 0)
		sway_log(SWAY_INFO,
				 "K230_CARD live commits=%u sampled=%u frame-done=%u output-presented=%u",
				 probe.commits, probe.samples, probe.frames, probe.presentations);
	wlr_output_schedule_frame(probe.output->wlr_output);
	wl_event_source_timer_update(probe.timer, 16);
	return 0;
}
static bool enter(struct sway_seat *seat) {
	if (probe.active || !live(probe.cards[0].view) || !live(probe.cards[1].view) ||
		root->outputs->length != 1 || server.session_lock.lock ||
		!wlr_renderer_is_pixman(server.renderer) || wlr_seat_touch_num_points(seat->wlr_seat) > 0 ||
		seat->cursor->simulating_pointer_from_touch)
		return false;
	probe.seat = seat;
	probe.seat_destroy.notify = card_seat_destroy;
	wl_signal_add(&seat->wlr_seat->events.destroy, &probe.seat_destroy);
	probe.output = root->outputs->items[0];
	probe.output_destroy.notify = card_output_destroy;
	wl_signal_add(&probe.output->node.events.destroy, &probe.output_destroy);
	probe.focus = seat_get_focus(seat);
	if (probe.focus) {
		probe.focus_destroy.notify = focus_destroy;
		wl_signal_add(&probe.focus->events.destroy, &probe.focus_destroy);
	}
	probe.closing = -1;
	probe.gesture = (struct card_gesture){0};
	for (int i = 0; i < 2; i++)
		probe.cards[i].original_enabled = probe.cards[i].view->scene_tree->node.enabled;
	probe.tree = wlr_scene_tree_create(root->layers.shell_overlay);
	/* Set active before any allocation so cleanup always unwinds listeners. */
	probe.active = true;
	if (!probe.tree) {
		leave("allocation", NULL);
		return false;
	}
	wlr_scene_node_set_enabled(&probe.tree->node, false);
	for (int i = 0; i < 2; i++) {
		probe.cards[i].tree = wlr_scene_tree_create(probe.tree);
		if (!probe.cards[i].tree) {
			leave("allocation", NULL);
			return false;
		}
	}
	probe.timer = wl_event_loop_add_timer(server.wl_event_loop, tick, NULL);
	if (!probe.timer || !sync_cards()) {
		leave("scene-setup", NULL);
		return false;
	}
	/* Both complete before hiding either original. */
	for (int i = 0; i < 2; i++)
		wlr_scene_node_set_enabled(&probe.cards[i].view->scene_tree->node, false);
	wlr_scene_node_set_enabled(&probe.tree->node, true);
	wl_event_source_timer_update(probe.timer, 16);
	sway_log(SWAY_INFO, "K230_CARD attached cards=2 renderer=pixman source=live-scene-surfaces");
	return true;
}
void k230_card_observe(struct sway_view *view) {
	if (!card_opted_in(getenv("SWAY_K230_CARD_COMPOSITION_PROBE")))
		return;
	if (!probe.initialized) {
		for (int i = 0; i < 2; i++)
			wl_list_init(&probe.cards[i].mirrors);
		probe.closing = -1;
		probe.fail_mirror_after = -1;
		probe.initialized = true;
	}
	int i = card_allowlist(view_get_app_id(view));
	if (i < 0 || !live(view))
		return;
	if (probe.cards[i].view && probe.cards[i].view != view)
		return;
	if (!probe.cards[i].view) {
		probe.cards[i].view = view;
		sway_log(SWAY_INFO, "K230_CARD map card=%d container=%zu", i, view->container->node.id);
	}
	/* Entry is deliberate: touch the bottom 48 logical pixels after both map. */
}
void k230_card_unmap(struct sway_view *view) {
	if (!probe.initialized)
		return;
	for (int i = 0; i < 2; i++)
		if (probe.cards[i].view == view) {
			bool closing = probe.closing == i;
			if (probe.focus == &view->container->node) {
				wl_list_remove(&probe.focus_destroy.link);
				probe.focus = NULL;
			}
			/* Restore visibility before unmapping; exclude dying view from focus. */
			if (probe.active)
				wlr_scene_node_set_enabled(&view->scene_tree->node,
										   probe.cards[i].original_enabled);
			probe.cards[i].view = NULL;
			sway_log(SWAY_INFO, "K230_CARD %s card=%d", closing ? "app-exit" : "unmap", i);
			leave(closing ? "app-exit" : "unmap", NULL);
		}
}
void k230_card_frame(struct wlr_scene_buffer *buffer) {
	if (!probe.active)
		return;
	for (int i = 0; i < 2; i++) {
		struct mirror *m;
		wl_list_for_each(m, &probe.cards[i].mirrors, link) if (m->copy == buffer) probe.frames++;
	}
}
void k230_card_present(struct sway_output *output, bool presented) {
	if (probe.active && output == probe.output && presented)
		probe.presentations++;
}
bool k230_card_down(struct sway_seat *seat, int32_t id, double x, double y) {
	if (!probe.initialized || server.session_lock.lock)
		return false;
	if (!probe.active) {
		if (probe.held) {
			probe.held++;
			return true;
		}
		if (root->outputs->length != 1)
			return false;
		struct sway_output *o = root->outputs->items[0];
		if (x < o->lx || x >= o->lx + o->width || y < o->ly + o->height - 48 ||
			y >= o->ly + o->height || !enter(seat))
			return false;
		probe.held = 1;
		card_down(&probe.gesture, id, -1, x, y);
		return true;
	}
	probe.held++;
	if (seat != probe.seat || probe.gesture.down) {
		leave("second-contact", NULL);
		return true;
	}
	int selected = -1;
	for (int i = 0; i < 2; i++) {
		struct card *c = &probe.cards[i];
		if (x >= c->x && x < c->x + c->width && y >= c->y && y < c->y + c->height)
			selected = i;
	}
	card_down(&probe.gesture, id, selected, x, y);
	sway_log(SWAY_INFO, "K230_CARD dragging card=%d contact=%d", selected, id);
	return true;
}
bool k230_card_motion(struct sway_seat *seat, int32_t id, double x, double y) {
	if (!probe.held)
		return false;
	if (probe.active && seat == probe.seat) {
		card_motion(&probe.gesture, id, x, y);
		k230_card_prepare(probe.output);
	}
	return true;
}
bool k230_card_up(struct sway_seat *seat, int32_t id) {
	if (!probe.held)
		return false;
	probe.held--;
	if (!probe.active || seat != probe.seat)
		return true;
	int selected = probe.gesture.selected;
	enum card_action action = card_up(&probe.gesture, id);
	if (action == CARD_SELECT) {
		sway_log(SWAY_INFO, "K230_CARD selected-expanded card=%d", selected);
		leave("selected-expanded", probe.cards[selected].view);
	} else if (action == CARD_CLOSE && probe.closing < 0) {
		probe.closing = selected;
		probe.close_deadline = milliseconds() + 1500;
		sway_log(SWAY_INFO, "K230_CARD dismissal-requested card=%d", selected);
		view_close(probe.cards[selected].view);
	} else
		k230_card_prepare(probe.output);
	return true;
}
bool k230_card_cancel(struct sway_seat *seat) {
	if (!probe.held && !probe.active)
		return false;
	probe.held = 0;
	leave("touch-cancel", NULL);
	return true;
}

/* Explicit injected-event entry for reproducible headless lifetime tests.
 * This is deliberately named and logged: it is not physical touch proof. */
struct cmd_results *cmd_k230_card_probe(int argc, char **argv) {
	if (!card_opted_in(getenv("SWAY_K230_CARD_COMPOSITION_PROBE")) || config->reading) {
		return cmd_results_new(CMD_FAILURE, "card probe is disabled");
	}
	struct sway_seat *seat = config->handler_context.seat;
	bool accepted = false;
	if (argc == 2 && strcmp(argv[0], "fail-mirror") == 0) {
		char *end;
		long n = strtol(argv[1], &end, 10);
		if (*end || n < 0 || n > 32 || probe.active)
			return cmd_results_new(CMD_INVALID, "invalid allocation fault");
		probe.fail_mirror_after = n;
		accepted = true;
	} else if (argc == 1 && strcmp(argv[0], "enter") == 0)
		accepted = enter(seat);
	else if (argc == 1 && strcmp(argv[0], "cancel") == 0)
		accepted = k230_card_cancel(seat);
	else if (argc == 2 && strcmp(argv[0], "up") == 0) {
		char *end;
		long id = strtol(argv[1], &end, 10);
		if (*end || id < 0 || id > INT32_MAX)
			return cmd_results_new(CMD_INVALID, "invalid contact");
		accepted = k230_card_up(seat, id);
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
		if (strcmp(argv[0], "down") == 0)
			accepted = k230_card_down(seat, id, x, y);
		else
			accepted = k230_card_motion(seat, id, x, y);
	} else
		return cmd_results_new(CMD_INVALID,
							   "expected enter|cancel|down ID X Y|motion ID X Y|up ID");
	sway_log(SWAY_INFO, "K230_CARD input=injected operation=%s accepted=%d", argv[0], accepted);
	return cmd_results_new(accepted ? CMD_SUCCESS : CMD_FAILURE,
						   accepted ? NULL : "card event rejected");
}

/* Explicit headless-only fixture: exercise the real input-manager/cursor/seat path. */
#include "sway/card_shell_test_input.h"
#include "sway/output.h"
#include "sway/server.h"
#include <errno.h>
#include <limits.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <wlr/backend.h>
#include <wlr/backend/headless.h>
#include <wlr/interfaces/wlr_touch.h>
#include <wlr/types/wlr_output.h>
static struct wlr_touch touch;
static bool initialized;
static const struct wlr_touch_impl impl = {.name = "card-shell-headless-test"};
void card_shell_test_input_finish(void) {
	if (initialized) {
		initialized = false;
		wlr_touch_finish(&touch);
	}
}
static bool contact(const char *text, int32_t *id) {
	char *end;
	errno = 0;
	long value = strtol(text, &end, 10);
	if (errno || !text[0] || *end || value < 0 || value > INT32_MAX)
		return false;
	*id = value;
	return true;
}
bool card_shell_test_input(struct sway_output *output, int argc, char **argv) {
	const char *env = getenv("SWAY_K230_CARD_TEST_INPUT");
	if (!env || strcmp(env, "1") || !output ||
		!wlr_backend_is_headless(output->wlr_output->backend) || argc < 1)
		return false;
	if ((argc == 1 || argc == 2) && !strcmp(argv[0], "init")) {
		const char *name = "Card shell headless fixture";
		if (argc == 2) {
			if (!strcmp(argv[1], "injected-device"))
				name = "K230 injected touchscreen";
			else if (!strcmp(argv[1], "physical-label-fixture"))
				name = "Card shell physical-label fixture";
			else
				return false;
		}
		if (!initialized) {
			wlr_touch_init(&touch, &impl, name);
			initialized = true;
			wl_signal_emit_mutable(&server.backend->events.new_input, &touch.base);
		}
		return true;
	}
	if (!initialized)
		return false;
	if (argc == 1 && !strcmp(argv[0], "remove")) {
		card_shell_test_input_finish();
		return true;
	}
	struct timespec stamp;
	clock_gettime(CLOCK_MONOTONIC, &stamp);
	uint32_t now = (uint64_t)stamp.tv_sec * 1000 + stamp.tv_nsec / 1000000;
	if (argc == 1 && !strcmp(argv[0], "cancel")) {
		struct wlr_touch_cancel_event event = {.touch = &touch, .time_msec = now, .touch_id = 0};
		wl_signal_emit_mutable(&touch.events.cancel, &event);
	} else if (argc == 2 && !strcmp(argv[0], "up")) {
		int32_t id;
		if (!contact(argv[1], &id))
			return false;
		struct wlr_touch_up_event event = {.touch = &touch, .time_msec = now, .touch_id = id};
		wl_signal_emit_mutable(&touch.events.up, &event);
	} else if (argc == 4 && (!strcmp(argv[0], "down") || !strcmp(argv[0], "motion"))) {
		int32_t id;
		if (!contact(argv[1], &id))
			return false;
		char *end;
		double x = strtod(argv[2], &end);
		if (*end || !isfinite(x) || x < 0 || x >= output->width)
			return false;
		double y = strtod(argv[3], &end);
		if (*end || !isfinite(y) || y < 0 || y >= output->height)
			return false;
		x /= output->width;
		y /= output->height;
		if (!strcmp(argv[0], "down")) {
			struct wlr_touch_down_event event = {
				.touch = &touch, .time_msec = now, .touch_id = id, .x = x, .y = y};
			wl_signal_emit_mutable(&touch.events.down, &event);
		} else {
			struct wlr_touch_motion_event event = {
				.touch = &touch, .time_msec = now, .touch_id = id, .x = x, .y = y};
			wl_signal_emit_mutable(&touch.events.motion, &event);
		}
	} else
		return false;
	wl_signal_emit_mutable(&touch.events.frame, NULL);
	return true;
}

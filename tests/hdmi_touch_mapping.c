#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <wayland-server-core.h>
#include <wlr/backend/headless.h>
#include <wlr/interfaces/wlr_touch.h>
#include <wlr/render/allocator.h>
#include <wlr/render/pixman.h>
#include <wlr/render/wlr_renderer.h>
#include <wlr/types/wlr_cursor.h>
#include <wlr/types/wlr_output_layout.h>

static double actual_x, actual_y;
static unsigned received;
static void on_down(struct wl_listener *listener, void *data) {
	(void)listener;
	struct wlr_touch_down_event *event = data;
	actual_x = event->x; actual_y = event->y; received++;
}
static void on_motion(struct wl_listener *listener, void *data) {
	(void)listener;
	struct wlr_touch_motion_event *event = data;
	actual_x = event->x; actual_y = event->y; received++;
}
int main(int argc, char **argv) {
	assert(argc == 8);
	int turn = atoi(argv[1]);
	double matrix[6];
	for (int i = 0; i < 6; i++) matrix[i] = strtod(argv[i + 2], NULL);
	struct wl_display *display = wl_display_create(); assert(display);
	struct wlr_backend *backend = wlr_headless_backend_create(wl_display_get_event_loop(display)); assert(backend);
	struct wlr_output *output = wlr_headless_add_output(backend, 1920, 1080); assert(output);
	struct wlr_renderer *renderer = wlr_pixman_renderer_create(); assert(renderer);
	struct wlr_allocator *allocator = wlr_allocator_autocreate(backend, renderer); assert(allocator);
	assert(wlr_output_init_render(output, allocator, renderer));
	struct wlr_output_state state; wlr_output_state_init(&state);
	wlr_output_state_set_transform(&state, turn);
	assert(wlr_output_commit_state(output, &state));
	wlr_output_state_finish(&state);
	struct wlr_output_layout *layout = wlr_output_layout_create(display); assert(layout);
	assert(wlr_output_layout_add_auto(layout, output));
	struct wlr_cursor *cursor = wlr_cursor_create(); assert(cursor);
	wlr_cursor_attach_output_layout(cursor, layout);
	struct wlr_touch touch;
	static const struct wlr_touch_impl impl = {.name = "fixture"};
	wlr_touch_init(&touch, &impl, "fixture");
	wlr_cursor_attach_input_device(cursor, &touch.base);
	wlr_cursor_map_input_to_output(cursor, &touch.base, output);
	struct wl_listener down = {.notify = on_down}, motion = {.notify = on_motion};
	wl_signal_add(&cursor->events.touch_down, &down);
	wl_signal_add(&cursor->events.touch_motion, &motion);
	const double points[][2] = {{0,0},{1,0},{0,1},{1,1},{.5,.5},{.2,.5},{.8,.5},{.5,.98},{.5,.3}};
	unsigned count = sizeof(points)/sizeof(points[0]);
	for (unsigned i = 0; i < count; i++) {
		double x = points[i][0], y = points[i][1];
		double calibrated_x = matrix[0]*x + matrix[1]*y + matrix[2];
		double calibrated_y = matrix[3]*x + matrix[4]*y + matrix[5];
		struct wlr_touch_down_event d = {.touch=&touch, .touch_id=1, .x=calibrated_x, .y=calibrated_y};
		wl_signal_emit_mutable(&touch.events.down, &d);
		assert(fabs(actual_x-x) < 1e-9 && fabs(actual_y-y) < 1e-9);
		struct wlr_touch_motion_event m = {.touch=&touch, .touch_id=1, .x=calibrated_x, .y=calibrated_y};
		wl_signal_emit_mutable(&touch.events.motion, &m);
		assert(fabs(actual_x-x) < 1e-9 && fabs(actual_y-y) < 1e-9);
		double lx, ly;
		wlr_cursor_absolute_to_layout_coords(cursor, &touch.base, actual_x, actual_y, &lx, &ly);
		int width, height; wlr_output_transformed_resolution(output, &width, &height);
		assert(fabs(lx - x*width) < 1e-9 && fabs(ly - y*height) < 1e-9);
	}
	assert(received == count*2);
	wl_list_remove(&down.link); wl_list_remove(&motion.link);
	wlr_cursor_destroy(cursor); wlr_touch_finish(&touch);
	wlr_output_layout_destroy(layout); wlr_backend_destroy(backend);
	wlr_allocator_destroy(allocator); wlr_renderer_destroy(renderer); wl_display_destroy(display);
	printf("PASS mapped-touch enum=%d points=%u down+motion=%u; corners and horizontal/vertical glass axes preserved\n", turn, count, received);
	return 0;
}

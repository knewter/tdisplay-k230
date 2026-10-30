/*
 * k230-life-wayland: optional Wayland continuation of the boot Game of Life
 * (openspec change the-boot-shows-a-computational-game-of-life, task 3.3).
 *
 * One layer-shell surface on the BACKGROUND layer, no exclusive zone, no
 * keyboard interactivity: it sits under the shell's own surfaces and can never
 * cover Apps, Keyboard, Windows/Home, System or recovery.  It opens no DRM
 * device, so it does not compete with the compositor for the panel.  Quit it
 * (SIGTERM, the layer surface closing, or --run-seconds) and the shell is
 * exactly as before.  A tap or click on a part of the background that no shell
 * surface covers drops a glider.
 *
 *   k230-life-wayland [--life-state P --life-instance P] [--seed N]
 *                     [--interval-ms N] [--rotate 0|90|270] [--report P]
 *                     [--run-seconds N]
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>

#include "life.h"
#include "wlr-layer-shell-unstable-v1-client-protocol.h"
#include "xdg-shell-client-protocol.h"

static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct wl_seat *seat;
static struct zwlr_layer_shell_v1 *layer_shell;
static struct wl_surface *surface;
static struct zwlr_layer_surface_v1 *layer_surface;
static struct wl_buffer *buffer;
static void *pixels;
static size_t map_size;
static uint32_t width, height;
static volatile sig_atomic_t quit;
static bool configured;
static bool frame_pending;
static int rotate = -1; /* -1 auto: 90 when landscape */
static unsigned scale = 1, off_x, off_y;
static struct life life;
static struct life_opts opts = { .interval_ms = 250, .seed = 0x4b323330u, .log_tag = "k230-life-wayland" };
static unsigned run_seconds, ticks;
static struct timespec started;

static void on_term(int s) { (void)s; quit = 1; }

static double now_ms(void) {
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

/* Map a grid cell to the top-left surface pixel of its scale x scale square. */
static void cell_origin(unsigned cx, unsigned cy, unsigned *px, unsigned *py) {
	if (rotate == 90) { /* grid x runs down the surface, grid y runs left-to-right */
		*px = off_x + (GOL_H - 1u - cy) * scale;
		*py = off_y + cx * scale;
	} else if (rotate == 270) {
		*px = off_x + cy * scale;
		*py = off_y + (GOL_W - 1u - cx) * scale;
	} else {
		*px = off_x + cx * scale;
		*py = off_y + cy * scale;
	}
}

static bool pixel_to_cell(double sx, double sy, unsigned *cx, unsigned *cy) {
	if (sx < off_x || sy < off_y) return false;
	unsigned u = (unsigned)(sx - off_x) / scale, v = (unsigned)(sy - off_y) / scale;
	unsigned gw = rotate ? GOL_H : GOL_W, gh = rotate ? GOL_W : GOL_H;
	if (u >= gw || v >= gh) return false;
	if (rotate == 90) { *cx = v; *cy = GOL_H - 1u - u; }
	else if (rotate == 270) { *cx = GOL_W - 1u - v; *cy = u; }
	else { *cx = u; *cy = v; }
	return true;
}

static void draw(void) {
	uint32_t *px = pixels;
	for (size_t i = 0; i < (size_t)width * height; i++) px[i] = 0xff000000u;
	for (unsigned cy = 0; cy < GOL_H; cy++)
		for (unsigned cx = 0; cx < GOL_W; cx++) {
			if (!gol_get(&life.st.grid, cx, cy)) continue;
			unsigned ox, oy;
			cell_origin(cx, cy, &ox, &oy);
			for (unsigned y = 0; y < scale && oy + y < height; y++)
				for (unsigned x = 0; x < scale && ox + x < width; x++)
					px[(size_t)(oy + y) * width + ox + x] = 0xff000000u | GOL_COLOR_ON;
		}
	wl_surface_attach(surface, buffer, 0, 0);
	wl_surface_damage_buffer(surface, 0, 0, (int32_t)width, (int32_t)height);
}

static void frame_done(void *data, struct wl_callback *cb, uint32_t t) {
	(void)data; (void)t;
	wl_callback_destroy(cb);
	frame_pending = false;
}
static const struct wl_callback_listener frame_listener = { .done = frame_done };

static void commit_frame(void) {
	struct wl_callback *cb = wl_surface_frame(surface);
	wl_callback_add_listener(cb, &frame_listener, NULL);
	frame_pending = true;
	wl_surface_commit(surface);
}

static void add_glider(double sx, double sy, const char *how) {
	unsigned cx, cy;
	if (!pixel_to_cell(sx, sy, &cx, &cy)) return;
	gol_insert_glider(&life.st.grid, cx, cy);
	life.gliders++;
	life_log(&life, "wayland %s: glider inserted at cell %u,%u (surface %.0f,%.0f) generation %u grid hash 0x%08x",
		how, cx, cy, sx, sy, life.st.generation, gol_grid_hash(&life.st.grid));
	if (configured && !frame_pending) { draw(); commit_frame(); }
}

static void touch_down(void *d, struct wl_touch *t, uint32_t s, uint32_t tm, struct wl_surface *sf,
		int32_t id, wl_fixed_t x, wl_fixed_t y) {
	(void)d; (void)t; (void)s; (void)tm; (void)id;
	if (sf == surface) add_glider(wl_fixed_to_double(x), wl_fixed_to_double(y), "touch");
}
static void touch_noop_up(void *d, struct wl_touch *t, uint32_t s, uint32_t tm, int32_t id) { (void)d; (void)t; (void)s; (void)tm; (void)id; }
static void touch_noop_motion(void *d, struct wl_touch *t, uint32_t tm, int32_t id, wl_fixed_t x, wl_fixed_t y) { (void)d; (void)t; (void)tm; (void)id; (void)x; (void)y; }
static void touch_noop(void *d, struct wl_touch *t) { (void)d; (void)t; }
static void touch_shape(void *d, struct wl_touch *t, int32_t id, wl_fixed_t a, wl_fixed_t b) { (void)d; (void)t; (void)id; (void)a; (void)b; }
static void touch_orient(void *d, struct wl_touch *t, int32_t id, wl_fixed_t o) { (void)d; (void)t; (void)id; (void)o; }
static const struct wl_touch_listener touch_listener = {
	.down = touch_down, .up = touch_noop_up, .motion = touch_noop_motion, .frame = touch_noop,
	.cancel = touch_noop, .shape = touch_shape, .orientation = touch_orient,
};

static double ptr_x, ptr_y;
static bool ptr_in;
static void ptr_enter(void *d, struct wl_pointer *p, uint32_t s, struct wl_surface *sf, wl_fixed_t x, wl_fixed_t y) {
	(void)d; (void)p; (void)s; ptr_in = sf == surface; ptr_x = wl_fixed_to_double(x); ptr_y = wl_fixed_to_double(y);
}
static void ptr_leave(void *d, struct wl_pointer *p, uint32_t s, struct wl_surface *sf) { (void)d; (void)p; (void)s; (void)sf; ptr_in = false; }
static void ptr_motion(void *d, struct wl_pointer *p, uint32_t tm, wl_fixed_t x, wl_fixed_t y) {
	(void)d; (void)p; (void)tm; ptr_x = wl_fixed_to_double(x); ptr_y = wl_fixed_to_double(y);
}
static void ptr_button(void *d, struct wl_pointer *p, uint32_t s, uint32_t tm, uint32_t button, uint32_t st) {
	(void)d; (void)p; (void)s; (void)tm; (void)button;
	if (ptr_in && st == WL_POINTER_BUTTON_STATE_PRESSED) add_glider(ptr_x, ptr_y, "pointer");
}
static void ptr_axis(void *d, struct wl_pointer *p, uint32_t tm, uint32_t a, wl_fixed_t v) { (void)d; (void)p; (void)tm; (void)a; (void)v; }
static const struct wl_pointer_listener ptr_listener = {
	.enter = ptr_enter, .leave = ptr_leave, .motion = ptr_motion, .button = ptr_button, .axis = ptr_axis,
};

static void seat_caps(void *d, struct wl_seat *s, uint32_t caps) {
	(void)d;
	if (caps & WL_SEAT_CAPABILITY_TOUCH) wl_touch_add_listener(wl_seat_get_touch(s), &touch_listener, NULL);
	if (caps & WL_SEAT_CAPABILITY_POINTER) wl_pointer_add_listener(wl_seat_get_pointer(s), &ptr_listener, NULL);
}
static void seat_name(void *d, struct wl_seat *s, const char *n) { (void)d; (void)s; (void)n; }
static const struct wl_seat_listener seat_listener = { .capabilities = seat_caps, .name = seat_name };

static int make_buffer(void) {
	int stride = (int)width * 4;
	size_t size = (size_t)stride * height;
	char name[64];
	int fd = -1;
	for (int i = 0; i < 100 && fd < 0; i++) {
		snprintf(name, sizeof name, "/k230-life-%d-%d", (int)getpid(), i);
		fd = shm_open(name, O_RDWR | O_CREAT | O_EXCL, 0600);
	}
	if (fd < 0) { perror("shm_open"); return -1; }
	shm_unlink(name);
	if (ftruncate(fd, (off_t)size) < 0) { perror("ftruncate"); return -1; }
	pixels = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	if (pixels == MAP_FAILED) { perror("mmap"); return -1; }
	map_size = size;
	struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, (int32_t)size);
	buffer = wl_shm_pool_create_buffer(pool, 0, (int32_t)width, (int32_t)height, stride, WL_SHM_FORMAT_ARGB8888);
	wl_shm_pool_destroy(pool);
	close(fd);
	return 0;
}

static void layer_configure(void *d, struct zwlr_layer_surface_v1 *ls, uint32_t serial, uint32_t w, uint32_t h) {
	(void)d;
	zwlr_layer_surface_v1_ack_configure(ls, serial);
	if (configured || !w || !h) return;
	width = w; height = h;
	if (rotate < 0) rotate = w > h ? 90 : 0;
	unsigned gw = rotate ? GOL_H : GOL_W, gh = rotate ? GOL_W : GOL_H;
	scale = width / gw < height / gh ? width / gw : height / gh;
	if (!scale) scale = 1;
	off_x = (width - gw * scale) / 2;
	off_y = (height - gh * scale) / 2;
	if (make_buffer()) { quit = 1; return; }
	configured = true;
	life_log(&life, "wayland: layer surface %ux%u, rotation %d, cell %u px, background layer, exclusive zone -1", w, h, rotate, scale);
	draw();
	commit_frame();
}
static void layer_closed(void *d, struct zwlr_layer_surface_v1 *ls) { (void)d; (void)ls; quit = 1; }
static const struct zwlr_layer_surface_v1_listener layer_listener = { .configure = layer_configure, .closed = layer_closed };

static void global_add(void *d, struct wl_registry *reg, uint32_t name, const char *iface, uint32_t v) {
	(void)d; (void)v;
	if (!strcmp(iface, wl_compositor_interface.name)) compositor = wl_registry_bind(reg, name, &wl_compositor_interface, 4);
	else if (!strcmp(iface, wl_shm_interface.name)) shm = wl_registry_bind(reg, name, &wl_shm_interface, 1);
	else if (!strcmp(iface, wl_seat_interface.name)) { seat = wl_registry_bind(reg, name, &wl_seat_interface, 5); wl_seat_add_listener(seat, &seat_listener, NULL); }
	else if (!strcmp(iface, zwlr_layer_shell_v1_interface.name)) layer_shell = wl_registry_bind(reg, name, &zwlr_layer_shell_v1_interface, 1);
}
static void global_remove(void *d, struct wl_registry *r, uint32_t n) { (void)d; (void)r; (void)n; }
static const struct wl_registry_listener registry_listener = { .global = global_add, .global_remove = global_remove };

int main(int argc, char **argv) {
	for (int i = 1; i < argc; i++) {
		if (!strcmp(argv[i], "--life-state") && i + 1 < argc) opts.state_path = argv[++i];
		else if (!strcmp(argv[i], "--life-instance") && i + 1 < argc) opts.instance_path = argv[++i];
		else if (!strcmp(argv[i], "--seed") && i + 1 < argc) opts.seed = (uint32_t)strtoul(argv[++i], NULL, 0);
		else if (!strcmp(argv[i], "--interval-ms") && i + 1 < argc) opts.interval_ms = (unsigned)strtoul(argv[++i], NULL, 0);
		else if (!strcmp(argv[i], "--rotate") && i + 1 < argc) rotate = atoi(argv[++i]);
		else if (!strcmp(argv[i], "--report") && i + 1 < argc) opts.report_path = argv[++i];
		else if (!strcmp(argv[i], "--run-seconds") && i + 1 < argc) run_seconds = (unsigned)strtoul(argv[++i], NULL, 0);
		else {
			fprintf(stderr, "usage: k230-life-wayland [--life-state P --life-instance P] [--seed N] [--interval-ms N] [--rotate 0|90|270] [--report P] [--run-seconds N]\n");
			return 2;
		}
	}
	if (rotate != -1 && rotate != 0 && rotate != 90 && rotate != 270) { fprintf(stderr, "k230-life-wayland: --rotate must be 0, 90 or 270\n"); return 2; }
	if (!opts.interval_ms) opts.interval_ms = 250;
	struct sigaction sa = { .sa_handler = on_term };
	sigemptyset(&sa.sa_mask);
	sigaction(SIGTERM, &sa, NULL);
	sigaction(SIGINT, &sa, NULL);

	life_load(&life, &opts);
	display = wl_display_connect(NULL);
	if (!display) { fprintf(stderr, "k230-life-wayland: cannot connect to a Wayland display; nothing started\n"); return 1; }
	struct wl_registry *reg = wl_display_get_registry(display);
	wl_registry_add_listener(reg, &registry_listener, NULL);
	wl_display_roundtrip(display);
	if (!compositor || !shm || !layer_shell) { fprintf(stderr, "k230-life-wayland: need wl_compositor, wl_shm and zwlr_layer_shell_v1\n"); return 1; }

	surface = wl_compositor_create_surface(compositor);
	layer_surface = zwlr_layer_shell_v1_get_layer_surface(layer_shell, surface, NULL, ZWLR_LAYER_SHELL_V1_LAYER_BACKGROUND, "k230-life");
	zwlr_layer_surface_v1_add_listener(layer_surface, &layer_listener, NULL);
	zwlr_layer_surface_v1_set_anchor(layer_surface, ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP | ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM |
		ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT | ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT);
	zwlr_layer_surface_v1_set_size(layer_surface, 0, 0);
	zwlr_layer_surface_v1_set_exclusive_zone(layer_surface, -1);
	zwlr_layer_surface_v1_set_keyboard_interactivity(layer_surface, ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE);
	wl_surface_commit(surface);

	clock_gettime(CLOCK_MONOTONIC, &started);
	double next = now_ms() + opts.interval_ms;
	int fd = wl_display_get_fd(display);
	while (!quit) {
		while (wl_display_prepare_read(display) != 0) wl_display_dispatch_pending(display);
		wl_display_flush(display);
		struct pollfd pfd = { .fd = fd, .events = POLLIN };
		if (poll(&pfd, 1, 50) > 0) wl_display_read_events(display); else wl_display_cancel_read(display);
		if (wl_display_dispatch_pending(display) < 0) { fprintf(stderr, "k230-life-wayland: display error: %s\n", strerror(errno)); break; }
		if (configured && !frame_pending && now_ms() >= next) {
			life_tick(&life);
			ticks++;
			do next += opts.interval_ms; while (next <= now_ms());
			draw();
			commit_frame();
		}
		struct timespec now;
		clock_gettime(CLOCK_MONOTONIC, &now);
		if (run_seconds && now.tv_sec - started.tv_sec >= (time_t)run_seconds) quit = 1;
	}
	life_log(&life, "wayland: stopping at generation %u after %u ticks, %u gliders inserted, grid hash 0x%08x",
		life.st.generation, ticks, life.gliders, gol_grid_hash(&life.st.grid));
	if (layer_surface) zwlr_layer_surface_v1_destroy(layer_surface);
	if (surface) wl_surface_destroy(surface);
	wl_display_flush(display);
	(void)map_size;
	return 0;
}

/* wlfps: measure how often a wlroots compositor actually presents a frame.
 *
 * It maps one small layer-shell surface (an 8x8 red square in the overlay
 * layer, exclusive zone 0, so it changes no layout) and then does nothing but
 * request wl_surface.frame callbacks. A wlroots-scene compositor such as sway
 * sends `done` to every visible surface once per output frame it renders
 * (sway/desktop/output.c: output_repaint_timer_handler -> send_frame_done),
 * so the interval between two `done`s is the compositor's real frame period
 * under whatever load the rest of the screen is generating. The timestamp in
 * the callback is the compositor's own (milliseconds, CLOCK_MONOTONIC), so
 * the measurement does not depend on this client being scheduled promptly.
 *
 * Every --interval seconds it prints frames, fps and the mean / min / p95 /
 * max frame interval. It says nothing about how long a frame took to render,
 * only how often one was presented; combine with the compositor's CPU time
 * over the same window for cost per frame.
 *
 *   wlfps [--interval S] [--duration S]
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>

#include "wlr-layer-shell-unstable-v1-client-protocol.h"
#include "xdg-shell-client-protocol.h"

#define SIDE 8
#define MAX_SAMPLES 8192

static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct zwlr_layer_shell_v1 *layer_shell;
static struct wl_surface *surface;
static struct zwlr_layer_surface_v1 *layer_surface;
static struct wl_buffer *buffer;
static bool running = true;
static bool configured = false;

static double interval_s = 5.0;
static double duration_s = 0.0;

/* stats for the current reporting window */
static bool have_last = false;
static uint32_t last_ms;
static uint32_t samples[MAX_SAMPLES];
static size_t nsamples;
static double window_start;
static double run_start;
static unsigned long total_frames;

static double now_s(void) {
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec + ts.tv_nsec / 1e9;
}

static int cmp_u32(const void *a, const void *b) {
	uint32_t x = *(const uint32_t *)a, y = *(const uint32_t *)b;
	return (x > y) - (x < y);
}

static void report(void) {
	double now = now_s();
	double span = now - window_start;
	if (nsamples == 0) {
		printf("t=%6.1fs frames=0 in %.1fs (no frame callbacks: compositor idle)\n",
			now - run_start, span);
	} else {
		qsort(samples, nsamples, sizeof(samples[0]), cmp_u32);
		unsigned long long sum = 0;
		for (size_t i = 0; i < nsamples; i++) sum += samples[i];
		double mean = (double)sum / nsamples;
		uint32_t p95 = samples[(size_t)((nsamples - 1) * 0.95)];
		/* nsamples is intervals; frames in the window is intervals + 1 */
		printf("t=%6.1fs frames=%zu fps=%.1f interval ms: mean=%.1f min=%u p95=%u max=%u\n",
			now - run_start, nsamples + 1, (nsamples + 1) / span, mean,
			samples[0], p95, samples[nsamples - 1]);
	}
	fflush(stdout);
	nsamples = 0;
	window_start = now;
}

static void request_frame(void);

static void frame_done(void *data, struct wl_callback *cb, uint32_t time_ms) {
	wl_callback_destroy(cb);
	total_frames++;
	if (have_last) {
		uint32_t dt = time_ms - last_ms;
		if (nsamples < MAX_SAMPLES) samples[nsamples++] = dt;
	}
	last_ms = time_ms;
	have_last = true;
	request_frame();
}

static const struct wl_callback_listener frame_listener = { .done = frame_done };

static void request_frame(void) {
	struct wl_callback *cb = wl_surface_frame(surface);
	wl_callback_add_listener(cb, &frame_listener, NULL);
	wl_surface_commit(surface);
}

static struct wl_buffer *make_buffer(void) {
	int stride = SIDE * 4, size = stride * SIDE;
	char name[] = "/wlfps-XXXXXX";
	int fd = -1;
	for (int i = 0; i < 100 && fd < 0; i++) {
		snprintf(name, sizeof name, "/wlfps-%d-%d", (int)getpid(), i);
		fd = shm_open(name, O_RDWR | O_CREAT | O_EXCL, 0600);
	}
	if (fd < 0) { perror("shm_open"); exit(1); }
	shm_unlink(name);
	if (ftruncate(fd, size) < 0) { perror("ftruncate"); exit(1); }
	uint32_t *px = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	if (px == MAP_FAILED) { perror("mmap"); exit(1); }
	for (int i = 0; i < SIDE * SIDE; i++) px[i] = 0xffff0000u; /* opaque red */
	munmap(px, size);
	struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, size);
	struct wl_buffer *buf = wl_shm_pool_create_buffer(pool, 0, SIDE, SIDE, stride,
		WL_SHM_FORMAT_ARGB8888);
	wl_shm_pool_destroy(pool);
	close(fd);
	return buf;
}

static void layer_configure(void *data, struct zwlr_layer_surface_v1 *ls,
		uint32_t serial, uint32_t w, uint32_t h) {
	zwlr_layer_surface_v1_ack_configure(ls, serial);
	if (!configured) {
		configured = true;
		buffer = make_buffer();
		wl_surface_attach(surface, buffer, 0, 0);
		wl_surface_damage_buffer(surface, 0, 0, SIDE, SIDE);
		request_frame(); /* commits */
		window_start = run_start = now_s();
	}
}

static void layer_closed(void *data, struct zwlr_layer_surface_v1 *ls) {
	running = false;
}

static const struct zwlr_layer_surface_v1_listener layer_listener = {
	.configure = layer_configure,
	.closed = layer_closed,
};

static void global_add(void *data, struct wl_registry *reg, uint32_t name,
		const char *iface, uint32_t version) {
	if (strcmp(iface, wl_compositor_interface.name) == 0) {
		compositor = wl_registry_bind(reg, name, &wl_compositor_interface, 4);
	} else if (strcmp(iface, wl_shm_interface.name) == 0) {
		shm = wl_registry_bind(reg, name, &wl_shm_interface, 1);
	} else if (strcmp(iface, zwlr_layer_shell_v1_interface.name) == 0) {
		layer_shell = wl_registry_bind(reg, name, &zwlr_layer_shell_v1_interface, 1);
	}
}

static void global_remove(void *data, struct wl_registry *reg, uint32_t name) {}

static const struct wl_registry_listener registry_listener = {
	.global = global_add,
	.global_remove = global_remove,
};

int main(int argc, char **argv) {
	for (int i = 1; i < argc; i++) {
		if (strcmp(argv[i], "--interval") == 0 && i + 1 < argc) {
			interval_s = atof(argv[++i]);
		} else if (strcmp(argv[i], "--duration") == 0 && i + 1 < argc) {
			duration_s = atof(argv[++i]);
		} else {
			fprintf(stderr, "usage: wlfps [--interval S] [--duration S]\n");
			return 2;
		}
	}

	display = wl_display_connect(NULL);
	if (!display) { fprintf(stderr, "wlfps: cannot connect to a Wayland display\n"); return 1; }
	struct wl_registry *reg = wl_display_get_registry(display);
	wl_registry_add_listener(reg, &registry_listener, NULL);
	wl_display_roundtrip(display);
	if (!compositor || !shm || !layer_shell) {
		fprintf(stderr, "wlfps: need wl_compositor, wl_shm and zwlr_layer_shell_v1\n");
		return 1;
	}

	surface = wl_compositor_create_surface(compositor);
	layer_surface = zwlr_layer_shell_v1_get_layer_surface(layer_shell, surface, NULL,
		ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY, "wlfps");
	zwlr_layer_surface_v1_add_listener(layer_surface, &layer_listener, NULL);
	zwlr_layer_surface_v1_set_size(layer_surface, SIDE, SIDE);
	zwlr_layer_surface_v1_set_anchor(layer_surface,
		ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP | ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT);
	zwlr_layer_surface_v1_set_exclusive_zone(layer_surface, 0);
	wl_surface_commit(surface);

	int fd = wl_display_get_fd(display);
	double started = now_s();
	while (running) {
		while (wl_display_prepare_read(display) != 0) {
			wl_display_dispatch_pending(display);
		}
		wl_display_flush(display);
		struct pollfd pfd = { .fd = fd, .events = POLLIN };
		int r = poll(&pfd, 1, 250);
		if (r > 0) {
			wl_display_read_events(display);
		} else {
			wl_display_cancel_read(display);
		}
		if (wl_display_dispatch_pending(display) < 0) {
			fprintf(stderr, "wlfps: display error: %s\n", strerror(errno));
			return 1;
		}
		if (configured && now_s() - window_start >= interval_s) {
			report();
		}
		if (duration_s > 0 && now_s() - started >= duration_s) {
			running = false;
		}
	}
	if (configured) report();
	printf("total frames: %lu\n", total_frames);
	return 0;
}

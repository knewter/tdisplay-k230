/*
 * k230-textfx: play a live ttfx effect on the panel (openspec change
 * the-boot-plays-terminal-text-effects).
 *
 * Runs `ttfx --parity-dump` as a child, reads its length-prefixed frames from a
 * pipe, parses each into a character-cell grid (src/textfx.c) and draws the
 * changed cells through the shared 8x16 glyph blitter, either into a file-backed
 * surface (--output-file, no DRM: used for host and board hash tests) or into
 * a KMS dumb buffer on the panel (--drm), using the splash owner's recipe: an
 * RG16 buffer, drmModeSetCrtc, a ready file, SIGUSR1 to drop DRM master.
 *
 * Continuation: --skip F --expect-hash H consumes frames 0..F without
 * drawing, requires the cell-grid hash of frame F to equal H, draws that grid
 * before the first modeset, and goes on from frame F+1.  A mismatch restarts
 * the run from frame 0.
 *
 * Pacing is by frame index against CLOCK_MONOTONIC; when late, frames are
 * coalesced (their cell changes drawn together), never delayed.
 */
#define _GNU_SOURCE
#include <sched.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#ifndef TEXTFX_NO_DRM
#include <drm.h>
#include <drm_fourcc.h>
#include <drm_mode.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#endif

#include "textfx.h"

#define PANEL_W 568u
#define PANEL_H 1232u
#define MAX_FRAME_BYTES (256u * 1024u)
#define HANDOFF_POLL_NS 100000000L
#define MAX_EXTRA 16
#define MAX_HASH_FRAMES 64

static volatile sig_atomic_t handoff_requested;
static volatile sig_atomic_t stopping;

struct opts {
	const char *ttfx, *banner, *effect;
	unsigned long long seed;
	unsigned cols, rows, fps, scale;
	long skip;            /* last frame stage 1 drew; -1 = play from frame 0 */
	uint32_t expect_hash; /* required when skip >= 0 */
	const char *output_file;
	bool drm;
	const char *card, *ready_file, *asset, *stats_file;
	bool no_pace, print_command, idle;
	long max_frames;
	long hash_frames[MAX_HASH_FRAMES];
	unsigned n_hash;
	const char *extra[MAX_EXTRA];
	unsigned n_extra;
};

static void say(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
#include <stdarg.h>
static void say(const char *fmt, ...)
{
	va_list ap;

	fputs("k230-textfx: ", stderr);
	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	va_end(ap);
	fputc('\n', stderr);
}

static void fail(const char *what)
{
	say("%s: %s", what, strerror(errno));
}

static void on_handoff(int s) { (void)s; handoff_requested = 1; }
static void on_stop(int s) { (void)s; stopping = 1; }

static int install_signals(void)
{
	struct sigaction h = { .sa_handler = on_handoff }, t = { .sa_handler = on_stop };

	sigemptyset(&h.sa_mask);
	sigemptyset(&t.sa_mask);
	if (sigaction(SIGUSR1, &h, NULL) || sigaction(SIGTERM, &t, NULL) || sigaction(SIGINT, &t, NULL)) {
		fail("install signal handlers");
		return -1;
	}
	return 0;
}

static long long now_ns(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static void sleep_until(long long t_ns)
{
	struct timespec ts = { .tv_sec = t_ns / 1000000000LL, .tv_nsec = t_ns % 1000000000LL };

	while (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, NULL) == EINTR && !stopping && !handoff_requested)
		;
}

/* ------------------------------------------------------------ ttfx child */

/* Must stay identical to ttfx_command() in tools/textfx_frames.py. */
static unsigned build_argv(const struct opts *o, const char **argv, char *store, size_t store_len)
{
	unsigned n = 0, i;
	char *p = store;
	int w;

	argv[n++] = o->ttfx;
	argv[n++] = "--seed";
	w = snprintf(p, store_len, "%llu", o->seed);
	argv[n++] = p;
	p += w + 1;
	argv[n++] = "--parity-dump";
	argv[n++] = "--canvas-width";
	w = snprintf(p, store_len - (size_t)(p - store), "%u", o->cols);
	argv[n++] = p;
	p += w + 1;
	argv[n++] = "--canvas-height";
	w = snprintf(p, store_len - (size_t)(p - store), "%u", o->rows);
	argv[n++] = p;
	p += w + 1;
	argv[n++] = "--ignore-terminal-dimensions";
	argv[n++] = "--frame-rate";
	w = snprintf(p, store_len - (size_t)(p - store), "%u", o->fps);
	argv[n++] = p;
	p += w + 1;
	argv[n++] = "--anchor-canvas";
	argv[n++] = "c";
	argv[n++] = "--anchor-text";
	argv[n++] = "c";
	argv[n++] = o->effect;
	for (i = 0; i < o->n_extra; i++)
		argv[n++] = o->extra[i];
	argv[n] = NULL;
	return n;
}

struct child {
	pid_t pid;
	int fd;
};

static int start_child(const struct opts *o, struct child *c)
{
	const char *argv[40];
	char store[256];
	int pipefd[2], banner;
	pid_t pid;

	build_argv(o, argv, store, sizeof store);
	banner = open(o->banner, O_RDONLY | O_CLOEXEC);
	if (banner < 0) { fail("open banner"); return -1; }
	if (pipe2(pipefd, O_CLOEXEC)) { fail("pipe"); close(banner); return -1; }
	pid = fork();
	if (pid < 0) { fail("fork"); return -1; }
	if (pid == 0) {
		int devnull = open("/dev/null", O_WRONLY);

		dup2(banner, 0);
		dup2(pipefd[1], 1);
		if (devnull >= 0)
			dup2(devnull, 2);
		execv(o->ttfx, (char *const *)argv);
		_exit(127);
	}
	close(banner);
	close(pipefd[1]);
	c->pid = pid;
	c->fd = pipefd[0];
	return 0;
}

static void stop_child(struct child *c)
{
	if (c->pid > 0) {
		kill(c->pid, SIGKILL);
		waitpid(c->pid, NULL, 0);
	}
	if (c->fd >= 0)
		close(c->fd);
	c->pid = -1;
	c->fd = -1;
}

static int read_full(int fd, uint8_t *buf, size_t n)
{
	size_t at = 0;

	while (at < n) {
		ssize_t r = read(fd, buf + at, n - at);

		if (r < 0 && errno == EINTR) {
			if (stopping || handoff_requested)
				return -2;
			continue;
		}
		if (r <= 0)
			return at == 0 && r == 0 ? 0 : -1;
		at += (size_t)r;
	}
	return 1;
}

/* 1 = frame read, 0 = clean end of stream, -1 = error, -2 = signalled. */
static int read_frame(int fd, uint8_t *buf, size_t *len)
{
	unsigned long n = 0;
	unsigned digits = 0;
	uint8_t c;
	int r;

	for (;;) {
		r = read_full(fd, &c, 1);
		if (r <= 0)
			return r;
		if (c == '\n')
			break;
		if (c < '0' || c > '9' || ++digits > 7)
			return -1;
		n = n * 10 + (c - '0');
	}
	if (!digits || n == 0 || n > MAX_FRAME_BYTES)
		return -1;
	r = read_full(fd, buf, n);
	if (r <= 0)
		return r == 0 ? -1 : r;
	r = read_full(fd, &c, 1);
	if (r <= 0 || c != '\n')
		return r == -2 ? r : -1;
	*len = n;
	return 1;
}

/* ------------------------------------------------------------- surfaces */

static uint8_t file_pixels[PANEL_W * PANEL_H * 4u];

struct kms {
	int fd;
	bool open_;
#ifndef TEXTFX_NO_DRM
	uint32_t connector_id, crtc_id, crtc_index, fb_id, handle;
	drmModeModeInfo mode;
#endif
	size_t size;
	uint32_t pitch;
	void *map;
};

#ifndef TEXTFX_NO_DRM
static bool is_primary_plane(int fd, drmModePlane *plane)
{
	drmModeObjectProperties *props = drmModeObjectGetProperties(fd, plane->plane_id, DRM_MODE_OBJECT_PLANE);
	bool primary = false;

	if (!props)
		return false;
	for (uint32_t i = 0; i < props->count_props; ++i) {
		drmModePropertyRes *p = drmModeGetProperty(fd, props->props[i]);

		if (p && strcmp(p->name, "type") == 0 && props->prop_values[i] == 1)
			primary = true;
		if (p)
			drmModeFreeProperty(p);
	}
	drmModeFreeObjectProperties(props);
	return primary;
}

static int find_target(struct kms *k)
{
	drmModeRes *res = drmModeGetResources(k->fd);
	int result = -1;

	if (!res) { fail("get DRM resources"); return -1; }
	for (int i = 0; i < res->count_connectors && result; ++i) {
		drmModeConnector *c = drmModeGetConnector(k->fd, res->connectors[i]);
		int preferred = 0;

		if (!c)
			continue;
		if (c->connection != DRM_MODE_CONNECTED || c->count_modes == 0) {
			drmModeFreeConnector(c);
			continue;
		}
		for (int m = 0; m < c->count_modes; ++m)
			if (c->modes[m].type & DRM_MODE_TYPE_PREFERRED) { preferred = m; break; }
		for (int e = -1; e < c->count_encoders && result; ++e) {
			uint32_t id = e < 0 ? c->encoder_id : c->encoders[e];
			drmModeEncoder *enc;

			if (!id || (e >= 0 && id == c->encoder_id))
				continue;
			enc = drmModeGetEncoder(k->fd, id);
			if (!enc)
				continue;
			for (int ci = 0; ci < res->count_crtcs; ++ci) {
				if (!(enc->possible_crtcs & (1U << ci)))
					continue;
				k->connector_id = c->connector_id;
				k->crtc_id = res->crtcs[ci];
				k->crtc_index = (uint32_t)ci;
				k->mode = c->modes[preferred];
				result = 0;
				break;
			}
			drmModeFreeEncoder(enc);
		}
		drmModeFreeConnector(c);
	}
	drmModeFreeResources(res);
	if (result)
		say("no connected connector with a usable CRTC");
	return result;
}

static int verify_primary_format(struct kms *k, uint32_t format)
{
	drmModePlaneRes *planes = drmModeGetPlaneResources(k->fd);
	int result = -1;

	if (!planes) { fail("get plane resources"); return -1; }
	for (uint32_t i = 0; i < planes->count_planes && result; ++i) {
		drmModePlane *pl = drmModeGetPlane(k->fd, planes->planes[i]);

		if (!pl)
			continue;
		if ((pl->possible_crtcs & (1U << k->crtc_index)) && is_primary_plane(k->fd, pl))
			for (uint32_t f = 0; f < pl->count_formats; ++f)
				if (pl->formats[f] == format) { result = 0; break; }
		drmModeFreePlane(pl);
	}
	drmModeFreePlaneResources(planes);
	if (result)
		say("primary plane lacks format %.4s", (char *)&format);
	return result;
}

/* Everything up to, but not including, the first modeset. */
static int kms_prepare(struct kms *k, const char *card)
{
	struct drm_mode_create_dumb create = { .width = PANEL_W, .height = PANEL_H, .bpp = 16 };
	uint32_t handles[4], pitches[4] = { 0 }, offsets[4] = { 0 };
	struct drm_mode_map_dumb map = { 0 };

	k->fd = open(card, O_RDWR | O_CLOEXEC);
	if (k->fd < 0) { fail("open DRM card"); return -1; }
	if (drmSetClientCap(k->fd, DRM_CLIENT_CAP_UNIVERSAL_PLANES, 1)) { fail("enable universal planes"); return -1; }
	if (find_target(k))
		return -1;
	if (k->mode.hdisplay != PANEL_W || k->mode.vdisplay != PANEL_H) {
		say("connected mode is %ux%u, expected %ux%u", k->mode.hdisplay, k->mode.vdisplay, PANEL_W, PANEL_H);
		return -1;
	}
	if (verify_primary_format(k, DRM_FORMAT_RGB565))
		return -1;
	if (drmIoctl(k->fd, DRM_IOCTL_MODE_CREATE_DUMB, &create)) { fail("create dumb buffer"); return -1; }
	k->handle = create.handle;
	k->pitch = create.pitch;
	k->size = create.size;
	if (create.pitch < PANEL_W * 2u || create.size < (uint64_t)create.pitch * PANEL_H) {
		say("invalid dumb buffer pitch/size");
		return -1;
	}
	handles[0] = create.handle;
	pitches[0] = create.pitch;
	if (drmModeAddFB2(k->fd, PANEL_W, PANEL_H, DRM_FORMAT_RGB565, handles, pitches, offsets, &k->fb_id, 0)) {
		fail("add framebuffer");
		return -1;
	}
	map.handle = create.handle;
	if (drmIoctl(k->fd, DRM_IOCTL_MODE_MAP_DUMB, &map)) { fail("map dumb buffer"); return -1; }
	k->map = mmap(NULL, create.size, PROT_READ | PROT_WRITE, MAP_SHARED, k->fd, map.offset);
	if (k->map == MAP_FAILED) { k->map = NULL; fail("mmap dumb buffer"); return -1; }
	k->open_ = true;
	return 0;
}

static int kms_modeset(struct kms *k)
{
	if (drmModeSetCrtc(k->fd, k->crtc_id, k->fb_id, 0, 0, &k->connector_id, 1, &k->mode)) {
		fail("set mode");
		return -1;
	}
	say("scanout fb %u on connector %u crtc %u as RG16", k->fb_id, k->connector_id, k->crtc_id);
	return 0;
}

static bool successor_replaced(struct kms *k)
{
	drmModeCrtc *crtc = drmModeGetCrtc(k->fd, k->crtc_id);
	bool replaced;

	if (!crtc)
		return false;
	replaced = crtc->buffer_id != 0 && crtc->buffer_id != k->fb_id;
	drmModeFreeCrtc(crtc);
	return replaced;
}
#endif /* !TEXTFX_NO_DRM */

#ifndef TEXTFX_NO_DRM
static int write_ready(const char *path, const char *state)
{
	int fd;
	size_t n = strlen(state);
	int rc;

	if (!path)
		return 0;
	fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0600);
	if (fd < 0) { fail("write readiness file"); return -1; }
	rc = write(fd, state, n) == (ssize_t)n && fsync(fd) == 0 ? 0 : -1;
	if (rc)
		fail("flush readiness file");
	close(fd);
	return rc;
}

#endif

/* Show the stage-1 logo asset (B,G,R,X, 568x1232) in an RG16 surface. */
static int paint_asset(const struct tfx_surface *s, const char *path)
{
	static uint8_t row[PANEL_W * 4u];
	int fd = open(path, O_RDONLY | O_CLOEXEC);
	struct stat st;

	if (fd < 0) { fail("open splash asset"); return -1; }
	if (fstat(fd, &st) || st.st_size != (off_t)(PANEL_W * PANEL_H * 4u)) {
		say("%s must be exactly %u BGRX bytes", path, PANEL_W * PANEL_H * 4u);
		close(fd);
		return -1;
	}
	for (unsigned y = 0; y < PANEL_H; ++y) {
		size_t at = 0;

		while (at < sizeof row) {
			ssize_t r = read(fd, row + at, sizeof row - at);

			if (r < 0 && errno == EINTR)
				continue;
			if (r <= 0) { close(fd); return -1; }
			at += (size_t)r;
		}
		for (unsigned x = 0; x < PANEL_W; ++x) {
			uint16_t v = (uint16_t)(((row[x * 4 + 2] >> 3) << 11) | ((row[x * 4 + 1] >> 2) << 5) | (row[x * 4] >> 3));
			uint8_t *p = (uint8_t *)s->pixels + (size_t)y * s->stride_bytes + (size_t)x * 2u;

			p[0] = v & 0xff;
			p[1] = v >> 8;
		}
	}
	close(fd);
	return 0;
}

/* ----------------------------------------------------------------- main */

struct stats {
	unsigned long frames, presented, coalesced;
};

static struct tfx_grid grid;
static uint16_t changed[TFX_MAX_CELLS];
static uint8_t dirty[TFX_MAX_CELLS];
static uint8_t frame_buf[MAX_FRAME_BYTES];

static void mark_dirty(unsigned n)
{
	for (unsigned i = 0; i < n; i++)
		dirty[changed[i]] = 1;
}

static void present(const struct tfx_surface *s)
{
	unsigned cells = grid.cols * grid.rows;

	for (unsigned i = 0; i < cells; i++)
		if (dirty[i]) {
			tfx_draw_cell(&grid, i, s);
			dirty[i] = 0;
		}
}

static bool is_hash_frame(const struct opts *o, long k)
{
	for (unsigned i = 0; i < o->n_hash; i++)
		if (o->hash_frames[i] == k)
			return true;
	return false;
}

static void write_stats(const struct opts *o, const struct stats *st, long long wall_ns)
{
	struct rusage self, kids;
	FILE *f = stderr;
	char buf[512];

	getrusage(RUSAGE_SELF, &self);
	getrusage(RUSAGE_CHILDREN, &kids);
	snprintf(buf, sizeof buf,
		 "frames=%lu presented=%lu coalesced=%lu wall_ms=%lld self_user_ms=%ld self_sys_ms=%ld ttfx_user_ms=%ld ttfx_sys_ms=%ld",
		 st->frames, st->presented, st->coalesced, wall_ns / 1000000LL,
		 self.ru_utime.tv_sec * 1000L + self.ru_utime.tv_usec / 1000L,
		 self.ru_stime.tv_sec * 1000L + self.ru_stime.tv_usec / 1000L,
		 kids.ru_utime.tv_sec * 1000L + kids.ru_utime.tv_usec / 1000L,
		 kids.ru_stime.tv_sec * 1000L + kids.ru_stime.tv_usec / 1000L);
	say("stats %s", buf);
	if (o->stats_file) {
		f = fopen(o->stats_file, "w");
		if (f) {
			fprintf(f, "%s\n", buf);
			fclose(f);
		}
	}
}

static int usage(const char *argv0)
{
	fprintf(stderr,
		"usage: %s --ttfx PATH --banner PATH --effect NAME --seed N [--cols 35 --rows 38 --fps 30 --scale 2]\n"
		"          (--output-file PATH | --drm [--card /dev/dri/card0] [--ready-file PATH] [--asset logo.xrgb])\n"
		"          [--skip FRAME --expect-hash 0xHASH] [--hash-frames A,B,..] [--max-frames N]\n"
		"          [--no-pace] [--idle] [--stats-file PATH] [--print-command] [-- effect args...]\n", argv0);
	return 2;
}

static int parse_opts(int argc, char **argv, struct opts *o)
{
	*o = (struct opts){ .cols = 35, .rows = 38, .fps = 30, .scale = 2, .skip = -1,
			    .card = "/dev/dri/card0", .max_frames = -1 };
	for (int i = 1; i < argc; ++i) {
		const char *a = argv[i];
		const char *v = i + 1 < argc ? argv[i + 1] : NULL;

		if (!strcmp(a, "--"))  { for (++i; i < argc && o->n_extra < MAX_EXTRA; ++i) o->extra[o->n_extra++] = argv[i]; break; }
		else if (!strcmp(a, "--ttfx") && v) { o->ttfx = v; ++i; }
		else if (!strcmp(a, "--banner") && v) { o->banner = v; ++i; }
		else if (!strcmp(a, "--effect") && v) { o->effect = v; ++i; }
		else if (!strcmp(a, "--seed") && v) { o->seed = strtoull(v, NULL, 10); ++i; }
		else if (!strcmp(a, "--cols") && v) { o->cols = (unsigned)atoi(v); ++i; }
		else if (!strcmp(a, "--rows") && v) { o->rows = (unsigned)atoi(v); ++i; }
		else if (!strcmp(a, "--fps") && v) { o->fps = (unsigned)atoi(v); ++i; }
		else if (!strcmp(a, "--scale") && v) { o->scale = (unsigned)atoi(v); ++i; }
		else if (!strcmp(a, "--skip") && v) { o->skip = atol(v); ++i; }
		else if (!strcmp(a, "--expect-hash") && v) { o->expect_hash = (uint32_t)strtoul(v, NULL, 0); ++i; }
		else if (!strcmp(a, "--output-file") && v) { o->output_file = v; ++i; }
		else if (!strcmp(a, "--drm")) o->drm = true;
		else if (!strcmp(a, "--card") && v) { o->card = v; ++i; }
		else if (!strcmp(a, "--ready-file") && v) { o->ready_file = v; ++i; }
		else if (!strcmp(a, "--asset") && v) { o->asset = v; ++i; }
		else if (!strcmp(a, "--stats-file") && v) { o->stats_file = v; ++i; }
		else if (!strcmp(a, "--max-frames") && v) { o->max_frames = atol(v); ++i; }
		else if (!strcmp(a, "--no-pace")) o->no_pace = true;
		else if (!strcmp(a, "--idle")) o->idle = true;
		else if (!strcmp(a, "--print-command")) o->print_command = true;
		else if (!strcmp(a, "--hash-frames") && v) {
			char tmp[1024], *tok;

			strncpy(tmp, v, sizeof tmp - 1);
			tmp[sizeof tmp - 1] = 0;
			for (tok = strtok(tmp, ","); tok && o->n_hash < MAX_HASH_FRAMES; tok = strtok(NULL, ","))
				o->hash_frames[o->n_hash++] = atol(tok);
			++i;
		} else return -1;
	}
	if (!o->ttfx || !o->banner || !o->effect || !o->scale || !o->fps)
		return -1;
	if (o->cols * TFX_GLYPH_W * o->scale > PANEL_W || o->rows * TFX_GLYPH_H * o->scale > PANEL_H)
		return -1;
	if (o->skip >= 0 && !o->expect_hash)
		return -1;
	return (o->drm ? 1 : 0) + (o->output_file ? 1 : 0) == 1 || o->print_command ? 0 : -1;
}

int main(int argc, char **argv)
{
	struct opts o;
	struct tfx_surface surf;
	struct child child = { -1, -1 };
	struct stats st = { 0 };
	struct kms kms __attribute__((unused)) = { .fd = -1 };
	long long t0 = 0, wall0 = now_ns();
	long k, first_drawn = 0;
	bool modeset_done = false, continuing, mismatch_restart = false;
	int rc = 1;
	size_t flen;

	if (parse_opts(argc, argv, &o))
		return usage(argv[0]);
	if (o.print_command) {
		const char *av[40];
		char store[256];

		build_argv(&o, av, store, sizeof store);
		for (unsigned i = 0; av[i]; i++)
			printf("%s%s", i ? " " : "", av[i]);
		putchar('\n');
		return 0;
	}
	if (install_signals())
		return 1;
	if (o.idle) {
		struct sched_param sp = { 0 };

		/* One online CPU and boot is CPU-bound: run only when nothing else wants it. */
		if (sched_setscheduler(0, SCHED_IDLE, &sp))
			fail("SCHED_IDLE");
	}
	if (tfx_grid_init(&grid, o.cols, o.rows)) {
		say("grid does not fit");
		return 1;
	}
	surf = (struct tfx_surface){ .scale = o.scale,
				     .x0 = (PANEL_W - o.cols * TFX_GLYPH_W * o.scale) / 2,
				     .y0 = (PANEL_H - o.rows * TFX_GLYPH_H * o.scale) / 2,
				     .width = PANEL_W, .height = PANEL_H };
	if (o.drm) {
#ifdef TEXTFX_NO_DRM
		say("built without DRM");
		return 1;
#else
		if (kms_prepare(&kms, o.card))
			goto out;
		surf.pixels = kms.map;
		surf.stride_bytes = kms.pitch;
		surf.fmt = TFX_RGB565;
#endif
	} else {
		surf.pixels = file_pixels;
		surf.stride_bytes = PANEL_W * 4u;
		surf.fmt = TFX_XRGB8888;
	}

restart:
	continuing = o.skip >= 0 && !mismatch_restart;
	tfx_grid_init(&grid, o.cols, o.rows);
	memset(dirty, 0, sizeof dirty);
	if (!continuing) {
		/* The glass shows the stage-1 logo (or nothing): keep it until the first frame. */
		if (o.drm && o.asset && !modeset_done && paint_asset(&surf, o.asset))
			say("no splash asset; starting from black");
		else if (!o.drm || !o.asset)
			tfx_clear(&surf);
	}
	if (start_child(&o, &child))
		goto out;
	for (k = 0;; ++k) {
		int r, n;

		if (handoff_requested || stopping)
			break;
		r = read_frame(child.fd, frame_buf, &flen);
		if (r == -2)
			break;
		if (r == 0) {
			int status = 0;

			/* End of stream: complete only if ttfx says so and produced frames. */
			if (waitpid(child.pid, &status, 0) == child.pid)
				child.pid = -1;
			if (!st.frames || !WIFEXITED(status) || WEXITSTATUS(status)) {
				say("ttfx ended after %lu frames with status 0x%x", st.frames, status);
				goto out;
			}
			break; /* effect complete */
		}
		if (r < 0) {
			say("malformed or truncated ttfx stream at frame %ld", k);
			goto out;
		}
		n = tfx_parse_frame(&grid, frame_buf, flen, changed, TFX_MAX_CELLS);
		if (n < 0) {
			say("frame %ld not understood", k);
			goto out;
		}
		st.frames++;
		if (continuing && k <= o.skip) {
			if (k == o.skip) {
				uint32_t h = tfx_grid_hash(&grid);

				if (h != o.expect_hash) {
					say("continuation refused: frame %ld hash 0x%08x != record 0x%08x; playing from frame 0", k, h, o.expect_hash);
					stop_child(&child);
					mismatch_restart = true;
					memset(&st, 0, sizeof st);
					goto restart;
				}
				say("continuing after frame %ld (hash 0x%08x verified)", k, h);
				tfx_clear(&surf);
				tfx_draw_all(&grid, &surf);
				first_drawn = k + 1;
			}
			continue;
		}
		if (!modeset_done && o.drm) {
#ifndef TEXTFX_NO_DRM
			if (kms_modeset(&kms))
				goto out;
			if (write_ready(o.ready_file, "scanout\n"))
				goto out;
#endif
			modeset_done = true;
		}
		if (!t0) {
			t0 = now_ns();
			first_drawn = continuing ? first_drawn : k;
		}
		mark_dirty((unsigned)n);
		if (!o.no_pace) {
			long long due = t0 + (long long)(k - first_drawn + 1) * 1000000000LL / o.fps;

			if (now_ns() > due + 2LL * 1000000000LL / o.fps && !is_hash_frame(&o, k)) {
				st.coalesced++;
				continue; /* late: let the next frame's cells join this one */
			}
			present(&surf);
			st.presented++;
			sleep_until(due);
		} else {
			if (is_hash_frame(&o, k) || (o.max_frames >= 0 && k + 1 >= o.max_frames)) {
				present(&surf);
				st.presented++;
			}
		}
		if (is_hash_frame(&o, k)) {
			present(&surf);
			printf("hash frame %ld cell=0x%08x surface=0x%08x\n", k, tfx_grid_hash(&grid), tfx_surface_hash(&surf));
			fflush(stdout);
		}
		if (o.max_frames >= 0 && k + 1 >= o.max_frames)
			break;
	}
	if (!o.drm || modeset_done) {
		present(&surf);
	}
	if (o.drm && !modeset_done && !handoff_requested && !stopping) {
#ifndef TEXTFX_NO_DRM
		/* The stream ended during a continuation without a later frame: still take the scanout. */
		if (kms_modeset(&kms) || write_ready(o.ready_file, "scanout\n"))
			goto out;
#endif
		modeset_done = true;
	}
	stop_child(&child);
	printf("final frames=%lu cell=0x%08x surface=0x%08x\n", st.frames, tfx_grid_hash(&grid), tfx_surface_hash(&surf));
	fflush(stdout);
	write_stats(&o, &st, now_ns() - wall0);
	if (o.output_file) {
		FILE *f = fopen(o.output_file, "wb");

		if (!f || fwrite(file_pixels, 1, sizeof file_pixels, f) != sizeof file_pixels) {
			fail("write output file");
			if (f) fclose(f);
			goto out;
		}
		fclose(f);
	}
	rc = 0;
#ifndef TEXTFX_NO_DRM
	if (o.drm && modeset_done) {
		/* Hold the last frame until the shell asks for the display or we are stopped. */
		while (!stopping) {
			struct timespec pause = { .tv_nsec = HANDOFF_POLL_NS };

			if (handoff_requested) {
				handoff_requested = 0;
				if (drmDropMaster(kms.fd)) { fail("drop DRM master"); continue; }
				if (write_ready(o.ready_file, "master-dropped\n"))
					break;
				say("DRM master dropped; retaining fb %u for the successor", kms.fb_id);
				while (!stopping && !successor_replaced(&kms)) {
					nanosleep(&pause, NULL);
				}
				break;
			}
			nanosleep(&pause, NULL);
		}
	}
#endif
out:
	stop_child(&child);
	return rc;
}

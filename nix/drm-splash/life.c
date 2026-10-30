#include "life.h"

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#define BITS_PER_LONG_ (sizeof(long) * 8)
#define NBITS_(x) ((((x) - 1) / BITS_PER_LONG_) + 1)

static bool test_bit_(int bit, const unsigned long *arr)
{
	return (arr[bit / BITS_PER_LONG_] >> (bit % BITS_PER_LONG_)) & 1UL;
}

void life_log(const struct life *l, const char *fmt, ...)
{
	char line[320];
	va_list ap;
	struct timespec ts;

	va_start(ap, fmt);
	vsnprintf(line, sizeof line, fmt, ap);
	va_end(ap);
	clock_gettime(CLOCK_BOOTTIME, &ts);
	fprintf(stderr, "k230-drm-splash: life: %s\n", line);
	if (l->opts.report_path) {
		FILE *f = fopen(l->opts.report_path, "a");

		if (f) {
			fprintf(f, "%ld.%03ld %s\n", (long)ts.tv_sec, ts.tv_nsec / 1000000L, line);
			fclose(f);
		}
	}
}

static size_t read_file(const char *path, uint8_t *buf, size_t max)
{
	int fd = open(path, O_RDONLY | O_CLOEXEC);
	size_t at = 0;

	if (fd < 0)
		return 0;
	while (at < max) {
		ssize_t n = read(fd, buf + at, max - at);

		if (n < 0 && errno == EINTR)
			continue;
		if (n <= 0)
			break;
		at += (size_t)n;
	}
	close(fd);
	return at;
}

void life_load(struct life *l, const struct life_opts *opts)
{
	static uint8_t rec[16384];
	uint8_t inst[4] = { 0 };
	size_t n, ni = 0;
	uint32_t instance = 0;
	struct timespec ts;

	memset(l, 0, sizeof *l);
	l->opts = *opts;
	for (int i = 0; i < LIFE_MAX_TOUCH; i++)
		l->touch_fd[i] = -1;
	clock_gettime(CLOCK_BOOTTIME, &ts);

	if (opts->instance_path)
		ni = read_file(opts->instance_path, inst, sizeof inst);
	if (ni == 4)
		instance = (uint32_t)inst[0] << 24 | (uint32_t)inst[1] << 16 |
			   (uint32_t)inst[2] << 8 | inst[3]; /* device-tree cells are big-endian */
	n = opts->state_path ? read_file(opts->state_path, rec, sizeof rec) : 0;

	if (ni != 4 || instance == 0) {
		l->reject = GOL_BAD_INSTANCE;
		life_log(l, "no stage-1 instance token in the device tree; using the deterministic default (seed 0x%08x)",
			 opts->seed);
	} else if (n == 0) {
		l->reject = GOL_BAD_LENGTH;
		life_log(l, "no stage-1 state record readable; using the deterministic default (seed 0x%08x)",
			 opts->seed);
	} else {
		l->reject = gol_record_decode(&l->st, rec, n, instance);
		if (l->reject == GOL_OK)
			l->from_record = true;
		else
			life_log(l, "stage-1 state rejected (%s); using the deterministic default (seed 0x%08x)",
				 gol_status_name(l->reject), opts->seed);
	}
	if (l->from_record) {
		life_log(l, "continuing the stage-1 grid at generation %u (instance 0x%08x, seed 0x%08x, grid hash 0x%08x)",
			 l->st.generation, l->st.boot_instance, l->st.seed, gol_grid_hash(&l->st.grid));
		life_log(l, "ownership pause: the panel held stage 1's generation %u from the end of U-Boot until this Linux owner took it at uptime %ld.%03ld s",
			 l->st.frame_generation, (long)ts.tv_sec, ts.tv_nsec / 1000000L);
		l->st.owner = GOL_OWNER_LINUX;
	} else {
		gol_state_init_default(&l->st, instance ? instance : 1, opts->seed);
		l->st.owner = GOL_OWNER_LINUX;
		life_log(l, "default grid at generation 0 (grid hash 0x%08x) at uptime %ld.%03ld s",
			 gol_grid_hash(&l->st.grid), (long)ts.tv_sec, ts.tv_nsec / 1000000L);
	}
}

int life_touch_open(struct life *l)
{
	const char *dir = l->opts.input_dir ? l->opts.input_dir : "/dev/input";
	DIR *d = opendir(dir);
	struct dirent *e;

	if (!d) {
		life_log(l, "touch: cannot open %s (%s); animation continues without touch", dir,
			 strerror(errno));
		return 0;
	}
	while ((e = readdir(d)) && l->touch_n < LIFE_MAX_TOUCH) {
		char path[300];
		unsigned long evbits[NBITS_(EV_MAX + 1)] = { 0 };
		unsigned long absbits[NBITS_(ABS_MAX + 1)] = { 0 };
		struct input_absinfo ax, ay;
		int fd, k;

		if (strncmp(e->d_name, "event", 5))
			continue;
		snprintf(path, sizeof path, "%s/%s", dir, e->d_name);
		fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
		if (fd < 0)
			continue;
		if (ioctl(fd, EVIOCGBIT(0, sizeof evbits), evbits) < 0 ||
		    !test_bit_(EV_ABS, evbits) ||
		    ioctl(fd, EVIOCGBIT(EV_ABS, sizeof absbits), absbits) < 0 ||
		    !test_bit_(ABS_MT_POSITION_X, absbits) || !test_bit_(ABS_MT_POSITION_Y, absbits) ||
		    ioctl(fd, EVIOCGABS(ABS_MT_POSITION_X), &ax) < 0 ||
		    ioctl(fd, EVIOCGABS(ABS_MT_POSITION_Y), &ay) < 0 || ax.maximum <= ax.minimum ||
		    ay.maximum <= ay.minimum) {
			close(fd);
			continue;
		}
		k = l->touch_n++;
		l->touch_fd[k] = fd;
		l->touch[k].minx = ax.minimum;
		l->touch[k].maxx = ax.maximum;
		l->touch[k].miny = ay.minimum;
		l->touch[k].maxy = ay.maximum;
		{
			char name[80] = "?";

			ioctl(fd, EVIOCGNAME(sizeof name), name);
			life_log(l, "touch: using %s \"%s\" x %d..%d y %d..%d", path, name, ax.minimum,
				 ax.maximum, ay.minimum, ay.maximum);
		}
	}
	closedir(d);
	if (!l->touch_n)
		life_log(l, "touch: no multitouch device; animation continues without touch");
	return l->touch_n;
}

unsigned life_touch_poll(struct life *l)
{
	unsigned inserted = 0;

	for (int k = 0; k < l->touch_n; k++) {
		struct input_event ev[32];
		ssize_t n;

		while ((n = read(l->touch_fd[k], ev, sizeof ev)) > 0) {
			for (size_t i = 0; i < (size_t)n / sizeof ev[0]; i++) {
				if (ev[i].type == EV_ABS) {
					if (ev[i].code == ABS_MT_POSITION_X) {
						l->touch[k].x = ev[i].value;
						l->touch[k].have_x = true;
					} else if (ev[i].code == ABS_MT_POSITION_Y) {
						l->touch[k].y = ev[i].value;
						l->touch[k].have_y = true;
					} else if (ev[i].code == ABS_MT_TRACKING_ID && ev[i].value >= 0) {
						l->touch[k].new_contact = true;
					}
				} else if (ev[i].type == EV_SYN && ev[i].code == SYN_REPORT) {
					if (l->touch[k].new_contact && l->touch[k].have_x && l->touch[k].have_y) {
						long px = (long)(l->touch[k].x - l->touch[k].minx) * GOL_PANEL_W /
							  (l->touch[k].maxx - l->touch[k].minx + 1);
						long py = (long)(l->touch[k].y - l->touch[k].miny) * GOL_PANEL_H /
							  (l->touch[k].maxy - l->touch[k].miny + 1);
						unsigned cx, cy;

						if (px >= 0 && py >= 0 &&
						    gol_pixel_to_cell((unsigned)px, (unsigned)py, &cx, &cy)) {
							gol_insert_glider(&l->st.grid, cx, cy);
							l->gliders++;
							inserted++;
							life_log(l, "touch: glider inserted at cell %u,%u (pixel %ld,%ld) generation %u grid hash 0x%08x",
								 cx, cy, px, py, l->st.generation,
								 gol_grid_hash(&l->st.grid));
						}
					}
					l->touch[k].new_contact = false;
				}
			}
		}
	}
	return inserted;
}

void life_tick(struct life *l)
{
	gol_state_advance(&l->st);
}

void life_render_rgb565(const struct life *l, void *map, uint32_t pitch)
{
	gol_render_rgb565(&l->st.grid, map, pitch);
}

void life_close(struct life *l)
{
	for (int k = 0; k < l->touch_n; k++)
		if (l->touch_fd[k] >= 0)
			close(l->touch_fd[k]);
	l->touch_n = 0;
}

/*
 * Early-Linux continuation of the stage-1 Game of Life inside the DRM splash
 * owner (openspec change the-boot-shows-a-computational-game-of-life,
 * tasks 2.2 and 3.1).  Uses the shared engine in src/game_of_life.c.
 */
#ifndef LIFE_H
#define LIFE_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "game_of_life.h"

#define LIFE_MAX_TOUCH 4

struct life_opts {
	const char *state_path;    /* copy of the stage-1 record window */
	const char *instance_path; /* /proc/device-tree/chosen/canaan,life-instance */
	const char *report_path;   /* optional event log for evidence */
	const char *input_dir;     /* /dev/input unless overridden (tests) */
	const char *log_tag;       /* stderr prefix; default "k230-drm-splash" */
	uint32_t seed;             /* deterministic fallback seed */
	unsigned interval_ms;
};

struct life {
	struct gol_state st;
	struct life_opts opts;
	bool from_record;
	enum gol_status reject;
	int touch_fd[LIFE_MAX_TOUCH];
	int touch_n;
	struct {
		int x, y, minx, maxx, miny, maxy;
		bool new_contact, have_x, have_y;
	} touch[LIFE_MAX_TOUCH];
	unsigned gliders;
};

/* Always succeeds: a missing or invalid record selects the deterministic default. */
void life_load(struct life *l, const struct life_opts *opts);
/* Open every direct multitouch device; zero devices is a valid result. */
int life_touch_open(struct life *l);
/* Drain pending touch events; returns the number of gliders inserted. */
unsigned life_touch_poll(struct life *l);
void life_tick(struct life *l);
void life_render_rgb565(const struct life *l, void *map, uint32_t pitch);
void life_close(struct life *l);
/* One line to stderr and, when configured, the report file. */
void life_log(const struct life *l, const char *fmt, ...) __attribute__((format(printf, 2, 3)));

#endif

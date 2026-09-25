#ifndef SWAY_CARD_SHELL_APPEARANCE_H
#define SWAY_CARD_SHELL_APPEARANCE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define CARD_APPEARANCE_STOPS 8

struct card_brush_stop {
	uint32_t argb;
	double offset;
};

struct card_brush {
	struct card_brush_stop stops[CARD_APPEARANCE_STOPS];
	size_t count;
	double angle_degrees, alpha;
};

struct card_appearance {
	char generation[25];
	struct card_brush canvas, card, selected;
	uint32_t text, selected_text;
	bool wallpaper, canvas_authored;
	/* The active theme's own icon-theme name (report.json's top-level
	 * "icon_theme" string, the same field
	 * nix/rust-shell-client/src/render.rs's icon_theme_name_for prefers
	 * over K230_ICON_THEME) -- empty when the report does not specify one,
	 * in which case the card-header icon resolver's own env/default
	 * fallback applies instead (see nix/card-shell/icon.c). */
	char icon_theme[64];
};

typedef bool (*card_appearance_apply_fn)(const struct card_appearance *, void *);
/* Called once per successfully validated `prepare`, before its ack, with the
 * *candidate* appearance -- a chance to warm anything commit will want (see
 * adapter.c's `appearance_prepare`). Advisory only: it has no return value
 * and cannot affect whether prepare is acknowledged, matching
 * `background.cache`'s own posture in background_decode.rs -- a missed or
 * skipped warm-up can only cost time, never correctness. May be NULL. */
typedef void (*card_appearance_prepare_fn)(const struct card_appearance *, void *);

/* Enabled only with an explicit state root and private runtime socket. */
bool card_appearance_start(const char *socket_path, const char *state_root,
	const char *default_generation, card_appearance_apply_fn apply,
	card_appearance_prepare_fn prepare, void *data);
void card_appearance_poll(void);
void card_appearance_stop(void);
const struct card_appearance *card_appearance_current(void);

#endif

/*
 * Neutral boot-frame-source interface.  Stage 1 (U-Boot) and early Linux drive
 * any producer of boot frames through this; Game of Life is the first producer
 * (src/boot_life_stage1.c).  A text-effects producer implements struct
 * bf_source the same way and reuses the loop, the record window and the
 * ownership rules unchanged.
 *
 * Contract (freestanding C: <stdint.h>, <stddef.h>, memcpy/memset only):
 *   - The target is the 568x1232 XRGB8888 scanout already lit by stage 1
 *     (nix/boot-splash.nix framebufferAddress); the loop never touches panel
 *     or VO registers.
 *   - start() draws frame 0.  step() advances one frame and draws it; it may
 *     redraw only what changed.  Neither may write outside the target.
 *   - publish() writes the producer's complete record (header plus resumable
 *     payload; the payload may be empty if it cannot resume) into the record
 *     window inside the splash reservation (nix/boot-splash.nix
 *     lifeRecordOffset/Window; 8 KiB).  Every producer's record MUST start
 *     with the common prefix: bytes 0-3 magic, 4-7 ABI version, 8-11 total
 *     length, 12-15 boot-instance token (nonzero), byte 30 source id, and end
 *     the 40-byte header with an FNV-1a checksum at 36 over header and payload;
 *     Game of Life's layout (src/game_of_life.h) is the reference.  Linux
 *     validates the prefix, the checksum and the token against
 *     /chosen/canaan,life-instance before it hands the payload to the source
 *     that owns the id.
 *   - source ids: 0 and 1 = Game of Life (ABI v1 wrote 0 in that byte);
 *     2..255 are unassigned and are to be claimed in this comment.
 */
#ifndef BOOT_FRAME_H
#define BOOT_FRAME_H

#include "boot_compat.h"

#define BF_SOURCE_LIFE 1u

struct bf_target {
	void *fb;
	size_t stride_bytes;
	unsigned width, height; /* pixels, XRGB8888 */
};

struct bf_source {
	const char *name;
	unsigned id;
	void *ctx;
	/* Draw frame 0 (resuming nothing). Returns 0 or -1 (nothing drawn). */
	int (*start)(void *ctx, const struct bf_target *t, uint32_t seed);
	/* Advance and draw one frame. Returns 0 or -1 (stop the loop). */
	int (*step)(void *ctx, const struct bf_target *t);
	/* Write the complete record to out (max bytes) for the given boot
	 * instance; return its length or -1.  Reports the frame counter. */
	long (*publish)(void *ctx, uint8_t *out, size_t max, uint32_t instance, uint32_t *frame);
};

struct bf_ops {
	void *ctx;
	void (*flush)(void *ctx, const void *p, size_t n);
	void (*delay_ms)(void *ctx, unsigned ms);
};

struct bf_cfg {
	struct bf_target target;
	uint8_t *record;
	size_t record_window;
	uint32_t boot_instance; /* nonzero */
	uint32_t seed;
	unsigned frames;
	unsigned frame_ms;
};

struct bf_result {
	uint32_t frame;
	uint32_t instance;
};

/* 0 on success; -1 if the configuration is unusable (nothing written). */
int bf_run(const struct bf_cfg *cfg, const struct bf_ops *ops, struct bf_source *src,
	   struct bf_result *out);

#endif

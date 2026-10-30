/*
 * Stage-1 driver loop for the boot Game of Life, free of any U-Boot or
 * hardware dependency so the host can run exactly the code the firmware runs.
 * The firmware wrapper (nix/uboot-k230-life/k230_boot_life.c) supplies the
 * framebuffer, the record window, a cache flush and a delay.
 *
 * Ownership contract (openspec change the-boot-shows-a-computational-game-of-life):
 *   - the record window is inside the no-map splash reservation, after the
 *     scanout (nix/boot-splash.nix lifeRecordOffset);
 *   - stage 1 invalidates the window first, renders, then publishes a
 *     checksummed record after every frame; a reader that sees a bad checksum
 *     falls back to the deterministic default;
 *   - stage 1 stops writing before it boots the kernel.
 */
#ifndef BOOT_LIFE_STAGE1_H
#define BOOT_LIFE_STAGE1_H

#include "game_of_life.h"

struct boot_life_ops {
	void *ctx;
	/* Make [p, p+n) visible to the display engine / the next owner. */
	void (*flush)(void *ctx, const void *p, size_t n);
	void (*delay_ms)(void *ctx, unsigned ms);
};

struct boot_life_cfg {
	void *fb;             /* 568x1232 XRGB8888 scanout, stride GOL_PANEL_W*4 */
	uint8_t *record;      /* window of at least GOL_RECORD_BYTES */
	size_t record_window; /* bytes available at `record` */
	uint32_t boot_instance; /* nonzero token for this boot */
	uint32_t seed;
	unsigned frames;      /* generations to run after the first frame */
	unsigned frame_ms;    /* delay between frames */
};

struct boot_life_result {
	uint32_t generation;       /* last generation drawn and published */
	uint32_t instance;
	uint32_t grid_hash;
	unsigned cells_redrawn;    /* differential redraw total, frames 1.. */
};

/* Returns 0 on success, -1 if the configuration is unusable (nothing drawn). */
int boot_life_stage1_run(const struct boot_life_cfg *cfg, const struct boot_life_ops *ops,
			 struct boot_life_result *out);

#endif

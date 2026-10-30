// SPDX-License-Identifier: GPL-2.0+
/*
 * Stage-1 Game of Life for the T-Display K230 (RM69A10).  Opt-in:
 * CONFIG_K230_BOOT_LIFE.  Runs the shared portable engine (src/game_of_life.c
 * and src/boot_life_stage1.c, copied in by nix/uboot-k230.nix) on top of the
 * already-lit logo scanout, then publishes its state for the next owner.
 *
 * The logo path is not changed: this runs only after k230_display_logo() has
 * set its ready flag, so /chosen/canaan,stage1-splash keeps its meaning.  A
 * failure here leaves the logo (or the last drawn frame) on the glass.
 */
#include <common.h>
#include <command.h>
#include <cpu_func.h>
#include <log.h>
#include <linux/delay.h>
#include <linux/kernel.h>
#include <mapmem.h>
#include <asm/io.h>
#include <timer.h>

#include "boot_life_stage1.h"
#include "display_logo.h"

#define LIFE_FB_BYTES ((unsigned long)GOL_PANEL_W * 4UL * GOL_PANEL_H)

static uint32_t life_instance;

static void life_flush(void *ctx, const void *p, size_t n)
{
	unsigned long a = (unsigned long)p & ~(unsigned long)(CONFIG_SYS_CACHELINE_SIZE - 1);
	unsigned long e = ROUND((unsigned long)p + n, CONFIG_SYS_CACHELINE_SIZE);

	flush_cache(a, e - a);
}

static void life_delay(void *ctx, unsigned ms)
{
	mdelay(ms);
}

uint32_t k230_boot_life_instance(void)
{
	return life_instance;
}

int k230_boot_life_run(void)
{
	struct boot_life_ops ops = { NULL, life_flush, life_delay };
	struct boot_life_cfg cfg;
	struct boot_life_result res;
	unsigned long fb_addr = CONFIG_K230_BARE_DISP_LOGO_FB_ADDR;
	unsigned long rec_addr = CONFIG_K230_BOOT_LIFE_RECORD_ADDR;
	uint32_t instance;

	life_instance = 0;
	/* The two windows must lie in the splash reservation: the scanout first,
	 * the record after it, as nix/boot-splash.nix defines them. */
	if (rec_addr < fb_addr + LIFE_FB_BYTES ||
	    rec_addr + GOL_RECORD_BYTES > fb_addr + CONFIG_K230_BOOT_LIFE_RESERVED_BYTES) {
		printf("boot life: record window 0x%lx is outside the reservation; skipped\n",
		       rec_addr);
		return -1;
	}

	instance = (uint32_t)get_ticks() | 1u;
	cfg.fb = map_sysmem(fb_addr, LIFE_FB_BYTES);
	cfg.record = map_sysmem(rec_addr, CONFIG_K230_BOOT_LIFE_WINDOW_BYTES);
	cfg.record_window = CONFIG_K230_BOOT_LIFE_WINDOW_BYTES;
	cfg.boot_instance = instance;
	cfg.seed = CONFIG_K230_BOOT_LIFE_SEED;
	cfg.frames = CONFIG_K230_BOOT_LIFE_FRAMES;
	cfg.frame_ms = CONFIG_K230_BOOT_LIFE_FRAME_MS;

	if (boot_life_stage1_run(&cfg, &ops, &res)) {
		printf("boot life: configuration rejected; logo left as is\n");
		return -1;
	}
	life_instance = res.instance;
	printf("boot life: %u generations, instance 0x%08x, grid hash 0x%08x, record at 0x%lx\n",
	       res.generation, res.instance, res.grid_hash, rec_addr);
	return 0;
}

static int do_k230_life(struct cmd_tbl *cmdtp, int flag, int argc, char *const argv[])
{
	return k230_boot_life_run() ? CMD_RET_FAILURE : CMD_RET_SUCCESS;
}

U_BOOT_CMD(
	k230_life, 1, 0, do_k230_life,
	"run the stage-1 Game of Life on the lit logo scanout",
	"- redraws the default pattern, advances it, publishes the state record"
);

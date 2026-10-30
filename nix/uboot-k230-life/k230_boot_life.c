// SPDX-License-Identifier: GPL-2.0+
/*
 * Stage-1 boot animation for the T-Display K230 (RM69A10).  Opt-in:
 * CONFIG_K230_BOOT_LIFE.  Runs a frame source (Game of Life today,
 * src/boot_frame.h) on top of the already-lit logo scanout and publishes its
 * state record for the next owner.
 *
 * Two drivers, same frames and same record:
 *   - cyclic (CONFIG_K230_BOOT_LIFE_CYCLIC, default): frame 0 is drawn at once,
 *     then one frame per period is drawn from the cyclic hook while U-Boot
 *     keeps working (SD reads, image checks).  Boot is not delayed by a sleep.
 *   - blocking: the whole run happens here, sleeping between frames.  Used when
 *     cyclic is configured off, when the `k230_life block` command is typed,
 *     and as the fallback if the cyclic session cannot start.
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
#include <time.h>
#ifdef CONFIG_K230_BOOT_LIFE_CYCLIC
#include <cyclic.h>
#endif

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

#ifdef CONFIG_K230_BOOT_LIFE_CYCLIC
static struct cyclic_info life_cyclic;
static struct bf_session life_session;
static struct bf_cfg life_cfg;
static struct bf_ops life_ops = { NULL, life_flush, life_delay };
static bool life_cyclic_active;
static unsigned life_cb_calls;
static unsigned long life_cb_us_total, life_cb_us_max;

static void life_cb(struct cyclic_info *c)
{
	unsigned long t0 = timer_get_us(), dt;
	int r = bf_advance(&life_session);

	dt = timer_get_us() - t0;
	life_cb_calls++;
	life_cb_us_total += dt;
	if (dt > life_cb_us_max)
		life_cb_us_max = dt;
	if (r <= 0) {
		cyclic_unregister(c);
		life_cyclic_active = false;
	}
}
#endif

/* Stop drawing.  Called by ft_board_setup() before the device tree is handed
 * over, so the record the kernel sees is final and checksum-consistent. */
void k230_boot_life_stop(void)
{
#ifdef CONFIG_K230_BOOT_LIFE_CYCLIC
	if (life_cyclic_active) {
		cyclic_unregister(&life_cyclic);
		life_cyclic_active = false;
	}
	if (life_cb_calls)
		printf("boot life: cyclic stopped at generation %u after %u callbacks, mean %lu us, max %lu us\n",
		       life_session.done, life_cb_calls, life_cb_us_total / life_cb_calls,
		       life_cb_us_max);
#endif
}

static int life_setup(struct bf_cfg *cfg, unsigned frames)
{
	unsigned long fb_addr = CONFIG_K230_BARE_DISP_LOGO_FB_ADDR;
	unsigned long rec_addr = CONFIG_K230_BOOT_LIFE_RECORD_ADDR;

	/* The two windows must lie in the splash reservation: the scanout first,
	 * the record after it, as nix/boot-splash.nix defines them. */
	if (rec_addr < fb_addr + LIFE_FB_BYTES ||
	    rec_addr + GOL_RECORD_BYTES > fb_addr + CONFIG_K230_BOOT_LIFE_RESERVED_BYTES) {
		printf("boot life: record window 0x%lx is outside the reservation; skipped\n",
		       rec_addr);
		return -1;
	}
	cfg->target.fb = map_sysmem(fb_addr, LIFE_FB_BYTES);
	cfg->target.stride_bytes = GOL_PANEL_W * 4u;
	cfg->target.width = GOL_PANEL_W;
	cfg->target.height = GOL_PANEL_H;
	cfg->record = map_sysmem(rec_addr, CONFIG_K230_BOOT_LIFE_WINDOW_BYTES);
	cfg->record_window = CONFIG_K230_BOOT_LIFE_WINDOW_BYTES;
	cfg->boot_instance = (uint32_t)get_ticks() | 1u;
	cfg->seed = CONFIG_K230_BOOT_LIFE_SEED;
	cfg->frames = frames;
	cfg->frame_ms = CONFIG_K230_BOOT_LIFE_FRAME_MS;
	return 0;
}

static int life_run_blocking(void)
{
	struct boot_life_ops ops = { NULL, life_flush, life_delay };
	struct boot_life_cfg cfg;
	struct boot_life_result res;
	struct bf_cfg c;

	if (life_setup(&c, CONFIG_K230_BOOT_LIFE_FRAMES))
		return -1;
	cfg.fb = c.target.fb;
	cfg.record = c.record;
	cfg.record_window = c.record_window;
	cfg.boot_instance = c.boot_instance;
	cfg.seed = c.seed;
	cfg.frames = c.frames;
	cfg.frame_ms = c.frame_ms;
	if (boot_life_stage1_run(&cfg, &ops, &res)) {
		printf("boot life: configuration rejected; logo left as is\n");
		return -1;
	}
	life_instance = res.instance;
	printf("boot life: %u generations (blocking), instance 0x%08x, grid hash 0x%08x, record at 0x%x\n",
	       res.generation, res.instance, res.grid_hash, CONFIG_K230_BOOT_LIFE_RECORD_ADDR);
	return 0;
}

int k230_boot_life_run(void)
{
	life_instance = 0;
#ifdef CONFIG_K230_BOOT_LIFE_CYCLIC
	k230_boot_life_stop();
	life_cb_calls = 0;
	life_cb_us_total = life_cb_us_max = 0;
	if (!life_setup(&life_cfg, CONFIG_K230_BOOT_LIFE_CYCLIC_MAX_FRAMES) &&
	    !bf_begin(&life_session, &life_cfg, &life_ops, &boot_life_source)) {
		life_instance = life_cfg.boot_instance;
		life_cyclic_active = true;
		cyclic_register(&life_cyclic, life_cb, (uint64_t)life_cfg.frame_ms * 1000ULL,
				"boot-life");
		printf("boot life: cyclic, frame 0 drawn, %u ms period, instance 0x%08x, record at 0x%x\n",
		       life_cfg.frame_ms, life_instance, CONFIG_K230_BOOT_LIFE_RECORD_ADDR);
		return 0;
	}
	printf("boot life: cyclic session did not start; falling back to the blocking loop\n");
#endif
	return life_run_blocking();
}

static int do_k230_life(struct cmd_tbl *cmdtp, int flag, int argc, char *const argv[])
{
	if (argc > 1 && !strcmp(argv[1], "stop")) {
		k230_boot_life_stop();
		return CMD_RET_SUCCESS;
	}
	if (argc > 1 && !strcmp(argv[1], "block")) {
		life_instance = 0;
		k230_boot_life_stop();
		return life_run_blocking() ? CMD_RET_FAILURE : CMD_RET_SUCCESS;
	}
	return k230_boot_life_run() ? CMD_RET_FAILURE : CMD_RET_SUCCESS;
}

U_BOOT_CMD(
	k230_life, 2, 0, do_k230_life,
	"run the stage-1 boot animation on the lit logo scanout",
	"       - start it (cyclic when built in, else blocking)\n"
	"k230_life block - run the blocking loop now\n"
	"k230_life stop  - stop drawing; the record stays valid"
);

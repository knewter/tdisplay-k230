#include "boot_life_stage1.h"

#include <string.h>

/* Game of Life as the first boot_frame producer (src/boot_frame.h).  State is
 * static: U-Boot's stack is small. */
static struct gol_state state;
static struct gol_grid prev;
static struct gol_grid next;
static unsigned redrawn;

static int life_start(void *ctx, const struct bf_target *t, uint32_t seed)
{
	(void)ctx;
	if (t->width != GOL_PANEL_W || t->height != GOL_PANEL_H || t->stride_bytes != GOL_PANEL_W * 4u)
		return -1;
	gol_state_init_default(&state, 1, seed);
	gol_render_xrgb(&state.grid, t->fb, t->stride_bytes);
	redrawn = 0;
	return 0;
}

static int life_step(void *ctx, const struct bf_target *t)
{
	(void)ctx;
	prev = state.grid;
	gol_step(&next, &prev);
	state.grid = next;
	state.generation++;
	redrawn += gol_render_xrgb_diff(&prev, &state.grid, t->fb, t->stride_bytes);
	return 0;
}

static long life_publish(void *ctx, uint8_t *out, size_t max, uint32_t instance, uint32_t *frame)
{
	(void)ctx;
	if (max < GOL_RECORD_BYTES)
		return -1;
	state.boot_instance = instance;
	state.owner = GOL_OWNER_UBOOT;
	state.frame_generation = state.generation;
	gol_record_encode(&state, out);
	*frame = state.generation;
	return GOL_RECORD_BYTES;
}

int boot_life_stage1_run(const struct boot_life_cfg *cfg, const struct boot_life_ops *ops,
			 struct boot_life_result *out)
{
	struct bf_source src = { "life", BF_SOURCE_LIFE, NULL, life_start, life_step, life_publish };
	struct bf_ops bops = { ops ? ops->ctx : NULL, ops ? ops->flush : NULL,
			       ops ? ops->delay_ms : NULL };
	struct bf_cfg c;
	struct bf_result r;

	memset(out, 0, sizeof(*out));
	if (!cfg || !ops || !cfg->fb || !cfg->record || cfg->record_window < GOL_RECORD_BYTES)
		return -1;
	c.target.fb = cfg->fb;
	c.target.stride_bytes = GOL_PANEL_W * 4u;
	c.target.width = GOL_PANEL_W;
	c.target.height = GOL_PANEL_H;
	c.record = cfg->record;
	c.record_window = cfg->record_window;
	c.boot_instance = cfg->boot_instance;
	c.seed = cfg->seed;
	c.frames = cfg->frames;
	c.frame_ms = cfg->frame_ms;
	if (bf_run(&c, &bops, &src, &r))
		return -1;
	out->generation = state.generation;
	out->instance = r.instance;
	out->grid_hash = gol_grid_hash(&state.grid);
	out->cells_redrawn = redrawn;
	return 0;
}

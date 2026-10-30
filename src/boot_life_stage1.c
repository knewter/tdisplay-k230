#include "boot_life_stage1.h"

#include <string.h>

/* Kept out of the stack: U-Boot's stack is small. */
static struct gol_state state;
static struct gol_grid prev;
static struct gol_grid next;
static uint8_t scratch[GOL_RECORD_BYTES];

static void publish(const struct boot_life_cfg *cfg, const struct boot_life_ops *ops)
{
	state.owner = GOL_OWNER_UBOOT;
	state.frame_generation = state.generation;
	gol_record_encode(&state, scratch);
	memcpy(cfg->record, scratch, GOL_RECORD_BYTES);
	ops->flush(ops->ctx, cfg->record, GOL_RECORD_BYTES);
}

int boot_life_stage1_run(const struct boot_life_cfg *cfg, const struct boot_life_ops *ops,
			 struct boot_life_result *out)
{
	unsigned i;

	memset(out, 0, sizeof(*out));
	if (!cfg || !ops || !cfg->fb || !cfg->record || cfg->record_window < GOL_RECORD_BYTES ||
	    !cfg->boot_instance)
		return -1;

	/* Invalidate whatever a previous boot or owner left in the window. */
	memset(cfg->record, 0, GOL_RECORD_HEADER_BYTES);
	ops->flush(ops->ctx, cfg->record, GOL_RECORD_HEADER_BYTES);

	gol_state_init_default(&state, cfg->boot_instance, cfg->seed);
	gol_render_xrgb(&state.grid, cfg->fb, GOL_PANEL_W * 4u);
	ops->flush(ops->ctx, cfg->fb, (size_t)GOL_PANEL_W * 4u * GOL_PANEL_H);
	publish(cfg, ops);

	for (i = 0; i < cfg->frames; i++) {
		if (cfg->frame_ms)
			ops->delay_ms(ops->ctx, cfg->frame_ms);
		prev = state.grid;
		gol_step(&next, &prev);
		state.grid = next;
		state.generation++;
		out->cells_redrawn += gol_render_xrgb_diff(&prev, &state.grid, cfg->fb,
							   GOL_PANEL_W * 4u);
		ops->flush(ops->ctx, cfg->fb, (size_t)GOL_PANEL_W * 4u * GOL_PANEL_H);
		publish(cfg, ops);
	}
	out->generation = state.generation;
	out->instance = state.boot_instance;
	out->grid_hash = gol_grid_hash(&state.grid);
	return 0;
}

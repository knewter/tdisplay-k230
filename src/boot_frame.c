#include "boot_frame.h"

#include <string.h>

#define BF_HEADER_BYTES 40u

/* Kept out of the stack: U-Boot's stack is small. */
static uint8_t scratch[8192];

static int publish(const struct bf_cfg *cfg, const struct bf_ops *ops, struct bf_source *src,
		   uint32_t *frame)
{
	long n = src->publish(src->ctx, scratch, cfg->record_window, cfg->boot_instance, frame);

	if (n < (long)BF_HEADER_BYTES || (size_t)n > cfg->record_window)
		return -1;
	memcpy(cfg->record, scratch, (size_t)n);
	ops->flush(ops->ctx, cfg->record, (size_t)n);
	return 0;
}

int bf_run(const struct bf_cfg *cfg, const struct bf_ops *ops, struct bf_source *src,
	   struct bf_result *out)
{
	unsigned i;
	uint32_t frame = 0;
	size_t fb_bytes;

	memset(out, 0, sizeof(*out));
	if (!cfg || !ops || !src || !src->start || !src->step || !src->publish ||
	    !cfg->target.fb || !cfg->record || !cfg->boot_instance ||
	    cfg->record_window < BF_HEADER_BYTES || cfg->record_window > sizeof(scratch))
		return -1;
	fb_bytes = cfg->target.stride_bytes * cfg->target.height;

	/* Invalidate whatever a previous boot or owner left in the window. */
	memset(cfg->record, 0, BF_HEADER_BYTES);
	ops->flush(ops->ctx, cfg->record, BF_HEADER_BYTES);

	if (src->start(src->ctx, &cfg->target, cfg->seed))
		return -1;
	ops->flush(ops->ctx, cfg->target.fb, fb_bytes);
	if (publish(cfg, ops, src, &frame))
		return -1;

	for (i = 0; i < cfg->frames; i++) {
		if (cfg->frame_ms)
			ops->delay_ms(ops->ctx, cfg->frame_ms);
		if (src->step(src->ctx, &cfg->target))
			break;
		ops->flush(ops->ctx, cfg->target.fb, fb_bytes);
		if (publish(cfg, ops, src, &frame))
			return -1;
	}
	out->frame = frame;
	out->instance = cfg->boot_instance;
	return 0;
}

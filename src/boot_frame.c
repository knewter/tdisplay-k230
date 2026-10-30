#include "boot_frame.h"

#include <string.h>

#define BF_HEADER_BYTES 40u

/* Kept out of the stack: U-Boot's stack is small. */
static uint8_t scratch[8192];

static int publish(const struct bf_session *s)
{
	const struct bf_cfg *cfg = s->cfg;
	uint32_t frame;
	long n = s->src->publish(s->src->ctx, scratch, cfg->record_window, cfg->boot_instance,
				 &frame);

	if (n < (long)BF_HEADER_BYTES || (size_t)n > cfg->record_window)
		return -1;
	memcpy(cfg->record, scratch, (size_t)n);
	s->ops->flush(s->ops->ctx, cfg->record, (size_t)n);
	return 0;
}

int bf_begin(struct bf_session *s, const struct bf_cfg *cfg, const struct bf_ops *ops,
	     struct bf_source *src)
{
	size_t fb_bytes;

	memset(s, 0, sizeof(*s));
	if (!cfg || !ops || !src || !src->start || !src->step || !src->publish ||
	    !cfg->target.fb || !cfg->record || !cfg->boot_instance ||
	    cfg->record_window < BF_HEADER_BYTES || cfg->record_window > sizeof(scratch))
		return -1;
	s->cfg = cfg;
	s->ops = ops;
	s->src = src;
	fb_bytes = cfg->target.stride_bytes * cfg->target.height;

	/* Invalidate whatever a previous boot or owner left in the window. */
	memset(cfg->record, 0, BF_HEADER_BYTES);
	ops->flush(ops->ctx, cfg->record, BF_HEADER_BYTES);

	if (src->start(src->ctx, &cfg->target, cfg->seed))
		return -1;
	ops->flush(ops->ctx, cfg->target.fb, fb_bytes);
	return publish(s);
}

int bf_advance(struct bf_session *s)
{
	struct bf_target t = s->cfg->target;
	size_t fb_bytes = t.stride_bytes * t.height;

	if (s->done >= s->cfg->frames)
		return 0;
	t.dirty_off = t.dirty_len = 0;
	if (s->src->step(s->src->ctx, &t)) {
		s->done = s->cfg->frames;
		return 0;
	}
	if (t.dirty_len && t.dirty_off + t.dirty_len <= fb_bytes)
		s->ops->flush(s->ops->ctx, (char *)t.fb + t.dirty_off, t.dirty_len);
	else
		s->ops->flush(s->ops->ctx, t.fb, fb_bytes);
	if (publish(s))
		return -1;
	s->done++;
	return s->done < s->cfg->frames;
}

int bf_run(const struct bf_cfg *cfg, const struct bf_ops *ops, struct bf_source *src,
	   struct bf_result *out)
{
	struct bf_session s;
	int r;

	memset(out, 0, sizeof(*out));
	if (bf_begin(&s, cfg, ops, src))
		return -1;
	for (;;) {
		if (cfg->frame_ms && s.done < cfg->frames)
			ops->delay_ms(ops->ctx, cfg->frame_ms);
		r = bf_advance(&s);
		if (r < 0)
			return -1;
		if (r == 0)
			break;
	}
	out->frame = s.done;
	out->instance = cfg->boot_instance;
	return 0;
}

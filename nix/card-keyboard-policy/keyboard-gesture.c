#include "keyboard-gesture.h"
#include <math.h>
#include <string.h>

static double clamp(double x) { return fmax(0, fmin(1, x)); }
static void own(struct kg_policy *p, int32_t id) {
	for (unsigned i=0;i<p->owned_count;i++) if (p->owned[i]==id) return;
	if (p->owned_count < 16) p->owned[p->owned_count++]=id;
	else if (p->overflow_contacts < 1024) p->overflow_contacts++;
}
static bool release(struct kg_policy *p, int32_t id) {
	for (unsigned i=0;i<p->owned_count;i++) if (p->owned[i]==id) {
		p->owned[i]=p->owned[--p->owned_count]; return true;
	}
	if (p->overflow_contacts) { p->overflow_contacts--; return true; }
	return false;
}
static bool owns(const struct kg_policy *p, int32_t id) {
	for (unsigned i=0;i<p->owned_count;i++) if (p->owned[i]==id) return true;
	return p->overflow_contacts != 0;
}
void kg_init(struct kg_policy *p, double height, bool reduced_motion) {
	memset(p, 0, sizeof(*p));
	p->mode = KG_IDLE;
	p->height = height > 0 ? height : 420;
	p->reduced_motion = reduced_motion;
}
unsigned kg_down(struct kg_policy *p, int32_t id, double x, double y,
	uint64_t ms, double output_height, bool keyboard_mapped, bool claimed_card,
	bool overlay_owns_input) {
	if (overlay_owns_input) return KG_NONE;
	if (keyboard_mapped && p->mode == KG_SHOWN &&
		y >= output_height - p->height - 56 && y < output_height - p->height) {
		p->mode = KG_GRIP_DRAG;
		p->first = id; p->first_live = true; p->second_live = false;
		p->grip_start = y; p->start_progress = p->progress = 1;
		p->velocity = 0; p->last_ms = p->sample_ms = ms;
		own(p,id);
		return KG_CONSUME;
	}
	if (p->mode == KG_GRIP_DRAG || p->mode == KG_SHOW_DRAG) {
		/* Additional contact cancels gesture, restoring shown keyboard. */
		p->target_shown = true; p->mode = KG_SETTLE;
		p->velocity = 0; p->last_ms = ms;
		own(p,id);
		return KG_CONSUME;
	}
	if (p->owned_count || p->overflow_contacts || p->mode == KG_SETTLE ||
		p->mode == KG_WAIT_SURFACE || p->mode == KG_WAIT_UNMAP) {
		own(p,id);
		if (p->mode == KG_WAIT_SURFACE) {
			p->target_shown=false; p->mode=KG_SETTLE; p->velocity=0; p->last_ms=ms;
		}
		return KG_CONSUME;
	}
	if (keyboard_mapped || p->mode == KG_SHOWN) return KG_NONE;
	if (p->mode == KG_IDLE && y >= output_height - 72 && y < output_height) {
		p->mode = KG_CHORD; p->first = id; p->first_live = true;
		p->first_x = x; p->first_y = y; p->first_ms = ms;
		return KG_NONE; /* first contact remains ordinary card input */
	}
	if (p->mode == KG_CHORD && id != p->first &&
		ms >= p->first_ms && ms - p->first_ms <= 180 &&
		!claimed_card && y >= output_height - 72 && y < output_height &&
		fabs(x - p->first_x) >= 24 && fabs(x - p->first_x) <= 480) {
		p->second = id; p->second_live = true;
		p->second_x = x; p->second_y = y;
		p->start_centroid = (p->first_y + y) * .5;
		p->start_progress = p->progress = 0;
		p->velocity = 0; p->last_ms = p->sample_ms = ms;
		p->mode = KG_WAIT_SURFACE;
		own(p,p->first); own(p,id);
		return KG_CONSUME | KG_CANCEL_CARD;
	}
	if (p->mode == KG_CHORD) p->mode = KG_IDLE;
	return KG_NONE;
}
unsigned kg_motion(struct kg_policy *p, int32_t id, double x, double y, uint64_t ms) {
	(void)x;
	bool owned = owns(p,id);
	if (p->mode == KG_CHORD && id == p->first) {
		if (fabs(y - p->first_y) > 12 || ms > p->first_ms + 180) p->mode = KG_IDLE;
		return KG_NONE;
	}
	if (p->mode == KG_WAIT_SURFACE) {
		if (id == p->first) p->first_y = y;
		if (id == p->second) p->second_y = y;
		if (!p->show_requested &&
			p->start_centroid - (p->first_y + p->second_y) * .5 >= 16) {
			p->show_requested = true;
			return KG_CONSUME | KG_SHOW;
		}
		return KG_CONSUME;
	}
	if (p->mode != KG_SHOW_DRAG && p->mode != KG_GRIP_DRAG)
		return owned ? KG_CONSUME : KG_NONE;
	if (p->mode == KG_SHOW_DRAG) {
		if (id == p->first) p->first_y = y;
		else if (id == p->second) p->second_y = y;
		else return KG_CONSUME;
	}
	if (p->mode == KG_GRIP_DRAG && id != p->first) return KG_CONSUME;
	double next = p->mode == KG_SHOW_DRAG ?
		clamp(p->start_progress + (p->start_centroid - (p->first_y + p->second_y) * .5) / p->height) :
		clamp(p->start_progress - (y - p->grip_start) / p->height);
	if (ms > p->sample_ms && ms - p->sample_ms <= 80) {
		double dt = (double)(ms - p->sample_ms) / 1000;
		p->velocity = fmax(-4, fmin(4, (next - p->progress) / dt));
	} else if (ms > p->sample_ms + 80) p->velocity = 0;
	p->sample_ms = p->last_ms = ms;
	if (fabs(next - p->progress) < 0.00001) return KG_CONSUME;
	p->progress = next;
	return KG_CONSUME | KG_DIRTY;
}
unsigned kg_up(struct kg_policy *p, int32_t id, uint64_t ms) {
	bool owned = release(p,id);
	if (p->mode == KG_SETTLE && (p->first_live || p->second_live)) {
		if (id == p->first) p->first_live = false;
		else if (id == p->second) p->second_live = false;
		return KG_CONSUME;
	}
	if (p->mode == KG_CHORD && id == p->first) {
		p->mode = KG_IDLE; return KG_NONE;
	}
	if (p->mode == KG_WAIT_SURFACE || p->mode == KG_SHOW_DRAG) {
		if (id == p->first) p->first_live = false;
		else if (id == p->second) p->second_live = false;
		else return KG_CONSUME;
		if (p->first_live && p->second_live) return KG_CONSUME;
		if (p->mode == KG_WAIT_SURFACE && !p->show_requested) {
			p->mode=KG_IDLE;
			return KG_CONSUME;
		}
	} else if (p->mode == KG_GRIP_DRAG && id != p->first) return KG_CONSUME;
	else if (p->mode != KG_GRIP_DRAG) return owned ? KG_CONSUME : KG_NONE;
	if (ms > p->sample_ms + 80) p->velocity = 0;
	p->target_shown = p->progress + p->velocity * .09 >= .5;
	p->mode = KG_SETTLE; p->last_ms = ms;
	return KG_CONSUME | KG_DIRTY;
}
unsigned kg_surface(struct kg_policy *p, bool mapped) {
	if (mapped && p->mode == KG_WAIT_SURFACE && p->show_requested) {
		p->mode = KG_SHOW_DRAG;
		p->progress = clamp((p->start_centroid -
			(p->first_y + p->second_y) * .5) / p->height);
		p->start_progress = 0;
		return KG_DIRTY;
	}
	if (mapped && (p->mode == KG_IDLE || p->mode == KG_CHORD)) {
		p->mode = KG_SHOWN; p->progress = 1;
		return KG_DIRTY;
	}
	if (!mapped && p->mode != KG_IDLE && p->mode != KG_CHORD &&
		p->mode != KG_WAIT_SURFACE) {
		bool had = p->progress > 0;
		int32_t ids[16]; unsigned n=p->owned_count, overflow=p->overflow_contacts;
		memcpy(ids,p->owned,n*sizeof(*ids));
		kg_init(p, p->height, p->reduced_motion);
		memcpy(p->owned,ids,n*sizeof(*ids));p->owned_count=n;
		p->overflow_contacts=overflow;
		return had ? KG_DIRTY : KG_NONE;
	}
	return KG_NONE;
}
unsigned kg_tick(struct kg_policy *p, uint64_t ms) {
	if (p->mode == KG_WAIT_SURFACE && p->show_requested &&
		ms > p->last_ms + 750) {
		unsigned action=kg_cancel(p);
		return action | KG_HIDE;
	}
	if (p->mode != KG_SETTLE || ms <= p->last_ms) return KG_NONE;
	double dt = (double)(ms - p->last_ms) / 1000;
	p->last_ms = ms;
	double target = p->target_shown ? 1 : 0;
	double omega = p->reduced_motion ? 32 : 18;
	/* Closed-form critically damped update for actual elapsed time. */
	double displacement = p->progress - target;
	double component = p->velocity + omega * displacement;
	double decay = exp(-omega * dt);
	p->progress = clamp(target + (displacement + component * dt) * decay);
	p->velocity = (p->velocity - omega * component * dt) * decay;
	if ((fabs(p->progress - target) < .002 && fabs(p->velocity) < .04) ||
		(p->progress == target && (target == 0 ? p->velocity <= 0 : p->velocity >= 0))) {
		p->progress = target; p->velocity = 0;
		p->mode = target ? KG_SHOWN : KG_WAIT_UNMAP;
		return KG_DIRTY | (target ? KG_NONE : KG_HIDE);
	}
	return KG_DIRTY;
}
unsigned kg_cancel(struct kg_policy *p) {
	if (p->mode == KG_SHOWN && p->owned_count == 0 &&
		p->overflow_contacts == 0) return KG_NONE;
	bool mapped = p->progress > 0 || p->mode == KG_SHOWN || p->mode == KG_GRIP_DRAG;
	bool requested = p->show_requested;
	int32_t ids[16]; unsigned n=p->owned_count, overflow=p->overflow_contacts;
	memcpy(ids,p->owned,n*sizeof(*ids));
	kg_init(p, p->height, p->reduced_motion);
	memcpy(p->owned,ids,n*sizeof(*ids));p->owned_count=n;
	p->overflow_contacts=overflow;
	p->progress = mapped ? 1 : 0;
	p->mode = mapped ? KG_SHOWN : KG_IDLE;
	return (mapped ? KG_DIRTY : KG_NONE) | (requested && !mapped ? KG_HIDE : KG_NONE);
}

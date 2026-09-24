#ifndef K230_KEYBOARD_GESTURE_H
#define K230_KEYBOARD_GESTURE_H
#include <stdbool.h>
#include <stdint.h>

enum kg_mode { KG_IDLE, KG_CHORD, KG_WAIT_SURFACE, KG_SHOW_DRAG, KG_SHOWN,
	KG_GRIP_DRAG, KG_SETTLE, KG_WAIT_UNMAP };
enum kg_action { KG_NONE = 0, KG_CONSUME = 1, KG_SHOW = 2, KG_HIDE = 4,
	KG_DIRTY = 8, KG_CANCEL_CARD = 16 };
struct kg_policy {
	enum kg_mode mode;
	int32_t first, second;
	uint64_t first_ms, last_ms, sample_ms;
	double first_x, first_y, second_x, second_y, start_centroid;
	double grip_start, start_progress, progress, velocity;
	double height;
	bool first_live, second_live, reduced_motion, target_shown;
	bool show_requested;
	int32_t owned[16];
	unsigned owned_count;
	unsigned overflow_contacts;
};
void kg_init(struct kg_policy *p, double height, bool reduced_motion);
/* `claimed_card` is true after one-finger card motion has qualified. */
unsigned kg_down(struct kg_policy *p, int32_t id, double x, double y,
	uint64_t ms, double output_height, bool keyboard_mapped, bool claimed_card,
	bool overlay_owns_input);
unsigned kg_motion(struct kg_policy *p, int32_t id, double x, double y, uint64_t ms);
unsigned kg_up(struct kg_policy *p, int32_t id, uint64_t ms);
unsigned kg_surface(struct kg_policy *p, bool mapped);
unsigned kg_tick(struct kg_policy *p, uint64_t ms);
unsigned kg_cancel(struct kg_policy *p);
#endif

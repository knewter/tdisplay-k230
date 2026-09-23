/* Small input policy shared by the compositor and executable host tests. */
#ifndef K230_CARD_MODEL_H
#define K230_CARD_MODEL_H
#include <math.h>
#include <stdbool.h>
#include <string.h>

enum card_action { CARD_NONE, CARD_SELECT, CARD_CLOSE, CARD_CANCEL };
struct card_gesture {
	int contact, selected;
	bool down;
	double start_x, start_y, dx, dy, distance;
};
static inline bool card_opted_in(const char *value) {
	return value && strcmp(value, "1") == 0;
}
static inline int card_allowlist(const char *id) {
	if (!id)
		return -1;
	if (strcmp(id, "k230.card.one") == 0)
		return 0;
	if (strcmp(id, "k230.card.two") == 0)
		return 1;
	return -1;
}
static inline bool card_down(struct card_gesture *g, int contact, int selected, double x,
							 double y) {
	if (g->down)
		return false;
	*g = (struct card_gesture){
		.contact = contact, .selected = selected, .down = true, .start_x = x, .start_y = y};
	return true;
}
static inline void card_motion(struct card_gesture *g, int contact, double x, double y) {
	if (!g->down || contact != g->contact)
		return;
	g->dx = x - g->start_x;
	g->dy = y - g->start_y;
	double distance = hypot(g->dx, g->dy);
	if (distance > g->distance)
		g->distance = distance;
}
static inline enum card_action card_up(struct card_gesture *g, int contact) {
	if (!g->down || contact != g->contact)
		return CARD_NONE;
	g->down = false;
	if (g->selected < 0)
		return CARD_NONE;
	if (g->dy < -120 && fabs(g->dy) > fabs(g->dx))
		return CARD_CLOSE;
	if (g->distance < 20)
		return CARD_SELECT;
	return CARD_NONE;
}
#endif

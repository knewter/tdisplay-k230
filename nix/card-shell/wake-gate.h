#ifndef CARD_SHELL_WAKE_GATE_H
#define CARD_SHELL_WAKE_GATE_H
/* A touch on a dark display wakes it and is consumed, never delivered to the
 * app underneath (the power key's wake is consumed the same way). The first
 * contact that lands on a dark panel starts a swallowed sequence; it, and
 * any contact that joins it, are consumed until every swallowed contact has
 * lifted. Contacts that went down while the display was lit are never
 * swallowed, so a screen that darkens mid-touch cannot strand an app. */
#include <stdbool.h>
#include <stdint.h>
#define WAKE_GATE_MAX 16
struct wake_gate {
	int32_t ids[WAKE_GATE_MAX];
	unsigned count;
};
static inline bool wake_gate_has(const struct wake_gate *gate, int32_t id) {
	for (unsigned i = 0; i < gate->count; i++)
		if (gate->ids[i] == id) return true;
	return false;
}
/* Returns true when the contact is consumed. *wake is set when the display
 * must now be lit (only for the contact that opens the sequence). */
static inline bool wake_gate_down(struct wake_gate *gate, int32_t id, bool dark, bool *wake) {
	*wake = false;
	if (gate->count == 0 && !dark) return false;
	if (gate->count == 0) *wake = true;
	if (!wake_gate_has(gate, id) && gate->count < WAKE_GATE_MAX)
		gate->ids[gate->count++] = id;
	return true;
}
static inline bool wake_gate_motion(const struct wake_gate *gate, int32_t id) {
	return wake_gate_has(gate, id);
}
static inline bool wake_gate_up(struct wake_gate *gate, int32_t id) {
	for (unsigned i = 0; i < gate->count; i++) {
		if (gate->ids[i] != id) continue;
		gate->ids[i] = gate->ids[--gate->count];
		return true;
	}
	return false;
}
#endif

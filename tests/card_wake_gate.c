#include "wake-gate.h"
#include <assert.h>
int main(void) {
	struct wake_gate g = {0};
	bool wake;
	/* Lit display: nothing is consumed. */
	assert(!wake_gate_down(&g, 1, false, &wake) && !wake);
	assert(!wake_gate_motion(&g, 1));
	assert(!wake_gate_up(&g, 1));
	/* Dark: the first contact wakes and is consumed through its release. */
	assert(wake_gate_down(&g, 2, true, &wake) && wake);
	assert(wake_gate_motion(&g, 2));
	assert(wake_gate_up(&g, 2));
	assert(!wake_gate_motion(&g, 2) && !wake_gate_up(&g, 2));
	/* A second finger joins the swallowed sequence without a second wake,
	 * even though the display is now lit, and the sequence outlives the first. */
	assert(wake_gate_down(&g, 3, true, &wake) && wake);
	assert(wake_gate_down(&g, 4, false, &wake) && !wake);
	assert(wake_gate_up(&g, 3));
	assert(wake_gate_motion(&g, 4));
	assert(wake_gate_down(&g, 5, false, &wake) && !wake);
	assert(wake_gate_up(&g, 4) && wake_gate_up(&g, 5));
	/* Sequence over: a fresh touch on the lit display reaches the app. */
	assert(!wake_gate_down(&g, 6, false, &wake) && !wake);
	/* A contact that began lit is not swallowed when the panel then goes dark. */
	assert(!wake_gate_motion(&g, 6) && !wake_gate_up(&g, 6));
	/* A repeated down for a tracked id does not duplicate it. */
	assert(wake_gate_down(&g, 7, true, &wake));
	assert(wake_gate_down(&g, 7, true, &wake) && !wake);
	assert(wake_gate_up(&g, 7) && g.count == 0);
	return 0;
}

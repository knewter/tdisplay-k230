/* Executes the exact policy compiled into Sway; no compositor API simulation. */
#include "../nix/card-composition-probe/model.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
	assert(!card_opted_in(NULL));
	assert(!card_opted_in(""));
	assert(!card_opted_in("0"));
	assert(!card_opted_in("true"));
	assert(card_opted_in("1"));
	assert(card_allowlist(NULL) == -1);
	assert(card_allowlist("foot") == -1);
	assert(card_allowlist("k230.card.one.extra") == -1);
	assert(card_allowlist("k230.card.one") == 0);
	assert(card_allowlist("k230.card.two") == 1);
	struct card_gesture g = {0};
	assert(card_down(&g, 31, 1, 200, 600));
	for (int n = 1; n <= 100; n++) {
		card_motion(&g, 31, 200 + n, 600 - n);
		assert(g.dx == n && g.dy == -n);
	}
	card_motion(&g, 32, 0, 0);
	assert(g.dx == 100);
	assert(card_up(&g, 32) == CARD_NONE && g.down);
	assert(card_up(&g, 31) == CARD_NONE && !g.down);
	assert(card_down(&g, 3, 0, 200, 300));
	assert(!card_down(&g, 4, 1, 100, 100));
	assert(g.contact == 3 && g.selected == 0);
	card_motion(&g, 3, 210, 140);
	assert(card_up(&g, 3) == CARD_CLOSE);
	assert(card_down(&g, 5, 1, 200, 700));
	card_motion(&g, 5, 205, 704);
	assert(card_up(&g, 5) == CARD_SELECT);
	assert(card_down(&g, 6, 1, 200, 700));
	card_motion(&g, 6, 240, 700);
	card_motion(&g, 6, 200, 700);
	assert(card_up(&g, 6) == CARD_NONE); /* drag back is not accidental tap */
	assert(card_down(&g, 7, -1, 50, 1200));
	assert(card_up(&g, 7) == CARD_NONE);
	g.down = false; /* same cancellation used by compositor leave/unmap */
	assert(card_up(&g, 7) == CARD_NONE);
	puts("PASS exact-opt-in allowlist two-app-drag contact-isolation select close-threshold "
		 "cancellation");
}

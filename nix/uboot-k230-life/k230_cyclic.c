// SPDX-License-Identifier: GPL-2.0+
/* See include/cyclic.h: minimal back-port of the 2023.01 cyclic framework. */
#include <common.h>
#include <time.h>
#include <cyclic.h>

static struct cyclic_info *cyclic_head;
static bool cyclic_busy;

void cyclic_register(struct cyclic_info *c, cyclic_func_t func, uint64_t delay_us,
		     const char *name)
{
	struct cyclic_info **pp;

	cyclic_unregister(c);
	c->func = func;
	c->delay_us = delay_us;
	c->delay_ticks = usec_to_tick(delay_us);
	c->next_tick = get_ticks() + c->delay_ticks;
	c->name = name;
	c->next = NULL;
	for (pp = &cyclic_head; *pp; pp = &(*pp)->next)
		;
	*pp = c;
}

void cyclic_unregister(struct cyclic_info *c)
{
	struct cyclic_info **pp;

	for (pp = &cyclic_head; *pp; pp = &(*pp)->next) {
		if (*pp == c) {
			*pp = c->next;
			c->next = NULL;
			return;
		}
	}
}

void cyclic_run(void)
{
	struct cyclic_info *c, *next;
	uint64_t now;

	if (!cyclic_head || cyclic_busy)
		return;
	cyclic_busy = true;
	now = get_ticks();
	for (c = cyclic_head; c; c = next) {
		next = c->next; /* the callback may unregister itself */
		if (now >= c->next_tick) {
			/* Deadline from now, not from the last deadline: a slow callback
			 * must not be called back-to-back to "catch up" while mmc waits. */
			c->next_tick = now + c->delay_ticks;
			c->func(c);
		}
	}
	cyclic_busy = false;
}

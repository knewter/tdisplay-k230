/* SPDX-License-Identifier: GPL-2.0+ */
/*
 * Minimal back-port of U-Boot's cyclic framework (upstream: common/cyclic.c,
 * include/cyclic.h, v2023.01).  This tree is 2022.10 and has neither.  The
 * names, argument order and semantics of cyclic_register(), cyclic_unregister()
 * and schedule() follow upstream so the project can drop this file when the
 * vendor tree moves to 2023.01 or later and use CONFIG_CYCLIC directly.
 *
 * Differences from upstream, on purpose: a singly linked list of static
 * entries (no hlist, no gd field, no `cyclic` command), a single run-level
 * re-entrancy guard, deadlines kept in timer ticks, and callbacks run from
 * WATCHDOG_RESET() (include/watchdog.h patch), which lib/time.c's udelay() and
 * the LZMA/zlib/gunzip loops already call.
 */
#ifndef __CYCLIC_H
#define __CYCLIC_H

#include <linux/types.h>

struct cyclic_info;
typedef void (*cyclic_func_t)(struct cyclic_info *c);

struct cyclic_info {
	cyclic_func_t func;
	uint64_t delay_us;
	uint64_t delay_ticks;
	uint64_t next_tick;
	const char *name;
	struct cyclic_info *next;
};

void cyclic_register(struct cyclic_info *c, cyclic_func_t func, uint64_t delay_us,
		     const char *name);
void cyclic_unregister(struct cyclic_info *c);
/* Run every callback whose deadline has passed; never re-entered. */
void cyclic_run(void);

static inline void schedule(void)
{
	cyclic_run();
}

#endif

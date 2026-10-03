/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_K230_UART_PROGRESS_H
#define _LINUX_K230_UART_PROGRESS_H
#include <linux/types.h>

enum k230_uart_progress_state {
	K230_UP_OK, K230_UP_LIFETIME_BUSY, K230_UP_PORT_BUSY,
	K230_UP_UNAVAILABLE, K230_UP_BINDING, K230_UP_CHANGED,
};
struct k230_uart_progress_snapshot {
	u32 state, irq, irq_count, rx, tx, frame, parity, overrun, buf_overrun;
	u32 ier, read_mask, ignore_mask, uartclk;
};
void k230_uart_progress_snapshot(struct k230_uart_progress_snapshot *out);
unsigned int k230_uart_progress_timer_irq(void);
#endif

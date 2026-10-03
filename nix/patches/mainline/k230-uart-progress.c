// SPDX-License-Identifier: GPL-2.0
/* Finite cached observations. No console/TTY/hardware operations here. */
#include <linux/init.h>
#include <linux/jiffies.h>
#include <linux/k230_uart_progress.h>
#include <linux/kernel_stat.h>
#include <linux/kthread.h>
#include <linux/ktime.h>
#include <linux/string.h>
#include <linux/delay.h>
#include <asm/sbi.h>

#define K230_UP_SAMPLES 6
#define K230_UP_DELAY_MS 5000
#define K230_UP_RECORD_SIZE 256
static bool k230_uart_progress_enabled;
/* Ordinary data; alignment and size guarantee containment in a 4KiB page. */
static char k230_uart_progress_record[K230_UP_RECORD_SIZE] __aligned(256);

static int __init k230_uart_progress_setup(char *value)
{
	k230_uart_progress_enabled = value && !strcmp(value, "1");
	return 1;
}
__setup("k230.uart_progress=", k230_uart_progress_setup);

static int k230_uart_progress_worker(void *unused)
{
	unsigned int sample, first_irq = 0;
	(void)unused;
	for (sample = 0; sample < K230_UP_SAMPLES; sample++) {
		struct k230_uart_progress_snapshot s;
		unsigned int timer_irq, uart_count = 0, timer_count = 0;
		u64 time_ns, ticks;
		int length;

		if (kthread_should_stop())
			break;
		/* Six finite sleeps; no polling, RT priority or CPU affinity. */
		msleep(K230_UP_DELAY_MS);
		if (kthread_should_stop())
			break;
		k230_uart_progress_snapshot(&s);
		if (s.state == K230_UP_OK) {
			if (first_irq && first_irq != s.irq) {
				memset(&s, 0, sizeof(s));
				s.state = K230_UP_CHANGED;
			} else {
				first_irq = s.irq;
				uart_count = s.irq_count;
			}
		}
		timer_irq = k230_uart_progress_timer_irq();
		if (timer_irq)
			timer_count = kstat_irqs_usr(timer_irq);
		time_ns = ktime_get_ns();
		ticks = get_jiffies_64();
		/* Formatting and the single firmware call are outside every lock. */
		length = snprintf(k230_uart_progress_record, sizeof(k230_uart_progress_record),
			"\nK230_UP1 n=%u s=%u j=%016llx t=%016llx u=%08x ti=%08x ui=%08x tc=%08x rx=%08x tx=%08x fe=%08x pe=%08x oe=%08x be=%08x ie=%08x rm=%08x im=%08x hz=%08x\n",
			sample, s.state, (unsigned long long)ticks, (unsigned long long)time_ns,
			s.irq, timer_irq, uart_count, timer_count, s.rx, s.tx, s.frame,
			s.parity, s.overrun, s.buf_overrun, s.ier, s.read_mask, s.ignore_mask, s.uartclk);
		if (length <= 0 || (size_t)length >= sizeof(k230_uart_progress_record))
			break;
		/* Count/error is deliberately not retried or sent through printk. */
		(void)sbi_debug_console_write(k230_uart_progress_record, length);
	}
	return 0;
}

static int __init k230_uart_progress_init(void)
{
	struct task_struct *task;
	if (!k230_uart_progress_enabled || !sbi_debug_console_available)
		return 0;
	task = kthread_run(k230_uart_progress_worker, NULL, "k230-uart-progress");
	return IS_ERR(task) ? PTR_ERR(task) : 0;
}
late_initcall(k230_uart_progress_init);

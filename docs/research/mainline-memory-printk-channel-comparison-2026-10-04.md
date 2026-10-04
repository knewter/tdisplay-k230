# Separate Linux-console output from the final firmware call

Both [zero-input](../evidence/mainline-uart-progress-memory/no-stimulus-physical-2026-10-04/README.md)
and [idle-polling](../evidence/mainline-uart-progress-memory/poll-idle-physical-2026-10-04/README.md)
reached exact args/Bash without a final Memory summary. Each is inconclusive:
observer scheduling/timeout and its final explicit DBCN call remain unobserved.
A separate Linux printk output channel can test that last dependency. This is
planned instrumentation, not a diagnosed fault or useful mainline boot.

Read-only actual DT audit decoded the selected lznjjfx1 DT: one cpu@0/hart0,
27 MHz timebase, riscv,cpu-intc, no SSTC in either ISA declaration. CLINT local
interrupts 3/7 and PLIC external contexts 11/9 are distinct. Realized source
`/nix/store/f7xg031sjb9dy3bswm5s3qjr9xwx1g02-linux-mainline-k230-uart-progress-memory-src`
uses the resolved SSTC capability in `drivers/clocksource/timer-riscv.c` lines
198–201; without it the expected compare path is SBI set_timer (lines 47–61).
Runtime path/delivery remains UNVERIFIED. Pinned vendor source
`/nix/store/pn7bm6ck5a3x6pnk1ng30hlf24qn85jx-source`
(commit 7d4e1f444f461dbe3833bd99a4640e7b6c2cd529) has matching 27 MHz/no-SSTC
declarations in `arch/riscv/boot/dts/canaan/k230.dtsi` and the same timer feature
check. No advertised mismatch grounds a timer-DT switch. Removing absent SSTC
changes nothing; adding it assumes unsupported CSR capability. The fallback ISA
boot option does not override the present extension list.

Saved polling UART has exactly one UART0 0x91400000→ttyS0 registration and one
`printk: console [ttyS0] enabled`. No tty0/SBI bootconsole registration or
`earlycon=`/`keep_bootcon` argument was observed. Selected `8250_core.c` lines
398–411/524–534 binds ttyS callbacks to serial8250_console_write with CON_NBCON;
`8250_dw.c` maps the UART and registers that port. This grounds the registered
Linux backend, not later liveness or which callback emitted every captured byte.
The firmware DBCN capability banner describes the separate explicit SBI route.

Matching 1pvqbm4 dev config has PRINTK, PRINTK_TIME, PRINTK_EXECUTION_CTX,
SERIAL_8250_CONSOLE and SERIAL_8250_DW all built in. Observed console framing is
only a six-decimal timestamp prefix followed by payload and CRLF, for example
`[    4.549880] ` before the public /bin/sh milestone. No execution-context field
was observed despite the configuration option. Actual config has
`# CONFIG_PRINTK_CALLER is not set`: `kernel/printk/printk.c` lines 1355–1394
formats six-decimal timestamps and adds a caller prefix only under PRINTK_CALLER.
PRINTK_EXECUTION_CTX captures metadata without forcing a kthread prefix (lines
2144–2167/2246–2250). Qualify disabled CALLER together with PRINTK_TIME before
accepting timestamp-only framing. Future UMK framing is UNVERIFIED; use the
observed convention, never broad arbitrary-prefix repair.

Keep the Memory worker's six sleeps/cached snapshots/atomic publication and the
observer's one 45-second completion wait and acquire snapshot. A separately gated
variant replaces only that observer's final explicit DBCN attempt with one
ordinary KERN_INFO/pr_info public K230_UMK1 record, retaining the same bounded
fields. Include a leading newline in that same call: the already observed Bash
prompt has no trailing newline. Selected `kernel/printk/printk.c` lines 1434–1489
adds a timestamp prefix to each message line, including an initial empty line;
that separator leaves the following UMK line independently parseable. Without
it, prompt and timestamp can share one physical UART line. Native fixtures must
check exact leading-newline bytes; controller fixtures must model prefixed blank
line plus prefixed summary, without stripping prompts. Physical framing remains
UNVERIFIED. Log level 7 already includes KERN_INFO. Use registered console ownership;
no force flush, emergency print, raw MMIO, IRQ changes, fallback or second channel.
Base zero-input arguments are retained; do not combine the nohlt intervention.
Every previous source/config/package/trial identity remains available unchanged.

A qualified fresh UMK record would establish progress through observer snapshot/
formatting and Linux console output while avoiding the final explicit DBCN call.
It would not prove printk returned or explain the missing firmware record. The
Linux backend itself masks/restores IER and has ownership-reacquire loops
(`8250_port.c` lines 3447–3457/3493–3526). Its scheduling/locking/IRQ behavior is
another intervention, without a wall-clock return guarantee. Missing UMK still
leaves timer/observer/printk/nbcon/UART unknown. Native/object/build evidence,
actual controller qualification, physical summary and protected recovery remain
separate gates; ordinary /init/root/panel/glass task 5b.5 stays open.

# Memory-progress comparison after variable reporter output

Evidence: [PostSample physical capture](../evidence/mainline-uart-progress-post-sample/physical-2026-10-03/README.md)
observed worker-entry only, one stimulus, no receipt/samples/new points in180.0975s.
The previous Breadcrumbs capture reached n0/n1 and receipt. Neither establishes
a stable stall location, or a cause. Normal recovery for PostSample is pending.

Read-only source review used pinned OpenSBI1.4 source
`/nix/store/k6kih6q1vh5nashsgaz96ch012742s8z-source`:

| File | Lines | SHA256 | Finding |
| --- | --- | --- | --- |
| lib/sbi/sbi_ecall_dbcn.c | 45–55 | 854a663c43fd4f408dff2ab9e04038f33fa552581e7a6db5315e56f1b2010e28 | map, sbi_nputs, unmap, return |
| lib/sbi/sbi_console.c | 80–86 | 07045de213aae2055d43f5662d2b6e3c654d8ac9cf24ff5b9f11e16ca548f7b5 | output spinlock around nputs |
| lib/utils/serial/uart8250.c | 74–79 | e354cb2247cd1d0ac7c6b649c1e1b94db47c459de18f0138026d8d5bf13afe9b | unbounded THRE polling before THR write |

The nine-file vendor overlay listed in nix/opensbi-k230.nix does not replace
these files. Exact byte correspondence with the board's installed firmware has
not been proved by this audit. A one-attempt kernel ECALL has no firmware
wall-clock bound; a fully visible record can precede lock release/unmap/return.

Selected kernel source
`/nix/store/wnvbxaiqgbhhajsajy5mlpn36zf8alga-linux-mainline-k230-uart-progress-post-sample-src`:
`kernel/time/sleep_timeout.c` SHA444ae37a7ea7444361c084828d2f68a592aa1401873240d09b85aabb88c5026f
at313–318 loops jiffy-based sleep, at93–105 arms/schedules/deletes its timer,
and at23–27 wakes the task. `drivers/tty/serial/8250/8250.h`
SHA69523b42abee40768f66a850b40ae642a827cdab86b4790c8f4b965e96775537
at137–153 preserves LSR read-clear error bits. Direct polling requires more
ownership/nbcon review and is not currently qualified as side-effect-free.

Recommended intervention: separately selected worker keeps six sleeps/cached
snapshots but suppresses every worker DBCN/printk call, publishing finite progress
in ordinary memory. An independent normal-priority observer waits with a finite
kernel timeout, then makes one final aligned bounded-size DBCN summary attempt.
The summary records state before that call; it does not prove its own return.
A received completion supports progress when repeated worker output is removed,
not a firmware root cause. No summary leaves scheduling/observer/output unknown;
an M-mode stall on the executing hart can prevent any S-mode observer or timeout.
No firmware/MMIO/IRQ/TTY/PID1/clock/priority changes are included.

<!-- UNVERIFIED: this comparison has not been implemented, built or run. -->

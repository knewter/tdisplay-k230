# A same-image idle-polling discriminator

The [zero-input physical capture](../evidence/mainline-uart-progress-memory/no-stimulus-physical-2026-10-04/README.md)
reached Bash but no summary, with no candidate stimulus. A next comparison can
remove idle entry while retaining the exact already-built Memory image. This
is a diagnostic hypothesis; idle failure and useful mainline boot are **UNVERIFIED**.

Read-only review used realized source
`/nix/store/f7xg031sjb9dy3bswm5s3qjr9xwx1g02-linux-mainline-k230-uart-progress-memory-src`,
matching dev `/nix/store/1pvqbm4r3gqcvsabgkz5wvrpxfbk5k1v-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev`
and Image in the lznjjfx1 bundle. Root independently verified:

- Full `.config` SHA256 `52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`;
  `CONFIG_GENERIC_IDLE_POLL_SETUP=y` appears exactly once. `CONFIG_CPU_IDLE=y`
  and `CONFIG_RISCV_SBI_CPUIDLE=y` are also selected (lines 565, 576, 693).
- `kernel/sched/idle.c` SHA256
  `6a478625d6d7f722c3a2142f308a4ac79a6f38ab4f97c9c859e936e0c6da1f36`.
  Lines 40–46 register bare `nohlt` and set forced polling; lines 351–355 restart
  the tick and take the polling branch; lines 57–74 poll with local IRQs enabled.
- The linked Image contains one NUL-terminated `nohlt` setup string. String
  presence is host evidence, not proof of runtime selection.

The reviewer read `drivers/soc/canaan/k230-uart-progress.c` lines 99–120 and
131–185: the observer waits once for completion, while the worker sleeps between
cached snapshots. `kernel/sched/completion.c` and `kernel/time/sleep_timeout.c`
use scheduling timeouts; `drivers/tty/n_tty.c` blocks a shell read waiting for
input. All three can block, making idle/wakeup a useful dependency to change.
A fresh Bash prompt does not prove later timer delivery. The selected timer
source `drivers/clocksource/timer-riscv.c` programs compare through SSTC or SBI;
which path executes on this run remains **UNVERIFIED**.

Rejected alternative: `cpuidle.off=1` alone is not the same intervention, because
RISC-V's default idle path can still execute WFI (`arch/riscv/kernel/process.c`
lines 45–47, `arch/riscv/include/asm/processor.h` lines 188–190). Adding ECALL
markers would introduce another firmware-output dependency. No MMIO polling,
IRQ masking, affinity/priority changes, firmware replacement or new kernel build
is needed for the bounded `nohlt` comparison.

A returned summary under polling would support idle/tick-policy dependence,
not isolate WFI, timer, IRQ or firmware causation. Continued silence remains
inconclusive, including possible final DBCN output blocking. Forced polling is
not a proposed production power policy or ordinary-root acceptance. Keep zero
candidate writes, exact qualified arguments, bounded capture and separate normal
recovery proof. Land a typed controller plan before implementation.

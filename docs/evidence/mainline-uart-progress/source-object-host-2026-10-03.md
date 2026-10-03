# Finite UART/IRQ reporter: source and object proof

Evidence class: native actual-code fixtures, immutable source/configuration
realization, prepared-header RISC-V objects and read-only Nix evaluation.
Full matching kernel/system/bundle, physical records, Bash reception, usable
root, panel/glass and automatic return are **UNVERIFIED**. Task 5b.5 remains open.

Worktree `/home/jadams/tmp/k230-mainline-uart-progress`, branch
`mainline-uart-progress`, base `a5629a3d40a1d9f15a0bd5f875a190472a19648f`.
Owned: the new kernel/object recipes, new patch/header/reporter, additive flake
outputs, kernel/source tests, this evidence directory and task 5f.1–2 entries.
No board/UART/camera/full-kernel build. The shared build lock was held only
for two source/object attempts and configure-only realization, then released.

## Selected source and configuration

The optional `kernelMainlineUartProgress` layers over the original SBI-only
source, preserving all existing outputs. Realized source:
`/nix/store/4av3w0kigacwah6w04zfpnky4gsh0k59-linux-mainline-k230-uart-progress-src`;
derivation `rywsq0srln1k18z7iyls7m40wsz7xwi8-linux-mainline-k230-uart-progress-src.drv`.
Its actual derivation `env.src` is exactly
`/nix/store/26hzn5vin6b27cc4mpffc9fn5x8ikwqn-linux-mainline-k230-boot-trace-sbi-only-src`.
This is source layering proof, not a new kernel binary.

Changed-source SHA-256:

| File | SHA-256 |
| --- | --- |
| `drivers/tty/serial/8250/8250_core.c` | `e310fed432d878b81e71b814e7f442c6ae0d3013735f4b6010ee24d35dac8ed7` |
| `drivers/clocksource/timer-riscv.c` | `f8e5977bd8170f84719c89952178efa22c1162ebd526c182b1bf74e5c4cffa24` |
| `drivers/soc/canaan/k230-uart-progress.c` | `7c71e64025009f1a5407709e470a57cdf1078110a1dda4ef7d2062d682dcfd51` |

Configure-only realization passed:
`/nix/store/5pgcm3w58zrbjhzxk79g9g8x9iaxaja2-linux-config-riscv64-unknown-linux-gnu-7.3.0-rc5`,
SHA-256 `d1930cd8f11c526a6c503099897ade73ccef156109d58728c99837e13422ffe7`.
Kconfig resolves K230_UART_PROGRESS/RISCV/ARCH_CANAAN/RISCV_SBI/RISCV_TIMER/
SERIAL_8250/SERIAL_8250_DW/OF to built-in `y`; 64BIT/4KiB/VMAP_STACK are also `y`.
Compared with the installed base effective configuration, the assignments differ
in K230_UART_PROGRESS (absent → y) and OPENSSL_SUPPORTS_ML_DSA (y → absent).
The latter is a host crypto configuration result, with no hardware implication
claimed. This is not the installed config of a newly linked diagnostic kernel.

## Snapshot and finite worker

The internal 8250 getter uses one `mutex_trylock(serial_mutex)` to pin the
registration/removal lifetime. It validates line0, the selected UART device,
mapbase and actual mapped PLIC source16 under RCU. It makes one plain
`spin_trylock_irqsave` attempt and copies cached counters/masks/IER only.
It avoids UART lock wrappers: their nbcon release can flush printk.
No MMIO, IRQ-chip hardware getters, PM calls, TTY opens/reads/polls/settings or
clock/register writes occur. UART IRQ statistics are collected after releasing
the spinlock while registration remains pinned; all locks are released before
formatting or SBI output. `READ_ONCE(uartclk)` is an independent cached rate
observation because existing DW termios writers do not all hold the port lock.

The timer getter publishes only the actual mapped CPU-local timer IRQ after
successful interrupt request and CPU-hotplug setup. Zero means unavailable,
not a measured zero count. No Linux IRQ number is guessed from source16.

Exact runtime `k230.uart_progress=1` and available DBCN permit one late-init
normal-priority worker. Absent/bare/invalid values start no worker. No priority,
affinity, tick-policy or IRQ/PID1-path instrumentation is added. Six finite
5-second sleeps precede at most six samples, approximately thirty seconds.
Each sample performs one single-attempt SBI write from regular aligned storage;
there is no printk/emergency fallback, retry or automatic reboot.
Sleep, scheduling, lock primitives and firmware are not guaranteed wall-clock
deadlines. Missing records remain unknown.

Fixed wire contract (leading newline, one ASCII line, final newline):

```text
K230_UP1 n=N s=S j=JJJJJJJJJJJJJJJJ t=TTTTTTTTTTTTTTTT u=UUUUUUUU ti=IIIIIIII ui=CCCCCCCC tc=CCCCCCCC rx=CCCCCCCC tx=CCCCCCCC fe=CCCCCCCC pe=CCCCCCCC oe=CCCCCCCC be=CCCCCCCC ie=MMMMMMMM rm=MMMMMMMM im=MMMMMMMM hz=HHHHHHHH
```

N is decimal0–5; S is decimal0–5. All other fields are fixed-width lowercase
hexadecimal. States: 0 measured, 1 lifecycle busy, 2 port busy, 3 unavailable,
4 wrong binding, 5 changed UART IRQ. All UART fields are zero/unmeasured for
nonzero state; independent time/timer fields remain available. `j` is jiffies,
`t` ktime nanoseconds, `u` actual Linux UART IRQ, `ti` actual timer IRQ, `ui/tc`
their aggregate kernel-accounted counts. `rx/tx/fe/pe/oe/be` are cached processed
RX/break, TX, framing, parity, overrun and failed-flip insertion counts;
`ie/rm/im/hz` are cached IER/read mask/ignore mask/independent uartclk.

RX includes synthesized break handling; an increment does **not** prove a
physical FIFO read per increment or Bash delivery. UART IRQ totals may include
shared/spurious activity. Timer IRQ growth is accounted dispatch and can include
the reporter's own wakeups. Sequence/time progress does not prove physical
timer health. Integer counters may wrap. Firmware results (full/partial/zero/
error) are deliberately discarded; a later record shows an earlier call returned,
not that it fully wrote. No frame proves receipt, recovery, ordinary root or cause.

## Host commands and actual objects

Run from the owned worktree:

```sh
python3 tests/test_mainline_uart_progress.py
nix-instantiate --parse nix/kernel-mainline-uart-progress.nix
nix-instantiate --parse nix/kernel-mainline-uart-progress-objects.nix
nix-instantiate --parse flake.nix
flock /tmp/k230-nix-build.lock nix build .#kernelMainlineUartProgressObjects \
  --offline --no-link --print-out-paths --max-jobs 1 --cores 2
flock /tmp/k230-nix-build.lock nix build .#kernelMainlineUartProgress.configfile \
  --offline --no-link --print-out-paths --max-jobs 1 --cores 2
nix eval --offline --no-write-lock-file --json --impure --expr \
  'import /home/jadams/tmp/k230-mainline-uart-progress/docs/evidence/mainline-uart-progress/check-identities.nix { root = /home/jadams/tmp/k230-mainline-uart-progress; }'
openspec validate the-board-runs-a-mainline-kernel --strict
openspec validate --all
git diff --check
```

Twelve native tests pass (0.370s), executing the actual snapshot, timer getter
and worker with isolated callbacks. They check exact/disabled/invalid gates,
extension absence, single lock attempts, missing/wrong/changed bindings,
complete maximum-value frames, alignment, six-sample bounds, stop behavior,
and full/partial/zero/error no-retry behavior. These are fixtures, not kernel
or firmware execution. Parse/strict/all56/whitespace checks pass.
The reproducible expression and [identity receipt](identities.json) assert all
22 existing kernel/system/bundle/device-tree/image derivations are unchanged.
Uname remains `7.3.0-rc5`. No evaluation command builds a kernel.

Successful object output:
`/nix/store/yx0vkrrn9z58iycbi8mlfb0mk10gxsxx-k230-mainline-uart-progress-objects`.
It compiles only the changed 8250/timer/reporter translation units, no MODULE
define or final link, against copied immutable installed SBI-only `iw4iyn…`
dev headers. Their actual config SHA is
`c5c128ed8b9701f78a0b8bd4f18dacd0d2407ae90eda79a35bba2d9f5ffbeae7`.
The explicit `-DCONFIG_K230_UART_PROGRESS=1` overlay makes the new code visible;
this prepared-header/API proof is distinct from the separately resolved Nix
config above and the still-unbuilt new kernel. GCC is 15.3.0, W=1.
[Compile log](object-compile.log) retains the pahole-version mismatch warning;
no C warning was observed. [Object hashes](object-sha256.txt) identify the bytes.

[Actual ELF inspection](object-readelf.txt), reproducible with
`readelf -hSWs OBJECT`, confirms ELF64 little-endian RISC-V relocatable files.
Snapshot/timer getter/worker are ordinary `.text`; timer state and enable flag
are `.sbss`. The record is 256 bytes at BSS offset0, section alignment256,
so it remains page-contained on the configured 4KiB pages and is not VMAP_STACK
or freed init storage. Only setup/late-init functions use `.init.text`.
These objects use the installed base headers plus the explicit reporter overlay,
not generated headers from the separately resolved new configuration. Exact new
configured-header compilation, final linkage and runtime progress remain
unverified; task 5f.2 therefore remains unchecked.

The first object derivation `hdmdjivj271zn9aya4n7x4mi7g2mm9ym` failed with
builder RC2. Its redirected compiler log disappeared with the failed output;
the compiler cause was not recovered. The corrected recipe supplies the
8250 local-header include directory and prints the retained compile log on
failure. The successful corrected derivation is `q3fd8jpm728j6yv3mbvbzhljfmsna084`.
No failed run is treated as successful evidence.

## Remaining gates

Independent source/API review approved the frozen implementation. Coordinator
review/landing/push/CI, additive matching-system/bundle preparation and a full
matching kernel build remain separate. Only the reserved board operator may
run the group5f.5 command after protected recovery, exact artifact/controller
proof and one-stimulus/passive-capture review. No hardware action was performed
for this note. Task5f.2–6 and usable-root/panel/glass task5b.5 remain open.

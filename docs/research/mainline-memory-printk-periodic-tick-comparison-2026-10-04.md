# Same-image MemoryPrintk tickless-policy comparison

Source/artifact proof only. The recommended next comparison is the actual p2
MemoryPrintk bundle with one additional volatile token, `nohz=off`, retaining
zero candidate input and all qualified arguments/artifacts. No implementation,
new build or hardware action was performed for this note. Runtime tick policy,
UMK output, automatic return, IRQ diagnosis and mainline acceptance remain
**UNVERIFIED**. The coordinator reports the latest changed-channel trial had
fresh matching arguments/backend and Bash entry, but no UMK or normal return in
180.1019 seconds; its new operator reset is pending. That report is not replaced
with a source inference here.

## Exact selected artifacts and gates

- Bundle: `/nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files`.
- Kernel: `/nix/store/xna7x12lh4lmzwgmwq51cyc9wf86504p-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
- Dev: `/nix/store/24hbalyljs6gn6fzkkl24znv8a0x6jdl-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev`.
- Source: `/nix/store/0l4mgw9hr1j7pj247jsrxjd478fnlfy8-linux-mainline-k230-uart-progress-memory-printk-src`.

The actual selected `Image` SHA-256 is
`c2c9663bc385a0c62a15b740ccd46b36b51bc3fd9c0c6281b2a2e5a1882878c3`.
It contains exactly one NUL-terminated `nohz=` setup string at zero-based byte
offset **19425910** (decimal). The selected source registers that string with
`__setup` in `kernel/time/tick-sched.c:706`; this is compiled support on the
same already-built image, not a proposed kernel option.

The installed `lib/modules/7.3.0-rc5/build/.config` SHA is
`52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`.
Relevant actual assignments are `CONFIG_NO_HZ_COMMON=y`, `CONFIG_NO_HZ_FULL=y`,
`CONFIG_HIGH_RES_TIMERS=y`, `CONFIG_HZ=250`, `CONFIG_RISCV_TIMER=y` and
`CONFIG_RISCV_SBI=y`. NO_HZ_IDLE and HZ_PERIODIC are unset. The legacy
`CONFIG_NO_HZ` symbol is also unset; NO_HZ_COMMON is the source gate for this
parser, so requiring the legacy symbol would incorrectly reject this image.
GENERIC_IDLE_POLL_SETUP is built in for the earlier `nohlt` comparison.
PRINTK/PRINTK_TIME/8250 console/DW are built in and PRINTK_CALLER is disabled,
as established in [exact/full proof](../evidence/mainline-uart-progress-memory-printk/exact-full-host/README.md).

## What the option changes, and how it differs from nohlt

All line references below use the exact selected source above.
`kernel/time/tick-sched.c:692–706` compiles the parser under NO_HZ_COMMON,
initializes `tick_nohz_enabled` to true and passes the value to `kstrtobool`.
Exact `off` sets it false and the setup callback returns 1. Absent option retains
true. `lib/kstrtox.c:351–394` accepts common boolean prefixes, including `of`
for false; it is deliberately not a strict whole-token parser. An invalid value
such as `garbage` returns -EINVAL without updating the flag, and the setup
callback returns 0. Bare, empty, duplicate and alternate spelling must therefore
be rejected by the typed host policy rather than treated as this comparison.

`tick-sched.c:1412–1419` declines TS_FLAG_NOHZ activation when this flag is false;
`1425–1432` also declines the low-resolution nohz transition. The idle-tick stop
predicate rejects a missing TS_FLAG_NOHZ at `1096–1101`, and full-dynticks tick
updates similarly check that flag at `1047–1055`. The high-resolution scheduler
timer can still be started and forwarded at `1494–1520`. This comparison keeps
the scheduler tick recurring instead of authorizing tickless suppression; it
**does not** disable high-resolution timers or turn the RISC-V device into a
hardware periodic timer. Its CLOCK_EVT_FEAT_ONESHOT/SBI scheduling path remains
selected (`drivers/clocksource/timer-riscv.c:36–85`).

Earlier `nohlt` sets `cpu_idle_force_poll` (`kernel/sched/idle.c:39–46`). The
poll loop enables interrupts and spins (`57–74`). The common idle loop still
calls `tick_nohz_idle_enter` (`305–306`); the forced-poll arm explicitly calls
`tick_nohz_idle_restart_tick` before polling (`351–353`). Ordinary cpuidle paths
may stop or retain the tick (`164–169`, `228`). Thus nohlt already avoids a
stopped tick while in its poll arm; its negative result weakens a simple
"only idle WFI/idle tick stop" hypothesis. It does not disable global nohz
activation/transition policy. The new option tests that remaining difference,
with normal idle selection restored and no combined nohlt or highres option.

Source file SHA-256 receipts are:

| Selected source file | SHA-256 |
| --- | --- |
| kernel/time/tick-sched.c | `fd06d55e38d99717f32d3ef73efdd80e804d5c4f77b2042baaf11c522e9ee73c` |
| kernel/sched/idle.c | `6a478625d6d7f722c3a2142f308a4ac79a6f38ab4f97c9c859e936e0c6da1f36` |
| lib/kstrtox.c | `b2b52e31906d7a0e7231d5abf4713a13c91bf398ffa39fcc0ea937187cb606e8` |

## Bounded next proof and interpretation

Proposed typed selector: `--uart-progress-memory-printk-nohz-off`, requiring the
existing minimal/same-image/progress/Memory/no-stimulus/MemoryPrintk selectors.
Reject all competing point/poll/clock/trace/timer selectors and any original or
transformed nohz spelling/duplicate; append exactly one trailing `nohz=off`.
Retain the same immutable source/dev/Image and all existing manifest/archive,
config/backend/framing/length gates, exact received argument proof, zero input,
180-second passive capture and independent protected normal recovery. Do not
add output retries, commands or recovery authorization based on UMK presence.
This requires reviewed controller/planning work, no kernel/initrd/DT build.

A valid UMK would establish that the observer reached a coherent snapshot and
Linux output under the changed policy; it would support tickless-policy
dependence without identifying the failing interrupt or proving printk returned.
No UMK leaves sleep/wakeup, worker/observer scheduling and output unresolved.
A completed record does not establish RX, ordinary root or touch. The earlier
[Breadcrumbs physical proof](../evidence/mainline-uart-progress-breadcrumbs/physical-2026-10-03/README.md)
observed both breadcrumbs and numeric samples 0 and 1, with time advancing
5.116997479 seconds, jiffies 1280 and timer IRQ count 252. That disproves a
universal assertion that timers never progress; it does not guarantee progress
on another boot. A new protected recovery must precede the next physical trial.

A second, unimplemented fallback is a fixed noninteractive Bash-PID1 argv probe:
`init/main.c:489–511,1029–1036` passes post-`--` arguments to init, while
`593–604` clears prior argv for rdinit and `1572–1583` executes the final vector.
The actual p2 archive contains RISC-V `/bin/sh` (Bash 5.3p15) and `/bin/sleep`
(coreutils 9.11). Fixed initial output, one five-second sleep and completion
output could distinguish autonomous PID1 progression from the reporter's
threads without RX. It needs separately reviewed constrained quoting/argv and
candidate guards; the current transport rejects script syntax and enforces a
512-byte U-Boot command bound. No unconditional reboot/exit, arbitrary script
option or claim of ordinary init is authorized by this fallback description.
The single nohz token is the smaller practical next comparison.

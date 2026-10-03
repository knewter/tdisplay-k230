# Debug-console receipt failure: terminal and UART source boundary

Evidence class: read-only host source, archived-unit and candidate-DTB inspection.
No board, UART, MMIO, build or source implementation. Worktree
`/home/jadams/tmp/k230-mainline-debug-tty-rx`, branch
`audit/mainline-debug-tty-rx`, base
`b2e219e21532df62871ff0ff8dbd0358c720817a`. Own only this note; no board/build
reservation. Cached work-status start completed with exit zero at idle priority.
This continues mainline task 5b.5; the next diagnostic and its automatic recovery
remain **UNVERIFIED**.

## Observed boundary and exact artifacts

The coordinator's committed [receipt-failure packet](../evidence/mainline-system-trial/debug-receipt-physical-2026-10-03/README.md)
records a fresh Linux/systemd/primary-shell prompt, followed by one receipt and
no command echo, receipt body or complete frame in ten seconds. No later input,
snapshot, identity/ownership guard or reboot was sent. Operator reset and
protected normal recovery subsequently passed. This is a reception/completion
failure, not evidence that the proposed debug shell's ownership guards passed.

The same five-clock candidate previously completed minimal-shell and standalone
blkid commands and protected automatic recovery. Earlier paused-shell RX silence
was also reported by the coordinator; it is not exclusive to systemd debug-shell.
The ordinary-init boot quietness is a separate observation, not proof of the
same failure. The [earlier UART audit](mainline-uart-readiness-2026-10-02.md)
identified premature boot-time command input in an older controller; that defect
cannot explain away this corrected, post-prompt receipt trial.

Inspected artifacts:

- Bundle `/nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files`;
  system `/nix/store/9gdmsrh2igqla1qz0ll97czfw2x42icw-nixos-system-nixos-26.11.20260919.20b1ddd`;
  kernel `/nix/store/9vdk79pa4pm38mlmbflkqh4i4sc9kha0-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.
- Exact kernel source `/nix/store/l0j3rf11mr65wl5x88a9zzma45ciz687-linux-mainline-k230-drm-src`,
  pinned Linux `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` plus the reviewed
  optional DRM/restart/SD1 five-clock changes. Line numbers below refer to this
  installed source, rather than a moving upstream branch.
- Initrd SHA-256 `046c5b012a2b993caa1082926e9928c14bccc0fff456f20f8716c91d13f51842`;
  archived systemd 261.2 unit and executable identities are in the
  [debug-console source audit](mainline-initrd-debug-console-2026-10-03.md).
  Its source store path is unavailable locally: systemd implementation citations
  use the official exact v261.2 tag; compiled unit substitutions were inspected
  in the archive.

## What systemd changes, and what it preserves

Archived `debug-shell.service` runs the same `/bin/sh` used in minimal mode,
with `StandardInput=tty`, `TTYReset=yes`, `TTYVHangup=yes`, `Restart=always`.
The generator's [TTY override](https://github.com/systemd/systemd/blob/v261.2/src/debug-generator/debug-generator.c#L255-L278)
selects `/dev/ttyS0` and clears the tty9 existence condition; it does not set a
baud rate. The unit's archived SHA-256 is
`edc8fe166b94d3c9e76879662780679b6092944f88e9966a27a41f0aa2767a81`.

The [destructive reset](https://github.com/systemd/systemd/blob/v261.2/src/core/execute.c#L127-L196)
temporarily opens the TTY, resets it, performs `TIOCVHANGUP`, and closes that
possibly hung-up fd. [Execution setup](https://github.com/systemd/systemd/blob/v261.2/src/core/exec-invoke.c#L5310-L5318)
does this before acquiring actual stdin. `setup_input` at 333–402 then acquires
the terminal with `TIOCSCTTY`; normal `tty` mode waits for ownership, whereas
`tty-force` can take ownership. A constructive reset on actual output follows
at 5020–5058. The source anticipates settings disappearing across temporary
fd closure. Revert/cleanup can reset again (`execute.c:1767–1776`), but no shell
exit/restart or competing reset was observed in the failed trial.

[Terminal reset](https://github.com/systemd/systemd/blob/v261.2/src/basic/terminal-util.c#L906-L975)
preserves hardware baud, character size, parity, `CRTSCTS`, `CLOCAL` and `HUPCL`,
and ORs `CREAD` into `c_cflag`. It sets canonical/echo/software flags and control
characters, then flushes `TCIOFLUSH`. Existing `IXON`/`IXOFF` are not explicitly
cleared. Thus neither baud change nor reception-disable is implied by this
reset; queued bytes can be discarded during it. ANSI terminal reset is a
separate output operation, not UART baud programming.

The archived interactive shell is Bash 5.3p15. GNU base Bash 5.3's
`lib/readline/rltty.c:520–552` clears `ICANON|ECHO` for Readline and conditionally
clears software flow control. Base source was fetched from
[GNU's release archive](https://ftp.gnu.org/gnu/bash/bash-5.3.tar.gz), SHA-256
`0d5cd86965f869a26cf64f4b71be7b96f90a3ba8b3d74e27e8e9d9d5550f31ba`.
The candidate's recorded Bash derivation is absent locally, so its complete
patchset/configuration was not reproduced. This corroborates why kernel echo
cannot be assumed while a shell edits input; it is not proof of candidate
Readline state or a Bash defect. The receipt is approximately 150 bytes, below
the canonical input limit, and no overflowing input sequence was sent.

## `/dev/console` is a lifetime difference, not a separate RX mechanism

The minimal PID1 shell inherits console fds; debug-shell explicitly opens ttyS0.
`drivers/tty/tty_io.c:1893–1908` resolves `/dev/console` through `console_device`
to a TTY driver/index and forces nonblocking open. `serial_core.c:2848–2855`
maps the UART console to its serial TTY driver. With ttyS0 selected as the
serial console, both names can reach the same UART and line discipline. This
does not make `/dev/console` input a polling bypass of serial RX interrupts.

There are meaningful lifetime differences. `tty_io.c:568–656` invalidates
ordinary opened TTY fds on hangup, with special handling for redirected console
fds. `serial_core.c:1714–1748` last-close shutdown calls `stop_rx`, shuts the
port down and changes PM state. Hangup has a related path at 1816–1845.
Activation at 1921–1965 restarts the port; startup at 304–337 restores inherited
console termios and calls `uart_change_line_settings`.

`serial_core.c:1669–1675` skips the low-level termios update when hardware flags,
speeds and relevant input flags did not change. A software-only reset therefore
does not necessarily program the UART clock/divisor. Reopening/startup does
run line-settings setup. `8250_dw.c:473–491` rounds/programs the functional
clock for baud times 16 before divisor setup; its idle/divisor path at 135–175
temporarily disables IER and clears FIFOs. These are source paths to measure,
not evidence that their restoration failed.

## Exact UART, clock, IRQ and PM limits

Fresh `fdtget` inspection confirmed `serial0:115200n8`, UART0 `okay`, and clock
specifier `6 a1` (ID161, `K230_LS_UART0_RATE`). The DT source
`arch/riscv/boot/dts/canaan/k230.dtsi:112–121` specifies
`snps,dw-apb-uart`, address `0x91400000`, width4/shift2, interrupt16 level-high,
reset `RST_UART0`; the board enables it. DT interrupt16 is not a measured
Linux IRQ number/count. No new pinmux transition is established by this audit.

`drivers/clk/clk-k230.c:678–682,903–914` marks UART0 APB and functional gates
critical. The DW driver adopts the unnamed functional clock and optional APB
clock at `8250_dw.c:708–725`. Its PM callback at 462–470 takes/releases runtime
PM references; runtime suspend/resume at 811–833 disables/enables those clocks.
Console setup itself holds a runtime-PM reference
(`8250_port.c:3614–3615`, balanced on console exit). Critical gates do not
prevent rate programming. These facts neither prove a runtime suspend happened
nor justify another global `clk_ignore_unused` workaround.

Configuration has built-in DW/8250/serial console and PM; DMA support is enabled,
but `8250_port.c:2372–2382` explicitly rejects DMA for a kernel-console UART.
Startup sets RX/status interrupt shadow bits at 2385–2390; `CREAD` absence can
discard receive characters at 2742–2743. Console output at 3438–3554 saves,
disables and restores IER and polls TX. Continued printk/prompt TX consequently
does not prove RX/IRQ progress; no echo does not locate the failure below the
shell. Static mapping or generally broken wiring is less persuasive given
same-bundle returned commands, but intermittent RX, lifecycle, termios and
system-wide progress remain undistinguished. No specific kernel cause is proven.

## Recommended next implementation: autonomous reporter, one stimulus

Avoid another unchanged interactive debug-shell retry. Prepare a separate
opt-in initrd/bundle using the already built kernel/DT; leave the default image,
normal profile, protected card files and existing controllers unchanged. A
small native helper and a debug-shell ExecStart override are sufficient; no
kernel patch is established by this audit. Require source/host review before
an operator chooses this newly manifested candidate.

Keep the original three qualified controls and two supported diagnostic args
from the landed debug plan. The override runs the helper on the service's actual
TTY fds; after initial checks it forks a bounded observer and execs the original
`/bin/sh` in the main process. This preserves the shell's ExecMainPID and PPID1
and the original reset/vhangup behavior. The observer inherits/duplicates fds;
it must not introduce another TTY open/close, hangup, read, flush or termios
write. The experiment observes the failing setup before perturbing it.

Before emitting a fixed READY frame, verify the exact candidate/kernel/sole-init
cmdline, systemd PID1, initrd marker, actual fd0 ttyS0, service identity/PID/TTY,
volatile root/proc/sys/dev/cgroup and all five inactive/no-job root-chain units;
no `/sysroot` mount. Use the reviewed host preparation, artifact/load/hash and
protected preflight gates. Candidate execution guards must return boundedly;
a guard error/timeout means FAILED/UNKNOWN and no claimed readiness or automatic
recovery. Never substitute host preflight for an unperformed candidate guard.

Emit bounded numeric termios state/speeds plus `TIOCGICOUNT` snapshots before
Readline, shortly afterward and after one ten-second receipt window. The helper
can use `tcgetattr`, `tcgetsid`/process-group queries and TTY ioctls directly,
without candidate Python. `serial_core.c:1259–1286` implements the counter
snapshot; `8250_port.c:1610–1667` increments RX before line-discipline delivery
and counts framing/parity/overrun/break errors. These are driver receive/error
counters, **not IRQ-entry counts or exact delivered receipt-byte counts**.
Validate the UART's sysfs ancestry before a bounded runtime-status read. Do not
dump arbitrary `/proc/interrupts`, raw registers, command lines or private data.
Actual IRQ-entry attribution needs separately reviewed driver instrumentation;
do not fabricate it from these counters.

Host behavior is one fresh receipt after READY/primary prompt, with no second
input needed to obtain the autonomous snapshots. A counter increase without a
returned receipt separates driver RX activity from shell/TTY delivery; no
increase leaves wire, RX-enable/IRQ and execution-progress hypotheses open.
Error deltas constrain baud/noise hypotheses but do not prove one. Compare the
same timing/counter format in known working minimal mode only if a later scoped
comparison is required, rather than changing several flags at once.

The observer retains private, bounded output and emits complete fresh frames to
the already protected host wire log before any recovery. Prearrange one direct
`/bin/reboot -ff` attempt only after renewed same-boot/service/TTY/initrd/root-chain
guards and completed observer work. It must not depend on another inbound shell
command. A missing observer frame, blocked guard, lost identity or unknown child
state forbids further input; it does not authorize unconditional reboot. A timer
or userspace timeout cannot guarantee execution during a kernel stall. Require
kernel restart, SPL, protected normal identity/services/eight hashes/new boot ID
to claim automatic recovery; otherwise the known operator-reset path remains.

Host tests must cover inherited-fd/no-extra-open behavior, pre/post state and
counter framing, a missing receipt with autonomous completion, exact identity
and mount/root-chain failures, guard deadline/blocked observer, raw retention
before the single reboot, and no recovery request on unknown. This plan reduces
dependence on failed RX for evidence/recovery; it does not yet guarantee fewer
operator resets or prove a repaired UART.

A secondary source-supported comparison is `rd.systemd.break=pre-udev` with
`rd.systemd.unit=basic.target`, replacing debug-shell rather than combining both.
The [archived breakpoint unit](https://github.com/systemd/systemd/blob/v261.2/units/breakpoint-pre-udev.service.in)
uses default `/dev/console`, `tty-force`, no explicit reset/vhangup, and orders
before udev daemon/trigger. It changes ownership, lifecycle and coldplug timing
together; success cannot attribute one factor, and failure can still require
operator reset. Prefer the autonomous observation first.

## Narrow host checks

Read selected exact source ranges and archived units; `fdtget` checked the three
properties above. Official v261.2 terminal/breakpoint source and GNU base Bash
source were read without a build. Exact candidate Bash derivation/source was
unavailable; this limit is retained. `openspec validate
the-board-runs-a-mainline-kernel --strict` and `git diff --check` passed.
The idle cached handoff scan was started, session 47146, with output in
`/home/jadams/tmp/mainline-debug-tty-rx-handoff-status.txt`; it was still running
when the otherwise ready note was committed. No controller tests, physical
command or production acceptance were performed by this audit.

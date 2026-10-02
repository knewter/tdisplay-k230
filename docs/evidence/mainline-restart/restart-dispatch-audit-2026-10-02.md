# Restart dispatch source audit — 2026-10-02

Audit recorded at `2026-10-02T17:17:05Z`. Evidence class: host source/artifact
inspection and bounded interpretation of private operator captures. No build,
board input, reset, or hardware acceptance was performed by the auditor.
Automatic restart and callback execution remain **UNVERIFIED**.

The audit used worktree `/home/jadams/tmp/k230-mainline-restart`, branch
`mainline-restart-port`, base `c5254075e531487af82841b3ae76582e5535f0fb`, with
host-proof HEAD `75dee78cdd61e9a8f30ec08a90784c93a11534df`. Only this new file
is owned by this follow-up. The coordinator owns physical operation and its
separate trial evidence. The completed task-start `tools/work-status.py` output
is cached privately; the handoff scan also completed at idle I/O priority.

## Exact sources and dispatch

The corrected candidate source is
`/nix/store/jvz4v73g8a67pqwm06v079h6s1cpqr9s-linux-mainline-k230-drm-src`,
based on Linux `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e` plus the optional
K230 restart patch. Source inspection found:

- [RISC-V reset.c, lines 19–29](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/arch/riscv/kernel/reset.c#L19-L29)
  calls `do_kernel_restart(cmd)` from `machine_restart()`.
- [reboot.c, lines 246–249](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/kernel/reboot.c#L246-L249)
  dispatches `restart_handler_list`. Its lines 443–470 register
  `SYS_OFF_MODE_RESTART` on that same list; lines 342–354 adapt its notifier to
  the sys-off callback; lines 529–543 implement managed registration/cleanup.
  The candidate's local `drivers/reset/reset-k230.c:388–390` registers priority
  128. This API therefore reaches the RISC-V dispatch; there is no separate
  managed restart list that RISC-V fails to call.
- [notifier.c, lines 17–40](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/kernel/notifier.c#L17-L40)
  orders higher priorities first. [sbi.c, lines 682–689](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/arch/riscv/kernel/sbi.c#L682-L689)
  registers SBI SRST at priority 192 only when the extension probe succeeds.
  That would precede K230's 128. No SRST detection message appeared in the
  inspected capture; absence of that message is not an independent firmware
  capability test.
- [reboot.c, lines 101–106 and 288–299](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/kernel/reboot.c#L288-L299)
  runs blocking reboot notifiers, disables usermode helpers, shuts devices
  down, runs restart-prepare callbacks, migrates to the reboot CPU, and shuts
  syscore down before printing the kernel restart announcement. The subsequent
  path is `kmsg_dump` → `machine_restart` → `do_kernel_restart` → callbacks.
  An announcement alone would still not prove callback execution.
- Local `drivers/reset/reset-k230.c:341–402` has neither a successful-probe
  message nor a callback message. Mapping failure logs `cannot map boot reset
  register`; registration errors propagate. [dd.c, lines 621–646](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/base/dd.c#L621-L646)
  logs other probe failures, while deferral/match rejection uses debug logging.
  No corresponding K230 error appeared. Silence does not prove binding.
  [platform.c, lines 1527–1537](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/base/platform.c#L1527-L1537)
  calls a driver's shutdown method, not device removal/devres cleanup. The
  K230 driver has no shutdown method; ordinary shutdown does not itself remove
  this managed restart registration.

The matching bundle is
`/nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files`.
`fdtget` found `/soc/reset-controller@91101000`, compatible `canaan,k230-rst`,
`reg = <0 0x91101000 0 0x1000>`, and no `status` property. Missing status means
available in [of/base.c, lines 552–560](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/of/base.c#L552-L560).
Node availability and a matching compatible do not prove successful probe.

## Candidate-phase boundary

The coordinator's controller sends `/bin/reboot -ff` after a distinct candidate
receipt. Local inspection selected the actual receipt line, excluding echoed
commands and the preceding normal-system boot/reboot phase. After that receipt,
the only nonblank captured output was `Rebooting.`. There was no candidate
kernel restart announcement, second SPL, or normal-kernel banner before the
reported physical intervention. The capture's sole kernel restart announcement
belongs to the **normal pretrial reboot**, not the candidate. It must not be
used as candidate dispatch evidence. The controller ended on serial disconnect;
this audit does not claim expiration of its full recovery deadline.

The matching system's `sw/bin/reboot` resolves to
`/nix/store/srwrq12f962d5prr382vvsq76nfvmm84-systemd-riscv64-unknown-linux-gnu-261.2/bin/systemctl`.
The source named by its derivation was not locally present; the following
version-matched upstream files were inspected read-only:

- [systemctl-compat-halt.c, lines 78–80 and 143–159](https://github.com/systemd/systemd/blob/v261.2/src/systemctl/systemctl-compat-halt.c#L143-L159)
  sets force level 2 for the compatibility `-f` option and calls `halt_now`.
- [systemctl-util.c, lines 893–922](https://github.com/systemd/systemd/blob/v261.2/src/systemctl/systemctl-util.c#L893-L922)
  performs `sync()` before calling `reboot_with_parameter`.
- [reboot-util.c, lines 124–133](https://github.com/systemd/systemd/blob/v261.2/src/shared/reboot-util.c#L124-L133)
  prints the observed userspace message immediately before `reboot(RB_AUTOBOOT)`.

Thus the captured message is consistent with reaching beyond userspace sync
and immediately before the reboot syscall. It does not show syscall entry,
kernel preparation completion, handler registration, or callback execution.
The location of any stall is unknown; kernel preparation/device shutdown is
among the paths preceding the unobserved kernel announcement.

The separate private manual-recovery capture was 35 bytes, with bracketed-paste
disable/enable sequences and a final `>`. This is consistent with a readline
shell continuation prompt. Its preceding fragment was not usable identity
text. It establishes neither a normal nor a mainline shell, a fresh boot, nor
protected normal recovery. A full operator power cycle and identity postflight
were pending at this audit boundary. Raw UART and private runtime fields are
not copied here.

## Read-only commands and limits

Commands included `date -u '+%Y-%m-%dT%H:%M:%SZ'`, narrow `rg -n`/`sed -n`
reads of the exact local source files named above, `readlink -f` on the matching
system's `sw/bin/reboot`, and `nix derivation show` on
`/nix/store/hrg87xdmvmibsh6mwh9i65mhy03i8887-systemd-riscv64-unknown-linux-gnu-261.2.drv`.
The upstream systemd files were read at their `v261.2` URLs above. DT inspection
used the following commands, with `BUNDLE` set to the exact bundle above:

```sh
fdtget -t s "$BUNDLE/k230-tdisplay-mainline-drm.dtb" /soc/reset-controller@91101000 compatible
fdtget -t x "$BUNDLE/k230-tdisplay-mainline-drm.dtb" /soc/reset-controller@91101000 reg
fdtget -t s "$BUNDLE/k230-tdisplay-mainline-drm.dtb" /soc/reset-controller@91101000 status
```

The first two returned the values recorded above; the third returned
`FDT_ERR_NOTFOUND`. Private Python parsing of
`$HOME/tmp/k230-mainline-restart-board/minimal-uart.log` selected a line matching
`^K230_RDINIT_REBOOT\s`, then counted candidate-phase announcements and classified
only safe post-receipt output. Parsing
`$HOME/tmp/k230-mainline-restart-board/manual-recovery-uart.log` counted terminal
sequences and tested the final continuation character without publishing its
raw contents. These inspections are not new board actions or hardware passes.
Task 5d.4 and the usable-root gate 5b.5 remain open.

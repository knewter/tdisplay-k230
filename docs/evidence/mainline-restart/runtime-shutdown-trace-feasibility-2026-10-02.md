# Runtime shutdown tracing feasibility, 2026-10-02

Recorded at `2026-10-02T17:54:57Z`. Evidence class: read-only host source and
artifact inspection. No board, serial, build or controller mutation. Runtime
parameter availability, returned write/readback, shutdown tracing and restart
remain **UNVERIFIED** physically.

Worktree `/home/jadams/tmp/k230-mainline-root-path`, branch
`audit/mainline-root-path`, base `6533f27a1857aeba45d7b5a6849a5abb329780c2`;
only this note is owned. No board/build reservation. The preceding cached
handoff status scan completed with exit zero and is reused for task start.

## Exact source permits a late toggle

The inspected candidate is the same installed `4wkhxf55...` kernel,
`jvz4v73...` source and `asj7l4zj...` bundle pinned with full paths and hashes
in [the shutdown audit](shutdown-path-audit-2026-10-02.md). Its dev-output
configuration has `CONFIG_SYSFS=y`, `CONFIG_TRACEPOINTS=y`,
`CONFIG_SERIAL_8250_CONSOLE=y`; security lockdown LSM is not enabled.
All source paths below are relative to that exact `jvz4v73...` source.

- `init/main.c:794–795` declares a mutable boolean with
  `core_param(initcall_debug, initcall_debug, bool, 0644)`.
- `include/linux/moduleparam.h:344–346` gives this core parameter an
  unprefixed name and normal boolean operations, without unsafe/hardware flags.
- `kernel/params.c:817–843` puts unprefixed core parameters in the `kernel`
  module kobject. The parameter group is `parameters`. The expected path is
  **`/sys/module/kernel/parameters/initcall_debug`**, readable by all and
  writable by root. Its store operation invokes the bool setter
  (`params.c:579–598`), which accepts `1`; its getter prints `Y\n` or `N\n`
  (`params.c:312–334`). This is not a boot-only, read-only parameter.
- Device shutdown and syscore shutdown read this boolean directly before
  their trace lines (`drivers/base/core.c:4920–4936`,
  `drivers/base/syscore.c:125–128`). A successful late write therefore enables
  those checks without needing kernel changes or verbose boot.
- Boot initcall tracepoint registration is different: `start_kernel` calls
  the `__init` registration helper only if the boolean is already true at
  `init/main.c:1088–1089`. Writing later does not call this helper or replay
  completed initcalls. With this configuration it enables shutdown's direct
  checks, not retroactive boot tracing.

The exact bundle's selected console argument is `console=ttyS0,115200n8`.
It has `loglevel=4` followed by `loglevel=7`; the final level already permits
the shutdown `dev_info` and syscore `pr_info` messages. The runtime proposal
needs no `initcall_debug` boot argument, extra console argument or persistent
environment change.

## Bounded operator/controller proposal

After independently verified protected normal recovery, use the reviewed
nondebug minimal trial for this exact bundle/system. Obtain fresh receipt,
true, proc mkdir/mount and uptime gates first. Only after those returned gates:

1. Separately bracket `/bin/mkdir -p /sys` and inspect `/proc/mounts` with
   shell builtins. If `/sys` is already mounted, require exactly one sysfs
   entry; reject another filesystem or duplicate entry. Otherwise perform
   exactly one `/bin/mount -t sysfs -o nosuid,nodev,noexec sysfs /sys` and
   verify its returned mount-table entry. Preserve mount-table redirection
   failures; use `if ...; then ...; fi` in scan loops so a nonmatching final
   row does not accidentally become the scan's failure status.
2. Separately bracket builtin `test -r` and `test -w` on the exact parameter
   file. Read with `IFS= read -r _k230_before < /sys/module/kernel/parameters/initcall_debug`
   and require the complete value `N` for this nondebug trial.
3. Separately bracket builtin
   `printf '1\n' > /sys/module/kernel/parameters/initcall_debug`.
   Capture the redirection/write status, then independently read back with
   `IFS= read -r _k230_after < /sys/module/kernel/parameters/initcall_debug`
   and require exactly `Y`. Suppress incidental utility/parameter stderr;
   publish only fixed stage RC and expected-value match booleans.
4. Only returned write RC zero **and** returned readback match may authorize
   the existing single `/bin/reboot -ff` command and normal-return wait.
   There is no full `/init` activation, root mount, filesystem repair, driver
   unbind or persistent write in this diagnostic.

Each stage needs its own fresh-token `BEGIN`/`RC`/`END` markers and a finite
host deadline (at most 20 seconds per child/setup stage is a proposed ceiling,
not an observed runtime). Missing, stale, duplicate or truncated final markers
mean unknown/recovery-required: send no next child, retry, exit, Ctrl-C or
reboot. A returned known setup failure must skip the toggle and trace request;
any existing safe recovery requires healthy protocol acknowledgements. Retain
the reviewed single-reboot 180-second normal-return bound and independent
protected normal postflight. The runtime flag is volatile and disappears on
reset. Its sysfs write is an intentional diagnostic state change, not a
read-only board operation; this note itself performed neither.

The [shutdown audit](shutdown-path-audit-2026-10-02.md) explains why the last
shutdown trace is callback entry, not completion, and why probe drains,
device locks and runtime-PM barriers can wait before any trace. This proposal
does not close those gaps or guarantee console visibility.

## Serial reopening is not evidence of target shutdown

Installed pyserial 3.5 source at
`/usr/lib/python3.14/site-packages/serial/serialposix.py` was read with Python
`inspect`, without constructing/opening a serial device. `Serial.open()`
opens the host tty, reconfigures termios, applies DTR/RTS state and flushes
input. `Serial.close()` closes the tty and cancellation pipe descriptors.
Constructor defaults are `xonxoff=False`, `rtscts=False`, `dsrdtr=False`.
The controller selects 115200 and `exclusive=True` without overriding those
defaults. Reopening can discard received bytes; while closed, normal capture
and buffer continuity are absent. These operations provide no target-side
kernel-stop instruction.

The candidate's `drivers/usb/class/cdc-acm.c:676–694`, `696–738`, `764–780`
illustrates ordinary CDC control-line changes, read-URB activation and shutdown.
It is **not a verification of the host's running kernel version**. The
repository's prior [CH342 open audit](../ch342-open-garbage.md) separately
grounds historical host baud/programming and ModemManager issues; no current
ModemManager state or new recurrence was tested here.

The original board schematic in the main checkout,
`repo/schematic/T-Display K230_V1.0_NEW.pdf`, was read with `pdftotext -layout`.
U11 is labelled CH342K; its ten pin labels are USB, power/ground and the two
TXD/RXD pairs, consistent with the earlier audit's net list. There is no U11
DTR/RTS/CTS pin establishing a modem-control connection to K230 reset or its
console. The selected DT uses `serial0:115200n8`, not a hardware-flow-control
console option. Kernel console CTS waiting additionally requires console flow
and CTS flags (`include/linux/serial_core.h:1182–1187`), so a host tty's DTR
state is not by itself evidence of target console flow control.

Ordinary capture loss, bridge USB state, target progress and console visibility
remain distinct unknowns. Zero bytes after reopening cannot decide among them;
this source inspection cannot attribute the verbose trial's silence to DTR,
prove a target hang or prove shell readiness. The coordinator owns the
readiness/unknown-result correction and any later physical trial. No source
change was duplicated here.

## Narrow checks

Commands were `rg -n` / `sed -n` on the files above, Python `inspect` on
pyserial, a filtered read of only console/loglevel/debug arguments from the
immutable bundle, and `pdftotext -layout` followed by normalized U11/pin-label
selection from its private host text output. No raw UART, private cmdline or
credentials were read/published. `openspec validate the-board-runs-a-mainline-kernel --strict`
and `git diff --check` validate this documentation; no runtime test is claimed.

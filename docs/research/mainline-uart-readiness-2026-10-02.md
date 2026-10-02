# Mainline UART and shell readiness source audit

Recorded `2026-10-02T18:42:38Z`. Evidence class: read-only host source and
candidate-DTB inspection. No board, serial, MMIO, build or controller edit.
Worktree `/home/jadams/tmp/k230-mainline-uart-readiness`, branch
`audit/mainline-uart-readiness`, base
`6c03cc496fe8f74d1222099280fe0de458d8b05e`. Only this note is owned;
no board/build reservation. Cached start `tools/work-status.py` completed
with exit zero at idle I/O priority.

The coordinator reports that the quiet `--runtime-shutdown-trace` trial of
the exact `asj7l4zj...` / `4wkhxf55...` candidate printed `Run /bin/sh as init
process` at kernel uptime `4.026622`, then a no-job-control message and
`sh-5.3#`. Receipt lines had already been sent during boot; input echoes
contained garbling, bells/control sequences, and the later shell showed a
continuation prompt `> `. No fresh receipt was accepted and no candidate
reboot was requested. These are coordinator-provided observations, not an
independent capture review or new physical proof by this auditor. The shell
was preserved; no corrective input is proposed for that unknown parser state.

## Concrete timing issue precedes any UART-cause inference

At the audited controller revision, `main()` waits for `Linux version
7.3.0-rc5` and invokes `await_initrd_ready()` **only for `debug_shutdown`**
(`tools/mainline-drm-initrd-shell-trial.py:1276–1291`). Runtime shutdown tracing
and ordinary minimal mode proceed directly to `run_probe_protocol()` after
the version banner. The latter immediately enters `await_reception()`
(`703–734`): up to eight attempts, one second each, drain received output and
send the single-quoted builtin receipt line (`224–226`, `545–576`):

```sh
PATH=/bin:/sbin; export PATH; printf 'K230_RDINIT_RX FRESH_32_HEX_TOKEN\n'
```

The kernel version banner is early boot output, not a shell readiness marker.
`session.pump()` drains host RX, not the board's UART or shell input queue.
Fresh-token parsing correctly rejects echoed/stale receipt text but does not
prevent sending before the consumer exists. If part of a quoted line is lost
or retained across startup, later retries can enter an unfinished shell quote;
there is no automatic proof that the next line starts at a fresh command.
The reported continuation prompt is consistent with incomplete shell input;
its appearance does not by itself identify baud corruption or a kernel stall.

The coordinator's restart agent owns the common readiness-gate correction.
This audit changes no controller or tests. Missing receipt still means no
accepted command execution, no following child probe and no reboot request.

## Exact UART mapping and clocks

Full kernel/source/configuration/bundle paths and hashes are preserved in
[the shutdown audit](../evidence/mainline-restart/shutdown-path-audit-2026-10-02.md).
Source below is the exact installed
`/nix/store/jvz4v73g8a67pqwm06v079h6s1cpqr9s-linux-mainline-k230-drm-src`,
based on Linux `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`.
`fdtget` on
`/nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files/k230-tdisplay-mainline-drm.dtb`
confirmed:

| Property | Exact candidate value |
| --- | --- |
| `aliases.serial0` | `/soc/serial@91400000` |
| `chosen.stdout-path` | `serial0:115200n8` |
| UART compatible/status | `snps,dw-apb-uart`, `okay` |
| UART address/access | `0x91400000`, four-byte register access, register shift 2 |
| UART interrupt | DT specifier 16/type 4, not a measured Linux IRQ count |
| Functional clock | sysclk phandle 6, ID 161 (`K230_LS_UART0_RATE`) |
| Reset | controller phandle 7, ID 50 (`RST_UART0`) |
| `clock-names`, fixed `clock-frequency`, `pinctrl-0` | absent |

The bundle selects `console=ttyS0,115200n8`; host `Session` opens the same
serial device once at 115200 (`1038`) and does not reopen it at Linux/shell
startup. Configuration has `SERIAL_8250_DW`, `SERIAL_8250_CONSOLE` and
`SERIAL_8250_DWLIB` built in. The SoC UART0 node is at
`arch/riscv/boot/dts/canaan/k230.dtsi:112–121`; the board enables it without
adding a pinctrl consumer. This gives no source basis for a new UART0 pinmux
selection during this boot. DT selection is not an independent wire/baud
measurement.

Importantly, **both UART0 gates are critical**:
`drivers/clk/clk-k230.c:678–682` marks its APB gate `CLK_IS_CRITICAL`, and
`903–914` marks its functional gate critical and provides a divider 1–8 from
PLL0/16. The clock core prepares/enables critical clocks at registration
(`drivers/clk/clk.c:4133–4156`) and refuses their last disable/unprepare
(`1120`, `1260`). Its unused-clock walk skips nonzero enable counts (`1539–1578`).
Direct UART0 gate loss from normal unused-clock cleanup therefore ranks below
the concrete timing problem; it is not supported merely by other peripherals'
different clock flags. Parent rates, divisor accuracy and actual RX error
counts remain unmeasured.

## Real console-to-TTY transitions can discard early input

The exact DesignWare driver uses the unnamed functional-clock fallback when
`baudclk` is absent, obtains the optional `apb_pclk`, deasserts reset, then
registers the port (`drivers/tty/serial/8250/8250_dw.c:708–735`). This compatible
uses the normal clock-setting termios path, not the skip-set-rate quirk.
`dw8250_set_termios()` (`473–491`) requests baud × 16, rounds/sets the clock,
then programs UART termios/divisors. At 115200 the requested rate is
1,843,200 Hz; the actual rounded clock and resulting wire baud cannot be
derived without the actual parent rate. Critical gates do not forbid divider
changes.

`uart_port_startup()` calls UART startup and then inherits/reapplies console
termios (`drivers/tty/serial/serial_core.c:304–336`). The 8250 startup clears
RX/TX FIFOs (`8250_port.c:2325–2331`; helper `496–503`); DW idle entry disables
RX interrupts and clears FIFOs while entering divisor-change idle
(`8250_dw.c:135–171`). Thus input arriving across startup/reconfiguration can
be dropped or partially retained without a persistent wrong-baud condition.
These source paths establish possibility, not which path affected this trial.

The kernel opens `/dev/console` for init's descriptors after basic initcalls
and initramfs completion (`init/main.c:1632–1645,1677–1680`). Its
`Run /bin/sh as init process` line is printed **before** `kernel_execve`
(`1472–1484`). That line is a useful phase checkpoint, not proof that shell
initialization/readline has completed. Readable kernel TX also does not prove
that a complete host command reached shell RX. The historical same-bundle
[minimal trial](../evidence/mainline-restart/physical-minimal-2026-10-02/README.md)
did return receipt/true/proc/uptime; that is prior bidirectional command
evidence, not acceptance of this later failed receipt or every boot state.

## Small discriminator and limits

For a later coordinator-owned trial after protected recovery, first passively
observe the fresh candidate phase and kernel shell-entry checkpoint in every
mode. Where available, observe the initial shell prompt before the first
quoted command. Then require a fresh executed receipt before any child. A
prompt, echo or shell-entry line alone cannot replace the receipt. Keep the
readiness wait finite and preserve missing-marker/unknown recovery semantics;
do not try to repair an unmatched quote by sending more receipt lines or
closing/reopening the port.

Returned clean receipt/minimal gates after that timing correction would
distinguish early-input contamination from a persistent RX problem on that
new trial. Continued garbling after passive shell readiness would leave
baud/clock/divisor accuracy, receive errors and host bridge state as separate
questions needing bounded evidence. No clock-ignore flag, MMIO read, arbitrary
interrupt survey, pinmux change or UART driver patch is justified by this
source audit. It does not explain or prove restart callback execution, and
runtime shutdown tracing was not reached by the failed receipt protocol.

Checks were narrow `rg -n`/`sed -n` reads of the exact source/controller and
configuration, plus `fdtget -t s/-t x` of the table properties. No private raw
UART or credentials were read/published. Validation:
`openspec validate the-board-runs-a-mainline-kernel --strict` and
`git diff --check`. No new physical pass, cause finding or task completion.

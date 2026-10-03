# Mainline debug-console receive boundary

Read-only source audit, 2026-10-03 UTC, source checks completed at 05:22 UTC. Worktree
`~/tmp/k230-mainline-uart-rx-audit`, branch `audit/mainline-uart-rx`, base
`b2e219e21532df62871ff0ff8dbd0358c720817a`. Only this note is owned. No board,
UART, kernel build, driver change or terminal-setting change was performed.
This supports current mainline task 5b.5; it does not complete it.

The corrected debug controller recognized the candidate manager and primary
prompt, then sent one receipt command. No echo or receipt arrived during ten
seconds; it stopped before identity, ownership or diagnostic commands. See the
[physical packet](../evidence/mainline-system-trial/debug-receipt-physical-2026-10-03/README.md).
The operator subsequently reset and qualified protected normal Home. This was
not automatic candidate recovery. A visible prompt establishes output, not
working input, and does not identify a kernel fault.

## Exact material read

The unchanged optional candidate is bundle
`/nix/store/5yqilsfyj35jzrcqjjqilkr6sd47qlms-k230-mainline-drm-trial-boot-files`,
kernel `/nix/store/9vdk79pa4pm38mlmbflkqh4i4sc9kha0-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`,
and patched source
`/nix/store/l0j3rf11mr65wl5x88a9zzma45ciz687-linux-mainline-k230-drm-src`.
Mainline pin is `72d3fcf802c45d00b300f25b848a93c3a2bd7c7e`.
Actual configuration is
`/nix/store/7vxby0h1nz78r9qzbqfjjs9vw4x7gpl0-linux-config-riscv64-unknown-linux-gnu-7.3.0-rc5`.
Lines 541, 2983–3001 and 7428–7433 enable PM, 8250 console, DW/DWLIB, DMA,
RISC-V INTC and SiFive PLIC. Configuration alone does not show active RX state.

Vendor source read is `/nix/store/pn7bm6ck5a3x6pnk1ng30hlf24qn85jx-source`,
pin `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`, selected by
[kernel-src.nix](../../nix/kernel-src.nix). Protected normal uses
`/nix/store/03zyl0mjsxbjyisb3lhjaxswpxm71ap6-linux-riscv64-unknown-linux-gnu-6.6.36-xuantie/Image`.
Vendor `arch/riscv/configs/k230_defconfig:145–147` selects 8250 console/DW;
this defconfig was read, not substituted for the realized normal configuration.

Commands were bounded local reads, principally `sed -n '<first>,<last>p'
<source>/<path>` and `rg -n '<symbol>' <source>/<path>`, plus a JSON inventory
lookup in the previously inspected exact initrd archive. No private raw UART
content is reproduced. The exact initrd remains
`/nix/store/jdgads5ibbb0zflglhjfncq8ayc1jbfz-initrd-linux-riscv64-unknown-linux-gnu-7.3.0-rc5/initrd`,
SHA-256 `046c5b012a2b993caa1082926e9928c14bccc0fff456f20f8716c91d13f51842`.

## Clock, interrupt and receive paths

The candidate enables upstream UART0 at `serial@91400000`, retains
`snps,dw-apb-uart`, 32-bit register accesses shifted by two, PLIC source 16
with level-high type, reset UART0, and the unnamed UART0 rate clock. Repository
`nix/dts/k230-tdisplay-mainline.dts:76,85,293–295` selects serial0 and
`115200n8`. [Upstream k230.dtsi:112–121](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/arch/riscv/boot/dts/canaan/k230.dtsi#L112)
defines the device. Vendor uses the same address, access shape and interrupt,
but a fixed 50 MHz clock (`k230.dtsi:182–186,261–269`), enabled by repository
`nix/dts/k230-tdisplay.dts:140–142`.
[Vendor source](https://github.com/ruyisdk/linux-xuantie-kernel/blob/7d4e1f444f461dbe3833bd99a4640e7b6c2cd529/arch/riscv/boot/dts/canaan/k230.dtsi#L261)
grounds this difference; it does not establish either physical clock rate.

Both mainline UART0 APB and functional gates are `CLK_IS_CRITICAL`, at
`drivers/clk/clk-k230.c:678–682,903–914`.
[Clock source](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/clk/clk-k230.c#L678)
The clock core enables critical clocks on registration (`clk.c:4133–4156`),
rejects their last disable/unprepare (`1250–1272,1120–1130`), and unused cleanup
skips nonzero enable counts (`1539–1560`). Thus a blanket assertion that late
unused-clock cleanup turns UART0 off is unsupported. Dynamic divider/rate
changes remain a separate mechanism: DW termios requests baud times 16 and
updates the port clock (`8250_dw.c:473–491`); vendor has the same broad operation
at `379–400`. Neither actual baud error nor failed rate change was observed.

RX is interrupt-driven PIO for this kernel console. Although DMA is configured,
`8250_port.c:2372–2382` explicitly removes DMA for a console. Startup links the
IRQ handler (`8250_core.c:154–178`); nonzero IRQ ports do not receive the IRQ0
polling fallback (`264–286`). PLIC maps hardware source IDs to Linux IRQs
(`irq-sifive-plic.c:320–368,382–421`), so source 16 must not be treated as an
observed Linux IRQ number.
[8250 startup](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/tty/serial/8250/8250_port.c#L2372),
[PLIC dispatch](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/irqchip/irq-sifive-plic.c#L382).

DW reads IIR and dispatches to locked 8250 RX handling
(`8250_dw.c:395–458`; `8250_port.c:1816–1864`). The common receive path increments
`icount.rx` before character filtering and flip-buffer delivery (`1627–1687`).
With CREAD absent, termios sets the DR ignore mask (`2740–2745`). Accordingly,
an RX-count increase can coexist with no shell echo. It is aggregate driver
progress, not proof that the exact receipt bytes reached the shell.
[Receive path](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/tty/serial/8250/8250_port.c#L1627).

Terminal close/startup/termios are relevant transitions: serial-core shutdown
marks the TTY uninitialized and calls hardware shutdown (`serial_core.c:389–429`);
successful reopen calls startup then line settings (`304–354`). DW divisor
changes temporarily disable IER and clear FIFOs (`8250_dw.c:129–207`), with
documented restore through `idle_exit:102–120`. Termios then programs IER,
divisor and FIFO (`8250_port.c:2809–2855`). No missing restore defect was found
in these paths. Userspace TTY reset/vhangup/lifetime is audited separately.
[DW transitions](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/tty/serial/8250/8250_dw.c#L102).

Kernel console output polls TX readiness (`8250_port.c:3283–3297`). Its write
path saves/disables then restores IER (`3438–3531`); it does not prove receive
IRQ service. The same exact candidate's successful minimal and standalone
blkid protocols demonstrate bidirectional input in the rdinit shell, including
the no-clock-ignore clock-fixed candidate. A universal static wiring/IRQ/DMA
or UART-unused-clock explanation does not fit those observations. This does
not rule out a later terminal/driver/IRQ transition under systemd.

## Bounded next discriminator; not an implemented trial

<!-- UNVERIFIED --> The failed debug terminal's termios, RX/error counters,
active Linux IRQ and runtime-PM state were never captured. No driver patch,
MMIO write, IRQ kick, global clock policy or repeated receipt is justified.

Prepare an immutable, initrd-only autonomous reporter before a further trial,
using the current kernel and the same protected bundle checks. It must run
without successful serial input, prove its own PID/unit/initrd identity and
unmounted sysroot boundary, and emit fresh, bounded private frames. Reuse an
already owned terminal descriptor to read TCGETS and TIOCGICOUNT; do not change
baud, CREAD, flow control or repeatedly close/reopen the terminal to sample it.
TCGETS is a getter (`tty_ioctl.c:804–819`); TIOCGICOUNT copies cached counters
under the port lock (`serial_core.c:1259–1285`). A reviewed small helper is
needed for explicit ioctl data; Python is not assumed available in this initrd.
[Getter implementation](https://github.com/torvalds/linux/blob/72d3fcf802c45d00b300f25b848a93c3a2bd7c7e/drivers/tty/serial/serial_core.c#L1259).

If IRQ comparison is included, obtain the Linux IRQ via the cached
TIOCGSERIAL getter (`serial_core.c:785–816`) and retain only that bounded
`/proc/interrupts` row before/after one controlled receipt. Do not dump arbitrary
IRQ rows or infer a per-byte attribution from an IRQ-count increase. Optional
runtime-PM reads must first verify the exact UART sysfs device ancestry and
remain bounded/read-only. Avoid `/proc/tty/driver/serial` as a supposedly pure
cached probe: its privileged path temporarily changes PM state and reads modem
control (`serial_core.c:1996–2034`). No raw registers are needed.

Record baud/framing, CREAD/CLOCAL/CRTSCTS/HUPCL and line discipline; compare
before/after RX, framing/parity/overrun/buffer counters and selected IRQ count.
An increasing RX count with unchanged termios narrows toward TTY consumption
or filtering; no RX increase leaves IRQ, clock/divisor, FIFO and input arrival
unresolved. Neither outcome alone identifies a faulty driver. The archive
inventory contains coreutils `stty`, but tool inventory is not physical proof
and does not replace the descriptor-based counter helper.

Design a single prearranged direct return only after known-safe reporter and
initrd guards, with fresh acknowledgement and passive 180-second protected
normal postflight. This must not require a second host command after unknown
input. A userspace timer/timeout cannot guarantee recovery from kernel or
uninterruptible hangs; operator reset remains necessary if completion or return
is unknown. Do not widen root activation or masks, run coldplug retries, or
send further input after an unknown receipt. Reporter source/tests, exact
initrd artifact inspection, coordinator review and a separate reserved physical
trial remain required. Ordinary usable root and real touch remain UNVERIFIED.

Host validation: `openspec validate the-board-runs-a-mainline-kernel --strict`
passed. `git diff --check` is the narrow documentation check. No hardware gate
or task checkbox was changed.

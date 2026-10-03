# Serial-only observer: boot/output discrimination

Evidence class: exact installed source/config audit and coordinator-reported
physical milestones. No implementation, build, board access or raw UART read
was performed. Cause attribution and the next comparison are **UNVERIFIED**.
Task 5b.5 remains open.

Worktree `/home/jadams/tmp/k230-mainline-serial-only-boundary`, branch
`audit/mainline-serial-only-boundary`, base
`33242719c08d38cf0758e8181088fd57c5dfcd6e`; this note is the sole owned path.
The coordinator owns hardware/builds. Cached start/handoff status scans run at
idle priority with output outside the repository; slow scans do not hold this
source deliverable.

## Observation and source order

The coordinator reports that the reviewed serial-only controller passed its
32 host tests and full immutable preparation. Bundle `16cpjjiifxgwyb6bndhi39vfmlvcdw6h`,
system `k1zjqdn4ks7b5dd7b3py6cavhf85g6j6` and kernel `9vdk79pa4pm38mlmbflkqh4i4sc9kha0`
were unchanged from the [dual-console READY trial](../evidence/mainline-system-trial/uart-observer-physical-2026-10-03/README.md).
Only the reviewed volatile `console=tty0` removal was applied. Serial console
enabled; no systemd banner, observer frame, primary prompt, host input or
restart followed. The bounded return wait ended with controller exit 2.
The coordinator committed the [serial-only failure packet](../evidence/mainline-system-trial/uart-observer-serial-console-physical-2026-10-03/README.md)
as `bb76750c`; its private raw-log SHA256 is
`3446fdaaa2e524d05026409d66a6744c60878b66bd86c51a2fbe11e3f4492d24`
(47,035 bytes). The earlier dual-console packet has raw-log SHA256
`7fefbf17759b9ea8accd808a3e6cb9fcdf92ad811cb730eba62118450ddd8427`
(53,905 bytes).
Operator reset recovery was pending at this audit checkpoint. This is a
coordinator-reported failure, not a new observation by this auditor.

Safe final milestones were DRM registration at 2.548986, Goodix input
registration at 2.810421, unused-clock cleanup at 2.811995, unused-power-domain
cleanup at 2.812201, ALSA list at 2.812254 and no soundcards at 2.812261. There
was no visible init-memory freeing or `Run /init`. Both private captures
contained `fbcon:`/`fb0` adoption strings and neither contained the stage-1
fbdev-skip message. Those strings narrow the earlier conditional fbcon limit;
they do not prove an active tty0 write or a blocked framebuffer callback.

Exact source/config paths and pins are in the
[READY/write-boundary audit](mainline-uart-ready-printk-boundary-2026-10-03.md).
All line references here were checked against that installed `l0j3rf11…`
source and `7vxby0h…` config, matching the same `9vdk79…` kernel.

`drivers/clk/clk.c:1588–1627` prints the cleanup marker before runtime-PM
acquisition, prepare-lock acquisition and clock traversal. It is an entry
marker. The later PM/ALSA late-initcall milestones show progression beyond
that clock initcall; they do not identify one clock as responsible for a later
stall. `sound/last.c:10–29` prints the final observed ALSA lines and returns 0,
as a `late_initcall_sync`. Do not equate its last printed line with a stuck
ALSA callback or assume no later initcall ran.

The UART0 functional gate is critical (`drivers/clk/clk-k230.c:903–914`);
the APB gate is also critical, as established in the
[UART audit](mainline-uart-rx-boundary-2026-10-03.md). Earlier no-bypass
five-clock minimal/blkid trials reached a shell, accepted UART commands and
returned automatically. A universal static UART clock/IRQ/wiring failure does
not fit that evidence. Those trials used a different userspace/init path;
they do not establish liveness of this observer run.

After initcalls, `init/main.c:1675–1705` performs `wait_for_initramfs()`,
`console_on_rootfs()`, init accessibility handling and `integrity_load_keys()`.
Returning to `kernel_init()` is followed by `async_synchronize_full()`, init
memory cleanup, read-only mapping work and init execution
(`init/main.c:1554–1595`). The initramfs wait joins a dedicated async cookie
domain (`init/initramfs.c:770–798`). This is a concrete set of unseen boundaries,
not proof that any particular wait blocked. The same archive already reached
READY in the earlier trial, so generic archive absence/corruption is not
established by this failure.

## Existing-image early console comparison

There is a source-supported way to alter printk delivery without changing the
Image. A retained `CON_BOOT` console makes `have_boot_console` stay true;
`keep_bootcon` prevents normal deregistration (`kernel/printk/printk.c:3868–3878`,
`4212–4225`). The kernel then does not start nbcon printer threads
(`printk.c:3827–3837`), and normal flush policy uses the legacy path instead of
nbcon offload/atomic selection (`kernel/printk/internal.h:194–215`). In the
current path, UART work can be offloaded through `irq_work` to `pr/ttyS0`
(`kernel/printk/nbcon.c:1311–1342`, `1375–1398`). Thus retaining a polling boot
console is a concrete output-policy comparison, not a clock or RX fix.

Two explicit forms need separate qualification:

- `earlycon=sbi keep_bootcon`: the installed config enables
  `SERIAL_EARLYCON_RISCV_SBI` but disables `RISCV_SBI_V01`. Therefore it requires
  an actual detected SBI DBCN extension; legacy SBI console fallback is not
  available (`drivers/tty/serial/earlycon-riscv-sbi.c:40–52`,
  `arch/riscv/kernel/sbi.c:691–695`). The coordinator checked the literal safe
  `SBI DBCN extension detected` banner in both exact private logs identified
  above. `sbi_init()` precedes early-parameter parsing
  (`arch/riscv/kernel/setup.c:309–319`), so this detected availability is set
  when explicit SBI earlycon setup runs. This qualifies the **preferred first
  source-supported comparison**, without the UART fallback's direct IER
  change or baud assumptions. Actual boot-console registration/retention
  markers are still required in any future run. Late printk cleanup also
  unregisters boot consoles whose live callbacks/data reside in init memory
  (`printk.c:4431–4456`); the SBI write callback and generic early console/data
  here are ordinary static objects, not `__init`/`__initdata`
  (`earlycon-riscv-sbi.c:25–38`, `drivers/tty/serial/earlycon.c:29–37`).
  Firmware printing its own banner is insufficient qualification. The DBCN
  write loop is firmware-mediated and has no timeout if writes return zero
  (`earlycon-riscv-sbi.c:25–38`).
- `earlycon=uart8250,mmio32,0x91400000 keep_bootcon`: UART0 address, 32-bit I/O
  and shift 2 come from the exact enabled DT node
  (`arch/riscv/boot/dts/canaan/k230.dtsi:112–120` and the board UART0 enable).
  This contains **no baud or clock-rate argument**. Explicit mmio32 parsing
  sets shift 2 (`drivers/tty/serial/earlycon.c:86–113`). With baud unset, 8250
  early setup assumes firmware initialization and masks IER once; it does not
  reset FIFO or program a guessed divisor
  (`drivers/tty/serial/8250/8250_early.c:154–172`). Subsequent TX writes poll LSR
  with an unbounded loop (`8250_early.c:86–106`). This is a reviewed driver
  operation using a qualified DT address, not an arbitrary MMIO probe.

Do not substitute bare `earlycon`: this config enables `ACPI_SPCR_TABLE`, so
the bare-parameter branch selects the ACPI SPCR path rather than the DT
stdout path (`drivers/tty/serial/earlycon.c:223–242`). Do not add a baud to the
explicit UART form: absent a qualified rate, its generic default clock could
reprogram a wrong divisor. The early console is intentionally an additional
kernel TX path; it is outside the observer helper's getter-only contract.

`keep_bootcon` has a real tradeoff: the kernel explicitly notes that boot and
regular console hardware registers cannot be synchronized (`printk.c:3827–3832`).
It changes output scheduling and timing, may duplicate/interleave output, and
retains a polling path that can itself block. It does not guarantee automatic
recovery. Before any trial, require operator reset and the full protected normal
postflight, unchanged selected artifacts, and a separately reviewed controller
allowlist for precisely one explicit earlycon form plus `keep_bootcon` on the
serial-only argument set. Preserve all identity/control guards and printed
exact arguments; never enable a permanent clock bypass or `saveenv`.

If this comparison reveals later kernel/init progress, it establishes dependence
on this output/boot-console policy, with the timing perturbation qualified.
It cannot identify a broken irq_work, UART interrupt, clock or renderer. Exact
observer CRC/sequence parsing must not silently accept duplicated/interleaved
records. Retained SBI and regular ttyS0 can print the same record twice on the
shared UART. The existing strict parser may therefore reject this run even
when output progresses. Preserve the current strict parser: retain a recovered
failed/unknown diagnostic classification while recording raw fresh progress
and separately qualifying any protected automatic return. Send zero receipts
when duplicate readiness fails. Do not claim RX success. If actual duplicated
output later makes collapse necessary, it requires a separately reviewed
explicit mode, bounded maximum-two/source semantics and meaningful tests;
no such acceptance change is proposed or implemented here. Raw wire
provenance stays intact. Existing unknown-state behavior remains decisive. No receipt until the
fresh READY/before/prompt gates; unknown output stops input and still requires
the passive deadline/operator recovery. This plan is not a command to run now.

## If existing boot arguments are insufficient

A finite optional diagnostic kernel patch can bracket the unseen boundaries:
basic-setup exit; initramfs wait enter/exit; root-console open enter/exit;
init-accessibility/namespace boundary; integrity-key work enter/exit; global
async wait enter/exit; init-memory cleanup enter/exit; and init-exec entry.
Use fixed public step names and no cmdline, pointer, label or address dump.
Every marker can briefly call `nbcon_cpu_emergency_enter()`, `pr_info()` and
`nbcon_cpu_emergency_exit()` to attempt direct UART atomic flushing
(`kernel/printk/nbcon.c:1709–1758`, `kernel/printk/internal.h:216–227`). Use this
as an alternative on the serial-only/no-boot-console baseline, rather than
stacking it with `keep_bootcon`, which changes the emergency flush policy too. Never
hold emergency state/preemption disabled across the bracketed blocking work.
This separates selected task progress from normal nbcon-thread delivery more
directly than another quiet retry, but still cannot guarantee output from a
halted kernel or an unavailable UART. Ordinary log severity alone does not
select nbcon emergency priority.

The marker helper and opt-in flag must survive `free_initmem()`; do not place
them in `__init`/`__initdata` if used afterward. Disabled mode must be a no-op.
A separate reviewed opt-in kernel/bundle and explicit host identity acceptance
are required: current observer Image/base-kernel equality guards must not be
bypassed. Host source/API/object proof and a root-owned full matching build
precede any physical gate. No such patch/build was made here.

Unfiltered `initcall_debug` adds broad output without bracketing the waits
after initcalls.
Filtered bootconfig tracing is unavailable on this exact image because
`CONFIG_BOOT_CONFIG` is unset, despite ftrace/tracepoints being enabled. The
supported `initramfs_async=0` knob changes where extraction is joined
(`init/initramfs.c:603–608`, `789–798`), but does not by itself distinguish lost
printk delivery from an actual init wait; it is weaker than boundary evidence.

Validation: exact installed source/config reads and `nl -ba` citation checks;
`git diff --check`/commit whitespace check. No claim of a kernel root cause,
automatic observer recovery, usable root, panel frame or glass touch follows.

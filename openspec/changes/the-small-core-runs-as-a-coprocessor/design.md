## Context

See `proposal.md`, `docs/closeout/second-core-plan.md`, and
`docs/research/second-core-feasibility.md` for the full audit trail behind
the SMP-to-AMP redirect. This document covers only the AMP architecture
itself: what runs where, which registers and memory regions are involved,
what firmware to run first, and how each step is proved.

Layer map for this change, per `.skills/k230-spec-change/SKILL.md`'s design
rule ("name the layer"):

- **Device tree**: a reserved-memory carveout and a new consumer node for the
  existing `canaan,k230-sysctl-reset` reset controller.
- **Kernel**: a new, K230-specific `remoteproc` driver; no existing driver
  is modified.
- **Firmware (CPU0)**: a new bare-metal image, built the same way as
  `tools/small-core-heartbeat.{S,ld}` already is, extended incrementally.
  Not RT-Smart, not Zephyr, not FreeRTOS, for this first step (see below).
- **Nix**: no change to the normal image's derivations; a new, default-off
  derivation for the CPU0 firmware image, following the precedent of
  `uboot-k230-cpu0-identity-probe` / `stage1-cpu0-identity-probe`
  (`flake.nix:275-278`).

## Goals / Non-Goals

**Goals:** decide the Linux-side driver shape, the firmware choice, the
cache-maintenance contract, the recovery/authorization gate, and the first
workload, each with a citation to vendor source, the TRM, in-tree kernel
documentation, or an external reference; stage the work so early tasks need
no board and no register write.

**Non-Goals:** implementing any of the drivers or firmware described here
(this is a proposal); choosing the K230 mailbox hardware driver (its
register layout has not been read into this project); deciding LoRa,
battery/charger, or keyboard-base ownership; giving CPU0 any ability to
reset CPU1 or Linux automatically; bringing up RT-Smart.

## Decisions

### 1. Linux side: a new, minimal remoteproc driver — nothing to reuse as-is

**Does the vendor kernel or SDK already have one? No.** A direct read of the
pinned kernel source (`/nix/store/hn11x8zd5linl193d8q0k9k99b46zqbm-linux-xuantie-k230-src`,
pinned by `nix/kernel-src.nix` from `ruyisdk/linux-xuantie-kernel`) found:

- No file matching `*k230*mailbox*`, `*k230*rproc*`, or `*k230*remoteproc*`
  anywhere in the tree, and no `"k230"` or `"canaan"` string in
  `drivers/mailbox/`, `drivers/remoteproc/`, `drivers/rpmsg/`, or
  `drivers/watchdog/`.
- `drivers/misc/canaan/` exists but only holds `ai2d`, `gnne`, and `mmz` —
  the AI-accelerator and memory-zone helpers, nothing inter-core.
- No `mailbox` or `reserved-memory`/`rpmsg`/`remoteproc` property anywhere in
  `arch/riscv/boot/dts/canaan/k230.dtsi`.
- The vendor's `k230-amp.c` / `amp_test.c`
  (https://github.com/kendryte/k230_sdk/blob/main/src/little/linux/drivers/misc/canaan/k230-amp.c,
  reviewed in `docs/research/second-core-feasibility.md`, "Vendor AMP source
  establishes a release contract, not SMP support") is a raw misc-device
  driver: `open("/dev/k230-amp")`, map a DT-selected region, load an
  RT-Smart image, flush it from the calling CPU's cache by hand, write the
  CPU1 reset-vector register, then the `CPU1_RST_CTL` sequence — an `ioctl`
  loader, not a `remoteproc_ops` implementation. It creates no
  `struct rproc`, no virtio device, no resource table. Its release sequence
  is exactly the primitive this design reuses; its code is not, because it
  hardcodes vendor addresses and gives Linux no generic start/stop/status
  interface.

By contrast, this exact pinned kernel tree already carries, unmodified from
mainline, a same-vintage T-Head sibling SoC's mailbox and rpmsg drivers —
`drivers/mailbox/th1520-mailbox.c` (XuanTie TH1520, Alibaba, 2024) and
`drivers/rpmsg/th1520_rpmsg.c` — as an architectural precedent, though
neither is wired into any device tree in this tree and TH1520's mailbox
register layout is not K230's. There is no TH1520 remoteproc driver in this
tree either; `th1520_rpmsg.c` implements its own lightweight rpmsg-over-mailbox
client directly (`virtio`-based, but not via `drivers/remoteproc/`), which is
a second usable pattern if a full `remoteproc` load/boot lifecycle turns out
to be unnecessary for a firmware image Linux never actually loads from disk
in the first version (see Decision 5).

**Reset control and the vector registers.** The TRM- and source-grounded
register facts already collected in
`docs/research/second-core-feasibility.md` and
`docs/evidence/second-core/` map directly onto Linux abstractions already
present in the pinned kernel, which this driver should use instead of a raw
`ioremap` the way the vendor driver does:

- RMU (`sysctl_reset`) is at `0x91101000`, declared in
  `k230.dtsi:233-241` as `compatible = "canaan,k230-sysctl-reset"`. It is
  already bound by `drivers/reset/reset-k230.c`, which registers a generic
  `reset_controller_dev` (`k230_reset_probe`, `reset_controller_register`)
  over this exact block and is *already exercised by Linux today*: its own
  `k230_restart()` restart-notifier writes to this address range
  (`SYSCTL_BOOT_BASE_ADDR + CPU0_RST_CTL` at `drivers/reset/reset-k230.c:311-323`,
  though that offset — `0x60` inside `sysctl_boot`, not the CPU0 reset-request
  bit — is a whole-system restart path and should not be confused with the
  per-core `CPU0_RST_CTL`/`CPU1_RST_CTL` request bits described next; this is
  named only to show the register block is not a new, untouched surface).
  The reset lines this design needs are already named in
  `include/dt-bindings/reset/canaan-k230-reset.h`:
  `K230_RESET_CPU0_REG_OFFSET 0x4` / `K230_RESET_CPU1_REG_OFFSET 0xc`
  (matching the TRM's `CPU0_RST_CTL`/`CPU1_RST_CTL` at `0x91101004`/`0x9110100c`,
  section 2.1.4), each `K230_RESET_TYPE_CPU`, done bit 12, assert bit 0, plus
  a separate `K230_RESET_CPU0_FLUSH_REG_OFFSET 0x4` / `..._ASSERT_BIT 4` pair
  for the documented L2-flush-request bit. A K230 remoteproc driver should
  request its reset line the ordinary way —
  `resets = <&sysctl_reset 0x4 0 12 0>;` in DT, consumed with
  `devm_reset_control_get_exclusive()` and `reset_control_assert()`/
  `deassert()` — instead of a second, competing raw MMIO mapping of the same
  physical registers the reset-controller driver already owns.
- `sysctl_boot` at `0x91102000` (`k230.dtsi:244-247`) is declared only
  `compatible = "simple-bus"`, with no children and no driver claiming it —
  it is free for a new consumer. This is where the CPU reset-vector
  registers live: pinned U-Boot's `boot_baremetal` path
  (`arch/riscv/cpu/k230/cpu.c:125-160`) writes CPU0's vector at
  `0x91102100` and asserts/deasserts `CPU0_RST_CTL` at `0x91101004`; the
  2026-09-26 stage-1 audit separately records CPU1's vector write at
  `0x91102104`. No existing Linux binding names this register; the
  remoteproc driver either `ioremap`s this one small range itself (as the
  restart driver already does for its own purposes in the same block) or a
  small syscon/regmap wrapper node is added first. Which of those is worth a
  separate node is an open, small design decision left to the implementing
  task, not resolved here. **The exact width and side effects of a write to
  the vector register beyond what `boot_baremetal` already performs are not
  independently reconfirmed by this change** — this design reuses the
  pinned, already-executed sequence rather than deriving a new one.
- **Reserved memory.** `nix/dts/k230-tdisplay.dts:47-57` already carries a
  precedent `reserved-memory` node with `no-map` for the splash framebuffer.
  The AMP carveout for CPU0's firmware and its shared ring follows the same
  pattern, sized and placed to (a) sit inside the live 1 GiB DRAM window
  Linux otherwise manages (`docs/evidence/second-core/heartbeat-host.md`
  records `0x00000000..0x3fffffff` with only the framebuffer reserved at
  `0x10000000..0x103fffff`) and (b) **not** silently overlap the heartbeat's
  already-used `0x07000000..0x07004fff` scratch range, which sits inside
  that same normal DRAM window and is therefore ordinary allocatable RAM to
  Linux today, not a hardware-reserved region. A `reserved-memory`/`no-map`
  node is mandatory before any Linux-coexistence step reuses that or any
  other address, exactly as the heartbeat change's own task 4.1 already
  required.
- **Resource table, virtio, rpmsg.** The generic remoteproc/rpmsg machinery
  is already in this pinned kernel and needs no K230-specific work:
  `drivers/remoteproc/remoteproc_core.c`, `remoteproc_virtio.c`,
  `drivers/rpmsg/virtio_rpmsg_bus.c`, documented in-tree at
  `Documentation/staging/remoteproc.rst` and `Documentation/staging/rpmsg.rst`
  ("the remoteproc framework allows different platforms/architectures to
  control (power on, load firmware, power off) those remote processors...
  this framework also adds rpmsg virtio devices"). The resource-table
  convention itself (a `.resource_table` ELF section describing vdevs,
  vrings, and carveouts, parsed by `remoteproc_elf_loader.c`) is the OpenAMP
  project's own format
  (https://github.com/OpenAMP/open-amp/blob/main/lib/include/openamp/remoteproc.h;
  https://openamp.readthedocs.io/en/v2025.10.0/lopper/specification/source/chapter5-remoteproc.html) —
  a firmware image only needs to embed that table once it actually speaks
  virtio/rpmsg, which step zero (Decision 5) deliberately defers.
- **Mailbox: absent, and its register layout is unread.** No `mailbox`
  driver or DT node exists for K230 anywhere in the pinned kernel (verified
  above). `docs/research/second-core-feasibility.md`'s TRM review only
  reports that "the interrupt table lists distinct mailbox sources in both
  CPU0-to-CPU1 and CPU1-to-CPU0 directions" (TRM section 2.4) — it does not
  record a register map, and none has been transcribed into this project's
  evidence. Writing a real K230 mailbox driver is therefore blocked on a
  TRM-reading task this change does not do. `th1520-mailbox.c` in this same
  tree is the nearest architectural cousin (status/clear/mask registers, a
  per-channel data-register window, a "generate remote IRQ" register) but is
  a different IP block on a different SoC and must not be assumed to match
  K230's layout.

Because of that gap, this design avoids a hardware-mailbox dependency for
the steps it actually proposes (Decisions 5-6): Linux's own mailbox
framework (`drivers/mailbox/mailbox.c`) already supports a polling
completion mode (`txdone_poll`) for controllers with no interrupt-driven
acknowledgement, so a "mailbox" backed purely by a status word in the same
non-cacheable shared region can drive the standard `virtio_rpmsg_bus`/
`remoteproc_virtio` stack unmodified, without touching the real K230
mailbox IP until its registers are separately read and a task exists to
write a real driver for it.

### 2. Firmware side: bare-metal first, not Zephyr, FreeRTOS, or RT-Smart

| Option | K230/C908 support today | Nix cross build complexity | Verdict |
| --- | --- | --- | --- |
| **Bare-metal (extend the heartbeat)** | Physically proved: `tools/small-core-heartbeat.{S,ld}` already runs on CPU0 via `boot_baremetal 0` (`docs/evidence/second-core/cpu0-identity-physical-trial.md`). | Smallest possible: `tools/test-small-core-heartbeat.sh` invokes host `clang`/`lld` directly (`--target=riscv64-unknown-elf`), no nixpkgs cross toolchain package, no OS tree to build. | **Recommended first step.** |
| **Zephyr** | No K230 or C908 board/SoC support. A 2025-era PR adds T-Head **C906** support for Sophgo's Milk-V Duo (CV1800B/SG2002, PR #69594) — different vendor, different core, and even that support needed a Zephyr timer-driver change (`mtime-is-32bits`) for a T-Head core lacking a standard 64-bit `MTIME`. No public evidence of C908 or K230 work. | Would require writing a whole new SoC+board port (Kconfig, devicetree bindings, CLINT/PLIC quirks, boot code) from nothing, then getting Zephyr's own build system working inside this project's Nix cross environment — a multi-week, uncertain undertaking. | Not recommended as a first step; revisit only if a later workload needs Zephyr's driver/RTOS ecosystem specifically. |
| **FreeRTOS** | Generic RV32I/RV64I + CLINT port exists upstream (`FreeRTOS/Source/Portable/.../RISC-V`, `configCLINT_BASE_ADDRESS`), but no K230 BSP. | Buildable with the same lightweight `clang`/`lld` approach as the heartbeat (FreeRTOS's RISC-V port is a handful of C/asm files, not a full OS tree), but still needs a hand-written CLINT tick-timer and trap-vector port validated against K230's actual CLINT wiring (`k230.dtsi:255-259`, wired only to `cpu0_intc` today). | Medium effort; worth it only once a workload needs preemptive multitasking on CPU0, which none of the current candidates (Decision 5/6) do. |
| **RT-Smart (vendor's own choice)** | Fully supported — it is the vendor's shipped big-core RTOS — but this project carries no RT-Smart payload today, and the vendor's own AMP driver (`k230-amp.c`) demonstrates only a boot-loader/cache-flush contract, not an rpmsg/mailbox IPC contract to reuse. | Largest lift: a second, independent OS source tree with its own toolchain assumptions, no existing Nix packaging in this repo, and no build precedent to extend (unlike the heartbeat's plain `clang`/`lld` invocation). | Not recommended as a first step; would only be reconsidered if a workload specifically needed RT-Smart's own driver ecosystem (e.g. its NPU/DSP support), which none of the current candidates do. |

**Recommendation:** extend `tools/small-core-heartbeat.{S,ld}` into the
step-zero firmware (Decision 5) directly. It is the only option with
existing physical proof on this board, and its build has effectively zero
Nix cross complexity because it never enters the nixpkgs riscv64 cross
toolchain at all.

### 3. Cache maintenance for shared buffers without hardware coherency

No document in hand states a CPU0/CPU1 cache-coherency contract (Decision 1
above, and `docs/research/second-core-feasibility.md`, "What the vendor
register map proves—and does not"). Until one exists, every shared buffer
between CPU0 and Linux SHALL follow the same discipline this project's own
heartbeat probe already uses and the vendor's own AMP driver independently
converges on:

1. **The shared region is `no-map` and mapped non-cacheable on the Linux
   side** — matching the existing `reserved-memory`/`no-map` precedent
   (`nix/dts/k230-tdisplay.dts:47-57`) and this SoC's existing, broader
   `dma-noncoherent;` property at the `soc` node
   (`k230.dtsi:207`, also present per-controller at `:346` and `:360`) —
   i.e. Linux already treats this SoC's bus masters as non-coherent for DMA
   purposes; extending that same non-coherent assumption to the CPU0 shared
   ring is a familiar contract on this board, not a new one. `virtio_ring.c`
   already conditions its barriers (`dma_wmb()`/`dma_rmb()` vs. plain
   `wmb()`/`rmb()`) on the transport's declared coherence, so a
   `dma-noncoherent` virtio transport is a supported, not exotic, case.
2. **CPU0 flushes after every write it wants Linux to see**, using the
   pinned `l2cache.ciall` encoding U-Boot's `cache.c:158-161` already
   defines and the heartbeat firmware already issues
   (`tools/small-core-heartbeat.S:25-28`, `.word 0x0170000b`), plus a
   `fence rw, rw` before it. This is CPU0's private-L2 flush; it says
   nothing about Linux's own cache state and does not replace step 1.
3. **Neither side infers freshness from a second read of a line it might
   already hold cached.** The heartbeat runbook's interim rule — "read each
   output page only once ... since the two physical cores do not have a
   proven coherent-cache contract" — generalizes to any descriptor or ring
   index: a consumer must map its view of shared state non-cacheably (step
   1) rather than rely on eventually re-reading a fresh value through its
   own cache.
4. **Memory types stay pinned per region.** The firmware carveout, the ring
   /descriptor area, and any future data buffers are each a distinct
   `reserved-memory` child with an explicit `no-map`; nothing shares a page
   between a cacheable Linux allocation and CPU0-visible state.

### 4. Recovery and safety

Every task that writes CPU0's reset, vector, or reset-controller register
needs the board operator's explicit authorization, per AGENTS.md, and the
same rehearsed recovery path both parent changes already required and left
incomplete: `the-system-runs-on-both-cores` task 2.1/2.2's external
SD-card-reader restore rehearsal, described in
`docs/closeout/second-core-plan.md`'s step 1. This design does not restate
that procedure; it inherits it as a hard prerequisite (Task 2 below) and
adds nothing new to the registers already in scope for it — an AMP release
writes the exact same `CPU0_RST_CTL`/vector registers a Linux SMP release
would have.

**Resetting a crashed coprocessor without rebooting Linux.** Because CPU0's
reset-controller line (`K230_RESET_CPU0_REG_OFFSET`, offset `0x4`) is
independent of CPU1's (offset `0xc`) in the same RMU block (TRM section
2.1.4), a Linux-side `reset_control_assert()`/`deassert()` cycle on the CPU0
line alone should not touch CPU1/Linux execution. This is a reasonable
inference from the register map, **not yet a board-proved claim**: the TRM's
CPU power-flow text also requires "a completed NOC low-power handshake
before a power transition" (section 2.3.3), which this design has not
tested for CPU0 alone. A bounded board task (Task 5.3 below) proves or
disproves "CPU0 can be reset and restarted while Linux keeps running and
stays responsive" before this design's recovery story is trusted beyond a
successful full-board reset.

**A hardware watchdog already exists in QEMU's model but has no Linux driver
here.** QEMU's `k230` machine documents two K230 watchdog-timer instances
among its modeled devices, and the pinned kernel has no K230 watchdog driver
(`drivers/watchdog/` search, Decision 1). If K230 silicon has a standalone
WDT peripheral independent of CPU0/CPU1, a plain `watchdog` driver detecting
"Linux stopped petting the dog" would be a simpler, lower-risk answer to
"has Linux hung" than routing that question through CPU0 at all — that is a
different, smaller capability with no coprocessor involved, and this
proposal does not claim CPU0 is the only or best way to detect a hang. What
CPU0 can add beyond a hardware WDT is choosing *how* to react (see Decision
6) rather than only forcing a blind full reset; that is the value this
change actually proposes.

### 5. First proof: a trivial echo/ping over a polling ring — step zero

Before any peripheral or workload decision, this design's first
Linux-coexistence firmware slice reuses the heartbeat's proven layout —
scalar RV64, no runtime, one bounded loop — extended with a small
request/response ring in the same style of dedicated scratch pages the
heartbeat already uses, instead of a monotonic counter:

- Linux writes a request word into a producer slot, flushes (its own cache
  maintenance, whatever the chosen non-cacheable mapping requires), and
  polls a response slot.
- CPU0 polls the request slot, echoes it (or increments it) into the
  response slot, and issues `l2cache.ciall` before returning to the poll
  loop — the same discipline as Decision 3.
- No K230 mailbox hardware is touched. If a `remoteproc`/`virtio_rpmsg_bus`
  skeleton is layered on top later (Decision 1's "resource table" note),
  this ring is a plausible seed for its vring backing store, but step zero
  itself does not commit to the full virtio/rpmsg stack — it only proves the
  memory/cache contract and the release/observe/recover loop end to end with
  two-way traffic instead of the heartbeat's one-way counter.

This is deliberately the smallest possible extension of already-proved work,
matching this project's evidence-first discipline: prove the mechanism
before committing to a peripheral or a driver framework.

### 6. First useful workload: a CPU0 liveness watchdog for Linux

Evaluated against value, independence, and I/O ownership conflict with
Linux (`docs/research/board-capability-inventory.md`):

| Candidate | Value | Independence | I/O ownership conflict |
| --- | --- | --- | --- |
| Keyboard-base scanning (TCA8418/XL9555) | High, but only once the accessory exists — **the user's base has no connector hardware yet**, so nothing can be tested on real hardware regardless of SMP/AMP. | Needs an I2C bus CPU0 does not currently have any wiring or driver for. | Shares the I2C4-alt bus with the charger/fuel-gauge/AHT20 parts (`board-capability-inventory.md` row 129's noted "shared UART3 conflict"); contested even once hardware exists. |
| LoRa timing (SX1262/LR2021 over SPI0) | Medium — a real headline feature, but niche. | Needs SPI0, which the DT currently disables entirely (`status = "disabled"` on all three SPI controllers). | This project's own roadmap already plans to give **Linux** `spidev` ownership of SPI0 for RadioLib (`board-capability-inventory.md`, "Effort M", already `CONFIG_SPI_SPIDEV=y`/`CONFIG_SPI_DW_MMIO=y` in the pinned defconfig) — handing the same bus to CPU0 would preempt a Linux feature already in motion, not a vacant one. |
| Battery/charger monitoring (BQ25896/BQ27220) | Very high — "the single most-requested handheld capability" per the same inventory — but for exactly that reason Linux is the more likely long-term owner: the charger driver (`bq25890_charger.c`) already covers the exact chip ID in the pinned kernel, and only the fuel-gauge driver is missing. | Same I2C4-alt bus as the keyboard-base parts; register writes there are explicitly flagged risky in existing research. | Would contest Linux's own probable near-term ownership of the same bus and chips. |
| **Hardware watchdog / heartbeat monitor** | Real safety value: detect a hung Linux hart and preserve a fault record across a reset, independent of any accessory. | **Touches no shared bus and no peripheral Linux wants** — only the RMU/vector registers already in scope for this change and a private reserved-memory region. Directly extends already-proved, already-evidenced work. | None. |

**Recommendation: the watchdog/heartbeat monitor**, built directly on step
zero's ring. CPU0 watches a liveness counter Linux increments on a timer; if
it stops advancing within a budget, CPU0 writes a fault record (last-seen
counter value, a timestamp source, whatever minimal state fits) into a
second reserved page and **keeps running**, taking no reset action of its
own. Reading that record after a manual recovery is the acceptance
criterion for this change. **Explicitly out of scope for this change:**
CPU0 asserting CPU1's or the whole board's reset automatically. That is a
materially larger hazard — a false-positive reset of a live Linux system —
and needs its own proposal, its own authorization, and its own repeated
board evidence once detection alone is proved, matching this project's
existing discipline of not promising a capability before its narrower
prerequisite is proved (`the-system-enables-proven-c908-extensions`'s
acceptance-before-performance rule).

## Evidence classes per step

| Step | Host build | QEMU | Board trace |
| --- | --- | --- | --- |
| 1. Recovery rehearsal | — | — | Required: external-reader restore proof (inherited, still open) |
| 2. Step-zero echo/ping firmware | Required: disassembly/footprint/no-V check, extending `tools/test-small-core-heartbeat.sh`'s method | Possibly available: QEMU's `k230` machine models exactly one core described as "the little core (c908)" — the same role as CPU0 — which may make a standalone, Linux-free boot of this firmware a real QEMU proof; **unverified**, a task must confirm whether this project's QEMU invocation can target that machine without Linux before this is relied on | Required: `boot_baremetal 0` release and readback, after the recovery rehearsal |
| 3. Reserved memory + read-only driver skeleton | Required: `nix build .#deviceTree`; kernel module builds | Not applicable (no execution claim) | Not applicable |
| 4. Linux-driven CPU0 start/stop | Required: driver builds against the pinned kernel | Not applicable (QEMU's k230 machine does not model RMU/reset-control registers or per-core release) | Required: release, echo round-trip, and stop-without-reboot, after the recovery rehearsal |
| 5. Watchdog detection | Required: host fixture for the fault-record format | Not applicable | Required: a deliberately frozen liveness counter is detected and recorded, then read back after a manual recovery |

A QEMU result never substitutes for a board trace on any step that claims
CPU0 actually executed, matching `.skills/k230-spec-change/SKILL.md`'s
existing rule that QEMU's `k230` machine "models none" of this board's real
peripherals; the possible exception noted above is a standalone CPU0 image
with no peripheral claim at all, and only once confirmed.

## Risks / Trade-offs

- **A new remoteproc driver duplicates the reset-controller's own MMIO
  mapping** → use `devm_reset_control_get_exclusive()` against the existing
  `canaan,k230-sysctl-reset` binding instead of a second raw `ioremap` of
  the same physical registers (Decision 1).
- **A mailbox driver is written against a guessed K230 register layout** →
  this design defers any real mailbox driver until TRM section 2.4 is
  transcribed into project evidence, and uses a poll-mode software mailbox
  in the interim (Decision 1, Decision 5).
- **CPU0 reset-controller independence from CPU1 is assumed, not proved** →
  Task 5.3 tests it directly before any recovery claim is trusted beyond a
  full board reset (Decision 4).
- **A watchdog design creeps into auto-reset before detection is proved** →
  explicitly out of scope for this change (Decision 6); any auto-reset
  capability needs its own proposal.
- **Scope creep into LoRa/battery/keyboard ownership** → explicitly
  deferred (proposal.md non-goals); Decision 6's table exists precisely to
  make that deferral evidence-based rather than arbitrary.

## Migration Plan

Land this proposal, then work strictly in the staged order in `tasks.md`:
source/register grounding first (no board), then the inherited recovery
rehearsal (board, read/verify only), then step-zero firmware (host, then
board), then the reserved-memory and driver skeleton (host/cross-build
only), then the Linux-driven start/stop (board, first register-writing
Linux code), then the watchdog (board). Each stage's board task is blocked
on the previous stage's evidence being committed, exactly as both parent
changes already practiced. No normal image or boot behavior changes until a
later, separate change proposes making any of this default-on.

## MODIFIED Requirements

### Requirement: Bring-up is gated by firmware, interrupt, and coherency evidence

*Grounding: `docs/evidence/second-core/README.md` records the decision
against each prerequisite; `docs/research/second-core-feasibility.md` traces
the pinned firmware/kernel and vendor AMP sources. `design.md` in
`the-small-core-runs-as-a-coprocessor` traces the pinned kernel's absence of
a K230 remoteproc/mailbox driver, the existing `canaan,k230-sysctl-reset`
reset-controller binding, and the TRM's undocumented mailbox register
layout.*

Before a later change may release a second core for **Linux SMP**, it SHALL
have source- or board-grounded evidence for the second hart ID and
reset/vector protocol, OpenSBI domain/HSM behavior, local timer and
IPI/PLIC routes, CPU ISA and cache description, and a CPU-to-CPU
shared-memory coherency contract. This SMP path remains blocked: both
physical cores have been directly measured reading `CSR.MHARTID = 0`
(`docs/evidence/second-core/cpu0-identity-physical-trial.md`), which breaks
OpenSBI's hart table, warm-entry scratch/stack selection, and HSM/IPI
targeting before interrupt routing or coherency are even reached, and no
document in hand supplies a second per-core identity signal to fix it.

A separate **AMP (coprocessor) path** SHALL instead:

- Use a Linux-side driver that requests CPU0's reset-controller line through
  the existing `canaan,k230-sysctl-reset` binding
  (`drivers/reset/reset-k230.c`, `include/dt-bindings/reset/canaan-k230-reset.h`
  `K230_RESET_CPU0_*`) rather than a redundant raw MMIO mapping of the same
  physical registers, and perform the CPU0 vector-register write at the
  address the pinned `boot_baremetal` sequence already uses
  (`arch/riscv/cpu/k230/cpu.c:125-160`, `sysctl_boot@91102000` offset
  `0x100`).
- Reserve its firmware image and any shared ring in a `no-map`
  `reserved-memory` device-tree node, following the existing splash
  framebuffer precedent (`nix/dts/k230-tdisplay.dts:47-57`), and map that
  region non-cacheably on the Linux side rather than sharing a cacheable
  page between CPU0 and Linux.
- Not depend on a K230 hardware mailbox driver until its register layout
  (TRM section 2.4) has been read into this project's evidence; a
  poll-mode software doorbell in the same non-cacheable region MAY stand in
  for it.
- Not claim ownership of any peripheral bus (I2C, SPI, or otherwise) already
  planned or likely for Linux ownership without a separate, explicit
  ownership decision recorded against that peripheral's own capability.
- Not give CPU0 the ability to reset CPU1, Linux, or the board
  automatically without that ability being proposed, authorized, and
  board-proved as its own, separate capability.

#### Scenario: A prerequisite remains undocumented

- **WHEN** the reset/vector protocol, interrupt route, or coherency contract
  has not been established
- **THEN** the project retains the single-hart image and records the
  missing evidence and safe next action without attempting a core release

#### Scenario: An AMP change proposes reusing an SMP prerequisite as satisfied

- **WHEN** a change cites CPU0 firmware execution, a heartbeat, or any other
  AMP evidence as proof that Linux SMP's hart-identity, interrupt-routing,
  or coherency gates are met
- **THEN** that citation is rejected; AMP execution proves independent
  physical execution under stage 1 or Linux control, not a Linux-addressable
  SBI hart

## ADDED Requirements

### Requirement: The coprocessor stage follows a staged, evidence-gated AMP bring-up plan

*Grounding: `docs/closeout/second-core-plan.md`'s recommendation and "Next 3
concrete steps"; `the-small-core-runs-as-a-coprocessor/design.md`'s staged
decisions and evidence-class table; `tools/small-core-heartbeat.{S,ld}` and
`docs/evidence/second-core/heartbeat-*.md` as the already-proved foundation.
The external-reader recovery rehearsal this stage list originally named is
waived by the operator's 2026-09-28 decision (see the requirement below).*

The project SHALL stage CPU0 coprocessor bring-up as: source/register
grounding, confirming a current fallback recovery route, a step-zero
polling-ring firmware proof, a reserved-memory carveout with a read-only
driver skeleton, Linux-driven runtime start/stop, and only then a first
workload. It SHALL NOT skip a stage's committed evidence to reach a later
one, and it SHALL NOT write a CPU0 reset, vector, or reset-controller
register without the operator's explicit authorization at the time, per the
requirement below.

#### Scenario: A stage is proposed out of order

- **WHEN** a change proposes a Linux-driven CPU0 release, a real workload,
  or a mailbox hardware driver before the preceding stage's board or source
  evidence is committed
- **THEN** the change is not authorized to proceed, and the missing stage's
  evidence is named as the blocker

### Requirement: Shared CPU0/Linux memory has an explicit non-coherent cache-maintenance contract

*Grounding: no TRM or vendor SDK document states a CPU0/CPU1 cache-coherency
contract; the vendor `k230-amp.c` driver and this project's own
`tools/small-core-heartbeat.S:25-28` both flush by hand rather than rely on
implicit coherency; the SoC's `dma-noncoherent;` property already applies at
the DT `soc` node (`k230.dtsi:207`).*

Any memory region shared between CPU0 firmware and Linux SHALL be a
`no-map` `reserved-memory` region mapped non-cacheably on the Linux side.
CPU0 firmware SHALL issue the pinned L2 cache-maintenance instruction after
any write it intends Linux to observe, and neither side SHALL infer
freshness from a second read of a location it may already hold cached.

#### Scenario: A shared buffer is added without a cache-maintenance rule

- **WHEN** a change adds a new CPU0/Linux shared buffer without specifying
  its non-cacheable mapping and its write-side flush instruction
- **THEN** the change is not authorized to proceed until both are specified
  and cited against pinned source

### Requirement: A CPU0 register write requires explicit authorization and a proven fallback recovery route

<!-- Narrowed 2026-09-28: the operator waived the external-reader recovery
rehearsal this requirement originally depended on. The user: "we can easily
fix the sd card damn. don't worry about recovery we've literally done that
fine already before. i don't want to do a heartbeat test on a spare card."
See `docs/closeout/second-core-plan.md`'s 2026-09-28 addendum. -->

*Grounding: pinned U-Boot `arch/riscv/cpu/k230/cpu.c:125-160` defines
CPU0's reset/vector writes; `nix/stage1.nix:176-180` puts SPL at raw
SD-card offsets. `docs/evidence/card-shell/bottom-band-flicker/
kernel-patch-boot-panic.md` records a proven U-Boot one-shot recovery from
a bad boot, and `docs/uboot-ums.md` documents the `ums`/flash reimaging
route; both remain reachable without an external card reader or a
spare/disposable card.*

Before any change writes a CPU0 reset, power, reset-vector, or
reset-controller register, the board operator SHALL hold explicit user
authorization for that specific session. No task SHALL require a separate
spare or disposable card; every board step in this bring-up SHALL run on
the normal card. If a release, stop, or restart write fails or hangs the
board, the operator SHALL recover using the already-proven U-Boot one-shot
boot from `boot-prev` or `ums`/flash reimaging, and SHALL record the
outcome of a failed or hung release separately from a successful one.

#### Scenario: A register write is attempted without authorization

- **WHEN** the operator has not obtained the user's explicit authorization
  for the current board session
- **THEN** the reset/power/vector register write does not proceed

#### Scenario: A CPU0 release or stop fails or hangs the board

- **WHEN** a release, stop, or restart write does not produce the expected
  result
- **THEN** the operator restores the board using the U-Boot one-shot or
  `ums`/flash reimaging route, on the normal card, and records the outcome
  separately from the attempt's own result

### Requirement: AMP execution does not imply Linux SMP or unreviewed peripheral ownership

*Grounding: the pinned stage-1 release path starts a separate physical core
under explicit software control, not a Linux-addressable hart; the vendor
`k230-amp.c` path requires a separate payload and cache-managed memory, not
Linux scheduling.
`docs/research/board-capability-inventory.md` records overlapping or
Linux-planned ownership for the LoRa SPI bus and the charger/fuel-gauge I2C
bus, and that the keyboard-base accessory has no connector hardware on the
board yet.*

The project SHALL identify any CPU0 execution as independent physical
execution under stage 1 or Linux control. It SHALL NOT claim a second Linux
CPU, cache-coherent shared memory beyond the explicit contract above,
working general interrupts, or safe general scheduling from that
observation. It SHALL NOT wire a peripheral bus to CPU0 that is already
planned or contested for Linux ownership without a separate, explicit
ownership decision recorded against that peripheral's own capability, and
it SHALL NOT claim readiness for an accessory that has no hardware present
on the board.

#### Scenario: A workload is proposed for a contested or absent peripheral

- **WHEN** a change proposes giving CPU0 a peripheral bus Linux already
  plans to own, or an accessory with no connector hardware present
- **THEN** the change records that conflict or absence explicitly and does
  not proceed on that peripheral until the ownership question is separately
  decided or the hardware exists

#### Scenario: CPU0 detects a Linux hang

- **WHEN** CPU0 firmware detects that a Linux liveness counter has stopped
  advancing within its documented budget
- **THEN** it records a fault report and continues running; it does not
  assert any reset register itself unless a separate, later capability
  explicitly authorizes and proves that action

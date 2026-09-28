## ADDED Requirements

### Requirement: A physical small-core execution proof is recoverable and bounded

*Grounding: the pinned `k230_linux_sdk` U-Boot overlay at revision
`1104236db4d1e47873bd68924f912747b820228c`,
`arch/riscv/cpu/k230/cpu.c:125-160`, provides `boot_baremetal 0` and writes
physical CPU0's reset vector at `0x91102100`; `docs/research/second-core-feasibility.md`
records its limits. The output memory and coexistence behavior remain
`<!-- UNVERIFIED -->` until board evidence exists.*

<!-- Narrowed 2026-09-28: the disposable-rollback-card requirement below is
waived by the operator's decision the same day ("we can easily fix the sd
card damn. don't worry about recovery we've literally done that fine
already before. i don't want to do a heartbeat test on a spare card."); see
`docs/closeout/second-core-plan.md`'s addendum. The normal card plus a
proven fallback recovery route (U-Boot one-shot/`ums`/reimaging) replaces
it below. -->

The project SHALL provide a scalar test payload and a readback procedure that
allow an operator to tell from the console whether physical CPU0 executed
while physical CPU1 remained at the stage-1 prompt. Before the release, the
payload address and output location SHALL be checked against stage-1 memory
use, and a proven fallback recovery route (the U-Boot one-shot boot or
`ums`/flash reimaging) SHALL be available on the normal card; no separate
disposable or spare card SHALL be required. The experiment SHALL record
the release command, repeated observations, and recovery outcome as physical
evidence. A host build or QEMU run SHALL NOT be counted as physical proof.

#### Scenario: Small core heartbeat is observed

- **WHEN** the operator runs the bounded release on the normal card and
  reads the agreed output location repeatedly while stage 1 remains responsive
- **THEN** the console shows a changing value produced by the small core,
  identifies the payload and card used, and records a return to normal boot

#### Scenario: Release does not produce the expected heartbeat

- **WHEN** the release hangs the board, the output location does not change,
  or the large-core prompt stops responding
- **THEN** the experiment is recorded as failed, the fallback recovery route
  (U-Boot one-shot or `ums`/flash reimaging) is used, and no Linux-coexistence
  claim is made

### Requirement: Physical CPU0 keeps a heartbeat while physical CPU1 runs Linux

*Grounding: the pinned stage-1 source at
`board/canaan/common/k230_img.c:276-285` releases physical CPU1 into U-Boot
and parks physical CPU0 in an endless `wfi`. The continued heartbeat and
Linux readback are `<!-- UNVERIFIED -->` until the board transcript exists.*

Only after the stage-1 prompt heartbeat is physically proved, an experimental
stage-1 build SHALL let physical CPU0 update a reserved heartbeat location
while physical CPU1 continues into the normal Linux boot. The system SHALL
exclude that location from Linux allocation and expose a read-only
observation method with an explicit cache-maintenance or uncached-memory
contract. The operator SHALL record repeated changing values alongside a
responsive Linux console and shell, then restore the known-good stage 1.

#### Scenario: Linux and the small-core heartbeat coexist

- **WHEN** the experimental image boots Linux on the normal card and the
  operator reads the reserved heartbeat repeatedly
- **THEN** the value changes across at least three reads, Linux remains
  responsive, and the transcript records the exact image, addresses, and
  restored normal boot

#### Scenario: Linux does not coexist with the small-core heartbeat

- **WHEN** boot hangs, the heartbeat is static, or Linux/UI function fails
- **THEN** the experiment is reported as failed and the fallback recovery
  route (U-Boot one-shot or `ums`/flash reimaging) is used without claiming
  useful offload or Linux SMP

### Requirement: An AMP heartbeat does not imply shared Linux scheduling

*Grounding: the pinned U-Boot release path starts a separate physical core;
the vendor `k230-amp.c` path requires a separate payload and cache-managed
memory. The [K230 Linux DTS review](https://lkml.rescloud.iu.edu/2403.3/00159.html)
reports physical CPU1 `mhartid` 0; a further first-hand developer report says
both physical cores report 0, pending confirmation on this board.*

The project SHALL identify the heartbeat as independent physical CPU0
execution under stage 1. It SHALL NOT claim a second Linux CPU, cache-coherent
shared memory, working interrupts, timer delivery, video offload, or safe
general scheduling from that observation. Those claims require separate
physical tests and an ownership/cache-maintenance protocol.

#### Scenario: Heartbeat passes but Linux still reports one CPU

- **WHEN** the operator observes the heartbeat and later boots the normal
  system with only one Linux CPU present
- **THEN** the result is reported as a physical AMP execution proof with
  Linux SMP still unverified

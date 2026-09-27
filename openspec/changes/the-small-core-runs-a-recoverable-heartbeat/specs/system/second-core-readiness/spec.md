## ADDED Requirements

### Requirement: A physical small-core execution proof is recoverable and bounded

*Grounding: the pinned `k230_linux_sdk` U-Boot overlay at revision
`1104236db4d1e47873bd68924f912747b820228c`,
`arch/riscv/cpu/k230/cpu.c:125-160`, provides `boot_baremetal 0` and writes
physical CPU0's reset vector at `0x91102100`; `docs/research/second-core-feasibility.md`
records its limits. The output memory and coexistence behavior remain
`<!-- UNVERIFIED -->` until board evidence exists.*

The project SHALL provide a scalar test payload and a readback procedure that
allow an operator to tell from the console whether physical CPU0 executed
while physical CPU1 remained at the stage-1 prompt. Before the release, the
payload address and output location SHALL be checked against stage-1 memory
use, the normal card SHALL be preserved, and a disposable rollback card plus
a rehearsed recovery route SHALL be available. The experiment SHALL record
the release command, repeated observations, and recovery outcome as physical
evidence. A host build or QEMU run SHALL NOT be counted as physical proof.

#### Scenario: Small core heartbeat is observed

- **WHEN** the operator runs the bounded release on a disposable card and
  reads the agreed output location repeatedly while stage 1 remains responsive
- **THEN** the console shows a changing value produced by the small core,
  identifies the payload and card used, and records a return to normal boot

#### Scenario: Release does not produce the expected heartbeat

- **WHEN** the release hangs the board, the output location does not change,
  or the large-core prompt stops responding
- **THEN** the experiment is recorded as failed, the rehearsed recovery route
  is used, and no Linux-coexistence claim is made

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

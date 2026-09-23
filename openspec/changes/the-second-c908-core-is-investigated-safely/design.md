## Context

The current board boots a source-built Canaan-overlay OpenSBI 1.4 and a Linux
6.6.36 kernel with `CONFIG_SMP=y`, yet stage 1, the live device tree, and Linux
all enumerate exactly hart 0. See proposal.md and the existing
`docs/research/second-core-feasibility.md` for prior evidence. The shell, USB
recovery, display, VPU, and current video tests must remain available.

Vendor SDK source provides a distinct AMP mechanism rather than a normal Linux
SMP configuration: `k230-amp.c` maps a reserved RT-Smart region, explicitly
writes it back from cache, programs `CPU1_HART_RSTVEC`, then toggles `CPU1_RST_CTL`.
That source establishes that releasing the other core has real ownership and
cache consequences. It is not carried by this image and is excluded here.

## Goals / Non-Goals

**Goals:**

- Produce a repeatable factual handoff snapshot while the board remains booted.
- Record the decision boundary for Linux SMP versus vendor-style AMP.
- Make a future experimental image dependent on explicit evidence rather than a
  plausible DTS edit.

**Non-Goals:**

- Starting, stopping, resetting, powering, or sending mailbox traffic to a
  secondary core.
- Adding CPU nodes, reserving AMP memory, modifying stage 1, or benchmark work.
- Treating logical hart 0 as physical CPU0 solely because it is numbered zero.

## Decisions

### Use a passive snapshot rather than an HSM probe

The helper reads `/sys/devices/system/cpu`, the live `/proc/device-tree` CPU,
PLIC and timer nodes, `/proc/cpuinfo`, and existing `dmesg` messages. It does
not issue SBI calls: even `HART_GET_STATUS` would add a new runtime interaction
whose behavior for an undocumented hart is not needed to establish that the
current handoff is one-hart. It also avoids MMIO reads because the known RMU
register includes write-one-to-clear bits and board access is owned by the
coordinator.

### Separate OpenSBI extension discovery from startability

Linux's `cpu_ops_sbi.c` calls `SBI_EXT_HSM_HART_START` only after a second DT
CPU has supplied a hart ID. Generic OpenSBI derives platform hart count from
`/cpus`; the current single CPU node therefore explains the one-hart banner.
The observed HSM extension means the ecall handler exists, not that an
undocumented CPU1 is assigned to the domain or has a release vector.

### Treat Linux SMP and AMP as different future changes

Linux SMP requires shared page tables, spinlocks, TLB/IPI operation and matching
CPU topology. Vendor AMP instead supplies a firmware image, reserved memory,
cache maintenance, reset vector, and interprocessor protocol. Combining them
would hide incompatible peripheral and power-domain ownership decisions.

## Risks / Trade-offs

- [Passive state cannot prove a dormant physical core] → Record the exact
  missing firmware and TRM evidence, then require a separately authorized,
  rollback-image experiment.
- [SMP experiment could strand the handheld] → Preserve known-good UMS recovery
  and run it only after all gates are met on a disposable image/card.
- [Vendor AMP source may assume its own Linux/RT-Smart layout] → Do not copy its
  addresses or reset writes into NixOS; use it only to identify required
  contracts.
- [The data source may contain terminal control bytes] → The helper formats
  binary DT properties as hex and filters the requested dmesg lines.

## Migration Plan

No deployment changes occur. The coordinator may run the read-only helper and
commit a sanitized transcript. A later implementation proposal must cite that
transcript plus vendor source for every gate, build a rollback-capable image,
and stop at the first failed secondary-hart condition.

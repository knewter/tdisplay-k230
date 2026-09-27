## Context

See proposal.md and `docs/research/second-core-feasibility.md`. The pinned
U-Boot overlay runs the normal Linux boot on physical CPU1 and exposes
`boot_baremetal 0`, which sets the physical CPU0 vector at `0x91102100` and
uses `CPU0_RST_CTL` at `0x91101004`. Reports that both cores expose hart ID 0
make a guessed second Linux CPU node especially unsafe. The existing
`the-system-runs-on-both-cores` proposal remains the separate Linux SMP path
and retains its gates.

## Goals / Non-Goals

**Goals:** produce a tiny independent CPU0 execution proof, preserving the
large-core U-Boot prompt and a recoverable normal boot. Make the exact payload
bytes, load/output locations, command, timestamps, and observations reviewable.

**Non-Goals:** Linux SMP, booting RT-Smart, Linux coexistence during this first
probe, inter-core interrupts, shared coherent memory, useful task offload, or
video improvement.

## Decisions

1. **Stage 1 controls release.** Use the existing pinned U-Boot
   `boot_baremetal 0` command. It already contains the physical CPU0 vector
   and reset sequence, so the probe does not add a kernel `/dev/mem` writer
   or alter the normal boot image. A CPU1-targeted vendor AMP driver is
   rejected: Linux is already on physical CPU1 in this image.
2. **The payload is scalar and standalone.** Build a small RV64I program with
   no vector instruction, runtime dependency, heap, or interrupt assumption.
   It writes a monotonic heartbeat to one output location and stays in a
   bounded loop. Host inspection checks disassembly, entry point and image
   footprint; QEMU may check logic but cannot prove CPU0 release on this board.
3. **Memory must be sourced, not guessed.** Before a linker/load/output
   address is selected, audit the pinned U-Boot memory map, its command
   buffers, the board RAM/SRAM layout, and the normal boot images. Reserve a
   disposable-card-only region which the live U-Boot prompt does not use.
   If no such location is grounded, the physical release remains blocked.
   Readback at the U-Boot prompt must use a known uncached or explicitly
   invalidated view; an unchanged cached read is not proof that CPU0 failed.
4. **Recovery is part of the experiment.** Preserve the known-good card and
   rehearse the current U-Boot one-shot or independent UMS/card-reader path
   in the same board session before `boot_baremetal`. Run the command only
   with the board operator's exclusive console and a disposable rollback
   card. Stop at the first hang or unexpected value; capture the recovery
   transcript separately.

## Risks / Trade-offs

- A wrong load or output address corrupts U-Boot state → require a cited
  memory map and a disposable card before selecting addresses.
- A stale big-core cache hides the heartbeat → define the readback/cache
  protocol before the board run and never infer failure from one static read.
- A CPU0 reset affects shared peripheral state → payload touches only its
  nominated output location; recovery rehearsal precedes release.
- A passing stage-1 heartbeat is mistaken for useful Linux compute → keep
  Linux coexistence and IPC in a later change with separate proof.

## Migration Plan

Land this proposal first. Prepare and inspect the payload on the host. After
the source and recovery gates pass, perform the physical test on a disposable
card and commit the evidence. Return to the normal card/boot and record its
Linux CPU mask. Keep this change open if physical proof is unavailable.

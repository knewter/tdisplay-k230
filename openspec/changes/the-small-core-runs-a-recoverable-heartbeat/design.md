## Context

See proposal.md and `docs/research/second-core-feasibility.md`. The pinned
U-Boot overlay runs the normal Linux boot on physical CPU1 and exposes
`boot_baremetal 0`, which sets the physical CPU0 vector at `0x91102100` and
uses `CPU0_RST_CTL` at `0x91101004`. Reports that both cores expose hart ID 0
make a guessed second Linux CPU node especially unsafe. The existing
`the-system-runs-on-both-cores` proposal remains the separate Linux SMP path
and retains its gates.

## Goals / Non-Goals

**Goals:** first prove a tiny independent CPU0 payload while the large-core
U-Boot prompt remains responsive; then prove a separately gated CPU0
heartbeat continues while CPU1 runs Linux. Make payload bytes, load/output
locations, boot images, timestamps, and observations reviewable.

**Non-Goals:** Linux SMP, booting RT-Smart, inter-core interrupts, coherent
shared memory, useful task offload, or video improvement.

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
5. **Coexistence uses CPU0's existing SPL parking path.** After the first
   physical proof, patch the source-backed `k230_img.c:276-285` WFI loop in
   an experimental SPL to update a reserved heartbeat at low duty cycle
   after releasing physical CPU1. This avoids a second CPU0 reset from a
   running Linux system and preserves CPU1's normal boot path. The
   experimental device tree excludes the exact output region from Linux
   allocation, and a read-only Linux probe uses a documented uncached or
   cache-maintained view. A normal image is not replaced until a disposable
   card boots and rolls back successfully. An alternative Linux `/dev/mem`
   writer to release CPU0 is rejected because the big-core PWR registers
   already return `EPERM`, because it would reset the parked core without
   restoring SPL context, and because it bypasses stage-1 ownership.

## Risks / Trade-offs

- A wrong load or output address corrupts U-Boot state → require a cited
  memory map and a disposable card before selecting addresses.
- A stale big-core cache hides the heartbeat → define the readback/cache
  protocol before the board run and never infer failure from one static read.
- A CPU0 reset affects shared peripheral state → payload touches only its
  nominated output location; recovery rehearsal precedes release.
- A passing stage-1 heartbeat is mistaken for useful Linux compute → keep
  Linux coexistence as a distinct physical gate and keep IPC/offload for a
  later change with separate proof.

## Migration Plan

Land this proposal first. Prepare and inspect the payload on the host. After
the source and recovery gates pass, perform the U-Boot physical test on a
disposable card and commit the evidence. Only then build the experimental SPL
and DT reservation and test Linux coexistence on a rollback card. Return to
the normal card/boot and record its Linux CPU mask. Keep this change open if
either physical proof is unavailable.

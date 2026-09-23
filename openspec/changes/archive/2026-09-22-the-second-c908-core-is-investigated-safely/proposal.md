## Why

The handheld has one Linux CPU online even though the K230 contains two C908
cores. Enabling a guessed second CPU could reset a core, conflict with the
vendor AMP ownership model, or leave Linux without correct timer, interrupt,
and cache-coherency support. The current single-core shell and recovery path
must stay usable while the project reaches an evidence-backed decision.

## What Changes

- Add a system capability for a reproducible, read-only second-core readiness
  audit that records the Linux/OpenSBI handoff without starting, resetting, or
  power-transitioning another hart.
- Ground the decision in the pinned K230 DTS, Linux SMP startup path, Canaan
  OpenSBI overlay and SDK/primary documentation, distinguishing demonstrated
  facts from hypotheses about physical-core identity and coherency.
- Add a passive board collection helper and operator procedure for CPU/DT/SBI
  evidence. It neither accesses MMIO nor changes CPU online state.
- Record the concrete blockers and the gated follow-up needed before a separate
  rollback-image SMP or AMP bring-up change may release a core.

Non-goals: enabling CPU1, adding a `cpu@1` DTS node, changing OpenSBI, loading
RT-Smart, writing reset/power/mailbox registers, or claiming a video speedup.

## Capabilities

### New Capabilities

- `system/second-core-readiness`: The system preserves safe single-hart
  operation and supplies a read-only evidence/decision path before any
  second-core bring-up is attempted.

### Modified Capabilities

- None.

## Impact

- Adds OpenSpec planning artifacts, a source-grounded research record, and a
  host-reviewed shell helper for the coordinator to run on a physical board.
- Does not alter the kernel, device tree, stage 1, image closure, or normal
  shell behavior. Physical evidence collection requires the board coordinator;
  source and helper validation run on the host.

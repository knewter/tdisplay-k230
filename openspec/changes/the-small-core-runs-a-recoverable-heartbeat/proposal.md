## Why

**Suspended 2026-09-26 after user scope correction.** The requested feature
is Linux SMP with both physical cores addressable by one kernel and ordinary
processes schedulable on either. A CPU0 heartbeat or AMP payload does not
meet that request. This proposal and its unchecked tasks remain for history;
do not implement or treat them as a substitute for
`the-system-runs-on-both-cores`.

The handheld currently runs all Linux work on the large physical core, so no
background work can use the small core. Before promising shared Linux
scheduling, an operator needs a recoverable proof that the small core can
execute an independently loaded program while the large core remains under
stage-1 control. The pinned U-Boot source supplies a physical CPU0 reset
vector/release path, while first-hand K230 developer reports say both cores
may report `mhartid` 0; the ordinary two-hart Linux path is therefore unsafe
to assume.

## What Changes

- Prepare a tiny position-independent, scalar CPU0 heartbeat payload and a
  host check of its instructions and memory footprint.
- Ground an exact payload/load/output memory reservation and readback method
  in the pinned stage-1 source before executing the payload.
- On a disposable rollback card, use U-Boot's existing `boot_baremetal 0`
  release with the large core at the U-Boot prompt, then observe a changing
  heartbeat from the small core. Capture the console transcript and restore
  the normal boot path.
- Only after that first physical proof, change the CPU0 SPL parking loop in a
  disposable stage-1 build so CPU0 updates a reserved heartbeat while CPU1
  boots Linux; observe it from the running system and prove normal UI/console
  function and rollback. This is a separate, gated coexistence requirement.
- Treat mailbox IPC, useful background offload, and general peripheral
  ownership as later work. Neither heartbeat is Linux SMP or video
  acceleration.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/second-core-readiness`: add a recoverable, explicitly bounded
  physical CPU0 execution proof and distinguish it from shared Linux SMP.

## Impact

The first stage covers a standalone test payload, host inspection tool, narrow
operator runbook and committed board evidence. The second stage changes SPL
and reserves an observation region in the experimental device tree; it does
not alter the normal installed image until physically proved. Both stages
need the physical board, the exclusive console, a disposable rollback card,
and a rehearsed recovery path. Host preparation does not need the board.

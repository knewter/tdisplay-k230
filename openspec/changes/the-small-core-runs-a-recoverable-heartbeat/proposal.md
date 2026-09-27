## Why

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
- Treat Linux coexistence, mailbox IPC, cache maintenance, peripheral
  ownership, and useful background offload as later evidence gates. This
  heartbeat is an AMP execution proof, not Linux SMP or video acceleration.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/second-core-readiness`: add a recoverable, explicitly bounded
  physical CPU0 execution proof and distinguish it from shared Linux SMP.

## Impact

The proposal covers a standalone test payload, host inspection tool, narrow
operator runbook and committed board evidence. It does not change the normal
NixOS image, device tree, OpenSBI, or U-Boot source. The actual release needs
the physical board, the exclusive console, a disposable rollback card, and a
rehearsed recovery path. Host preparation does not need the board.

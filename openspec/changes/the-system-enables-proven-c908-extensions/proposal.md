## Why

The normal system leaves a physically verified CPU vector path unused, so applications cannot benefit from the board's proven vector execution without selecting a diagnostic image. The user now wants that path enabled by default and wants every other useful, actually supported CPU extension audited rather than assumed from a processor name.

## What Changes

- Make the physically tested vector kernel configuration and runtime-gated Pixman vector implementation part of the normal system, with a complete matching kernel/modules/initrd/userspace build and a scalar fallback.
- Inventory the extensions declared by the pinned board device tree against the running hardware/kernel, stage 1, toolchain and selected libraries. Enable useful extensions at the layer that can safely use them, and record unsupported, unproven, privileged-only or unhelpful cases and reasons.
- Test the new normal image with narrow cross-build and emulated checks, then one-time physical boot, vector context and pixel checks, representative ordinary workloads, and a separately recorded return to the known recovery image. Preserve earlier mixed card-cost results and all existing budgets.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `system/kernel`: the ordinary system uses physically proved vectors and records a bounded ISA inventory with explicit runtime gates and recovery evidence.

## Impact

The Nix kernel, Pixman and image package graph, kernel build patch, extension inventory and board evidence change. The normal kernel and renderer store paths change; stage 1 and device tree are audited but changed only if a specific supported extension demonstrably requires it. Physical-board proof is required for default deployment. QEMU and host checks can proceed independently but cannot establish board support.

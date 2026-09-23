## Why

The shell can spend most of a panel-sized RGB565 scale operation in its own
process even though GPU and Pixman have similar elapsed time. The measured
GPU path reduced this process's CPU time from about 1.7 ms to 0.10 ms per
completed panel-sized operation, which justifies a bounded renderer trial to
learn whether that capacity can help decoding and interaction.

## What Changes

- Add an opt-in, client-side experimental VG-Lite composition path that can be
  selected for a controlled Sway session while Pixman remains the default.
- Import a private DRM dumb-buffer dma-buf into the single VG-Lite context and
  prove RGB565 composition, ownership, cache synchronization, and scanout
  behavior before measuring a session.
- Define rollback, validation, and evidence gates for any future default.

## Capabilities

### New Capabilities
- `runtime/gpu-composition-trial`: An opt-in GPU composition experiment whose
  activation and acceptance remain bounded by board evidence.

### Modified Capabilities

None.

## Impact

Touches a new experimental userspace renderer path, a source-built VG-Lite
library package, the shell launch configuration, tests, and board-only
evidence. It does not change stage 1, device tree, system defaults, video
decoder selection, or DRM ownership policy.

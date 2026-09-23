## Why

The handheld shell still draws through Pixman on its single online Linux CPU. We need to establish whether its GPU can reduce real shell rendering cost while preserving working touch controls and display output.

The validated VG-Lite path used private buffers, not Sway's render pass. Its full-panel elapsed time was comparable to Pixman, so it does not justify a compositor rewrite on wall time alone. The committed validation record limits the result to RGB565, one premultiplied-alpha case, and private dma-buf import; it explicitly leaves live compositor integration unproven ([`docs/evidence/gpu-validation/README.md`](../../../docs/evidence/gpu-validation/README.md)).

The three-round CPU transcript at [`docs/evidence/gpu-validation/cpu-timing-pass.txt`](../../../docs/evidence/gpu-validation/cpu-timing-pass.txt) may justify an experiment because panel-size GPU work used far less process CPU. It cannot establish system-wide offload: process CPU includes user and system time charged to the process; it excludes other processes, separately accounted interrupt work, and whole-device cost.

## What Changes

- Add a source-built **wlroots renderer fork** for an opt-in Sway package. It receives the actual Sway scene render passes; it is not a separate Wayland client or a private-buffer painter.
- Keep Sway's existing wlroots DRM backend as the sole DRM master, swapchain allocator, and scanout committer. The renderer uses only the output buffer handed to `begin_buffer_pass`; it does not open a second DRM client or create a competing scanout path.
- Record each wlroots render pass, run it wholly on VG-Lite only when every operation is supported, otherwise replay the whole pass through paired Pixman into that same wlroots-owned output buffer.
- Define format, clipping, blend, damage, completion, cache, and board gates. Pixman remains the default session.

## Capabilities

### New Capabilities

- `runtime/gpu-composition-trial`: An opt-in actual Sway/wlroots renderer experiment with per-frame coherent fallback and board-evidence gates.

### Modified Capabilities

None.

## Impact

This requires a maintained local fork of pinned wlroots 0.20.2 and an opt-in Sway package linked to it. It touches renderer, texture and render-pass code, not a desktop client. It does not alter stage 1, device tree, normal Sway, video decoder selection, or DRM ownership policy.

Physical-board trials are required for live composition, cache ownership, scanout, interaction and performance acceptance. Host builds and operation tests can proceed independently while the coordinator reserves the board. General GPU support and changing the default renderer are non-goals.

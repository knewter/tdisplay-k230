## Context

The physical validation passes private RGB565, premultiplied alpha, and private
DRM dumb-buffer import. At 568x1232, GPU completion wall time is about 1.97 ms
versus Pixman's 1.78 ms, while process CPU time is about 0.10 ms versus 1.70
ms. Process CPU time excludes interrupt, kernel, and whole-device work, and
the validated dma-buf was not the live compositor buffer.

## Goals / Non-Goals

**Goals:**

- Test whether the measured process-CPU reduction survives a client renderer
  operating on a private, compositor-owned dumb buffer.
- Define one context, one buffer owner, explicit completion, cache/fence, and
  failure fallback boundaries.

**Non-Goals:**

- A default renderer, direct live-buffer import, independent GPU clients,
  video overlay promotion, DMA fence invention, EGL/GBM, or a performance
  guarantee.

## Decisions

### Client-side experimental renderer

The trial is a wlroots/Sway client-side renderer implementation selected by an
explicit shell option. It retains the existing DRM backend and master owner.
Replacing Sway's DRM ownership or exposing `/dev/vg_lite` to desktop clients is
rejected: the pinned kernel Kconfig requires a single context/submission
thread, and the vendor driver does not validate command-buffer physical
addresses.

### One private dumb-buffer dma-buf

The renderer creates its own RGB565 dumb buffer through the existing DRM owner,
exports it as PRIME, CPU maps it, and imports the same fd with
`vg_lite_map(..., VG_LITE_MAP_DMABUF, fd)`. Board evidence selected
`VG_LITE_BGR565` for little-endian DRM/Pixman RGB565 memory. The vendor SDK
implements dma-buf map; its allocation-export path is not used. The experiment
does not map an existing live scanout buffer.

### Explicit producer/consumer boundaries

VG-Lite submission ends with `vg_lite_finish` before CPU sampling or handing
the buffer to DRM. The implementation must identify the DRM commit completion
mechanism available in this kernel and record it; it must not infer an implicit
shared dma-buf fence. CPU reads/writes use the vendor cache helper already
grounded in the C908 kernel source. Every mapped buffer is unmapped before its
DRM handle and fd are released.

### Narrow formats and scene

The first scene uses opaque RGB565 rectangles and point scales, then the
already observed premultiplied RGBA SRC_OVER operation. YU12/NV12 video,
textures, paths, and arbitrary client buffers are excluded until separate
format and ownership proof exists.

## Risks / Trade-offs

- [Wall time is slower than Pixman] → retain Pixman; process CPU reduction
  alone does not promote the trial.
- [Completion/cache ambiguity corrupts output] → stop the trial and retain
  the buffer/trace evidence; do not reuse it for live scanout.
- [Single-context contention] → serialize one renderer thread and reject a
  second client rather than relaxing the kernel constraint.
- [Renderer initialization fails] → explicit Pixman fallback with no modeset.

## Migration Plan

Ship no default configuration. Build and run the experimental option only on a
separate board trial, capture evidence, then either remove it or propose a
default change after every promotion gate passes.

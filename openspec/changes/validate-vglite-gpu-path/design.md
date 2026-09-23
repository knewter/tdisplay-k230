## Context

See [proposal.md](proposal.md). The pinned kernel exposes a root-only
`/dev/vg_lite` single-context API, while the shell owns DRM master and scans
out RGB565 dumb buffers. Existing board evidence proves only an opaque RGBX
private allocation; strict partially-alpha RGBA color preservation failed.

## Goals / Non-Goals

**Goals:**

- Produce one source-built, explicit board diagnostic for the next GPU gates.
- Test a private RGB565 result, report alpha/color samples, and test a private
  DRM dumb-buffer dma-buf import without modesetting.
- Print a reproducible GPU submit-to-`vg_lite_finish` timing window alongside
  a Pixman CPU window for the same 2x RGB565 blit geometry.

**Non-Goals:**

- A wlroots renderer, EGL/GBM support, compositor replacement, scanout,
  permission changes, DMA fence policy, video zero-copy, or a performance
  claim beyond the reported probe timing.

## Decisions

### One privileged executable with explicit subtests

The executable runs `rgb565`, `alpha`, `dmabuf`, and `benchmark` subtests (or
all in sequence), printing begin/end markers and sampled pixels. This keeps
the one-context vendor API serialized and gives the board owner a compact
transcript. Separate binaries were rejected because an accidental overlap of
their VG-Lite contexts is explicitly unsupported by the kernel driver.

### Private DRM allocation without changing display ownership

The dma-buf subtest opens the explicitly supplied DRM node with
`O_RDWR|O_CLOEXEC`; on this board it is `/dev/dri/card0`, with the running shell
already holding DRM master. It calls only dumb-create, PRIME export, dumb-map,
and dumb-destroy ioctls. The code contains no `drmSetMaster`, modeset,
add-framebuffer, plane, or atomic APIs. It maps the private dumb buffer on the
CPU, supplies that mapping and exported fd to `vg_lite_map`, waits with
`vg_lite_finish`, and checks every CPU-visible pixel. It must run with the
shell active; it does not select or adopt a scanout buffer.

### RGB565 is exact; alpha is diagnostic

The RGB565 test uses nonuniform red/green/blue/black quadrants and exact
multi-row boundary samples. Vendor `VG_LITE_BGR565` is the memory layout that
matches DRM/Pixman RGB565 on this board. The alpha test prints original and
blended pixels and compares one sample against explicit straight and
premultiplied source-over models; an unmatched result fails. Passing this
sample does not resolve the previously observed general RGBA quantization.

### Comparable, limited timing

Both paths perform identical nearest 2x scaling at 128x128-to-256x256 and
284x616-to-568x1232. After output validation and warmups, three rounds measure
monotonic elapsed and process-CPU time. GPU per-operation completion uses 20
iterations; batched GPU work ending in one finish and Pixman use 200 each.
This is not a compositor benchmark: cache state, memory placement,
synchronization, interrupt work, and future buffer-import costs differ.

## Risks / Trade-offs

- [VG-Lite rejects dumb-buffer import] → Preserve the ioctl error and record
  the exact blocker; do not fall back to a display-owner path.
- [A primary DRM node is unavailable to an unprivileged process] → The board
  owner runs the optional root-only diagnostic; no udev rule is added.
- [CPU observation needs cache synchronization] → `vg_lite_finish` is required
  before every read and outputs samples even on an assertion failure.
- [Timing is not a frame metric] → Label its scope and retain Pixman as the
  shell renderer until an end-to-end renderer proposal passes.

## Migration Plan

Build the optional package, run it only under the board coordinator, commit the
captured transcript, and update the integration recommendation. There is no
deployment, service, image, or boot-state migration. Remove the package export
to roll back host-side availability.

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

### DRM render-node access without display ownership

The dma-buf subtest opens `/dev/dri/renderD128` if present, otherwise opens the
provided DRM node with `O_RDWR|O_CLOEXEC`; it calls only dumb-create, PRIME
export, dumb-map, and dumb-destroy ioctls. The code contains no
`drmSetMaster`, `drmModeSetCrtc`, add-framebuffer, plane, or atomic APIs. It
maps the private dumb buffer on the CPU, supplies that mapping and exported fd
to `vg_lite_map`, waits with `vg_lite_finish`, and checks CPU pixels. A render
node is preferred because it cannot become DRM master. The primary-node
fallback remains bounded to allocation/export and does not alter the live
configuration.

### RGB565 is exact; alpha is diagnostic

The RGB565 test uses saturated red and black and exact 16-bit boundary samples,
avoiding the already observed alpha quantization. The alpha test uses separate
clear and blend samples and prints raw values; it fails only on API/completion
failure, because its role is to measure the unresolved color behavior rather
than encode an unsupported exactness assertion.

### Comparable, limited timing

Both paths perform the same repeated 128x128-to-256x256 point-scale geometry.
The GPU window begins before submissions and ends after one final
`vg_lite_finish`; the Pixman window begins before the first composite and ends
after the last. The output includes iterations, dimensions, elapsed nanoseconds
and ns/operation. This is a diagnostic, not a compositor-frame benchmark:
CPU cache state, memory placement, and synchronization differ.

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

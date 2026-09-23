# Opt-in VG-Lite compositor checkpoint

Date: 2026-09-23. This is a source and host contract checkpoint, not physical
GPU, cache, scanout, interaction, or performance acceptance. The default shell
still selects Pixman. The experiment must remain outside the default image.

## Pinned interfaces and ownership

wlroots 0.20.2 defines renderer/texture/pass implementations in
`include/wlr/render/interface.h` and operation fields in
`include/wlr/render/pass.h`. `types/scene/wlr_scene.c:1480-1578` supplies
non-null regions, opacity/luminance pointers, default premultiplied blending,
and default bilinear filtering even for unscaled opaque buffers. Its background
at line 2577 excludes visible opaque scene regions. The renderer supports that
ordinary full-redraw shape, as demonstrated by the host scene-region test.

The renderer locks only the output buffer passed by wlroots. It obtains dma-buf
attributes and a real CPU mapping through that buffer's API; it never opens
DRM, becomes master, allocates a scanout buffer, modesets, or commits. The
existing Sway/wlroots DRM backend remains responsible for all those operations.
The mapping must match the dma-buf format and stride and remains held until GPU
completion or lifetime quarantine. The SDK refuses `vg_lite_map` with both a
NULL memory pointer and zero physical address even for its dma-buf flag.

Recording copies clips, opacity, luminance, and primaries. Each texture operation
captures immutable RGBA pixels and a paired Pixman texture, so original textures
can be updated/destroyed and caller options released before submit. Texture
readback/allocation/region-copy failure fails the whole recorded pass; no prefix
is submitted. No GPU command occurs while recording.

## Current eligibility

Only `WLR_RENDERER=vglite` selects the fork. GPU submission additionally requires
**exactly** `K230_VGLITE_ALLOW_UNPROVEN_CACHE=1`; other strings, including `0`,
retain full-pass Pixman replay. This flag acknowledges missing physical proof.

- Target: one linear DRM RGB565 plane, matching dimensions, zero offset, valid
  descriptor, adequate 64-byte-aligned stride, checked size, and matching CPU
  mapping. It maps to `VG_LITE_BGR565`, supported by the prior private-buffer
  board probe. Other targets replay with Pixman.
- Rectangles: opaque colors, converted from the same 16-bit values as Pixman;
  arbitrary region intersections become disjoint GPU clear rectangles. Alpha
  rectangles replay with Pixman.
- Textures: CPU-accessible XRGB8888/ARGB8888 input only; arbitrary dma-buf input
  is ineligible. Readback uses DRM **ABGR8888**, whose little-endian bytes are
  R,G,B,A, matching the selected `VG_LITE_RGBA8888` byte convention. Integer
  source crops are copied into padded GPU allocations. Integer nearest upscales,
  or unscaled bilinear (identical sampling), with normal orientation are
  eligible. Partial texture clips, fractional/downscale geometry, color metadata
  and extra opacity replay with Pixman. Premultiplied blending is GPU-eligible
  only for fully opaque sources; other `SRC_OVER` cases remain Pixman. `NONE`
  replaces destination RGB with the source's premultiplied RGB.
- Damage: the union of eligible writes must cover the entire target. A typical
  clipped background plus opaque scene texture is supported. Partial damage
  replays the complete recorded list with Pixman, preserving undamaged pixels.
- Timelines: neither renderer advertises/implements explicit synchronization.
  Waits fail recording before source readback; output signals reject begin.
  Output color transforms and timers also reject begin because paired Pixman
  cannot implement those contracts. Texture color metadata follows paired
  Pixman's existing fallback behavior; the renderer advertises no color
  transformation feature.

GPU failures after commands start fail submit and permanently disable GPU use
in that process; they never start Pixman on the partially written target. The
next pass uses Pixman. Every allocated GPU source stays alive through finish.
If finish fails, target access/lock, GPU mappings and GPU allocations are
quarantined for process lifetime: no free, unmap, close, or buffer reuse can race
unproven completion. A process-global mutex serializes the vendor context,
including multiple renderer instances.

## Vendor cache and geometry audit

SDK pin: `kendryte/k230_linux_sdk` commit
`1104236db4d1e47873bd68924f912747b820228c`, under
`buildroot-overlay/package/vg_lite/`:

- `VGLite/vg_lite.c:2510`: `vg_lite_blit` cleans/invalidates CPU source memory
  before queuing. `vg_lite_blit_rect` at line 2990 omits that cache operation.
  The renderer consequently crops during upload and uses `blit`.
- `VGLite/vg_lite_matrix.c:73-106`: matrix helpers post-multiply, so scale then
  translate incorrectly scales the destination translation. The renderer sets
  the affine matrix explicitly using crop-local coordinates.
- `VGLite/vg_lite_image.c:123-157`: `upload_buffer` copies destination stride
  bytes per row, potentially reading past a tightly packed source. The renderer
  instead copies each checked row into the padded allocation itself.
- `VGLite/vg_lite.c:4114-4180`: mapping requires a CPU/physical address and maps
  the supplied dma-buf. `finish` at line 4298 submits, waits, and then performs
  target cache maintenance on its normal path. Its error returns establish no
  quiescence. `close` at line 3650 invokes termination; it is not a proven reset
  after failed completion.
- The renderer cleans/invalidates its CPU target before GPU ownership with the
  same C908 sequence packaged in `nix/vglite-probe.nix`. CPU upload to GPU read,
  GPU write to CPU read, and GPU write to DRM scanout still require physical
  observations. Source inspection and a mock cannot prove them.

## Host proof and remaining gates

Run the behavior test with the pinned source paths:

```sh
WLROOTS_SOURCE=/path/to/pinned-wlroots-0.20.2 \
VGLITE_SOURCE=/path/to/pinned-sdk/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
nix build .#shell-compositor-vglite --no-link --print-out-paths
```

The test compiles the actual renderer and pinned wlroots Pixman pass, uses real
Pixman image operations as its reference, and injects an asynchronous mock VG
API. It checks every output pixel plus padding, source/option lifetime, complete
recording failures, import rejection, source allocation failure before/after GPU
commands, command failures, failed finish quarantine, and following-pass Pixman
recovery under ASan/UBSan. It does not emulate physical GPU rounding or caches.
`tools/test-vglite-fallback.py` remains only a source wiring check.

[Committed host evidence](../evidence/vglite-renderer-host.md) records exact
commands, source artifacts, and output package. The OpenSpec tasks for physical
RGBA/alpha correctness, cache ownership, live Sway scene use, fallback rates,
scanout ownership, interaction and matched performance comparison remain open.

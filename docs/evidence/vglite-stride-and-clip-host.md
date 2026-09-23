# Padded scanout allocation and unscaled clip pieces

2026-09-23 UTC, original branch `apply/vglite-composition`, continued by the
coordinator in `apply/vglite-local-continuation`, base
`033def7fe766e3e7c41e58ea6254a0fb9bfd2336`. Source and sanitizer-backed host
proof only. Actual padded scanout and clipped GPU rendering remain
**UNVERIFIED** until a reserved board trial records them.

## Why pad the allocation

The instrumented board investigation exposed a 568-pixel RGB565 target with
1136-byte stride and a parent texture clipped into four visible rectangles.
Committed board inputs: `docs/evidence/vglite-scene-board/README.md` and
`docs/evidence/vglite-scene-board/diagnostic/decisions.log` (master `48238b0`).
The renderer's conservative 64-byte stride guard and whole-texture clip guard
therefore prevented submission after the color-metadata gate. This checkpoint
retains the stride guard and changes allocation in the opt-in wlroots fork.

Pinned kernel source is the tree used by `nix/kernel.nix`, available during this
review at `/nix/store/a28q49s6dyj4sd82y657bjlmyvk5574m-linux-xuantie-k230-src`:

- `drivers/gpu/drm/canaan/canaan_drv.c:153–175`,
  `canaan_drm_dumb_create`, computes pitch directly from requested width and
  bits per pixel, then allocates pitch times height.
- `drivers/gpu/drm/canaan/canaan_vo.c:210–241` programs visible width/height
  from the plane source rectangle, separately from stride (`fb->pitches[0]/8`).
  A padded pitch does not require changing visible dimensions.
- Pinned wlroots `render/allocator/drm_dumb.c` keeps buffer/base/dma-buf logical
  dimensions separately from the width supplied to `drmModeCreateDumbBuffer`.
  Its CPU access and exported dma-buf both report the returned kernel stride.

Only RGB565 allocations under the exact `WLR_RENDERER=vglite` selection round
storage width up to 32 pixels. Thus 568 logical pixels request 576 storage
pixels, yielding a 1152-byte stride in the reviewed driver. Buffer dimensions,
framebuffer dimensions, DRM descriptor, modeset/commit owner, and renderer
output-buffer selection stay with the existing wlroots path. No renderer opens
DRM. Width rounding is checked for overflow. Other formats, absent renderer
selection, and `WLR_RENDERER=pixman` preserve the old request.

The normal image does not use this fork. For a comparison with identical padded
allocation, keep `WLR_RENDERER=vglite` and use cache flag `0` to force Pixman;
switching the renderer environment to `pixman` deliberately uses its original
allocation. Kernel returned layout is still checked by the renderer before GPU
use; padding is not permission to bypass that check.

## Why CPU crop the visible rectangles

Pinned SDK `1104236db4d1e47873bd68924f912747b820228c`, under
`buildroot-overlay/package/vg_lite`:

- `VGLite/vg_lite.c:1899–1906` checks `DEST_ALIGNMENT_LIMITATION` for tiled
  targets. That alone is insufficient hardware evidence to relax the existing
  linear-target guard, so this change keeps it.
- `VGLite/vg_lite_image.c:254–275` changes scissor state.
  `VGLite/vg_lite.c:1846–1880` can then enter `set_render_target` and call
  `vg_lite_finish` without checking its return value. This change introduces
  no scissor API dependency or repeated target change.
- `VGLite/vg_lite.c:3960–4009` leaves RGBA source width/height intact and pads
  source stride for allocation. `vg_lite_blit` cleans source cache before use;
  the existing CPU upload and blit path is retained for each piece.

A partially clipped texture is admitted only when integer source size equals
integer destination size. Each nonoverlapping rectangle from the intersected
Pixman region maps to source origin
`source_origin + rectangle_origin - destination_origin`, with the rectangle's
integer size. Uploading exactly that crop and blitting at the rectangle origin
therefore preserves pixel correspondence without new sampling or clipping
semantics. Each source has its own padded GPU allocation; checked preflight
counts reserve their array, and every allocation stays alive through finish.

Existing whole-texture integer scaling remains supported. A scaled texture
with a partial clip still replays Pixman (`texture_clip_scaled`). Fractional
source geometry, out-of-target destinations and all earlier unsupported color,
alpha, transform and sync cases retain their guards. **Partial redraw stays
ineligible:** the union of actual visible regions must cover the full target.

An allocation error after any prior piece was submitted calls finish before
cleanup and discards the frame rather than replaying over partial GPU work.
An error before submission can replay the complete pass. Failed finish retains
all pieces plus the mapped target/lock for process lifetime, as before.

## Executed tests

```sh
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
  tools/test-vglite-dumb-stride.sh
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
VGLITE_SOURCE=/tmp/k230-sdk-vglite-src/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
nix build .#shell-compositor-vglite --no-link --print-out-paths
```

Allocator ASan/UBSan test: PASS. Compiles the actual patched wlroots allocator
with fake DRM calls/mapping plumbing. It verifies 568/576/1152 logical/storage/
stride values, CPU/dma-buf agreement, already aligned and one-pixel widths,
unchanged Pixman/unset/near-match selection and other formats, overflow rejection,
and cleanup after failure following dumb-buffer creation. All calls use the
same supplied DRM descriptor; no real device or ioctl is involved.

Renderer ASan/UBSan test: PASS. Actual pinned Pixman pixel comparison covers a
568-wide parent with four visible rectangles surrounding an opaque child,
nonzero source crop origin, a clip extending beyond target bounds, an empty
texture region, partial-damage rejection, and scaled-clip rejection. Failure
injection on the third source allocation proves two previously queued uploads
finish before being freed, with no fallback over a partial frame. Failure on
the first allocation permits full replay; failed finish quarantines all four
source uploads and the target. Earlier color, geometry and lifetime tests pass.

The coordinator independently reran both sanitizer tests successfully. The
first full cross-build ended with signal/exit 143 without a compiler diagnostic;
a retry completed successfully using the cached dependencies:
`/nix/store/iy08ig1xw3xhhh1ph31g5jy59lj04f19-sway-1.12`. The retry used
`--max-jobs 1 --cores 4`. This is cross-build proof only; no new GPU board
result is claimed here.

## Physical gate

The reserved operator must import the rebuilt package and use the bounded root
scene harness, retain a visible-frame prerequisite before capture (IPC mapping
alone is insufficient), verify decision logs report stride 1152 and whether
submission actually occurs, compare against matched forced-Pixman output, and
verify normal-shell restoration. A successful cross-build or host pixel model
does not prove the hardware stride, source/cache path, completion, or scanout.

## Context

The physical probe established exact private RGB565 composition using `VG_LITE_BGR565`, one premultiplied-alpha result, and private dumb-buffer dma-buf import. The committed record at [`docs/evidence/gpu-validation/README.md`](../../../docs/evidence/gpu-validation/README.md) also records that this is not live compositor or scanout proof. Three CPU-timing rounds are committed at [`docs/evidence/gpu-validation/cpu-timing-pass.txt`](../../../docs/evidence/gpu-validation/cpu-timing-pass.txt): at 568x1232, GPU finish used about 0.10 ms process CPU versus Pixman's 1.70 ms while wall time was about 1.97 ms versus 1.78 ms. Process CPU includes user and system time charged to the process; it does not measure other processes, separately accounted interrupt work, or whole-device cost.

The current shell explicitly selects Pixman in [`nix/shell.nix`](../../../nix/shell.nix) and uses Sway with wlroots 0.20. The pinned wlroots source creates the output buffer in `types/output/render.c:wlr_output_begin_render_pass`, passes it to `wlr_renderer_begin_buffer_pass`, and commits the result from `types/scene/wlr_scene.c`. Scene rendering emits rectangles and textures through `wlr_render_pass_add_rect` and `wlr_render_pass_add_texture` in that file. The renderer and render-pass vtables are unstable compiled interfaces in `include/wlr/render/interface.h`; operation options, clipping, blend, filter, color and explicit-sync fields are in `include/wlr/render/pass.h`.

## Goals / Non-Goals

**Goals:**

- Test an actual VG-Lite `wlr_renderer` backend under the existing Sway scene and DRM backend.
- Keep exactly one DRM master and exactly one serialized VG-Lite context.
- Make every submitted frame coherent: entirely VG-Lite or entirely Pixman, never a partial mixture.
- Establish the narrow operation, format, synchronization and damage contract before any default change.

**Non-Goals:**

- A standalone Wayland client, a second DRM master or framebuffer owner, direct scanout, EGL/GBM, video-overlay promotion, a general dma-buf texture importer, invented fence APIs, or a performance guarantee.

## Decisions

### Fork wlroots, then rebuild the experimental Sway against it

wlroots has no runtime loadable renderer plug-in interface: the renderer and render-pass vtables are compiled interfaces. The experiment therefore needs a local fork of pinned 0.20.2, adding a VG-Lite `struct wlr_renderer_impl`, `struct wlr_texture_impl`, and `struct wlr_render_pass_impl`, plus an opt-in Sway package built against that fork. Calling a separate painter “the renderer” would not exercise the Sway scene path and is insufficient.

The default package keeps `WLR_RENDERER=pixman`. The opt-in package may select the fork's VG-Lite renderer only after host and board gates pass. It must not expose `/dev/vg_lite` to ordinary Wayland clients.

### Preserve the existing wlroots DRM owner

Sway and its existing wlroots DRM backend retain DRM master, output selection, swapchain allocation, and commit ownership. For every frame, `wlr_output_begin_render_pass` supplies the destination `struct wlr_buffer`. The VG-Lite backend may obtain dma-buf attributes with `wlr_buffer_get_dmabuf` and import that specific output buffer; it does not open a card node, allocate an independent scanout buffer, modeset, or commit. It returns after `wlr_render_pass_submit`, so the existing owner continues the normal commit path.

### Record then choose one renderer for the entire pass

The forked render pass records immutable copies of each `add_rect` and `add_texture` operation until `submit`. At submit it selects one path:

1. If the target buffer and every operation meet the VG-Lite contract, execute the complete list in the one serialized VG-Lite context, finish it, and return success.
2. Otherwise replay the complete recorded list through a paired Pixman renderer targeting the *same wlroots-provided output buffer* and return that result.

No command is sent to VG-Lite before path selection. This avoids a frame where one unsupported texture, clip, or blend leaves an incomplete GPU buffer that Pixman then tries to repair. A failure after GPU work starts fails `submit`, lets wlroots discard the frame/damage ring as it already does, and forces the next frame to Pixman; it must not commit a partial buffer.

### Make operation support explicit

The initial VG-Lite eligibility table must be implemented and tested before a board session:

| wlroots render-pass input | Initial experimental handling |
| --- | --- |
| Destination | Only the wlroots-provided dma-buf proved to have a DRM format / VG-Lite mapping. The board result points to DRM RGB565 memory with `VG_LITE_BGR565`; every plane, stride and modifier must be checked. |
| `add_rect` | Opaque and premultiplied rects after exact color conversion, with the supplied clip region. Unsupported color/clip makes the whole pass Pixman. |
| `add_texture` | First establish `wlr_texture_from_buffer` and exact `WL_SHM` XRGB/ARGB mapping. Conversion/upload into a VG-Lite source allocation is permitted only after samples prove it. Arbitrary dma-buf textures, modifiers and YUV cause whole-pass Pixman replay. |
| Scaling / transform | Nearest scale only after source/destination and bounds tests. Bilinear, non-identity output transforms and unsupported source boxes cause replay. |
| Blend | Only observed premultiplied `SRC_OVER` and `NONE`, once matched to wlroots' premultiplied `wlr_render_color` contract. Any mismatch causes replay. |
| Clip / damage | Translate every pixman clip only after region tests. Until then, any nontrivial clip or partial damage makes the entire pass Pixman. Full-frame GPU redraw may be enabled only after preservation of undamaged output is proved. |
| Color / synchronization | Transfer functions, primaries, YCbCr fields, timeline waits/signals, and unproved cache transitions cause replay. |

The table reflects fields actually carried by `wlr_render_texture_options` and `wlr_render_rect_options`, not a claimed VG-Lite feature set. `types/scene/wlr_scene.c` supplies damage-driven background and scene operations, so treating damage as ignorable would be incorrect.

### Completion and cache ownership

The sole submission thread calls `vg_lite_finish` before a successful VG-Lite `submit`. The fork must prove C908 cache clean/invalidate direction for the imported target and CPU-uploaded source, and identify how wlroots/DRM consumes the buffer and whether source timeline fields can be honored. Until that proof, it uses synchronous completion and rejects operations with timeline fields rather than claiming a fence.

## Risks / Trade-offs

- Comparable or worse elapsed time → retain the normal Pixman session even if one process spends less CPU time.
- Unsupported scene command → replay the full pass in Pixman; do not mix output from two renderers.
- DMA-buf format, stride, modifier, completion, or cache ambiguity → reject GPU for that pass and retain Pixman.
- Fork maintenance burden or wlroots API change → keep the feature opt-in and do not present it as upstream integration.

## Migration Plan

Ship no changed default. Build the fork and experimental Sway separately, run only board-coordinated trials, retain per-pass fallback logs and evidence, then either remove the experiment or open a separate default-change proposal after all readiness gates pass.

# Opt-in VG-Lite compositor checkpoint

Date: 2026-09-23. This checkpoint contains an opt-in renderer with real
VG-Lite RGB565 rectangle and normalized SHM texture upload routes, plus a
complete Pixman replay fallback. It does not claim board acceptance or cache
and import correctness beyond the guarded routes.

## Pinned interface audit

The target is wlroots 0.20.2. Its unstable renderer interface declares
`wlr_renderer_impl.begin_buffer_pass(renderer, buffer, options)`,
`wlr_texture_impl`, and `wlr_render_pass_impl` in
`include/wlr/render/interface.h`. The render-pass options in
`include/wlr/render/pass.h` carry the destination buffer, clip regions, source
and destination boxes, transform, filter, premultiplied or NONE blend mode,
color metadata, and optional timeline wait or signal fields.

`render/wlr_renderer.c` selects the renderer from `WLR_RENDERER`. This patch
adds an explicit `vglite` branch and compiled render-pass implementation.
Supported full passes use the supplied single-plane linear DRM RGB565 dma-buf,
map it as `VG_LITE_BGR565`, issue rectangle clears, or upload normalized
ARGB8888 pixels to a VG-Lite RGBA8888 source and blit it, then call
`vg_lite_finish`. Unsupported textures, clips, transforms, metadata, timelines,
formats, modifiers, cache state, or failures replay the complete pass through
Pixman. `WLR_RENDERER=pixman` and the normal `auto` path are unchanged.

The GPU route is opt-in through `K230_VGLITE_ALLOW_UNPROVEN_CACHE`; it fails
closed unless the output is the exact linear RGB565 dma-buf and all recorded
operations fit the narrow route. The texture upload is eligible only for an
opaque, nearest, normal-orientation copy. Any failed upload, import, command,
or finish causes a complete Pixman replay.

## Remaining proof and integration work

The renderer is built in the wlroots source fork, not as a separate Wayland
client. `begin_buffer_pass` accepts only the supplied output buffer;
`add_rect` and `add_texture` record immutable operations; and `submit` chooses
either all-VG-Lite or all-Pixman replay before any GPU command is sent.
Unsupported target/source format, modifier, clip, transform, filter, color,
blend, damage, cache, or timeline behavior selects Pixman for the complete
pass. Existing evidence only grounds private `VG_LITE_BGR565` behavior; it does
not ground scanout or wlroots texture import.

The vendor context is single-context and is serialized. Cache clean and
invalidate direction, `vg_lite_finish`, wlroots buffer lifetime, texture channel
mapping, and timeline fields need source and board evidence before enabling
them by default. No default change is justified by this checkpoint.

## Host proof

Run:

```sh
python3 tools/test-vglite-fallback.py
```

The narrow check verifies the opt-in selection marker, real rectangle/upload
symbols, complete-pass Pixman fallback declaration, and absence of DRM
ownership calls in the patch. It is a source contract check only. A raw
pinned-source apply check is:

```sh
git -C /tmp/wlroots-contract apply --check \
  nix/patches/wlroots-vglite-full-pass-pixman.patch
```

A board session is still required for any claim about VG-Lite, scanout,
compositor timing, cache ownership, touch recovery, or default promotion.

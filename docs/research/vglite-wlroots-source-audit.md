# Opt-in VG-Lite compositor checkpoint

Date: 2026-09-23. This checkpoint contains an opt-in renderer with a real VG-Lite RGB565 rectangle submission route and a complete Pixman replay fallback. It does not claim board acceptance or texture/GPU coverage beyond the guarded route.

## Pinned interface audit

The target is wlroots 0.20.2. Its unstable renderer interface declares
`wlr_renderer_impl.begin_buffer_pass(renderer, buffer, options)`,
`wlr_texture_impl`, and `wlr_render_pass_impl` in
`include/wlr/render/interface.h`. The render-pass options in
`include/wlr/render/pass.h` carry the destination buffer, clip regions, source
and destination boxes, transform, filter, premultiplied or NONE blend mode,
color metadata, damage-related caller behavior, and optional timeline wait or
signal fields.

`render/wlr_renderer.c` selects the renderer from `WLR_RENDERER` and the
existing Pixman implementation begins a pass against the wlroots-provided
`wlr_buffer`. The checkpoint adds an explicit `vglite` selection branch and a compiled render-pass implementation. Supported full passes use the supplied single-plane linear DRM RGB565 dma-buf, map it as `VG_LITE_BGR565`, issue rectangle clears, and call `vg_lite_finish`; unsupported textures, clips, transforms, metadata, timelines, formats, modifiers, cache state, or failures replay the complete pass through Pixman. `WLR_RENDERER=pixman` and the normal `auto` path are unchanged.

The patch applies cleanly to the pinned source and is intentionally named a
fallback. It is a safe integration seam for an experimental Sway package while
the actual VG-Lite implementation remains unverified. The next implementation
must replace this branch with a compiled renderer and preserve the same
full-pass fallback rule.

## Required next renderer work

A real renderer must be built in the wlroots source fork, not as a separate
Wayland client. `begin_buffer_pass` must accept only the supplied output buffer;
`add_rect` and `add_texture` must record immutable operations; and `submit` must
choose either all-VG-Lite or all-Pixman replay before any GPU command is sent.
Unsupported target/source format, modifier, clip, transform, filter, color,
blend, damage, cache, or timeline behavior must select Pixman for the complete
pass. The initial board evidence only grounds private `VG_LITE_BGR565` behavior;
it does not ground scanout or wlroots texture import.

The vendor context is single-context and must be serialized. Cache clean and
invalidate direction, `vg_lite_finish`, wlroots buffer lifetime, and timeline
fields need source and board evidence before enabling them. No default change
is justified by this checkpoint.

## Host proof

Run:

```sh
python3 tools/test-vglite-fallback.py
```

The narrow check verifies the opt-in selection marker, complete-pass Pixman
fallback declaration, and absence of DRM ownership calls in the patch. It is a
source contract check only. A raw pinned-source apply check is:

```sh
git -C /tmp/wlroots-contract apply --check \
  nix/patches/wlroots-vglite-full-pass-pixman.patch
```

A board session is still required for any claim about VG-Lite, scanout,
compositor timing, cache ownership, touch recovery, or default promotion.

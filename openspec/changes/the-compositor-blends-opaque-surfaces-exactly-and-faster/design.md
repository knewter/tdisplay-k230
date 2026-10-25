## Context

The pixman renderer composites each scene buffer with
`pixman_image_composite32`. For ARGB8888 client buffers onto the RGB565
output this dispatches to RVV `over_8888_0565`: load source, load and widen
destination, blend, narrow and store, 16 pixels per chunk at VLEN 128. Opaque
and empty sources pay for that just like translucent ones.

## Goals / Non-Goals

- **Goal:** skip the destination read and the blend wherever they cannot
  change the result, with byte-identical output.
- **Non-goal:** opacity hints at the scene level. Opaque regions on sliding
  surfaces are excluded, and a scan of mutable client buffers would need
  invalidation on every commit.

## Decisions

- **Test inside the kernel, per vector chunk.** The test is one compare and
  one popcount on data already loaded, so it needs no cache and no
  invalidation.
  - Alpha all 0xff: OVER yields the source exactly, because pixman's UN8
    multiply by 0 is 0. The chunk is converted and stored.
  - Source all zero: OVER yields the destination exactly. The chunk is
    skipped, and the destination's 0565 → 0888 → 0565 round trip is lossless
    anyway.
- **Stop testing a row after its first chunk that is neither.** Testing every
  chunk cost the 0.95-alpha drawer 0.6 ms per frame; one test per row costs
  nothing measurable.
- **Scope the patch to the compositor.** A global Pixman change rebuilds 104
  store paths (about 300 MB). sway names `libpixman-1.so.0` directly, so with
  the patched Pixman first in its RUNPATH, that copy is loaded and cairo
  reuses it by soname. The board confirms this in `/proc/<sway>/maps`.
- **Rejected options:**
  - wvkbd opaque region: rejected by the operator;
  - `--no-popup`: wvkbd still maps the transparent surface, and measured no
    gain.

## Risks / Trade-offs

- Two copies of Pixman exist in the closure. If a future sway stopped linking
  Pixman directly, the load order could pick the shared copy. That would be
  slower but still correct; `/proc/<sway>/maps` shows which copy is loaded.
- Upstream Pixman changes to `pixman-rvv.c` can make the patch fail to apply.
  Any such failure happens at build time, not at runtime.

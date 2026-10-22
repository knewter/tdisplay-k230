## Context

`scaled_mirror` pre-scales an eligible SHM card source into a buffer it can
reuse, together with the RGB565 interior the landscape quarter-turn needs.
The buffer is reused while the size, format, filter and source generation
match. On a fixed-size deck that is a good trade. During entry and expand,
`card_shown_large` also makes the buffer due on every client commit. The
size changes on every frame anyway, so the cache never hits.

## Goals / Non-Goals

- **Goal:** no thumbnail rebuild for a size that will be gone next frame.
- **Non-goal:** a cheaper rescale. The direct path already composites a
  scaled source in one pass.

## Decisions

- **Bypass on a size change only while in motion.** `scene_in_motion()`
  already selects the nearest filter for both paths, so the frames look the
  same either way. Outside motion, a size change still rebuilds the cache
  once, because the new size will hold.
- **Keep the existing cached buffer.** A drag at the cached size picks it up
  again without a rebuild.
- **Rejected options:**
  - reusing the previous thumbnail scaled again by the scene: that resamples
    twice and blurs content while moving;
  - lowering the per-frame rescale cost with RVV: the work is still thrown
    away every frame.

## Risks / Trade-offs

- The direct path composites from the full-size source every frame while
  resizing. For the busy arm on the board, this still cut sway's entry repaint
  median from 13.7 to 9.3 ms (p90 from 27.6 to 12.7 ms).

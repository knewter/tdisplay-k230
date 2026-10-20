# Exact title ink bounds — 2026-10-20 UTC

The source37be9567 profile measures0.399ms mean for32 draws of a787×44
ARGB OVER title, most of which is transparent. The selected producer change
scans the completed immutable Cairo raster once, after full-size Pango layout
and ellipsis. Bounds include every nonzero32-bit texel, not merely alpha.
No resolution, font, color, glyph edge, ellipsis or layout size changes.

Only header paint crops to these bounds at integer1:1 coordinates; source
coordinates and destination position move together. The authored buffer's full
size stays the reuse key. Empty/invalid/unrecognized buffers retain the former
path. Icons, plates, client content and chrome are unchanged. Label metadata
lives inside its existing owner, with no new pixel allocation or client ref.
Deck touch/pointer ownership and hit tests use unchanged policy geometry.

The header caller now retains the clipping helper's visibility result when
applying entry/expansion visibility. Otherwise a cropped label whose ink has
left the viewport could be reenabled at its stale previous position. Other
label_clip callers retain their existing behavior.

`python3 tests/test_panel_paint.py` passes6 tests, including1104 independent
full-image versus cropped Pixman comparisons intoRGB565 andXRGB, changing
patterns, all-zero labels, alpha-zero/nonzeroRGB texels, padding, clips,
global alpha, partially/wholly offscreen movement, real antialiasedPango
glyphs, ellipsis, Unicode, font size and weight changes. Invalid bounds retain
the caller's output unchanged. Earlier cache/corner/output-buffer lifetime
and live-pixel native oracles remain passing. Named affine1152 and rounded288
comparisons also pass. Native tests are not integrated timing or optical proof.

Exact cross-build, deterministic paired board timing, changing-client checks,
camera, persistent default and archive remain open for this candidate. Keep
all frozen budgets, image quality and the8ms anti-flicker guard unchanged.

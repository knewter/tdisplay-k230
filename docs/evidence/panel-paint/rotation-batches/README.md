# Batched exact rotation — 2026-10-20 UTC

The source895e753d integrated profile leaves output rotation at3.015ms mean,
versus1.142ms texture work across49 grouped gesture passes. The next selected
boundary is exact RGB565 gather/store scheduling, with the same16×16 tile.
The8ms guard, source freshness, physical-buffer ownership, damage history,
quality and frozen timing budgets are unchanged.

All comparisons hold the sole board reservation while baseline48af runs
normally. Fresh heap source pixels rotate into **unattached** DRM dumb buffers
at1232×568 logical geometry. No modeset or compositor replacement. Three
alternating12-copy rounds per branch/transform follow warmup. Each variant
first compares complete destination pixels/padding from independently reset
buffers. Full copies and a separate synthetic region union of measured card
geometries are tested; the region is not claimed to be a captured repaint.
Exact sources, commands, hashes, UTC bounds and all raw rows are adjacent.

Twelve rectangular tile combinations find no useful gain: the best region
270 difference is0.4%, while taller tiles substantially regress. Regrouping
horizontal tiles or swapping outer loop order also regresses.32-bit stores
are slower. General compiler unrolling remains rejected by earlier evidence.

A bounded eight-pixel batch plus the existing guarded no-overlap contract
expressed with C restrict wins both tested transforms and both regions:

| Transform | Copy | Baseline CPU | Selected CPU | Cost reduction |
| --- | --- | ---: | ---: | ---: |
| 90 | Full | 4.318ms | 3.835ms | 11.2% |
| 270 | Full | 4.236ms | 3.721ms | 12.2% |
| 90 | Synthetic region | 3.480ms | 2.907ms | 16.5% |
| 270 | Synthetic region | 3.384ms | 2.834ms | 16.3% |

Restrict alone does not help. Sixteen-pixel batches have a smaller regional
gain; deferring stores gives similar regional results but a less consistent
full-copy result. The selected eight-pixel body emits two aligned64-bit stores,
retains the four-pixel/scalar prefix/tail fallbacks, and keeps the32-bit pixel
algorithm. Both public full/partial callers already reject overlapping complete
ranges before entering the restricted helper. No ISA/compiler-option change.
The published header normalizes whitespace,0/1 offsets and sizeof spelling;
experimental source snapshots/hashes preserve the compiled prototypes.

The named native command passes6 tests:288 guarded changing-frame rotation
cases plus eight **distinct overlapping image pairs** rejected unchanged for
both full and partial calls,352 exact three-buffer output compositions and
existing lifecycle failures,160 full-precision caches,512 opaque-interior
oracles/32 corner-loss sentinels,768 conversion oracles and1104 real-label
comparisons. Affine1152 and rounded288 checks also pass. Synthetic CPU gains
are not integrated latency, optical continuity or paired budget acceptance.

The board was left on baseline48af/Home/normal with no owned overrides/test
devices and released after experiments. Exact-source build, comparable paired
timing/live/camera/default/archive proof remain open for this new source.

# The per-boot effect set: `beams decrypt matrix middleout synthgrid rain waves wipe`

Chosen by the coordinator on 2026-10-30 (the user: "you pick what goes"). Each member is checked against the three
budgets. No effect was swapped. Evidence classes are named per line.

| Budget | Result | Source (class) |
| --- | --- | --- |
| Code size | `fw,boot-set` staticlib: .text 216 262 + .rodata 36 280 = **252 542 bytes** (all 37 effects: 520 046; the earlier 8-effect set: 197 630). The slot has 658 919 bytes free after Life's current candidate (389 657 of 1 048 576), so about 406 KB remain for the font table, glue, fallback sequences and growth | host link of the riscv64imac archive with rust-lld; `readelf -S`, same method as `nostd-sizes.txt` |
| Arena | peak heap, maximum over both texts, seeds 1, 2, 3, 7, 11 and both orientations: `beams` 8 552 KiB, `synthgrid` 6 243, `waves` 4 043, `decrypt` 3 271, `rain` 1 612, `middleout` 1 566, `matrix` 1 388, `wipe` 1 188; limit 16 352 KiB | `boot-effect-set-peaks.txt` (host, counting allocator) |
| Frame time | on the C908, as a Linux static executable running the firmware object code, both orientations, both texts: worst **1.96 ms per frame** (`beams`, portrait, K230 banner); `wipe` 0.23 to 0.24, `middleout` 0.1 to 0.5, `matrix` 0.6 to 0.8, `synthgrid` 0.6 | `board-boot-set-bench.txt` (board process run); all 32 frame streams (count, bytes, FNV-1a) equal the std ttfx's |

Durations at 30 fps (frames / 30, over both texts and orientations): `middleout` 2.6 to 3.1 s, `wipe` 4.6 s, `rain` 2.4 to 7.9 s,
`beams` 10.3 to 11.6 s, `waves` 16.4 to 17.1 s, `synthgrid` 21 to 22 s, `decrypt` 19.6 to 27.2 s, `matrix` 31 to 48 s.
Only the first seconds happen in U-Boot; Linux continues the same run (design D4, D9).

Limits: the frame times are Linux with caches on, not U-Boot (design D14); the heap peaks are the host's allocator counts
for the same code; the glyph coverage of each effect is the Unifont subset already generated (decrypt and matrix draw
Latin and half-width katakana, `ttfx-research.md`).

# The DSI PHY is calibrated for 445.5 Mbps whatever we actually run

2026-09-21. `canaan_dsi.c:424`:

```c
k230_dsi_config_4lan_phy(dsi, m - 2, n - 1, voc, 0x96);
```

`voc` (the VCO range) is computed from the requested frequency by a
ladder of comparisons. `hsfreqrange` is the literal **`0x96`**, which
the driver's own header names `TXPHY_445_5_HS_FREQ` -- the setting for
445.5 Mbps. It is never derived from anything.

In a DWC MIPI D-PHY, `hsfreqrange[6:0]` (PHY register 0x44) selects the
HS timing calibration -- T(hs-prepare), T(hs-zero), T(hs-trail) and
friends. It must track the actual lane bit rate. Ours never moves.

## The evidence is a clean monotonic ladder

Measured on hardware, all on the same board and image, varying only the
device tree pixel clock (and in two cases the reverted 25% headroom
patch). Lane rate is 2 x the PHY clock.

| pixel clock | PHY clock | lane rate | vs 445.5 | panel |
| --- | --- | --- | --- | --- |
| 31.68 MHz +25% | 237.6 MHz | 475 Mbps | +7% | works |
| **49.5 MHz** | **297 MHz** | **594 Mbps** | **+33%** | **works, but this is where the roll is** |
| 56.9 MHz | 341 MHz | 682 Mbps | +53% | **frozen** -- stale frame, framebuffer writes do not reach the glass |
| 49.5 MHz +25% | 371.25 MHz | 742 Mbps | +67% | **blank** (`dsi-burst-headroom.md`) |

Degradation is monotonic in distance from the hardcoded calibration
point. That is the signature of a wrong `hsfreqrange`, not of a clock
that is simply too fast: nothing else in the chain changes character at
445 Mbps.

Note the bucket ladder is a red herring. 297 and 341 MHz do sit in
different `voc` buckets (`<330000` and `<440000`), which is a tempting
explanation, but 475 Mbps and 594 Mbps share a bucket and behave
differently in degree, and the ordering tracks the lane rate rather
than the bucket boundary.

## The vendor does not do this

`display_logo.c:952` in the SDK's U-Boot:

```c
k230_dsi_config_4lan_phy(phy->m, phy->n, phy->voc, phy->hs_freq);
```

`hs_freq` comes from a **per-panel** attribute struct
(`st7701.c:795`, `k_connectori_phy_attr`). The vendor treats it as
configuration. The Linux driver dropped that and froze one value.

## Why this is the lead suspect for the residual roll

Our working configuration already runs the link **33% above** what the
PHY is timed for. HS transitions are therefore marginal, which is
consistent with an image that is mostly stable and occasionally slips a
few rows -- `flicker-after-headroom-revert.md` measures a uniform
whole-frame roll of ~2.8 rows RMS that wraps.

It also explains why raising the clock makes things worse in a graded
way -- frozen, then blank -- rather than failing cleanly.

## What the fix needs, and the one thing not known

Derive `hsfreqrange` from the lane rate instead of hardcoding it. The
obstacle is the mapping table: the driver exposes only three points,
and two of them disagree with a simple monotonic reading --
445.5 Mbps -> 0x96, 891 Mbps -> 0x96, 475 Mbps -> 0xa3. The high bit
appears to be a flag (the vendor's own comment asks why it is set), so
the code is probably `0x80 | hsfreqrange`, giving 0x16, 0x16 and 0x23.
That is not enough to interpolate from, and guessing PHY timing is how
the panel got blanked the first time.

**Proposed approach: make it a device tree property first.** Plumb
`hsfreqrange` through from the DT with 0x96 as the default, so the
value can be swept with an 11 second `push-file.py` DTB push instead of
a 20 minute kernel rebuild per candidate, exactly as was done for the
panel init sequence. One rebuild, then measure the roll against each
candidate and keep what is measured to be best.

---

# RESOLVED: 0x87 stops the roll

2026-09-21, later. `hsfreqrange` was plumbed through the device tree
(`canaan,hsfreqrange`, commit `ac31e98`) so candidates could be tried
with an 11 s DTB push rather than a 20 minute rebuild each. Three were.

| value | code | standard-table meaning | result |
| --- | --- | --- | --- |
| 0x96 | 0x16 | 450..499 Mbps | works, **rolls** (the shipped default) |
| 0x97 | 0x17 | 550..599 Mbps | **blanks the panel** |
| **0x87** | **0x07** | **500..549 Mbps** | **works, stable** |

## The prediction was wrong, and that is the interesting part

The standard Synopsys hsfreqrange table puts 594 Mbps in the 550..599
band, i.e. 0x17, byte 0x97. That was the reasoned first candidate. It
blanks the panel outright. The value that works is one band BELOW what
the table prescribes, so this SoC's bands do not line up with the
standard table. 0x87 is here because it was measured, not because it
was derived.

## Measurement

Like-for-like: same board, same camera position, same crop, only the
device tree value changed between runs. Registration deliberately not
used -- for a relative A/B with the geometry fixed, perspective is
identical and cancels, so camera pixels are a valid comparison even
though an absolute figure in panel rows would not be.

| | 0x96 | 0x87 run 1 (20 s) | 0x87 run 2 (30 s) |
| --- | --- | --- | --- |
| motion std | 0.68 px | 0.35 px | **0.02 px** |
| span | 4.50 px | 1.92 px | **0.09 px** |
| frame-to-frame mean | 0.26 px | 0.02 px | **0.00 px** |
| frame-to-frame max | 2.33 px | 0.35 px | **0.04 px** |
| jumps > 2 px | 1 | 0 | **0** |
| brightness range | 91..101% | 88..101% | **100..100%** |

The user, watching the screen, called 0x87 "rock solid" before any of
these numbers existed.

**Run 2 was checked for the failure it resembles.** Numbers that good --
and a brightness range of exactly 100..100% -- are also what a FROZEN
panel produces, which is how the 60 Hz experiment fooled us earlier.
Verified by writing an all-white framebuffer and re-photographing: mean
absolute difference 59.8 against the target image, so the panel is
live and updating. The stability is real.

## What this does not settle

Why 0x07 rather than 0x17 -- that is empirical. A different pixel clock
would need its own value and there is still no table to derive it from,
which is precisely why the value stays in the device tree rather than
being folded back into a driver constant.

---

# The PLL numbers for 594 Mbps, derived by hand from `canaan_dsi_clk_cfg()`

2026-09-22, task 1.3 of `the-screen-lights-before-linux`. U-Boot's logo
path takes the PHY PLL as a per-panel `{n, m, voc, hs_freq}` table
(`display_logo.h:430-436`) where Linux derives `m`, `n` and `voc` from
the pixel clock at runtime. Stage 1 must drive the panel at the same mode
as Linux, so here are the numbers Linux actually uses, worked through the
driver's own arithmetic. Source: `drivers/gpu/drm/canaan/canaan_dsi.c:316-383`
in the pinned tree (`nix/kernel-src.nix`,
`ruyisdk/linux-xuantie-kernel @ 7d4e1f44`), unpatched line numbers.

## The arithmetic, for `clock = 49500` kHz and `lanes = 2`

| line | expression | value |
| --- | --- | --- |
| 323 | `div = DIV64_U64_ROUND_CLOSEST(594000, 49500)` | 12 (exact) |
| 324 | `clk_freq = 594000 / div` | 49 500 kHz |
| 325 | `phy_clk_freq = clk_freq * 3 * 8 / lanes / 2` | 49500·24/2/2 = **297 000 kHz** |
| 326-347 | ladder: `297000 < 330000` | **`voc = 0x17`** |
| 349 | `voc_freq = phy_clk_freq << (voc >> 4)` = 297000·2 | 594 000 kHz |
| 350-352 | `cmp = voc_freq * 1000 / 24` | 24 750 000 |
| 353-367 | for `i` in 1..16: `val = (cmp·i + 500000) / 1000000`, `diff = \|cmp − val·10⁶/i\|` | i=1: val 25, diff 250 000; i=2: 50, 250 000; i=3: 74, 83 334; **i=4: 99, diff 0 → break** |
| — | result | **`m = 99`, `n = 4`** |
| 370-374 | `phy_freq = 24000 · 2 · m / n / 2^(voc>>4)` = 24000·198/4/2 | 594 000 kHz |
| 376-380 | pixel-clock divider: `(div − 1) << 3` into `0x91100078` | 11 |
| 383 | `k230_dsi_config_4lan_phy(dsi, m − 2, n − 1, voc, hsfreqrange)` | **`(97, 3, 0x17, 0x87)`** |

`m − 2` and `n − 1` are the register encodings: `canaan_phy.c:73-75` writes
them as `M = m + 2` into `TXDPHY_PLL_CFG0[26:17]` and `N = n + 1` into
`[30:27]`; U-Boot's `display_logo.c:757-760` is the same code. So a U-Boot
connector table carries the *encoded* values, which is why LILYGO's entry
reads `{4, 97, …}` for a PLL whose real `M/N` is 99/5.

The transcription of the function in Python integer arithmetic that these
rows were checked against reproduces the boot log's line exactly:
`phy_clk_freq * 2 = 594000` kbps and `voc = 0x17` are what
`docs/evidence/boot-from-source-cold.txt` line 315 prints —
`canaan-mipi-dsi 90850000.dsi: DSI PHY: lane 594000 kbps, voc 0x17,
hsfreqrange 0x87`. The same transcription run at 39 600 kHz gives
`m = 99, n = 5 → (97, 4)`, matching both LILYGO's table and the earlier
hand-derivation in `docs/research/linux-on-t-display-k230.md` §3.

## The table

`{n, m, voc, hs_freq}` in U-Boot's table order, encoded as the PHY takes
them. VCO = 24 MHz · 2 · M / N; PHY clock = VCO / 2^(voc>>4); lane rate =
2 · PHY clock.

| entry | pclk | `{n, m, voc, hs_freq}` | real M/N | VCO | PHY clk | lane rate | where |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **this system, derived** | 49.5 MHz | **`{3, 97, 0x17, 0x87}`** | 99/4 | 1188 MHz | 297 MHz | **594 Mbps** | this section; `hs_freq` measured above |
| LILYGO RM69A10 (U-Boot table, and RT-Smart) | 39.6 MHz | `{4, 97, 0x19, 0x96}` | 99/5 | 950.4 MHz | 237.6 MHz | 475.2 Mbps | `docs/evidence/lilygo-uboot-logo.md`, `k230_logo.c` |
| SDK ST7701 480x800 (the `#else` default) | 39.6 MHz | `{9, 196, 0x17, 0xa3}` | 198/10 | 950.4 MHz | 237.6 MHz | 475.2 Mbps | SDK `k230_logo.c:259-260` |
| SDK ILI9881 (4 lanes) | 74.25 MHz | `{15, 295, 0x17, 0x96}` | 297/16 | 891 MHz | 222.75 MHz | 445.5 Mbps | SDK `k230_logo.c:244-245` |
| Linux, what it would compute for 39.6 MHz | 39.6 MHz | `{4, 97, 0x17, 0x96}` | 99/5 | 950.4 MHz | 237.6 MHz | 475.2 Mbps | same arithmetic, `i = 5` |

Three things the table makes visible:

1. **`m` does not change between LILYGO's mode and ours; only `n` does.**
   49.5/39.6 = 5/4, and the VCO ladder keeps `voc = 0x17` (PHY clock in
   220..330 MHz) for both, so the same M = 99 with N = 4 instead of 5 is the
   whole PLL change. The pixel-clock divider (`pixclk_div`, written `div <<
   3`) goes from 14 to 11.
2. **The SDK's ST7701 entry and the Linux computation are the same PLL
   frequency in two encodings** (198/10 = 99/5). The driver's search picks
   the smallest `n` with zero error; the SDK's author picked a larger one.
   Neither is "more right".
3. **`voc`: LILYGO's `0x19` versus the ladder's `0x17`.** The upper nibble
   (the post-divider, `voc >> 4`) is 1 in both; only the low nibble differs,
   and `docs/research/linux-on-t-display-k230.md` §3 could find no
   documentation for what it selects. This system has booted with `0x17` at
   594 Mbps on every capture since the panel lit, so `0x17` is the grounded
   value and the one stage 1 should use; `0x19` is LILYGO's and has only
   been seen at 475 Mbps.

`hs_freq` is the one column no arithmetic produces: `0x87` is in the table
because it was measured (the section above), and it goes into stage 1's
table for the same reason it went into the device tree.

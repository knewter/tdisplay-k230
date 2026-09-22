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

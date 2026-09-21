# The 25% DSI burst headroom blanked the panel

2026-09-21. Commit `e3a9c8a` multiplied the DSI PHY bit clock by 5/4 in
`canaan_dsi_clk_cfg()` to give a burst-mode link some slack. It was built
into the image written at 17:12 and **never visually confirmed**. It
blanks the panel completely.

## How it was found

The panel had been lit and photographed (`panel-lit.md`). It went dark and
stayed dark across reboots and a full power cycle. Ruled out, each by
measurement on the board rather than by reasoning:

| hypothesis | test | result |
| --- | --- | --- |
| framebuffer is all zeroes | wrote 1.4 MB `/dev/urandom`, then all-`0xFF`, to `/dev/fb0` | still black |
| the pushed touch DTB broke it | decompiled both DTBs and diffed | only `interrupts` type + `touchscreen-size-*` differ; **zero** display deltas |
| ...still the DTB | pushed the image's original DTB back, rebooted | still black |
| console blanking (`consoleblank`, default 600 s) | black 35 s after a cold boot | not blanking |
| panel power / reset GPIO | `/sys/kernel/debug/gpio` | `dsi_reset` hi, `backlight_gpio` hi |
| display power domain off | `pm_genpd_summary` | `disp_domain on`, subsystem `active` |
| display clocks gated | `clk_summary` | all `disp_*` enabled |
| panel latched in a bad state | user power-cycled the board | still black |

Every status bit the driver exposes said the display was on. DRM reported
`connected` / `enabled` / `dpms On`. That is the same trap as
`panel-dark.md` and `dsi-phy-hang.md`: **a driver's own opinion of itself
is not evidence.**

What broke the tie was the persistent journal. `journalctl --list-boots`
held all four boots of this card, and the display lines are byte-identical
in every one of them -- including the first. So this card has *never* lit
the panel, which dates the regression to the image, not to anything done
at runtime. The only kernel-affecting commit between the last lit image
and this one is `e3a9c8a`.

## The confirming experiment

The headroom is a kernel patch, so it cannot be pushed over serial. But
the PHY clock is derived from the DTB's pixel clock:

```
phy_clk_freq = pclk * 3 * 8 / lanes / 2   = pclk * 6      (2 lanes, 24bpp)
phy_clk_freq = phy_clk_freq * 5 / 4                       (e3a9c8a)
```

so scaling `clock-frequency` down by 4/5 cancels the patch exactly.
`fdtput` on the DTB, pushed with `tools/push-file.py`:

| pclk | PHY bit clock | panel |
| --- | --- | --- |
| 49 500 000 (shipped) | 371.25 MHz | black |
| 31 680 000 | **237.6 MHz** -- the rate that was lit | **lights, console legible** |

Photograph: `panel-photos/06-sheared-console-31.68mhz.jpg`.

## Why it fails

At 31.68 MHz the panel lights but every scanline is sheared progressively
to the right, drawing diagonal bands across the frame, and the image
ripples. That is a line-length mismatch: the panel is clocked for one
number of bytes per line and fed another.

The VO's pixel timing and the DSI byte clock are **not independent** in
this driver. Nothing recomputes the video-mode timing registers when the
PHY clock moves, so scaling the PHY alone desynchronises them. This also
means no DTB value can work around the patch -- any `clock-frequency`
leaves the two clocks off by exactly the same 5/4.

The fix is to drop the patch, which restores `pclk * 6` and the LILYGO
52 Hz timings from `6978dde` -- the last state seen working.

## What is still open

The flicker that motivated the patch is real and unfixed: stripe jitter
-9..+1 px with no monotonic drift over 30 s, and 19 irregular brightness
dips in 30 s, one to 53% of mean. Whatever addresses it has to move the
VO timing and the DSI byte clock **together**.

## Postscript: it also moved the VCO bucket

Reading the source the corrected kernel was actually built from
(`30kiycz38bv840qdzdzzjyvniyh5camf-linux-xuantie-k230-src`,
`canaan_dsi.c:366`), `phy_clk_freq` is in **kHz** and immediately feeds a
ladder of range comparisons that select `voc`:

```c
phy_clk_freq = dsi->clk_freq * 3 * 8 / device->lanes / 2;
if (phy_clk_freq > 1250000 || phy_clk_freq < 40000) ...
else if (phy_clk_freq < 55000)  ...
...
else if (phy_clk_freq < 330000) ...
else if (phy_clk_freq < 440000) ...
```

297 000 kHz lands in the `< 330000` bucket. 371 250 kHz lands in the
`< 440000` bucket. So the patch did not merely raise the bit clock, it
silently reprogrammed the PHY's VCO range as well. The original commit
message called that out as "intended -- the bucket is chosen from the PHY
frequency, so it should follow it." It follows the PHY frequency
correctly and still breaks, because nothing moved the VO's pixel timing
to match.

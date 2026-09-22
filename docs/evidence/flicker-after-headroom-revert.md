# Flicker after the burst-headroom revert

2026-09-21, measured on the corrected image (`a96ca99`, headroom patch
removed, 49.5 MHz pixel clock, LILYGO 52.19 Hz timings). Panel lit, no
shear. 30 s of webcam video at 30 fps, **manual exposure** (`auto_exposure=1`,
`exposure_time_absolute=200`) so brightness numbers mean something.

## Brightness: largely fixed

| | before (25% headroom era baseline) | now |
| --- | --- | --- |
| dips below 85% of mean | 19 in 30 s, worst to **53%** | **0** |
| dips below 90% of mean | -- | **0** |
| dips below 95% of mean | -- | 2 in 30 s |
| min / max vs mean | -- | 95% / 102%, std 1.66 |

The user's report, "brightness flickers sometimes", matches 2 events in
30 s. This is the single clearest improvement.

## Vertical motion: real, magnitude ~3 panel rows, mechanism NOT established

There is residual vertical movement; the user sees it directly and
describes the bands as moving "up and down in unison", with no tearing.
Scale is roughly 3 panel rows out of 1232 (~0.25%).

**What I could not establish, and why.** Apparent displacement measured
in camera pixels grows steeply toward the bottom of the frame -- 0.67 px
std at the top to 6.28 px at the bottom, 9.3x, R^2 = 0.97 after removing
slow brightness variation. That looks exactly like timing error
accumulating down the frame from a vsync anchor.

It is not safe to conclude that. The board is photographed at a steep
oblique angle, and registering the known pattern against the image gives
a perspective magnification of **5.6x** across the same strip, in the
same direction. A perfectly uniform shift would therefore *also* appear
to grow toward the bottom. 5.6x against 9.3x is the same order, the
pattern-registration correlation is only 0.44, and once local scale is
divided out the remaining trend is not significant (R^2 = 0.13).

So the honest state is: uniform whole-frame shift and
accumulate-down-the-frame are **not distinguished** by this footage. The
direct observation of unison motion favours the uniform explanation.

## Methodology notes, because two earlier attempts were wrong

1. **A periodic stripe pattern cannot measure this.** With 16-row bands,
   cross-correlation aliases onto the neighbouring stripe and FFT phase
   is only defined modulo one period. A measured "step" of exactly 16
   panel rows -- precisely one period -- is indistinguishable from an
   unwrap artifact. Both of the first two analyses produced numbers that
   looked meaningful and were not.
2. The pattern must be **aperiodic**. `barcode.fb` is 137 bands of
   random 4..14 rows from a fixed seed (20260921), so the correlation
   peak is unique and reproducible across runs.
3. Auto-exposure must be off, or the camera's own gain control is
   measured instead of the panel.

## What would settle it

Photograph the panel **perpendicular**, not obliquely. That removes the
perspective term entirely, at which point the camera-pixel gradient
means what it appears to mean. Until then the accumulation hypothesis is
unsupported rather than disproven.

## Deskewing: first attempt was botched by inverting near and far

Four fiducial squares were drawn at known panel coordinates (cols
80/488, rows 120/1112) to fit a homography and warp every frame into
true panel space. Two things went wrong, both mine.

**Blob detection locked onto the worktop.** Specular highlights on the
bright table passed the size and squareness filters, and the first
rectified frame was a neatly warped picture of the table. Fixed with a
dark-surround test: a real fiducial sits on black panel, so the ring
around it must be much darker than the blob.

**Near and far were inverted.** The camera looks at the panel from the
TOP of the device; the USB cable, visible in frame, is at the BOTTOM.
So panel row 0 is NEAREST the camera and row 1232 is furthest. I had it
backwards, drew the near fiducials large (116 px) and the far ones small
(36 px), and so compensated the wrong end -- which is why the far pair
was never detected.

Measured correctly from that same footage:

| panel end | drawn | rendered | scale |
| --- | --- | --- | --- |
| row 120, near | 116 px | ~122 px | 1.05 camera px per panel px |
| row 1112, far | 36 px | ~14 px | 0.39 camera px per panel px |

The magnification ratio is therefore about **2.7x**, not the 30x a first
pass suggested by comparing rendered sizes without accounting for the
different drawn sizes. At the far end one camera pixel spans ~2.6 panel
rows, so the ~3 row motion subtends a bit over 1 px: marginal but
measurable. Rectification is viable; it needs the fiducial sizes
compensated the correct way round.

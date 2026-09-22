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

## Why the oblique footage cannot be rescued computationally

Deskewing was tried properly before concluding this, because
"just unskew it" is the obvious objection and it is usually right.

Four fiducial squares were drawn at known panel coordinates
(cols 80/488, rows 120/1112) so a homography could be fitted and every
frame warped into true panel space. Detection needed a dark-surround
test to stop it locking onto specular highlights on the worktop, which
it initially did -- the first rectified frame was a warped picture of
the table.

With that fixed, only the two NEAR fiducials are ever found. The reason
is visible in `panel-photos/`: the far squares were drawn **116 panel px**
and the near ones **36**, and on the sensor the far ones are ~14 px while
the near ones are ~130. That is a magnification ratio near **30x**, not
the ~3.5x assumed. The panel is viewed at a grazing angle.

At the far end one camera pixel therefore covers roughly 10 panel rows,
so the ~3 row motion under investigation subtends about 0.3 px -- below
the noise floor. A homography redistributes resolution, it does not
create it, so no rectification recovers the far half of the panel from
this footage. This also explains the earlier failures: pattern
registration plateaued at corr 0.39 whether the model was linear,
quadratic or projective.

The limitation is the viewing geometry, not the analysis. A camera
looking square at the panel fixes it outright; the same 4-fiducial
homography then works and the top-versus-bottom question becomes
directly measurable.

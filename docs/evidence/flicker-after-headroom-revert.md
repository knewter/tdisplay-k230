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

## Vertical motion: a uniform whole-frame shift, ~2.8 panel rows

**Settled by rectification.** Four fiducials at known panel coordinates
give a homography; fitted ONCE from median positions over 900 frames and
applied fixed to every frame, so it corrects geometry without absorbing
the motion being measured. Displacement is then in real panel rows.

| region | std | span |
| --- | --- | --- |
| near half, panel rows 240..620 | 2.76 rows | 26.5 |
| far half, panel rows 620..1000 | 2.76 rows | 27.2 |

Ratio **1.00**, correlation between halves **0.959**, mean absolute
difference 1.26 rows. The two halves move together by the same amount.

**Therefore: a uniform whole-frame vertical shift.** Not accumulation
down the frame, not tearing, not shear. The whole image is placed at a
slightly different vertical offset from frame to frame, by about 2.8
rows RMS out of 1232 (0.2%), occasionally up to ~27 rows peak-to-peak.
This matches the direct observation of the bands moving "in unison".

Brightness over the rectified panel area is flat: min 95%, max 101% of
mean, std 0.68.

### Hypothesis for the mechanism, not yet tested

A frame-level offset that varies while line timing stays consistent
points at frame start timing rather than pixel or line timing. The init
sequence issues `35 00` (SET_TEAR_ON), but nothing in the driver
consumes the TE signal, so if the panel is refreshing from its own GRAM
on its own oscillator, the phase between our frame writes and its scan
is free to walk. That is precisely a uniform positional offset that
varies per frame.

Untested. Distinguishing it needs either TE wired into the VO or a
deliberate change of frame rate to see whether the jitter tracks it.

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

## What settled it

Not a better camera position -- a homography. The panel need not be
photographed square-on if four points of known panel coordinates are
visible, because the rectification can be computed. The requirement is
that the fiducials be **sized for their own end** of the panel: the
camera views the device from its top edge, so panel row 0 is nearest and
row 1232 furthest, at roughly 1.05 against 0.39 camera px per panel px.
Drawing the far ones ~2.7x larger makes all four detectable at once.

Fit the homography ONCE, from median fiducial positions across the whole
recording, and apply it fixed. Re-fitting per frame would let the
fiducials -- which are themselves on the moving display -- absorb the
motion and report zero.

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

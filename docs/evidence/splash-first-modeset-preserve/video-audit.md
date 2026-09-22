# Video audit: preserved first owner to Sway

This audit covers [`20260922T225553Z-preserved-first-owner-to-sway.mp4`](20260922T225553Z-preserved-first-owner-to-sway.mp4), SHA-256
`b914704003bd4f7f2fef7e6293888a90bbd9cf72549c5b323c73e23f6788b59c`.
`ffprobe` reports H.264, 1920x1080, 30/1 fps, and 65.000 seconds. The
capture manifest is [`20260922T225553Z-preserved-first-owner-to-sway.json`](20260922T225553Z-preserved-first-owner-to-sway.json).

## Review method

I reviewed the video at 1 fps for the full scene, and inspected every
source frame at 30 fps from video 2.00 through 16.00 s (420 frames, using
seven sequential two-second contact sheets). I also inspected all 18 source
frames from 22.45 through 23.05 s at 30 fps for the owner-to-Sway transition.
The input was never re-encoded for these observations. Representative
commands were:

```sh
ffmpeg -ss 2 -t 2 -i 20260922T225553Z-preserved-first-owner-to-sway.mp4 \
  -vf 'fps=30,scale=240:-1,tile=10x6' -frames:v 1 owner-2s.jpg
ffmpeg -ss 20.8 -t 1.2 -i 20260922T225553Z-preserved-first-owner-to-sway.mp4 \
  -vf 'fps=30,scale=320:-1,tile=10x4' -frames:v 1 takeover.jpg
ffmpeg -ss 22.45 -t 0.60 -i 20260922T225553Z-preserved-first-owner-to-sway.mp4 \
  -vf 'fps=30,scale=480:-1,tile=18x1' -frames:v 1 handoff-all-18.jpg
```

The two representative frames are [`preserved-owner-logo.png`](preserved-owner-logo.png)
(SHA-256 `8d32feee01660f8828efb7fb638ca9544fee143d5da836b661089543131f53ac`)
and [`preserved-sway-shell.png`](preserved-sway-shell.png)
(SHA-256 `cf1b9a2acb27341bed769554ddd762f79057d31e85e5205c379dfc9d7b7f2203`).

## Observed result

The physical panel shows the K230 logo throughout the early owner interval.
Across the complete 2.00–16.00 s frame review, the logo remains visible in
every frame; this includes the interval where the owner command begins (about
video 4 s). In the complete 22.45–23.05 s handoff sequence, the last clearly
logo-only frame is about 22.82 s and the first shell bar is visible at about
22.85 s. The visible transition is therefore bounded to approximately
22.82–22.85 s in the camera timeline. No
sampled frame in the reviewed owner or handoff intervals is a dark panel;
the transition appears directly from the logo to the blue shell bar. The
shell remains visible in later samples, including the representative frame
above.

This is consistent with the separate software transcript in
[`sway-inspection.txt`](sway-inspection.txt): the owner reports scanout fb49
as RG16 (lines 9–10), retains it when DRM master is dropped (lines 11–12),
and releases it after the successor replaces it (lines 13–14). Sway then
reports seeding and removing its initial splash (lines 16–17). Those logs
establish the intended owner/release ordering; they do not measure panel
pixels.

The timing is camera-relative and approximate. The camera is oblique and has
reflections/glare, so this review does not establish calibrated geometry or
color, uninterrupted electrical scanout between frames, or the absence of a
sub-frame blackout. The trial was manually/serial started on an already booted
system with alternate units; it is not evidence of a cold/battery boot,
real-finger input, or power-cycle behavior.

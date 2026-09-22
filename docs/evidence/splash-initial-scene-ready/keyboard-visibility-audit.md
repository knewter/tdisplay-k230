# Physical keyboard visibility audit

Source: [20260922T224622Z-keyboard-visible-focus30.mp4](20260922T224622Z-keyboard-visible-focus30.mp4)

SHA-256: `d411b25e783eae3d63736a1bca1acf3c8f6e5c5479c035173134e90d615e7406`

`ffprobe` reports H.264, 1920x1080, 30/1 fps, and 30.000 s. The capture
manifest records a C920 focus-30/manual-exposure setup, serial `USR2` to show
the unchanged default keyboard and `USR1` to hide it, with injected
interaction provenance. It does not claim real touch or calibrated geometry.

## Method

I reviewed the full recording at 1-second cadence and extracted one frame from
the shown interval and one from the hidden interval:

```sh
ffmpeg -y -hide_banner -loglevel error \
  -i docs/evidence/splash-initial-scene-ready/20260922T224622Z-keyboard-visible-focus30.mp4 \
  -vf 'fps=1,scale=480:-1,tile=5x6' -frames:v 1 /tmp/kbvis/all.jpg
ffmpeg -y -hide_banner -loglevel error -ss 8 \
  -i docs/evidence/splash-initial-scene-ready/20260922T224622Z-keyboard-visible-focus30.mp4 \
  -frames:v 1 -vf scale=960:-1 keyboard-visible-shown.png
ffmpeg -y -hide_banner -loglevel error -ss 26 \
  -i docs/evidence/splash-initial-scene-ready/20260922T224622Z-keyboard-visible-focus30.mp4 \
  -frames:v 1 -vf scale=960:-1 keyboard-visible-hidden.png
```

## Result

The shown frame at approximately 8 s,
[keyboard-visible-shown.png](keyboard-visible-shown.png), SHA-256
`69b610fa9249b2b6fcd89235641829e83a63687cab97d5e7f73806e322013741`, shows
a distinct faint grid of illuminated keyboard keys across the lower part of
the physical panel. The hidden frame at approximately 26 s,
[keyboard-visible-hidden.png](keyboard-visible-hidden.png), SHA-256
`0fd988037536dd0b6d21f9e1abfab558fe913cbcc666f74ce83bd363a85c9bcb`, shows
that lower region dark while the shell bar and terminal remain visible.

This establishes camera-visible keyboard presence and removal for the
initial-scene diagnostic boot, supporting the visibility portion of splash
task 5a.3. The labels and individual key boundaries are not readable in this
oblique reflective recording. It therefore says nothing about touch accuracy,
coordinate calibration, complete keyboard geometry, real-finger input, or
the separate shell task 5.1 acceptance.

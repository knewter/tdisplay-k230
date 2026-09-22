# Camera timing audit: panel-ready initial-scene boot

Source: [20260922T222835Z-initial-scene-panel-ready-boot.mp4](20260922T222835Z-initial-scene-panel-ready-boot.mp4)

SHA-256: `c2d6856150e7ffab2d38ad8766689ec4f2459c75c50b99b01f08c14b0201f8ef`

`ffprobe` reports H.264, 1920x1080, 30/1 fps, and 120.000 s. Build and
runtime provenance are recorded in [build.txt](build.txt),
[integration-build.txt](integration-build.txt), and [inspection.txt](inspection.txt).
The inspection log reports the compositor seed and removal messages with
`commit_seq=6`; those logs are not used here as proof of physical display
continuity.

## Method

I reviewed the full recording at 5-second cadence:

```sh
ffmpeg -y -hide_banner -loglevel error \
  -i docs/evidence/splash-initial-scene-ready/20260922T222835Z-initial-scene-panel-ready-boot.mp4 \
  -vf 'fps=1/5,scale=480:-1,tile=5x5' -frames:v 1 /tmp/ready-audit/broad.jpg
```

The handoff was sampled at 5 fps over 68.0–77.8 s, 10 fps over 72.0–73.9 s,
and 10 fps over 72.5–73.4 s:

```sh
ffmpeg -y -hide_banner -loglevel error -ss 68 -t 10 \
  -i docs/evidence/splash-initial-scene-ready/20260922T222835Z-initial-scene-panel-ready-boot.mp4 \
  -vf 'fps=5,scale=320:-1,tile=10x5' -frames:v 1 /tmp/ready-audit/transition.jpg
ffmpeg -y -hide_banner -loglevel error -ss 72 -t 2 \
  -i docs/evidence/splash-initial-scene-ready/20260922T222835Z-initial-scene-panel-ready-boot.mp4 \
  -vf 'fps=10,scale=480:-1,tile=10x2' -frames:v 1 /tmp/ready-audit/fine.jpg
ffmpeg -y -hide_banner -loglevel error -ss 72.5 -t 1 \
  -i docs/evidence/splash-initial-scene-ready/20260922T222835Z-initial-scene-panel-ready-boot.mp4 \
  -vf 'fps=10,scale=960:-1' -frames:v 1 panel-ready-transition.png
ffmpeg -y -hide_banner -loglevel error -ss 88 -t 1 \
  -i docs/evidence/splash-initial-scene-ready/20260922T222835Z-initial-scene-panel-ready-boot.mp4 \
  -vf 'fps=1,scale=960:-1' -frames:v 1 panel-ready-shell.png
```

## Observations

The initial K230 scene remains visible in the broad samples through about
72.5 s. In the dense sequence, the logo is visible at approximately 72.5
and 72.6 s; the first shell top-bar pixels appear around 72.7 s, with the
shell clearly established by about 72.8–72.9 s. No dark camera frame was
observed around this handoff. The camera therefore brackets the visible
change at roughly 72.6–72.7 s and again does not reproduce the earlier
1.1–1.2 s dark interval from the first preserve-image trial.

The handoff still has camera-frame limits: it cannot exclude a sub-frame or
exposure transition and does not prove uninterrupted electrical scanout. The
physical panel is oblique and reflective. The extracted
[initial-scene frame](panel-ready-transition.png) (SHA-256
`15d4fdc1a82bae8c09d97218ba0ff9484480e969dd65d757e648342b5e8804a6`) shows
the lower-panel K230 scene; [shell frame](panel-ready-shell.png) (SHA-256
`d093fcf3768834ef40205f558e17832bf22d0404de0451b5430239377ed8690d`) shows
the first Linux portrait shell bar and terminal.

The shell is visibly in the expected portrait orientation, without an
obvious horizontal wrap or magenta color swap in these frames. This is a
visual observation rather than calibrated geometry or color evidence. It
does not establish battery-only boot, real-finger input, or that the result
generalizes beyond this captured boot; the runtime seed/remove log and the
camera recording are evidence from the same trial, not independent proof of
physical continuity.

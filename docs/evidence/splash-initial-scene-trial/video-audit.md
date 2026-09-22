# Camera timing audit: initial Sway scene trial

Source: [20260922T221824Z-initial-scene-automatic-boot.mp4](20260922T221824Z-initial-scene-automatic-boot.mp4)

SHA-256: `a675bf43671b9c099e6fe33c436d0f955c8d95a729f414ace8d75dc1d5b2dafd`

`ffprobe` reports H.264, 1920x1080, 30/1 fps, and 120.000 s. The source
image/build provenance is recorded in [build.txt](build.txt), including source
`06cd7a854e0f4287b83425007acc836c28225c16` and the successful image build.

## Method

I first reviewed the whole recording at 5-second cadence:

```sh
ffmpeg -y -hide_banner -loglevel error \
  -i docs/evidence/splash-initial-scene-trial/20260922T221824Z-initial-scene-automatic-boot.mp4 \
  -vf 'fps=1/5,scale=480:-1,tile=5x5' -frames:v 1 \
  /tmp/initial-audit/broad.jpg
```

I then sampled the transition at 5 fps from 68.0 through 75.8 s, 10 fps
from 70.0 through 73.9 s, and a focused 10 fps sequence from 72.5 through
73.4 s:

```sh
ffmpeg -y -hide_banner -loglevel error -ss 68 -t 8 \
  -i docs/evidence/splash-initial-scene-trial/20260922T221824Z-initial-scene-automatic-boot.mp4 \
  -vf 'fps=5,scale=320:-1,tile=8x5' -frames:v 1 /tmp/initial-audit/transition-68-76.jpg
ffmpeg -y -hide_banner -loglevel error -ss 72.5 -t 1.0 \
  -i docs/evidence/splash-initial-scene-trial/20260922T221824Z-initial-scene-automatic-boot.mp4 \
  -vf 'fps=10,scale=480:-1,tile=10x1' -frames:v 1 /tmp/initial-audit/transition-72.5.jpg
```

## Observations

The initial K230 scene remains visible in the broad samples through 72 s.
The focused sequence shows the logo at approximately 72.5 and 72.6 s, the
first shell top-bar pixels appearing at approximately 72.7 s, and the shell
bar clearly established by approximately 72.8–72.9 s. Thus the camera data
brackets the logo-to-shell change at about 72.6–72.7 s. No dark camera frame
was observed in this dense sample around the handoff, so the earlier
approximately 1.1–1.2 s dark interval was not reproduced in this trial.
This is a camera-frame result: it cannot exclude a sub-frame or exposure
transition and does not prove uninterrupted electrical scanout.

The logo is a lower-panel initial scene; the first Linux image shows the
portrait shell bar at the top. The post-handoff shell is visibly oriented as
the expected portrait layout, with no obvious horizontal wrap or magenta
color swap in this oblique, glare-affected recording. This does not provide
calibrated geometry/color evidence. The trial also does not establish a
cold-boot-only result versus a warm/reused boot state; the capture describes
this particular automatic boot sequence only.

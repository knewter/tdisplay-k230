# Camera audit: initial-scene controls recording

Source: [20260922T223311Z-initial-scene-ready-controls.mp4](20260922T223311Z-initial-scene-ready-controls.mp4)

SHA-256: `b9831514a542c77ac820a2e2fd4a611e817b50e7e3120e21cfeacf7416827420`

`ffprobe` reports H.264, 1920x1080, 30/1 fps, and 65.000 s. The capture
manifest identifies a 30 fps `/dev/video0` camera recording rotated 180° and
labels the control provenance as injected; it makes no real-finger claim.

## Method

I reviewed the complete recording at 1-second cadence and made 2 fps contact
sheets for the keyboard interval and the display-off/recovery interval:

```sh
ffmpeg -y -hide_banner -loglevel error \
  -i docs/evidence/splash-initial-scene-ready/20260922T223311Z-initial-scene-ready-controls.mp4 \
  -vf 'fps=1,scale=320:-1,tile=7x10' -frames:v 1 /tmp/controls-audit/all.jpg
ffmpeg -y -hide_banner -loglevel error -ss 6 -t 20 \
  -i docs/evidence/splash-initial-scene-ready/20260922T223311Z-initial-scene-ready-controls.mp4 \
  -vf 'fps=2,scale=480:-1,tile=5x8' -frames:v 1 /tmp/controls-audit/keyboard.jpg
ffmpeg -y -hide_banner -loglevel error -ss 26 -t 20 \
  -i docs/evidence/splash-initial-scene-ready/20260922T223311Z-initial-scene-ready-controls.mp4 \
  -vf 'fps=2,scale=480:-1,tile=5x8' -frames:v 1 /tmp/controls-audit/dpms-recovery.jpg
```

## Observations

- During the requested keyboard-show interval, approximately 8–22 s, the
  camera continues to show the portrait shell. The physical recording does
  not resolve the keyboard key grid or labels at this distance and angle.
  The native reference [keyboard-native.png](keyboard-native.png), SHA-256
  `cb6db86340520a8a1ec7bf6efa76bc40ce6bca085080982a9237fe6858ecc70e`, shows
  the complete expected keyboard layout, but it is not physical-panel proof.
- The panel is dark in the 2 fps samples covering approximately 29–32 s,
  matching the deliberate display-off interval.
- The shell top bar returns in samples around 32–33 s and remains visible
  through the later recording, including the representative 38 s still
  [controls-recovery-38s.png](controls-recovery-38s.png), SHA-256
  `c0153647eb895d46e5a220986d181389d917fe1e6c808246a44dfd5fe46982b7`.

The camera therefore records visible recovery after the display-off interval.
It does not measure DPMS latency, prove compositor state preservation beyond
the visible result, establish touch accuracy, or distinguish injected input
from real finger input. Glare and the oblique camera angle also prevent a
complete physical keyboard geometry or label-readability claim.

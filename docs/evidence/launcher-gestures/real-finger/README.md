# Real-finger paging and window cards

[The 23-second camera excerpt](gestures.mp4) shows the operator using the
integrated launcher on 2026-09-23 UTC. It is trimmed from 5–28 seconds of a
49.533-second recording and cropped around the device. The operator replied
“done” after the requested sequence. No injected touch ran during this take.
Source/image provenance is the same as the [integrated injected matrix](../integrated-injected/README.md).
[Capture metadata and hashes](capture.json) preserve the transformations.

The requested sequence was left/right paging, upward entry to window cards,
downward return to Apps, another upward entry and a window-card tap, then
Apps → overview → Back. The footage visibly shows paging, Windows cards,
Monitor becoming visible after selection, Apps reopening, and return from the
last overview. The finger crosses and sometimes obscures the contact area;
individual motion directions are corroborated by the instructed sequence and
operator confirmation, not inferred solely from each sampled camera frame.

Within the excerpt, paging occurs near 2–5 seconds, overview navigation near
6.5–12 seconds, Monitor selection near 12.7 seconds, Apps reopening near
17 seconds, and the final overview/return near 19–22 seconds. Timing is
approximate visual annotation, not a touch latency or optical cadence measure.
[The selection still](window-selection.jpg) is a camera frame from the clip.

The crop excludes legs and the adjacent phone. Review found no readable
credentials or private addresses in the excerpt. Monitor displays ordinary
process diagnostics. The perspective remains oblique: headings and state
changes are readable, while the lower screen and small labels are softer,
with a reflection near its bottom edge. This documents a real-finger workflow;
it does not establish uniform sharpness, exact finger coordinates, or the
200 ms transition limit. Native captures and instrumentation provide separate
state/timing evidence. The full sharpness acceptance gate remains open.

Reproduction from the already cropped local source:

```sh
ffmpeg -ss 5 -i source.mp4 -t 23 -an -c:v libx264 -preset veryfast \
  -crf 23 -pix_fmt yuv420p -movflags +faststart gestures.mp4
ffmpeg -ss 12 -i gestures.mp4 -frames:v 1 window-selection.jpg
```

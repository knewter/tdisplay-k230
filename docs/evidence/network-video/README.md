# Integrated video work: presentation measurements

These preliminary runs use the existing persistent-Wi-Fi image and a transferred
source-built mpv. They do not yet prove the new player entry in a freshly built
image. Big Buck Bunny © 2008 Blender Foundation, [CC BY 3.0](https://peach.blender.org/about/).

## Presentation trace

The optional `K230_PRESENTATION_TRACE=1` instrumentation requests a dedicated
`wp_presentation_feedback` for each wlshm video-buffer commit. Each record carries
its own submission serial, mpv VO frame ID and media PTS. Presented/discarded
callbacks resolve that serial. This is independent of mpv's frame-drop counter
and its ordinary frame-throttling callback. It adds protocol and logging work,
so the results are instrumented trials, not a zero-overhead estimate.

Built player: `/nix/store/zd6gv6aaj0w1mxg0h439m9fgc0nwsmzq-mpv-riscv64-unknown-linux-gnu-0.41.0`.
Source pin and patch: `nix/video-probe.nix`, `nix/patches/mpv-k230-presentation-trace.patch`.
The narrow cross-build completed and its closure was transferred over Wi-Fi,
SHA256 checked, then imported by Nix. No image, kernel or compositor change
was needed for these observations.

Both requests use the public
`https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd`, start at 45 seconds,
request 35 seconds, disable audio, use `wlshm`, `sw-fast`, cache enabled and
30 seconds of demuxer readahead, with a 70-second wall-clock termination limit.
Software selects track 6, native H.264 and requests 480×270. MVX selects track
7, `h264_v4l2m2m`, point scaling after `sw-fast`, requests 568×320, and uses the
known-30-fps-only `--correct-pts=no --container-fps-override=30` workaround.
The first software sizing IPC emitted a move/floating error; its requested
geometry must not be treated as a separately verified live window rectangle.
The MVX trial installed a single floating rule for its distinct window title.

| Measurement | Software 480×270 source | MVX 640×360 source |
| --- | ---: | ---: |
| Submitted surface updates | 1,049 | 1,043 |
| Presented distinct VO frames | 1,047 | 1,042 |
| Discarded updates | 2 | 1 |
| Unresolved at log end | 0 | 0 |
| Presentation span | 34.909953 s | 35.002123 s |
| Presentation intervals per second | 29.9628 | 29.7411 |
| Median / p95 interval | 38.320 / 38.324 ms | 38.316 / 57.474 ms |
| Largest interval | 76.640 ms | 76.637 ms |
| Player decoder / output drops | 0 / 1 | 0 / 8 |

Raw logs: [software](software-presentation.log), [MVX](mvx-presentation.log).
Machine-readable analyses: [software](software-presentation.json),
[MVX](mvx-presentation.json). Both logs report normal EOF. Software's teardown
also printed an interrupted HTTP-fetch error; it exited 0, so that message is
not reinterpreted as a failed playback trial or a general network-recovery test.

Reproduce each analysis with:

```sh
python3 tools/analyze-video-presentation.py docs/evidence/network-video/software-presentation.log --require-hardware-completion
python3 tools/analyze-video-presentation.py docs/evidence/network-video/mvx-presentation.log --require-hardware-completion
```

## What the timestamps establish

The compositor declared Linux `CLOCK_MONOTONIC` (1). Every presented event
carried flags 7: VSYNC, HW_CLOCK and HW_COMPLETION, without ZERO_COPY. Sequence
values advanced monotonically within each run. Presentation timestamps followed
the corresponding submission and preceded receipt in the same clock domain.
The trace does not combine counters across resets or treat a sequence value as
a duration. Reported refresh prediction is 19,160,758 ns; this is retained rather
than assuming a 60-Hz panel cadence.

In the pinned kernel, `drivers/gpu/drm/canaan/canaan_crtc.c` arms each pending
flip event with `drm_crtc_arm_vblank_event`; the VO interrupt handler in
`canaan_vo.c` calls `drm_crtc_handle_vblank` when enabled. Thus these records
follow the hardware interrupt/compositor presentation path, not a software
frame-callback estimate. The driver does not check individual interrupt status
bits before calling the vblank handler; an independent optical cadence test
would be stronger evidence of exact panel timing. No photon measurement or
pixel-identical camera-frame count is claimed here.

The [Wayland protocol](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/main/stable/presentation-time/presentation-time.xml)
defines feedback per content submission and distinguishes hardware completion
from a guessed timer. The actual decoded movie remains visually grounded by
[prior native/camera captures](../video-acceleration/README.md); final-image
controls, captures and regression evidence are still pending.

## MVX empty-capture candidate

The [patched FFmpeg trace audit](mvx-patched-trace-audit.md) retains three
300-frame repeats and a 480-frame EOF run for the local empty-capture requeue
candidate. All runs exit successfully and preserve EOF, but the raw trace also
shows duplicated MVX capture timestamps propagated by FFmpeg. The candidate is
therefore diagnostic-only; it is not enabled in the system or used to claim
native timestamp correctness.

The [strict decoder comparison](strict-comparison/README.md) records verified
software/MVX profiles, steady presentation/CPU/cache counters and the separate
MVX seek stall; software remains the default.

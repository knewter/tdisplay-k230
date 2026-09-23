# Video decoding and rendering follow-up

Physical board, 2026-09-22 America/Chicago (2026-09-23 UTC), running the
[persistent Wi-Fi image](../wifi-persistent/README.md). These are temporary
probe packages from `nix/video-probe.nix`, not an installed default video app.
Audio is disabled throughout. Big Buck Bunny © 2008 Blender Foundation,
[CC BY 3.0](https://peach.blender.org/about/).

## Hardware decoder

The [live capability query](v4l2-capabilities.txt) identifies `/dev/video0` as
MVX/Linlon, V4L2 memory-to-memory, with H.264 compressed input and raw YUV
output. Listing other formats is not proof that those codecs work. The small
query binary was first built against a different cross-libc path; invoking it
with the board's installed compatible loader resolved that host-build mismatch.

The rebuilt FFmpeg enables `withV4l2M2m = true` and `h264_v4l2m2m` explicitly.
The decoder flag is `-c:v h264_v4l2m2m`; mpv selects it with
`--vd=h264_v4l2m2m`. `--hwdec=no` in the trial disables mpv's separate automatic
hwaccel negotiation; it does not override this explicit V4L2 decoder selection.
Logs confirm the selected decoder opens `/dev/video0` using driver `mvx`.

Packages:

- mpv: `/nix/store/dpylynz13fl5kmkfksnvwgv9arqy0hpr-mpv-riscv64-unknown-linux-gnu-0.41.0`
- FFmpeg: `/nix/store/vr4r48cj2wlbzsqmkvgp35chngjidk3z-ffmpeg-riscv64-unknown-linux-gnu-9.0.1-bin`

The driver already includes vendor codec microcode in the kernel. See the
[source and firmware audit](../mvx-v4l2-audit.md); this is not a blob-free path
or evidence of GPU rendering.

## Decode-only comparison

A local fragmented-MP4 sample concatenated the initialization segment and
segments 12–15 of `bbb_30fps_640x360_1000k` from
`https://dash.akamaized.net/akamai/bbb_30fps/`. It contains the same public BBB
representation used for the network trial. Local input removes network time;
null output removes scaling and display. Each invocation stopped at 300 output
frames, with `-debug_ts -benchmark`, no input seek, and no duration-based stop.
These are single bounded observations, not statistical benchmark estimates.

| Decoder | Output frames | Wall time | User + system CPU time | Reported rate |
| --- | ---: | ---: | ---: | ---: |
| [Software H.264](software-decode-300.txt) | 300 | 3.873 s | 3.626 s | 77 fps |
| [MVX H.264](mvx-decode-300.txt) | 300 | 1.259 s | 0.469 s | 239 fps |

Both completed successfully with zero reported decode errors. Those rates
measure decode to a null sink, not on-screen frame rate.

MVX's timestamps are not yet trustworthy: the [captured sequence](mvx-pts.txt)
starts with repeated zeros, whereas software starts 0,1,2,3,4 at time base 1/30.
The excerpt contains 292 parseable timestamps and is not a complete frame-index
map. The hardware run reports 9.33 s for 300 frames, versus 10.00 s in software.
This limits seeking, variable-frame-rate playback, and audio synchronization.
No speculative driver patch or general timestamp repair was applied.

For the known 30-fps, silent BBB experiment only, mpv can generate timing with
`--correct-pts=no --container-fps-override=30`. That is a scoped workaround,
not acceptance of MVX timestamps for arbitrary media.

## Streaming and window size

The original public remote MPD is
`https://dash.akamaized.net/akamai/bbb_30fps/bbb_30fps.mpd`.
All following runs request the same 30 seconds, starting at 45 seconds, with
`--cache=yes --demuxer-readahead-secs=30 --vo=wlshm --profile=sw-fast`.
A Sway rule makes the `k230-video-probe` window floating and borderless at the
specified size. `--geometry` alone does not constrain a tiled Sway window.

| Trial | Source / output | Decoder | Decoder / VO drops |
| --- | --- | --- | ---: |
| [Software, video-sized window](software-270p-window.txt) | 480×270 / 480×270 | native H.264 | 0 / 0 |
| [MVX, fixed 30-fps timing](mvx-360p-cfr.txt) | 640×360 / 568×320 | MVX | 0 / 134 |
| [Same, internal vsync disabled](mvx-360p-no-vsync.txt) | 640×360 / 568×320 | MVX | 0 / 138 |
| [MVX, point scaling, internal vsync auto](mvx-360p-point.txt) | 640×360 / 568×320 | MVX | 0 / 0 |

The 270p result improves on the earlier 106-drop tiled-window observation.
Window size and explicit cache settings changed together, so this is a usable
configuration comparison, not an isolated attribution of all improvement to
one flag. Network buffers stayed ahead in the original-URL trials.

An intermediate experiment used a filtered MPD stored locally. Both native and
MVX runs kept only about one second of cache and advanced in bursts. Their
zero-drop counters are excluded from acceptance; they do not establish smooth
playback. A first seek/duration-limited FFmpeg DASH trial was also discarded as
a throughput benchmark in favor of the fixed-frame local comparison above.

The software baseline uses an unscaled YUV-to-BGRA converter. The 360p output
still uses CPU bilinear scaling; neither the VPU nor the KPU accelerates this
Wayland SHM rendering path. Counters describe player behavior, not a measured
panel scanout cadence. Physical/native captures and a presentation-timing
acceptance remain separate evidence layers in the video proposal.

The decisive 360p setting was `--sws-scaler=point`, placed **after**
`--profile=sw-fast` so that the profile does not overwrite it with bilinear.
The first attempt put it before the profile and still logged bilinear; that
attempt is not a point-scaler result. The corrected log explicitly records
nearest-neighbor/point scaling. This trades interpolation quality for speed.

`tools/play-bbb-probe.sh` preserves two bounded recipes: `software` for
unscaled 270p with native timing, and `mvx` for 360p with point scaling and the
known-CFR timing override. Run it as the shell user with the built mpv path and
its Wayland/Sway environment. It runs the public 30-second test, with audio off.

## Compositor versus 2.5D GPU

Sway currently forces the CPU Pixman renderer. That is not evidence that the
chip lacks graphics acceleration: [the live GPU preflight](gpu-preflight.txt)
records `CONFIG_GPU_VGLITE=y` and a root-only `/dev/vg_lite` device. DRM exposes
`card0` but no render node. The VG-Lite 2.5D engine is a different integration
path from a Mesa/OpenGL renderer; it is not used by the current shell or these
wlshm playback tests. An offscreen blit/scale test and integration audit are
separate from the proven VPU decode result above.

## Captured repeat

The same 360p/point/CFR configuration was repeated while taking a compositor
screenshot and a host-camera recording. This [captured run](mvx-360p-capture.txt)
reported 0 decoder and 2 video-output drops, versus 0/0 in the earlier run.
The screenshot adds work on the board; this record does not isolate whether
that caused the two drops. Both outcomes are retained.

[Native screenshot](360p-native.png), [four-second physical clip](360p-physical.mp4)
and [camera still](360p-physical.jpg) show the actual decoded movie. The camera
crop excludes the surrounding body/desk scene; [provenance](capture.json)
records its coordinates, timing, source hash and autofocus setting. It is an
oblique hand-held camera view, not a panel frame-rate measurement. The source
recording remains private on the host; only selected derivatives are published.

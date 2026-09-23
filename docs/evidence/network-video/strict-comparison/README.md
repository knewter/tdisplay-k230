# Strict decoder profiles: steady playback and seek limitation

Physical board, 2026-09-23, boot `506e9b30-5617-4ecf-9c88-95e50dd5113e`.
Controller source `7984a58`, imported wrapper
`/nix/store/krqszp7x14mi9xyyz0k6bp2p3ywvhkyn-k230-video-session`;
installed mpv `/nix/store/zd6gv6aaj0w1mxg0h439m9fgc0nwsmzq-mpv-riscv64-unknown-linux-gnu-0.41.0`.
The board retained its prior system image: these are transferred-controller
measurements, not final-image regression or a new physical-finger trial.

Both profiles opened the public BBB DASH manifest, with audio off and wlshm
output through the existing Sway/Pixman RGB565 panel path. The helper verified
actual process UID/PID/start-time and decoder arguments: `--vd=h264` for software,
`--vd=h264_v4l2m2m,-` for MVX. The latter forbids mpv's internal software fallback;
prior device/format proof is in `docs/evidence/mvx-v4l2-audit.md`, and forced
initialization failure followed by the software profile is in
`../recovery-fixed/README.md`. `hwdec-current=no` refers to mpv's separate hwdec
API and is not a verdict on the explicitly selected V4L2 decoder.

| Observed steady interval | Software | Strict MVX |
| --- | ---: | ---: |
| Representation | track 6, 480x270, 30 fps | track 7, 640x360, 30 fps |
| Output/timing profile | native dimensions and media PTS | point-scaled 568x320, known-CFR 30 fps override |
| Sampling wall time | 35.013 s | 34.999 s |
| Media advancement | 35.033 s | 34.967 s |
| Player process CPU estimate | 54.67% of one CPU | 50.32% of one CPU |
| Decoder drop delta | 0 | 0 |
| Video-output drop delta | 0 | 6 |
| Hardware-signalled surface presentation | 29.994 events/s | 29.835 events/s |
| Presentation interval median / p95 / max | 38.320 / 38.324 / 57.482 ms | 38.320 / 57.476 / 76.644 ms |

`steady-results.json` contains all eight IPC and `/proc` samples per profile,
cache occupancy, RSS, and cleanup. CPU is delta `(utime + stime) / CLK_TCK / wall`;
the board reported `CLK_TCK=100` and page size 4096. It is player-process CPU,
not total CPU including Sway, IRQs, or the controller. No sampled cache pause
occurred. Profiles differ in resolution, scaling, and timestamp workaround;
this is not an equal-work decoder efficiency benchmark.

## Seek/startup is a separate limitation

`initial-results.json` deliberately remains a failure: seeking to 45 seconds
then waiting only two seconds produced an MVX stall and only 29.1 seconds of
media advancement in 35 seconds. Its full presentation trace contains a roughly
7.8-second gap. This is not evidence of seamless seek. Seek is not exposed by
the shipped touch controls.

`steady-check.py` waits until the post-seek position reaches 45 seconds, then
requires a further three seconds of real progression before measuring. The
recorded warm-up was 3.812 seconds for software and 10.810 for MVX. An intermediate
helper iteration mistakenly counted the seek jump itself as progression; it was
rejected and corrected, not treated as steady-playback evidence.

Full `steady-*-presentation.log` traces preserve startup and seek, including the
MVX gap. `summarize.py` selects submissions and matching feedback whose media PTS
lie between the first and last IPC samples; it does not select by frame quality.
The resulting `*-window.log` and analyses cover over 30 seconds in both cases.
This PTS-bounded presentation window approximates the IPC sampling interval; IPC
and `/proc` reads are sequential, not an atomic synchronized snapshot.

Reproduce analysis:

```sh
python3 docs/evidence/network-video/strict-comparison/summarize.py
python3 tools/analyze-video-presentation.py docs/evidence/network-video/strict-comparison/software-window.log --require-hardware-completion
python3 tools/analyze-video-presentation.py docs/evidence/network-video/strict-comparison/mvx-window.log --require-hardware-completion
```

Presentation flags are 7, using declared CLOCK_MONOTONIC feedback. These are
compositor/kernel completion signals, not measured photons; driver provenance
and refresh-event limitations remain those in the parent network-video report.
No optical smoothness or audio claim follows. Software remains the default;
MVX remains a bounded known-30-fps experiment with the measured seek limitation.

Both steady runs passed Stop cleanup of controller state and IPC sockets.
Final-image controls, post-start network-error recovery, and broad timestamp
correctness remain separate from these comparison results. No new image/video
asset is included; the public BBB media attribution remains in the parent report.

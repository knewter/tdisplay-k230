# MVX V4L2 timestamp boundary investigation

This investigates the timestamp limitation recorded in
[`docs/evidence/video-acceleration/mvx-pts.txt`](../evidence/video-acceleration/mvx-pts.txt).
It does not change the driver, firmware, FFmpeg, or the board image.

## Observation and limit

For one local, no-seek, 300-frame H.264 sample, FFmpeg's native decoder
reported frame timestamps `0..299` at time base `1/30`. The MVX run completed
300 frames but the retained extraction contains only 292 parseable output
timestamps: its first eleven are zero, then values ascend through the captured
range, with a duplicate `238` and no captured `239`. The MVX run reported
9.33 seconds, while the native run reported 10.00 seconds.

That is evidence of an output timestamp defect for this run. It is *not* a
complete packet-to-frame map: eight frame lines are absent from the extraction,
and H.264 reordering means that numeric ordering alone cannot identify the
layer that first lost a tag. There is no general timestamp synthesis patch in
this change. Forcing a constant 30-fps clock would break valid variable-rate,
seek, and audio-synchronised inputs.

## The intended path in the pinned sources

The pinned FFmpeg 9.0.1 V4L2 code converts each compressed input packet PTS to
a microsecond `v4l2_buffer.timestamp` before `VIDIOC_QBUF`:

* `libavcodec/v4l2_buffers.c:56-76` selects `pkt_timebase` when present and
  writes the converted value.
* `libavcodec/v4l2_buffers.c:502-515` calls that conversion for an input
  `AVPacket`; `:585-597` submits the buffer.
* After `VIDIOC_DQBUF`, `:441-460` converts the capture buffer timestamp back
  and assigns `AVFrame.pts`.

The pinned K230 MVX driver explicitly asks videobuf2 to preserve submitted
timestamps (`drivers/media/platform/canaan/vpu/mvx_v4l2_vidioc.c:743-751`,
`V4L2_BUF_FLAG_TIMESTAMP_COPY`). It treats the value as a firmware tag:

* `mvx_v4l2_buffer.c:300-317` copies `vb2->timestamp` into
  `mvx_buffer.user_data` on queueing.
* `mvx_firmware_v2.c:1456-1491` writes that field as
  `mve_buffer_bitstream.user_data_tag` for compressed input.
* Firmware frame completion assigns `f->user_data_tag` to the completed MVX
  buffer (`mvx_firmware_v2.c:610-684`), and
  `mvx_v4l2_buffer.c:480-501` returns it as `vb2->timestamp`.

The output-frame buffers themselves also carry a `user_data_tag` when they are
provided to firmware (`mvx_firmware_v2.c:1146-1164`). The host source does not
prove whether the opaque MVX firmware returns the decoded input tag or the
recycled output-buffer tag. That distinction matters: initially queued capture
buffers normally have zero timestamps, which is a plausible source of repeated
zeros, but it remains a hypothesis until the API boundary is measured.

## Read-only boundary probe

`tools/mvx-ioctl-trace.c` builds into a small `LD_PRELOAD` library through
`nix/mvx-ioctl-trace.nix`. With `MVX_IOCTL_TRACE=1`, it logs only V4L2
`VIDIOC_QBUF` and successful `VIDIOC_DQBUF` calls on `/dev/video*`. It records
the queue direction, index, timestamp, flags, payload byte count, and result.
It does not alter a buffer or invoke an ioctl itself.

`MVX_IOCTL_TRACE_DEVICE=/path` is a test-only exact path selector. Without it,
the observer's fixed `/dev/video` filter prevents unrelated application ioctl
traffic from being logged.

The included host fixture builds the library and sends a deliberately invalid
`OUTPUT_MPLANE QBUF` to `/dev/null` through the exact-path selector. It verifies
that the pre-call record carries `index=7`, `timestamp=12.345678`, and
`bytesused=99`, followed by the real `ENOTTY` result. It tests observation and
formatting only; a successful DQBUF requires the board's MVX node. Its second
mode closes stderr before QBUF and verifies that the real `ENOTTY` errno is
still returned, so failed tracing cannot change FFmpeg's ioctl behaviour.

This is intentionally a narrow observer for the current FFmpeg V4L2 call
pattern, whose ioctls carry an argument. It is not a general-purpose `ioctl`
interposer for applications that use no-argument requests.

After transferring its single `.so` to the board, run the existing bounded
local decode with the same FFmpeg binary and add the environment variable:

```sh
MVX_IOCTL_TRACE=1 LD_PRELOAD=/path/libmvx-ioctl-trace.so \
  /nix/store/vr4r48cj2wlbzsqmkvgp35chngjidk3z-ffmpeg-riscv64-unknown-linux-gnu-9.0.1-bin/bin/ffmpeg \
  -v error -debug_ts -c:v h264_v4l2m2m -i /path/public-bbb-360p.mp4 \
  -frames:v 300 -an -f null - 2>/tmp/mvx-qbuf-dqbuf.log
```

Keep the FFmpeg `-debug_ts` output in a separate run or preserve all stderr;
both streams are line-prefixed and can be separated later. The probe needs no
root privilege beyond the existing permission to open `/dev/video0`.

Interpret the result in this order:

1. If compressed `OUTPUT_MPLANE QBUF` timestamps are already zero/repeated,
   inspect FFmpeg's packet/demuxer timestamps. A kernel/firmware patch is not
   justified.
2. If those input QBUFs have valid packet timestamps but `CAPTURE_MPLANE
   DQBUF` returns zero/repeated timestamps, the loss lies below FFmpeg's V4L2
   boundary. Compare each DQBUF timestamp with both input tags and initial
   capture-QBUF tags. That makes the firmware-tag versus driver-association
   question concrete before instrumenting or changing the kernel.
3. If DQBUF timestamps are sound but FFmpeg's decoder lines are not, investigate
   FFmpeg's time-base conversion/output handling with the captured values. The
   two conversions cited above are the first narrow patch boundary.

The trace is diagnostic only. It cannot see the opaque firmware's internal
association and must not be used as a claim that timestamps are physically
presented on the display.

## Initial decision before the physical boundary trace

No source patch was warranted until the trace identified a broken boundary. If
valid QBUF tags are replaced by capture-buffer tags on DQBUF, add a narrowly
reviewed kernel trace at the two documented `user_data` assignments and compare
the firmware completion message. If QBUF is wrong, repair the packet timestamp
source or FFmpeg mapping instead. If both boundaries are correct, retain the
trace with the FFmpeg log and investigate the `AVFrame` conversion path rather
than changing playback timing globally.

## Physical boundary result and candidate FFmpeg correction

The board trace collected after this investigation is committed at `docs/evidence/network-video/mvx-ioctl-boundary.log`. It changes the
working diagnosis:

* It contains 297 `OUTPUT_MPLANE QBUF` records, with submitted timestamps from
  `0.000000` through `9.866667` in the observed sequence.
* It contains 302 `CAPTURE_MPLANE DQBUF` records. The first 20 have
  `bytesused=0`, `timestamp=0.000000`, and flags `0x00004001`; the remaining
  282 have `bytesused=230400` and valid ascending timestamps through
  `9.366667` in the observed capture sequence.
* The FFmpeg log records `Reinit context to 640x368, pix_fmt: yuv420p` before
  those completions. The trace alone does not prove why MVX returns the empty
  buffers. Together with FFmpeg's current dequeue code, it provides a concrete
  mechanism for the earlier repeated output-frame PTS without implicating the
  timestamps on nonempty completions; an exact frame-by-frame map still needs a
  patched repeat.

Pinned FFmpeg only recognizes an empty capture DQBUF as completion while
`draining` (`libavcodec/v4l2_context.c:399-410`). Outside draining it wraps the
buffer as an `AVFrame`, even though raw capture data has zero payload. The
candidate [source patch](../../nix/patches/ffmpeg-v4l2-requeue-empty-capture.patch)
requeues an empty, non-draining, non-`LAST` capture buffer and returns no frame.
It deliberately leaves the current drain/EOS path and existing `LAST` behavior
unchanged. Requeueing is required: simply dropping the buffer would shrink the
capture pool and can deadlock an M2M decoder.

The patch applies cleanly to the pinned FFmpeg source. It has not yet been
built or run on hardware. A review-only derivation evaluation against the
coordinator's current `nix/video-probe.nix` resolves to
`/nix/store/18dqh3l0kjqahh1h584mdny817ii0q82-ffmpeg-riscv64-unknown-linux-gnu-9.0.1.drv`:

```sh
nix build --impure --option max-jobs 1 --option cores 4 --print-out-paths --expr '
let
  root = builtins.toPath (builtins.getEnv "PWD");
  f = builtins.getFlake (toString root);
  pkgs = f.inputs.nixpkgs.legacyPackages.x86_64-linux.pkgsCross.riscv64;
  probe = import (root + /nix/video-probe.nix) { inherit pkgs; };
  ffmpeg = probe.ffmpeg.overrideAttrs (old: {
    patches = (old.patches or []) ++ [
      (root + /nix/patches/ffmpeg-v4l2-requeue-empty-capture.patch)
    ];
  });
in ffmpeg
'
```

Before accepting it, build that temporary derivation, repeat the same bounded
300-frame local clip with the observer, and verify that no zero-payload capture
buffer becomes a decoder frame while normal timestamps and end-of-stream remain
intact. The patch must remain a local video-probe override until that evidence
exists.

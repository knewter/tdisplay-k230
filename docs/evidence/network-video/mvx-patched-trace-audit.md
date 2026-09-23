# MVX empty-capture candidate trace audit

This audit covers the physical board traces in
[`mvx-patched-traces.tar.gz`](mvx-patched-traces.tar.gz), SHA-256
`7c8c6558a8bce911d9660d2afea92b64ce416d80f6340ea305ca7b1ce9558775`
(243864 bytes). The archive contains three capped runs, one uncapped EOF run,
and the coordinator's exit-status record. It is evidence for the local FFmpeg
candidate only; it does not enable the patch in the image or make it an mpv
default.

## Provenance

The logs identify FFmpeg 9.0.1 using `h264_v4l2m2m` on MVX `/dev/video0`, with
H.264 input `/run/bbb-360p-sample.mp4` (640x360, 30 fps), a null output, and
FFmpeg decoder/filter/encoder timestamp logging. `MVX_IOCTL_TRACE` records the
V4L2 queue boundary. The candidate is the local source patch
[`nix/patches/ffmpeg-v4l2-requeue-empty-capture.patch`](../../../nix/patches/ffmpeg-v4l2-requeue-empty-capture.patch): it requeues only zero-payload,
non-draining, non-`LAST` capture dequeues. The exact shell invocation is not
preserved separately; the raw FFmpeg configuration and observed arguments are
retained in each archive member, so this record does not reconstruct omitted
arguments.

## Completion and empty-capture result

`mvx-candidate-result.txt` records exit status zero for all four runs. Each
capped run muxed 300 frames over 10.00 seconds, with elapsed times 1.48, 1.45,
and 1.47 seconds. The uncapped run muxed and decoded 480 frames over 16.00
seconds in 2.10 seconds, reported zero decode errors, and reached decoder and
filter EOF.

Every trace has exactly 20 intact initial `CAPTURE_MPLANE DQBUF` lines with
`bytesused=0`, timestamp zero and flags `0x00004001`. Each has one intact
decoder, filter, and encoder PTS-zero line, consistent with the empty buffers
being requeued instead of becoming twenty zero-PTS frames. This is not a
per-buffer event-ID proof because FFmpeg and tracer writes share stderr. In
the EOF run the final nonempty capture dequeue has `bytesused=230400` and flags
`0x10104001`; normal EOF completed. Thus the trace is consistent with the
candidate retaining the nonempty and end-of-stream path.

## Remaining timestamp defect

The candidate does not repair the capture timestamp association. Each capped
run has an intact duplicate capture dequeue timestamp `7.933333`; decoder,
filter, and encoder each show PTS 238 twice and no PTS 239. The EOF run repeats
that defect and adds three intact capture dequeues with timestamp `12.033333`.
Its decoder/filter/encoder records show PTS 361 three times and omit 362 and
363. The upstream demuxer records the input PTS 239, so this is not evidence of
a missing input packet. It locates the remaining failure at or below the MVX
capture boundary, then shows FFmpeg preserving it.

The capped filter and encoder logs each contain 300 frame records but only 299
unique PTS values because of the 238/239 duplicate/gap. The EOF filter and
encoder logs each contain 480 records but only 477 unique values (duplicate
238, triple 361, missing 239/362/363). Decoder literal-line counts differ from
the stream summaries because the capped decode thread runs beyond the output
frame limit and concurrent stderr lines interleave; they do not prove a frame
loss. Similarly, only intact trace-prefix records can be counted exactly. The
archive is retained so later work can parse or instrument a serialized boundary
without treating these logging artifacts as a packet-to-frame proof.

## Decision

The narrow requeue behavior and successful EOF repeat support using this patch
only as a local diagnostic override for the next mpv native-PTS trial. Do not
enable it globally or claim timestamp correctness. A follow-up must preserve
the trace and investigate the duplicated MVX capture timestamps before making
playback timing policy depend on this candidate.

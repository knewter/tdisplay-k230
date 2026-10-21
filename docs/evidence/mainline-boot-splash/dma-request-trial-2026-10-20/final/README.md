# Qualified normal warm-boot film

Task4.1: **PASS for the observed warm boot**, with the empirical conditions
below. The original raw recorder's unqualified flag is preserved; the later
`qualification-review.json` records the completed optical/counter/source review.

The same one-field bootloader candidate returned ordinary boot
`fbfdd9d3-7f95-4aec-978f-1a19b2a220f9` to the accepted p501 system, unchanged
kernel/executables, native Settings and landscape. Direct first4MiB readback
still matched the deployed candidate and all protected boot-file hashes were
unchanged. `postboot-normal-controls.json`, `postboot-protected-assets.json`
and `restoration.json` retain the exact observations. The camera and panel
brightness255 were restored and the board lease released.

`boot-and-calibration.mp4` is the complete8993frame,640×480/nominal30fps viewing
proxy of the300s recording. The original8993 per-buffer timestamps and flags
are in `frames.jsonl.gz`; use these rather than proxy PTS. The full raw MJPEG
(520533494bytes) remains protected on the host, hash-pinned in `capture.json`.
The entire splash-to-compositor interval is within the first120s. No garbled
logo frame was observed: the unchanged baseline selector flags no interior
frame, and original peak-score frame355 and its neighbors show an intact
logo. This is a filmed30fps sample, not a guarantee about every52Hz panel
refresh or every future boot.

## Timing evidence

The kernel/video result is obtained from this same recording:

- 5989 contemporaneous host MONOTONIC/RAW brackets cover the capture. Host
  TSC is invariant/nonstop; the read-only timex query and conversion envelope
  are recorded. No bare MONOTONIC and RAW timestamps are subtracted.
- All120 SSH brackets constrain an affine host-RAW to board-RAW map; no
  network symmetry, discarded samples or relaxed constraints are used.
- Eight physical255↔32 brightness transitions begin at camera-process
  elapsed230.906s, well after the shell appeared. They empirically bound the
  camera path in the same fixed mode, exposure, timestamp source and stream.
- The largest observed timestamp-minus-changed-photon upper bound is
  76.987ms. An additional46.384ms allows a complete largest-observed frame
  interval plus10ms exposure. Per-frame dequeue causality supplies the
  opposite physical-acquisition bound.
- Thirty-two direct RISC-V `rdtime`/RAW/kernel-log brackets locate the
  physical counter epoch. The live DT and log identify27MHz; the exact
  configured kernel source reads that same continuous64-bit counter for
  both sched_clock and raw timekeeping, preserving the sched_clock epoch.
  This resolves the early-origin question without treating the old
  display-enable message as a presentation event.

The resulting physical-photon time intervals for **every first3600 frame**
have a maximum half-width of **75.244ms**, below the required±100ms.
`timing-analysis.json.gz` retains every interval; `timing-summary.json`
retains the constraints and assumptions. The measured qualification assumes
that the observed fixed camera pipeline's empirical latency envelope and the
invariant hardware-counter model apply across this one stream/boot. It does
not assert an unmeasured universal worst-case camera or oscillator guarantee.

An independent check uses the *actual successor framebuffer* journal record:
after explicit journal MONOTONIC/RAW conversion its83.0068..83.0128s interval
overlaps the observed persistent replacement frame2989's82.9021..83.0355s
physical interval. The framebuffer polling message is not itself a
presentation timestamp. See `handoff-clock-crosscheck.json`.

## Replay and limits

`python3 replay-timing.py` (Python3 and NumPy) reproduces all3600 intervals and
the all-sample constraint fit from the committed compressed clock/frame data,
original numeric ROI observations and counter records. Its output matched the
recorded analysis exactly during verification. The original JPEGs for all
eight calibration transitions are committed as well as the peak-frame samples;
`calibration-roi-luma.json` pins the raw source hash and records the ROI method.
No raw image timestamps or images were rewritten to qualify the result.

The source correction, build and first successful7193frame warm boot are in
the parent README. Together there are two clean candidate warm-boot films.
The change makes no cold-power-on, second-card, new physical gesture,
FIFO-underrun mechanism or universal performance claim.

The independent cold-runner source CI also passed: [stage1 run39526986591](https://github.com/knewter/tdisplay-k230/actions/runs/39526986591).
All five published artifact hashes match the locally built candidate exactly
(`independent-ci.json`), including the installed U-Boot-proper payload.

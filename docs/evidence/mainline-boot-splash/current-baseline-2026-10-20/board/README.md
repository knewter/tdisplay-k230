# The installed default still corrupts the splash briefly

On October 20, 2026, a normal warm reboot of the accepted landscape default
reproduced the brief logo distortions reported on October 12. Task 4.1
remains **open, 8/9 complete**. This is a diagnostic baseline, not a fix or
the final qualified film.

The operator reconnected/repositioned the camera and answered **“ready.”**
The sole board lease was held at `/tmp/k230-board.lock` by pane23, then
released after recording and checking the restored normal session. No USB
console was used, no boot file was changed, and no kernel or bootloader was
installed. The normal reboot command was:

```sh
ssh -F /home/jadams/tmp/k230-coordination/ssh_config.private k230 'systemctl --no-block reboot'
```

It ran once and returned 0 at `2026-10-20T23:30:31Z`. The new boot ID is
`3d59df47-0267-4ab3-8c1e-42a38ae4ae1e`. The preceding boot was
`9cc88abc-dc62-490e-8035-5d4832558a41`.

## Recording and observations

The recorder from `71a71df925e8b9caea4cbaec1ef59686b3324f40` captured
**5,393 frames / 279,370,428 MJPEG bytes** over a 180-second limit, with
**zero sequence discontinuities**, no error-buffer or timestamp-regression
flags, and exit 0. The camera reports `CLOCK_MONOTONIC` and start of
exposure for every buffer. See the unmodified numeric buffer records in
[`frames.jsonl.gz`](frames.jsonl.gz), and the hashes and process results in
[`capture.json`](capture.json).

[`baseline.mp4`](baseline.mp4) is a smaller viewing copy of the first
3,600 frames: 640×480, nominal 30 fps, H.264 CRF26. It covers logo appearance,
the retained-logo interval and the visible shell handoff. Its frame numbers
match the raw recording over that excerpt. Use the original buffer
timestamps, rather than the viewing copy's nominal frame times, for clock
analysis. The full 960×720 MJPEG and exact metadata remain in the protected
capture directory named below; the viewing copy is lossy and resized.

Original, unmodified camera JPEGs provide a before/bad/after example:

| Original frame | Camera time from first recorded buffer | Observation |
| --- | ---: | --- |
| [1426](frame-1426.jpg) | 47.533 s | Ordinary retained logo |
| [1431](frame-1431.jpg) | 47.701 s | Logo displaced/garbled |
| [1436](frame-1436.jpg) | 47.869 s | Ordinary logo returns |

Exact times, byte offsets and SHA-256 hashes are in
[`selected-frames.json`](selected-frames.json). Phase correlation on the
off-panel keyboard control between frames 1426 and 1431 gives a camera-pixel
shift of approximately **−0.015 / −0.123**, response **0.960**. This is an
image comparison, not a physical pose measurement. The distortion in the
panel with a stable surrounding control reproduces the reported defect.

[`candidate-episodes.json`](candidate-episodes.json) records the transient
frame selector's candidates. Several occur near camera times 17, 45–50 and
60 seconds. The selector compares logo-region luminance with frames five
positions before and after, independently of the keyboard control. Its
threshold is a candidate-selection aid, not an exhaustive defect count or
an identification of the cause. The large change when the shell appears
is a handoff and is excluded from those early-splash candidates.

## Identity, normal return and restored controls

[`postboot-normal.json`](postboot-normal.json) verifies the same current,
booted and persistent system:

`/nix/store/p501mchy0dq9lyjnaxwkx5s2pdm4i2yj-nixos-system-nixos-26.11.20260919.20b1ddd`.

The GNU kernel build ID remains `7a61d8cea3e26df94695189b766de3fd66fa6860`;
kernel notes SHA-256 remains
`1a98ea1e0a6e75f923c0fd53cfcf472f576ddb36de86b89361bfc224a305d9b6`.
Rust PID1075 and Sway PID1062 have the previously accepted executable hashes.
Both services are active, the native Settings wrapper remains selected,
and trace environment variables are absent. DSI-1 is still physical
568×1232@52.19 Hz, transform270, logical1232×568, scale1. This is normal-return
identity proof; it does not add a new gesture or smoothness claim.

Protected boot-file hashes and accepted/rollback roots matched before the
reboot. The capture did not alter them. Full raw boot logs stay protected;
[`kernel-phases.log`](kernel-phases.log) contains a selected safe excerpt.

The recording used 960×720 MJPEG at requested30 fps, manual exposure readback99,
gain0, focus80 and white-balance4513, with automatic exposure/focus/WB and
dynamic frame rate disabled. Earlier framing/exposure samples were unsuitable
for a complete proof. One combined focus-disable/manual-value request was
rejected while the manual field was inactive. The first driver attempt then
failed before opening the camera or requesting a reboot because its control
receipt did not exist. Separate auto-disable calls succeeded; the successful
capture is the `20261020b` attempt. No duplicate reboot was issued.

[`camera-restoration.json`](camera-restoration.json) records restoration of
the original 640×480 YUYV /30 fps format and original automatic modes. Inactive
cached manual values are governed by those automatic modes; byte identity of
those inactive values is not claimed. The board lease was released with exit0.

## Clock measurements and remaining timing gate

The 120 post-boot persistent-SSH samples bracket the board clock read between
host send and receipt; the narrowest interval is about4.66 ms. No symmetric
network-delay assumption is used. Large delayed replies are retained.

Eight uniquely named `K230_BOOT_CLOCK_PANE23_A` messages were appended to the
kernel log **after filming** to compare Python, direct kernel
`clock_gettime(CLOCK_MONOTONIC)`, raw time and printk timestamps. Their numeric
results are in [`kernel-clock-check.json`](kernel-clock-check.json).
The active source is `riscv_clocksource`; the configured kernel's
`drivers/clocksource/timer-riscv.c` reads `get_cycles64()` for both the
clocksource and scheduler clock, registering both with `riscv_timebase`.
These log messages were the only diagnostic kernel-log writes; they did not
change tracing, boot assets or configuration.

[`conditional-clock-map.json`](conditional-clock-map.json) fits all SSH
brackets and the separately bracketed printk/raw offset. It preserves
negative early-frame estimates and its assumptions. Reproduce the public
numeric calculation with:

```sh
python3 docs/evidence/mainline-boot-splash/current-baseline-2026-10-20/board/clock-analysis.py
```

<!-- UNVERIFIED: optical accuracy of the reported exposure timestamp,
affine extrapolation before the first SSH sample, and the early-kernel clock
origin have not been physically qualified to ±0.1s. The conditional software
map does not complete task4.1's timing gate. -->

The kernel's “preserving VO to first plane update” message is an enable-phase
observation; it does not timestamp the first visible replacement of the logo.
It must not be used as a camera-presentation anchor.

## Candidate found in source; scope answer pending

The pinned Canaan SDK `1104236db4d1e47873bd68924f912747b820228c`,
`board/canaan/common/logo/display_logo.c`, lines401–408, has
`kd_vo_osd_set_dma_request`: it masks bits3:0 of `VO_OSD_DMA_CTRL` and sets
them to `0xf`. Its byte-map function handles bits5:4 separately. The current
RM69A10 port in `nix/patches/uboot-k230/0004-rm69a10-logo-port.patch` instead
writes `0x40` for OSD4. Mainline ARGB/RGB565 setup uses `0x4f`.

This grounds a **one-field candidate**, `0x40 → 0x4f`, while preserving the
other bits, pixel format, addresses, stride and timing. It does not establish
that the request field caused the recorded corruption or prove current
stage-1 register readback. No speculative register write was performed.

[`dma-candidate-review.json`](dma-candidate-review.json) records a successful
dry run against the pinned SDK overlay. The first dry-run fixture omitted
the existing patch's Kconfig file; completing the fixture and running with
`--batch` checked all five files successfully. The patch is prepared outside
the worktree; no repository bootloader source was edited, built or deployed.

The current proposal explicitly excludes changing the stage-1 splash port.
A question asking whether to extend that scope or retain kernel-only
investigation is pending. Neither “ready” (camera framing) nor elapsed time
answers it. Task4.1 stays unchecked; no scope split, archive or acceptance of
remaining distortion is inferred.

## Source artifacts and limits

Protected original input directory:
`/home/jadams/tmp/codex-claude-handoff-20261019/3/baseline-boot-20261020b`.
The full MJPEG and raw logs remain there. Raw MJPEG/metadata hashes in
`capture.json` identify the exact source. The recorded capture driver and
original full-frame analysis are retained as `capture-driver.py.txt` and
`frame-analysis.py.txt`; they use that scratch layout and require the protected
raw input to replay. `kernel-clock-check.py.txt` records the executed probe.
The separate `clock-analysis.py` replays only committed numeric artifacts.

The current image's defect is reproduced. Its cause, removal and final
qualified default-image film remain unperformed.

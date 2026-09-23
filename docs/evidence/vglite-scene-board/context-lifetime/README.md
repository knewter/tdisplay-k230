# Retain the serialized GPU context across frames

The [board cost profile](../cost-profile/README.md) measured about 107 ms of
initialization/cleanup in a 149 ms GPU pass. Pinned kernel source confirms that
opening and closing its last context triggers clock/reset sequences with sleeps.
The opt-in renderer now retains one process-global context under its existing
mutex and closes it when the last renderer owner is destroyed.

Only clear and image-blit operations are admitted. Initialization uses `(0, 0)`
to omit unused tessellation storage; the pinned SDK demonstrates this in
`test/samples/imgIndex/main.c` and `imgIndex.c`. Its `VGLite/vg_lite.c`
`set_render_target` updates target dimensions per pass, so output-size changes
do not depend on tessellation dimensions. Source ownership, per-pass imported
targets, whole-pass replay, and explicit finish before release are unchanged.

A failed finish still disables GPU use and quarantines context, source memory,
and target mapping for process lifetime. Last-owner destruction does not call
close in that state. A failed shutdown close similarly prevents a second close
or reinitialization; future renderer instances use Pixman. Successful final
shutdown permits a later new owner to initialize a fresh context.

The ASan/UBSan production-renderer suite passes. New tests cover repeated
frames at different dimensions, two renderer owners, first-owner destruction,
last-owner close, subsequent reinitialization, shutdown-close failure, and
last-owner destruction after failed-finish quarantine. Existing exact Pixman
pixel, crop, scale, fallback, and failure tests remain passing.

```sh
TMPDIR=/mnt/MediaVolume/home/jadams \
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
VGLITE_SOURCE=/nix/store/pvpqrg3diyi9mcgmqjc0f80hpdmk699p-source/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
nix build .#shell-compositor-vglite --max-jobs 1 --cores 8 --no-link --print-out-paths
```

The narrow cross-build passes:
`/nix/store/rr671hlb8pg35qx2fl9hwxl42rlj7bgg-sway-1.12`.
Board cost, capture and recovery comparisons are recorded below.
Retaining a context also retains its allocations and active device clock state
between frames; idle-power impact is unmeasured. This is still opt-in, with the
normal shell on Pixman and every broader acceptance gate unchanged.


## Three paired board repeats

On 2026-09-23, the candidate at source `f656f199059a` ran three GPU/forced-Pixman
pairs on the same boot, with the same animated SHM parent/child client, native
568x1232 RGB565 output and padded allocation. `scene-check.py` records the
45-second watchdog and 30-second client commands. Each `round-N` directory
contains original fixed-schema cost/decision logs, exact executable and system
identities, two native captures per mode, parser summaries and a palette check.
The first 20 frames are excluded from timing aggregates; each run retains at least
470 measured frames. All six runs returned zero, observed one Sway process
and restored both normal shell and seatd. GPU runs had zero Pixman replays.

| Round | GPU frames | Pixman frames | GPU mean wall/pass | Pixman mean wall/pass | GPU mean process CPU/pass | Pixman mean process CPU/pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 495 | 571 | 43.959 ms | 36.242 ms | 37.046 ms | 32.471 ms |
| 2 | 492 | 566 | 44.191 ms | 36.647 ms | 37.259 ms | 32.594 ms |
| 3 | 490 | 567 | 44.452 ms | 36.523 ms | 37.205 ms | 32.646 ms |

Compared with the earlier 149.210 ms GPU baseline, mean render-pass wall time
fell about 70%. Steady-state initialization plus cleanup fell from about
106.7 ms to 0.55–0.58 ms. GPU completion remains about 2.38 ms. All three
parent/child palette comparisons pass exactly, including the later captures.
This compares stable region colors across different animation frames, not
whole-frame equality or every format/blend/scale/cache case.

The GPU path still loses to its paired fallback: about 21% more wall time and
14% more process CPU per pass. Immutable snapshots cost about 20 ms wall time
and allocation/conversion/upload another 17 ms. Source preparation is therefore
the next measured bottleneck; claiming an offload benefit or changing the
normal default would be premature. Frame counts are completed diagnostic
render passes, not optical refresh or input latency. This fixed GPU-then-Pixman
order is not a randomized benchmark, and process CPU excludes separately
accounted IRQ and whole-device cost. Ordinary-service access, the normal
renderer comparison, physical controls, idle power and broader correctness
gates remain open; no proposal task is closed by this diagnostic alone.

```sh
python3 tools/vglite-cost.py \
  docs/evidence/vglite-scene-board/context-lifetime/round-1/gpu/costs.log \
  --minimum-frames 100 --discard-frames 20
python3 docs/evidence/vglite-scene-board/context-lifetime/round-1/analyze-palette.py
# Repeat for rounds 2 and 3; parse both modes.
```

The transferred archive SHA256 matched the board:
`54d86bdc243adfb95ef38c74466d2ff0ebdd8b630372fbc620be37aefbe46428`.
Only the named results, fixed-schema logs and captures were transferred; raw
service logs remain private. The normal shell and seatd were checked active
again after collection. No board reboot, image replacement or real-finger
observation was performed.

# Opt-in renderer cost profile

`K230_VGLITE_PROFILE=1` records wall and process CPU durations for each render
pass. The ordinary image remains unchanged; other values disable profiling.
The root diagnostic harness accepts `--profile` and passes that setting only
to its compositor. It retains its unprivileged client and recovery watchdog.

Phases cover immutable snapshot creation, imported-target cache maintenance,
VG-Lite initialization, target import, source allocation/conversion, GPU API
commands (including SDK source cache cleaning), synchronous finish, GPU resource
cleanup, and full Pixman replay. Total spans pass creation through source
release. It includes other pass bookkeeping and diagnostic logging; phase sums
need not equal total. Setup/clock/log overhead and capture disturbance remain.
Process CPU includes user/system time charged to the process; it excludes other
processes, separately accounted interrupts and whole-device cost. No optical
latency or scanout cadence is measured by these timers.

The production renderer sanitizer suite passes with profiling both disabled
and enabled, retaining exact pinned Pixman comparisons and failure quarantine.
Eight root-harness tests pass, including compositor-only opt-in, as do four
parser tests rejecting absent, malformed, failed, insufficient or mixed runs.
The narrow `nix build .#shell-compositor-vglite --max-jobs 1 --cores 8
--no-link --print-out-paths` passes and yields
`/nix/store/kb31nr0jgpz8bcpzy26s7l50r99vzxib-sway-1.12`.

```sh
TMPDIR=/mnt/MediaVolume/home/jadams \
WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
VGLITE_SOURCE=/nix/store/pvpqrg3diyi9mcgmqjc0f80hpdmk699p-source/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
python3 tests/vglite/test_root_trial.py
python3 tests/vglite/test_cost.py
python3 tools/vglite-cost.py COST_LOG --minimum-frames 100 --discard-frames 20
```

Board profiling is recorded below. This is a diagnostic for the next
optimization decision, not completion of the matched performance, normal-service,
cache or physical-control acceptance gates.


## First measured board pair

The source-built artifact above ran the same animated parent/child fixture on
native 568x1232 RGB565 scanout. `scene-check.py` records the exact harness and
client invocation. Both runs returned zero, observed one Sway process, and
restored the normal shell and seatd on the unchanged boot. The GPU run completed
182 GPU frames with no replays; forced Pixman completed 571 replays. After
excluding 20 warmup frames, the parser retained 162 GPU and 551 CPU samples.
`baseline/*/costs.log` contains every original fixed-schema sample; matching
`summary.json` files record the command's aggregates and limits. Decision logs
and actual native captures are retained too. The same palette checker still
passes exactly for parent and child in both captures/modes.

Mean render-pass costs in milliseconds:

| Phase | GPU wall | GPU process CPU | Forced-Pixman wall | Forced-Pixman process CPU |
| --- | ---: | ---: | ---: | ---: |
| Immutable snapshots | 19.592 | 18.190 | 19.851 | 18.460 |
| GPU initialize | 67.355 | 1.494 | 0 | 0 |
| Source allocation/conversion | 16.301 | 14.945 | 0 | 0 |
| GPU completion | 2.377 | 0.107 | 0 | 0 |
| GPU cleanup | 39.372 | 0.704 | 0 | 0 |
| Pixman replay | 0 | 0 | 13.279 | 11.722 |
| Complete pass | 149.210 | 38.389 | 36.267 | 32.515 |

This identifies per-frame GPU context lifetime as the first optimization target.
The renderer currently calls `vg_lite_init` and `vg_lite_close` for each pass.
The pinned running kernel source (Xuantie revision
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`),
`drivers/gpu/vglite/vg_lite_kernel.c:gpu/init_vglite/terminate_vglite`, switches
clocks and resets hardware on the context-reference transitions 0→1 and 1→0.
Those sequences call `vg_lite_hal_delay`; the same tree's
`drivers/gpu/vglite/vg_lite_hal.c` implements it with `msleep`. This source
behavior explains why repeatedly rebuilding the context can add waits unrelated
to the actual draw. It is not a claim that every measured nanosecond belongs to
one kernel sleep.

The next experiment should retain one serialized context across completed
passes, close it after the final renderer owner is destroyed, and preserve
failed-finish quarantine. It must repeat the actual pixel and recovery checks.
The current path spends more process CPU as well as more wall time than its
paired Pixman fallback. No offload benefit, ordinary-shell comparison, optical
latency, IRQ accounting or performance acceptance is claimed from this pair.

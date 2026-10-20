# Current-candidate concurrent camera proof — 2026-10-20 UTC

The operator aimed the camera at the small K230 handheld. A separate fresh
still at03:40:31UTC was visually checked before recording. Both40s clips
show the actual handheld, not the earlier rejected Ladybird display.

Compiled source is `221bbcf34a276a939356e5a6af9bfb124af9896a`; exact build12
system is `/nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd`,
bundle `/nix/store/rmhy6m2cfq72alwrxb1s2wzwalx2l47a-k230-coherent-shell-boot-files`.
Source8d7a32a4 supplies the same compiled inputs plus committed proof. Sole
board reservation and recoverable600s baseline rollback protect the trial.
No reboot, full-image flash, changed8ms render window, profiling, altered
visual quality or reduced resolution was used. Full/reduced are real runtime
modes, verified in each metadata file before native injection.

## Workload and software result

The unchanged controlled three-card workload waits for startup Terminal,
serially maps one/two, verifies focus and actual selected card, and uses six
alternating native-uinput gestures (35 moves/700ms,800ms settle,3.2s baseline/tail).
No board queries, copies or journal export overlap either timed workload.
Camera runs on the host. Preparation runs before the camera/workload so its
bounded startup hide-route retry cannot consume recording coverage. Every
capture/workload exits0. Normal mode is restored immediately after reduced.

| Mode | Trace run | Input→present p95 | p99 | Frame interval p95 | RSS growth |
| --- | --- | ---: | ---: | ---: | ---: |
| full | `103544496099461` | 31.423ms | 34.793ms | 38.317ms | 17,973,248B |
| reduced | `103604819332476` | 34.447ms | 38.113ms | 38.313ms | 20,934,656B |

Both reports PASS all unchanged frozen budgets (p95≤38.32151753209427ms,
p99≤57.4822762981414ms, RSS growth≤64MiB), with216 complete accepted IDs per
mode and no unresolved chains. Reduced settle p50 is123.535ms versus256.482ms
full. These are injected software presentation timestamps, not glass latency.
The preceding two quiet pairs16/17, exact native pixel/lifetime tests, actual
compositor regression, current-source live clients and separate cost profile
remain in the parent evidence directory; camera proof supplements them.

## Video correlation and observed movement

Original video bytes: [full.mp4](full.mp4), [reduced.mp4](reduced.mp4).
The capture manifests retain SHA-256, exact FFmpeg command, clock samples,
monotonic/UTC stamps and progress receipts. Board metadata retains actual
source/system, axes, card setup, down/up stamps and counter intervals.
[correlation.json](correlation.json) associates each mode, trace run, gesture
IDs1–6 and input ranges1–36,37–72,73–108,109–144,145–180,181–216 with bounded
video PTS. Both complete gesture-plus-settle uncertainty windows fit in video.

SSH request/response brackets the board monotonic sample. Camera launch and
first FFmpeg progress conservatively bracket the first frame. Combined
alignment uncertainty is1.881s full and1.255s reduced; review windows are
PTS10.763–21.552s full and8.889–19.051s reduced. No exact optical event time
is inferred from the midpoint of those intervals.

All four contact sheets were visually inspected: [full1](full-contact-1.jpg),
[full2](full-contact-2.jpg), [reduced1](reduced-contact-1.jpg),
[reduced2](reduced-contact-2.jpg). Each mode samples48 evenly spaced original
PTS across its full conservative review window; labels preserve actual PTS.
The card separator visibly moves back and forth and returns to rest, in both
modes. The bright header and panel image remain visible in those reviewed
samples; no whole-panel blackout is visible there. The camera is tilted/soft
and glare is present, so subtle text quality/tearing is not established.

Actual decoded frame PTS have maximum gap33.334ms in each clip and zero gaps
above50ms. This30fps camera samples more slowly than the52.19Hz panel and can
miss a one-refresh blank or tear. Contact sheets are sampled review, not an
all-frame calibrated black-level test. No optical38ms latency, every-refresh
continuity, or real-finger claim is made. The parser's camera `UNVERIFIED`
fields remain unchanged because that tool does not analyze video; this
independent bounded observation supplies the named movement gate.

## Reproduction and selection

Executed host protocol is preserved as `.py.txt` files; original scratch
paths are historical command records. `capture-steps.json` records preparation,
full capture, reduced-on, preparation, reduced capture, and finally reduced-off.
Current-source collection and candidate source pins are in the parent sources.
The pure software report is reproducible:

```sh
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-scene-coalescing/camera/telemetry.log --provenance injected --compare-motion --output /tmp/panel-paint-camera-motion.json
```

Result: exit0, both runs PASS. Physical video observations remain separate.
[qualified-selection.json](qualified-selection.json) and
[qualified-normal-check.json](qualified-normal-check.json) record completed
persistent selection and normal/Home cleanup: verified boot hashes, preserved
backup, matching running/profile identity and exact owned override absence.
The board reservation is released. Installing boot files is not a reboot proof.

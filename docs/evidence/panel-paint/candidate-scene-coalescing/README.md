# Coalesced scene candidate — 2026-10-20 UTC

**Two consecutive controlled full/reduced pairs and a new camera-associated
pair pass all frozen software motion budgets. Current K230 camera movement
proof is complete; the exact qualified candidate is persistently selected.**

Exact compiled source `221bbcf34a276a939356e5a6af9bfb124af9896a`, bundle
`/nix/store/rmhy6m2cfq72alwrxb1s2wzwalx2l47a-k230-coherent-shell-boot-files` and temporary system
`/nix/store/j30yag05ic9k68n9dzbzindgf4ardp08-nixos-system-nixos-26.11.20260919.20b1ddd`
are preserved by build-command/result/log/identity. The exact build succeeds;
reviewed revision7905e5e3 changes only the host fixture/proof. source-equivalence.json
checks all Nix/flake inputs unchanged between those revisions. The current
candidate is221bbcf3, not an inferred build of a later documentation revision.
CI39360785955 and the exact published7905e5e3 work revision are verified.

| Pair | Mode | Trace run | p95 input→present | p99 input→present | p95 frame interval |
| --- | --- | --- | ---: | ---: | ---: |
| 16 | Full | 100430188286655 | 31.537ms | 46.500ms | 19.193ms |
| 16 | Reduced | 100481864814207 | 31.845ms | 36.571ms | 38.319ms |
| 17 | Full | 100561175375289 | 33.886ms | 42.257ms | 38.313ms |
| 17 | Reduced | 100611005458918 | 37.690ms | 48.304ms | 38.316ms |

The unchanged p95 budget is38.32151753209427ms, p99 is57.4822762981414ms;
all four reports pass without rounding a failure to a pass. Every mode has
216 complete trace IDs, zero unresolved, and210 move-latency observations.
RSS growth16,539,648/15,077,376B (pair16),20,791,296/15,122,432B (pair17) is
below64MiB; peak RSS and sampling limits remain explicit in each report.
All earlier failed/intermediate runs remain committed in their own trial dirs.
These two passing pairs do not promise every future event or panel refresh.

Each capture waits for exactly the startup Terminal, maps controlled terminals
serially, verifies focus/app set and actual selected card before injection.
All four starting PNGs are byte-identical to the shared committed static frame.
A per-run equality manifest preserves hashes; it is one settled setup frame,
not every-frame or camera proof. No board queries/copies/journal scans overlap
either timed workload. Pair17 begins after pair16 mode restoration, before
cost export. Known hide-route failures occur before injection, receive only
one bounded retry, and remain in capture metadata. Normal mode is restored
immediately after each reduced capture. No later normal events are relabeled.

| Pair | Mode | Build CPU mean | Build CPU p95 | Mean accepted-input CPU |
| --- | --- | ---: | ---: | ---: |
| 16 | Full | 4.958ms | 5.438ms | 0.191ms |
| 16 | Reduced | 4.949ms | 5.387ms | 0.199ms |
| 17 | Full | 4.935ms | 5.408ms | 0.190ms |
| 17 | Reduced | 4.924ms | 5.458ms | 0.188ms |

All build p95 values pass19.161ms. The unchanged CPU probe previously charged
about0.75ms per accepted input, including0.53ms scene synchronization. Current
scene input means are0.015–0.021ms, with p95 zero for these runs: deferred work
is charged in render preparation, not subtracted or hidden. Complete prepare,
build, commit, input and other CPU stages are retained. Timer coalescing removes
additional repeated paint. Policy and chrome remain immediate, structural
changes synchronous, idle refresh/bilinear restoration intact, with no new
content/frame cap, ISA/compiler-option/quality change or8ms guard change.

Each run records before/after counters. Pair16 coalesces216 redraws and232/231
timer scene passes. The counter interval begins immediately before gestures
and ends after benchmark export; render-sync counts are preparations and may
exceed presentations. They are activation evidence, not physical frame counts
or an independent budget decision. Structural synchronization is separately
proved by the actual-compositor regression, not inferred from these gestures.

Separate512-draw/128-rotation-capped profiling yields53 complete grouped
passes in the three-gesture window: texture mean1.234ms, rotation2.789ms.
All54 selected damage rows report preserved=1, copying416,663.5 logical pixels
on average. Profiler/receipt grouping/cap limits remain in profile.json;
profiling is separate from qualifying motion and its overhead is not subtracted.

The separate live-content run advances main and desynchronized child clients.
At exit, one reports124 frames/123 callbacks/122 releases, child118/117/116;
two194/193/192, child192/191/190. In-flight buffers may remain, and startup/
invisibility contributes maximum gaps. No every-release/leak-free/latency
acceptance claim follows from these counts. Both compositor PNGs were inspected:
visible counter patterns change and rounded composition remains visible.
This is board software capture, not camera or real-glass proof.

The operator subsequently aimed the camera at the K230. New40s full/reduced
recordings and48 sampled contact frames per mode show card movement. The
camera-associated pair also passes every frozen software budget: full31.423/
34.793ms p95/p99 input, reduced34.447/38.113ms. Both videos cover all six gestures;
maximum camera PTS gap33.334ms, no gap above50ms. Clock/camera origin bounds
are1.881s/1.255s wide. See [camera/README.md](camera/README.md) for all artifacts,
SHA-256, original PTS, trace IDs and observations. No optical input latency,
every-refresh blanking, real-glass or subtle text/tearing claim is made.

After camera qualification, the exact source221bbcf3/build12 candidate is
selected in the persistent system profile and verified boot files. Running
and persistent system both resolve to j30yag05ic9k68n9dzbzindgf4ardp08 above.
The previous baseline48af profile and boot files are backed up; the owned trial
rollback timer is stopped after selection. Normal mode/Home, shell/UI active,
profiling off, exact owned91/92 paths absent and no injected devices are
verified in camera/qualified-normal-check.json. See qualified-selection.json
and its command/log for boot hashes and backup. No reboot or full-image flash
was performed; a subsequent cold boot is not claimed. The source default
already includes the qualified renderer, without any quality/window change.

```sh
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-scene-coalescing/pair-16/telemetry.log --provenance injected --compare-motion --output /tmp/scene-pair16.json
python3 tools/shell-motion-trace.py --board --log docs/evidence/panel-paint/candidate-scene-coalescing/pair-17/telemetry.log --provenance injected --compare-motion --output /tmp/scene-pair17.json
python3 tools/panel-paint-profile.py --log docs/evidence/panel-paint/candidate-scene-coalescing/profile.log --workload docs/evidence/panel-paint/candidate-scene-coalescing/profile-workload.json --output /tmp/scene-profile.json
```

Both motion commands and the camera-associated pair command exit0. Task3.1
now has its named current-camera movement proof; software/native/QEMU and
physical evidence classes remain separate. Reproduction requires the sole
board/build reservations as applicable.

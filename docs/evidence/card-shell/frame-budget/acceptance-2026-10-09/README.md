# Card Overview performance acceptance — 2026-10-09

The operator explicitly chose the proposal's accept-performance option:

> i mean i'm happy with the card overview's performance just close it on my permission and land it

[operator-decision.json](operator-decision.json) retains the exact statement,
source records and limits. This completes decision task 4.2d. The user also
confirmed current app switching in the
[UX walkthrough](../../../ux-review-round-2/candidate-2026-10-09/operator-report.json);
its [candidate identity](../../../ux-review-round-2/candidate-2026-10-09/README.md)
identifies the current normal mainline runtime separately from older tests.

## Measured cost and the accepted distinction

The historical [tracking measurements](../../board-cost/long-trace/README.md)
record p95 presentation intervals about 57.47–57.49 ms against the declared
33.334 ms budget, and recorded CPU-budget misses. The later
[vblank observation](../board-result-2026-09-28.md) found a 19.16 ms hardware
grid during idle and injected Overview transitions. The discrepancy is
render/commit overrun quantized to vblank, rather than a 57 ms panel limit.
The historic cost is less frequent visual updates while cards move.

Those measured misses remain measured misses on their identified candidates.
The current accepted mainline/HDMI runtime has different geometry and
artifacts; this approval supplies no new numeric timing for it. The operator
is satisfied with its observed performance. Further performance optimization
and the known-risk commit-pipelining experiment are not needed for closure.
Functional card behavior remains accepted separately; no behavior is removed
to meet a benchmark.

No new UART, camera or performance session ran for this decision. The separate
selected board-system host build and selected, non-fixture QEMU guest smoke
passed. Their exact commands, timestamps, identities and limits are retained
below; neither supplies a fresh physical performance measurement.

Ownership: worktree `/home/jadams/tmp/k230-card-overview-close-final`, branch
`closeout/card-overview-accepted-2026-10-09`, base `427a15f3`. Owned paths are
this change's planning/evidence, system/QEMU selection, guest verifier, smoke documentation
and work-board status, plus the CLI-synced `runtime/card-shell` requirement.
Builds use `/tmp/k230-nix-build.lock`; no board reservation is taken.

## Selected board configuration build

The [host build and selection record](board-build.json) and [build log](board-build.log)
record a successful full `k230` system build with `coherentShell = true`.
`k230-bar-shell` retains the former bar-system derivation exactly. The existing
normal mainline configuration still evaluates to the accepted `yl3si5ak`
closure, unchanged; no board activation or boot was performed. The QEMU-pending limit in the host-build record describes that earlier source
checkpoint; the subsequent selected guest run passed as recorded below.


## Build cache retention

The [cache investigation and durable roots](build-retention.md) record unchanged
sampled dependency recipes and protect the realized selected artifacts and
build inputs against normal GC. The specific earlier deletion event remains
unverified. This host-local retention does not change global GC policy.


## First selected guest attempt

The [first ordinary selected-image run](qemu/failed-selected-first/result.json)
built and booted the image but failed `expand restores app focus`. Its
[manifest](qemu/failed-selected-first/manifest.json) and [actual failure lines](qemu/failed-selected-first/failure.log)
remain a failed integration attempt. The verifier held a 170-pixel drag while
checking both live previews, then expected that slow release to select the
neighbour. The original fixed-threshold policy supported that assumption;
current nearest-card/coasting policy and 80%-width cards require more travel.
The corrected verifier finishes the stroke and observes actual selection and
settlement before tapping. At that checkpoint a fresh selected guest pass was
required; the subsequent passing run is recorded below.


## Selected QEMU guest integration

The ordinary `tools/qemu-k230.sh --card-shell-smoke` invocation, without
`--fixture-image` or `--no-build`, built and booted the selected `k230-qemu`
image and returned zero. [Manifest](qemu/manifest.json), [result](qemu/result.json),
[provenance](qemu/provenance.json) and [actual guest reports](qemu/guest-reports.log)
retain the selected artifacts and two fresh runtime reports. Both report the
same selected system and compositor executable, unprivileged UID and RISC-V
guest, with different compositor PIDs after service restart. All six required
interaction checks and service teardown passed.

This is system-mode QEMU on `virt`, with headless Pixman output and injected
input. It proves the selected Linux/userspace integration, not a new board
boot, panel scanout, physical touch, optical latency or numerical frame-budget
pass. Current physical Overview performance is accepted by the separate
operator decision above. No new system was activated on the board.

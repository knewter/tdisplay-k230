# Paired RVV card workload

The physical context and 192-case pixel comparisons pass; see
[the vector trial](../board-trial/README.md) and
[pixel/package evidence](../../pixman-rvv/pixel-trial/README.md).
Six physical runs now compare the same live-card interactions with Pixman's
runtime RVV selection enabled and disabled. **Keep RVV experimental:** the
small CPU-cost differences do not resolve the existing card budgets. The
comparison is complete; card-product acceptance is not.

## Controlled workload

`tools/card-shell-rvv-benchmark.py` runs **on the reserved physical board**.
Its sibling session, acceptance and budget scripts must be staged alongside it.
It requires the exact matching trial system, physical model and a fresh PASS
from the bounded vector context probe. It then runs three matched pairs in
this order: disabled/automatic, automatic/disabled, disabled/automatic.

Both modes use the same optional `lgpv6h…` card package, kernel, client,
configuration, 568×1232 RGB565 output, producer and budget parser. The unchanged
acceptance script drives one- and two-card workloads with 24 drags apiece,
collects native captures, and records thirteen interaction checks. These are
injected inputs, not physical-finger acceptance.

The session harness sets `PIXMAN_DISABLE=rvv` or an explicit empty disable list
only on its transient compositor service. Automatic selection retains the
library's runtime kernel gate; it does not force instructions. The driver
checks the actual Sway executable, cgroup, process environment and mapped
Pixman library before the workload. The uninstrumented compositor has no
pixel-test callback wrappers. Mapping and policy observations are distinct
from the earlier pixel test's counted RVV callbacks.

Each run uses the existing independently armed root watchdog and restores
shell/seatd afterward. Failure to restore leaves the watchdog armed and aborts
the remaining pairs. Missing frame coverage or changed comparison identities
also prevent a complete measurement. A complete measurement may still fail all
card budgets or record failed interaction checks; those outcomes remain in the
result rather than being relabeled as successful product acceptance.

The output includes per-run full budget reports, normalized telemetry,
interaction observations, runtime identity and thermal/frequency readings where
available. Private process logs and native captures remain on the board until
reviewed. Only each run's `public/` files and the fixed-schema result/plan/progress
records are eligible for direct collection; a public capture hash is not a
claim that its picture has been visually reviewed.

## Commands and limits

Host preparation touches no device:

```sh
python3 tools/card-shell-rvv-benchmark.py --prepare --repeats 3 \
  --revision BENCHMARK_SOURCE_REV --output NEW_PLAN_DIRECTORY
python3 tests/test_card_shell_board_tools.py
python3 tests/test_card_shell_rvv_benchmark.py
python3 tools/card-shell-benchmark.py --self-test
```

The 24 session-control tests, six paired-evidence tests and 18 unchanged budget
parser tests pass. These are host checks, not a physical performance result.

After staging the published scripts/package and booting the recoverable trial,
run on the board:

```sh
python3 tools/card-shell-rvv-benchmark.py --board --repeats 3 \
  --revision BENCHMARK_SOURCE_REV \
  --output /var/lib/k230/rvv-benchmark-NEW_NAME
```

Use a new output directory; previous failed or successful evidence is retained.
The driver bounds each session with the existing 540-second service deadline
and 480-second acceptance subprocess timeout. Its ordinary-session restoration
is on the trial kernel. After collection the operator must reboot to the
persistent normal system and run `tools/check-root-growth.py --board --phase repeat`
with the normal baseline, as specified in the proposal's recovery task.

The default image remains unchanged. Three serial pairs are a small comparison,
not a confidence interval. Presentation feedback is not optical light-output
timing. Passing this experiment alone does not close the independent card UI,
image-integration or real-finger acceptance gates.

## Physical result, 2026-09-23

The guarded third trial boot is in `boot3.json`. The six runs in `run1/`
executed between **22:40:32 and 22:51:04 UTC**, using published producer revision
`678afb77805ef43d7d5e552dc331efadac9f6c08` and the exact immutable package,
configuration, client and system in `run1/plan.json`. All shared identities,
actual mapped libraries and per-process dispatch policies were verified.
A fresh two-process context diagnostic passed before rendering: 2,000 parent
checks, 2,000 signals and 466 involuntary switches; the child exited successfully.

`run1/result.json` records `measurement_status=COMPLETE`, with both
`all_card_budgets_pass` and `all_interaction_checks_observed` **false**.
Each of the six runs restored shell and seatd on the trial kernel. Input was
injected through the panel-coordinate path; native pictures were captured
but remain private and unreviewed. This is neither real-finger nor optical proof.

| Pair | Cards | RVV disabled p95 CPU ms | Automatic RVV p95 CPU ms | Change |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1 | 16.682 | 16.475 | −1.24% |
| 2 | 1 | 16.415 | 16.049 | −2.23% |
| 3 | 1 | 16.672 | 16.449 | −1.34% |
| 1 | 2 | 23.295 | 23.109 | −0.80% |
| 2 | 2 | 23.361 | 22.757 | −2.58% |
| 3 | 2 | 23.173 | 23.294 | +0.52% |

These are per-run p95 values, not pooled percentiles or a confidence interval.
The one-card automatic p95 is modestly lower in all three pairs; the two-card
result is mixed. Active compositor CPU is lower by 0.33–2.38 percentage points
across the six workload comparisons. Different submitted-frame counts mean
those sampled percentages are not an equal-frame throughput benchmark.

Every one- and two-card workload still fails **frame CPU** and **tracking
presentation interval** budgets. Two-card p95 CPU remains above 16.667 ms;
one-card maxima reach 48–111 ms against a 33.334 ms maximum. Tracking p95 stays
near 57.5 ms in both modes against a 33.334 ms budget. Motion-to-presentation,
release and incremental-memory budgets pass in every run. Incremental memory
is 393,216–630,784 bytes against the existing 64 MiB ceiling. Full timing,
CPU, memory and coverage details remain in each `public/budget.json`.

The upward-throw close request is missing in four runs: pair 1 disabled,
pair 2 automatic, and both modes of pair 3. Every other recorded interaction
check is observed. The independent Close route exercised by the unchanged
harness still permits the refusal and timeout checks. No causal attribution
to RVV is established, and no interaction failure has been removed.

Host-side `cpu-profile.json` files correlate every diagnostic frame row with
its accepted total. About 86.5–90.1% of charged CPU lies in the output repaint
handler, which includes scene preparation, renderer work and output commit.
This is not pure Pixman time. Both modes carry the same instrumentation;
its overhead remains a limit on the experiment.

Only CPU 0 is online. Frequency reporting is unavailable. Raw thermal sysfs
readings are retained without interpreting their implausibly low absolute
values as calibrated temperatures; frequency/thermal control was not proved.
The uninstrumented vector library's mapping and policy were observed in Sway;
actual callback counters belong to the separate pixel test, not these runs.
The diagnostic package substitutes an ABI-identical dependency recursively;
a default promotion would require a fully rebuilt and reviewed graph.

## Decision and remaining work

Do not promote this trial into the default image on this evidence. CPU vectors
work for the tested state and pixel cases, but do not resolve card cadence or
frame CPU limits. Continue the open card proposal's rendering/cadence work and
investigate the intermittent upward-throw request before product acceptance.
The independent GPU, image integration and real-finger gates remain open.
No budget was relaxed and no ordinary image setting changed.

`normal-reboot.json` records serial-requested return without physical
intervention. The separate `normal-recovery.json` and `.serial.log` verify the
normal system, unchanged boot/firmware hashes and root sentinel/layout,
shell/seatd and Wi-Fi HTTPS recovery. The normal persistent selection remains
`/nix/store/gnr36q39hmy4pq7ipwac1r1rpfbyqxd4-nixos-system-nixos-26.11.20260919.20b1ddd`.

## Reproduce the analysis

The on-board command was:

```sh
python3 /var/lib/k230/rvv-card-tools-678afb77/card-shell-rvv-benchmark.py \
  --board --repeats 3 \
  --revision 678afb77805ef43d7d5e552dc331efadac9f6c08 \
  --output /var/lib/k230/rvv-benchmark-678afb77-run1
```

It ran in a root transient service with a 3,600-second outer deadline and the
per-session deadlines above. `transfer.json` records the 45 named text files,
351,154-byte compressed transfer and SHA256 verified between board and host.
Raw process logs and images were excluded. Host analysis adds `comparison.json`
and the six CPU-subdivision reports without altering the captured files.

```sh
python3 docs/evidence/card-shell/kernel-rvv/card-cost/summarize.py
python3 docs/evidence/card-shell/render-cost/analyze.py \
  --input docs/evidence/card-shell/kernel-rvv/card-cost/run1/pair-1-auto/public/telemetry.log \
  --output /tmp/pair-1-auto-profile.json
```

The first command reconstructs all six budgets exactly from committed telemetry
(excluding only the analyzer's new report timestamp), checks shared identities
and ordering, and regenerates the per-run comparison. Repeat the second command
for each run to reproduce its CPU subdivision; it produces no acceptance claim.

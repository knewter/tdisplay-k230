# First valid correlated board cost report: FAIL

Actual Pixman/RGB565 at 568x1232, using corrected producer source `bc52538` and
`/nix/store/qh2jzzn4p5dgryfrwihimc7lad98rldl-k230-card-shell`. The original
six-drag-per-workload native harness ran unchanged; all thirteen interaction
checks were observed. `manifest.json` supplies collection identity, and
`telemetry.log` is the unchanged allowlisted producer output. The normal shell
restored, with the independent control regression passing at 16:35:25 UTC.

```sh
python3 tools/card-shell-benchmark.py --board \
  --input telemetry.log --manifest manifest.json --output pixman.json
```

The parser now accepts the ordering and correlations, returning exit 1 and
`FAIL` because the measured budgets fail. There are no unresolved input,
submission or presentation identifiers. This is not a passing cost gate.

| Metric | 1 card | 2 cards | Declared limit |
| --- | --- | --- | --- |
| Frame-update process CPU, p95 | 17.11 ms | 24.05 ms | 16.667 ms |
| Motion to submit, p95 | 39.72 ms | 57.28 ms | 50 ms |
| Motion to presentation, p95 | 47.50 ms | 66.23 ms | 66.667 ms |
| Tracking presentation interval, p95 | 57.48 ms | 76.63 ms | 33.334 ms |
| Release to final presentation, max | 32.88 ms | 51.07 ms | 266.667 ms |
| Incremental session memory | 454,656 bytes | 397,312 bytes | 67,108,864 bytes |

Coverage also needs extending. There were only 34/44 distinct submitted frames
and 13/26 qualifying tracking intervals, below the 60/30 minima. Many native
events coalesced. A numeric failure takes precedence over `INCOMPLETE` in each
metric's status; the sample counts must still be reviewed. The unchanged
parser excludes input gaps over 50 ms from the tracking-interval calculation:
13 gaps for one card and 7 for two.

The harness now requests 24 drags per workload to obtain adequate independent
frame samples. This changes coverage, not thresholds, the native gesture path,
client eligibility, or liveness requirements. A longer repeat is required.
The current data already rules out a performance pass. Image integration stays
open, and the next optimization needs to address measured frame/render work
while preserving live surfaces and direct movement.

Times begin at compositor input handling and use hardware-signalled output
presentation. They do not include independent glass/light-output timing.
Snapshots and logging are part of this instrumented workload. The memory
comparison uses the same apps before entry and after restoration; it is sampled
cgroup memory, not a claim that between-sample peaks are impossible.

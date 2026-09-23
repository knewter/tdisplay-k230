# Adequate-coverage Pixman card cost baseline: FAIL

Collected on the actual 568x1232 RGB565 panel at 2026-09-23 16:41:34 UTC.
The opt-in product package is
`/nix/store/qh2jzzn4p5dgryfrwihimc7lad98rldl-k230-card-shell`, source
`bc52538878e45ed1f9e747d011d8a81b3811a125`. The native injected harness at
`8b01b936` requests 24 horizontal drags for each card count. No budget changed.
The board archive transferred over Wi-Fi with matching SHA256 before extraction.

```sh
python3 tools/card-shell-benchmark.py --board \
  --input docs/evidence/card-shell/board-cost/long-trace/telemetry.log \
  --manifest docs/evidence/card-shell/board-cost/long-trace/manifest.json \
  --output /tmp/card-long-report.json
```

Expected exit: 1 (`FAIL`). There are no unresolved correlations or missing
provenance fields. One/two-card workloads have 136/139 submitted frames and
90/92 qualifying tracking intervals, exceeding the fixed 60/30 minima.
Input pauses over 50 ms are excluded by the existing parser: 20/18 respectively.

| Metric | 1 card | 2 cards | Limit |
| --- | --- | --- | --- |
| Frame-update CPU, p95 | 17.218 ms | 24.174 ms | 16.667 ms |
| Frame-update CPU, max | 110.196 ms | 25.595 ms | 33.334 ms |
| Motion to submit, p95 | 40.466 ms | 48.096 ms | 50 ms |
| Motion to submit, max | 106.568 ms | 66.825 ms | 100 ms |
| Motion to presentation, p95 | 48.898 ms | 61.998 ms | 66.667 ms |
| Tracking presentation interval, p95 | 57.482 ms | 57.485 ms | 33.334 ms |
| Release to final presentation, max | 133.849 ms | 53.162 ms | 266.667 ms |
| Incremental session memory | 479,232 bytes | 393,216 bytes | 67,108,864 bytes |

The raw interaction check report contains **12 observed checks and one failed
upward-throw-close-request check**. The refusal button fallback, separate close
timeout, accepted close and persistent control checks were observed. Earlier
successful injected throw evidence remains valid for those runs, but this repeat
shows that repeatability is unresolved. This is not a new passing product trial;
its screenshots have not been separately accepted as visual proof. The original
reviewed visual evidence remains in `../../injected/`.

The normal shell and seatd restored after the experiment. A subsequent independent
normal-control regression is recorded in `restoration.json`. No image flash or
reboot occurred. The installed default shell is unchanged.

Decision: keep task 4.2 and default image integration open. Profile actual scene
update and rendering work and investigate throw repeatability before claiming a
mitigation. Chrome already avoids rebuilding unchanged labels; adding caching
is not a justified performance claim. Its separate layout/failure invalidation
fix does not establish a cost improvement. Preserve live card surfaces and the
existing input path when evaluating any optimization.

These timings start at compositor input dispatch and end at backend presentation
feedback, not optical visibility. Memory is sampled cgroup memory and does not
exclude between-sample peaks. This is injected board evidence, not real-finger
acceptance. The optional GPU renderer remains independently unaccepted.

# Board CPU profile: repaint dominates, budgets still fail

The physical board ran diagnostic source `fcd9dc718bcba9a469e2417a7b0050af3558bebd`,
package `/nix/store/5cxcjkfayy93zhyy2qybbrnad5rd3s6f-k230-card-shell`, with the same
24-drag-per-count injected acceptance workload, 568x1232 panel and Pixman RGB565.
All thirteen interaction checks were observed, including the throw and refusal
recovery. The original shell restored; the independent control regression is
in `restoration.json`. No image flash or reboot occurred.

The archive transferred over Wi-Fi with matching SHA256. The initial host
transfer attempt did not satisfy its digest/completion guard and was not used;
retrying the same board archive with a longer console-observation window did.

```sh
python3 docs/evidence/card-shell/render-cost/analyze.py \
  --input docs/evidence/card-shell/render-cost/board/telemetry.log \
  --output /tmp/card-cpu-profile.json
python3 tools/card-shell-benchmark.py --board \
  --input docs/evidence/card-shell/render-cost/board/telemetry.log \
  --manifest docs/evidence/card-shell/render-cost/board/manifest.json \
  --output /tmp/card-profile-budget.json
```

The diagnostic correlation exits 0: all 133/131 one/two-card frame rows match
unique acceptance submission totals, with complete and non-overlapping CPU
subdivisions. The unchanged budget parser exits 1 (`FAIL`). Tracking interval
p95 remains 57.49 ms. The instrumentation is not a speedup experiment.

| CPU measurement | 1 card | 2 cards |
| --- | --- | --- |
| Total frame-update p95 | 17.516 ms | 25.054 ms |
| Repaint handler p95 | 14.432 ms | 20.125 ms |
| Input handler p95 | 3.167 ms | 6.200 ms |
| Other charged work p95 | 0.673 ms | 1.243 ms |
| Repaint fraction of total sampled CPU | 87.20% | 83.04% |
| Input fraction of total sampled CPU | 10.12% | 13.77% |
| Other fraction of total sampled CPU | 2.67% | 3.20% |

Percentiles are independent distributions and must not be added. Fractions use
summed CPU across sampled frames. Repaint includes scene preparation, wlroots,
Pixman and output commit: this does not isolate pure pixel-scaling cost or kernel
commit cost. A 111 ms one-card maximum remains in the full report; do not hide it
behind the percentile. Extra profiling calls/logging add overhead.

Decision: prioritize repaint/scene work, while retaining input and cost gates.
Source review found repeated raise-to-top operations for every parent/child
mirror on each synchronization, even when final stacking order is unchanged.
A candidate is to preserve already-correct sibling order while still applying
real restacks. It needs native order/privacy/liveness regression checks and the
same instrumented board comparison before any speedup claim. The existing
bilinear filtering, live updates and interaction semantics must remain intact.

This repeat is injected board evidence, not physical-finger or optical proof.
New captures have not been separately accepted as visual evidence; earlier
reviewed captures remain authoritative for that gate. Tasks 4.2, 5.1 and 5.3
remain open. No completed proposal is inferred from a diagnostic result.

# Mirror ordering board comparison: performance gate remains open

Candidate source `194f3357a18408456d819269500a6593c97dc41a`, package
`/nix/store/gk20p9l39pqs5xg3akgg3fxm4jc7cb5x-k230-card-shell`, ran the same
24-drag-per-count injected acceptance workload as
`../../render-cost/board/README.md`. All 13 interaction checks were observed;
the independent normal-shell restoration check passed. No flash or reboot.
Wi-Fi transfer of the evidence archive passed its SHA256 check.

The profile analyzer matched all 137/136 one/two-card frames to unique benchmark
submission totals. The unchanged board budget parser exits 1 (`FAIL`).

| Measurement | Baseline 1 card | Candidate 1 card | Baseline 2 cards | Candidate 2 cards |
| --- | --- | --- | --- | --- |
| Frame-update CPU p95 (ms) | 17.516 | 16.574 | 25.054 | 23.290 |
| Repaint CPU p95 (ms) | 14.432 | 14.418 | 20.125 | 20.216 |
| Input CPU p95 (ms) | 3.167 | 2.743 | 6.200 | 5.882 |
| Tracking presentation interval p95 (ms) | 57.492 | 57.496 | 57.490 | 76.658 |

This single comparison does not establish a user-visible speedup. Two-card
tracking got worse despite lower sampled CPU. Repaint p95 barely changed.
One-card CPU maximum remains 49.128 ms, exceeding 33.334 ms; two-card CPU p95,
motion-to-submit p95 (54.416 ms), and both tracking intervals fail their gates.
Memory and release recovery pass. The repeat comparisons below retain this unfavorable observation rather than
selecting only CPU.

Reproduce the reports with the existing analyzers, using this directory's
`telemetry.log` and `manifest.json`:

```sh
python3 docs/evidence/card-shell/render-cost/analyze.py --input TELEMETRY --output PROFILE
python3 tools/card-shell-benchmark.py --board --input TELEMETRY --manifest MANIFEST --output REPORT
```

This is injected board evidence. New captures have not been separately accepted
as visual proof; physical-finger and optical acceptance remain unverified.
Tasks 4.2, 5.1 and 5.3 remain open.

## Same-candidate repeat

A second reserved run of the identical package observed all 13 interaction
checks again. The profile covers 141/134 one/two-card frames. One/two-card total
CPU p95 was 16.763/25.060 ms, repaint 14.409/20.144 ms, input 2.530/4.912 ms,
and tracking intervals 57.493/57.505 ms. The first run's 76.658 ms two-card
tracking p95 did not repeat, but the CPU improvement did not repeat either.
Both runs fail the unchanged performance gate. Full reports are in `repeat/`.

## Original-package repeat and decision

Repeating the original instrumented package after both candidate runs again
observed all 13 checks; normal control restoration passed. Its 137/137 frames
had one/two-card CPU p95 17.228/24.508 ms and tracking p95 57.497/76.656 ms.
The slower two-card tracking also occurs without the candidate. Full reports
are in `baseline-repeat/`. All four runs used the same board, 24-drag workload,
clients and profiler; this is a small serial comparison, not a confidence
interval or a demonstration of smooth interaction.

Land the narrow ordering change to remove proven redundant scene invalidations,
with the actual ordering regression, native runtime tests and both candidate
board interaction passes. **No panel performance improvement is established.**
The source preserves bilinear filtering, live parent/child content, privacy,
close behavior and callbacks. Keep the cost gate open and prioritize remaining
repaint work. These results do not authorize default-image integration or an
archive. The normal shell is restored and separately checked after each run.

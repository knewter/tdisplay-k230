| metric | baseline #1 | egui #1 | baseline #2 |
| --- | ---: | ---: | ---: |
| arm_system_busy_pct | - | - | - |
| startup_ms | 190.00 | 283.00 | 198.00 |
| incremental_memory_mib | 35.55 | 37.98 | 38.06 |
| idle_client_cpu_pct | 0.02 | 0.02 | 0.02 |
| idle_sway_cpu_pct | 1.23 | 1.20 | 1.20 |
| active_client_cpu_pct | 7.59 | 45.85 | 0.45 |
| active_sway_cpu_pct | 7.63 | 16.63 | 1.80 |
| active_combined_cpu_pct | 15.22 | 62.49 | 2.25 |
| commit_gap_p50_ms | 19.00 | 41.00 | 500.00 |
| commit_gap_p95_ms | 567.00 | 57.00 | 501.00 |
| commit_gap_max_ms | 1384.00 | 490.00 | 502.00 |
| commits_in_active | 406.00 | 586.00 | 59.00 |
| render_p50_ms | - | 23.55 | - |
| render_p95_ms | - | 40.82 | - |
| render_max_ms | - | 75.15 | - |
| input_to_commit_p50_ms | 13.00 | 37.00 | 244.00 |
| input_to_commit_p95_ms | 814.00 | 53.00 | 474.00 |
| input_to_commit_p99_ms | 838.00 | 67.00 | 496.00 |
| input_samples | 333.00 | 333.00 | 333.00 |
| interactions | 48.00 | 48.00 | 48.00 |
| restored | yes | yes | yes |
| gate bounded_lifetime | PASS | PASS | PASS |
| gate interrupted_motion | PASS | PASS | PASS |
| gate pixels_correct | PASS | PASS | PASS |
| gate readable | PASS | PASS | PASS |
| gate restored | PASS | PASS | PASS |
| gate scroll | PASS | PASS | FAIL |
| gate software_route | PASS | PASS | PASS |
| gate tap | PASS | PASS | FAIL |
| gate text_entry | FAIL | FAIL | FAIL |
| gate text_focus | FAIL | FAIL | FAIL |

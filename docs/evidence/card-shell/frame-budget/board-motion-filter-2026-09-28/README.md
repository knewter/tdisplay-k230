# Card deck frame CPU on the board: motion-time filter, 2026-09-28

Evidence class: a board measurement over serial, driven by injected touch
through the compositor's own `card_shell down/motion/up` IPC with
`card_shell benchmark injected` telemetry. There is no real finger, so this
measures CPU cost, not feel.

The workload (`deck-bench.sh`) opens three apps (foot, galculator, foot),
enters the overview, then runs 6 passes of a leftward and a rightward
horizontal drag (12 drags, 360 input steps). Both runs used the identical
script and app set.

| System | Frame-update CPU p50 | p90 | p95 | max | Frames over 19.16 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Before: `ylkc0l6z…` (master plus overlay fix) | 37.2 ms | 37.7 | 38.0 | 39.4 | 348/360 (97%) |
| After: `jd7jb88d…` (plus `perf/deck-draw-less` and the two-axis fix) | 13.2 ms | 13.7 | 14.0 | 40.5 | 11/360 (3%) |

`after` recorded 30 `filter-mode` telemetry rows, so the nearest-while-moving
path was exercised. Reproduce with `python3 cpu-stats.py bench-before.log
bench-after.log`.

Limits:
- Presentation intervals in this workload track the swaymsg input rate
  (about 96 ms per injected step), so the presentation p95 criterion is not
  judged here.
- A real-finger drag is needed for the presentation-interval and feel
  checks (the change's remaining board task).

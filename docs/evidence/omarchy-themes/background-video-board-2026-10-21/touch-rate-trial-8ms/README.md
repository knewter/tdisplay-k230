# Paired trial at the installed 8 ms allowance with real-finger steps: three cards fail

The reserved-board trial ran **2026-10-21 23:53:45Z–23:57:47Z**. It repeats
the [12 ms touch-rate trial](../touch-rate-trial/README.md) exactly, with
86 steps per 700 ms drag (8.14 ms, matching the measured
[real-finger rate](../touch-rate/README.md)). The one difference is that it
leaves the installed **8 ms** render allowance in place. One-card arms pass.
**Three-card still and video arms fail tracking p95 (38.320 and 38.173 ms
against 33.334 ms).** This is a real render-time failure, not an input-rate
artifact. During three-card drags the all-present interval p95 is itself
38 ms, so the panel skipped refreshes.

| Metric | Still, one | Still, three | Video, one | Video, three |
| --- | ---: | ---: | ---: | ---: |
| Frame-update CPU p95 | 4.377 ms | 7.546 ms | 4.175 ms | 6.937 ms |
| Render wall p95 (all committed) | 7.130 ms | 10.891 ms | 8.298 ms | 10.004 ms |
| Motion-to-submit p95 | 18.659 ms | 28.873 ms | 18.826 ms | 25.701 ms |
| Motion-to-present p95 | 23.771 ms | 35.855 ms | 24.037 ms | 35.248 ms |
| Frozen tracking interval p95 | 19.165 ms | **38.320 ms FAIL** | 19.165 ms | **38.173 ms FAIL** |
| Tracking interval maximum | 19.182 ms | 38.348 ms | 38.314 ms | 38.203 ms |
| Above-target tracking intervals | 0 / 216 | 12 / 198 | 1 / 215 | 11 / 204 |
| All-present interval p95 / max during motion | 19.165 / 19.182 ms | 38.320 / 38.348 ms | 19.165 / 38.314 ms | 38.173 / 38.203 ms |
| Incremental session memory | 6,561,792 B | 11,309,056 B | 6,148,096 B | 9,711,616 B |

Every other numeric metric passes. There are no excluded input pauses, and
there are 516 motions per arm. [correlation-audit.json](correlation-audit.json)
finds zero mapping disagreements.

Compared with the 12 ms run, three-card render wall p95 is roughly 10–11 ms
in both. With an 8 ms allowance the compositor starts the render 8 ms before
the deadline, so a 10 ms render misses that refresh. With 12 ms it fits. The
frame-update CPU p95 (about 7–7.5 ms) passes its budget, so wall time beyond
CPU time (scheduling and commit) is what overruns. That matches the earlier
[elapsed](../tracking-elapsed/README.md) and
[render-profile](../render-profile/README.md) diagnostics.

The named background workload completed with restoration passed. Cover pauses
the decoder and uncovering resumes it. [final-audit.json](final-audit.json)
independently verifies the original system, compositor, landscape, 8 ms,
still wallpaper, exact preferences, the app pointer, fixture/override
removal, an inactive timer (`k230-touchrate8-20261021`), zero injected
devices, and active services.

## Source and commands

Source is `9b84b300744fa2360abcf52b6e308102829c2311`, with the same reused
candidate compositor `0v1q7r9g…-k230-card-shell-hdmi-trial`.
[prepare-host.py](prepare-host.py) applies the touch-rate substitutions plus
`max_render_time 8`, `allowance_ms: 8`, override `99-touchrate8.conf`, and
fresh owned paths. All tool and asset hashes are unchanged from paired12
([staged-sha256.json](staged-sha256.json)). The board command is
`/var/lib/k230/touchrate8-20261021/run.py`, run under the exclusive board
lock. [analyze.py](analyze.py) is the touch-rate replay script, with its two
12 ms assertions changed to 8 ms. There were no failed attempts.

## Consequence for task 3.3

With realistic input, the frozen gate passes at a 12 ms allowance and fails
at the installed 8 ms with three cards. Closing it requires one of two
things: making 12 ms (or similar) the shipped allowance, which costs about
4 ms of latency headroom per frame, or bringing three-card render wall p95
under 8 ms. Neither is decided here, and the task stays open.

# Paired quiet 12 ms trial at the real-finger step rate: all numeric metrics pass

The reserved-board trial ran **2026-10-21 23:04:19Z–23:08:22Z**. It repeats
the [paired quiet 12 ms trial](../paired12/README.md) with one change. Each
700 ms injected drag now takes 86 steps (8.14 ms each) instead of 35 steps
(20 ms each). This matches the operator's measured Goodix report interval of
8.122 ms during a real finger drag ([touch-rate](../touch-rate/README.md)).
Every frozen numeric metric passes in all four arms. **Tracking p95 is
19.164–19.165 ms against 33.334 ms.** The thresholds, the nearest-rank
percentile, the pause exclusion, the workload and the 12 ms allowance are all
unchanged.

## Why the step rate was changed

At 20 ms steps the panel's 19.16 ms refresh outran the input. Each drag's 34
input gaps spanned about 35.5 refreshes, so every drag had to contain one or
two present intervals of two refreshes. Six drags gave 6–12 such intervals out
of 204. The nearest-rank p95 crosses the target at 11. Paired12 recorded 6, 8,
7, and 12; its all-present maximum during motion never exceeded 19.26 ms. The
earlier pass/fail result followed the vsync phase, not render cost. A real
finger reports about 2.5 times per refresh, so the representative workload
always has a new position waiting at each refresh.

## Card results

| Metric | Still, one | Still, three | Video, one | Video, three |
| --- | ---: | ---: | ---: | ---: |
| Frame-update CPU p95 | 4.362 ms | 7.285 ms | 4.166 ms | 6.756 ms |
| Render wall p95 (all committed) | 8.513 ms | 10.292 ms | 7.557 ms | 9.908 ms |
| Motion-to-submit p95 | 18.613 ms | 19.623 ms | 18.633 ms | 19.537 ms |
| Motion-to-present p95 | 27.865 ms | 25.965 ms | 28.109 ms | 26.214 ms |
| Frozen tracking interval p95 | 19.165 ms | 19.164 ms | 19.165 ms | 19.165 ms |
| Tracking interval maximum | 19.175 ms | 38.319 ms | 19.192 ms | 19.286 ms |
| Above-target tracking intervals | 0 / 218 | 1 / 214 | 0 / 216 | 0 / 216 |
| Input dispatch interval p50 / p95 | 8.142 / 11.774 ms | 8.145 / 13.700 ms | 8.142 / 11.422 ms | 8.143 / 13.461 ms |
| Incremental session memory | 6,148,096 B | 8,495,104 B | 4,243,456 B | 11,255,808 B |

All CPU, input, release and session-memory checks pass in every arm. There
are zero excluded input pauses and 516 motion inputs per arm.
[correlation-audit.json](correlation-audit.json) maps every motion to the
first subsequent recorded render with zero disagreements. Three-card render
wall p95 (about 10 ms) still exceeds the normal **8 ms** allowance. The pass
therefore depends on this trial's 12 ms allowance. It says nothing about the
installed 8 ms setting.

The combined [budget-analysis.json](budget-analysis.json) still reports the
overall board-budget gate as `INCOMPLETE`. Its only missing item is "Board
acceptance needs observed DRM at 568x1232 RGB565", the portrait-geometry
check, which this landscape board does not provide. This trial does not
claim that gate.

## Playback, resources, cover, and restoration

The named `handheld-theme-trial.py --workload backgrounds` command completes
with `completed-needs-operator-review`, restoration passed, and
`physical_observation: UNVERIFIED` ([basic-result.json](basic-result.json)).
Its video sample records 77 decoded, submitted and callback frames, and
distinct native captures. Exposed video mean shell/shell-ui CPU is
0.8951 cores against 0.0209 for still, with process RSS peaks of 197,480,448 B
and 163,225,600 B. The decoder runs in the UI service. Sampled peaks can miss
spikes, and summed RSS can count shared mappings more than once.

The opaque Foot cover test reports `paused-covered`, no decoder PID, and
unchanged counters over two seconds. Removing the cover resumes `playing`.
Both video card arms start their gestures in `paused-covered`.

[final-audit.json](final-audit.json) independently verifies the original
system, profile and boot, the normal compositor, landscape, the **8 ms**
allowance, the still wallpaper, journal routing, exact preference bytes, the
app-appearance pointer, removal of the owned fixture and override, an
inactive restore timer, zero injected devices, and active normal services.
The trial makes no permanent change.

## Exact source and commands

Source is `701c1f591d21f71f64404ee1840654c59d138d66`. The compositor is the
same reused candidate `/nix/store/0v1q7r9g3zfkl1g7n12gsir7xkcbvbg3-k230-card-shell-hdmi-trial`
(ELF SHA256 `2778ed3c…`). Nix inputs are unchanged since the
[build receipt](../tracking-elapsed/build-receipt.json). No new build or
image is used.

[prepare-host.py](prepare-host.py) checks every committed paired12 staged file
against `../paired12/paired12-staged-sha256.json`. It then makes only checked
substitutions: fresh owned paths, override `98-touchrate.conf`, restore unit
`k230-touchrate-20261021`, fixture `source3-background-touchrate`, and
`steps=86` in place of `steps=35`. Every tool and asset hash is unchanged;
[staged-sha256.json](staged-sha256.json) lists them all. With the exclusive
board lock:

```sh
ssh -F ~/tmp/k230-coordination/ssh_config.private k230 \
  /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /var/lib/k230/touchrate-20261021/run.py
```

The run is staged as [run-board.py](run-board.py) (installed as `run.py`) and
[collect-board.py](collect-board.py) (installed as `collect.py`). A 720-second
independent restore timer was armed before the override. Raw stderr,
screenshots and rollback contents stay outside Git; their hashes are in
[private-source-receipt.json](private-source-receipt.json). There were no
failed attempts.

## Replay

```sh
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/touch-rate-trial/analyze.py \
  docs/evidence/omarchy-themes/background-video-board-2026-10-21/touch-rate-trial --repo .
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/touch-rate-trial/correlation-audit.py \
  docs/evidence/omarchy-themes/background-video-board-2026-10-21/touch-rate-trial --repo .
```

Both are verbatim copies of the paired12 replay and audit scripts.

## What remains open

Task 3.3 stays open. This is injected native input on the installed board,
not real-finger or optical acceptance. It passes only with a temporary 12 ms
allowance; the installed setting is still 8 ms, and 3-card render wall p95
exceeds 8 ms. The portrait-geometry item in the combined budget gate is not
covered.

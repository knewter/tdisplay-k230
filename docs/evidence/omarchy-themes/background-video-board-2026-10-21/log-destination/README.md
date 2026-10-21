# Journal logging adds measurable cost to the benchmark

The guarded installed-board comparison ran **2026-10-21
15:57:19Z–15:59:44Z**. The same tested compositor and three-card workload
ran with session stderr routed to the journal, an owned local file, and the
journal again. Each arm restarted the session and verified its binary, startup
terminal, original still theme, landscape output, and 8 ms render allowance.
The original normal compositor and logging configuration were restored.

## Results

| Metric | Journal | File | Journal return |
| --- | ---: | ---: | ---: |
| Correlated rendered frames | 195 | 204 | 192 |
| Frame-update CPU p95 | 7.359 ms | 6.677 ms | 7.284 ms |
| Render elapsed p95 | 9.181 ms | 7.150 ms | 9.141 ms |
| Precommit elapsed p95 | 8.484 ms | 6.705 ms | 8.456 ms |
| Commit-return elapsed p95 | 0.864 ms | 0.331 ms | 0.896 ms |
| Render-start lateness p95 | 0.398 ms | 0.086 ms | 0.458 ms |
| Journal service active-phase mean CPU, cores | 0.103509 | 0.000868 | 0.101581 |
| All-present interval p95 during motion | 38.310 ms | 19.163 ms | 38.316 ms |
| Frozen correlated tracking interval p95 | 38.312 ms | 38.315 ms | 38.319 ms |

Routing stderr to a file reduces render p95 by about 2 ms in this sequence;
returning to the journal restores the higher elapsed cost. Journal-service
CPU falls from roughly 10.35% to 0.087% of one core and returns to 10.16%.
This supports benchmark logging overhead as a material contributor to the
earlier [runnable-wait observation](../render-profile/README.md). It does not
identify the owner of every wait, prove causality beyond this short sequence,
or justify changing journal/kernel/compositor priorities. Journal CPU is
global and can include unrelated logs; restart/order/cache effects remain.

The file arm still has a 10.711 ms maximum render, so p95 below 8 ms does not
establish that every render meets the allowance. Log formatting and writes
still happen in all arms. The change is the session stderr destination,
including descriptors inherited by children, rather than a switch that
disables all logging or a compositor-only logging rewrite.

**The performance gate remains failed.** File-arm frozen tracking p95 is
38.315 ms against the unchanged 33.334 ms target. Of its 198 tracking
intervals, 11 exceed that target; five contain an intermediate actual
presentation. The all-present diagnostic has six two-vblank gaps among 203
intervals, versus 14/190 and 12/192 in the journal arms. Its 19.163 ms p95
does not replace the frozen input-correlated metric. All other numeric
CPU/input/release/session-memory checks pass, with zero excluded input pauses.
The reports also preserve their portrait-geometry warning and missing
one-card companion warning: these are three-card diagnostics, not full paired
static/video or one/multiple-card board acceptance. Tasks 3.3 and 4.2 stay
open, and video remains disabled by default.

The next scheduling comparison can use the quieter file destination while
retaining the same telemetry, workload, and frozen thresholds. A scheduling
improvement still needs to pass the original gate; this experiment supplies
no waiver or permanent product configuration change.

## Source and method

[result.json](result.json), [descriptor.json](descriptor.json), and
[log-destination-staged-sha256.json](log-destination-staged-sha256.json)
record source `d90f5943a3c56a180345f74adfc14a7e818100c6`, installed identities,
and all five staged input hashes. The reused compositor package is
`/nix/store/0v1q7r9g3zfkl1g7n12gsir7xkcbvbg3-k230-card-shell-hdmi-trial`,
actual ELF SHA256
`2778ed3cdac48b83806117a8d96accba0163dae21ba12b7a1104f1c1289fa3be`.
Its build source is `1a8e72ac52df5c80540bdeedc22edfcc4e5c167a`; Nix/runtime
inputs are unchanged through `d90f5943`. No new build, full system image,
ordinary boot, or source-level logging optimization is claimed. The earlier
[build receipt](../tracking-elapsed/build-receipt.json) still applies.

Each arm uses the existing persistent native-uinput collector: six alternating
35-motion drags, 700 ms movement each, three Foot cards, unchanged landscape
input mapping, and the same selected app. Before/after native screenshots
remain protected outside Git. No camera, real-finger, or optical performance
proof is claimed here.

The controller [run-board.py](run-board.py) is staged as `run.py` alongside
[collect-board.py](collect-board.py) as `collect.py`,
[cadence_audit.py](cadence_audit.py), the descriptor, and the tested revision's
`card-shell-board-session.py` normalizer. With the exclusive SSH board
reservation, the successful command was:

```sh
ssh -F /home/jadams/tmp/k230-coordination/ssh_config.private k230 \
  /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /var/lib/k230/log-destination-20261021/attempt2/run.py
```

The exclusive override changes only the executable to the same benchmark
candidate and `StandardError` between `inherit` and `append:<owned path>`.
All other logging properties are checked unchanged. File FD 2 must be a
regular file matching the exclusive log's device/inode; journal FD 2 must be
a socket. This verifies actual routing rather than inferring it from a unit
file. Every run is untraced; no ftrace setup or scheduling policy changes occur.

Journal extraction selects the existing telemetry families. File extraction
reads the bounded stderr suffix from the offset taken before benchmark arm,
then applies the same strict normalizer. It consequently includes additional
allowlisted diagnostic families that the journal query prefilters out; the
frozen benchmark rows and correlated timing records are preserved in both.
Private raw stderr is never published. [private-source-receipt.json](private-source-receipt.json)
verifies the file prefix hash at collector return and the final exported file
hash separately, because shutdown appends more lines afterward.

The collector samples the same two session cgroups as before. It additionally
samples journal-service CPU identically in all arms, outside the frozen
two-service session rows. The CPU comparison uses only measured samples
wholly inside the active phase: 44 samples over 11.124/11.081/11.142 seconds.
It neither interpolates phase boundaries nor relabels journal CPU as session
CPU. Cgroup identity, timestamps, and cumulative counters must remain valid.

## Failed first attempt and recovery

The [first attempt](attempt1/failure.json) captured one journal arm, then
failed a controller assertion before collecting the file arm. The controller
expected `StandardError` to serialize as the full `append:<path>` string;
this systemd reports `append` separately. The exact failed
[controller](attempt1/run.py), [collector](attempt1/collect.py),
[result](attempt1/result.json), and journal-arm telemetry/resources remain
committed. Its `finally` restoration completed; the error is not hidden as a
performance failure or a successful three-arm run.

The retry accepts the exact append output type or full append representation,
checks every other property unchanged, and independently requires actual FD
device/inode equality. It uses new occupied-directory guards, staging and
recovery directories, output root, and restore timer. No failed artifacts
were overwritten. Both attempts have an independently armed 480-second root
restoration timer before any session mutation.

[final-audit.json](final-audit.json) independently verifies the original `2ig`
system/profile, `4fc7bf3a…` normal compositor, same boot, original still
generation, landscape, 8 ms allowance, original logging properties, journal
stderr socket, active normal services, absent owned override, zero injected
devices, and both restore timers inactive. The board reservation was released
after export and audit. Boot files, system profile, priorities, and defaults
were not changed.

## Replay and validation

From the repository root:

```sh
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/log-destination/test-log-destination-analyze.py
python3 -m unittest tests.test_card_shell_board_tools
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/log-destination/log-destination-analyze.py \
  docs/evidence/omarchy-themes/background-video-board-2026-10-21/log-destination --repo .
openspec validate --all --strict
python3 tools/blob-scan.py --no-vendor
```

The five new CPU-window tests cover phase clipping without extrapolation,
cgroup replacement, counter resets, clock reversal, and insufficient samples.
The 30 existing board-tool tests include telemetry normalization/privacy checks.
Replay validates normalizer idempotence, all six gestures, unique timing/frame
boundaries and single render attempts, journal sample validity, restoration,
and equality of the frozen tracking count/p95 with the cadence diagnostic.
[destination-analysis.json](destination-analysis.json) and
[budget-analysis.json](budget-analysis.json) retain all results and limits.

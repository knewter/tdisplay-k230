# Elapsed rendering exceeds the 8 ms allowance on some three-card frames

The guarded installed-board probe ran **2026-10-21 05:22:54Z–05:24:16Z**.
It adds benchmark-only wall-clock boundaries to distinguish elapsed work from
CPU charges. It changes no scheduling policy, render allowance, workload,
orientation, theme preference, or acceptance threshold. The original still
background and landscape output remain selected. This is a timing diagnostic,
not a paired-video gate, real-finger test, or optical performance measurement.

## Findings

The same six-drag persistent-uinput workload as the [render-allowance
comparison](../tracking-cadence/README.md) ran with one and three Foot cards.
The normal render allowance remained 8 ms in both arms.

| Metric | One card | Three cards |
| --- | ---: | ---: |
| Correlated rendered frames | 208 | 202 |
| Charged frame-update CPU p95 | 4.491 ms | 7.200 ms |
| Elapsed rendering p95 | 6.515 ms | 8.946 ms |
| Elapsed work before commit call p95 | 6.029 ms | 8.285 ms |
| Commit call elapsed p95 | 0.901 ms | 0.776 ms |
| Render-start lateness beyond requested delay p95 | 0.460 ms | 0.521 ms |
| Elapsed render minus render CPU p95 | 2.562 ms | 2.595 ms |
| Frames whose elapsed rendering exceeds 8 ms | 4 / 208 | 26 / 202 |
| Frozen correlated tracking interval p95 | 38.318 ms | 38.322 ms |
| All-present interval p95 during motion | 19.170 ms | 38.312 ms |

All correlated frames in this probe have one render attempt, so the CPU/wall
comparison does not combine a failed attempt's CPU with another attempt's
elapsed duration. Fourteen three-card frames spend over 8 ms *before* calling
the commit function. CPU budget compliance therefore does not establish that
rendering completes within the compositor's 8 ms scheduling allowance.

This narrows the next investigation to elapsed rendering and competing work,
while retaining commit/timer observations. It does **not** identify which
process, syscall, interrupt, memory access, or scheduler decision accounts for
the non-CPU time. Commit CPU and elapsed return time are not the asynchronous
kernel commit worker's completion latency. No kernel change is justified by
these boundaries alone, and the older failed register-latch patch was not used.

The frozen numeric CPU/input/release/session-memory checks pass in both arms;
tracking still fails the unchanged **33.334 ms p95** target. There are no
excluded input pauses in these two runs. In the one-card arm, nine of twelve
above-budget correlated intervals have an intermediate actual presentation;
in the three-card arm, six of twenty do. The all-present diagnostic does not
replace the frozen input-correlated metric. The parser's portrait-only geometry
warning is preserved because this board remains landscape. Tasks 3.3 and 4.2
remain unchecked; no performance waiver or default video selection follows.

## Instrumentation and identity

Runtime source `8d1eea0bc6b66f7d0ac0dcf15c8c260dd7078071` adds the
`K230_CARD_SHELL repaint-timing` diagnostic. The tested source revision
`1a8e72ac52df5c80540bdeedc22edfcc4e5c167a` adds a distinct-clock host fixture;
its Nix/runtime inputs are identical to `8d1eea0b`. The working branch is
`bg-31-closure`; this source step follows landed comparison `c26c2b27` in the
existing `.claude/worktrees/bg31` worktree.

The records use `CLOCK_MONOTONIC` for the point immediately before Sway's timer
update/immediate render, requested delay, actual render start, commit-call
start, and commit return. Existing process-CPU accounting, benchmark schema,
and frozen thresholds are retained. The new boundaries run only while the
benchmark is armed; the Sway hook otherwise returns without reading a clock.
The probe adds observer overhead while armed, so its measured costs are not
claimed byte-for-byte equivalent to the uninstrumented runtime.

Render-start lateness includes any Sway scene work after requesting its timer,
timer/event-loop dispatch, and scheduling delay. It is not a kernel-only
measurement. An initial already-scheduled frame can have `scheduled_ns=0`;
the analyzer reports its lateness as missing rather than inventing a request
time. Neither arm here had such a partial schedule sample. All 559/524
committed timing records are retained, including frames without input mappings;
the table above selects the 208/202 input-correlated frames explicitly.

[build-receipt.json](build-receipt.json) records the exact selected-package
cross-build, guard order, source, output, and executable hash. The build passed
in 47 seconds after waiting for the shared heavy-work slot:

```sh
nix build .#card-shell-hdmi-trial \
  --out-link /home/jadams/tmp/codex-claude-handoff-20261019/3/cadence-timing-root \
  --print-out-paths --max-jobs 1 --cores 6
```

The candidate is
`/nix/store/0v1q7r9g3zfkl1g7n12gsir7xkcbvbg3-k230-card-shell-hdmi-trial`,
with actual Sway executable SHA256
`2778ed3cdac48b83806117a8d96accba0163dae21ba12b7a1104f1c1289fa3be`.
This is a compositor-package cross-build and temporary installed-board probe;
no new full system image or ordinary boot is claimed for this diagnostic.

## Controller and recovery

The exact driver is [run-board.py](run-board.py), using
[collect-board.py](collect-board.py), [cadence_audit.py](cadence_audit.py),
the descriptor in [result.json](result.json), and the tested source's
`tools/card-shell-board-session.py` fixed-grammar normalizer. The successful
attempt stages these as `run.py`, `collect.py`, `cadence_audit.py`,
`descriptor.json`, and the normalizer under the protected directory below.
With the exclusive board reservation, the operator command was:

```sh
ssh -F /home/jadams/tmp/k230-coordination/ssh_config.private k230 \
  /nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  /var/lib/k230/cadence-timing-trial-20261021/attempt2/run.py
```

The driver refuses occupied recovery/result directories. A future replication
needs new owned staging/recovery directories and a unique restore unit; it must
not borrow a concurrent board reservation. The temporary service override was
protected by the independent root timer
`k230-source3-cadence-elapsed-20261021-attempt2.timer` with a 300-second deadline.
It restarts the normal services after removing only the owned override.

The [first attempt failed](attempt1-failure.json): restarting `shell.service`
removed its `/run/shell` staging directory, so the collector could not run and
the controller could not save its result there. Normal restoration completed
and was independently rechecked; this is not a successful capture. The retry
moves staging and recovery outside that service-owned runtime directory. The
private controller traceback and first recovery record remain preserved.

[result.json](result.json) records candidate identity, both successful
workloads, and restoration. [final-state.json](final-state.json) independently
confirms persistent/current system `2igpibpw…`, the same boot ID, original Sway
SHA256 `4fc7bf3a…`, 8 ms allowance, original still generation, landscape,
only the normal terminal, all three normal services active, zero injected input
devices, and absence of the owned override and active timer. The board lease
was released after export. Candidate/rollback artifacts remain rooted; no
boot payload, system profile, unrelated capture, or other agent's work changed.

## Replay and validation

```sh
python3 -m unittest tests.test_card_shell_telemetry \
  tests.test_card_shell_board_tools tests.test_card_shell_cache_session
python3 docs/evidence/omarchy-themes/background-video-board-2026-10-21/tracking-elapsed/analyze.py \
  docs/evidence/omarchy-themes/background-video-board-2026-10-21/tracking-elapsed \
  tools/card-shell-benchmark.py
```

The 35 host tests pass, including separate wall/CPU clocks, the initial partial
schedule, failed render accounting, and rejection of extra/missing/duplicate/
nonnumeric export fields. They do not establish hardware timing. The board
replay validates monotonic boundaries and unique frame IDs, preserves raw logs,
and derives the two-service resource rows from actual measured samples. It
checks that diagnostic correlated tracking counts/p95 equal the frozen parser.
[elapsed-analysis.json](elapsed-analysis.json),
[cadence-diagnostics.json](cadence-diagnostics.json), and
[budget-analysis.json](budget-analysis.json) retain the full results and limits.

`openspec validate --all --strict` passes all 49 items; the inventory scan
passes with no new binary assets. The [first local site check](site-local-failure.json)
renders all 825 pages and passes link/size checks but fails the unchanged
120-second time limit at 195.11 seconds. Its log/hash and source3 ownership are
preserved. A guarded retry and exact-revision CI publication are checked
separately; this local failure is not converted to a pass.

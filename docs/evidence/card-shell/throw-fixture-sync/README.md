# Wait for fixture classification before the close throw

The board-injected repaint-stage run at revision `58461f518821` recorded
12 of 13 acceptance checks. Its `upward-throw-close-request` check failed.
The source artifacts are
`../repaint-stages/board/run-1/public/acceptance.json` and
`../repaint-stages/board/run-1/public/telemetry.log`, collected
2026-09-23 23:55–23:56 UTC. The run used normal system `gnr36q…` and
package `xv8x9…`. The subsequent persistent Close control did request close;
the client explicitly refused it. This does not prove the throw requested
close.

The acceptance fixture removed `k230_card_unavailable` and immediately
started the throw. The retained shell telemetry is newest first. In event
order, lines 50, 49 and 46 show deck message 3 (unavailable), then dragging
with message 3, then deck message 0 (live) with actions 33 (reconcile and
redraw). The source policy cancels a pressed drag when its card changes
content class. The prior successful injected run's same segment has the
live reconciliation before its series of drag motions and close request
(`../throw-sampling/board/run-1/public/telemetry.log`, lines 67–41).

The fixture now records the selected client's compositor card ID and its
current mirror-event count before clearing the unavailable mark. It waits up
to three seconds for a *new* mirror event for that exact card, which occurs
only after live classification and scene synchronization. If none appears,
setup fails before the throw instead of reporting a gesture outcome. Raw Sway
journal lines carry a timestamp and source prefix, so the count uses the
existing strict telemetry normalizer before matching mirror events. Counting
is independent of the journal's output order and ignores prior mirror events
and other cards. The policy's content-change cancellation, throw thresholds,
twenty-frame input sequence and acceptance cases are unchanged.

Run the narrow host check with `python3 tests/test_card_shell_board_tools.py`.
This is host fixture proof only. The coordinator-owned board repeat below observes all thirteen checks; this
change does not establish real-finger behavior or repair the separate
performance budget failures.


## Retained setup failures and runtime correction

Two coordinator attempts stopped before acceptance and are retained here:

- `failed-runtime-reuse/result.json`: revision `b014cdef` refused the previous
  `/run` directory. It never armed a new compositor session.
- `failed-runtime-guard/result.json` and `run-1/public/run.json`: revision
  `d26ffab0` generated a unique directory with a prefix rejected by the session
  execution guard. No compositor invocation was established. The direct
  restoration path recorded normal shell and seatd active.

Neither attempt ran the corrected throw fixture. Their transfer reports retain
archive hashes; these are setup failures, not failed gesture observations.

Revision `a3fecb7c` generates a unique `/run/k230-card-shell-` directory with an
alphanumeric suffix and checks it against the session helper's actual guard
before creating or arming it. That same helper is copied into the protected
runtime for both compositor/input execution guards and the restore watchdog.
`python3 tests/test_card_repaint_runner.py` passes two host checks covering
unique valid names, socket path length, and continued rejection of the invalid
prefix. The 27 existing session/fixture tests and four cache policy tests also
pass. An independent source review found no new safety gap. These checks do
not substitute for the board repeat below.


## Board repeat after correction

`board/result.json` records the published tools at `a3fecb7c`, running the same
`xv8x9…` compositor package on the normal system from 2026-09-24 00:23:39 to
00:25:23 UTC. All **13 injected checks** were observed, including the upward
throw, explicit refusal, timeout recovery, accepted source exit, live parent
and child surfaces, and persistent control routes. This supports the fixture
classification-race diagnosis; one passing repeat does not prove universal
throw reliability or physical-finger acceptance.

The cost reports still fail:

| Cards | Submitted frames | Update CPU p95 / max | Tracking interval p95 |
| --- | ---: | ---: | ---: |
| One | 137 | 16.531 / 49.230 ms | 57.481 ms |
| Two | 140 | 23.855 / 25.644 ms | 57.485 ms |

The declared CPU limits are 16.667 ms p95 / 33.334 ms maximum; tracking is
33.334 ms p95. Input-to-submit/present, release, and incremental-memory checks
pass, with no missing benchmark evidence. `board/profile.json` correlates all
277 submitted frames to repaint-stage accounting. It is diagnostic profiling,
not an optimization comparison. `board/verification.json` records coordinator
reproduction of the budget and all producer hashes against the published source.
The paired scaled-cache trial is the next performance experiment.

`normal-restoration.json` and its serial transcript independently confirm the
same installed system, normal shell and seatd, associated Wi-Fi and HTTPS,
protected credential permissions, storage capacity and protected boot-file
hashes. The boot ID is unchanged: this check did not reboot or flash. Raw native
captures remain protected on the board; this repeat adds behavioral traces,
not a new visual or camera acceptance claim. Tasks 4.2, 5.1 and 5.3 stay open.


Independent coordinator review reproduced the staged producer hashes and
checked trace ordering: in the newest-first telemetry, unavailable state at
line 69 is followed chronologically by new mirror events for card 7 at lines
66/65, live state at line 64, drag at lines 62–42, and close request at line 41.
This establishes reconciliation before this injected throw.

The one-card CPU outlier is frame 167: 49.230 ms total includes 33.468 ms of
aggregate input work across five coalesced motion events and 15.537 ms of
render work. It does not identify a single slow motion callback. A next input
profile should subdivide policy and scene synchronization inside the existing
charged interval, preserving the total CPU accounting and declared limits.

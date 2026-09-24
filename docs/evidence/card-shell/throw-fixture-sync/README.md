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
This is host fixture proof only. A coordinator-owned board-injected repeat
of the same thirteen checks remains required; this change does not establish
real-finger behavior or repair the separate performance budget failures.

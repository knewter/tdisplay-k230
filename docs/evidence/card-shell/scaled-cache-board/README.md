# Paired scaled-cache board trial: measured, keep disabled

`run-board.py` performs one cache-off arm followed by one cache-on arm against
the same `/nix/store/hxilq8jdlb0b8mj8jzmvhwsw9mwnr69y-k230-card-shell`
package. It preserves the normal system, Sway configuration, two fixture
clients, Pixman auto policy, 13 injected acceptance cases, and each workload's
24 independent drags. It uses the unchanged declared budget parser. Each arm
has its own protected runtime, 540-second compositor limit, recovery timer,
raw captures, public text reports, budget, session manifest, and restoration
record. An acceptance failure is retained and the next arm still runs after
normal shell and seatd restoration. A setup, collection, or restoration error
stops the pair while retaining its partial files.

The runner was reviewed and then executed on the board; results follow below.
No performance improvement is claimed. Injected input and native captures do not establish
real-finger feel or optical latency. The result remains a measurement of task
4.2, not automatic acceptance; both budget gates and every interaction case
must be reviewed.

On the reserved normal board, stage this runner beside the published
`card-shell-board-session.py`, `card-shell-acceptance.py`, and
`card-shell-benchmark.py`. Compare all four SHA-256 values against the reviewed
source files before running. Use a fresh revision-specific output directory;
the runner refuses to overwrite a prior attempt. An outer systemd deadline of
at least 1,320 seconds covers both 540-second arm limits and restoration.

| Staged basename | SHA-256 |
| --- | --- |
| `run-board.py` | `d293ceb51abdcc7acfd02f1635e6ca70a635c9acd190359b7c8f0d1dcd65e4fc` |
| `card-shell-board-session.py` | `a179bb4b190550b01146876293ee20189de6c10816aab10a9e78d7b310f8b3a3` |
| `card-shell-acceptance.py` | `2140a8771b0b5677cfc1dc348d47e6b0cd86cfb6e03c09fd049498320ce8e574` |
| `card-shell-benchmark.py` | `ce547d2d675de8cc858c08223685eb0669815de963d544439a886771482be4a0` |

```sh
python3 /var/lib/k230/card-scaled-cache-tools-REVISION/run-board.py \
  --board --revision FULL_PUBLISHED_REVISION \
  --output /var/lib/k230/card-scaled-cache-REVISION
```

The operator must separately verify normal system identity and service,
storage, Wi-Fi, and HTTPS restoration after the paired run. Keep `raw/`
captures and `process-private.log` protected on the board; review public
exports before committing evidence. A failed attempt stays available in its
own output directory. Task 4.2 remains open until physical evidence is
collected, audited, and committed.


## Physical paired result

Published producer revision `ec838d9c38ffdecca3e45d72d58852b66f7c5ebc` ran the
same `hxilq8…` package with cache **off**, then **on**, on 2026-09-24 UTC:
00:30:09–00:31:54 and 00:31:54–00:33:40. Both arms observed all 13 injected
interaction checks. Both still fail the declared CPU and tracking budgets.
The benchmark workload, renderer, native 568×1232 RGB565 output, source fixture,
normal kernel and accepted limits were unchanged. This is one ordered pair;
it does not quantify run-to-run variation or every application's behavior.

| Cards | Cache | Submitted frames | Update CPU p95 | Update CPU max | Tracking interval p95 |
| --- | --- | ---: | ---: | ---: | ---: |
| One | Off | 127 | 16.773 ms | 49.181 ms | 57.483 ms |
| One | On | 201 | 18.685 ms | 50.739 ms | 57.479 ms |
| Two | Off | 146 | 23.533 ms | 25.658 ms | 57.481 ms |
| Two | On | 188 | 24.788 ms | 37.004 ms | 57.481 ms |

CPU limits remain 16.667 ms p95 / 33.334 ms maximum; the tracking p95 limit is
33.334 ms. The enabled mode increased p95 update CPU by about 11.4% with one
card and 5.3% with two in this pair. It did not improve tracking cadence.
Input-to-submit/present, release recovery and incremental memory passed in
both modes. The enabled mode produced more submitted frames, so comparison
is of the same input workload rather than a one-to-one frame pairing.

Cache use was observed: 10,132 cumulative sync hits, 2,216 misses and 10,506
fallbacks, with at most 776,240 cached pixel bytes and zero retained bytes in
the final recorded cache row. These counters identify sync decisions, not
submitted pixel samples or saved CPU. The enabled incremental session-memory
peaks were 843,776 and 790,528 bytes, below the 64 MiB limit. The off mode
emitted no cache diagnostic rows. Session manifests independently preserve the
requested off/on policy. No instrumentation or accepted cost boundary was moved.

**Decision:** keep this cache off in the normal and experimental defaults.
This pair does not establish a useful optimization for the required animated
live-card workload. A targeted static-content case could behave differently,
but it would not replace the live-card acceptance workload. The initial
one-card input CPU spike remains a separate profiling target. Task 4.2 stays
open, and this experiment does not satisfy image or real-finger acceptance.

`board/comparison.json` contains the condensed result. Each arm retains its
acceptance, manifests, complete normalized telemetry, independently reproduced
budget, repaint profile, and post-restoration session export. The coordinator
verified all four producer hashes against the published revision and reproduced
the budget reports exactly except for their generation timestamp. The profiles
correlate all 662 submitted frames; neither frame-count nor cache-hit count is
a claim of better responsiveness.

`normal-restoration.json` and its sanitized serial transcript independently
confirm the same installed system, shell and seatd, Wi-Fi association and HTTPS,
protected credential permissions, storage capacity and protected boot hashes.
The boot ID is unchanged; this experiment did not reboot or flash. No physical
finger or optical latency proof was obtained.


## Native capture review

Eight hash-matched fixture captures are committed under each arm's `captures/`:
[two visible cards, off](board/run-1-off/captures/two-live.png) and
[on](board/run-2-on/captures/two-live.png),
[held drag, off](board/run-1-off/captures/during-drag.png) and
[on](board/run-2-on/captures/during-drag.png),
[private state, off](board/run-1-off/captures/private.png) and
[on](board/run-2-on/captures/private.png), and
[close timeout, off](board/run-1-off/captures/close-timeout.png) and
[on](board/run-2-on/captures/close-timeout.png).
The coordinator reviewed all eight: both synthetic parent/child images remain
visible in the deck and held drag; private cards show no source pixels/title;
the refused app remains with timeout feedback and recovery controls. These are
native captures during injected input. The clients animate independently, so
the off/on images are not frame-synchronized pixel-equivalence tests. The
fixture's visible buttons and unfinished visual style are the existing test
shell, not the newer gesture-first design proposal or an acceptance of its UX.

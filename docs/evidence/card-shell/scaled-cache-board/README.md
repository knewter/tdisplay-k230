# Paired scaled-cache board trial: pending physical proof

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

This file and runner are host preparation only. No board result or performance
improvement is claimed. Injected input and native captures do not establish
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

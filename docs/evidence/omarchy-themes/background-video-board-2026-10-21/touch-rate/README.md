# Real-finger touch report rate

**Evidence class: real glass interaction** (operator's finger on the
installed board), read as raw kernel input events over SSH. No camera
observation; no board state was changed.

On 2026-10-21 the operator dragged one finger across the K230 glass during a
120-second capture window. The window started at board monotonic
66317.107 s; the first recorded event is at 23:39:57Z (kernel event clock).
[capture-board.py](capture-board.py) read `/dev/input/event1` ("Goodix
Berlin Capacitive TouchScreen") and stored each `input_event` as
`microseconds type code value` in [goodix-events.txt](goodix-events.txt)
(3,062 events). The `goodix-berlin` interrupt count rose from 4,568 to 5,466
across the window. An earlier 180-second window recorded zero events because
nobody touched the glass then; it is not used.

[analyze.py](analyze.py) splits strokes at `BTN_TOUCH` and measures the gap
between consecutive `SYN_REPORT`s that carry a position change:

```sh
python3 analyze.py goodix-events.txt
```

| Measure | Value |
| --- | ---: |
| Strokes | 11 |
| Moving-report gaps | 710 |
| Median gap | 8.122 ms |
| p5–p95 gap | 8.06–8.19 ms |

Per-stroke maxima of 32–187 ms happen while the finger rests without moving.
The controller then sends no report, so these gaps are not part of the moving
cadence. See [analysis.txt](analysis.txt).

## Why this matters for task 3.3

The paired card trials injected one motion every 20 ms (35 steps over
700 ms). The panel presents every 19.16 ms. Each drag's 34 input gaps
therefore span about 35.5 refreshes, so every drag must contain at least one
present interval of two refreshes (38.3 ms), and often two. Across six drags
that gives 6–12 such intervals out of 204. The frozen nearest-rank p95 reaches
38.3 ms at 11 or more. The committed paired12 data show 6, 8, 7, and 12
(`../paired12/correlation-audit.json`). A real finger reports about 2.5 times
per refresh, so a refresh with no new input should not occur during a real
drag.

The operator chose to keep the 33.334 ms target and the metric, and to match
the injected step interval to this measured rate. The follow-up trial uses
86 steps over the same 700 ms drag (8.14 ms per step). Nothing else changes.
This capture covers one operator, one session, and horizontal drags only.

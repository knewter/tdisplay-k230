# The hiding keyboard uncovers the app

**Evidence class: board, injected native touch, grim captures.** All runs
were taken on 2026-10-26 between 03:18 and 03:30 UTC, on one boot
(`ec5fc197…`), on the board's DSI panel in landscape: 1232x568 logical
pixels, 52.19 Hz, `max_render_time 12`, one online CPU. There was no real
glass and no camera. Operator confirmation on glass is a separate, open task
of `the-hiding-keyboard-uncovers-the-app`.

## What the operator saw

Sliding the keyboard down showed a light, opaque strip between the app's
bottom edge and the keyboard grip. That strip is `ordinary_backdrop`, the
card-coloured rect behind ordinary apps (`nix/card-shell/adapter.c`).

## Probes

[`hide-probe.py`](hide-probe.py.txt) opens a Foot window that prints 60
numbered lines, so the app's pixels reach its bottom edge. It shows the
keyboard, then runs:

- a slow grip hide (1500 ms), grabbing with grim at 150, 500 and 900 ms;
- a drag 80 px down, held 300 ms and grabbed, then released downward;
- a hold-and-reverse, grabbed after it settles shown;
- an ordinary hide (350 ms).

A sampler thread logs the app container's height from `swaymsg get_tree`
every 50 ms. grim takes 0.5–1.7 s to finish on this board, so later grabs in
the slow hide land after release. Only `slow-0` and `held-80` show the
keyboard in motion or held.

[`strip.py`](strip.py.txt) finds the grip in each capture and counts the
light rows directly above it at x=1000, where the app is Foot's dark
background. The captures themselves are not committed.

| Probe | System | `slow-0` light rows | `held-80` light rows |
| --- | --- | ---: | ---: |
| [hp-k](probe/hp-k) | `dl2bzq4m`: app grows first (`kg_reserved`) | 130 | 84 |
| [hp-c](probe/hp-c) | `dwdcnvqb`: also commits the pending resize | **0** | **0** |

At rest with the keyboard shown, both builds measure 4 light rows at the
app's 272 px bottom edge, in `shown` and `reversed`.

## Why growing first was not enough

In hp-k, `get_tree` already reported the app at 568 px during the hide, yet
the app's pixels stopped at its old 272 px. [`nop-probe.py`](nop-probe.py.txt)
held the keyboard 80 px down and grabbed `held-a`. It then sent
`swaymsg nop` (sway commits dirty transactions after each IPC command) and
grabbed `held-b`. The result is in [np-k](probe/np-k): 84 light rows before,
0 after.

The cause is in `ordinary_sync_usable`:

- `arrange_layers` calls it with `commit` false and it records the new usable
  area;
- the per-frame call from `prepare_impl` then saw an unchanged area and
  returned before it reached `transaction_commit_dirty`.

So during a keyboard drag the app's resize waited for some unrelated event,
and the backdrop filled the gap. This predates `kg_reserved`. The fix carries
a resize that was not yet committed (`ordinary_resize_pending`) to the next
call that may commit, normally the next frame.

## Bench

[`measure.sh`](../compositor-repaint/measure.sh.txt), unchanged: a 30 s drawer
scroll, then eight keyboard cycles with the compositor benchmark armed. The
runs were made in the order kc1, kb1, kc2, each after a test-activation and
a shell restart.

| Run | System |
| --- | --- |
| [run-kb1](run-kb1) | `h4rqzlgr` (boot default) |
| [run-kc1](run-kc1), [run-kc2](run-kc2) | `dwdcnvqb` |

Cells give the presented interval median / p95 in ms, then the render wall
median / p95 in ms.

| Phase | kb1 | kc1 | kc2 |
| --- | --- | --- | --- |
| Show, contact | 19.2 / 172.5, 8.2 / 16.0 | 19.2 / 172.5, 8.2 / 16.1 | 19.2 / 172.4, 8.1 / 16.0 |
| Show, settle | 38.3 / 57.5, 12.1 / 12.8 | 38.3 / 57.5, 12.2 / 12.8 | 19.2 / 57.5, 11.8 / 12.9 |
| Hold and reverse, contact | 19.2 / 57.5, 7.1 / 8.4 | 19.2 / 38.3, 7.9 / 11.9 | 19.2 / 38.3, 7.8 / 12.1 |
| Hold and reverse, settle | 38.3 / 76.7, 7.9 / 14.1 | 38.3 / 76.6, 7.8 / 12.7 | 38.3 / 76.6, 7.8 / 12.3 |
| Hide, contact | 19.2 / 19.2, 6.2 / 8.2 | 19.2 / 19.2, 6.9 / 10.5 | 19.2 / 19.2, 6.9 / 10.5 |
| Hide, settle | 19.2 / 115.0, 3.7 / 9.0 | 19.2 / 115.0, 4.2 / 4.3 | 19.2 / 115.0, 4.2 / 4.3 |
| Drawer, distinct fps / sway repaint median | 23.7 / 10.23 | 23.9 / 10.11 | 23.9 / 10.17 |

- **No presented-interval median got worse.** Show settle varies between
  runs of the same build (38.3 and 19.2 ms) as it did in keyboard-blend; its
  render median sits at the 12 ms allowance either way.
- **Hide contact costs more to render** (6.2 → 6.9 ms median, p95 8.2 →
  10.5 ms): the app is now drawn at full height behind the keyboard.
- **Hold-and-reverse contact** has a better interval p95 (57.5 → 38.3 ms) but
  a higher render p95 (8.4 → about 12 ms). It also presents fewer frames
  (311 against 270 and 279), because the app now resizes during the drag.

## Limits

- Injected touch skips the Goodix interrupt and driver path.
- grim captures one composited frame per grab; the one or two frames before
  the app's first full-height commit were not captured, and the backdrop can
  still show there.
- Only Foot was used as the app. A client slow to answer a configure shows
  the backdrop for longer.
- Presentation time is not photon time.

Owned files under `/var/tmp` were removed.

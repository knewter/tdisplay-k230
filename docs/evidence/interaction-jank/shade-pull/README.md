# Notification-shade pulls after the compositor change

**Evidence class: board, injected native touch.** All captures were taken on
2026-10-22 on the board's DSI panel in landscape: 1232x568 logical pixels,
52.19 Hz (19.16 ms per refresh), `max_render_time 12` unless noted, one
online CPU. There was no real glass and no camera.

## Workload

[`shade-pull.py`](shade-pull.py.txt) is derived from the drawer workload. It
drives a persistent uinput touchscreen at the measured real-finger report rate
(8.14 ms). Each of 10 pulls:

1. starts one contact in the top edge band, at y 4;
2. drags it down 400 px over 400 ms and releases;
3. leaves the shade open for 1.5 s;
4. hides it with `k230-shell-rust --surface hide`, then pauses 1 s.

[`run.sh`](run.sh.txt) runs the workload and then
[`cadence.py`](../drawer-profile/cadence.py.txt), which reports frames
presented during contact. For n3 and later it also armed the compositor
benchmark. [`gaps.py`](gaps.py.txt) reports presented-frame gaps from the
start of each pull until 600 ms after release; its output is in
[`gaps.txt`](gaps.txt).

| Run | Build | Notes |
| --- | --- | --- |
| [base](run-base) | `g2yjvzv4` | boot default after the compositor change |
| [n](run-n), [n2](run-n2), [n3](run-n3) | `sgjam1h0` | `k230-settings status` without `pgrep`, test-activated; n3 with the compositor benchmark |
| [n-mrt15](run-n-mrt15), [n-mrtoff](run-n-mrtoff) | `sgjam1h0` | `max_render_time` 15 / off at runtime, restored to 12 afterwards |

## The `pgrep` cost

[prof-base](prof-base/flamegraph.svg) profiled the shell's processes and
their children during the 10 pulls on `g2yjvzv4`. `pgrep` used 789 ms of
sampled CPU, about 79 ms per pull. The native status helper, `k230-settings`
and `k230-settings-s`, used 282 ms between them.

The helper (`nix/settings-status.c`) ran `pgrep -u UID -x wvkbd-mobintl` to
decide whether to offer the keyboard toggle. procps reads every `/proc` entry
in full, and its stacks show glibc loading gconv modules to compile its
regular expression.

The replacement reads each `/proc/PID/comm`. Only for a name match does it
read `status`, to compare the effective UID. Host tests check it against a
fake `/proc` (`tests/test_settings_status.py`).

On the board, as the `shell` user, five consecutive `k230-settings status`
calls averaged:

- **old wrapper** (`kdc5bmnq…-k230-settings`): 103 ms per call;
- **new wrapper** (`q50zzfy1…-k230-settings`): 28 ms per call.

Both reported the keyboard as `action`, with wvkbd running.

## Results

| Run | Distinct fps in contact | Interval median / p95 | Client callback → commit median | Pull + 600 ms: median / p90 / max gap | Sway repaint median |
| --- | --- | --- | --- | --- | --- |
| base | 33.4 | 22 / 32 ms | 21 ms | 23 / 38 / 53 ms | not armed |
| n | 33.6 | 24 / 38 ms | 6 ms | 33 / 38 / 50 ms | not armed |
| n2 | 33.2 | 33 / 38 ms | 5 ms | 34 / 38 / 53 ms | not armed |
| n3 | 34.8 | 20 / 37 ms | 7 ms | 22 / 36 / 39 ms | 13.1 ms, 699,776 px every frame |
| n-mrt15 | 34.8 | 20 / 38 ms | 20 ms | — | 13.0 ms |
| n-mrtoff | 34.3 | 22 / 33 ms | 18 ms | — | 13.0 ms |

- **What removing `pgrep` changed.** The client now commits within 5–7 ms of
  its frame callback, down from 21 ms. Each status read costs about 75 ms
  less CPU.
- **What it did not change: presented cadence.** Before and after, presented
  frames run at about 34 fps, with gaps of at most 38–53 ms (two refreshes,
  occasionally three).
- **Why.** The shade moves the whole screen every frame, so sway's full-screen
  repaint (13.1 ms) plus the client's draw (about 6 ms) is about one 19.16 ms
  refresh of CPU on the one core.
- **`max_render_time` is not the limit.** Setting it to 15 or off made sway
  repaint more often, without more distinct presented frames.
- **The original stutter report.** That report recorded 77 ms median gaps.
  The base run, on the compositor change already promoted
  (`docs/evidence/interaction-jank/compositor-repaint/`), shows that most of
  that stutter was already gone before this change.
- **What would make the shade faster.**
  - Sway's remaining cost is blending the translucent shade over the layers
    beneath, plus the quarter-turn.
  - An opaque region on a sliding surface is excluded by the operator's
    2026-10-22 decision, so the next step would need a cheaper full-screen
    composite or a change in what the shade redraws.

## Limits

- Injected touch skips the Goodix interrupt and driver path.
- Presentation time is not photon time.
- Only landscape was measured.
- Contact windows are short (0.4 s per pull), so the gap columns include the
  settle as well.
- The helper timings come from one five-call loop for each wrapper, not a
  repeated distribution.

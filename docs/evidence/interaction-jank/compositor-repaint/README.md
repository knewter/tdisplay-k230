# Compositor repaint: iterations and re-measurement

**Evidence class: board, injected native touch.** All captures were taken on
2026-10-22 on the board's DSI panel in landscape: 1232x568 logical pixels,
52.19 Hz (19.16 ms per refresh), `max_render_time 12`, one online CPU. There
was no real glass and no camera.

Every run used [`measure.sh`](measure.sh.txt) with the compositor benchmark
armed (`card_shell benchmark injected` … `benchmark-stop`):

- a 30 s [drawer scroll](../drawer-scroll/drawer-scroll.py.txt), analysed with
  [`cadence.py`](../drawer-profile/cadence.py.txt);
- then eight [keyboard cycles](../keyboard/keyboard-cycles.py.txt) with
  `--bench`, analysed with [`analyze.py`](../keyboard/analyze.py.txt).

Each build was test-activated with `switch-to-configuration test`. Builds are
named by store prefix (`nixos-system-nixos-26.11.20260919.20b1ddd`).

| Run | Build | Change from the previous step |
| --- | --- | --- |
| [base](run-base) | `z1basiwi` | installed boot default, sway `-d` |
| [h-nodebug](run-h-nodebug) | `91iprygq` | sway without `-d` |
| [i-opaque](run-i-opaque) | `ca29br25` | + drawer opaque region from opaque sheet rows |
| [j-wvkbd](run-j-wvkbd) | `78gdnf6a` | + wvkbd opaque region (**rejected**, see below) |
| [k](run-k) | `hzn9lp4a` | h + i, plus an RVV quarter-turn for RGB565 |
| [k-rr](run-k-rr) | `hzn9lp4a` | k with sway set to `SCHED_RR` 1 at runtime by `chrt` |
| [l](run-l) | `rcysj8dp` | h + i + `LimitRTPRIO=1`: sway sets `SCHED_RR` itself |
| [m](run-m) | `g2yjvzv4` | h + `LimitRTPRIO=1` only (the change as landed) |

## Results

Sway repaint is `repaint-timing` from `start_ns` to `commit_start_ns`.
Keyboard cells give the presented interval median / render wall median, in ms.

| Run | Drawer distinct fps | Drawer interval median / p95 | Drawer sway repaint median (p10–p90) | Kbd show contact | Kbd show settle | Kbd hold-reverse contact | Kbd hide contact |
| --- | --- | --- | --- | --- | --- | --- | --- |
| base | 17.5 | 38 / 39 | 18.4 (15.6–20.0) | 76.6 / 32.8 | 57.5 / 40.1 | 38.3 / 22.5 | 38.3 / 19.7 |
| h-nodebug | 18.1 | 38 / 39 | 13.6 (11.4–15.7) | 76.6 / 42.6 | 57.5 / 42.3 | 38.3 / 22.8 | 38.3 / 20.1 |
| i-opaque | 18.1 | 38 / 39 | 13.8 (11.4–16.4) | 76.6 / 45.0 | 57.5 / 40.7 | 38.3 / 23.1 | 38.3 / 19.5 |
| j-wvkbd | 18.0 | 38 / 39 | 14.0 (11.6–15.9) | 57.5 / 38.4 | 38.3 / 20.7 | 38.3 / 13.2 | 38.3 / 14.5 |
| k | 17.9 | 38 / 39 | 14.7 (12.2–16.6) | 76.6 / 47.2 | 57.5 / 43.5 | 38.3 / 24.1 | 38.3 / 21.3 |
| k-rr | 23.2 | 22 / 39 | 10.9 (10.8–10.9) | 38.3 / 9.3 | 38.3 / 17.1 | 19.2 / 10.1 | 19.2 / 9.1 |
| l | 24.1 | 21 / 39 | 10.2 (10.1–10.3) | 19.2 / 8.2 | 38.3 / 16.3 | 19.2 / 9.9 | 19.2 / 8.8 |
| **m** | **23.4** | **21 / 39** | **10.2 (10.1–10.3)** | **19.2 / 8.0** | **38.3 / 16.1** | **19.2 / 9.8** | **19.2 / 8.6** |

Against the budgets:

- **Drawer.**
  - On m, sway's repaint fits the 12 ms allowance.
  - The median presented interval, 21 ms, is within the 33.334 ms card budget.
  - p95 is still 39 ms, two refreshes, so some frames still miss one refresh.
- **Keyboard contact phases.** Show, hold-reverse and hide now present every
  refresh (19.2 ms), within the budget.
- **Keyboard show settle: still a miss.** Its 16.1 ms render exceeds the 12 ms
  allowance, and it presents at 38.3 ms.
- **Keyboard typing:** not in this comparison (one-off key commits).

## What each step showed

- **Debug log off (h).** The drawer repaint median fell from 18.4 to 13.6 ms,
  but presentation did not move.
- **Drawer opaque region (i): no gain, dropped.**
  - The active theme draws the sheet at alpha 0.95, so no sheet row is fully
    opaque and the drawer never declares a region.
  - The code was removed again before m. Its patch was kept only in the
    session scratchpad.
- **wvkbd opaque region (j): rejected.**
  - It roughly halved keyboard renders.
  - The operator rejected it on 2026-10-22: an opaque region "once you start
    sliding the keyboard down … looks bad".
  - It is not in any later build.
- **RVV quarter-turn (k): no gain, dropped.**
  - In isolation it halved the turn: [`turn-bench.c`](turn-bench.c.txt) on the
    board, into heap memory, for the 1232x418 drawer band:
    - scalar 10.3 ms;
    - RVV with 32-row tiles 4.5 ms;
    - pixel-identical output.
  - In sway it did not help. The profiles' sampled turn time was 693 ms in
    [prof-i-drawer](prof-i-drawer/flamegraph.svg) and 819 ms in
    [prof-k-drawer](prof-k-drawer/flamegraph.svg), for the same workload.
  - The destination is the scanout buffer, so writes to it, not instruction
    count, set the cost. The patch was not kept.
- **Realtime priority (k-rr, l, m): the gain.**
  - sway asks for `SCHED_RR` at priority 1 (`sway/realtime.c`). Until now the
    journal logged `Failed to set scheduling priority to 1`, because the unit
    had `LimitRTPRIO=0`.
  - prof-k-drawer shows the cost of losing that request. sway used about
    7.5 ms of CPU per presented frame (2,854 ms sampled over 20 s), yet its
    repaint took 14.7 ms of wall time. On one CPU, the clients it was
    compositing preempted it.
  - With `LimitRTPRIO=1`, sway runs as `SCHED_RR` 1 from start, and the
    children it forks (`swaybg`, `foot`) are `SCHED_OTHER`; this was checked
    with `chrt -p` on l.
  - Kernel 7.3's fair server reserves 50 ms per second for ordinary tasks
    (`/sys/kernel/debug/sched/fair_server/cpu0`). `sched_rt_runtime_us` equals
    the period on this kernel.

## Where the rest goes

[prof-m-kbd](prof-m-kbd/flamegraph.svg) profiled keyboard cycles on m. Of
sway's samples:

- `rvv_composite_over_8888_0565`, blending wvkbd's ARGB surface: 40%;
- `k230_turn_copy_rect`: 21%;
- `k230_rgb565_blit`: 8%.

Removing the blend needs an opaque keyboard region, which is rejected. The
turn is bound by scanout writes. Remaining gains are therefore small or need
an operator decision, so the iterations stop here, as the operator asked.

## Grim checks

Each drawer run took `drawer-open`, `mid-scroll` and `after-close` captures,
and each keyboard run took `before`, `shown` and `hidden`. They are not
committed. The m and l drawer captures show the drawer with its search chrome
and grid intact, the same pixels as on k.

## Limits

- Injected touch skips the Goodix interrupt and driver path.
- Presentation time is not photon time.
- Only landscape was measured.
- Sampling distorts timing on one CPU, so timing comes from the unprofiled
  runs.
- The first l extraction of the drawer journal used a local-time window that
  missed the run. It was re-extracted by epoch window
  (`journalctl --since @1792651536 --until @1792651575`), and `measure.sh` now
  uses an epoch `--since`.
- The m drawer journal used the fixed script.

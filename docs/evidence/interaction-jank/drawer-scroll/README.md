# Sustained app-drawer scroll on the installed board: about 10 frames per second

**Evidence class: board, injected native touch.** A persistent uinput
touchscreen sent one report every 8.14 ms, the measured real-finger rate
([touch-rate](../../omarchy-themes/background-video-board-2026-10-21/touch-rate/README.md)).
There was no real-glass interaction and no camera recording for this
measurement.

The runs took place on 2026-10-22 between 03:23Z and 03:37Z. The system was
`/nix/store/8xkkpma4fvgw4fi6pl8qaz7d9d75kcdi-nixos-system-nixos-26.11.20260919.20b1ddd`,
the persistent profile installed by
[the 12 ms allowance change](../../omarchy-themes/background-video-board-2026-10-21/installed-12ms-trial/README.md).
Output DSI-1 was in landscape (1232x568, transform 270) with
`max_render_time 12`. One CPU was online, and 19 apps were in the drawer.

## Result

The drawer misses its ~20 ms target, and also exceeds the top of the design's
17.3–34.6 ms estimate
([app-drawer review §3.4](../../../design/app-drawer-review.md)).

| Run | `K230_DRAWER_FRAME ms=` during contact, median / p95 / max | Samples | Presented frames per second during contact | Frame interval within one drag, median / p95 |
| --- | ---: | ---: | ---: | ---: |
| run2 | 38.86 / 53.35 / 57.65 ms | 72 | 8.31 | 97.4 / 118.4 ms |
| run3 | 39.49 / 53.37 / 75.78 ms | 72 | 8.35 | 95.3 / 110.0 ms |
| run4 | 39.06 / 52.88 / 54.73 ms | 72 | 8.35 | 97.2 / 111.4 ms |
| run6 (traced, 30 s) | 39.56 / 52.64 / 55.25 ms | 36 | 8.35 | 100.7 / 124.7 ms |

**Every one of the 252 contact samples is over 34.6 ms.**

- The `ms=` value is the wall time of `RendererCache::draw` (render cost),
  rate-limited to one sample every 500 ms. On this single-CPU board it
  includes any time the client is pre-empted.
- The presented-frame columns come from the client's own `frame-done` log
  lines, which are the compositor's frame callbacks.
- In every run, every injected touch step was delivered as a `touch-move`
  (3,408 per 60 s run).
- The frame that opens the drawer takes 9.6–10.5 ms, so the cost appears only
  once scrolling starts.

CPU over the 60.6 s of run4, of which 31.4 s was contact (fractions of the
one core): `shell-ui` 0.291, sway 0.098, `systemd-journald` 0.031, injector
0.016. Whole-system busy time was 0.481. Almost all of that load falls inside
the contact windows, so the core is close to saturated while the finger is
down.

## Where the time goes (traced run6)

The installed client's opt-in recorder (`runtime_trace.rs`, thread-CPU and
wall time per span) was enabled with a volatile drop-in for one 45 s window.
Over the 15.7 s of contact, with no dropped events
([trace-analysis.json](run6/trace-analysis.json)):

- **All 154 drawer frames rendered during contact did a full `scene_rebuild`**
  (median 33.8 ms thread CPU, 49.4 ms wall). The cause is in
  `RendererCache::draw_with_hud` (`nix/rust-shell-client/src/render.rs`): any
  scroll change of 0.25 px or more takes the rebuild path. That path allocates
  a new full-screen buffer and repaints the whole drawer sheet: clear,
  background brush, grid slice from `DrawerGridCache`, and chrome. The grid
  cache does what the design intended, but the scene around it is rebuilt on
  every scroll frame.
- The client's main thread used 55.6% of contact time in total: 56.6 ms of
  CPU per rendered frame. Of that, 32.8 ms was `render_total`. The remaining
  ~23.5 ms per frame was Wayland dispatch outside rendering, which covers
  delivering about 110 touch events per second. The recorder does not
  attribute this further. The client writes one `touch-move` journal line per
  event (`main.rs`); that is a candidate cost, not a measured one.

## Workload and commands

[drawer-scroll.py](drawer-scroll.py.txt) is run as root under the exclusive
board lock:

```sh
flock -n /tmp/k230-board.lock "$PY" drawer-scroll.py RUN_DIR "$SYSTEM" 60
```

`$PY` is the system closure's python3. The script:

1. Checks the installed system and the landscape output.
2. Opens the drawer with `k230-shell-rust --surface drawer`.
3. Repeats four drags at x=616 for the given duration, with 600 ms between
   them:
   - a 250 ms flick from y=470 to y=130;
   - the same flick back;
   - a 900 ms drag from y=450 to y=150, held for 150 ms;
   - the same slow drag back.
4. Closes the drawer with `--surface hide`.
5. Saves gesture windows, cgroup CPU counters (from run3 on), grim captures,
   and the `shell-ui` journal.

[analyze.py](analyze.py.txt) replays each run:

```sh
python3 analyze.py.txt runN
```

[traced-run.py](traced-run.py.txt) wraps a 30 s workload. It writes
`/run/systemd/system/shell-ui.service.d/90-drawer-jank-trace.conf`
(`K230_TRACE_PATH`, `K230_TRACE_SECONDS=45`) and restarts `shell-ui` once. It
then removes the drop-in and restarts `shell-ui` normally. The sway PID was
unchanged (1049) throughout. [trace-analyze.py](trace-analyze.py.txt) replays
the trace:

```sh
python3 trace-analyze.py.txt run6 run6/trace.json
```

Captures from run4 show the drawer open ([drawer-open.png](run4/drawer-open.png)),
scrolled ([mid-scroll.png](run4/mid-scroll.png)) and closed afterwards
([after-close.png](run4/after-close.png)).

## Discarded and failed attempts

- **run1 (discarded):** the first injector busy-waited between 8.14 ms steps.
  On a one-CPU board that steals time from the client being measured, and
  render samples read 73–123 ms. The data is kept in [run1](run1/) and must
  not be used. The script now sleeps between steps.
- **run5 (failed, no data):** the trace directory under `/var/lib/k230` was
  not traversable for the `shell` user, and the client logged `trace
  unavailable: Permission denied`. The wrapper still removed its drop-in and
  restarted `shell-ui` normally ([manifest](run5-failed/manifest.json)).
  run6 put the trace under `/var/tmp`.

Owned board files (`/var/lib/k230/drawer-jank`, `/var/tmp/drawer-jank-*`)
were removed afterwards. Both services were active, and no `shell-ui` drop-in
remained.

## Limits

- Injected touch skips the Goodix interrupt and driver path; a real finger
  adds that cost.
- The `ms=` probe is render wall time only. Presentation latency
  (motion-to-photon) was not measured.
- Only landscape was measured; portrait was not.
- The drawer held 19 apps, and no search query was active.

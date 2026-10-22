# On-screen keyboard show, type, hold/reverse and hide on the installed board: budget missed

**Evidence class: board, injected native touch.** A persistent uinput
touchscreen sent one report every 8.14 ms, the measured real-finger rate.
There was no real-glass interaction and no camera recording. The board ran
system
`/nix/store/8xkkpma4fvgw4fi6pl8qaz7d9d75kcdi-nixos-system-nixos-26.11.20260919.20b1ddd`
on 2026-10-22, with DSI-1 in landscape (1232x568, transform 270) and
`max_render_time 12`. One CPU was online. The installed keyboard is 240 px
tall (`SWAY_K230_KEYBOARD_HEIGHT=240`), with a 56 px grip band above it.

The instrumentation is the installed compositor's own benchmark. While
armed (`swaymsg card_shell benchmark injected` … `benchmark-stop`), sway logs
the following for every output frame:

- `event=present` (presentation time, CLOCK_MONOTONIC);
- `repaint-timing` (render start/commit/end wall time);
- `frame-damage` (damaged pixels).

Its per-input latency rows cover card gestures only (`card_shell_motion`
records an input only when the card shell is active). They are therefore
absent here, and this report does not claim input-to-present latency for
keyboard motion.

## Workload

[keyboard-cycles.py](keyboard-cycles.py.txt) first opens an owned Foot window
(`k230.kbd.trial`, running `cat >/dev/null`, so typed keys go nowhere). It
then repeats eight cycles:

1. **Show:** two contacts in the bottom 72 px, 40 ms and 200 px apart,
   swiped up 250 px over 400 ms, followed by an 800 ms settle.
2. **Type:** three key taps, then a 400 ms pause.
3. **Hold and reverse:** a grip drag 150 px down over 400 ms, held still for
   300 ms, then dragged back up over 300 ms, followed by an 800 ms settle.
4. **Hide:** a grip drag 260 px down over 350 ms, followed by a 1 s settle.

Afterwards the script closes the window and saves the `shell` and
`shell-keyboard` journals. The command, run as root under the exclusive
board lock, was:

```sh
flock -n /tmp/k230-board.lock "$PY" keyboard-cycles.py RUN_DIR "$SYSTEM" 8 --bench
```

The functional probe ([probe1](probe1/), one cycle, no benchmark) captured:

- the shown keyboard ([shown.png](probe1/shown.png));
- the typed `zvm` in the trial window once the keyboard was hidden
  ([hidden.png](probe1/hidden.png)).

Replay either run with:

```sh
python3 analyze.py.txt bench1
```

[analyze.py](analyze.py.txt) splits frames into windows by gesture. A window
runs from one gesture's first contact to the next gesture's first contact.
Within it, "contact" means a finger was down and "settle" covers the motion
after release.

## Results

bench1 ran 03:45:03–03:45:57Z and bench2 ran 03:46:52–03:47:46Z. Every frame
was presented (592 and 588 rows), and the trial window was closed
after each run.

| Phase (bench1 / bench2) | Presented interval median | p95 | Intervals over 33.334 ms | Render wall median / p95 |
| --- | ---: | ---: | ---: | ---: |
| Show, contact | 76.7 / 76.6 ms | 172.5 / 172.4 ms | 22/22, 24/24 | 35.3 / 51.4, 33.3 / 51.2 ms |
| Show, settle | 57.5 / 57.5 ms | 76.7 / 95.8 ms | 63/66, 68/71 | 41.8 / 55.3, 38.7 / 52.9 ms |
| Hold and reverse, contact | 38.3 / 38.3 ms | 57.5 / 57.5 ms | 162/171, 159/165 | 23.0 / 29.8, 23.4 / 30.8 ms |
| Hold and reverse, settle | 38.3 / 38.3 ms | 57.5 / 57.5 ms | 32/35, 35/36 | 24.6 / 33.0, 24.4 / 41.5 ms |
| Hide, contact | 38.3 / 38.3 ms | 38.3 / 38.3 ms | 63/63, 63/63 | 21.1 / 28.8, 21.6 / 27.9 ms |

**Every moving phase misses the card frame budget** (presented interval
p95 33.334 ms or less, the frozen budget in
[card-shell frame budget](../../card-shell/frame-budget/acceptance-2026-10-09/README.md)).

- During a grip drag the keyboard updates every second panel refresh
  (38.3 ms, about 26 frames per second).
- During the show swipe it updates about every fourth refresh (76.7 ms,
  about 13 frames per second).
- Render wall time is 21–42 ms against the 12 ms allowance, so frames miss
  their refresh.

Show and hide durations:

- **Show:** the first presented frame arrives a median 79.0 / 78.9 ms
  after first contact, and the last frame of the show motion arrives at
  999 / 964 ms.
- **Hide:** the last frame arrives at 797 / 780 ms after first contact.

The typing rows are not a tracking measure: the window includes idle time
between taps. Typing renders were short (median 2.3 ms), and key-tap
acknowledgement was not timed separately.

## What the frames cost

- **Damage:** the show motion repaints the whole output on every frame
  (median damaged fraction 1.00). Grip drags and hide repaint a median 52%,
  which is the keyboard plus the app area above it.
- **Rearranging:** the compositor rearranges the workspace on every
  keyboard frame. Sway's debug log shows about 1,480 `Usable area changed,
  rearranging output` / `Arranging workspace` pairs per 54 s run. This is
  the per-tick usable-area update from
  `the-keyboard-follows-touch-gestures` task 2.4, and it makes the focused
  app reconfigure while the keyboard moves.
- **Debug logging:** the installed configuration runs sway with `-d`
  (`k230.shell.debugLog = true` in `flake.nix`). The flake's own comment
  calls this a bring-up setting that "should leave with" its change. About
  4,800 DEBUG journal lines are written per run (about 90 per second), all
  on the one CPU. An earlier same-binary comparison measured journald at
  about 0.10 cores for benchmark-volume logging
  ([log destination](../../omarchy-themes/background-video-board-2026-10-21/log-destination/README.md)).
  Its effect on keyboard frames was not isolated here.

The benchmark's own rows also go to the journal (about three per frame), so
these runs carry that observer cost.

## Limits

- Injected touch skips the Goodix interrupt and driver path.
- There is no per-input latency for keyboard motion; presented intervals
  and render wall time are what is measured.
- No camera recording or real glass was used.
- Only landscape was measured. One owned Foot window was the app being
  resized.
- This records a measured miss. Nothing was optimized, and no budget is
  waived.

Owned board files (`/var/lib/k230/kbd-jank`) were removed. The trial window
closed itself in every run.

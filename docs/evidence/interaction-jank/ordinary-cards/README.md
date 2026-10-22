# Ordinary-card entry and touch acknowledgement with a live video and a busy app

**Evidence class: board, injected native touch.** A persistent uinput
touchscreen, held open for the whole run, sent one report every 8.14 ms
(the measured real-finger rate). This is the injector the
[earlier attempt](../../card-shell/live-card-cost/README.md) lacked, when
per-sample `evemu-event` process spawns dominated the timing. There was no
real-glass interaction and no camera recording.

The board ran system
`/nix/store/8xkkpma4fvgw4fi6pl8qaz7d9d75kcdi-nixos-system-nixos-26.11.20260919.20b1ddd`
on 2026-10-22, with DSI-1 in landscape (1232x568, transform 270) and
`max_render_time 12`. One CPU was online.

Timing comes from the installed compositor's own benchmark (`swaymsg
card_shell benchmark injected` … `benchmark-stop`):

- per-input `input` → `submit` → `present` rows;
- the `motion-settle` frame for each released gesture.

All of these use CLOCK_MONOTONIC.

## Workload

[card-entry.py](card-entry.py.txt) runs as root under the exclusive board
lock. The command is:

```sh
flock -n /tmp/k230-board.lock "$PY" card-entry.py RUN_DIR "$SYSTEM" ARM 8 --bench
```

It requires the startup terminal to be the only app, then starts one arm
app. There are two arms:

- **video:** the shipped Video app, `k230-video-session run`. It played the
  public test stream through mpv with software decode
  (`k230-video-software`, 480x270, 30 fps). The stream was visibly advancing
  in the deck and when expanded ([deck](probe-video/deck.png),
  [expanded](probe-video/expanded.png)).
- **busy:** btop in an owned Foot window (`k230.busy.trial`) at font
  size 7. At the default font in landscape, btop draws only "Terminal size
  too small" (102x23 cells against the 80x24 it needs), so it is not busy.
  This is a separate usability finding: the shipped btop entry does not
  render in landscape. btop screenshots are not committed because its
  network panel shows the board's private address.

Each of the eight cycles starts from the focused arm app and does three
gestures:

1. **Entry:** one contact in the bottom-edge band (y=562), swiped up 262 px
   over 300 ms and released, then a 1.5 s pause.
2. **Drag:** a 300 px horizontal drag on the deck over 700 ms, released,
   then a 1.2 s pause.
3. **Tap:** an 80 ms tap on the centre card, which expands it, then a 2 s
   pause.

Afterwards the script stops the video (`k230-video-session stop`) or closes
the busy window. In both runs only the startup terminal remained.

Replay with:

```sh
python3 analyze.py.txt bench-video
```

## Results

bench-video ran 03:55:04–03:56:22Z and bench-busy ran 03:56:24–03:57:19Z.
Each arm had 1,007 inputs, every frame was presented, and all 24 gestures
reached `motion-settle`.

### Touch acknowledgement (target ~100 ms)

| Arm | Gesture | Measured from | Median | Max | Over 100 ms |
| --- | --- | --- | ---: | ---: | ---: |
| video | tap | release, the moment a tap acts | 50.4 ms | 66.5 ms | 0/8 |
| busy | tap | release | 21.8 ms | 52.5 ms | 0/8 |
| video | deck drag | first contact | 121.5 ms | 154.2 ms | 8/8 |
| busy | deck drag | first contact | 58.0 ms | 89.6 ms | 0/8 |
| video | entry | first contact | 136.4 ms | 195.4 ms | 7/8 |
| busy | entry | first contact | 127.6 ms | 143.6 ms | 7/8 |

Entry from first contact includes finger travel. The compositor's entry
threshold is 72 px, which this 0.87 px/ms swipe covers in about 83 ms.

### Entry animation (target ~400 ms)

| Arm | First contact to settled | Release to settled |
| --- | ---: | ---: |
| video | median 649 ms, max 740 ms (8/8 over 400) | median 294 ms, max 320 ms |
| busy | median 573 ms, max 595 ms (8/8 over 400) | median 259 ms, max 275 ms |

The first column includes the injected 300 ms swipe.

Tap-to-expand, from first contact to settled: video median 356 ms (2/8
over 400 ms), busy median 307 ms (0/8 over 400 ms).

### Frozen card budgets during these gestures

The budgets come from `tools/card-shell-benchmark.py`.

| Arm | Gesture | Motion-to-present p95 (budget 66.667 ms) | Tracking interval p95 (budget 33.334 ms) |
| --- | --- | ---: | ---: |
| video | drag | 80.3 ms | 76.6 ms (95/96 over) |
| video | entry | 152.4 ms | 210.8 ms (19/19 over) |
| busy | drag | 48.6 ms | 38.3 ms (21/252 over) |
| busy | entry | 69.2 ms | 76.6 ms (32/44 over) |

## Reading

- **Taps** acknowledge well within ~100 ms of release in both arms.
- **Deck drags** acknowledge within ~100 ms with the busy app, but not with
  the live video (median 122 ms).
- **Entry** is under ~400 ms only when measured from release. From first
  contact it is not under 400 ms with this swipe.

Both targets are informal ("~") and never defined a start point, so the
two definitions are reported side by side. Neither is declared passed.

With a live video, deck tracking misses the frozen budgets (p95 tracking
76.6 ms, motion-to-present 80.3 ms). With btop, the deck drag passes
motion-to-present but its tracking p95 is 38.3 ms. Every one of these runs
had sway running with `-d` (debug journal logging), as recorded in
[the keyboard report](../keyboard/README.md).

## Attempts

- **probe-busy (failed):** btop was not on sway's exec PATH, so the arm
  window never mapped. Nothing was measured. Later runs use absolute
  `/run/current-system/sw/bin` paths.
- **probe-busy2:** btop drew only its too-small message (see above). Not
  measured.
- **probe-busy3 and probe-video:** one-cycle functional probes with grim
  captures. They checked deck entry, drag and expand. No timing was taken.

## Limits

- Injected touch skips the Goodix interrupt and driver path.
- There was no camera, so this is presentation time, not photon time.
- Only landscape was measured, with two cards.
- The video arm's software decode depends on the network stream.
- Owned board files (`/var/lib/k230/card-jank`) were removed, and no mpv or
  btop process remained.

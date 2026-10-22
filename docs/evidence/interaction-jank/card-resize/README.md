# Card entry and expand while the card is resizing

**Evidence class: board, injected native touch.** All captures were taken on
2026-10-22 on the board's DSI panel in landscape: 1232x568 logical pixels,
52.19 Hz (19.16 ms per refresh), `max_render_time 12`, one online CPU. There
was no real glass and no camera.

## Workload

[`card-entry.py`](../ordinary-cards/card-entry.py.txt) with `--bench`, 8 cycles
per run. Each cycle does an entry swipe, a deck drag and a tap that expands
the centre card ([ordinary-cards](../ordinary-cards/README.md)). The busy arm
is btop in a Foot window at font size 7; the video arm is the shipped Video
app.

[`analyze.py`](../ordinary-cards/analyze.py.txt) gives touch acknowledgement
and tracking. [`frames.py`](frames.py.txt) gives, for each frame presented
with damage inside a gesture window (first contact until 400 ms after
release):

- sway's repaint wall time, from `repaint-timing` `start_ns` to
  `commit_start_ns`;
- the interval since the previous such frame.

| Run | Build | Arm |
| --- | --- | --- |
| [base-busy](run-base-busy) | `sgjam1h0` (boot default) | busy |
| [o-busy](run-o-busy) | `pb5l6lmb`, test-activated | busy |
| [o-video](run-o-video) | `pb5l6lmb`, test-activated | video |
| [boot-busy](run-boot-busy) | `pb5l6lmb`, boot default, ordinary boot | busy |

Video is compared with
[recheck-video](../ordinary-cards/recheck-video) on `sgjam1h0`.

## Where the time went

[prof-base-busy](prof-base-busy/flamegraph.svg) profiled sway and the shell
UI during 8 cycles of entry and tap only
([`entry-only.py`](entry-only.py.txt) is `card-entry.py` without the drag),
on `sgjam1h0`. Of 8.2 s sampled CPU, sway used 7.2 s, and `sync_card` held
42% of all samples. Most of that was `card_scaled_buffer_create_format`
(20.5%): it rescales the card's source into a cached RGB565-path thumbnail,
checks it for opacity and prepares it for the quarter-turn.

That cache (`scaled_mirror` in `nix/card-shell/adapter.c`) is keyed on the
thumbnail's size. During entry and expand the card's size changes on every
frame, so each frame rebuilt a full thumbnail from btop's 1232-wide buffer,
used it once, and then composited it. Busy-arm entry frames took 14–25 ms of
sway time for about 390,000 damaged pixels, so they presented every second
refresh. The video card's buffer is not eligible for the cache, and it already
took the direct scaled composite.

## The change

While the scene is in motion (`scene_in_motion()`, which already selects the
nearest filter), `scaled_mirror` now skips the cache when the size differs from
the cached thumbnail. The mirror then takes the direct composite path, the
fallback that ineligible buffers already used. A drag keeps its size, so it
still hits the cache. Once the size holds still, the cache is rebuilt as
before, with the bilinear filter at rest.

## Results

Cells give the median / p90 in ms, or a count.

| Busy arm | base-busy | o-busy |
| --- | --- | --- |
| Entry: sway repaint | 13.7 / 27.6 | 9.3 / 12.7 |
| Entry: presented interval | 38.3 / 38.3 | 19.2 / 38.3 |
| Entry: touch acknowledgement, median / max | 129 / 143 | 69 / 112 |
| Entry: tracking intervals over 33.334 ms | 48 of 59 | 25 of 85 |
| Entry: release to first present, median | 41 | 18 |
| Tap-expand: sway repaint | 10.7 / 20.2 | 9.3 / 13.4 |
| Tap-expand: presented interval | 38.3 / 38.3 | 19.2 / 38.3 |
| Drag: sway repaint | 3.9 / 4.9 | 4.0 / 4.9 |
| Drag: presented interval | 19.2 / 19.2 | 19.2 / 19.2 |

| Video arm | recheck-video | o-video |
| --- | --- | --- |
| Entry: sway repaint | 10.1 / 20.0 | 7.1 / 10.8 |
| Entry: presented interval | 19.2 / 38.3 | 19.2 / 19.2 |
| Entry: tracking intervals over 33.334 ms | 38 | 2 |
| Entry: touch acknowledgement, median | 63 | 49 |
| Drag: presented interval | 19.2 / 19.2 | 19.2 / 19.2 |
| Tap: touch acknowledgement, median | 120 | 119 |

- Entry and tap-expand with the busy card now present on most refreshes;
  before, they presented on every second refresh.
- In the video arm the other card is the startup terminal, a Foot surface that
  was also rebuilt every entry frame. Its entry now tracks almost every
  refresh.
- Drags and taps are unchanged.
- The `scaled-cache` counters sway logs, from the first to the last line of
  each run's journal:
  - base-busy: 435 misses (rebuilds), 14 fallbacks;
  - o-busy: 130 misses, 1,453 fallbacks;
  - recheck-video: 3,286 fallbacks before the change, so the video card was
    already on the direct path.
- Busy-arm entry still has 25 intervals over budget, and its touch
  acknowledgement includes about 83 ms of finger travel to the 72 px threshold
  (see ordinary-cards). Neither target is declared passed.

## Promotion to the boot default

On 2026-10-22, `pb5l6lmb` (commit `2905f5c8`, which is what master evaluates
to) replaced `sgjam1h0` as the persistent system. The kernel and initrd are
identical between the two. [`promote.py`](promotion/promote.py.txt) is the
shade-pull promotion script with the system paths and the state directory
changed. It ran as root under the board lock and set the profile to
`system-88-link`.

An SSH-initiated reboot booted `pb5l6lmb` as both `/run/booted-system` and
`/run/current-system`, with `shell` and `shell-ui` active, no failed units,
and sway at `SCHED_RR` 1. See the [receipt](promotion/receipt.json), boot ID
`69d72d47…`.

[run-boot-busy](run-boot-busy) repeated the busy arm on that boot, and it
matches o-busy:

- entry: sway repaint 9.2 / 12.5 ms, presented interval median 19.2 ms,
  acknowledgement median 73 ms, 22 tracking intervals over budget;
- tap-expand: presented interval median 19.2 ms;
- drag: presented interval median 19.2 ms.

Rollback: write the copies under
`/var/lib/k230/card-resize-promote-20261022/promotion/rollback/` back to
`/boot`, then run `nix-env --profile /nix/var/nix/profiles/system --set` with
`sgjam1h0`.

## Visual check

A one-cycle `--probe` run on `pb5l6lmb` took grim captures of the focused
app, the deck, the dragged deck and the expanded card. All were normal. They
are not committed, because btop's network panel shows the board's private
address. Frames in motion were not captured. Both paths use the nearest
filter in motion and the same rounded clip, and the rest state still comes
from the bilinear cache.

## Host tests

`python3 -m unittest tests.test_card_scaled_cache` passes; the cache itself
is unchanged. `tests.test_card_mirror_order`, `test_card_shell_chrome`,
`test_card_shell_home_bleed` and `test_card_shell_deck_title` fail to build
their harnesses with and without this change. They are not run in CI.

## Limits

- Injected touch skips the Goodix interrupt and driver path.
- Presentation time is not photon time.
- Only landscape was measured, with two cards.
- One run per build and arm. The video arm's software decode depends on the
  network stream.
- Sampling distorts timing on one CPU, so timing comes from the unprofiled
  runs.

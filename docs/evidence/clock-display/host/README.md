# Charging exhibition clock: host evidence

Change: `the-charging-display-shows-an-exhibition-clock`. Evidence class:
**host** (x86_64 desktop, a pty, no Foot, no compositor, no board, no glass).
Taken 2026-10-27. Nothing here shows CPU cost on the board, the look on the
panel, touch delivery, or which card returns in front.

## Settings row renders (task 2.5)

`cargo run --offline --example render_charger_idle_evidence -- ../../docs/evidence/clock-display/host`
from `nix/rust-shell-client`. `settings-<modem|no-modem>-charger-<clock|sleep>-<100|200>-1232x568.png`;
`200` is the largest vision text step. The third column is scrolled so the row
is mid-panel. The row reads "Idle on charger" with the value Clock or Sleep and
sits under Do Not Disturb; at 200% the label drops to the caption size and the
value stays large, and no word is cut off. Fixture values, host clock.

## Effect timings on the host (task 2.1 rotation)

`ttfx` v0.5.1 built with `cargo build --release` from the tag, run in a
100x26 pty with `-i nix/exhibition/K230.txt --frame-rate 15 --anchor-text c
<effect>`, wall time to exit and the process's own CPU time (x86_64; the board's
single core will be many times slower, and Foot's repaint cost is not included):

| effect | wall | CPU | ended itself |
| --- | ---: | ---: | --- |
| slice | 2.7 s | 0.02 s | yes |
| expand | 4.7 s | 0.01 s | yes |
| slide | 7.2 s | 0.02 s | yes |
| middleout | 7.1 s | 0.01 s | yes |
| scattered | 7.5 s | 0.01 s | yes |
| wipe | 9.2 s | 0.01 s | yes |
| highlight | 8.7 s | 0.02 s | yes |
| sweep | 14.7 s | 0.02 s | yes |
| beams | 15.0 s | 0.02 s | yes |
| laseretch | 23.3 s | 0.04 s | yes, over the 20 s cap |
| colorshift | 35.6 s | 0.06 s | yes, over the cap |
| decrypt | >40 s | | no (killed) |
| spotlights | >40 s | | no (killed) |

The card rotates only the first nine; the last four are left out because they
exceed the 20 s cap or never end at this frame rate.

## The card in a pty

`python3 nix/term-apps/k230_exhibition.py --render-once 100x30` prints one
frame (large HH:MM, the date). With the host `ttfx` and a pty:

- first effect 8 s after start (`slice`), then the 4 s banner hold, then the clock;
- one typed byte at 12 s (during the hold): exit status 0 after 12.2 s, the
  pid file removed, the terminal reset (OSC 111 and cursor restore sent);
- an SGR mouse press with no release at 9.5 s (during the effect): exit status 0
  after 9.8 s (the 0.25 s wait for the lift), no `ttfx` left running.

The harness was a throwaway Python pty driver kept in the scratchpad, not
committed; the same behaviours are asserted against fakes in
`tests/test_exhibition.py` (`python3 -m unittest tests.test_exhibition`).

## Not shown

Foot's handling of touch (whether a touch becomes mouse reports), which card
Sway puts in front when the card closes, the charger's `online` reading while
docked, the DRM `dpms` path, and CPU use on the board are all open board tasks
(tasks 4.1 to 4.8).

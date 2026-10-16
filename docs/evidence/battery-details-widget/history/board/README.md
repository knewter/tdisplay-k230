# Charge graph on the board (HDMI, 1280x800)

Evidence class: **native grim capture** plus the board's history file. Not a
camera recording, and not an operator observation.

System: `/nix/store/2qflnhdr4xalcncsdda53mi49yf5hm53-nixos-system-nixos-26.11.20260919.20b1ddd`
(bundle `hc1vdz9arzxnavdzlqjpkn7wq0pxaamf`, source cd43f5de). It was activated
live at 19:24 CDT on 2026-10-15 with `switch-to-configuration test`, after the
board had booted the earlier history build (1d4e…, recording since 17:57).

Page 2 was reached with `tools/board-pointer.py` (a uinput absolute pointer,
`swipe 1000 520 300 520 250`). The screen was then captured with grim:
`page2-graph-1280x800-grim.png`. `battery-history.txt` is
`/home/shell/.local/state/k230-shell/battery-history` copied right after the
capture.

## What the file and the graph show

- 17:57-18:13: 93 to 88 percent while discharging. The gauge had been reset
  and was overestimating.
- 18:14: 88 to 7 percent between two samples a minute apart, when the gauge
  recalibrated (3.61 V at about -600 mA; full capacity relearned as
  2872 mAh). The graph shows the cliff.
- 18:15-18:18: 7 to 3 percent. The board then powered off on low battery.
- About 55 minutes with no samples: drawn as a gap.
- 19:13 onward: 2 percent, "Not charging", 0 mA. The board was powered from
  the K230 module's own USB, and the charger reported no input.

The span caption reads "2 h ago" because the history covers about 1.5 h,
rounded up to whole hours.

## Limits

- There is no charging span on the board yet, so the accent-coloured charge
  stretch is shown only in the host renders.
- Task 3.2 (the operator's look at the glass) is still open.

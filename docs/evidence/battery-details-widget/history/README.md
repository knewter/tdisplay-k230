# Battery - Details charge graph: host renders

Evidence class: **host render** (Cairo/Pango via `render::paint_home`; no
compositor, no board, no real sysfs). Date: 2026-10-15.
Change: `openspec/changes/battery-details-graphs-charge-over-time`, task 2.1.

Command, from `nix/rust-shell-client`:

```
cargo run --example render_battery_history_evidence -- ../../docs/evidence/battery-details-widget/history
```

Source: `examples/render_battery_history_evidence.rs`. The gauge values are an
invented discharging fixture: 71 percent, -412 mA, 3.89 V, charger offline.
The history is built by the real `history::History::record` with no file:

- `day-*`: a discharge from 90 to 40 percent over 6 h, starting 11.5 h before
  "now". Then 20 minutes with no samples (the shell was off), shown as a break.
  Then a 3 h charge to 78 percent in the accent colour, and a discharge to
  71 percent at "now".
- `fresh-*`: one sample only, so the graph shows a dot and "Recording charge".

Sizes: 568x1232 (portrait panel), 1232x568 (landscape panel), 1280x800 and
1920x1080 (HDMI). The graph takes the bottom 27 percent of the widget, and the
other content lays out in the rest.

Limits: these renders show painting and layout from invented samples only.
Recording on the board, the history file, and how the graph looks on the
glass are covered by tasks 3.1 and 3.2.

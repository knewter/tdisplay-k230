## Why

The Battery - Details widget shows the battery at one instant. With the board
unplugged, the operator asked to see how the charge has filled or drained over
time. The widget's own proposal left history graphs out of scope, so this
adds them as a separate change.

## What Changes

- The shell records the battery percentage and whether it was charging about
  once a minute to a small history file beside `home.json`. It records whether
  or not the widget is placed, so a newly placed widget already has history.
- The history file keeps the last 24 hours, survives shell restarts and
  reboots, and caps its size by rewriting itself when it grows.
- The Battery - Details widget draws the last 12 hours of charge as a filled
  line graph in the space to the right of the ring. The vertical axis runs from
  0 to 100 percent. Spans where the shell was not running show as gaps, and
  charging spans are drawn in the accent colour.

**Non-goals:** current or power graphs, a zoomable or tappable graph, history
for the 2x2 Battery widget, a history view in Settings, recording while the
shell is not running.

## Impact

- `nix/rust-shell-client`: `home_widgets::battery` (history file), `main.rs`
  (recording on the existing poll), `render.rs` (graph painting).
- New per-user state file `$XDG_STATE_HOME/k230-shell/battery-history`.

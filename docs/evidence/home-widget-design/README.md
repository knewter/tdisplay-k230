# Widget visual redesign: host render evidence

Host-rendered screenshots, not board or QEMU evidence. Produced by
`cargo run --example render_widget_evidence -- <out-dir>`
(`nix/rust-shell-client/examples/render_widget_evidence.rs`), which calls
the real, unmodified `render::paint_home` offscreen (a Cairo `ImageSurface`,
no Wayland, no compositor) against two synthetic `AppearanceSnapshot`
themes built directly from `appearance.rs`'s own public fields -- a
Catppuccin Mocha-derived dark palette and a Catppuccin Latte-derived light
one -- rather than a live Omarchy IPC session, which this host has no
compositor to run. This is what `home-widget-design`'s task 3 asks for when
"the QEMU one is flaky under load": a small host render harness.

I looked at every image myself before writing this and iterated on the
widget layouts (padding, hero-numeral size, forecast-strip column count)
until they read cleanly at both the evidence PNG's zoomed-out scale and a
1:1 crop.

## What this captures

Ten distinct captures, each in both themes (`dark-*.png`/`light-*.png`,
18 files -- the two drag-mechanic captures are theme-independent mechanics
and are only captured once, in the dark theme):

- `clock-big.png` -- the "Big stacked" clock style: hour and minute each
  their own huge bold line, a small tracked-caps date beneath.
- `clock-minimal.png` -- "Minimal line": one thinner `HH:MM` line.
- `clock-analog.png` -- "Analog": a drawn clock face (ticks, a neutral hour
  hand, an accent-colored minute hand) plus a short date caption.
- `battery-present.png` -- a themed ring at 72%, charging (the bolt glyph
  in the ring's center).
- `battery-absent.png` -- the "No battery info" state: a muted outline
  battery glyph, no spinner or dash -- this board's actual everyday state
  today (no fuel gauge connected).
- `weather.png` -- current temperature, a Cairo-drawn condition glyph
  (cloud, here), location, high/low, and a 3-entry forecast strip, each
  with its own small glyph.
- `overview.png` -- all three widget kinds together on one Home page
  (Clock-big, Battery, Weather), plus a populated dock, the composition
  closest to what a person actually sees.
- `widget-picker.png` -- the widget-picker sheet's Widgets page, showing
  that every row previews its actual widget rendered live (task: "Show the
  widgets rendered in the picker previews as well"), not a static icon.
- `drag-edge-indicator.png` (dark only) -- a live external drag, driven
  through `HomeScreen::begin_external_drag`/`external_drag_motion`/`tick`
  (the real public API, not a faked field), held in the right edge zone for
  240ms of the ~380ms first-dwell threshold: the edge glow and the growing
  arrow chevron, mid-progress.
- `drag-no-room.png` (dark only) -- a live rearrange drag (real
  `down`/`tick`/`motion` sequence) of a pinned Weather widget hovered over
  the Clock widget's own 4x2 span: rearrange mode is active (Done/Remove
  pills visible) and the lifted Weather card sits over a cell that has no
  room for it. The red dashed "no room" ring itself is mostly hidden behind
  the lifted card at this exact hover point, since both are centered on the
  same finger position -- this is also true in the real client, for any
  drag whose card is as large as or larger than a single highlighted cell.
  `home_screen::tests::dragging_a_widget_over_another_widgets_full_span_shows_no_room`
  is the stronger proof for this specific behavior (asserting
  `HomeScreen::drop_target_fits` directly), not this screenshot alone.

## What this does not prove

This is host software rendering, not the board's panel, not real-finger
touch, and not a full Sway/compositor frame. It proves the widget-drawing
code paths run and look the way described; it does not prove daylight
readability, real touch-latency feel, or on-device color reproduction.
Physical-board acceptance remains open (see the change's `tasks.md`).

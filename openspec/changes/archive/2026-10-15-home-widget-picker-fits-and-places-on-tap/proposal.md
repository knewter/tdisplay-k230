## Why

On 2026-10-15 the operator added the Battery widget from Home's widget picker
on the HDMI monitor (1280x800) and "nothing showed up". A board capture
(`docs/evidence/home-screen/widget-picker-fit/board/before-widget-rows-past-the-card-1280x800-grim.png`)
shows the Widgets page drawing its Battery and Weather rows below the picker
card, over the dock. The picker treats a press outside its card as a dismiss
(`HomeScreen::resolve_picker_tap`), so pressing either row closed the sheet.
A plain tap on a widget row also did nothing; only a press-and-hold followed
by a drag placed a widget, which is awkward on a trackpad.

## What Changes

- The picker's rows always fit inside its card. On wide surfaces they split
  into two columns, and rows shrink to fit, with labels scaling with them.
- A tap or click on a widget row places that widget at the first free spot
  it fits on the page in view, else on the first page with room, and closes
  the sheet. Press-and-hold still drags it.
- The row subtitles say "tap to add, hold to drag".

## Impact

- `nix/rust-shell-client/src/home_grid.rs` (picker row geometry),
  `home_screen.rs` (`resolve_picker_tap`), `render.rs` (row labels),
  `home_state.rs` (subtitles), `evidence_render.rs` and the
  `render_landscape_surfaces` example (picker renders).
- Spec: `runtime/home-screen` gains one requirement.

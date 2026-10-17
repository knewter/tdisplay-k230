# Battery details on the Label floor (visual language task 2.2)

## Change

`paint_battery_details` in `nix/rust-shell-client/src/render.rs`:

- **Grid labels.** "CURRENT", "POWER" and the others were tracked capitals at
  about 14 px. They are now sentence case, regular weight, at the 26 px
  Label floor (`BATTERY_TEXT_FLOOR`). Each label sits on one line with its
  bold value (26 × 1.15 px), two cells to a row.
- **Rows.** Current, Power, Voltage, Temp, Health and Cycles, in up to three
  rows, as many as the space holds. The two-column "Charge 2872 / 2872 mAh"
  cell was dropped: at this size it does not fit beside a label.
- **Graph captions and input line.** "12 h ago", "now", "Recording charge"
  and the charger/input line are also on the 26 px floor. The input line is
  drawn only when it fits under the rows. The graph area grows enough to
  keep a plot under the larger captions.
- **Text step.** The step enlarges the grid only as far as the widest label
  and value pair still fits its cell, and two rows still fit. In a 4x2 Home
  cell the 26 px floor already fills the width, so the grid stays the same
  size at every step. Nothing is cut off.
- **Picker preview.** The floor scales down in proportion for widgets
  narrower than 400 px, such as the picker's preview.

## Host evidence (2026-10-16)

- `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml`:
  every target passed, including `--lib` (569 passed, 2 ignored) and
  `responsive_pixel_identity` (4 passed, baselines unchanged).
- Renders were made with `render_accessibility_scale_evidence` and the
  default/large/larger/largest generations described in
  `docs/evidence/coherent-shell/accessibility-scale/README.md`, then cropped
  to the widget.

| File | Content |
|---|---|
| `host-landscape-steps.png` | 1232x568, widget crop, in a 2x2 grid: 100%, 130% (top), 160%, 200% (bottom). |
| `host-portrait-steps.png` | 568x1232, widget crop, left to right: 100%, 130%, 160%, 200%. |

The host fixture has fewer than two charge samples, so the plot shows
"Recording charge".

## Limits

- The board capture is a single grim frame at 160%; the other steps are host renders.
- The battery ring's percentage (Display role, fitted inside the ring) is
  unchanged.
- The input line ("USB power - limit … @ …") is still ellipsized at the
  26 px floor in a 4x2 Home cell. It is dropped when there is no room for
  it, and is cut off when there is room for part of it.

## Board evidence (2026-10-16)

The fix was deployed live to the board with `deploy-live.sh` (commit
`96844d6e`, sway restarted). The text step was `larger` (160%). The
capture was taken with `grim` on the HDMI output, after the terminal was
moved to the scratchpad.

| File | Content |
|---|---|
| `board-hdmi-home-160.png` | 1280x800 grim capture of Home at 160%. The battery widget shows Current, Power, Voltage, Temp, Health and Cycles as label/value pairs in two columns, and every value is whole. |

An earlier deploy of `42849460` showed "Current +53 m…" ellipsized. The
value's room is now the full column, and the value shrinks toward the
label size before it is cut off. That deploy's frame was not kept. The
volume overlay, raised by the sway restart, covers the graph's right-hand
"now" caption in this frame. The overlay is not part of the widget.

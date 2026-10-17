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

## Host evidence (2026-10-17)

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

- Host renders only, until the board section below.
- The battery ring's percentage (Display role, fitted inside the ring) is
  unchanged.

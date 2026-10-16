# The Clock widget's date is readable (change `the-clock-widget-date-is-readable`)

## Why

On 2026-10-16 the operator looked at the landscape panel at 200% and said the
clock widget "has got some text too small to see really". The date line was
drawn at a fixed 17 px, or 15 px for the analog style
(`docs/evidence/coherent-shell/accessibility-scale/board/14-panel-200-home.png`).

## What changed

`clock_date_metrics` in `nix/rust-shell-client/src/render.rs` sizes the date
line for every Clock style:

- It starts at 26 px times the Vision text step.
- When the date is too wide for the card (less 22 px insets and a 4% margin),
  it first drops the thin-space letter tracking, then shrinks to fit.
- It moves up from its old position when it needs more height. The time
  above it shrinks by the same ratio, so the two never overlap.

## Host evidence (2026-10-16)

- `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml
  --lib clock_date` passed (1 test). Test
  `clock_date_is_readable_at_every_text_step` checks four card sizes at 100%,
  130%, 160% and 200%:
  - the date fits the width and the card;
  - it never gets smaller as the step grows;
  - the time ends above it;
  - it is at least 26 px at 100% on cards 250 px wide or wider.
- The full `--lib` suite passed: 569 passed, 2 ignored. All integration test
  binaries passed, including `tests/responsive_pixel_identity.rs` (4 passed).
- Renders: `render_accessibility_scale_evidence` was run with the
  default/large/larger/largest generations described in
  `docs/evidence/coherent-shell/accessibility-scale/README.md`. The output
  was cropped to the Clock area.

| File | Content |
|---|---|
| `host-landscape-steps.png` | Home at 1232x568, top-left 640x460, in a 2x2 grid: 100%, 130% (top), 160%, 200% (bottom). |
| `host-portrait-steps.png` | Home at 568x1232, top 568x520, left to right: 100%, 130%, 160%, 200%. |

## Limits

- Only the Bubble style appears in these renders. The Thin, dot-matrix and
  analog styles use the same metrics but were not rendered.
- These are host renders. Board captures and the operator's look are task 2.1.

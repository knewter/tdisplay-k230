# Clock restyle (change `the-shell-has-one-visual-language`, task group 1)

Evidence class: host renders from real theme generations. There is no native
panel capture and no judgement on glass yet (tasks 5.1 and 5.2).

## What changed

`paint_widget_card_content` in `nix/rust-shell-client/src/render.rs`:

- Hour in the foreground colour, minute in the accent, in the Bubble, Thin
  and dot-matrix styles. Analog keeps its accent minute hand.
- Bubble: lines 0.92 em apart and 38% of the card's height (was 30%, 1.13 em).
- Thin: Inter Light, drawn as three runs with a 60% colon.
- Dot matrix: unlit dots at 16% opacity.
- Date: one line of Inter Semibold in mixed case in the foreground colour, at
  32 px or more at 100% (was tracked capitals in the accent at 26 px).

## Command

```
cargo run --offline -q --manifest-path nix/rust-shell-client/Cargo.toml \
  --example render_clock_styles_evidence -- <out> <state>/generations \
  default=5c64a4c1de62429c468041bc large=af7b32bfc4793dfe05c678e7 \
  larger=bcc10b3fb39a95aa3c43ea80 largest=0fc1fc47cd7b409f46f67425 \
  largest-high=c1792d0524753badee55226d
```

The generations are the ones in
`docs/evidence/coherent-shell/accessibility-scale/README.md` (the default
theme at each text step, and 200% with high contrast). The example draws each
Clock style alone in slot 0 of Home at 1232x568, over a flat teal and a flat
orange backdrop (the two halves of the vinyl wallpaper), cropped to the left
620 px. "Before" was rendered the same way from `9d213511`, the base of this
branch.

## Files

Each sheet has four rows (Bubble, Thin, dot matrix, analog) and four columns:
teal before, teal after, orange before, orange after. Tiles are half size.
The clock reads 17:54 in the "before" tiles and 17:55 in the "after" tiles
because they were rendered a minute apart.

| File | Step |
|---|---|
| `host-100-before-after.png` | 100% |
| `host-130-before-after.png` | 130% |
| `host-160-before-after.png` | 160% |
| `host-200-before-after.png` | 200% |
| `host-200-high-before-after.png` | 200%, high contrast |

## Tests

- `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml
  --lib`: 569 passed, 2 ignored.
- `--tests`: all integration targets passed, including
  `responsive_pixel_identity` with its baselines unchanged.
- `clock_date_is_readable_at_every_text_step` now measures the Inter date
  line and the Bubble geometry (`bubble_lines`) at four card sizes and four
  steps.

## Limits

Landscape only. Flat backdrops, not the wallpaper. No light theme. The
Bubble clock in the card is a 2-column cell; wider cells were not rendered.

## Board captures (2026-10-16, DSI-1 1232x568 landscape)

The system was `/nix/store/5vj9z6z0ims1svg437qncsv7y2p5hw2z-nixos-system-…`,
built from integration commit `e71dabce`. That is this restyle plus the
side-edge Back menu fix, which touches only `main.rs` and the card shell. It
was deployed live by the coordinator. The text step was set with
`k230-theme vision --text-scale <step> --contrast standard`. The theme was
retro-82 with its vinyl wallpaper. Each frame is a native `grim` capture.

Evidence class: native captures. No judgement on glass yet.

| File | Step |
|---|---|
| `board-panel-100-home.png` | 100% |
| `board-panel-160-home.png` | 160% |
| `board-panel-200-home.png` | 200% |

On this theme the hour is cream and the minute is retro-82's orange accent.
Both have the dark halo over the teal and orange vinyl. The date is one cream
line that grows with the step.

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

## Host evidence (2026-10-17): portrait, wallpaper, light theme

Evidence class: host renders only, from real theme generations. No board
capture and no judgement on glass. Tasks 1.3 and 1.4 of the change.

The example gained two optional environment variables:
`CLOCK_SIZE=portrait` renders 568x1232, cropped to the top 620 px, and
`CLOCK_WALLPAPER=<png>` replaces the flat backdrops with that image, scaled to
cover the panel. Each Clock style is drawn alone in slot 0 of Home, so the
dock placeholder shows below it. The text step comes from the generation, not
from the name. The generations were prepared on the host with
`tools/theme_activate.py` and `tools/theme_vision.py` at each of `default`,
`large`, `larger` and `largest` (100/130/160/200%), contrast `standard`.

Sources: `nix/handheld-theme-default/catppuccin` (the default theme), and
`/nix/store/sk567bs144zc0fpn7v16q10amjsz4wsb-source/themes/retro-82` and
`.../themes/catppuccin-latte`.

| Theme | 100% | 130% | 160% | 200% |
|---|---|---|---|---|
| catppuccin | 3ca9e2aff350ca417e2ff4d4 | 4bb1717c22218debb2901ff7 | 51892a062666a9636a15a911 | 00b94d7cb2c378c9e167bfea |
| retro-82 | 32b73c36b03bf9f4e1836b3b | 3ac6617e73fc472072bb22a5 | 42d25c3f28bba5ca4b7b5093 | 0017cb90ff4788c72a594ed0 |
| catppuccin-latte | c3f3ed1da29e4794867c6407 | 055d709f012e41598de6e193 | 122e3e491beb0684d6a9580a | 3d3427bb1dcfe70d59c085c3 |

Commands (from the worktree root; wallpapers converted with ImageMagick to
1800 px wide PNG first):

```
magick .../themes/retro-82/backgrounds/1-in-the-groove.webp -resize 1800x groove.png
magick .../themes/catppuccin-latte/backgrounds/1-color-fade.webp -resize 1800x fade.png
E="cargo run --offline -q --manifest-path nix/rust-shell-client/Cargo.toml \
  --example render_clock_styles_evidence --"
CLOCK_SIZE=portrait $E <out> <catppuccin-state>/generations default=<id> large=<id> larger=<id> largest=<id>
CLOCK_WALLPAPER=groove.png $E <out> <retro-82-state>/generations default=<id> ...
CLOCK_WALLPAPER=fade.png   $E <out> <catppuccin-latte-state>/generations default=<id> ...
```

Each sheet has four rows (Bubble, Thin, dot matrix, analog) and four columns
(100%, 130%, 160%, 200%), built with `magick montage` and then
`-resize 50% -strip`. The clock reads a different minute on each sheet because
they were rendered at different times.

| File | Shows |
|---|---|
| `host-portrait-steps.png` | catppuccin, 568x1232 portrait (top 620 px), over flat teal |
| `host-retro82-wallpaper.png` | retro-82 over its `1-in-the-groove` vinyl wallpaper, landscape |
| `host-latte.png` | catppuccin-latte over its `1-color-fade` wallpaper, landscape |

What the images show:

- Portrait: all four styles fit the 568 px width at every step; no clipping.
  The dot-matrix clock nearly fills the width at 200%. The date grows with the
  step. The analog clock is small and sits left in its cell in portrait.
- retro-82 over the vinyl:
  - The Bubble and Thin minutes, in the orange accent, stay readable because
    of the dark halo, including over the orange label. The Thin minute at
    200% is thin and reads mainly by its halo outline.
  - The first renders showed the dot-matrix minute as the weak case: orange
    dots over the orange label, separated only by faint soft halos.
    `draw_dot_matrix_glyph` now gives each lit dot a crisp ring in the halo
    colour (`pitch * 0.1`, at least 1.5 px, at 80%). The re-rendered sheet
    shows the minute dots outlined and legible at every step, including
    where they cross the spindle.
  - The analog style's cream hour ticks are faint over the orange label;
    its hands keep their halo and read.
  - The hour and date, in cream, read well.
- catppuccin-latte over the pastel wallpaper: the hour is dark and the minute
  is the saturated blue accent, both clearly legible at all steps and styles.
  The halo is a light tone and is not visible on this light wallpaper; it is
  not needed there.

Limits: host renders only. The wallpaper is scaled to cover and is not the
panel's exact crop or the shell's wallpaper pipeline. The clock is in slot 0
only, so its position over the vinyl is not where a user would place it.
The sheets were re-rendered after the dot-ring change, from the same generations.

## Theme change without a restart (2026-10-19 UTC)

Native `grim` captures of Home on DSI-1 (1232x568), Bubble Clock, 100%,
from the db133d1f closure. `shell-ui` kept MainPID 1080 throughout, so the
shell was not restarted.

| File | Theme (accent) | Minute | Time (UTC) |
| --- | --- | --- | --- |
| `board-theme-change-retro.png` | retro-82 (`#faa968`) | orange "27" | about 00:27 |
| `board-theme-change-catppuccin.png` | catppuccin (`#89b4fa`) | blue "29" | 00:29:47 activate |
| `board-theme-change-retro-back.png` | retro-82 (`#faa968`) | orange "30" | 00:30:19 activate |

Each theme was applied with `k230-theme preview --json <id>` and then
`k230-theme activate --json --expected-generation <preview generation>
<id>`; retro-82 was restored with its vinyl background. The hour stays the
foreground colour in both themes.

# Wide reflow of Wi-Fi and the theme chooser (landscape 7.2), host renders

Operator design answer, 2026-10-14: "Real wide reflow" for the Wi-Fi pages
and the theme chooser on wide screens.

Host renders only, 2026-10-15, from

```
cd nix/rust-shell-client
cargo run --example render_landscape_surfaces -- <dir>
```

They prove paint and layout at each size, not the board, a monitor or touch.

- **Wi-Fi** (`wifi_ui::layout_for`): the two columns come from the surface's
  own size. The left column keeps 520/1184 of the content width, the list
  column takes the rest, and the list runs to the bottom margin. Refresh,
  the saved-network buttons and Cancel/Connect follow the real right and
  bottom edges. At the landscape panel's 1232x568 every rect is the panel's
  old literal: the seven Wi-Fi renders at 1232x568 are byte-identical to
  `docs/evidence/panel-landscape/host/wifi-*-1232x568.png`.
- **Themes** (`theme_ui::chooser_layout_for`, `render::paint_grid`): every
  wide surface, the landscape panel included, shows all themes and all of the
  active theme's backgrounds at once as two side-by-side grids of cards, each
  with its name below. The theme in use and the background on Home are
  outlined; a tap on a card applies it (`ThemeIntent::Theme`/`Background`,
  the carousel's existing apply path); a drag applies nothing; a finger down
  washes the card and an applying card spins. Cards take the largest size
  that fits the column (themes at most 240 px wide, backgrounds 360 px).
  Portrait keeps the carousels.

Files: `theme-chooser-{1232x568,1280x800,1920x1080}.png`,
`wifi-list-{1232x568,1280x800,1920x1080}.png`,
`wifi-entry-password-{1280x800,1920x1080}.png`,
`wifi-entry-saved-1280x800.png`, `wifi-forget-1920x1080.png`. The fixtures
load no thumbnails, so cards show their loading spinner.

Tests: `wifi_ui::tests::the_wide_wifi_layout_keeps_the_panel_literals_and_fills_a_monitor`
(1280x800, 1920x1080, 1280x720: list to the right and bottom margins, every
control on the surface, the last network, Connect, Cancel and the eye
reachable) and
`theme_ui::tests::wide_choosers_show_every_theme_and_background_as_a_tappable_grid`
(1232x568, 1280x720, 1280x800, 1920x1080 with 1, 7 and 12 themes: cards at
least 80 px wide, inside their column, not overlapping, labels above the
message line, each card's centre applying that card, a drag applying
nothing, Back and Close still working). `cargo test`: 513 + 22 + 14 + 8 + 4 +
11 + 1 + 6 pass.

## On the board (2026-10-15)

Evidence class: **operator report** on the HDMI monitor (1280x800), test
system `7n025h1fvw5nxkmja2y0j5zk4adazf50` (this change plus a kernel test).
The operator: "it works and it feels pretty good", and reported a dark band
over the dock on Home. That band was the HDMI render timing, not this change;
it is fixed separately (`docs/evidence/card-shell/bottom-band-flicker/hdmi.md`).
The shell does not log chooser taps, so no record shows which card was
tapped or what it applied.

Limits: no frame capture on the board. The grid has no scrolling: with
many user themes its cards shrink (the test holds 12 at 80 px or more), and a
much longer list would need a scrolling grid.

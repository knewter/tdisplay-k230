# The shade leads with time and quick tiles: evidence

Change: `openspec/changes/the-shade-leads-with-time-and-quick-tiles/`.

## Host (task 1.3)

Rendered 2026-10-27T03:19Z from commit `af5f70f4`'s tree with:

```
cargo run --offline -q --manifest-path nix/rust-shell-client/Cargo.toml \
  --example render_shade_pass_evidence -- <out>
```

The time and date are the host clock at render time. Host render only: it
proves paint and layout, not the board's glass.

| File | Content |
|---|---|
| `host/shade-no-modem-2-1232x568.png` | Wi-Fi and Keyboard tiles, two notifications. |
| `host/shade-no-modem-empty-1232x568.png` | Empty list: the message centred in the list column. |
| `host/shade-modem-location-off-4-1232x568.png` | Modem present: four tiles; Cellular on, Location off. |
| `host/shade-modem-location-on-4-1232x568.png` | Location searching: the tile reads "Searching", the status line carries both glyphs. |
| `host/shade-modem-location-on-4-568x1232.png` | Portrait keeps its single column (no tiles). |
| `host/vision-100-shade-1232x568.png`, `host/vision-200-shade-1232x568.png` | The catppuccin generation at the default and largest text steps, from `render_accessibility_scale_evidence` with generations prepared by `theme_activate.prepare` (`default` and `largest` text scale). At 200% the date moves to the status line and the tiles' text shrinks to the 112 px tile cap; both sliders stay on the column. |

Tests: `cargo test --offline` in `nix/rust-shell-client`, all targets ok
(lib 616 passed, 2 ignored), including
`the_wide_shade_tiles_meet_the_tap_floor_and_open_their_pages` and
`the_shade_tile_flips_location_with_no_page_open`.

## Board (task 2.1)

Board-native `grim` captures from the test-activated system
`xk69fsf7238xkgsh5808y40xf282i4la` (commit `98a154e2`; `c3xkprj9…` from
`4cba5ccb` for the Location and Keyboard frames), driven by
`docs/evidence/base-keys/ui.py.txt` with injected touch. No person touched
the panel.

| File | UTC | What happened |
|---|---|---|
| `board/tile-location-off.png` | 03:11:07-03:11:13 | Tap on the Location tile (129, 312): the modem service turned GNSS off; the tile reads Off and the status-line glyph is gone. |
| `board/tile-location-on.png` | 03:11:13-03:11:18 | A second tap turned it back on (the operator's earlier setting restored). |
| `board/tile-keyboard.png` | 03:11:32 | Tap on the Keyboard tile (351, 201): the on-screen keyboard rose. A second tap hid it. |
| `board/shade-open.png` | 03:18:34 | The shade on the panel: time, date, "100% · Charging", the location glyph, four tiles, both sliders, the empty list. |
| `board/tile-cellular.png` | 03:18:37 | Tap on the Cellular tile (351, 312) opened Settings › Cellular. |

The Wi-Fi tile (129, 201) opened Settings › Wi-Fi at 03:18:43. That capture
lists network names and is not committed.

This board build predates the "Searching"/"Fix" text on the Location tile
(commit `af5f70f4`), so the board frames read "On". The first build tried
(`c3xkprj9…`) left the Wi-Fi and Cellular tiles inert because their pages
live on the Settings route; `98a154e2` routes them there first.

Remaining: the operator's glass check (task 2.2) and promotion (task 2.3).

## Context

The shade is a top-anchored sheet. On the 1232x568 landscape panel,
`shade_layout` splits it into a 480 px controls column and the notification
list. `render.rs` paints both, and the hit tests in `service_ui.rs` read the
same layout, so a tap and its paint cannot drift apart. That stays true here.

## Decisions

- **Wide only.** Portrait and HDMI keep their constants and tests.
- **Time first.** Apps are full-screen, so the shade is where the time is read.
  The header shows the time in the clock widget's 24-hour form, with the date
  under it. When a larger text step leaves no room for both, the time keeps
  the band and the date moves to the start of the status line.
- **Status line.** Battery reads "<percent>% · <state>", then the cellular and
  location glyphs while those are on. Wi-Fi's state ("Connected" or "Not
  connected") is on its tile, so it is not repeated here. Each fact appears
  once. No SSID is shown, so captures stay committable.
- **Tiles, not rows.**
  - Each tile is a themed card with an icon, a label and a state line.
  - Location toggles in place through the modem worker that the Location page
    already uses.
  - Wi-Fi and Cellular need a password or PIN path, so they open their pages.
  - Keyboard keeps its `KeyboardToggle` request and `ControlState` gate.
- **Sliders last.** They are drag bands and the least-used items, so they sit
  at the bottom of the column, where a thumb rests.
- **Wi-Fi and Cellular tiles open Settings.** Their pages live on the
  Settings route, so the tile shows Settings and then opens the page there.
- **Capped tiles.** A tile grows with the text step, as the keyboard row does,
  but stops at 112 px; its text shrinks to fit. Two rows and both sliders then
  still fit the 568 px column at 200%.
- **The list heading** moves to the list column. "Dismiss all" keeps a band at
  least 99 px tall.

## Risks

- The tile grid adds height. The tile cap keeps both sliders on the column at
  200%, at the cost of smaller tile text there. The renders cover 100% and the
  largest step.

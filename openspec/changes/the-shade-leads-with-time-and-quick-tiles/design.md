## Context

The shade is a top-anchored sheet. On the 1232x568 landscape panel,
`shade_layout` splits it into a 480 px controls column and the notification
list. `render.rs` paints both, and the hit tests in `service_ui.rs` read the
same layout, so a tap and its paint cannot drift apart. That stays true here.

## Decisions

- **Wide only.** Portrait and HDMI keep their constants and tests.
- **Time first.** Apps are full-screen, so the shade is where the time is read.
  The header shows the time in the clock widget's 24-hour form, with the date
  under it.
- **Status line.** Battery reads "<percent>% · <state>". After it come Wi-Fi
  ("Wi-Fi off", "Connected" or "Not connected"), then the cellular and
  location glyphs while those are on. Each fact appears once. No SSID is shown,
  so captures stay committable.
- **Tiles, not rows.**
  - Each tile is a themed card with an icon, a label and a state line.
  - Location toggles in place through the modem worker that the Location page
    already uses.
  - Wi-Fi and Cellular need a password or PIN path, so they open their pages.
  - Keyboard keeps its `KeyboardToggle` request and `ControlState` gate.
- **Sliders last.** They are drag bands and the least-used items, so they sit
  at the bottom of the column, where a thumb rests.
- **The list heading** moves to the list column. "Dismiss all" keeps a band at
  least 99 px tall.

## Risks

- The tile grid adds height. At the largest vision step the column may not fit,
  and then the sliders scroll off the bottom. The renders cover 100% and the
  largest step.

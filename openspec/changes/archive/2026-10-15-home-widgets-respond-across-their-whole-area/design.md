## Context

`home_grid::slot_at` returns the cell whose tile contains the point and
returns nothing for gaps; a test says gaps between icons are intentionally
inert. `render.rs` paints a widget over `home_grid::spanned_tile_rect`, which
covers the gaps inside its span.

## Decisions

1. **Resolve spans in `HomeScreen::filled_slot_at`.** Before the per-cell
   lookup, check each multi-cell item on the page in view against its
   `spanned_tile_rect` and return its anchor. Press, long press, rearrange
   drag and secondary click all share this one lookup.
2. **Leave `home_grid::slot_at` unchanged.** Drop targeting and the icon gap
   behaviour keep their current semantics and tests.

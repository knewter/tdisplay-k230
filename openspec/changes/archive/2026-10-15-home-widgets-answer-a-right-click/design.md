## Context

`main.rs` handles a pointer press of `BTN_RIGHT` (0x111) on Home by asking
`HomeScreen::app_at` for an app, then `HomeScreen::open_menu_at` for empty
space. A widget is neither, so the click falls through. In rearrange mode
`HomeScreen::badge_at` already hit-tests a badge for every filled anchor at
`home_grid::plate_top_left`, but `render.rs` paints widgets with
`paint_widget_card` and skips the badge, so a widget's badge is invisible and
sits at its anchor cell's plate corner rather than the widget's corner.

## Decisions

1. **`HomeScreen::rearrange_at`.** A secondary click that lands on a widget
   (through `filled_slot_at`, which covers the widget's whole painted rect)
   sets `rearranging` and arms no drag. It refuses under the same conditions
   as `open_menu_at`: picker open, folder open, already rearranging, or a
   drag or contact live.
2. **One badge corner for paint and hit test.** `HomeScreen::badge_corner`
   returns the plate corner for icons and the widget rect's top-left (inset
   by the same amount) for widgets. `badge_at` and `render.rs` both use it.
3. **No new menu.** Rearrange mode already offers move, remove and Done, so a
   right-click goes straight there.

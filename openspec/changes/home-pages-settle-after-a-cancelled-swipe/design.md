## Context

`HomePager::cancel` clears the drag and velocity but not the position, and
`HomePager::tick` only moves the pager while coasting or settling.
`HomeScreen::tick` does not tick the pager at all in rearrange mode, which
pages through `page_switch` instead. `HomeScreen::is_animating` decides whether
`main.rs` keeps ticking.

## Decisions

1. **`cancel` settles a fractional position** to the nearest page.
2. **`HomePager::off_page(count)`**: at rest and either fractional or past
   the last page. `tick` starts a settle to the clamped nearest page when it
   holds, and `HomeScreen::is_animating` reports it so ticks resume.
3. **Rearrange mode** ticks the pager only while it is off-page or already
   settling and no `page_switch` is live, so the two never fight over the
   position.

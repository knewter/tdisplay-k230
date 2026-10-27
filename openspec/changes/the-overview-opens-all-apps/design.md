## Context

The overview chrome (`rebuild_chrome`) already paints an "Overview" title at
the left of its title row. Backdrop taps reach two paths: the policy's
`CS_HOME` result (`handle_result`), and the edge-band path for taps that
start inside the Shade, side Back or bottom Home bands. Both went straight to
`home_settle(true)`.

## Decisions

- **Placement.** The label sits at the right of the title row, right-aligned
  by `card_label_ink_box`, opposite "Overview". The hit box is 220 px wide
  plus the 48 px margin, and `max(99, top_reserved + title_height)` tall.
- **Only on backdrop taps.** Both tap paths call `overview_apps_hit` only
  after deciding that the tap missed every card, so the target can never
  steal a card tap.
- **Home first, then the drawer.** The tap settles Home, and the drawer is
  requested when the settle finishes. Requested at once, it was lost: the
  settle's `restore()` ran after it. A later `home_settle()` clears the
  pending request.
- **The edge path tests before `edge_reset`.** `edge_reset()` zeroes the
  edge state, so the hit is computed from `edge.x`/`edge.y` first.

## Risks

- The label is ink-measured, so a theme with a much wider font could push it
  past 220 px. The hit box is fixed, so the visible text would then exceed
  its target on the left.

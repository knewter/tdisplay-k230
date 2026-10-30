## Context

A touch on the Shade can become three things: a close drag (upward, from a
close zone), a list scroll (vertical, in the list), or a row swipe
(sideways, on a dismissible row). `main.rs` decides at touch-down whether
the touch is a close-drag candidate. While it is a candidate, every motion
event goes to the close-drag branch of an `if … else if` chain, so the
row-swipe branch below it never runs.

`shade_panel_close_zone` returns true on the list when the list is
scrolled to its end, so that an upward drag at the end of a list closes the
panel. A list that fits without scrolling is always at its end, so every
touch on it starts as a candidate.

## Decisions

- **Release the candidate on sideways motion (Shade only).** A pure helper,
  `close_drag_sideways(route, dx, dy)`, is true on the Shade once
  `|dx| >= CLOSE_DRAG_SLOP` and `|dx| > |dy|`. When it is true and the
  close drag has not engaged, the motion handler clears
  `panel_close_candidate`, as `close_drag_refused` already does for Settings
  and Help. The next motion event reaches the row-swipe branch. The swipe
  offset is measured from the touch-down point, so no displacement is lost.
- **Rejected: never treat the list as a close zone.** That would remove the
  existing "drag up at the end of the list closes the shade" behaviour.
- **Rejected: try the row swipe first in the motion chain.** That reorders
  a long branch chain shared with Settings, Power and Help, for a
  Shade-only problem.

## Risks

- A diagonal drag that is more sideways than upward no longer closes the
  shade from the list. It did not before either: `close_drag_engaged`
  already requires vertical dominance.

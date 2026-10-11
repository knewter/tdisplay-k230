## Context
Layer: userspace (Rust shell client, `.#handheld-shell-rust`). `AppMenu` opens
from `PointerHandler::pointer_frame` on a right-button press only. Touch input
in the drawer goes through `navigation::DrawerNavigation`, where a long press
arms the drag to Home. The recovery copy and its rendering already exist
(`src/recovery.rs`, archived change
`2026-10-11-the-rust-shell-explains-stale-denied-and-ended-states`).

## Decisions
- The touch route is chosen in task 1.1. Candidates: a long press released
  without movement (the drag arms only once the finger moves), a press on the
  launch splash or the card, or an overflow affordance on the tile. Whichever
  is chosen must leave the drawer's existing drag-to-Home gesture unchanged.
- The capture records serial-triggered setup steps as setup, never as finger
  input.

## Rejected
- Requiring a USB mouse for acceptance: the handheld is touch-only, and the
  operator declined to attach one on 2026-10-11.

## Context
Layer: userspace (Rust shell client, `.#handheld-shell-rust`). `AppMenu` opens
from `PointerHandler::pointer_frame` on a right-button press only. Touch input
in the drawer goes through `navigation::DrawerNavigation`, where a long press
arms the drag to Home. The recovery copy and its rendering already exist
(`src/recovery.rs`, archived change
`2026-10-11-the-rust-shell-explains-stale-denied-and-ended-states`).

## Decisions
- Touch route (operator choice 2026-10-11, "Android-style"): holding a drawer
  tile still for `LONG_PRESS_MS` (500 ms) opens its `AppMenu`. The finger
  still owns the touch (`app_actions::MenuHold`). Lifting it without moving
  leaves the menu open. Moving it past the 12 px hold slop closes the menu and
  starts the existing drag to Home from the hold's start point, so the
  drag-to-Home gesture still works in the same way.
- Home's long press (rearrange) is unchanged. The requirement allows the
  drawer or Home, and the drawer route reaches every installed app.
- The capture records serial-triggered setup steps as setup, never as finger
  input.

## Rejected
- Opening on lift only (a still hold that arms nothing until release). It
  gives no feedback during the hold and delays the menu to the lift.
- A press on the launch splash or the card. It only reaches apps that are
  already launching or running, and conflicts with the splash's own recovery
  tap.
- An overflow (⋯) affordance on each tile. It adds a small target to every
  tile on a 568 px-wide touch panel and changes the drawer's layout.
- Reusing Home's long press. It already enters rearrange mode.
- Requiring a USB mouse for acceptance: the handheld is touch-only, and the
  operator declined to attach one on 2026-10-11.

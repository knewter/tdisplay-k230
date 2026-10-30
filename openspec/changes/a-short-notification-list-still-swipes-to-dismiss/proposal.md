## Why

On the landscape shade, a sideways swipe does not dismiss a notification
while the list fits without scrolling. With one or two notifications, the
shell logs the touch but draws no swipe and sends no dismissal
(`docs/evidence/notification-actions/board/README.md`, 2026-10-30). Once
the list is long enough to scroll, the same swipe works.

The cause is in the shell's gesture code. `shade_panel_close_zone` lets an
upward close drag start on a list that is already at its end, and a list
that does not scroll is always at its end. Such a touch becomes a
close-drag candidate. Only Settings and Help ever release a candidate
(`close_drag_refused`), so on the Shade the horizontal motion never reaches
`notification_swipe_start`. The defect predates the notification-actions
change (`e5f27ecd`, `4cba5ccb`). The operator asked for this fix on
2026-10-30.

## What Changes

- A close-drag candidate on the Shade gives up as soon as the finger moves
  sideways past the drag slop. The rest of the gesture then goes to the
  notification row swipe.
- An upward drag from the same place still closes the shade, as before.

## Non-goals

- The unexplained single failed swipe on a five-row list just after the
  shade reopened (same evidence file). It is not reproduced; if it recurs,
  it gets its own change.
- The adaptor forgetting notification ids across its own restart.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `runtime/notification-center`: a sideways swipe dismisses a row whether or
  not the list scrolls.

## Impact

`nix/rust-shell-client` only: `service_ui.rs` (a pure helper plus tests) and
the Shade branch of `main.rs`'s touch-motion handler. No service, protocol
or settings change.

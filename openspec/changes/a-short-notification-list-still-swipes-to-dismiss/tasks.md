## 1. Host

- [x] 1.1 Add `close_drag_sideways` with unit tests, and clear the Shade's
  close-drag candidate on sideways motion. Proof (host):
  `cargo test --offline --lib` in `nix/rust-shell-client`, including a test
  that a two-row landscape list starts a row swipe after the candidate is
  released, and that an upward drag there still engages the close drag.

## 2. Board (injected)

- [ ] 2.1 Test-activate a build. With one and with two notifications from a
  probe app, swipe a row sideways with injected touch and record
  `NotificationClosed(id, 2)`. Also check that an upward drag on the short
  list still closes the shade. Proof (board, injected):
  `docs/evidence/short-list-swipe/board/`.

## 3. Closeout

- [ ] 3.1 Archive. Proof:
  `openspec validate a-short-notification-list-still-swipes-to-dismiss --strict`.

## 1. Design

- [x] 1.1 Choose how the Timer helper survives a shell restart, or how its
  loss is reported, and record the decision and the rejected routes in
  design.md. Check on the board, read-only, which cgroup the helper lands in
  today (`/proc/<pid>/cgroup`). Proof (board, read-only): the transcript
  under `docs/evidence/timer-restart/board/`.
  *Board, read-only console plus injected touch, 2026-10-30, on `p393r76c…`:
  the helper ran in `shell-ui.service`'s cgroup and died with
  `systemctl restart shell`. The decision is a socket-activated
  `k230-timer@.service` running as `shell` (design.md).*

## 2. Host

- [x] 2.1 Implement the timer decision. Proof (host):
  `python3 tests/test_term_apps.py`, with a case that stops the shell's
  process group while a helper waits.
  *Host, 2026-10-30: `python3 tests/test_term_apps.py` runs 43 tests, all
  pass. A fake timer socket starts a `timerd-serve` instance in its own session
  for each request, as `Accept=yes` does; the test kills the card's process
  group and the instance still posts "Timer finished" once at its deadline.
  Adopting ends the instance without an alert, and a paused or reset card
  hands the socket nothing. `nix eval` of the landscape HDMI configuration
  succeeds with `k230-timer.socket` and `k230-timer@.service`. Not run: the
  units on the board (task 3.1).*
- [x] 2.2 Record the close cause in the broker and emit reasons 1, 2 and 3
  from the adaptor. Store actions and emit `ActionInvoked`. Proof (host):
  `python3 tests/test_notification_center.py && python3 tests/test_notification_dbus.py`,
  on a private bus with the real broker and adaptor.
  *Host, 2026-10-30: `test_notification_center.py` runs 17 tests and
  `test_notification_dbus.py` 20, all pass. On a private `dbus-daemon` with the
  real broker and adaptor, a dismissal reaches the app as
  `NotificationClosed(id, 2)`, an app's `CloseNotification` as reason 3, and a
  tapped action as `ActionInvoked(id, key)` then reason 2. Reason 1 (expiry)
  is covered with the broker's injected clock, not waited for on the bus.*
- [x] 2.3 Draw actions in the shade at the 99 px floor. Proof (host):
  `cargo test --offline --lib` in `nix/rust-shell-client`, and renders at
  100% and 200% under `docs/evidence/notification-actions/host/`.
  *Host, 2026-10-30: `cargo test --offline` passes (684 lib tests and the
  integration tests). Host renders at 100% and 200%, 1232x568 and 568x1232,
  under `docs/evidence/notification-actions/host/` (host render class, FIXTURE
  notifications). Not run: a tap on the panel (tasks 3.2 and 3.3).*

## 3. Board (hardware-only)

- [ ] 3.1 Test-activate a build. Start a 2-minute Timer, close its card, run
  `systemctl restart shell` a minute in, and record what arrives and when.
  Proof (board, injected): `docs/evidence/timer-restart/board/`.
- [ ] 3.2 Send a notification with an action from a probe app on the shell
  bus. Dismiss one and tap the action of another with injected touch, and
  record the signals the probe received. Proof (board, injected):
  `docs/evidence/notification-actions/board/`.
- [ ] 3.3 Glass: the operator taps an action and dismisses a notification.
  Physical proof: a timestamped operator report tied to the installed build.

## 4. Closeout

- [ ] 4.1 Archive once 3.3 is done. Proof:
  `openspec validate pending-timers-survive-restarts-and-apps-hear-dismissals --strict`.

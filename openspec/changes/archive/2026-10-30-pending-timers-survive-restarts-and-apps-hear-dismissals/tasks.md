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

- [x] 3.1 Test-activate a build. Start a 2-minute Timer, close its card, run
  `systemctl restart shell` a minute in, and record what arrives and when.
  Proof (board, injected): `docs/evidence/timer-restart/board/`.
  *Board, console plus injected touch, 2026-10-30, `q8hbkb1g…` test-activated:
  a 2:00 Timer started at about 01:08:06Z ran in
  `k230-timer@….service`, survived `systemctl restart shell` at 01:09:07Z,
  and "Timer finished" (source "Timer") arrived once at 01:10:06Z. Two
  earlier runs on the same build also fired once after a restart, and a
  reopened card adopted the countdown (`04:14 Running`). Not tested: a
  reboot.*
- [x] 3.2 Send a notification with an action from a probe app on the shell
  bus. Dismiss one and tap the action of another with injected touch, and
  record the signals the probe received. Proof (board, injected):
  `docs/evidence/notification-actions/board/`.
  *Board, injected touch plus `action_probe.py`, 2026-10-30, `q8hbkb1g…`:
  the adaptor advertises `actions`; a tapped Snooze gave `ActionInvoked(2,
  snooze)` then `NotificationClosed(2, 2)`; a swipe gave
  `NotificationClosed(7, 2)`; Dismiss all gave reason 2 for both rows; an
  app's own close gave reason 3; after `systemctl restart
  shell-notification-dbus` a tapped Open gave `ActionInvoked(1, open)` then
  reason 2. Found, not fixed here: a sideways swipe does not start while
  the landscape list fits without scrolling, and a restarted adaptor no
  longer reports closes for notifications posted before the restart.*
- [x] 3.3 Glass: the operator taps an action and dismisses a notification.
  Physical proof: a timestamped operator report tied to the installed build.
  *Waived by the operator on 2026-10-29 ("you don't need my fingers on the
  glass just do virtual events and watch screenshots",
  `docs/evidence/glass-checklist-2026-10-29/operator-report.md`). No glass
  evidence exists; the injected run in 3.2 stands in for it.*

## 4. Closeout

- [x] 4.1 Archive once 3.3 is done. Proof:
  `openspec validate pending-timers-survive-restarts-and-apps-hear-dismissals --strict`.
  *2026-10-30: valid; archived with the board evidence.*

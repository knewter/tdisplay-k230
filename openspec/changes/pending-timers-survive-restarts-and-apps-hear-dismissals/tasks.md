## 1. Design

- [ ] 1.1 Choose how the Timer helper survives a shell restart, or how its
  loss is reported, and record the decision and the rejected routes in
  design.md. Check on the board, read-only, which cgroup the helper lands in
  today (`/proc/<pid>/cgroup`). Proof (board, read-only): the transcript
  under `docs/evidence/timer-restart/board/`.

## 2. Host

- [ ] 2.1 Implement the timer decision. Proof (host):
  `python3 tests/test_term_apps.py`, with a case that stops the shell's
  process group while a helper waits.
- [ ] 2.2 Record the close cause in the broker and emit reasons 1, 2 and 3
  from the adaptor. Store actions and emit `ActionInvoked`. Proof (host):
  `python3 tests/test_notification_center.py && python3 tests/test_notification_dbus.py`,
  on a private bus with the real broker and adaptor.
- [ ] 2.3 Draw actions in the shade at the 99 px floor. Proof (host):
  `cargo test --offline --lib` in `nix/rust-shell-client`, and renders at
  100% and 200% under `docs/evidence/notification-actions/host/`.

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

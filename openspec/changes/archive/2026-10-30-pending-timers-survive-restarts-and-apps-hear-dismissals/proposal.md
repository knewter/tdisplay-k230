## Why

Two alert gaps remain after `apps-and-timers-can-alert-the-user`.

- **A timer can vanish silently.** When the Timer's card is closed, a helper
  waits for the deadline. It runs inside `shell.service`'s cgroup, so a shell
  restart or a crash kills it. The person is never told, and "Timer finished"
  never arrives.
- **Apps never hear what the person did.** When someone dismisses an app's
  notification in the shade, or taps its action, the app is not told
  (`NotificationClosed` for a person's close, and `ActionInvoked`). An app
  that waits for either waits forever, and an app cannot offer an action that
  works.

These are tasks 4.2 and 4.3 of `apps-and-timers-can-alert-the-user`, moved
here on the operator's decision of 2026-10-29 ("Record and defer",
`docs/evidence/glass-checklist-2026-10-29/operator-report.md`). Those tasks
read:

- 4.2: "A shell restart ends a pending timer silently. Decide whether the
  helper should move out of `shell.service`'s cgroup, or the restart should
  say so."
- 4.3: "`NotificationClosed` for closes the person makes in the shade, and
  `ActionInvoked`, are not delivered. Open a successor change if an app needs
  either."

## What Changes

- A pending timer either survives a shell restart, or its loss is reported to
  the person when the shell comes back. Design task 1.1 picks one.
- The desktop notification adaptor sends `NotificationClosed` with reason 2
  (dismissed by the user) when the person dismisses an app's event in the
  shade, and `ActionInvoked` when the person taps an action the app offered.

## Non-goals

- Timer behaviour across suspend. This image does not suspend, so the helper
  keeps `CLOCK_MONOTONIC` (`apps-and-timers-can-alert-the-user` task 4.1).
- Notification sounds or vibration. The handheld has no speaker path or
  motor for them.
- Inline replies and other notification-spec extensions beyond actions.

## Capabilities

### Modified Capabilities

- `runtime/notification-center`: pending timers survive a shell restart, and
  apps hear dismissals and actions.

## Impact

- `nix/term-apps/k230_term_apps.py` (the `timerd` helper) and `nix/shell.nix`
  (where the helper runs).
- `tools/notification_center.py` (the broker records who closed an event, and
  any action) and `tools/notification_dbus.py` (the adaptor emits the
  signals).
- The shell's shade, if actions are drawn as buttons.
- Host-testable on a private bus. The board is needed for the restart check
  and the glass check.

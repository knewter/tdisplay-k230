## Context

The layers are userspace and Nix. The Timer's detached helper
(`k230_term_apps.py timerd`) starts in a new session but stays in
`shell-ui.service`'s cgroup (Sway's unit). That unit is `PartOf=` and
`BindsTo=` `shell.service`, so restarting the shell kills the helper; on
2026-10-30 a waiting helper was gone 5 s after `systemctl restart shell`
(`docs/evidence/timer-restart/board/design-check.md`). The shell
user has no `systemd --user` instance. The adaptor (`tools/notification_dbus.py`)
sends `NotificationClosed` only for `CloseNotification` calls (reason 3). The
broker (`tools/notification_center.py`) records dismissals, but not who made
them, and stores no actions.

## Goals / Non-Goals

**Goals:** no timer lost without the person knowing, and apps told about
dismissals and actions.

**Non-Goals:** suspend-aware timers, sounds, inline replies.

## Decisions

Settled by task 1.1 (`docs/evidence/timer-restart/board/design-check.md`).

- **Timer: survive, not just report.** A system socket unit,
  `k230-timer.socket` (`/run/k230-timer.sock`, owner root, group `shell`,
  mode 0660, `Accept=yes`), starts one `k230-timer@.service` instance per
  pending timer, with `User=shell`. The instance is in its own cgroup under
  `system.slice`, outside `shell.service` and `shell-ui.service`, so a shell
  restart does not reach it. The Timer card sends the deadline over the
  connection instead of forking a helper. Taking the timer back (adopt),
  pausing and resetting end that instance. The broker's trusted map names
  the new unit, so its "Timer finished" keeps the Timer's identity. Nothing
  is resident while no timer is pending.
- **Dismissals: the broker records the cause** (expired, dismissed by the
  person, or closed by the app), and the adaptor maps them to the
  specification's reasons 1, 2 and 3.
- **Actions: the broker keeps an app's action list,** the shade draws at
  most a fixed small number of action buttons at the 99 px floor, and a tap
  reaches the adaptor as `ActionInvoked`.
- **As built (host, 2026-10-30).** The adaptor holds one subscription to the
  broker, which pushes close and action notices; the broker refuses a tap
  (`app-unavailable`) when no adaptor listens. The shade draws at most two
  actions and names a tap by index (`invoke`); the broker keeps the keys. A tap
  sends `ActionInvoked`, then closes the notification with reason 2. The timer
  instance records `{pid, deadline, initial}` in `/run/k230-timer-state`
  (outside `shell.service`'s `RuntimeDirectory`) so a reopened card can adopt
  it; the request carries seconds left, and the instance adds its own
  `CLOCK_MONOTONIC`.

Rejected:

- **A resident timer daemon.** Rejected before in
  `apps-and-timers-can-alert-the-user` for its always-on memory cost.
- **`systemd-run --user` or a user manager.** The `shell` user has none.
- **A sudo rule for `systemd-run`.** It would give the shell user a way to
  start arbitrary units.
- **Only reporting the loss.** That is the fallback, not needed: the
  socket unit needs no new privilege.
- **`CLOCK_BOOTTIME`.** It is not needed while the image does not suspend.

## Risks / Trade-offs

- [Moving the helper out of the shell's cgroup leaves a stray process if the
  Timer is uninstalled] → it exits at its deadline either way.
- [Action buttons crowd the shade's rows] → host renders at 100% and 200%
  before any board work.

## Migration Plan

None. Existing notifications have no actions, so nothing changes for them.

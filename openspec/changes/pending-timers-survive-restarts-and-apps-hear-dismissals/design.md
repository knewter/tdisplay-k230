## Context

The layers are userspace and Nix. The Timer's detached helper
(`k230_term_apps.py timerd`) starts in a new session but stays in
`shell.service`'s cgroup, so systemd kills it when the shell stops. The shell
user has no `systemd --user` instance. The adaptor (`tools/notification_dbus.py`)
sends `NotificationClosed` only for `CloseNotification` calls (reason 3). The
broker (`tools/notification_center.py`) records dismissals, but not who made
them, and stores no actions.

## Goals / Non-Goals

**Goals:** no timer lost without the person knowing, and apps told about
dismissals and actions.

**Non-Goals:** suspend-aware timers, sounds, inline replies.

## Decisions

Open for task 1.1. The current leaning:

- **Timer: survive, not just report.** Run the helper in its own transient
  scope or service outside `shell.service`, for example through a small
  system unit template started over a narrow path. Fall back to reporting
  ("A timer was stopped when the shell restarted") if no unprivileged route
  exists.
- **Dismissals: the broker records the cause** (expired, dismissed by the
  person, or closed by the app), and the adaptor maps them to the
  specification's reasons 1, 2 and 3.
- **Actions: the broker keeps an app's action list,** the shade draws at
  most a fixed small number of action buttons at the 99 px floor, and a tap
  reaches the adaptor as `ActionInvoked`.

Rejected:

- **A resident timer daemon.** Rejected before in
  `apps-and-timers-can-alert-the-user` for its always-on memory cost.
- **`CLOCK_BOOTTIME`.** It is not needed while the image does not suspend.

## Risks / Trade-offs

- [Moving the helper out of the shell's cgroup leaves a stray process if the
  Timer is uninstalled] → it exits at its deadline either way.
- [Action buttons crowd the shade's rows] → host renders at 100% and 200%
  before any board work.

## Migration Plan

None. Existing notifications have no actions, so nothing changes for them.

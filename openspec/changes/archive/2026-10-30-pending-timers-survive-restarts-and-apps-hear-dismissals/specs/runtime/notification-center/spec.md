## ADDED Requirements

### Requirement: A pending timer is never lost silently

*Grounding (2026-10-29): `apps-and-timers-can-alert-the-user` design.md records that the Timer's detached helper lives in `shell.service`'s cgroup and is ended by a shell restart; the operator moved the follow-up here on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

*Grounding (2026-10-30): on the board, with injected touch, a 2:00 Timer whose card was closed survived `systemctl restart shell` a minute in and posted "Timer finished" once at its deadline, from `k230-timer@.service` (`docs/evidence/timer-restart/board/README.md`).*

When the shell restarts while a Timer runs with its card closed, either the
timer SHALL still post "Timer finished" once at its deadline, or the person
SHALL be told, when the shell returns, that the timer was stopped.

#### Scenario: Shell restarts with a timer pending

- **WHEN** a 2-minute Timer is running with its card closed and the shell
  restarts a minute in
- **THEN** "Timer finished" arrives once at the original deadline, or a
  notification says the timer was stopped

### Requirement: Apps hear when the person dismisses or acts on their notification

*Grounding (2026-10-29): `tools/notification_dbus.py` emits `NotificationClosed` only for an app's own `CloseNotification` (reason 3), and the broker stores no actions (`apps-and-timers-can-alert-the-user` design.md, Risks). The operator moved the follow-up here on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

*Grounding (2026-10-30): on the board, a probe app on the shell bus received `NotificationClosed` reason 2 for an injected swipe and for Dismiss all, `ActionInvoked` then reason 2 for tapped actions drawn as 99 px buttons, and reason 3 for its own close (`docs/evidence/notification-actions/board/README.md`). Expiry (reason 1) is grounded by host tests only. A restarted adaptor does not report closes for notifications posted before the restart. No glass contact; the operator waived it on 2026-10-29.*

When the person dismisses an app's notification, the desktop notification
service SHALL send that app `NotificationClosed` with reason 2. When an
event expires, it SHALL send reason 1. When the app offered actions, the
shade SHALL show them as tap targets at the shell's 99 px floor, and a tap
SHALL send the app `ActionInvoked` with that action's key.

#### Scenario: The person dismisses an app's notification

- **WHEN** an app's notification is dismissed in the shade
- **THEN** the app receives `NotificationClosed` for its id with reason 2

#### Scenario: The person taps an action

- **WHEN** an app's notification offers an action "Open" and the person taps it
  in the shade
- **THEN** the app receives `ActionInvoked` for its id with the key it gave
  for "Open"

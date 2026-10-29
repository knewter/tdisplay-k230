## ADDED Requirements

### Requirement: Apps raise notifications through the desktop notification service

*Grounding: source read of `nix/shell.nix` and `tools/notification_center.py` (no `org.freedesktop.Notifications` owner exists; only the shell is a trusted source). Host behaviour: `tests/test_notification_dbus.py` against a private bus, the real broker and the real adaptor. Nothing here is observed on the board.*
*Grounding (2026-10-27/29, board): `busctl Notify` and a `GApplication` probe produced banners and history entries, and an app naming itself "Shell" was recorded as "Application" (`docs/evidence/apps-alert/README.md`, tasks 3.1 and 3.2). On glass, build `ql630glm…`, the operator saw an app banner at 22:32:48Z: "saw it" (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`). `notify-send` itself is not on the image.*
The shell userspace SHALL own `org.freedesktop.Notifications` on the application session bus and SHALL pass an app's notification to the notification broker, so that the call returns an id and the event follows the same preview, history and dismissal rules as any other. Urgency critical SHALL become important; any other urgency SHALL be ordinary. The app SHALL appear under its own name and themed icon, SHALL NOT appear as the Shell or the System, SHALL NOT be raised above important, SHALL NOT be kept as an ongoing event or aimed at a window, and its preview text SHALL be hidden as for any unsolicited event. A replace request SHALL update only the same app's event, and a close request SHALL remove only that app's event.

#### Scenario: notify-send
- **WHEN** an app or a terminal runs `notify-send "Build finished"`
- **THEN** a preview appears with a neutral source and summary, and History shows the app's name and "Build finished"

#### Scenario: App claims to be the system
- **WHEN** an app sends a notification whose name is "Shell", "System" or similar
- **THEN** History shows it as "Application" and it cannot be pinned or raised to critical

#### Scenario: Urgent notification
- **WHEN** an app sends a notification with urgency critical
- **THEN** it is shown as important and the person can still dismiss it

#### Scenario: App closes its notification
- **WHEN** an app closes the id it was given
- **THEN** that event leaves History and no other app's event does

### Requirement: A running timer alerts the person without its card open

*Grounding: source read of `nix/term-apps/k230_term_apps.py` (expiry wrote only `\a`; the device has no speaker); host behaviour in `tests/test_term_apps.py`. Nothing here is observed on the board.*
*Grounding (2026-10-27, board, injected): Timer banners with the card open and closed, one history entry each, and the countdown resumed after a reopen (`docs/evidence/apps-alert/README.md`, tasks 3.3 and 3.4). On glass, 2026-10-29, the operator saw the Timer's banner (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*
When the Timer reaches zero it SHALL post an important "Timer finished" notification stating the duration. If the person closes the Timer's card while it runs, the countdown SHALL continue without a visible card and SHALL post the same notification when it ends, once. Reopening the Timer while a closed countdown is pending SHALL show that countdown running. A paused timer SHALL NOT alert.

#### Scenario: Expiry with the card open
- **WHEN** the Timer counts down to zero in the foreground
- **THEN** a "Timer finished" preview appears and the entry stays in History

#### Scenario: Expiry with the card closed
- **WHEN** the person starts a timer, closes its card, and the time elapses
- **THEN** a "Timer finished" preview appears over whatever is on screen

#### Scenario: Reopen during the countdown
- **WHEN** the person reopens the Timer before the time elapses
- **THEN** it shows the remaining time counting down and does not alert twice

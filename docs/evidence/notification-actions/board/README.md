# Notification actions and close reasons on the board (task 3.2)

Evidence class: **board, injected touch plus a probe app on the shell bus**.
No glass. The operator asked for injected events and captures instead of
fingers on the glass (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).

The build is `q8hbkb1g…` (master at `6415e84c`), test-activated on
2026-10-30 at 00:46:22Z. The probe is
`action_probe.py`. It posts through `org.freedesktop.Notifications` and
prints every `NotificationClosed` and `ActionInvoked` signal with a UTC
timestamp. It ran as the `shell` user with the adaptor's own interpreter and
`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/shell-bus/bus`, for example:

```sh
python3 -I action_probe.py 600 "Probe dismiss:open=Open,snooze=Snooze" \
  "Probe action:open=Open,snooze=Snooze" "Probe app close!close:open=Open"
```

`probe-1.log` to `probe-4.log` are the four runs' complete
output. Signals are broadcast, so a probe that was still running also printed
signals for a later probe's ids (the last lines of `probe-2.log`).

## What happened

| UTC | Injected step | Probe output |
| --- | --- | --- |
| 00:55:28 | none; three notifications posted | `capabilities body,actions` |
| 00:55:33 | none; the probe closes id 3 itself | `NotificationClosed 3 3` |
| 00:57:55.0 | tap Snooze on "Probe action" (1026,451), `na-01` → `na-02` | `ActionInvoked 2 snooze`, then `NotificationClosed 2 2` |
| 01:05:38.6 | swipe the top row "Probe swipe" right (650,200 → 980,202), list of five, `na-08` → `na-09` | `NotificationClosed 7 2` |
| 01:05:58 | `systemctl restart shell-notification-dbus` | none |
| 01:06:01 | none; two new notifications posted to the restarted adaptor | `capabilities body,actions` |
| 01:06:07 | none; the probe closes id 2 itself | `NotificationClosed 2 3` |
| 01:06:33.2 | tap Open on "After restart" (685,306), `na-10` → `na-11` | `ActionInvoked 1 open`, then `NotificationClosed 1 2` |
| 01:11:49 | none; two notifications posted (one with an action) | `capabilities body,actions` |
| 01:12:00.3 | tap Dismiss all (1136,35), `na-13` → `na-14` | `NotificationClosed 3 2`, `NotificationClosed 4 2` |

`na-01-shade.png` shows a row with Open and Snooze. Each button is 99 px tall
and the row is 115 px taller than a row without actions. After the tap
(`na-02`) the row is gone and the count drops from 3 to 2. `na-12-cleared.png`
is the shade after Dismiss all removed the rest (see the third finding). The history count was 0
afterwards.

A notification expiring (reason 1) was not waited for on the board. It is
covered by the host tests with the broker's injected clock (task 2.2).

## Findings

- **A sideways swipe cannot dismiss a row while the landscape list fits
  without scrolling.** With one or two notifications (00:58:07, 00:58:29,
  00:59:06 and 00:59:41Z, `na-03-after-swipe.png`), the shell logged
  `touch-down` and `touch-up` but drew no swipe and sent no dismissal. A
  host check of the shell's own gesture functions, with the board's
  coordinates, shows the cause. `shade_panel_close_zone` treats a list that
  is already at its end as a place where a close drag may start, so the
  touch becomes a close-drag candidate. `close_drag_refused` releases a
  candidate only on Settings and Help, so the horizontal motion never
  reaches `notification_swipe_start`. Once five notifications made the list
  scroll, the same swipe dismissed the row (01:05:38Z). This code predates
  this change (`e5f27ecd`, `4cba5ccb`); it is reported, not fixed here.
- One swipe on the five-row list failed (01:03:15Z), 2 s after `surface
  shade` had reopened the panel. The one that worked came after a vertical
  scroll and a 3 s wait. The cause of the failure was not isolated.
- Restarting the adaptor forgets its id map. Notifications posted before the
  restart (ids 1 and 4–6 here) gave their apps no `NotificationClosed` when
  Dismiss all removed them. The restarted adaptor also numbered its new
  notifications from 1 again, so the ids it returns can repeat ids an app
  received before the restart.

Limits: injected touch only, with no glass contact. The banner path was not
captured. The adaptor's "re-subscribe after a restart" was shown by the
signals of notifications posted after the restart, not by older ones.

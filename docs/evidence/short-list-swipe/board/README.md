# A short landscape list swipes to dismiss (task 2.1)

Evidence class: **board, injected touch plus a probe app on the shell bus**.
No glass contact; the operator asked for injected events and captures
instead (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).

Build `49mnsl2s…-nixos-system-nixos-26.11.20260919.20b1ddd` (master at
`6c164a02`), copied to the board and test-activated on 2026-10-30 at
13:20:54Z. Notifications were posted with
`docs/evidence/notification-actions/board/action_probe.py`, run as the
`shell` user on the shell bus, as in that change's evidence. Swipes were
injected through uinput by the bench driver. Captures are `grim` of the
1232x568 output. `probe-logs.txt` holds the three probes' complete output
(signals are broadcast, so each probe also printed the later ones).

Before the fix, on build `q8hbkb1g…`, the same sideways swipes on a one- or
two-row list drew nothing and sent nothing
(`docs/evidence/notification-actions/board/README.md`, Findings).

| UTC | List | Injected step | Probe output |
| --- | --- | --- | --- |
| 13:21:55.2 | one row, "Only row" (`sl-01`) | swipe right, 650,200 → 980,202 in 600 ms | `NotificationClosed 1 2`; the list is empty (`sl-02`) |
| 13:22:20.5 | two rows (`sl-03`); the newest, "Lower row" with buttons, is on top | swipe right, 650,330 → 980,332 (the swipe starts on the row's Open button band) | `NotificationClosed 3 2` (`sl-04`) |
| 13:22:24.3 | one row left, "Upper row" | swipe left, 980,200 → 650,202 | `NotificationClosed 2 2` (`sl-05`) |
| 13:22:57.4 | one row, "Close check" (`sl-06`) | drag up, 850,200 → 850,40 in 500 ms | none; the panel followed the finger and settled back open (`sl-07`) |
| 13:23:26.9 | same | drag up, 850,230 → 850,2 in 250 ms | none; the shell logged `unmap` at 13:23:27.379Z and Home shows (`sl-08`) |

The two upward drags show that the short list still closes the shade. The
first was too short and slow to pass the close threshold and settled back,
as a close drag does anywhere else. The row was then cleared with Dismiss
all (`NotificationClosed 4 2` at 13:23:44Z), and the history count was 0.

Limits: injected touch only. The tap-to-open path and action buttons were
not re-tested here; they are unchanged by this fix.

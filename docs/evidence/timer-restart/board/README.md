# A pending Timer across a shell restart (task 3.1)

Evidence class: **board, console plus injected touch**. No glass. The
operator asked for injected events and captures instead of fingers on the
glass (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).

Build `q8hbkb1g…-nixos-system-nixos-26.11.20260919.20b1ddd` (master at
`6415e84c`). It was copied to the board and test-activated with
`switch-to-configuration test` at 00:46:22Z on 2026-10-30. Taps were injected
through uinput by the bench driver (`ui.py`). Captures are `grim` of the
1232x568 output.

`design-check.md` holds the task 1.1 check on the old build. It shows the
helper inside `shell-ui.service` and no alert after a restart.

## The task as written: a 2:00 Timer, restart a minute in

```text
$ switch-to-configuration test                                 # 00:46:22Z
the following new units were started: … k230-timer.socket …
$ systemctl is-active k230-timer.socket; ls -ld /run/k230-timer.sock /run/k230-timer-state
active
srw-rw---- 1 root  shell  0 … /run/k230-timer.sock
drwx------ 2 shell shell 40 … /run/k230-timer-state
```

The Timer card was opened from the drawer. "−1 min" was tapped three times,
from 5:00 down to 2:00 (`tr-10-set-2min.png`). Start was tapped at about
01:08:06Z (`tr-11-running.png`, 01:58 left). The card's window was then
killed through sway.

```text
$ systemctl list-units 'k230-timer@*'                          # 01:08:11Z
k230-timer@2-5-3187_3187-1000.service loaded active running Pending Timer countdown (PID 3187/UID 1000)
$ cat /proc/3209/cgroup          # the k230_term_apps.py timerd process
0::/system.slice/system-k230\x2dtimer.slice/k230-timer@2-5-3187_3187-1000.service
$ cat /run/k230-timer-state/k230-timer.json
{"pid": 3209, "deadline": 2069.3805492419997, "initial": 120}
$ sudo systemctl restart shell                                 # 01:09:07.096Z
$ systemctl is-active shell shell-ui                           # 01:09:18Z
active
active
$ systemctl list-units 'k230-timer@*'; kill -0 3209
k230-timer@2-5-3187_3187-1000.service loaded active running …
3209 alive
```

```text
$ journalctl -u 'k230-timer@*'
20:08:08.570 systemd[1]: Started Pending Timer countdown (PID 3187/UID 1000).
20:10:06.749 systemd[1]: k230-timer@2-5-3187_3187-1000.service: Deactivated successfully.
$ journalctl -t k230-shell-rust
20:10:07.319 rust-shell 47421ms notification-banner-map-request
$ sudo -u shell k230-notifications history                     # 01:10:24Z
{"schema":1,"count":1,"events":[{"id":10,"source":"Timer","icon":"k230-timer",
 "summary":"Timer finished","body":"02:00 elapsed","priority":"important",
 "timestamp":1793322606,…}],…}
```

(The journal prints local time, UTC−5.) `1793322606` is 01:10:06Z, the 2:00
deadline. "Timer finished" arrived once, from the source "Timer", and the shell
that had restarted showed its banner within a second. `tr-12-shade-finished.png`
is the shade afterwards. The notification was then cleared with Dismiss all.

## Two earlier runs on the same build

- **A 4:00 Timer, restart about 9 s in.** Only one of three "−1 min" taps
  landed, because the card was still starting. Start was at 00:48:24Z,
  `systemctl restart shell` ran at 00:48:33Z, and the instance
  `k230-timer@0-3-1778_1778-1000` kept running. It ended at 19:52:23 local,
  and the history held one "Timer finished", "04:00 elapsed", with timestamp
  `1793321543` (00:52:23Z).
- **Reopening adopts the countdown.** A 5:00 Timer was started at about
  00:54:18Z and its card closed. The shell was restarted at about 00:54:24Z,
  and the instance was still listed 30 s later. Reopening the card at
  00:55:04Z showed `04:14 Running` (`tr-20-reopened-adopts.png`). Reset then
  showed `05:00 Ready` (`tr-21-reset.png`), and the instance ended at
  19:55:01 local with no alert.

A first adoption attempt is not used here. Its Start tap landed before the
card was ready, so no timer started. The run above waited 6 s before tapping.

Limits: injected touch only, with no glass contact. The banner was seen in the
journal, not in a capture. Each restart was a `systemctl restart shell`; a
reboot was not tested, and a pending timer is not expected to survive one
(`/run`).

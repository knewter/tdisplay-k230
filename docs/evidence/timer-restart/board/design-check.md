# Timer restart design check (task 1.1)

Evidence class: **board, console plus injected touch**. Build `p393r76c…`,
2026-10-30. A Timer was set to 1:00 and started with injected taps at about
00:13:08Z. Its card was then closed (the window was killed through sway).

```text
$ systemctl show shell -p KillMode -p ControlGroup        # 00:12:27Z
ControlGroup=/system.slice/shell.service
KillMode=control-group
$ (pid of `k230_term_apps.py timerd`, cgroup)              # 00:13:10Z
pid 1950: …/python3 …-k230-term-apps/lib/…/k230_term_apps.py timerd …
cgroup: 0::/system.slice/shell-ui.service
$ systemctl show shell-ui -p PartOf -p BindsTo -p KillMode
BindsTo=shell.service PartOf=shell.service KillMode=control-group
$ sudo systemctl restart shell                             # 00:13:16Z
$ kill -0 1950                                             # 00:13:21Z
1950 gone
```

The helper lives in `shell-ui.service`'s cgroup (Sway's unit), not in
`shell.service`'s as the proposal assumed. `shell-ui.service` is `PartOf=` and
`BindsTo=` `shell.service`, so restarting the shell ends the helper, and
the timer due at about 00:14:08Z can no longer fire. `systemd-run --user` is
unavailable: the `shell` user has no user manager. The `shell` user's only
sudo rights are `systemctl reboot` and `systemctl poweroff`.

```text
$ sudo -u shell env XDG_RUNTIME_DIR=/run/shell k230-notifications history   # 00:15:05Z
{"schema":1,"count":0,"events":[],"preview":null}
```

No "Timer finished" arrived after the deadline (about 00:14:08Z). The loss
was silent, which is the defect this change addresses.

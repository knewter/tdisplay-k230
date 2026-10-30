# Time zone design check (task 1.1)

Evidence class: **board, read-only console** (over SSH). The one write
attempt was refused by timedated, so nothing changed. Build `p393r76c…`,
2026-10-30 00:09:06Z.

```text
$ readlink /run/current-system
/nix/store/p393r76ci9zqlsy0vsn9gdvcxgx2pml0-nixos-system-nixos-26.11.20260919.20b1ddd
$ command -v timedatectl pkcheck pkexec
/run/current-system/sw/bin/timedatectl          # no pkcheck, no pkexec
$ systemctl is-enabled polkit.service
not-found
$ ls -l /etc/localtime
lrwxrwxrwx 1 root root 29 Oct 29 18:37 /etc/localtime -> /etc/zoneinfo/America/Chicago
$ timedatectl show
Timezone=America/Chicago
LocalRTC=no
CanNTP=yes
NTP=yes
NTPSynchronized=yes
$ sudo -u shell timedatectl set-timezone Europe/London
Failed to set time zone: Access denied
$ ls /usr/share/zoneinfo
ls: cannot access '/usr/share/zoneinfo': No such file or directory   # zones are in /etc/zoneinfo
$ id shell
uid=1000(shell) gid=995(shell) groups=995(shell),17(audio),26(video),174(input),991(k230-modem),996(seat)
$ systemctl show systemd-timedated -p LoadState -p ActiveState
LoadState=loaded
ActiveState=active
$ sudo -n -l -U shell     # 00:12:27Z
    (ALL : ALL) NOPASSWD: …/systemctl reboot, …/systemctl poweroff
```

Host-side reading of the pinned nixpkgs (`20b1ddd1`):
`nixos/modules/config/locale.nix` makes `/etc/localtime` a managed
`direct-symlink` only while `time.timeZone` is non-null. The systemd patch set
does not disable timedated's `SetTimezone`.

# Time zone and network time: board check (task 3.1)

Evidence class: **board, injected input, native `grim` capture, console**.
Not glass. The operator replaced the glass step with injected checks on
2026-10-30 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).

Build `/nix/store/sqd58h8czqrxlnlhab6iid2n0swcvyab-nixos-system-nixos-26.11.20260919.20b1ddd`
(`93ae2a97`), test-activated at 00:31:29Z on 2026-10-30. Times are UTC.
Taps were injected through `ui.py`'s uinput touch device.

## After activation

```text
/etc/localtime -> /etc/zoneinfo/America/Chicago    (re-linked at activation: time.timeZone is now null)
k230-time.socket active; srw-rw---- root shell /run/k230-time.sock
Timezone=America/Chicago NTP=yes NTPSynchronized=yes
```

## Changing the zone (00:32:51Z)

`tz-01-date-time.png`: the page before, America/Chicago (UTC-05:00), 19:32:28.
`tz-02-areas.png` is the area page; `tz-03-europe-1.png` is Europe, page 1 of
4; `tz-04-europe-2.png` is page 2, after an injected Next. One tap on London:

```text
00:32:51.876 rust-shell time-request zone Europe/London
00:32:51.925 systemd: Created slice Slice /system/k230-time.
00:32:53.255 python3: k230-time: ok
00:32:53.388 k230-time@0-1-2462_2462-1000.service: Deactivated successfully.
00:32:53.404 rust-shell time-request zone Europe/London -> ok
/etc/localtime -> /etc/zoneinfo/Europe/London; Timezone=Europe/London
```

`tz-05-date-time-london.png`: Date & time reads Friday, October 30 2026,
00:32:54, and Europe/London (UTC+00:00). The running clocks followed with
no restart: `tz-06-shade-london.png` shows the shade at `00:33 Fri, Oct 30`,
and `tz-08-clock-app-london.png` shows the Clock app at `00:33`, Friday 30
October. Chicago was on daylight time (UTC-05:00) and London on GMT, so the
clocks moved 5 hours.

## Network time off (00:33:47Z)

One tap on the Network time switch:

```text
00:33:47.732 rust-shell time-request network-time off
00:33:48.899 rust-shell time-request network-time off -> ok
/var/lib/k230-time/network-time-off (root, 0644); systemd-timesyncd inactive; NTP=no
```

`tz-10-network-off.png`: the row reads `Off` and the switch is off.

## The helper refuses everything else (00:34:00Z)

`/var/tmp/tzprobe.py` connects to the socket and sends each argument as a
request line.

```text
as shell:  'reboot now' -> error request
           'zone Etc/GMT+5' -> error zone            (not in zone1970.tab)
           'zone ../../etc/shadow' -> error request
           'network-time maybe' -> error request
           'set-ntp off' -> error request
           'time 12:00' -> error request
as nobody: 'zone UTC' -> PermissionError 13            (socket is root:shell 0660)
as root:   'zone UTC' -> error peer                    (only the shell user is answered)
after: Timezone=Europe/London NTP=no                  (nothing changed)
```

## Persistence

- `switch-to-configuration test` again at 00:34:15Z: `/etc/localtime` still
  pointed to Europe/London, NTP was still no, timesyncd was inactive, and the
  flag remained. No units failed.
- Reboot: `sqd58h8c` was promoted with the charger online (`online` = 1), and
  kernel, initrd and dtbs matched the old default. `/boot/bootargs.txt` was
  backed up to `/var/tmp/bootargs.txt.before-sqd58h8c`. Reboot at 00:35:19Z;
  the shell was back by 00:37:29Z. Europe/London held, NTP was no,
  timesyncd was inactive with `ConditionResult=no`, and the flag remained.
  `tz-11-shade-after-reboot.png` shows the shade at `00:37 Fri, Oct 30`, and
  `tz-12-date-time-after-reboot.png` shows Date & time with Europe/London
  and Network time Off.

## Restored (00:38Z)

Through the UI: Network time switched on (`-> ok` at 00:38:06Z), then
America, page 3 of 11 (`tz-13-america-3.png`), then Chicago (`-> ok` at
00:38:24Z). `tz-14-restored.png` shows America/Chicago (UTC-05:00) and
Network time Synchronized. Over SSH: `Timezone=America/Chicago`, `NTP=yes`,
`NTPSynchronized=yes`, timesyncd active, no flag.

Not shown: Home's clock widget in another zone. The terminal was in front
for that capture. Home reads time through the same
`home_widgets::clock::now_local` as the shade, which did follow.

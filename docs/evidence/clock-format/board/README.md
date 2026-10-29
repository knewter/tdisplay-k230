# Clock format: board captures

Evidence class: **board, injected input, native `grim` capture**. It is not
glass evidence. Task 3.1 of `settings-chooses-a-12-or-24-hour-clock`.

Build: `/nix/store/p393r76ci9zqlsy0vsn9gdvcxgx2pml0-nixos-system-nixos-26.11.20260919.20b1ddd`
(`a9d8411b`), test-activated with `switch-to-configuration test` on
2026-10-29. The boot default remains `ql630glm…`. Input was injected through
the uinput touch device of `ui.py`. Times are UTC; the panel shows
America/Chicago (UTC-05:00).

| File | When (UTC) | Shows |
| --- | --- | --- |
| `shade-24h.png` | ~22:53 | Before the switch: no `clock-format` file exists, and the shade reads `17:53`. |
| `date-time-24h.png` | 22:56:09 | Date & time with the switch off: `24-hour`, Time `17:56:09`. |
| `date-time-12h.png` | 22:56:18 | One injected tap on the switch at 22:56:17.6. The switch is on, it reads `12-hour`, and Time reads `5:56:18 PM`. `/var/lib/k230-shell-prefs/clock-format` was written at 22:56:17.688 with `12-hour`. |
| `home-12h.png` | ~22:56 | Home's Bubble clock: `5` over `56`, with `PM · Thu, Oct 29`. |
| `shade-12h.png` | ~22:56 | The shade reads `5:56 PM`. |
| `clock-app-12h.png` | ~22:57 | The Clock app, launched from the drawer: `5:56`, with `PM · Thursday 29 October`. |
| `weather-12h.png` | ~22:57 | Weather's status line reads `Updated 5:42 PM`. The location line is blacked out in this copy. |
| `idle-clock-12h.png` | ~22:58 | The idle clock screen, after 80 s without input (idle timeout 1 min, on the charger): `5:58`, with `PM · Thursday 29 October`. |
| `shade-after-restart.png` | ~22:59 | `systemctl restart shell` at 22:58:54. The unit was active again at 22:58:56, the file still read `12-hour`, and the shade reads `5:59 PM`. |

## Reboot (after promotion)

The operator approved promotion on 2026-10-29 ("promote it"), with the charger
online (`bq25890-charger-0/online` = 1). The kernel, initrd and dtbs matched
the old default. `/boot/bootargs.txt` was backed up to
`/var/tmp/bootargs.txt.before-p393r76c`, its `init=` was pointed at
`p393r76c…/init`, and the system profile was set to the same path.

| File | When (UTC) | Shows |
| --- | --- | --- |
| `shade-after-reboot.png` | ~23:40 | `systemctl reboot` at 23:36:34. SSH and the shell were back by 23:38:42. `/run/current-system` and the kernel command line's `init=` both name `p393r76c`, the file reads `12-hour`, and the shade reads `6:38 PM`. |

The Home widgets other than Bubble (Thin, Dot matrix) were not placed on the
board's Home. The host renders (`../host/`) cover them.

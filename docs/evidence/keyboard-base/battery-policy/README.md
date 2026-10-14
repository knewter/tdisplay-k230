# Low-battery policy on the board (task 6.6; board-read)

2026-10-14, landscape image `s53ywx90…`, second board in the keyboard case.
Evidence class: **board-read** (journal and sysfs samples). No camera frame:
the bench webcam cannot see the panel, and the two shade captures the script
tried to take failed (`grim` as user `shell` could not write into the
root-owned log directory).

## Method

`policy-test.sh` ran on the board as a transient unit (`systemd-run`). It:

1. wrote `/run/k230-battery-policy.json` = `{"warn": 100, "urgent": 99,
   "shutdown": 98}`, the override the service reads every loop;
2. set the charger's Hi-Z (`echo 0 > …/bq25890-charger-0/online`): USB-C
   stays plugged, the input is disconnected and the battery carries the
   system, a real discharge of about 400 mA;
3. once "Battery critically low" appeared, set `online` back to 1 (the cable
   cancel, by software), then cut it again and let the countdown run out;
4. sampled charger and gauge every 10 s into `samples-2026-10-14.log`.

A first start at 00:37:15 CDT had no `PATH` under `systemd-run` and was
stopped within 30 s; its Hi-Z had already produced the first "Battery low"
line. The charger was restored (which re-arms the warnings) and the run
restarted at 00:37:59.

## Result (`journal-2026-10-14.log`, times CDT)

| Time | Gauge | Policy |
| --- | --- | --- |
| 00:38:07 | 100 %, Discharging, ~-400 mA | `Battery low: 100% remaining.` |
| 00:42:37 | 99 % | `Battery very low: 99% remaining.` |
| 00:47:07 | 98 %, two readings | `Battery critically low: Shutting down in 60 seconds.` |
| 00:47:21 | charger `online` 1, Charging | — |
| 00:47:22 | | `Charging: Shutdown cancelled.` |
| 00:47:52 | charger `online` 0 again | — |
| 00:48:52 | 98 %, two readings | `Battery critically low: Shutting down in 60 seconds.` |
| 00:49:52 | | logind: `poweroff requested from client … (unit k230-battery-policy.service)` |
| 00:49:58 | | `Reached target System Power Off`; `systemd-shutdown`: sync, SIGTERM |

The notifications, the countdown, the cancel and the orderly shutdown all
happened as specified.

## The board did not power off

After the last journal line the panel stayed lit and the board stopped
responding; the operator pressed the reset button. This kernel has no
power-off path: OpenSBI here offers no SRST extension (`dmesg` lists TIME,
IPI, RFENCE, DBCN, HSM only), and the K230 PMU driver was ported without
LILYGO's system-off callback (power-key task 1.2). So `systemctl poweroff`
ends in a halt with the board still powered, and on battery that keeps
draining the cell. Until a power-off handler exists, the policy's shutdown
protects the filesystem but not the battery.

Also found: the charger's Hi-Z survived the halt and the reset (REG00 0xff,
`online` 0 after boot) because nothing resets the BQ25896. It was cleared by
hand. The test's last-moment "reconnect the charger" hook was put in
`/run/systemd/system-shutdown/`, which systemd-shutdown does not read, so it
never ran.

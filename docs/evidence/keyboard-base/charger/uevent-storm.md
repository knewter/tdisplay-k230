# Charger uevent storm while charging (2026-10-18)

Patch: `nix/patches/mainline/bq25890-poll-without-irq.patch` (commit
db133d1f). Board: T-Display K230 with the keyboard base, mainline 7.3-rc5,
landscape DSI-1. Evidence class: board observation over SSH.

## Symptom

While the BQ25896 was charging, `/tmp/bp.py` (`tools/board-pointer.py`)
exited 0 but sway never listed "k230 scripted pointer"; `udevadm monitor`
showed the kernel `add` with no `UDEV` event. `systemd-udevd` sat in
`i2c_dw_xfer` <- `bq25890_get_chip_state` <- `power_supply_uevent`.

## Cause

Mainline `bq25890_update_state()` re-samples the chip on every property read
and calls `power_supply_changed()` when the state differs. Building a uevent
reads every property, and udevd reads them again, so while any field
chatters each uevent can raise the next. With the driver's dynamic debug on,
`CHRG_STAT` flipped between 2 (fast charge) and 3 (done) within 20-40 ms,
15 times in 35 s, after an `online` 0 -> 1 cycle near a full battery.

The fix: a polled chip (no interrupt; this board) is sampled only by the
2 s poll work, so a property read reports the cached state and change
uevents are capped at one per poll.

## Measurement

Same procedure before and after: `echo 0 > online; sleep 3; echo 1 >
online`, then `udevadm monitor --kernel --subsystem-match=power_supply` for
20 s, with `file bq25890_charger.c +p` in dynamic debug.

| | before (80b12e58 system) | after (db133d1f) |
| --- | --- | --- |
| change uevents in 20 s | 83 (all `bq25890-charger-0`; 4.2/s) | 5 |
| chip state reads (debug lines) | 1449 | 13 |
| `systemd-udevd` wchan at the end | `i2c_dw_xfer` | `do_epoll_wait` |

After the fix, during a charge cycle (status Charging, Charging, Full),
`board-pointer.py 'move 600 300; wait 2500'` was listed by
`swaymsg -t get_inputs` 3 times out of 3.

## Limits

- The 2026-10-17 storm during a long fast charge (about 5/s) was not
  re-created; this test charged a battery already at 100%, which reaches
  termination within seconds. The mechanism is the same feedback, and the
  fix removes the read-path sampling whatever field chatters.
- Status in sysfs now lags the chip by up to 2 s.

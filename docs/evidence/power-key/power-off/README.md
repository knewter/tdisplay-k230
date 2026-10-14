# PMU power-off on the mainline kernel (2026-10-14)

Second board in the keyboard case, landscape image `9m683dbp…` (commit
`21923ce8`: the vendor's system-off callback restored in
`nix/patches/mainline/k230-pmu-pwrkey.c`). USB-C connected throughout.

## Before

Keyboard-base 6.6 (`../../keyboard-base/battery-policy/README.md`): the
policy's `systemctl poweroff` reached `systemd-shutdown`, then the board
halted with the panel lit and stayed powered until the reset button. No
power-off handler existed (no SBI SRST extension; PMU driver ported without
the callback).

## After

- Boot (board-read, `dmesg`): `K230 PMU power key input registered on IRQ
  17`, and no `failed to register PMU poweroff handler` warning.
- Restart (board-read): the deploy's reboot into this system returned on its
  own (`readlink /run/current-system` = `9m683dbp…`). Not observed by camera
  or serial.
- Power off: `systemd-run --on-active=2 systemctl poweroff` over SSH at
  07:08:36 UTC. Journal of that boot ends `Finished System Power Off`,
  `systemd-shutdown: Syncing …`, `Sending SIGTERM …` at 02:08:49 CDT.
  Operator: "it shut off this time" (panel dark, unlike the earlier halt).
- Power on: operator held the power key about 3 s ("i held the power key for
  three seconds and it woke"). USB-C stayed connected; the cable alone did
  not start it. Next boot began 02:09:15 CDT; the charger read `online` 1 and
  the gauge `Full` afterwards.

Evidence classes: board-read (journal, dmesg) and operator report. No serial
console was attached and no camera frame was taken; the kernel's own
`PMU poweroff:` message is printed after journald stops, so it is not in the
journal.

## Limits

- Triggered by `systemctl poweroff`, not by the shell's confirmed Power off
  sheet (power-key task 3.4 asks for that path) and not by the battery policy.
  All three end in the same `systemctl poweroff`.
- Wake is the power key's long press only; a USB-C plug-in is not a wake
  source in this configuration.

## Why

A person who takes the handheld to another time zone cannot make its clock
right. The zone is fixed when the image is built (`time.timeZone =
"America/Chicago"` in `nix/k230.nix`), so the only fix is a rebuild. Network
time cannot be turned off or on from the device either. Settings' Date & time
page shows the zone and whether the clock is synchronized, but cannot change
them.

This is task 4.2 of `settings-has-about-and-date-time-pages`, moved here on
the operator's decision of 2026-10-29 ("Split them out",
`docs/evidence/glass-checklist-2026-10-29/operator-report.md`) so that change
could archive. That task read: "Changing the time zone and NTP from the
device: needs a design for privilege and persistence, since `time.timeZone`
is build-time. Needs its own proposal."

## What Changes

- The Date & time page lets a person pick a time zone from a list and turn
  network time on or off.
- A narrow privileged path, owned by the system rather than the shell, applies
  the choice. The shell user never gains general root access.
- The choice survives a reboot and a switch to a new build.

## Non-goals

- Setting the time by hand while network time is off. That can follow once
  this change shows the privileged path is sound.
- Detecting the zone automatically (from the modem, GNSS or an IP lookup).
- The 12/24-hour clock (`settings-chooses-a-12-or-24-hour-clock`).

## Capabilities

### Modified Capabilities

- `runtime/device-settings`: Settings changes the time zone and network time.

## Impact

- `nix/k230.nix` (`time.timeZone`) and a new system service or polkit rule
  for the privileged path. Which one is decided in design task 1.1.
- `nix/rust-shell-client/src/device_info.rs` (the page becomes editable) and a
  zone list page.
- Needs the physical board: privilege, persistence across a reboot and a
  `switch-to-configuration`, and the glass check. Zone-list layout can be
  checked on the host.

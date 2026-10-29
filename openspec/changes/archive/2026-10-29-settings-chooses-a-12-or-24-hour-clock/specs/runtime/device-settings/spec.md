## ADDED Requirements

### Requirement: Settings chooses a 12-hour or 24-hour clock

*Grounding (2026-10-29): Settings' Date & time page shows "Clock format: 24-hour" as a fixed value (`nix/rust-shell-client/src/device_info.rs`), and the Python clocks format with `%H:%M` (`nix/term-apps/k230_term_apps.py`, `k230_exhibition.py`). The operator moved this follow-up out of `settings-has-about-and-date-time-pages` on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

*Grounding (2026-10-29): host tests and renders (`docs/evidence/clock-format/host/`); board, injected, on `p393r76c…`: the switch, every clock in 12-hour form, a shell restart and a reboot (`docs/evidence/clock-format/board/`); glass, 2026-10-29 23:54Z, the operator flipped the switch and saw the shade and Home follow (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*

Settings' Date & time page SHALL offer the clock format as a choice between
24-hour and 12-hour, with a hit region that meets the shell's 99 px floor. The
choice SHALL persist across a shell restart and a reboot, and SHALL default to
24-hour when it has never been set or cannot be read. Every clock drawn by the
shell and by the shell's own apps SHALL follow it within a minute of a change,
without a restart.

#### Scenario: Switching to a 12-hour clock

- **WHEN** a person sets the clock format to 12-hour at 21:05
- **THEN** the shade, Home and the Date & time page show 9:05 PM, and the
  idle clock screen shows it the next time it draws

#### Scenario: No preference yet

- **WHEN** the shell starts and the clock-format preference has never been set
- **THEN** every clock is 24-hour, as before this change

## MODIFIED Requirements

### Requirement: Settings has a Date & time page

*Grounding (2026-10-27/28, board): `/run/systemd/timesync/synchronized` existed after sync on build `kllh24ww…`, and grim captures of the page in both orientations are in `docs/evidence/settings-about/`. The operator read it on glass on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`). Changing the zone or network time moved to `settings-sets-the-time-zone-and-network-time`.*
*Grounding (2026-10-29): the clock format became a switch in `settings-chooses-a-12-or-24-hour-clock`; board and glass evidence in `docs/evidence/clock-format/`.*
*Grounding: `nix/rust-shell-client/src/device_info.rs` (`localtime_r`, the `/etc/localtime` link, the timesyncd stamp); `nix/k230.nix` sets the zone at build time and `nix/hardware.nix` enables timesyncd and a time-sync-ordered RTC write. No board observation yet.*
Settings SHALL offer a Date & time row, ahead of About, that opens a page showing the date, the time, the time zone with its UTC offset, whether the clock is synchronized from the network, and the clock format. The date and time SHALL come from the system's local time so they follow the installed time zone, and the time SHALL follow the chosen clock format. The clock format row SHALL be the switch that "Settings chooses a 12-hour or 24-hour clock" describes; the page SHALL NOT offer a control that changes a setting the image cannot change. It SHALL have the same Back link, type roles, vision text step and refresh as About.

#### Scenario: Reading the clock

- **WHEN** a person opens Settings and taps Date & time
- **THEN** the page shows today's date, the time to the second, the zone name with its UTC offset, whether the clock is synchronized and the clock format

#### Scenario: Clock not yet synchronized

- **WHEN** the system has not set its clock from the network
- **THEN** the network time row says Not synchronized

#### Scenario: Portrait at the largest text step

- **WHEN** the vision text step is 200% on the portrait panel
- **THEN** every row fits the panel and Back is at least 99 pixels tall

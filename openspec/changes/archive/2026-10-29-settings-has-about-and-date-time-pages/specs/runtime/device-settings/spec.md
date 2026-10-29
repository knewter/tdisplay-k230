## ADDED Requirements

### Requirement: Settings has an About page for the installed build

*Grounding (2026-10-27/28, board, injected): grim captures of About on builds `kllh24ww…` and `vf91pbq6…` in both orientations, and About's System row matched `readlink /run/current-system` (`docs/evidence/settings-about/README.md`). The operator read both pages on glass on 2026-10-29, build `37g1magg…`: "8 good" (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`).*
*Grounding: `nix/rust-shell-client/src/device_info.rs` reads `/etc/hostname`, the `/run/current-system` link, `/proc/sys/kernel/osrelease`, `/proc/uptime` and `statvfs`; the Cellular and Location pages (`modem_ui.rs`) are the page pattern. No board observation of the values yet.*
Settings SHALL offer an About row, the last row before Power, that opens a read-only page showing the device name, the system generation as the short hash and name of its store path, the kernel release, the uptime, the storage free and total, and the shell build as its version and the short store-path hash of the running shell. A value that cannot be read SHALL show "Unavailable" rather than a guessed value. The page SHALL NOT show an IP address, MAC address, SSID, serial number or secret. It SHALL have a Back link to Settings at least 99 pixels tall, use the shell's type roles and the vision text step, and refresh while open so the uptime moves.

#### Scenario: Which build is installed

- **WHEN** a person opens Settings and taps About
- **THEN** the page shows the device name, an eight-character system hash with its name, the kernel release, the uptime, the storage free and total and the shell version with its hash

#### Scenario: A value cannot be read

- **WHEN** a source such as the system generation link is missing
- **THEN** that row says Unavailable and the other rows still show

#### Scenario: Largest text step, landscape

- **WHEN** the vision text step is 200% on the landscape panel
- **THEN** every About row fits on the panel without scrolling and Back is still tappable

#### Scenario: Leaving About

- **WHEN** a person taps Back on About
- **THEN** Settings returns with its rows where they were

### Requirement: Settings has a Date & time page

*Grounding (2026-10-27/28, board): `/run/systemd/timesync/synchronized` existed after sync on build `kllh24ww…`, and grim captures of the page in both orientations are in `docs/evidence/settings-about/`. The operator read it on glass on 2026-10-29 (`docs/evidence/glass-checklist-2026-10-29/operator-report.md`). Changing the format, zone or network time moved to `settings-chooses-a-12-or-24-hour-clock` and `settings-sets-the-time-zone-and-network-time`.*
*Grounding: `nix/rust-shell-client/src/device_info.rs` (`localtime_r`, the `/etc/localtime` link, the timesyncd stamp); `nix/k230.nix` sets the zone at build time and `nix/hardware.nix` enables timesyncd and a time-sync-ordered RTC write. No board observation yet.*
Settings SHALL offer a Date & time row, ahead of About, that opens a read-only page showing the date, the time, the time zone with its UTC offset, whether the clock is synchronized from the network, and the clock format. The date and time SHALL come from the system's local time so they follow the installed time zone. The page SHALL say 24-hour for the clock format while the shell has no other format, and SHALL NOT offer a control that changes a setting the image cannot change. It SHALL have the same Back link, type roles, vision text step and refresh as About.

#### Scenario: Reading the clock

- **WHEN** a person opens Settings and taps Date & time
- **THEN** the page shows today's date, the time to the second, the zone name with its UTC offset, whether the clock is synchronized and the clock format

#### Scenario: Clock not yet synchronized

- **WHEN** the system has not set its clock from the network
- **THEN** the network time row says Not synchronized

#### Scenario: Portrait at the largest text step

- **WHEN** the vision text step is 200% on the portrait panel
- **THEN** every row fits the panel and Back is at least 99 pixels tall

### Requirement: The Settings rows reach the touch floor

*Grounding: host tests in `nix/rust-shell-client/src/service_ui.rs` and `render.rs` for the 99 px height. On the board, injected taps opened Date & time and About from Settings in both orientations (`docs/evidence/settings-about/`). Row heights were not measured on the board.*
Every Settings row that opens a page, including Cellular, Location, Date & time and About, SHALL be at least 99 pixels tall at every vision text step, and a tap on it SHALL open its page in both orientations whether or not the modem has answered.

#### Scenario: Rows with and without the modem

- **WHEN** Settings is shown with and without the modem rows
- **THEN** Date & time and About open their pages in both orientations and Power remains tappable below them

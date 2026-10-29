## Why

Two questions have no answer on the device.

- **Which build is this?** A person (or the operator) holding the handheld cannot
  tell which system generation, kernel and shell build is installed, or how long
  it has been up and how much storage is left, without a console. This is the
  recurring "which build is installed" question (gap 10 of
  `docs/design/shell-ux-review-webos-firefoxos-2026-10.md`).
- **Is the clock right?** Settings shows no date, time, time zone or whether the
  clock was set from the network. The time zone is a build-time constant
  (`nix/k230.nix`, `time.timeZone`), so a wrong clock cannot be told apart from
  an unsynchronized one.

## What Changes

- Settings gets two rows after Cellular and Location, in this order: **Date &
  time** and **About**. About is the last row before Power. They are present
  whether or not the modem has answered, and are plain tap rows at the 99 px
  touch floor.
- **About** page (read-only): device name, system generation (short store-path
  hash and name from `/run/current-system`), kernel release, uptime, storage
  free and total, and the shell build (version and short store-path hash of the
  running binary).
- **Date & time** page (read-only): date, time, time zone with its UTC offset,
  whether the clock is synchronized from the network, and the clock format
  (24-hour, the only one the shell has).
- Both pages follow the Cellular and Location page pattern: Back to Settings,
  the shell's type roles and the vision text step, portrait as the scaled
  568x1232 artwork and landscape as three columns of cards.
- The shared plain-row height rises from 88 to the 99 px floor, so the existing
  Cellular and Location rows meet it too.

Neither page shows an IP address, MAC, SSID, serial number or any secret.

## Non-goals

- No change to the time zone, the clock format or NTP from the device. The shell
  has no clock-format preference and no privileged path to change the zone; those
  stay a recorded follow-up (tasks 4.1 and 4.2), not invented here.
- No time-zone list, and no About rows for IP, MAC, Wi-Fi or modem identity.
- No change to the shade, the Home clock or the Settings sleep row (gap 4) and
  no Settings search (gap 10's remaining bullets).

## Capabilities

### Modified Capabilities

- `runtime/device-settings`: Settings offers read-only About and Date & time
  pages.

## Impact

- `nix/rust-shell-client/src/device_info.rs` (new: readers, layout, hit-test)
- `nix/rust-shell-client/src/render.rs`, `service_ui.rs`, `glyph.rs`, `main.rs`
  (rows, intents, painting, the page's state and one-second refresh)
- `nix/rust-shell-client/examples/render_settings_about_evidence.rs` (host renders)
- `docs/evidence/shell-responsive/settings-*.png` (regenerated: Settings gained
  two rows) and `docs/evidence/settings-about/`

Host-verifiable now. It needs the physical board for the glass check and to
confirm the values (tasks 3 and 4).

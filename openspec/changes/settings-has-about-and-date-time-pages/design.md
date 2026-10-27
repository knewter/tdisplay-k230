## Context

Layer: userspace (the Rust shell client, `nix/rust-shell-client`); no kernel,
device-tree or image change. Settings' Cellular and Location pages
(`modem_ui.rs`) are the pattern: a page enum, a public view handed to the
renderer in `ServiceView`, one layout function that both the painter and the
tap read, and a Back link.

## Decisions

- **A new module, `device_info.rs`.** It owns the readers, the page state, the
  layout and the Back hit-test. The renderer gets only `InfoPublic` (a page and
  label/value rows), so paint cannot read the system itself.
- **Row placement: plain rows, About last.** The Cellular and Location rows are
  "plain label-and-value rows" placed from the base rows' bottom and leading
  the Power column. Date & time and About join that list after them
  (`settings_plain_row_count`), so the order is Wi-Fi, Brightness, Volume,
  Keyboard, Reduce motion, [Key backlight], [Cellular, Location], Date & time,
  About, then Power. Hit-testing, the wide column offset, scroll extent and
  paint all read the same helpers, as before. The rows are always present, so
  the wide third column no longer depends on the modem.
- **Touch floor.** The plain-row height was `max(88)`; it is now the 99 px
  floor (`SHADE_TAP_MIN`). This also lifts the existing modem rows, which sat
  under it.
- **Sources, no helpers.** Every value is read directly, with no D-Bus and no
  child process, and a missing source shows "Unavailable" rather than a guess.
  - Device: `/etc/hostname`.
  - System: the `/run/current-system` link target's store leaf, shown as the
    first 8 characters of its hash and the name.
  - Kernel: `/proc/sys/kernel/osrelease`. Uptime: `/proc/uptime`.
  - Storage: `statvfs("/")`, free and total in decimal units.
  - Shell: the crate version and the short hash of the store path that holds
    the running executable (`current_exe`).
  - Date and time: `localtime_r`, so it follows `TZ` and `/etc/localtime`
    exactly as every other program does.
  - Time zone: the `/etc/localtime` link target after `zoneinfo/`, with the
    UTC offset from `tm_gmtoff`.
  - Network time: the existence of `/run/systemd/timesync/synchronized`, the
    stamp systemd-timesyncd creates after setting the clock. The image enables
    timesyncd (`nix/hardware.nix`, `k230-rtc-sync` waits on `time-sync.target`).
- **Clock format is a fixed "24-hour" row.** The shell's clocks are 24-hour and
  there is no preference to hook a toggle to, so the row states the fact and no
  toggle is invented.
- **Fresh data.** The open page is re-read once a second from the main loop so
  the time and uptime move; no timer runs while it is closed.
- **Layout.** Portrait is the 568x1232 artwork in one column. Landscape fills
  three columns top to bottom so the largest text step (200%) still fits 568 px
  without scrolling. At 150% and above the portrait header drops to the compact
  form (title under a high Back link) so six rows fit 1232 units at 200%. A
  value too long for its card shrinks to the role size and then ellipsizes; the
  system row therefore shows the hash first.
- **Summary values on the Settings rows are static** ("Clock and time zone",
  "Device and build"). A live time there would make the Settings renders and the
  committed pixel-identity references depend on the wall clock.

## Rejected

- **`timedatectl` or `org.freedesktop.timedate1`.** Needs a child process or a
  D-Bus client the shell does not have, for facts available from three files.
- **A 12/24-hour toggle now.** No existing preference; it would need new state,
  a settings-broker path and every clock consumer changed.
- **Changing the time zone from the device.** `time.timeZone` is build-time and
  `/etc/localtime` is a read-only store link on NixOS; a change needs a design
  for privilege and persistence, left as a follow-up.
- **Showing the IP address (gap 10's suggestion).** Excluded by this change's
  no-secrets rule for evidence and screenshots; the Wi-Fi page already shows
  connection state.

## Risks

- `/run/systemd/timesync/synchronized` comes from systemd's source, not from a
  board observation here. Until task 3.2 records it on the board the sync row
  is UNVERIFIED and could read "Not synchronized" while synchronized.
- The hostname may be the NixOS default if the image does not set one; the page
  shows whatever `/etc/hostname` holds.
- Portrait Settings now scrolls at 100% by the two rows' height plus its prior
  overflow.

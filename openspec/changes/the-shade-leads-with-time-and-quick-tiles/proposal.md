## Why

The landscape shade is where a person looks for the time, how the device is
doing, and what came in. A design pass over board captures from 2026-10-27
(`docs/evidence/nrf9151/shell/board/shade-location-searching.png`) and the
host renders found the following:

- **IA.** "Notifications" titles the left column, which holds controls. The
  list on the right has no heading of its own.
- **No time.** Apps run full-screen, so the device has no status bar, and the
  shade does not show the clock either.
- **Status.** Battery, location and cellular state are squeezed into one
  right-aligned caption under the title. Wi-Fi state is not shown at all.
- **Quick controls.**
  - Keyboard is the shade's only tile.
  - Wi-Fi, Location and Cellular each take two taps through Settings.
  - webOS's device menu and Firefox OS's utility tray both put these
    one tap from the top.
- **Rhythm.** The sliders float in the middle of the column, with a large
  empty gap above them and a lone tile below.

## What Changes

These changes apply to the wide (landscape) shade only. Portrait and HDMI
outputs keep their single-column layout.

- **Left column, top to bottom:**
  1. The time in large type, the date under it, and "Settings ›" at the
     right.
  2. One status line: battery, and the cellular and location glyphs. Wi-Fi's
     state is on its tile.
  3. A grid of quick tiles, two columns wide, each at least 99 px tall:
     - **Wi-Fi:** shows its state and opens the Wi-Fi page.
     - **Keyboard:** show or hide, as now.
     - **Location:** toggles directly and shows Off, Searching or Fix.
     - **Cellular:** shows its state and opens the Cellular page.

     Location and Cellular appear only once the modem has answered.
  4. The brightness and volume sliders at the bottom of the column.
- **Right column:** "Notifications" titles the list, with "Dismiss all" on
  the same row. The list starts under that heading.

## Capabilities

### Modified Capabilities

- `runtime/notification-center`: the shade states each fact once (wide
  layout, time and tiles).

## Impact

- `nix/rust-shell-client/src/service_ui.rs` (layout, hit-testing)
- `nix/rust-shell-client/src/render.rs` (painting)
- `nix/rust-shell-client/src/main.rs` (the Location tile's toggle)

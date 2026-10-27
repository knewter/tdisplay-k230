## Why

A person who is reading, typing or sleeping next to the handheld cannot make
it stop covering the top of the screen. Every received text, Wi-Fi or app
notification raises a banner for five seconds, and the only way to avoid one
is to leave the device with the screen off. There is no quiet mode, so the
person either puts up with the interruptions or does without notifications.

The image has no other alert channel to silence. The handheld has no speaker
(`the-handheld-plays-through-its-speaker` is parked, and nothing in `nix/`
emits a notification sound) and no vibration motor, so the banner is the whole
interruption. This change is about that banner only.

Review gap 12 of `docs/design/shell-ux-review-webos-firefoxos-2026-10.md`
named Do Not Disturb as a quick control the shade redesign left out: "suppresses
banners but keeps history (the broker has priorities but no mute mode)".

## What Changes

- **A quiet mode.** While it is on, the shell does not show a banner for a
  new event, but the event is still recorded in history, still counted, and
  still listed in the shade.
- **What still breaks through.** A banner that the broker marks as an alert
  still appears: critical events (the base-battery "critically low" event),
  and important events from a trusted shell-side source such as the Timer's
  "Timer finished". Apps that reach the broker through the
  `org.freedesktop.Notifications` adaptor, SMS, and unknown senders never
  break through, because the broker already caps them at ordinary, or at
  important with `app: true`.
- **One new preview field.** The broker adds a boolean to its already
  privacy-filtered preview saying whether it may interrupt quiet mode. The
  client treats a missing field as false.
- **A shade tile.** The landscape shade's quick-tile grid goes from two
  columns to three, so Do Not Disturb is added without a third row. The grid
  stays two rows tall, the sliders stay on the 568 px panel at the largest
  vision text step, and every tile stays at least 99 px tall.
- **A status indicator.** While quiet mode is on, a moon glyph joins the
  glyphs at the right of the shade's status line.
- **A Settings row.** Portrait and HDMI shades have no tile grid, so
  Settings gains a Do Not Disturb switch row. The row and the tile read and
  write one state.
- **Persistence.** The choice is a one-word file under the shell user's
  state directory, read at start, so it survives a reboot and a shell restart.
  A missing or unreadable file means off.

## Non-goals

- Sound, vibration, LED or haptic suppression. None exists on this image.
- Scheduled quiet hours, auto-expiry, "until morning", or per-app rules.
- Hiding notifications from the shade, or a lock screen.
- Changing the privacy default (banners already hide the text) or what counts
  as critical in the broker.
- Changing the Timer's priority, or the apps-and-timers delegate rules.
- A tile for any other quick control (Radios off, Stay awake).

## Capabilities

### Modified Capabilities

- `runtime/notification-center`: quiet mode, its break-through rule, and the
  three-column tile grid with the status indicator.
- `runtime/device-settings`: a Do Not Disturb row.

## Impact

- `tools/notification_center.py` (one preview field),
  `tests/test_notification_center.py`.
- `nix/rust-shell-client/src/service_data.rs` (parse the field),
  `service_ui.rs` (`ShadeTile`, `shade_tiles`, `shade_tile_rect`, the tap
  intent), `render.rs` (tile, status glyph), `glyph.rs` (moon),
  `main.rs` (filter the preview, read and write the preference),
  a new small preference module beside `keyboard_base.rs`.
- `nix/shell.nix`: one `systemd.tmpfiles.rules` entry for the state directory.

Depends on `the-shade-leads-with-time-and-quick-tiles` landing first (it
introduces the tile grid this change widens). Host work needs no board. The
banner staying away, the tile and the reboot persistence need the board, and
the glass check needs the operator.

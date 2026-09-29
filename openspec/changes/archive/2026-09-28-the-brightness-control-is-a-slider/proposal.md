## Why

A person adjusting brightness today only has a discrete `−`/`+` stepper,
reachable only from inside Settings, one navigation hop from the shade
they just pulled down. `docs/design/shell-polish-review-2026-09.md`
finding #8 ("Brightness is a stepper everywhere, not a slider", Settings/
Shade, P2) recommends a drag slider instead, matching Android's Quick
Settings shade, which puts a full-width brightness slider directly under
the tile grid on every pull (§5, "Brightness slider: none"). The same
review's finding #1 ("Touch targets are 4.3mm physical (330.9ppi × 56px),
well under Material's ~9mm", Global, P1) applies directly to the stepper's
existing `−`/`+` glyphs, which are smaller still.

Live brightness itself already works on hardware
(`docs/evidence/backlight/live-hs/README.md`, source `d76e126f`): the
backend writes `/sys/class/backlight/canaan-dsi-backlight/brightness`
through `tools/device_settings.py`, invoked once per stepper tap by
`ServiceRequest::Brightness` (`nix/rust-shell-client/src/service_data.rs`).
That per-tap Python subprocess is fine for a stepper's occasional discrete
steps; it is not fine for a slider's ~20-30 writes/sec while a finger
drags, which would spawn a process per sample and pile up behind the
service worker's single request queue.

## What Changes

- Replace the Settings brightness stepper (the `−`/`+` glyphs and their
  release-only tap classification in `panel_intent`) with a Material-3-
  style slider: a full-width track, a thick active portion up to the
  thumb, a round thumb, and a cheap vector sun glyph at each end. The
  touch target is the whole row (110px), well past the review's 56px
  floor.
- Add the same slider to the top of the pull-down shade (quick settings),
  as the design review's Android comparison recommends, reusing one
  component (`nix/rust-shell-client/src/slider.rs`, new) so the two never
  visually drift apart. The shade's existing drag-to-close gesture is
  unaffected: the slider's own touch band is excluded from the close-drag
  candidacy zone (`service_ui::shade_panel_close_zone`), the same way the
  scrollable notification list already is, so a horizontal drag on the
  slider never starts a close drag and a drag anywhere else on the sheet
  still closes it exactly as before.
- Add a throttled, fire-and-forget live-write path
  (`ServiceRequest::BrightnessLive`) that writes the backlight sysfs
  attribute directly from the shell process — no subprocess per write —
  throttled to about 20-30 writes/sec while dragging, always followed by
  one authoritative `ServiceRequest::Brightness` (the existing Python
  path, with its real read-back and UI feedback) on release. Clamp every
  value the slider itself can produce to a minimum of 3%, so the slider
  can never drive the screen fully black.
- Reflect the real backlight value (a sysfs read via
  `ServiceRequest::RefreshSettings`) whenever Settings or the shade opens,
  so an external change to brightness shows in either place.

## Non-goals

- No change to the panel/kernel backlight device, the DSI transport, or
  DPMS retention — those are already covered by the archived
  `2026-09-26-the-panel-brightness-is-adjustable` change and its
  `display/backlight` requirements; this change only replaces the touch
  model on top of the existing, already-working device.
- No change to the theme picker, its carousels, or its thumbnails
  (`theme_ui.rs`, `theme_carousel.rs`, `theme_thumbnails.rs`,
  `theme_catalog.rs`, `appearance.rs`) — a separate, concurrent change
  owns those files in the same crate.
- No quick-settings tile grid or shade clock/date header (review findings
  #6/#7) — out of scope here, tracked separately.
- Real-finger board acceptance is explicitly left open by this change; see
  tasks.md and AGENTS.md's evidence-class distinctions. This worktree does
  not touch the board or `/dev/ttyACM0`.

## Capabilities

### Modified Capabilities

- `display/backlight`: retires the "Settings brightness stepper drives
  the real device" requirement (see its own Reason/Migration) and adds
  four requirements in its place — the slider control itself, the
  shade's own slider without disturbing its close gesture, the throttled
  direct-sysfs live-write path, and reflecting the real value on open.

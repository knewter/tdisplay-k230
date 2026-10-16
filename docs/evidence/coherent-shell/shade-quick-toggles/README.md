# Shade quick toggle and tap floor (tasks B.1–B.3, B.5)

## What changed

- **Keyboard toggle (B.1/B.2).** The Shade has a keyboard quick-toggle card
  under the volume slider (`SHADE_TOGGLE_TOP`..+`SHADE_TOGGLE_H`). A tap sends
  the same `ServiceRequest::KeyboardToggle` that Settings' Keyboard row sends,
  under the same `ControlState::Action` gate. An unavailable or read-only
  keyboard paints the same `control_text`, muted, and the tap does nothing.
  Brightness stays the existing slider, as design decision 2 says.
- **Tap floor (B.5).** Every Shade tap band is at least `SHADE_TAP_MIN` = 99
  logical px (48dp at ~2.07 px/dp):
  - Settings entry: 0..112.
  - Dismiss all: 112..211. It was 116..190, 74 px.
  - Keyboard toggle: 362..461.
  - Notification rows: 116 px each.

  The sliders are drag bands. They keep `slider::TOUCH_TARGET_PX` (56) and now
  sit at 214 and 290, below Dismiss all. The list moved from 418 to 480. The
  empty-state tile now sits where the list starts; before, it overlapped the
  volume slider at 262..334.

## Host evidence (2026-10-16)

Evidence class: host renders and unit tests.

- `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml
  --no-fail-fast`: 549 lib tests passed (2 ignored), and all integration
  targets passed. The portrait pixel-identity renders, which do not include
  the Shade, are unchanged.
- New tests:
  - `the_shade_keyboard_toggle_sends_the_settings_request_only_when_available`:
    568x1232, 1232x568 and 1280x800; Action sends, Unavailable and ReadOnly
    send nothing, and both band edges hit.
  - `every_shade_tap_band_meets_the_floor_without_overlap`: band heights, no
    overlap between the tap and drag bands, and Dismiss all firing across its
    whole band (including y 200, which used to be dead space).
- The existing Shade tests moved with the list (+62 px):
  - `shade_and_settings_hits_are_bounded_and_cancel_scroll_taps` (B.3: scroll,
    item action, Dismiss all and Settings are unaffected);
  - `a_drag_on_the_shade_panel_closes_unless_it_would_scroll_the_list`;
  - `notification_swipe_tracks_reversal_and_refuses_critical_or_changed_rows`;
  - two pixel probes in `render.rs`.
- Renders: `host/*.png` from `cargo run --offline --example
  render_shade_quick_toggles_evidence -- <dir>`, with the keyboard available
  and unavailable, at 0 and 4 notifications, on the portrait panel, the
  landscape panel and HDMI.

Board check (B.4): see below once it has been run.

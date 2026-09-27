## RENAMED Requirements

- FROM: `### Requirement: The Settings brightness stepper drives the real device`
- TO: `### Requirement: The brightness control is a slider, not a stepper`

## MODIFIED Requirements

### Requirement: The brightness control is a slider, not a stepper

*Host build proof: `cargo test` and `cargo clippy --all-targets` pass for
`nix/rust-shell-client` (value↔x mapping, clamping, the live-write
throttle and gesture disambiguation are covered by unit tests in
`src/slider.rs` and `src/service_ui.rs`); `nix build .#handheld-shell-rust`
and the full `k230-coherent-shell` system closure cross-build. These are
host/build proofs only — see the open real-finger task below for physical
acceptance.*

The Settings screen and the pull-down shade SHALL each present the same
brightness control as a full-width Material-3-style slider (a track with
a thick active portion up to the thumb, a round thumb, and a sun glyph at
each end), replacing the previous discrete `−`/`+` stepper. Touch-drag
anywhere on the track SHALL set the value live while dragging; releasing
anywhere on the track SHALL commit that value through
`/sys/class/backlight/*/brightness` via the existing
`tools/device_settings.py` path (`ServiceRequest::Brightness`), exactly as
the stepper's taps did. The touch target SHALL be at least 56 physical
pixels tall, per `docs/design/shell-polish-review-2026-09.md` finding #1
(4.3mm/56px touch targets, well under Material's ~9mm guidance).

A drag SHALL never set brightness below 3%, so the slider itself can
never drive the panel fully black; a value read from sysfs (an external
change) SHALL be shown as-is, not raised to this floor.

*Grounding: `nix/rust-shell-client/src/render.rs`'s Settings row loop and
Shade paint arm both call one shared `paint_slider` (new
`src/slider.rs`); `service_ui::slider_band` gates both the Settings row
and the Shade's own header band on the same
`ControlState::Writable` check `tools/device_settings.py`'s
`Settings.brightness()` already reports.*

#### Scenario: A person drags the Settings slider

- **WHEN** a person drags a finger across the Settings brightness track
- **THEN** the panel's brightness visibly follows the finger while
  dragging, and the release commits the value the finger left it at

#### Scenario: A person taps the slider track without dragging

- **WHEN** a person taps a point on the track without a preceding drag
- **THEN** the value jumps directly to that point (tap-to-jump), the same
  as a drag released at that point

#### Scenario: A drag never reaches full black

- **WHEN** a person drags the slider to its very left (lowest) end
- **THEN** the requested brightness is clamped to 3%, never 0%

## ADDED Requirements

### Requirement: The shade carries the same slider, without disturbing its close gesture

*Host build proof: same `cargo test`/`clippy`/`nix build` evidence as the
sibling requirement above; `service_ui.rs` unit tests exercise
`shade_panel_close_zone`'s exclusion of the slider band directly. Real-
finger acceptance on the board is a separate, currently open task (see
`tasks.md`); this requirement's behavioral claim is unverified on
hardware pending that pass. <!-- UNVERIFIED: real-finger board pass -->*

The pull-down shade (quick settings) SHALL show the same brightness
slider component at the top of its own header, above the notification
list, matching Android's Quick Settings placement
(`docs/design/shell-polish-review-2026-09.md` §5, "Android's Quick
Settings shade puts a full-width brightness slider directly under the
clock/tile grid on every pull"). A horizontal drag that starts on the
slider's own band SHALL NOT be promoted into the shade's drag-to-close
gesture; a drag that starts anywhere else on the sheet (the header above
it, the backdrop below it, or the notification list once scrolled to its
end) SHALL still close the shade exactly as it did before this change.

*Grounding: `service_ui::shade_panel_close_zone` excludes
`service_ui::slider_band`'s own Y range from close-drag candidacy the
same way it already excludes the scrollable notification list; both
exclusions are sampled once at touch-down
(`ShellClient::panel_close_candidate`) and never re-evaluated mid-gesture,
so a touch already owned by one can never be reinterpreted as the other
partway through.*

#### Scenario: A horizontal drag on the shade's slider never closes the shade

- **WHEN** a person's finger lands on the shade's brightness slider band
  and drags left or right
- **THEN** the brightness value follows the drag and the shade does not
  begin closing

#### Scenario: A drag elsewhere on the shade still closes it

- **WHEN** a person's finger lands outside the slider band (the header,
  the backdrop, or a fully-scrolled notification list) and drags in the
  sheet's closing direction past the existing threshold
- **THEN** the shade closes exactly as it did before this change

### Requirement: Live drags write the backlight directly, throttled, never blocking the UI

*Host build proof: `nix/rust-shell-client/tests/service_data_module.rs`
covers `write_backlight_live` (percent-to-raw scaling against a fixture
sysfs tree, out-of-range rejection, a missing device) and confirms
`ServiceRequest::BrightnessLive` never shells out to
`tools/device_settings.py`. `src/slider.rs`'s own unit tests cover the
~20-30/s throttle gate and that release always reads the true value
regardless of it.*

While a brightness slider drag is in progress, the system SHALL send
backlight writes at roughly 20-30 per second, each writing the backlight
sysfs `brightness` attribute directly from the shell's existing service
worker thread (no subprocess spawned per write), so the Wayland/UI thread
is never blocked waiting on one. The drag's release SHALL always send one
additional, authoritative write through the existing
`tools/device_settings.py` path (`ServiceRequest::Brightness`) regardless
of the live-write throttle's own timing, so the committed value is always
the real, read-back-verified one.

*Grounding: `nix/rust-shell-client/src/service_data.rs`'s
`write_backlight_live` mirrors `tools/device_settings.py`'s
`Settings.backlight()` lookup (exactly one
`/sys/class/backlight/*` device, a valid `max_brightness`) but calls
`fs::write` directly instead of spawning `k230-settings`; the existing
stepper's `ServiceRequest::Brightness` already proved that per-request
subprocess path works but was only ever exercised at stepper-tap
frequency, never at drag frequency.*

#### Scenario: A drag sends throttled live writes

- **WHEN** a person drags the slider continuously for one second
- **THEN** on the order of 20-30 direct sysfs writes are sent, not one per
  touch-motion sample and not one Python subprocess per write

#### Scenario: Release always commits the true value

- **WHEN** a drag releases at a moment the live-write throttle had not
  yet fired for the finger's current position
- **THEN** the release still sends the finger's true final value through
  the authoritative, read-back-verified request

### Requirement: Opening Settings or the shade reflects the real brightness

*Host build proof: same evidence as above; `ShellClient::refresh_route`'s
change (Shade now also submits `ServiceRequest::RefreshSettings`) is
covered by the existing worker/reply test fixtures.*

Opening Settings or the shade SHALL read the panel's actual current
brightness from sysfs and show it, so a brightness changed from the other
sheet, or by anything else writing to the backlight device, is reflected
rather than stale.

*Grounding: `ServiceRequest::RefreshSettings` already reads
`/sys/class/backlight/*/actual_brightness` via
`tools/device_settings.py`'s `Settings.brightness()`; the Shade route
previously issued only `ServiceRequest::RefreshNotifications` on open
(`ShellClient::refresh_route`), so it never picked this up until this
change added the second request there.*

#### Scenario: Opening the shade after a Settings change

- **WHEN** brightness was changed from Settings and the shade is opened
  next
- **THEN** the shade's slider shows that same value, not a stale one

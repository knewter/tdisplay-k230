## Layer

Userspace: the Rust shell client (`nix/rust-shell-client`) and the existing
`tools/device_settings.py` sysfs bridge. No kernel, device tree, or Nix
module change — the backlight device itself is unchanged from the archived
`2026-09-26-the-panel-brightness-is-adjustable` change.

## Decision 1: One shared, dependency-light slider module

`src/slider.rs` holds only pure math and drag state (value↔x mapping,
`MIN_PERCENT` clamping, the live-write throttle, and an armed `Drag`
struct) — no `cairo`, no `service_data` types. This mirrors
`theme_carousel.rs`'s own split: `render.rs` paints from the module's
numbers (`track_bounds`, `x_at_value`), `main.rs`/`service_ui.rs` own
touch dispatch and the actual `ServiceRequest` calls. Both the Settings
row and the Shade header call the same `paint_slider`/`slider::Drag`, so
the two can never visually or behaviorally drift apart, and the module is
unit-testable with no display server.

Rejected: two independent slider implementations (one per surface). This
is exactly the "stepper's two separate hit-tested glyphs vs. one track"
duplication the design review's finding #8 flags as unnecessary cost, and
would double the surface for the two to disagree.

## Decision 2: Band ownership, not release-only classification

The old stepper was hit-tested only at touch-up, inside `panel_intent`'s
release-only tap classification. A slider needs continuous value updates
during the drag itself, so the slider is instead **armed at touch-down**
whenever the touch lands in its band (`service_ui::slider_band`), exactly
like `Carousel::down` arms on its own carousel band. Once armed, it owns
the rest of that gesture unconditionally — horizontal or not — through
`main.rs`'s `down`/`motion`/`up` handlers, added as a new sibling branch
ahead of the existing route-specific branches (close drag, notification
swipe/scroll, wifi/theme picker dispatch) rather than edited into any of
them. `slider_band` also feeds `shade_panel_close_zone`'s existing
carve-out mechanism (the same one that already excludes the scrollable
notification list), so a touch that starts on the slider is never even a
close-drag *candidate* — the guarantee task 3's "must not start a close
drag" needs. `slider_band` is gated on `ControlState::Writable` so an
unavailable brightness control never steals a gesture from whatever plain
text sits in its place instead.

Rejected: teaching `panel_intent`'s release-only classifier a drag state
of its own. That function is shared by every other Settings/Shade tap
(Wi-Fi, keyboard, power, dismiss-all, the close drag) and already carries
a large text describing why its zones must not overlap; adding live-drag
tracking to it would either slow down its other, still-discrete callers
or fork its logic in place, both worse than one new orthogonal component.

## Decision 3: A direct sysfs write for the live path, not a persistent helper process

The stepper's existing `ServiceRequest::Brightness` shells out to
`k230-settings brightness <percent>` (`tools/device_settings.py`) once per
tap — fine for occasional discrete steps, wrong for ~20-30 writes/sec: a
process spawn per sample would pile up behind the service worker's single
blocking-subprocess queue. `docs/evidence/backlight/live-hs/README.md`
already established the shell user has group write via udev directly on
`/sys/class/backlight/canaan-dsi-backlight/brightness`, so the cheaper fix
is a new `ServiceRequest::BrightnessLive(u8)` that writes that file
directly from the existing service worker thread (a `fs::write`, no
subprocess) — mirroring `tools/device_settings.py`'s own backlight lookup
(exactly one device, a valid `max_brightness`) so the two paths compute
the same raw value. The live path never touches the Settings `Control`'s
read-back/UI-feedback machinery; the UI's own optimistic local value
(`ShellClient::apply_brightness_preview`) is what the finger actually
sees, and release always follows with the ordinary, verified `Brightness`
request.

Rejected: a separate long-lived helper process (a second daemon) purely
for brightness. The direct write is simpler, needs no new socket or
process lifecycle, and the existing worker thread already isolates it
from the Wayland/UI thread.

## Decision 4: Where the slider physically fits

The Shade's header (title, notification count, "Dismiss all") already
occupies its first ~160px; the slider's band (`SHADE_SLIDER_TOP = 190.0`,
56px tall) sits just below it, clear of the existing "Dismiss all" tap
zone (`116.0..190.0`). Everything below — the preview card,
`NOTIFICATION_TOP` and the whole notification list — shifts down by the
same 76px this makes room for; both are still defined as one shared
constant each (`render.rs`'s preview-card `y`, `service_ui::
NOTIFICATION_TOP`), so nothing downstream needed its own layout change.

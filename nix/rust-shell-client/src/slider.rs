//! Shared Material-3-style brightness slider: value<->x mapping, live-drag
//! write throttling, and the track geometry both the Settings row and the
//! Shade's own quick-settings header draw against (task: "brightness
//! should be a slider" -- `docs/design/shell-polish-review-2026-09.md`
//! also asked for a slider here and for larger touch targets on this
//! 330 ppi panel).
//!
//! Pure math and drag state only, mirroring `theme_carousel.rs`'s own
//! split: no cairo, no service types. `render.rs` paints from this
//! module's numbers; `main.rs`/`service_ui.rs` own touch dispatch and the
//! actual `ServiceRequest::Brightness`/`BrightnessLive` calls.

/// Never let the slider itself drive the backlight fully black -- still
/// visibly dim, but the panel (and the slider) stays legible enough to
/// find and drag back up. Applies only to values *set* through this
/// slider; a real sysfs read (something else changed the backlight) is
/// shown as-is, never forced up to this floor.
pub const MIN_PERCENT: u8 = 3;

/// Both callers (the Settings row and the Shade header) keep this margin
/// clear of the panel edge on each side, for the sun glyphs and plain
/// visual breathing room -- one inset either place, so `track_bounds` is
/// the single source both the painter and touch dispatch read.
pub const TRACK_MARGIN_PX: f64 = 64.0;

/// The touch target's own minimum height (task: "at least about 56 px
/// tall" -- Material Design's 48dp floor, sized up for this panel's
/// 330 ppi; `docs/design/shell-polish-review-2026-09.md` found existing
/// targets too small here).
pub const TOUCH_TARGET_PX: f64 = 56.0;

/// About 25 writes/sec (task: "throttle writes to about 20-30 per
/// second") -- cheap enough that a direct sysfs write per sample never
/// piles up ahead of the next touch sample, frequent enough that the
/// backlight visibly tracks the finger.
pub const LIVE_WRITE_INTERVAL_MS: u32 = 40;

/// The track's own left/right screen-space x for a panel `width` wide --
/// shared by the painter (thumb/track extents) and touch dispatch
/// (`value_at_x` below), so the two can never drift apart. A width too
/// narrow to leave any real track (never expected on this fixed-geometry
/// panel, see `main.rs`'s own "always 568x1232" note) still returns a
/// valid, non-degenerate pair rather than an empty or inverted range.
pub fn track_bounds(width: f64) -> (f64, f64) {
    let left = TRACK_MARGIN_PX;
    let right = (width - TRACK_MARGIN_PX).max(left + 1.0);
    (left, right)
}

/// Clamp a candidate percent into a slider's valid range, given its own
/// floor. Brightness's floor is `MIN_PERCENT` (never fully black); a
/// volume slider's floor is `0` (silence is a real, reachable value --
/// muting is a separate flag from the level, so 0% must not get pinned
/// up like the backlight is). Applied to every value a slider ever
/// *emits* from a touch position -- never to a value merely being
/// displayed (a real read is trusted and shown as-is, even if some other
/// process left it below `floor`).
pub fn clamp_percent_with_floor(percent: i64, floor: u8) -> u8 {
    percent.clamp(i64::from(floor), 100) as u8
}

/// Clamp a candidate percent into the brightness slider's own valid
/// range (floor `MIN_PERCENT`). Thin wrapper over
/// `clamp_percent_with_floor` kept for brightness call sites and this
/// module's own pre-existing tests.
pub fn clamp_percent(percent: i64) -> u8 {
    clamp_percent_with_floor(percent, MIN_PERCENT)
}

/// Map a touch x position to a percent value against an arbitrary floor.
/// The thumb travels the whole track; there is no extra dead zone beyond
/// the clamp itself, so the very first `floor`% of the track all reads
/// as `floor` (never lower) and the last pixel always reads 100.
pub fn value_at_x_with_floor(x: f64, left: f64, right: f64, floor: u8) -> u8 {
    if right <= left {
        return floor;
    }
    let t = ((x - left) / (right - left)).clamp(0.0, 1.0);
    clamp_percent_with_floor((t * 100.0).round() as i64, floor)
}

/// Map a touch x position to a percent value for the brightness slider's
/// own floor (`MIN_PERCENT`). Thin wrapper kept for brightness call sites
/// and this module's own pre-existing tests; see `value_at_x_with_floor`
/// for the general form the volume slider uses (floor `0`).
pub fn value_at_x(x: f64, left: f64, right: f64) -> u8 {
    value_at_x_with_floor(x, left, right, MIN_PERCENT)
}

/// Inverse of `value_at_x`, for drawing the thumb at its current value.
pub fn x_at_value(percent: u8, left: f64, right: f64) -> f64 {
    let t = f64::from(percent.min(100)) / 100.0;
    left + t * (right - left)
}

/// Whether a live write may fire again yet, given the last one actually
/// sent -- in the same `u32` touch-event millisecond domain every other
/// drag in this shell already uses (`theme_carousel`'s own
/// `time_ms.wrapping_sub`), never a fresh `Instant` clock the touch
/// thread would need to sample separately. `None` (nothing sent yet this
/// gesture) always fires immediately, so tap-to-jump reaches the
/// backlight on the very first frame instead of waiting out a full
/// interval.
fn live_write_due(last_sent_ms: Option<u32>, now_ms: u32) -> bool {
    match last_sent_ms {
        None => true,
        Some(last) => now_ms.wrapping_sub(last) >= LIVE_WRITE_INTERVAL_MS,
    }
}

/// One armed slider drag: which touch id owns it, and the track it was
/// armed against. The track is fixed for the gesture's whole lifetime
/// (computed once from the panel width at `start`), exactly like
/// `Carousel`'s own `start_position`/`reference` -- it never moves
/// mid-drag even if a later frame's reported width somehow differed.
pub struct Drag {
    id: i32,
    left: f64,
    right: f64,
    floor: u8,
    last_sent_ms: Option<u32>,
}

impl Drag {
    pub fn start(id: i32, width: f64) -> Self {
        Self::start_with_floor(id, width, MIN_PERCENT)
    }

    /// Same as `start`, but for a slider whose floor is not the
    /// brightness floor -- the volume slider's is `0` (silence is a real
    /// value; muting is tracked separately in `volume.rs`).
    pub fn start_with_floor(id: i32, width: f64, floor: u8) -> Self {
        let (left, right) = track_bounds(width);
        Self {
            id,
            left,
            right,
            floor,
            last_sent_ms: None,
        }
    }

    /// Whether `id` is the touch this drag was armed for -- the same
    /// id-mismatch convention `Carousel`/`PanelClose` already use, so a
    /// stray or second touch can never move a drag it did not start.
    pub fn matches(&self, id: i32) -> bool {
        self.id == id
    }

    pub fn value_at(&self, x: f64) -> u8 {
        value_at_x_with_floor(x, self.left, self.right, self.floor)
    }

    /// Marks a live write as sent right now if (and only if) the
    /// throttle allows one yet. Callers should send exactly when this
    /// returns `true`, and may still repaint (from `value_at`) when it
    /// returns `false` -- the visible thumb tracks every touch sample;
    /// only the backlight write itself is throttled.
    pub fn should_write(&mut self, now_ms: u32) -> bool {
        let due = live_write_due(self.last_sent_ms, now_ms);
        if due {
            self.last_sent_ms = Some(now_ms);
        }
        due
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn value_at_x_maps_the_full_track_and_inverts_x_at_value() {
        assert_eq!(value_at_x(0.0, 0.0, 200.0), MIN_PERCENT);
        assert_eq!(value_at_x(200.0, 0.0, 200.0), 100);
        assert_eq!(value_at_x(100.0, 0.0, 200.0), 50);
        for percent in [MIN_PERCENT, 25, 50, 75, 100] {
            let x = x_at_value(percent, 0.0, 200.0);
            assert_eq!(value_at_x(x, 0.0, 200.0), percent);
        }
    }

    #[test]
    fn value_at_x_clamps_beyond_the_track_and_never_divides_by_zero() {
        assert_eq!(value_at_x(-500.0, 0.0, 200.0), MIN_PERCENT);
        assert_eq!(value_at_x(9000.0, 0.0, 200.0), 100);
        // A zero/negative-width track (a not-yet-configured surface, or a
        // caller's stale bounds) must never divide by zero or return an
        // out-of-range percent -- it just reads as the floor.
        assert_eq!(value_at_x(50.0, 100.0, 100.0), MIN_PERCENT);
        assert_eq!(value_at_x(50.0, 100.0, 40.0), MIN_PERCENT);
    }

    #[test]
    fn clamp_percent_enforces_the_minimum_and_the_ceiling() {
        assert_eq!(clamp_percent(0), MIN_PERCENT);
        assert_eq!(clamp_percent(1), MIN_PERCENT);
        assert_eq!(clamp_percent(3), 3);
        assert_eq!(clamp_percent(100), 100);
        assert_eq!(clamp_percent(500), 100);
        assert_eq!(clamp_percent(-40), MIN_PERCENT);
    }

    #[test]
    fn live_write_throttle_gates_to_about_25_writes_per_second() {
        assert!(live_write_due(None, 0));
        assert!(!live_write_due(Some(0), 10));
        assert!(!live_write_due(Some(0), 39));
        assert!(live_write_due(Some(0), 40));
        assert!(live_write_due(Some(0), 1_000));
        // A wrapped wall-clock (same convention as `theme_carousel`'s own
        // `time_ms.wrapping_sub`) never panics; it is read as barely
        // elapsed rather than a huge forward jump, so at worst one
        // sample near the wrap is skipped, not a burst of stale writes.
        assert!(!live_write_due(Some(u32::MAX), 30));
    }

    #[test]
    fn drag_throttles_writes_but_the_caller_can_always_read_the_final_value_on_release() {
        let mut drag = Drag::start(7, 568.0);
        assert!(drag.matches(7));
        assert!(!drag.matches(8));
        // Tap-to-jump: the very first sample of a gesture always writes.
        assert!(drag.should_write(0));
        assert!(!drag.should_write(5));
        assert!(!drag.should_write(39));
        assert!(drag.should_write(40));
        assert!(!drag.should_write(41));
        // Release always reads the true value at the release point --
        // callers never gate this read on `should_write`, matching the
        // task's "always write the final value on release".
        assert_eq!(drag.value_at(0.0), MIN_PERCENT);
        let (_, right) = track_bounds(568.0);
        assert_eq!(drag.value_at(right), 100);
    }

    #[test]
    fn track_bounds_stays_ordered_even_for_an_unreasonably_narrow_width() {
        let (left, right) = track_bounds(10.0);
        assert!(right > left);
    }

    #[test]
    fn floor_zero_reaches_true_silence_unlike_the_brightness_floor() {
        // The volume slider's floor is 0, not `MIN_PERCENT` -- the very
        // first pixel of its track must read 0, not the brightness
        // floor's 3.
        assert_eq!(value_at_x_with_floor(0.0, 0.0, 200.0, 0), 0);
        assert_eq!(clamp_percent_with_floor(0, 0), 0);
        assert_eq!(clamp_percent_with_floor(-40, 0), 0);
        assert_eq!(value_at_x_with_floor(200.0, 0.0, 200.0, 0), 100);
        // A zero-width track still returns the floor, never divides by
        // zero, same guarantee as the brightness form.
        assert_eq!(value_at_x_with_floor(50.0, 100.0, 100.0, 0), 0);
    }

    #[test]
    fn value_at_x_with_floor_matches_the_brightness_wrapper_at_the_brightness_floor() {
        for x in [0.0, 33.0, 100.0, 200.0] {
            assert_eq!(
                value_at_x(x, 0.0, 200.0),
                value_at_x_with_floor(x, 0.0, 200.0, MIN_PERCENT)
            );
        }
    }

    #[test]
    fn drag_start_with_floor_lets_a_volume_style_drag_reach_zero() {
        let mut drag = Drag::start_with_floor(3, 568.0, 0);
        assert!(drag.matches(3));
        assert!(drag.should_write(0));
        assert_eq!(drag.value_at(0.0), 0);
        let (_, right) = track_bounds(568.0);
        assert_eq!(drag.value_at(right), 100);
    }
}

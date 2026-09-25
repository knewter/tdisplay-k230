//! Whole-page horizontal pager physics for the Home screen's icon grid.
//!
//! `theme_carousel.rs`'s Cover Flow model fits a single hero item a person
//! browses one at a time (skewed neighbor slices, blend-driven bitmap
//! selection). Home's pages are not single items -- each page is a whole
//! icon grid read at a glance -- so this is a full-bleed pager instead:
//! every page sits exactly one panel-width from its neighbor, with no skew
//! and no partial-neighbor peeking. It borrows the *physics* conventions
//! that module and `navigation.rs`'s `DrawerNavigation` already established
//! for this shell (1:1 drag, the same per-16ms momentum decay factor, an
//! ease-out-cubic settle whose duration scales with distance) rather than
//! inventing a third set of constants, so every flick in this shell still
//! decays and settles the same way.

/// Per-16ms momentum decay factor, matching `navigation.rs::DrawerNavigation`
/// and `theme_carousel.rs::Carousel` exactly.
const DECAY_PER_16MS: f64 = 0.88;
/// Below this pages/sec, a release settles immediately instead of coasting a
/// fraction of a page -- mirrors `theme_carousel::MIN_COAST_VELOCITY`,
/// re-derived in page-units instead of carousel-index-units.
const MIN_COAST_VELOCITY: f64 = 0.35;
/// A touch that never moved more than this many pixels is a tap or a
/// long-press candidate, not a page drag.
pub const TAP_SLOP: f64 = 8.0;
/// A touch held this long without exceeding `TAP_SLOP` is a long-press.
pub const LONG_PRESS_MS: u32 = 500;
const MAX_FLING_PX_PER_SEC: f64 = 3000.0;

/// Settle duration scales with distance, exactly like
/// `theme_carousel::settle_duration_ms` (re-derived in page-units).
fn settle_duration_ms(distance: f64) -> u32 {
    (distance.abs() * 220.0).clamp(140.0, 280.0) as u32
}

#[derive(Clone, Copy, Debug)]
struct Settle {
    from: f64,
    target: f64,
    elapsed_ms: u32,
    duration_ms: u32,
}

/// Drag/momentum/settle state for the Home page pager. `position` is in
/// whole-page units (page 0, page 1, ...); a mid-drag position is
/// fractional. `page_width` is the drag distance (in panel pixels) that
/// moves the position by exactly one page -- ordinarily the panel width
/// itself, so a full-width drag pages exactly once.
pub struct HomePager {
    position: f64,
    page_width: f64,
    velocity: f64, // pages/sec
    drag_start: Option<(f64, f64)>,
    drag_start_position: f64,
    drag_last_x: f64,
    drag_last_ms: u32,
    finger_velocity: f64, // px/sec
    dragged: bool,
    settle: Option<Settle>,
}

impl HomePager {
    pub fn new(page_width: f64) -> Self {
        Self {
            position: 0.0,
            page_width: page_width.max(1.0),
            velocity: 0.0,
            drag_start: None,
            drag_start_position: 0.0,
            drag_last_x: 0.0,
            drag_last_ms: 0,
            finger_velocity: 0.0,
            dragged: false,
            settle: None,
        }
    }

    pub fn position(&self) -> f64 {
        self.position
    }

    /// The committed/nearest page, clamped to a possibly-changed `count`.
    pub fn page(&self, count: usize) -> usize {
        if count == 0 {
            return 0;
        }
        self.position.round().clamp(0.0, (count - 1) as f64) as usize
    }

    /// Jump to `index` with no animation -- used when Home first opens or
    /// the pinned layout changes shape underneath an at-rest pager.
    pub fn set_page(&mut self, index: usize) {
        self.position = index as f64;
        self.velocity = 0.0;
        self.drag_start = None;
        self.settle = None;
    }

    /// Updates the drag-distance-per-page, e.g. after a panel resize. Does
    /// not otherwise disturb the current position or animation.
    pub fn set_page_width(&mut self, page_width: f64) {
        self.page_width = page_width.max(1.0);
    }

    /// True while a momentum coast or a post-release settle is running with
    /// no touch to generate further Wayland events -- the caller keeps
    /// polling frames at the fast tick rate while this holds, and can fall
    /// back to the slow idle poll otherwise. Deliberately not true just
    /// because a touch is down and not yet dragging: a live touch already
    /// wakes the event loop on its own via incoming motion/up events, so
    /// this would otherwise force a needless fast poll for as long as a
    /// finger merely rests without moving.
    pub fn is_animating(&self) -> bool {
        self.velocity != 0.0 || self.settle.is_some()
    }

    /// Starts tracking a touch that might become a page drag. `point` is
    /// the touch-down position; only its `.0` (x) is used for paging, but
    /// both are kept so a caller can also run its own long-press/tap
    /// disambiguation from the same down point.
    pub fn down(&mut self, point: (f64, f64), time_ms: u32) {
        self.velocity = 0.0; // touching a coasting/settling pager stops it
        self.settle = None;
        self.drag_start = Some(point);
        self.drag_start_position = self.position;
        self.drag_last_x = point.0;
        self.drag_last_ms = time_ms;
        self.finger_velocity = 0.0;
        self.dragged = false;
    }

    /// True once the live touch has moved past `TAP_SLOP` from its down
    /// point -- the point at which this becomes a real page drag rather
    /// than a tap or long-press candidate.
    pub fn dragging(&self) -> bool {
        self.dragged
    }

    /// Moves the pager 1:1 with the finger: a drag of `page_width` pixels
    /// moves the position by exactly one page. Returns whether a repaint is
    /// needed.
    pub fn motion(&mut self, point: (f64, f64), time_ms: u32, count: usize) -> bool {
        let Some(start) = self.drag_start else {
            return false;
        };
        if !point.0.is_finite() || !point.1.is_finite() {
            return false;
        }
        let elapsed = time_ms.wrapping_sub(self.drag_last_ms);
        if elapsed > 0 && elapsed < 1000 {
            self.finger_velocity = ((point.0 - self.drag_last_x) * 1000.0 / f64::from(elapsed))
                .clamp(-MAX_FLING_PX_PER_SEC, MAX_FLING_PX_PER_SEC);
        }
        if (point.0 - start.0).abs() > TAP_SLOP || (point.1 - start.1).abs() > TAP_SLOP {
            self.dragged = true;
        }
        self.drag_last_x = point.0;
        self.drag_last_ms = time_ms;
        if !self.dragged {
            return false;
        }
        let old = self.position;
        let max_page = count.saturating_sub(1) as f64;
        self.position =
            (self.drag_start_position - (point.0 - start.0) / self.page_width).clamp(0.0, max_page);
        (self.position - old).abs() >= 0.001
    }

    /// Ends the touch this pager was tracking. Returns whether the pager
    /// itself consumed it as a real drag (in which case the caller must not
    /// also treat the release as a tap/long-press): `false` when the touch
    /// never moved past `TAP_SLOP` (a tap or long-press candidate, for the
    /// caller to interpret), `true` when it was a genuine page drag now
    /// coasting or settling.
    pub fn up(&mut self, count: usize) -> bool {
        self.drag_start = None;
        if count == 0 || !self.dragged {
            self.dragged = false;
            return false;
        }
        self.dragged = false;
        let velocity = -self.finger_velocity / self.page_width;
        if velocity.abs() < MIN_COAST_VELOCITY {
            self.start_settle(self.position.round());
        } else {
            self.velocity = velocity;
        }
        true
    }

    /// Cancels any in-progress drag without starting a settle -- used when
    /// a second contact lands or the touch is otherwise invalidated.
    pub fn cancel(&mut self) {
        self.drag_start = None;
        self.dragged = false;
        self.velocity = 0.0;
    }

    fn start_settle(&mut self, target: f64) {
        let duration_ms = settle_duration_ms(target - self.position);
        self.settle = Some(Settle {
            from: self.position,
            target,
            elapsed_ms: 0,
            duration_ms,
        });
        self.velocity = 0.0;
    }

    /// Advances momentum decay or a settle-to-nearest-page animation.
    /// Returns whether a repaint is needed. `elapsed_ms` is an accumulator
    /// since the caller's last tick, matching every other animated surface
    /// in this shell (`theme_carousel::Carousel::tick`,
    /// `service_ui::NotificationSwipeSettle::tick`).
    pub fn tick(&mut self, elapsed_ms: u32, count: usize) -> bool {
        if self.drag_start.is_some() || count == 0 {
            return false;
        }
        if let Some(settle) = self.settle.as_mut() {
            settle.elapsed_ms = settle.elapsed_ms.saturating_add(elapsed_ms.min(48));
            let t = (f64::from(settle.elapsed_ms) / f64::from(settle.duration_ms)).min(1.0);
            let eased = 1.0 - (1.0 - t).powi(3);
            self.position = settle.from + (settle.target - settle.from) * eased;
            if t >= 1.0 {
                self.position = settle.target;
                self.settle = None;
            }
            return true;
        }
        if self.velocity == 0.0 || elapsed_ms == 0 {
            return false;
        }
        let elapsed = elapsed_ms.min(50);
        let max_page = count.saturating_sub(1) as f64;
        let old = self.position;
        let next = self.position + self.velocity * f64::from(elapsed) / 1000.0;
        self.velocity *= DECAY_PER_16MS.powf(f64::from(elapsed) / 16.0);
        if next <= 0.0 || next >= max_page {
            self.position = next.clamp(0.0, max_page);
            self.start_settle(self.position.round());
            return true;
        }
        self.position = next;
        if self.velocity.abs() < MIN_COAST_VELOCITY {
            self.start_settle(self.position.round());
        }
        (self.position - old).abs() >= 0.001 || self.settle.is_some()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const PAGE_WIDTH: f64 = 568.0;

    #[test]
    fn drag_moves_one_to_one_with_the_finger() {
        let mut pager = HomePager::new(PAGE_WIDTH);
        pager.set_page(1);
        pager.down((300.0, 600.0), 0);
        pager.motion((300.0 - PAGE_WIDTH, 600.0), 16, 3);
        assert!((pager.position() - 2.0).abs() < 1e-6);
        pager.motion((300.0 + PAGE_WIDTH * 2.0, 600.0), 32, 3);
        assert_eq!(pager.position(), 0.0, "clamped at the first page");
    }

    #[test]
    fn small_wobble_is_not_a_drag() {
        let mut pager = HomePager::new(PAGE_WIDTH);
        pager.down((300.0, 600.0), 0);
        pager.motion((304.0, 601.0), 10, 3);
        assert!(!pager.dragging());
        assert!(!pager.up(3), "a wobble releases as a tap candidate");
        assert!(!pager.is_animating());
    }

    #[test]
    fn slow_release_settles_immediately_to_nearest() {
        let mut pager = HomePager::new(PAGE_WIDTH);
        pager.set_page(1);
        pager.down((300.0, 600.0), 0);
        pager.motion((300.0 - PAGE_WIDTH * 0.6, 600.0), 16, 4);
        pager.motion((300.0 - PAGE_WIDTH * 0.6 - 1.0, 600.0), 416, 4);
        assert!(pager.up(4), "a real drag release is consumed by the pager");
        assert!(pager.is_animating());
        let mut ticks = 0;
        while pager.is_animating() && ticks < 50 {
            pager.tick(16, 4);
            ticks += 1;
        }
        assert!((pager.position() - 2.0).abs() < 1e-6);
        assert!(!pager.is_animating());
    }

    #[test]
    fn fast_flick_coasts_then_settles_and_decays_over_time() {
        let mut pager = HomePager::new(PAGE_WIDTH);
        pager.set_page(0);
        pager.down((300.0, 600.0), 0);
        pager.motion((300.0 - PAGE_WIDTH * 3.0, 600.0), 20, 5);
        assert!(pager.up(5));
        assert!(pager.is_animating());
        let after_drag = pager.position();
        let mut ticks = 0;
        while pager.is_animating() && ticks < 200 {
            pager.tick(16, 5);
            ticks += 1;
        }
        assert!(!pager.is_animating(), "must eventually settle, not coast forever");
        assert!(pager.position() > after_drag);
        assert_eq!(pager.position().fract(), 0.0);
    }

    #[test]
    fn held_finger_stops_a_coasting_pager_without_a_stray_flick() {
        let mut pager = HomePager::new(PAGE_WIDTH);
        pager.set_page(0);
        pager.down((300.0, 600.0), 0);
        pager.motion((300.0 - PAGE_WIDTH, 600.0), 16, 3);
        pager.up(3);
        assert!(pager.is_animating());
        pager.down((120.0, 600.0), 50);
        assert!(!pager.is_animating(), "a new touch cancels any coast/settle");
    }

    #[test]
    fn cancel_stops_any_animation() {
        let mut pager = HomePager::new(PAGE_WIDTH);
        pager.set_page(0);
        pager.down((300.0, 600.0), 0);
        pager.motion((300.0 - PAGE_WIDTH * 3.0, 600.0), 20, 5);
        pager.up(5);
        assert!(pager.is_animating());
        pager.cancel();
        assert!(!pager.is_animating());
    }
}

//! Physics and layout for a Cover Flow carousel, adapted from Omarchy
//! Quattro's `ImagePicker.qml` (omacom/omarchy @28ceaae7, pinned by
//! `nix/handheld-theme-default/default.nix`) to this handheld's narrower
//! 568x1232 portrait panel and to touch drag/momentum, which upstream's
//! keyboard/mouse-only picker never has.
//!
//! ## What is scaled, what is new
//!
//! Upstream's own geometry (`expandedWidth: 768`, `expandedHeight: 475`,
//! `sliceWidth: 108`, `sliceHeight: 432`, `sliceSpacing: -30`,
//! `skewOffset: 28`) is sized for a desktop monitor. Every constant below is
//! that same geometry scaled by one factor to fit a 568px-wide panel, with
//! every ratio preserved: `EXPANDED_W`/`EXPANDED_H` for the centered item,
//! `SLICE_W`/`SLICE_H` for a side slice, `SKEW` for the parallelogram lean,
//! `ITEM_STEP` for the pitch between slices. `SKEW` is a constant offset
//! applied to every slice's own width, matching upstream: a small fraction
//! of a narrow side slice, a subtler lean on the wide centered one.
//!
//! Upstream has no `Behavior`/`Animation` at all (confirmed by reading the
//! whole file): selection jumps instantly, driven only by arrow keys, Tab,
//! or a slice tap. This module adds real drag-with-momentum on top of that,
//! because our panel is touch-first and a hard snap under a dragging finger
//! would feel broken. The interaction contract upstream does define is kept
//! exactly: browse (drag, or tap a side slice to bring it to the centre),
//! then confirm (tap the already-centered slice, or an explicit Apply).
//!
//! ## The approximation this module makes, and why
//!
//! Upstream's layout function is only ever evaluated at an integer
//! `selectedIndex` -- there is no continuous position, so its own two
//! branches (`relativeIndex < 0` vs `relativeIndex >= 1`) are never asked to
//! agree at a shared boundary. Making the same layout draggable needs a
//! continuous position, and the cheapest correct way to get one -- without
//! inventing a new closed-form layout that Quattro's screenshots would not
//! validate -- is to compute upstream's own exact discrete layout at the two
//! integer positions bracketing the current (possibly fractional) position,
//! then linearly interpolate every slice's `(x, width, height, y)` between
//! those two exact layouts. At rest (integer position) this reproduces
//! upstream's layout exactly, which is what the screenshot comparison in
//! `docs/evidence/omarchy-themes/quattro-carousel/` checks. Mid-drag it is a
//! plausible, cheap approximation (two small closed-form evaluations plus a
//! `lerp`, no iteration, no trigonometry) rather than a physically exact
//! continuous coverflow.
//!
//! Imagery is a second, deliberate approximation: rather than decode a new
//! crop every frame as a slice's blended size changes (the "needlessly
//! expensive per-frame transform" this change is told to avoid on a
//! software-rendered, in-order RISC-V core), `theme_thumbnails.rs` decodes
//! and caches exactly two bitmaps per catalog id -- one already cropped to
//! the expanded aspect, one to the slice aspect -- and this module's caller
//! picks whichever is closer to the current blend and scales it onto the
//! slice with a Cairo matrix (`cr.scale`), never a fresh decode. That is the
//! "pre-rendered skewed slices... or a shear via a Cairo matrix on cached
//! surfaces" approximation the task explicitly allows. The tradeoff: for a
//! few animated frames near the halfway point of a drag, the source crop is
//! very slightly the "wrong" aspect for the slice's current blended size;
//! nothing is ever decoded off the Wayland thread's hot path, and both
//! endpoints (fully expanded, fully slice) are pixel-exact.

/// Upstream's `expandedWidth: 768` / `expandedHeight: 475`, scaled by
/// `EXPANDED_W / 768.0` so this panel's centered slice is prominent without
/// crowding the 568px-wide screen.
pub const EXPANDED_W: f64 = 300.0;
pub const EXPANDED_H: f64 = 186.0; // 475 * (300/768) = 185.55, rounded for crisp raster.
/// Upstream's `sliceWidth: 108` / `sliceHeight: 432`, same scale factor.
pub const SLICE_W: f64 = 42.0;
pub const SLICE_H: f64 = 169.0; // 432 * (300/768) = 168.75, rounded.
/// Upstream's `skewOffset: 28`, same scale factor. Applied as a constant
/// pixel offset regardless of a slice's own width, exactly like upstream.
pub const SKEW: f64 = 11.0;
/// Upstream's `sliceSpacing: -30`, same scale factor. Negative: consecutive
/// slices overlap (a "shingled" look), resolved by z-order at paint time.
pub const SPACING: f64 = -12.0;
/// Pitch between adjacent slice centers/left-edges.
pub const ITEM_STEP: f64 = SLICE_W + SPACING;
/// How many slices either side of the centered position are laid out and
/// hit-tested at all. Upstream's own `nearby` cutoff is 16, sized for a
/// desktop monitor; ours is smaller because this screen is much narrower
/// (fewer slices are ever visible) and every visible id must fit in the
/// bounded thumbnail cache.
pub const NEARBY_LIMIT: i64 = 8;

const MAX_FLING_PX_PER_SEC: f64 = 3000.0;
/// Below this index-units/sec, a release settles immediately instead of
/// coasting -- a slow drag release should not "coast" a fraction of a slot.
const MIN_COAST_VELOCITY: f64 = 0.35;
/// Per-16ms decay factor, matching `navigation.rs`'s `DrawerNavigation` and
/// `service_ui.rs`'s `NotificationCoast` so every flick in this shell decays
/// at a visually consistent rate.
const DECAY_PER_16MS: f64 = 0.88;
/// A touch that never moved more than this many pixels is a tap, not a drag.
const TAP_SLOP: f64 = 8.0;
/// Settle duration scales with distance, like `service_ui.rs`'s
/// `NotificationSwipeSettle` (`(distance * 0.4).clamp(120.0, 240.0)` there,
/// in pixels; here in index-units, so the per-unit factor and clamp differ,
/// but the shape of the rule -- and the elapsed-accumulator `tick`, rather
/// than an absolute clock, so this never has to agree with Wayland's touch
/// timestamp domain -- is the same one every settle in this shell uses).
fn settle_duration_ms(distance: f64) -> u32 {
    (distance.abs() * 90.0).clamp(140.0, 260.0) as u32
}

/// One slice's on-screen placement, in absolute panel pixels, ready to
/// paint. `blend` is 0.0 at the centered/expanded slice and 1.0 at (or
/// beyond) a full slice-sized neighbor; the renderer uses it to pick which
/// cached bitmap variant is closer, per the module doc above.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SlicePlacement {
    pub index: usize,
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
    pub blend: f64,
    /// Paint order key, ascending: paint low-to-high so the item nearest the
    /// centered position (highest z, like upstream's `z: selected ? 100 :
    /// 50 - abs(relativeIndex)`) ends up drawn on top of its overlapping
    /// neighbors.
    pub z: i64,
}

fn blend_of(relative: f64) -> f64 {
    relative.abs().min(1.0)
}

/// Upstream's exact discrete layout (`ImagePicker.qml` lines 457-460),
/// evaluated at an arbitrary integer `selected` so it can be sampled at the
/// two integers bracketing a continuous position and interpolated.
fn exact_layout(selected: i64, i: i64, center_x: f64) -> (f64, f64, f64, f64) {
    let relative = i - selected;
    let preview_x = center_x - EXPANDED_W / 2.0;
    if relative == 0 {
        return (preview_x, EXPANDED_W, EXPANDED_H, 0.0);
    }
    let x = if relative < 0 {
        preview_x + relative as f64 * ITEM_STEP
    } else {
        preview_x + EXPANDED_W + SPACING + (relative - 1) as f64 * ITEM_STEP
    };
    let y = (EXPANDED_H - SLICE_H) / 2.0;
    (x, SLICE_W, SLICE_H, y)
}

/// The continuous approximation described in the module doc: lerp between
/// upstream's own exact layout at the two integers bracketing `position`.
fn interpolated_layout(position: f64, i: i64, center_x: f64) -> (f64, f64, f64, f64) {
    let lo = position.floor();
    let hi = position.ceil();
    let a = exact_layout(lo as i64, i, center_x);
    if (hi - lo).abs() < f64::EPSILON {
        return a;
    }
    let b = exact_layout(hi as i64, i, center_x);
    let t = position - lo;
    (
        a.0 + (b.0 - a.0) * t,
        a.1 + (b.1 - a.1) * t,
        a.2 + (b.2 - a.2) * t,
        a.3 + (b.3 - a.3) * t,
    )
}

/// Every slice within `NEARBY_LIMIT` of `position`, in back-to-front paint
/// order (ascending `z`, so the caller can just paint the returned `Vec` in
/// order and the centered slice naturally ends up on top).
pub fn visible_slices(position: f64, count: usize, center_x: f64, top_y: f64) -> Vec<SlicePlacement> {
    if count == 0 {
        return Vec::new();
    }
    let center = position.round() as i64;
    let lo = (center - NEARBY_LIMIT).max(0);
    let hi = (center + NEARBY_LIMIT).min(count as i64 - 1);
    let mut slices: Vec<SlicePlacement> = (lo..=hi)
        .map(|i| {
            let relative = i as f64 - position;
            let (x, width, height, y) = interpolated_layout(position, i, center_x);
            let z = if relative.round() == 0.0 {
                100
            } else {
                50 - relative.abs().min(40.0) as i64
            };
            SlicePlacement {
                index: i as usize,
                x,
                y: top_y + y,
                width,
                height,
                blend: blend_of(relative),
                z,
            }
        })
        .collect();
    slices.sort_by_key(|slice| slice.z);
    slices
}

/// Is `(px, py)` -- already relative to the slice's own top-left `(x, y)`
/// origin, i.e. `px = point.0 - slice.x`, `py = point.1 - slice.y` -- inside
/// the skewed parallelogram, not just its bounding rectangle? Upstream's
/// mask (`ImagePicker.qml` lines 463-489) shears the left edge from
/// `(SKEW, 0)` to `(0, height)` and the right edge from `(width, 0)` to
/// `(width - SKEW, height)`; at a given fractional height `t`, the valid
/// horizontal span narrows linearly from the top edge's full-`SKEW` inset.
fn in_slice(px: f64, py: f64, width: f64, height: f64) -> bool {
    if height <= 0.0 || py < 0.0 || py > height {
        return false;
    }
    let t = (py / height).clamp(0.0, 1.0);
    let left = SKEW * (1.0 - t);
    let right = width - SKEW * t;
    px >= left && px <= right
}

/// Which slice, if any, a tap at `point` lands on, honoring the skewed
/// shape and upstream's z-order (the slice nearest the centered position is
/// drawn on top of its shingled neighbors, so it is tested first).
pub fn hit_test(point: (f64, f64), position: f64, count: usize, center_x: f64, top_y: f64) -> Option<usize> {
    let mut slices = visible_slices(position, count, center_x, top_y);
    slices.sort_by(|a, b| b.z.cmp(&a.z));
    slices.into_iter().find_map(|slice| {
        let px = point.0 - slice.x;
        let py = point.1 - slice.y;
        in_slice(px, py, slice.width, slice.height).then_some(slice.index)
    })
}

#[derive(Clone, Copy, Debug)]
struct Contact {
    id: i32,
    start_x: f64,
    start_position: f64,
    last_x: f64,
    last_ms: u32,
    finger_velocity: f64, // px/sec, sign matching finger motion (not carousel position)
    dragged: bool,
    cancelled: bool,
}

#[derive(Clone, Copy, Debug)]
struct Settle {
    from: f64,
    target: f64,
    elapsed_ms: u32,
    duration_ms: u32,
}

/// What a completed touch on the carousel means. Mirrors upstream's
/// `onClicked: item.selected ? root.applySelected() : root.select(index)`,
/// plus the drag/momentum this touch panel adds on top.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CarouselOutcome {
    /// A side slice was tapped: browse only, no side effect. The carousel
    /// starts settling there on its own; the caller does nothing further.
    Recenter(usize),
    /// The already-centered slice was tapped: upstream's confirm gesture.
    /// The caller decides what "confirm" means (stage a preview, apply).
    Confirm(usize),
    /// The touch belonged to the carousel (a drag that ended, now coasting
    /// or settling; or a tap inside the band that missed every slice) but
    /// is not itself a tap outcome. The caller must not treat the release
    /// point as any other kind of tap (header/footer chrome, etc.).
    Consumed,
}

/// Drag/momentum/settle state for one carousel (the theme list, or a
/// theme's background list -- both get one of these; see `main.rs`).
#[derive(Default)]
pub struct Carousel {
    position: f64,
    velocity: f64, // index-units/sec
    contact: Option<Contact>,
    settle: Option<Settle>,
}

impl Carousel {
    /// Jump to `index` with no animation -- used when a page opens fresh.
    pub fn set_index(&mut self, index: usize) {
        self.position = index as f64;
        self.velocity = 0.0;
        self.contact = None;
        self.settle = None;
    }

    pub fn position(&self) -> f64 {
        self.position
    }

    /// The committed/nearest index, clamped to a possibly-changed `count`.
    pub fn index(&self, count: usize) -> usize {
        if count == 0 {
            return 0;
        }
        self.position.round().clamp(0.0, (count - 1) as f64) as usize
    }

    /// True while a drag, a momentum coast, or a post-release settle
    /// animation is in progress -- the caller keeps polling frames.
    pub fn is_animating(&self) -> bool {
        self.contact.is_some() || self.velocity != 0.0 || self.settle.is_some()
    }

    pub fn down(&mut self, id: i32, point: (f64, f64), time_ms: u32) {
        self.velocity = 0.0; // touching a coasting/settling carousel stops it
        self.settle = None;
        self.contact = Some(Contact {
            id,
            start_x: point.0,
            start_position: self.position,
            last_x: point.0,
            last_ms: time_ms,
            finger_velocity: 0.0,
            dragged: false,
            cancelled: false,
        });
    }

    /// Moves the carousel 1:1 with the finger: a drag of `ITEM_STEP` pixels
    /// moves the position by exactly one slice. Returns whether a repaint
    /// is needed.
    pub fn motion(&mut self, id: i32, point: (f64, f64), time_ms: u32, count: usize) -> bool {
        let Some(contact) = self.contact.as_mut() else {
            return false;
        };
        if contact.id != id || contact.cancelled || !point.0.is_finite() {
            return false;
        }
        let elapsed = time_ms.wrapping_sub(contact.last_ms);
        if elapsed > 0 && elapsed < 1000 {
            contact.finger_velocity = ((point.0 - contact.last_x) * 1000.0 / f64::from(elapsed))
                .clamp(-MAX_FLING_PX_PER_SEC, MAX_FLING_PX_PER_SEC);
        }
        if (point.0 - contact.start_x).abs() > TAP_SLOP {
            contact.dragged = true;
        }
        contact.last_x = point.0;
        contact.last_ms = time_ms;
        let old = self.position;
        let max_index = count.saturating_sub(1) as f64;
        self.position = (contact.start_position - (point.0 - contact.start_x) / ITEM_STEP)
            .clamp(0.0, max_index);
        (self.position - old).abs() >= 0.001
    }

    /// Ends a touch. Returns `None` only when this `id` never had an armed
    /// contact here (the down point was outside the carousel band, or a
    /// stray id): the caller should fall through to other hit-testing, same
    /// as `DrawerNavigation::up`'s id-mismatch convention. Any other
    /// outcome means the touch belonged to the carousel; see
    /// `CarouselOutcome`.
    pub fn up(
        &mut self,
        id: i32,
        point: (f64, f64),
        time_ms: u32,
        count: usize,
        center_x: f64,
        top_y: f64,
    ) -> Option<CarouselOutcome> {
        let contact = self.contact.take()?;
        if contact.id != id || contact.cancelled || !point.0.is_finite() || count == 0 {
            self.velocity = 0.0;
            return None;
        }
        if !contact.dragged {
            let Some(tapped) = hit_test(point, self.position, count, center_x, top_y) else {
                return Some(CarouselOutcome::Consumed);
            };
            let centered = self.index(count);
            return Some(if tapped == centered {
                self.set_index(centered); // clears any sub-pixel drift from the tap's own tiny motion
                CarouselOutcome::Confirm(tapped)
            } else {
                self.start_settle(tapped as f64);
                CarouselOutcome::Recenter(tapped)
            });
        }
        let _ = time_ms; // recency is implicit: finger_velocity already decays to 0 if motion() stalls
        let velocity = -contact.finger_velocity / ITEM_STEP;
        if velocity.abs() < MIN_COAST_VELOCITY {
            self.start_settle(self.position.round());
        } else {
            self.velocity = velocity;
        }
        Some(CarouselOutcome::Consumed)
    }

    pub fn cancel(&mut self) {
        self.contact = None;
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

    /// Advances momentum decay or a settle-to-nearest animation. Returns
    /// whether a repaint is needed. `elapsed_ms` is however long it has been
    /// since the caller's last `tick`/frame -- an accumulator, like
    /// `service_ui::NotificationSwipeSettle::tick`, never an absolute
    /// clock, so this never has to agree with any other subsystem's time
    /// domain (the Wayland touch timestamps `down`/`motion`/`up` receive
    /// included).
    pub fn tick(&mut self, elapsed_ms: u32, count: usize) -> bool {
        if self.contact.is_some() || count == 0 {
            return false;
        }
        if let Some(settle) = self.settle.as_mut() {
            settle.elapsed_ms = settle.elapsed_ms.saturating_add(elapsed_ms.min(48));
            let t = (f64::from(settle.elapsed_ms) / f64::from(settle.duration_ms)).min(1.0);
            let eased = 1.0 - (1.0 - t).powi(3); // ease-out cubic, matching NotificationSwipeSettle
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
        let max_index = count.saturating_sub(1) as f64;
        let old = self.position;
        let next = self.position + self.velocity * f64::from(elapsed) / 1000.0;
        self.velocity *= DECAY_PER_16MS.powf(f64::from(elapsed) / 16.0);
        if next <= 0.0 || next >= max_index {
            self.position = next.clamp(0.0, max_index);
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

    #[test]
    fn index_from_offset_rounds_to_nearest_and_clamps() {
        let mut carousel = Carousel::default();
        carousel.set_index(3);
        assert_eq!(carousel.index(10), 3);
        carousel.position = 3.49;
        assert_eq!(carousel.index(10), 3);
        carousel.position = 3.51;
        assert_eq!(carousel.index(10), 4);
        carousel.position = -1.0;
        assert_eq!(carousel.index(10), 0);
        carousel.position = 99.0;
        assert_eq!(carousel.index(10), 9);
    }

    #[test]
    fn drag_moves_one_to_one_with_the_finger() {
        let mut carousel = Carousel::default();
        carousel.set_index(5);
        carousel.down(1, (300.0, 600.0), 0);
        // Dragging left by one full ITEM_STEP must advance exactly one slot:
        // "moves the carousel 1:1 with the finger."
        carousel.motion(1, (300.0 - ITEM_STEP, 600.0), 16, 22);
        assert!((carousel.position() - 6.0).abs() < 1e-6);
        carousel.motion(1, (300.0 + ITEM_STEP * 2.0, 600.0), 32, 22);
        assert!((carousel.position() - 3.0).abs() < 1e-6);
    }

    #[test]
    fn drag_clamps_at_both_ends() {
        let mut carousel = Carousel::default();
        carousel.set_index(0);
        carousel.down(1, (300.0, 600.0), 0);
        carousel.motion(1, (300.0 + ITEM_STEP * 50.0, 600.0), 16, 5);
        assert_eq!(carousel.position(), 0.0);
        carousel.set_index(4);
        carousel.down(1, (300.0, 600.0), 0);
        carousel.motion(1, (300.0 - ITEM_STEP * 50.0, 600.0), 16, 5);
        assert_eq!(carousel.position(), 4.0);
    }

    #[test]
    fn slow_release_settles_immediately_to_nearest() {
        let mut carousel = Carousel::default();
        carousel.set_index(2);
        carousel.down(1, (300.0, 600.0), 0);
        // A quick initial move establishes real drag distance (past
        // TAP_SLOP), then the finger holds nearly still for a long moment
        // before lifting -- release velocity is measured from the last
        // motion segment only, matching a real touch driver, so this is a
        // "slow release" even though the whole gesture moved a full slot.
        carousel.motion(1, (300.0 - ITEM_STEP * 0.6, 600.0), 16, 22);
        carousel.motion(1, (300.0 - ITEM_STEP * 0.6 - 1.0, 600.0), 416, 22);
        let tap = carousel.up(1, (300.0 - ITEM_STEP * 0.6 - 1.0, 600.0), 420, 22, 284.0, 200.0);
        assert_eq!(tap, Some(CarouselOutcome::Consumed), "a drag release never itself confirms");
        assert!(carousel.is_animating(), "settle animation must be running");
        // Settle target is the nearest slot to where the finger let go,
        // ~2.9, which rounds to 3, reached once the settle duration elapses.
        let mut ticks = 0;
        while carousel.is_animating() && ticks < 50 {
            carousel.tick(16, 22);
            ticks += 1;
        }
        assert!((carousel.position() - 3.0).abs() < 1e-6);
        assert!(!carousel.is_animating());
    }

    #[test]
    fn fast_flick_coasts_then_settles_and_decays_over_time() {
        let mut carousel = Carousel::default();
        carousel.set_index(10);
        carousel.down(1, (300.0, 600.0), 0);
        // A fast leftward drag (finger velocity clamps to MAX_FLING) should
        // start a momentum coast, not an immediate settle.
        carousel.motion(1, (300.0 - ITEM_STEP * 3.0, 600.0), 20, 22);
        let tap = carousel.up(1, (300.0 - ITEM_STEP * 3.0, 600.0), 21, 22, 284.0, 200.0);
        assert_eq!(tap, Some(CarouselOutcome::Consumed));
        assert!(carousel.is_animating());
        let after_drag = carousel.position();
        let mut ticks = 0;
        while carousel.is_animating() && ticks < 200 {
            carousel.tick(16, 22);
            ticks += 1;
        }
        assert!(!carousel.is_animating(), "must eventually settle, not coast forever");
        assert!(
            carousel.position() > after_drag,
            "a leftward flick must keep advancing the index while it coasts"
        );
        // The committed index must be a whole slot once everything stops.
        assert_eq!(carousel.position().fract(), 0.0);
    }

    #[test]
    fn tap_on_centered_slice_confirms_tap_on_side_slice_only_recenters() {
        let mut carousel = Carousel::default();
        carousel.set_index(4);
        let center_x = 284.0;
        let top_y = 200.0;
        let centered = visible_slices(4.0, 22, center_x, top_y)
            .into_iter()
            .find(|slice| slice.index == 4)
            .unwrap();
        carousel.down(1, (center_x, top_y + centered.height / 2.0), 0);
        let tap = carousel.up(
            1,
            (center_x, top_y + centered.height / 2.0),
            10,
            22,
            center_x,
            top_y,
        );
        assert_eq!(tap, Some(CarouselOutcome::Confirm(4)));

        let neighbor = visible_slices(4.0, 22, center_x, top_y)
            .into_iter()
            .find(|slice| slice.index == 5)
            .unwrap();
        let side_point = (neighbor.x + neighbor.width / 2.0, neighbor.y + neighbor.height / 2.0);
        carousel.down(2, side_point, 100);
        let tap = carousel.up(2, side_point, 110, 22, center_x, top_y);
        assert_eq!(tap, Some(CarouselOutcome::Recenter(5)));
        assert!(carousel.is_animating(), "recenter starts a settle to the tapped slice");
        let mut ticks = 0;
        while carousel.is_animating() && ticks < 50 {
            carousel.tick(16, 22);
            ticks += 1;
        }
        assert!((carousel.position() - 5.0).abs() < 1e-6);
    }

    #[test]
    fn skewed_hit_test_excludes_the_sheared_corner() {
        // A point in the rectangle's top-left corner, but outside the
        // sheared-in left edge at y=0 (valid x there is [SKEW, width]).
        assert!(!in_slice(SKEW / 2.0, 0.0, SLICE_W, SLICE_H));
        // The same x is inside the shape once y has moved far enough down
        // that the shear has widened the left bound past it.
        assert!(in_slice(SKEW / 2.0, SLICE_H, SLICE_W, SLICE_H));
        // Dead center is always inside regardless of skew.
        assert!(in_slice(SLICE_W / 2.0, SLICE_H / 2.0, SLICE_W, SLICE_H));
        // Symmetric check on the right edge: it is untouched at the top
        // (valid x there is [SKEW, width]) but sheared in at the bottom
        // (valid x there is [0, width - SKEW]).
        assert!(in_slice(SLICE_W - SKEW / 2.0, 0.0, SLICE_W, SLICE_H));
        assert!(!in_slice(SLICE_W - SKEW / 2.0, SLICE_H, SLICE_W, SLICE_H));
    }

    #[test]
    fn hit_test_prefers_the_slice_nearest_center_in_overlap() {
        // Negative SPACING makes consecutive slices overlap; the centered
        // slice's z-order (100) beats every neighbor, so a point inside both
        // the expanded slice and a neighbor's bounding box must resolve to
        // the centered index.
        let center_x = 284.0;
        let top_y = 200.0;
        let centered = visible_slices(4.0, 22, center_x, top_y)
            .into_iter()
            .find(|slice| slice.index == 4)
            .unwrap();
        // 20px in from the centered slice's own left edge, at half its
        // height: inside the centered slice's sheared shape (the shear
        // only excludes the first ~SKEW px near an edge), and still inside
        // the shingled left neighbor's bounding box (ITEM_STEP < SLICE_W).
        let point = (centered.x + 20.0, centered.y + centered.height / 2.0);
        assert_eq!(hit_test(point, 4.0, 22, center_x, top_y), Some(4));
    }

    #[test]
    fn set_index_stops_any_animation_in_progress() {
        let mut carousel = Carousel::default();
        carousel.set_index(0);
        carousel.velocity = 5.0;
        carousel.settle = Some(Settle {
            from: 0.0,
            target: 3.0,
            elapsed_ms: 0,
            duration_ms: 200,
        });
        carousel.set_index(7);
        assert!(!carousel.is_animating());
        assert_eq!(carousel.index(22), 7);
    }
}

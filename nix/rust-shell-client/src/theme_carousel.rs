//! Physics and layout for a Cover Flow carousel, adapted from Omarchy
//! Quattro's `ImagePicker.qml` (omacom/omarchy @28ceaae7, pinned by
//! `nix/handheld-theme-default/default.nix`) to this handheld's narrow
//! 568x1232 portrait panel and to touch drag/momentum, which upstream's
//! keyboard/mouse-only picker never has.
//!
//! ## Two geometries, one shape
//!
//! The first pass of this module scaled every one of upstream's constants
//! (`expandedWidth: 768`, `expandedHeight: 475`, `sliceWidth: 108`,
//! `sliceHeight: 432`, `sliceSpacing: -30`, `skewOffset: 28`) down by one
//! flat factor. That reproduced upstream's landscape-monitor proportions
//! exactly, but on a screen this tall and narrow it left the Themes page's
//! carousel only ~186px tall at the very top of a 1232px page -- correct
//! geometry, wrong emphasis: the carousel is this page's only real content,
//! and it read as a small ornament above a mostly empty card.
//!
//! [`CarouselGeometry`] now bundles every size constant so each carousel
//! context can pick its own: [`THEME_GEOMETRY`] is the Themes page's hero --
//! a large, portrait-cropped centered slice that dominates the page, as
//! Quattro's own carousel dominates its (much larger) desktop page. Its
//! *width*-derived measures (`slice_w`, `skew`, `spacing`, hence
//! `item_step`) still keep upstream's exact ratio to `expanded_w`
//! (`108/768`, `28/768`, `-30/768`); only `expanded_h` breaks from the flat
//! scale -- see "Portrait crop" below for why. [`BACKGROUND_GEOMETRY`] is
//! the Preview page's background carousel: that page already carries a
//! palette swatch row and a screen-crop preview above the carousel, so it
//! keeps upstream's own landscape aspect (`expanded_h` derived from
//! `expanded_w` by upstream's exact `475/768` ratio, same as the first
//! pass), just enlarged as far as the remaining page budget allows.
//! Everything below that used to be a bare module constant (`EXPANDED_W`,
//! `SLICE_H`, `SKEW`, ...) is now a field on whichever `CarouselGeometry` a
//! caller is drawing; `Carousel` itself owns one for its whole lifetime
//! (set once at construction, matching which carousel -- theme or
//! background -- it drives), and the free layout functions
//! (`visible_slices`, `hit_test`) take one explicitly, so the theme
//! carousel and the background carousel can each be sized for their own
//! page without duplicating any layout math.
//!
//! ## Portrait crop, not letterboxing
//!
//! Every `preview.png` this module draws is a landscape desktop
//! screenshot. Two ways to put that into a much taller hero slot were
//! considered: pillarbox it (keep the image's own landscape aspect, pad
//! the extra vertical space with plain bars) or crop it to the slot's own
//! portrait aspect. Pillarboxing wastes exactly the vertical space this
//! change exists to use, and (having painted it as a quick comparison)
//! reads as a smaller picture floating in a bigger frame -- an admission
//! the source doesn't fill its slot, not a bigger picture. A portrait crop
//! (still just `FitMode::Crop`'s existing centered cover-crop, now to a
//! taller aspect -- no new render code) fills the whole slot with real
//! pixels and, since a desktop screenshot's visually distinctive content
//! (terminal, editor, panel) usually sits centered anyway, keeps that
//! content rather than cropping it away. `THEME_GEOMETRY` uses a 3:4
//! portrait aspect (`480x640`) for exactly this reason. The background
//! carousel's imagery is the opposite case -- actual wallpapers, already
//! meant to be viewed full-screen on a portrait device -- but that page
//! has far less spare vertical budget (see below), so it keeps upstream's
//! landscape aspect rather than fighting for the extra height a portrait
//! crop there would need.
//!
//! `SLICE_W`/`SLICE_H` (a fully-collapsed side slice) were never landscape
//! to begin with -- upstream's own `108x432` is already a narrow, nearly
//! full-height vertical strip (aspect `0.25`) -- so no crop decision was
//! needed there; `slice_h` simply keeps upstream's own `432/475` ratio to
//! whichever `expanded_h` a geometry picks, so a side slice always spans
//! nearly the full height of its own carousel band, exactly as upstream.
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

/// Every fixed size a Cover Flow carousel needs, bundled so each carousel
/// context (the Themes page's hero, the Preview page's background picker)
/// can pick its own without duplicating the layout math below. See the
/// module doc for how `THEME_GEOMETRY`/`BACKGROUND_GEOMETRY` were chosen.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct CarouselGeometry {
    /// The centered slice's width.
    pub expanded_w: f64,
    /// The centered slice's height.
    pub expanded_h: f64,
    /// A fully-collapsed side slice's width.
    pub slice_w: f64,
    /// A fully-collapsed side slice's height.
    pub slice_h: f64,
    /// Upstream's `skewOffset`: a constant pixel shear applied to every
    /// slice's own width, regardless of that slice's current size.
    pub skew: f64,
    /// Upstream's `sliceSpacing`: negative, so consecutive slices overlap
    /// (a "shingled" look), resolved by z-order at paint time.
    pub spacing: f64,
}

impl CarouselGeometry {
    /// Pitch between adjacent slice centers/left-edges.
    pub const fn item_step(&self) -> f64 {
        self.slice_w + self.spacing
    }

    fn center_pitch(&self) -> f64 {
        (self.expanded_w + self.slice_w) / 2.0 + self.spacing
    }

    // Inverse of interpolated_layout's reference-card center. The first
    // transition includes the card shrinking; collapsed neighbors use pitch.
    fn position_at_center(&self, center: f64, reference: f64) -> f64 {
        let shoulder = (self.expanded_w - self.slice_w) / 2.0;
        reference + if center.abs() <= self.center_pitch() {
            -center / self.center_pitch()
        } else if center < 0.0 {
            (-center - shoulder) / self.item_step()
        } else {
            (shoulder - center) / self.item_step()
        }
    }

    fn reference_center(&self, position: f64, reference: f64) -> f64 {
        let (x, width, _, _) = interpolated_layout(self, position, reference as i64, 0.0);
        x + width / 2.0
    }
}

/// The Themes page's hero carousel: a large, portrait-cropped centered
/// slice using most of the panel's width, as the page's dominant content.
/// Width-derived measures keep upstream's exact ratio to `expanded_w`
/// (`SLICE_W`: `108/768`, `SKEW`: `28/768`, `SPACING`: `-30/768`);
/// `expanded_h` is a deliberate 3:4 portrait crop, not upstream's own
/// landscape aspect -- see the module doc's "Portrait crop" section.
/// `slice_h` keeps upstream's own `432/475` ratio to `expanded_h`, so a
/// side slice still spans nearly the whole carousel band, whatever its
/// height.
pub const THEME_GEOMETRY: CarouselGeometry = CarouselGeometry {
    expanded_w: 480.0,
    expanded_h: 640.0, // 3:4 portrait crop, not upstream's 768:475 landscape.
    slice_w: 68.0,     // 480 * 108/768 = 67.5, rounded.
    slice_h: 582.0,    // 640 * 432/475 = 582.06, rounded.
    skew: 18.0,        // 480 * 28/768 = 17.5, rounded.
    spacing: -19.0,    // 480 * -30/768 = -18.75, rounded.
};

/// The Preview page's background carousel: smaller than the Themes hero
/// because that page already carries a palette row and a screen-crop
/// preview above it (see `theme_ui::chooser_layout` for
/// exactly what's above). Keeps upstream's own landscape aspect (`475/768`
/// between `expanded_h`/`expanded_w`, same as every other measure here)
/// rather than fighting for height a portrait crop would need but this
/// page cannot spare.
pub const BACKGROUND_GEOMETRY: CarouselGeometry = CarouselGeometry {
    expanded_w: 420.0,
    expanded_h: 260.0, // 420 * 475/768 = 259.77, rounded: upstream's own aspect.
    slice_w: 59.0,     // 420 * 108/768 = 59.06, rounded.
    slice_h: 237.0,    // 260 * 432/475 = 236.5, rounded.
    skew: 15.0,        // 420 * 28/768 = 15.31, rounded.
    spacing: -16.0,    // 420 * -30/768 = -16.41, rounded.
};

/// The landscape panel's theme carousel: `THEME_GEOMETRY`'s own ratios
/// (3:4 portrait crop; `slice_w`, `slice_h`, `skew` and `spacing` as the
/// same fractions of `expanded_w`/`expanded_h`) scaled down so the carousel,
/// its two-line label and the header fit the 568 px panel's height beside the
/// background carousel.
pub const THEME_GEOMETRY_WIDE: CarouselGeometry = CarouselGeometry {
    expanded_w: 294.0,
    expanded_h: 392.0,
    slice_w: 42.0,  // 294 * 108/768 = 41.3, rounded.
    slice_h: 356.0, // 392 * 432/475 = 356.5, rounded.
    skew: 11.0,     // 294 * 28/768 = 10.7, rounded.
    spacing: -12.0, // 294 * -30/768 = -11.5, rounded.
};

/// How many slices either side of the centered position are laid out and
/// hit-tested at all. Upstream's own `nearby` cutoff is 16, sized for a
/// desktop monitor; ours is smaller because this screen is much narrower
/// (fewer slices are ever visible) and every visible id must fit in the
/// bounded thumbnail cache. Shared by both geometries above: the smaller,
/// more tightly margined hero carousel needs no more of a lookahead than
/// the background carousel already used.
pub const NEARBY_LIMIT: i64 = 8;

const MAX_FLING_PX_PER_SEC: f64 = 3000.0;
const RELEASE_VELOCITY_MAX_AGE_MS: u32 = 100;
/// Below this fraction of one focused-center transition per second, release settles instead of
/// coasting -- a slow drag release should not "coast" a fraction of a slot.
const MIN_COAST_VELOCITY: f64 = 0.35;
/// Per-16ms decay factor, matching `navigation.rs`'s `DrawerNavigation` and
/// `service_ui.rs`'s `NotificationCoast` so every flick in this shell decays
/// at a visually consistent rate.
const DECAY_PER_16MS: f64 = 0.88;
/// A touch that never moved more than this many pixels is a tap, not a drag.
const TAP_SLOP: f64 = 8.0;
/// Centering is a critically damped spring in reference-card pixels
/// (task 18.2): it starts from the release or coast velocity, so speed never
/// jumps, and it is evaluated in closed form from the full elapsed time, so
/// 8 ms and 200 ms frame cadences trace the same wall-clock trajectory. At
/// this stiffness the card is within 5% of its slot after about 215 ms; a
/// tunable candidate, not an Apple-prescribed value (design.md, task 18.1).
const SETTLE_OMEGA: f64 = 22.0;
/// Below both of these the spring snaps exactly onto its slot.
const SETTLE_REST_PX: f64 = 0.25;
const SETTLE_REST_PX_PER_SEC: f64 = 4.0;

/// `DECAY_PER_16MS` as a continuous rate, so coasting can be integrated
/// exactly over any elapsed time instead of in clamped 16 ms steps.
fn coast_decay_per_sec() -> f64 {
    -DECAY_PER_16MS.ln() * 1000.0 / 16.0
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
fn exact_layout(geometry: &CarouselGeometry, selected: i64, i: i64, center_x: f64) -> (f64, f64, f64, f64) {
    let relative = i - selected;
    let preview_x = center_x - geometry.expanded_w / 2.0;
    if relative == 0 {
        return (preview_x, geometry.expanded_w, geometry.expanded_h, 0.0);
    }
    let item_step = geometry.item_step();
    let x = if relative < 0 {
        preview_x + relative as f64 * item_step
    } else {
        preview_x + geometry.expanded_w + geometry.spacing + (relative - 1) as f64 * item_step
    };
    let y = (geometry.expanded_h - geometry.slice_h) / 2.0;
    (x, geometry.slice_w, geometry.slice_h, y)
}

/// The continuous approximation described in the module doc: lerp between
/// upstream's own exact layout at the two integers bracketing `position`.
fn interpolated_layout(geometry: &CarouselGeometry, position: f64, i: i64, center_x: f64) -> (f64, f64, f64, f64) {
    let lo = position.floor();
    let hi = position.ceil();
    let a = exact_layout(geometry, lo as i64, i, center_x);
    if (hi - lo).abs() < f64::EPSILON {
        return a;
    }
    let b = exact_layout(geometry, hi as i64, i, center_x);
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
pub fn visible_slices(
    geometry: &CarouselGeometry,
    position: f64,
    count: usize,
    center_x: f64,
    top_y: f64,
) -> Vec<SlicePlacement> {
    if count == 0 {
        return Vec::new();
    }
    let center = position.round() as i64;
    let lo = (center - NEARBY_LIMIT).max(0);
    let hi = (center + NEARBY_LIMIT).min(count as i64 - 1);
    let mut slices: Vec<SlicePlacement> = (lo..=hi)
        .map(|i| {
            let relative = i as f64 - position;
            let (x, width, height, y) = interpolated_layout(geometry, position, i, center_x);
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
/// `(skew, 0)` to `(0, height)` and the right edge from `(width, 0)` to
/// `(width - skew, height)`; at a given fractional height `t`, the valid
/// horizontal span narrows linearly from the top edge's full-`skew` inset.
fn in_slice(skew: f64, px: f64, py: f64, width: f64, height: f64) -> bool {
    if height <= 0.0 || py < 0.0 || py > height {
        return false;
    }
    let t = (py / height).clamp(0.0, 1.0);
    let left = skew * (1.0 - t);
    let right = width - skew * t;
    px >= left && px <= right
}

/// Which slice, if any, a tap at `point` lands on, honoring the skewed
/// shape and upstream's z-order (the slice nearest the centered position is
/// drawn on top of its shingled neighbors, so it is tested first).
pub fn hit_test(
    geometry: &CarouselGeometry,
    point: (f64, f64),
    position: f64,
    count: usize,
    center_x: f64,
    top_y: f64,
) -> Option<usize> {
    let mut slices = visible_slices(geometry, position, count, center_x, top_y);
    slices.sort_by(|a, b| b.z.cmp(&a.z));
    slices.into_iter().find_map(|slice| {
        let px = point.0 - slice.x;
        let py = point.1 - slice.y;
        in_slice(geometry.skew, px, py, slice.width, slice.height).then_some(slice.index)
    })
}

#[derive(Clone, Copy, Debug)]
struct Contact {
    id: i32,
    start_x: f64,
    start_y: f64,
    start_position: f64,
    last_x: f64,
    last_ms: u32,
    finger_velocity: f64, // px/sec, sign matching finger motion (not carousel position)
    dragged: bool,
    cancelled: bool,
}

/// A critically damped approach to `target`, in the reference card's
/// pixel space: `offset`/`velocity` are its displacement from the target
/// card center and its speed when the settle began, `elapsed` seconds ago.
#[derive(Clone, Copy, Debug)]
struct Settle {
    reference: f64,
    target: f64,
    target_center: f64,
    offset: f64,
    velocity: f64,
    elapsed: f64,
}

impl Settle {
    /// Displacement and velocity `elapsed` seconds after the start.
    fn state(&self) -> (f64, f64) {
        let b = self.velocity + SETTLE_OMEGA * self.offset;
        let decay = (-SETTLE_OMEGA * self.elapsed).exp();
        (
            (self.offset + b * self.elapsed) * decay,
            (self.velocity - SETTLE_OMEGA * b * self.elapsed) * decay,
        )
    }
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
/// theme's background list -- both get one of these; see `main.rs`). Each
/// instance is constructed with the [`CarouselGeometry`] it draws (see
/// `THEME_GEOMETRY`/`BACKGROUND_GEOMETRY`) and keeps it for its whole
/// lifetime -- it never changes underneath a live drag.
pub struct Carousel {
    geometry: CarouselGeometry,
    position: f64,
    velocity: f64, // reference-card pixels/sec, matching finger direction
    coast_reference: f64,
    contact: Option<Contact>,
    settle: Option<Settle>,
    /// The next `tick` is the first since a release, tap or wheel stop
    /// started motion. Its `elapsed` predates that start (the event loop
    /// measures from its previous iteration, which may be a long hold), so
    /// it counts as zero rather than jumping the card forward.
    motion_started: bool,
}

impl Carousel {
    pub fn new(geometry: CarouselGeometry) -> Self {
        Self {
            geometry,
            position: 0.0,
            velocity: 0.0,
            coast_reference: 0.0,
            contact: None,
            settle: None,
            motion_started: false,
        }
    }

    /// Adopts `geometry` (the output's size changed, so the chooser's
    /// carousels were re-laid out), dropping any touch or motion in flight
    /// and snapping to the nearest item. A no-op when it is already in use.
    pub fn geometry(&self) -> CarouselGeometry {
        self.geometry
    }

    pub fn set_geometry(&mut self, geometry: CarouselGeometry) {
        if self.geometry == geometry {
            return;
        }
        self.geometry = geometry;
        self.position = self.position.round();
        self.velocity = 0.0;
        self.contact = None;
        self.settle = None;
    }

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

    /// Position, velocity (reference-card px/sec, finger direction) and
    /// motion phase for one bounded trace record per frame. The phase is
    /// 0 at rest, 1 under a finger, 2 coasting, 3 settling. Velocity is the
    /// coast or spring velocity; under a finger it is 0, since the card
    /// follows the touch directly.
    pub fn trace_state(&self) -> (f64, f64, u64) {
        if self.contact.is_some() {
            (self.position, 0.0, 1)
        } else if let Some(settle) = &self.settle {
            (self.position, settle.state().1, 3)
        } else if self.velocity != 0.0 {
            (self.position, self.velocity, 2)
        } else {
            (self.position, 0.0, 0)
        }
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

    /// Wheel movement browses candidates only, never applies one. Continuous
    /// deltas track directly; axis-stop (or a discrete wheel tick) settles.
    pub fn scroll_by(&mut self, delta: f64, count: usize, settle: bool) -> bool {
        if self.contact.is_some() || count == 0 || !delta.is_finite() { return false; }
        let old = self.position;
        self.velocity = 0.0;
        self.settle = None;
        self.position = (old + delta / self.geometry.item_step()).clamp(0.0, (count - 1) as f64);
        if settle { self.start_settle(self.position.round()); }
        self.position != old || self.settle.is_some()
    }

    /// Which slice, if any, should show an immediate "pressed" highlight
    /// this frame: the finger is down inside the carousel band and hasn't
    /// moved past `TAP_SLOP` into a real drag yet. Goal is a highlight
    /// visible within one frame of the touch landing (see `render.rs`'s
    /// `paint_carousel`), using the touch's own down point -- not its
    /// current point -- so the highlighted slice never flickers to a
    /// neighbor from a sub-slop wobble. Returns `None` once a drag starts
    /// (`Contact::dragged`), the contact is cancelled, or the touch has
    /// ended (`contact` is `None`), so callers never need to clear this
    /// explicitly on release.
    pub fn pressed(&self, count: usize, center_x: f64, top_y: f64) -> Option<usize> {
        let contact = self.contact.as_ref()?;
        if contact.dragged || contact.cancelled || count == 0 {
            return None;
        }
        hit_test(
            &self.geometry,
            (contact.start_x, contact.start_y),
            self.position,
            count,
            center_x,
            top_y,
        )
    }

    pub fn down(&mut self, id: i32, point: (f64, f64), time_ms: u32) {
        self.velocity = 0.0; // touching a coasting/settling carousel stops it
        self.settle = None;
        self.contact = Some(Contact {
            id,
            start_x: point.0,
            start_y: point.1,
            start_position: self.position,
            last_x: point.0,
            last_ms: time_ms,
            finger_velocity: 0.0,
            dragged: false,
            cancelled: false,
        });
    }

    /// Move the contact's reference card center by the finger displacement.
    /// Collapsed-slot spacing alone does not measure visible card travel.
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
        } else if elapsed >= 1000 {
            contact.finger_velocity = 0.0;
        }
        if (point.0 - contact.start_x).abs() > TAP_SLOP {
            contact.dragged = true;
        }
        contact.last_x = point.0;
        contact.last_ms = time_ms;
        let old = self.position;
        let max_index = count.saturating_sub(1) as f64;
        let reference = contact.start_position.round();
        let origin = self.geometry.reference_center(contact.start_position, reference);
        self.position = self.geometry.position_at_center(
            origin + point.0 - contact.start_x, reference,
        ).clamp(0.0, max_index);
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
            let Some(tapped) = hit_test(&self.geometry, point, self.position, count, center_x, top_y) else {
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
        let velocity = if time_ms.wrapping_sub(contact.last_ms) <= RELEASE_VELOCITY_MAX_AGE_MS {
            contact.finger_velocity
        } else {
            0.0
        };
        self.coast_reference = contact.start_position.round();
        if velocity.abs() < self.coast_threshold() {
            self.settle_with_velocity(velocity, count);
        } else {
            self.velocity = velocity;
            self.motion_started = true;
        }
        Some(CarouselOutcome::Consumed)
    }

    pub fn cancel(&mut self) {
        self.contact = None;
        self.velocity = 0.0;
    }

    fn coast_threshold(&self) -> f64 {
        MIN_COAST_VELOCITY * self.geometry.center_pitch()
    }

    /// Settle onto an explicit slot (a tapped side slice, a wheel stop)
    /// from rest.
    fn start_settle(&mut self, target: f64) {
        self.begin_settle(target, target, 0.0);
    }

    /// Settle while keeping `velocity` (reference-card px/sec). The slot is
    /// the nearest one to where that velocity would carry the card, moved
    /// one slot further along the motion if the spring would otherwise
    /// have to overshoot to reach it, so the approach stays monotonic.
    fn settle_with_velocity(&mut self, velocity: f64, count: usize) {
        let max_index = count.saturating_sub(1) as f64;
        let reference = self.coast_reference;
        let center = self.geometry.reference_center(self.position, reference);
        let projected = center + velocity / SETTLE_OMEGA;
        let mut target = self.geometry.position_at_center(projected, reference).round().clamp(0.0, max_index);
        if velocity != 0.0
            && (self.geometry.reference_center(target, reference) - projected) * velocity.signum() < 0.0
        {
            // Card centers move right as the index falls.
            target = (target - velocity.signum()).clamp(0.0, max_index);
        }
        self.begin_settle(target, reference, velocity);
    }

    fn begin_settle(&mut self, target: f64, reference: f64, velocity: f64) {
        let target_center = self.geometry.reference_center(target, reference);
        let offset = self.geometry.reference_center(self.position, reference) - target_center;
        // Only a catalogue end can leave the card heading for its slot faster
        // than a critically damped spring can stop without crossing it; stop
        // at the bound rather than bounce past it.
        let velocity = if velocity * offset < 0.0 && velocity.abs() > SETTLE_OMEGA * offset.abs() {
            -SETTLE_OMEGA * offset
        } else {
            velocity
        };
        self.settle = Some(Settle { reference, target, target_center, offset, velocity, elapsed: 0.0 });
        self.velocity = 0.0;
        self.motion_started = true;
    }

    /// Advances momentum decay or a settle-to-nearest animation. Returns
    /// whether a repaint is needed. `elapsed_ms` is however long it has been
    /// since the caller's last `tick`/frame -- an accumulator, never an
    /// absolute clock, so this never has to agree with any other subsystem's
    /// time domain (the Wayland touch timestamps `down`/`motion`/`up` receive
    /// included). The whole interval is used: coasting and settling are
    /// solved in closed form, and the coast-to-settle handover and catalogue
    /// ends are found exactly inside the interval, so irregular frame
    /// cadences do not stretch or reshape the motion.
    pub fn tick(&mut self, elapsed_ms: u32, count: usize) -> bool {
        if self.contact.is_some() || count == 0 || !self.is_animating() {
            return false;
        }
        let mut remaining = if std::mem::take(&mut self.motion_started) {
            0.0
        } else {
            f64::from(elapsed_ms) / 1000.0
        };
        let max_index = count.saturating_sub(1) as f64;
        if self.velocity != 0.0 && self.settle.is_none() {
            remaining = self.coast(remaining, max_index, count);
        }
        if let Some(settle) = self.settle.as_mut() {
            settle.elapsed += remaining;
            let (offset, velocity) = settle.state();
            let (target, reference, target_center) = (settle.target, settle.reference, settle.target_center);
            if offset.abs() < SETTLE_REST_PX && velocity.abs() < SETTLE_REST_PX_PER_SEC {
                self.position = target;
                self.settle = None;
            } else {
                self.position = self.geometry.position_at_center(target_center + offset, reference).clamp(0.0, max_index);
            }
        }
        true
    }

    /// Coasts for up to `dt` seconds of exponential decay, stopping early at
    /// the instant the velocity falls to the settle threshold or the card
    /// reaches a catalogue end, where it hands over to the spring. Returns
    /// the time left for that settle.
    fn coast(&mut self, dt: f64, max_index: f64, count: usize) -> f64 {
        let k = coast_decay_per_sec();
        let v = self.velocity;
        let reference = self.coast_reference;
        let center = self.geometry.reference_center(self.position, reference);
        let threshold = self.coast_threshold();
        let to_threshold = if v.abs() > threshold { (v.abs() / threshold).ln() / k } else { 0.0 };
        // Card centers move right (positive velocity) toward index 0.
        let bound = if v > 0.0 { 0.0 } else { max_index };
        let to_bound_px = self.geometry.reference_center(bound, reference) - center;
        let reach = to_bound_px * k / v; // fraction of the remaining coast distance
        let to_bound = if (0.0..1.0).contains(&reach) { -(1.0 - reach).ln() / k } else { f64::INFINITY };
        let step = dt.min(to_threshold).min(to_bound);
        let decay = (-k * step).exp();
        let moved = center + v * (1.0 - decay) / k;
        self.position = self.geometry.position_at_center(moved, reference).clamp(0.0, max_index);
        let velocity = v * decay;
        if step >= to_bound {
            self.position = bound;
            self.velocity = 0.0;
            self.begin_settle(bound, reference, velocity);
            self.motion_started = false;
        } else if step >= to_threshold {
            self.velocity = 0.0;
            self.settle_with_velocity(velocity, count);
            self.motion_started = false;
        } else {
            self.velocity = velocity;
        }
        dt - step
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn index_from_offset_rounds_to_nearest_and_clamps() {
        let mut carousel = Carousel::new(THEME_GEOMETRY);
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

    fn rendered_center(geometry: &CarouselGeometry, position: f64, index: usize) -> f64 {
        let slice = visible_slices(geometry, position, 30, 284.0, 200.0)
            .into_iter().find(|slice| slice.index == index).unwrap();
        slice.x + slice.width / 2.0
    }

    #[test]
    fn drag_tracks_rendered_pixels_in_both_rows_across_transitions_and_reversals() {
        for geometry in [THEME_GEOMETRY, BACKGROUND_GEOMETRY] {
            for start in [10.0_f64, 10.2, 10.8] {
                let mut carousel = Carousel::new(geometry);
                carousel.position = start;
                let reference = start.round() as usize;
                let origin = rendered_center(&geometry, start, reference);
                carousel.down(1, (284.0, 600.0), 0);
                for (i, dx) in [-20.0, -120.0, -280.0, -320.0, -140.0, 0.0, 120.0, 280.0].into_iter().enumerate() {
                    carousel.motion(1, (284.0 + dx, 600.0), (i as u32 + 1) * 16, 30);
                    let actual = rendered_center(&geometry, carousel.position(), reference) - origin;
                    assert!((actual - dx).abs() < 1e-6, "start={start} dx={dx} actual={actual}");
                    let held = carousel.position();
                    assert!(!carousel.tick(48, 30));
                    assert_eq!(carousel.position(), held);
                }
            }
        }
    }

    #[test]
    fn release_after_hold_expires_velocity_even_without_more_motion_events() {
        for geometry in [THEME_GEOMETRY, BACKGROUND_GEOMETRY] {
            for start_time in [0_u32, u32::MAX - 30] {
                let mut carousel = Carousel::new(geometry);
                carousel.set_index(10);
                carousel.down(1, (284.0, 600.0), start_time);
                carousel.motion(1, (184.0, 600.0), start_time.wrapping_add(16), 30);
                let held = carousel.position();
                carousel.up(1, (184.0, 600.0), start_time.wrapping_add(300), 30, 284.0, 200.0);
                assert_eq!(carousel.position(), held, "release must not jump");
                assert_eq!(carousel.velocity, 0.0, "stationary hold must not fling");
                assert_eq!(carousel.settle.unwrap().target, held.round());
            }
        }
    }

    #[test]
    fn trace_state_reports_each_motion_phase_with_its_velocity() {
        let mut carousel = Carousel::new(THEME_GEOMETRY);
        carousel.set_index(10);
        assert_eq!(carousel.trace_state(), (10.0, 0.0, 0));
        carousel.down(1, (284.0, 600.0), 0);
        carousel.motion(1, (184.0, 600.0), 20, 30);
        assert_eq!(carousel.trace_state(), (carousel.position(), 0.0, 1));
        carousel.up(1, (184.0, 600.0), 21, 30, 284.0, 200.0);
        let (_, velocity, phase) = carousel.trace_state();
        assert_eq!(phase, 2);
        assert!(velocity < 0.0, "a leftward fling reports leftward velocity");
        let mut ticks = 0;
        while carousel.trace_state().2 == 2 && ticks < 1000 {
            carousel.tick(16, 30);
            ticks += 1;
        }
        assert_eq!(carousel.trace_state().2, 3, "the coast hands over to the settle");
        while carousel.tick(16, 30) {}
        let (position, velocity, phase) = carousel.trace_state();
        assert_eq!((position.fract(), velocity, phase), (0.0, 0.0, 0));
    }

    #[test]
    fn release_preserves_screen_space_velocity_without_a_position_jump() {
        for geometry in [THEME_GEOMETRY, BACKGROUND_GEOMETRY] {
            let mut carousel = Carousel::new(geometry);
            carousel.set_index(10);
            carousel.down(1, (284.0, 600.0), 0);
            carousel.motion(1, (264.0, 600.0), 20, 30);
            let before = rendered_center(&geometry, carousel.position(), 10);
            carousel.up(1, (264.0, 600.0), 21, 30, 284.0, 200.0);
            assert_eq!(rendered_center(&geometry, carousel.position(), 10), before);
            // The first tick's interval predates the release: no jump.
            assert!(carousel.tick(16, 30));
            assert_eq!(rendered_center(&geometry, carousel.position(), 10), before);
            // Then the release speed (20 px in 20 ms, leftward) decays
            // exactly: the next 16 ms covers v(1 - e^-kt)/k, under 16 px.
            carousel.tick(16, 30);
            let k = coast_decay_per_sec();
            let expected = -1000.0 * (1.0 - (-k * 0.016).exp()) / k;
            let moved = rendered_center(&geometry, carousel.position(), 10) - before;
            assert!((moved - expected).abs() < 1e-6, "moved={moved} expected={expected}");
        }
    }

    #[test]
    fn drag_clamps_at_both_ends() {
        let mut carousel = Carousel::new(THEME_GEOMETRY);
        let item_step = THEME_GEOMETRY.item_step();
        carousel.set_index(0);
        carousel.down(1, (300.0, 600.0), 0);
        carousel.motion(1, (300.0 + item_step * 50.0, 600.0), 16, 5);
        assert_eq!(carousel.position(), 0.0);
        carousel.set_index(4);
        carousel.down(1, (300.0, 600.0), 0);
        carousel.motion(1, (300.0 - item_step * 50.0, 600.0), 16, 5);
        assert_eq!(carousel.position(), 4.0);
    }

    #[test]
    fn slow_release_settles_immediately_to_nearest() {
        let mut carousel = Carousel::new(THEME_GEOMETRY);
        let item_step = THEME_GEOMETRY.center_pitch();
        carousel.set_index(2);
        carousel.down(1, (300.0, 600.0), 0);
        // A quick initial move establishes real drag distance (past
        // TAP_SLOP), then the finger holds nearly still for a long moment
        // before lifting -- release velocity is measured from the last
        // motion segment only, matching a real touch driver, so this is a
        // "slow release" even though the whole gesture moved a full slot.
        carousel.motion(1, (300.0 - item_step * 0.6, 600.0), 16, 22);
        carousel.motion(1, (300.0 - item_step * 0.6 - 1.0, 600.0), 416, 22);
        let tap = carousel.up(1, (300.0 - item_step * 0.6 - 1.0, 600.0), 420, 22, 284.0, 200.0);
        assert_eq!(tap, Some(CarouselOutcome::Consumed), "a drag release never itself confirms");
        assert!(carousel.is_animating(), "settle animation must be running");
        // Settle target is the nearest slot to where the finger let go,
        // ~2.6, which rounds to 3, reached once the settle duration elapses.
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
        let mut carousel = Carousel::new(THEME_GEOMETRY);
        let item_step = THEME_GEOMETRY.item_step();
        carousel.set_index(10);
        carousel.down(1, (300.0, 600.0), 0);
        // A fast leftward drag (finger velocity clamps to MAX_FLING) should
        // start a momentum coast, not an immediate settle.
        carousel.motion(1, (300.0 - item_step * 3.0, 600.0), 20, 22);
        let tap = carousel.up(1, (300.0 - item_step * 3.0, 600.0), 21, 22, 284.0, 200.0);
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
        let mut carousel = Carousel::new(THEME_GEOMETRY);
        carousel.set_index(4);
        let center_x = 284.0;
        let top_y = 200.0;
        let centered = visible_slices(&THEME_GEOMETRY, 4.0, 22, center_x, top_y)
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

        let neighbor = visible_slices(&THEME_GEOMETRY, 4.0, 22, center_x, top_y)
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
        let skew = THEME_GEOMETRY.skew;
        let slice_w = THEME_GEOMETRY.slice_w;
        let slice_h = THEME_GEOMETRY.slice_h;
        // A point in the rectangle's top-left corner, but outside the
        // sheared-in left edge at y=0 (valid x there is [skew, width]).
        assert!(!in_slice(skew, skew / 2.0, 0.0, slice_w, slice_h));
        // The same x is inside the shape once y has moved far enough down
        // that the shear has widened the left bound past it.
        assert!(in_slice(skew, skew / 2.0, slice_h, slice_w, slice_h));
        // Dead center is always inside regardless of skew.
        assert!(in_slice(skew, slice_w / 2.0, slice_h / 2.0, slice_w, slice_h));
        // Symmetric check on the right edge: it is untouched at the top
        // (valid x there is [skew, width]) but sheared in at the bottom
        // (valid x there is [0, width - skew]).
        assert!(in_slice(skew, slice_w - skew / 2.0, 0.0, slice_w, slice_h));
        assert!(!in_slice(skew, slice_w - skew / 2.0, slice_h, slice_w, slice_h));
    }

    #[test]
    fn hit_test_prefers_the_slice_nearest_center_in_overlap() {
        // Negative spacing makes consecutive slices overlap; the centered
        // slice's z-order (100) beats every neighbor, so a point inside both
        // the expanded slice and a neighbor's bounding box must resolve to
        // the centered index.
        let center_x = 284.0;
        let top_y = 200.0;
        let centered = visible_slices(&THEME_GEOMETRY, 4.0, 22, center_x, top_y)
            .into_iter()
            .find(|slice| slice.index == 4)
            .unwrap();
        // 20px in from the centered slice's own left edge, at half its
        // height: inside the centered slice's sheared shape (the shear
        // only excludes the first ~skew px near an edge), and still inside
        // the shingled left neighbor's bounding box (item_step < slice_w).
        let point = (centered.x + 20.0, centered.y + centered.height / 2.0);
        assert_eq!(hit_test(&THEME_GEOMETRY, point, 4.0, 22, center_x, top_y), Some(4));
    }

    #[test]
    fn set_index_stops_any_animation_in_progress() {
        let mut carousel = Carousel::new(THEME_GEOMETRY);
        carousel.set_index(0);
        carousel.start_settle(3.0);
        carousel.velocity = 5.0;
        carousel.set_index(7);
        assert!(!carousel.is_animating());
        assert_eq!(carousel.index(22), 7);
    }

    #[test]
    fn pressed_shows_immediately_on_down_and_clears_on_drag_or_release() {
        let mut carousel = Carousel::new(THEME_GEOMETRY);
        carousel.set_index(4);
        let center_x = 284.0;
        let top_y = 200.0;
        let centered = visible_slices(&THEME_GEOMETRY, 4.0, 22, center_x, top_y)
            .into_iter()
            .find(|slice| slice.index == 4)
            .unwrap();
        let point = (center_x, top_y + centered.height / 2.0);
        assert_eq!(
            carousel.pressed(22, center_x, top_y),
            None,
            "nothing is pressed before any touch lands"
        );
        carousel.down(1, point, 0);
        assert_eq!(
            carousel.pressed(22, center_x, top_y),
            Some(4),
            "the tapped slice reads as pressed on the very same frame as the touch-down"
        );
        // A small wobble under TAP_SLOP must not clear the press.
        carousel.motion(1, (point.0 + 2.0, point.1), 10, 22);
        assert_eq!(carousel.pressed(22, center_x, top_y), Some(4));
        // Once the drag exceeds TAP_SLOP, this is a drag, not a tap: the
        // pressed highlight must clear even though the finger is still down.
        carousel.motion(1, (point.0 + 40.0, point.1), 20, 22);
        assert_eq!(
            carousel.pressed(22, center_x, top_y),
            None,
            "a real drag must not keep showing a stale press highlight"
        );
        carousel.up(1, (point.0 + 40.0, point.1), 30, 22, center_x, top_y);
        assert_eq!(carousel.pressed(22, center_x, top_y), None);
        // The drag above moved the carousel itself; reset to a clean,
        // known-settled position 4 before the next tap-and-release check so
        // `point` (computed once, above, for position 4) is still where
        // slice 4 actually sits.
        carousel.set_index(4);

        // A clean tap-and-release also clears the press once the touch ends.
        carousel.down(2, point, 100);
        assert_eq!(carousel.pressed(22, center_x, top_y), Some(4));
        carousel.up(2, point, 110, 22, center_x, top_y);
        assert_eq!(
            carousel.pressed(22, center_x, top_y),
            None,
            "press highlight clears once the touch is released"
        );
    }

    #[test]
    fn background_geometry_is_smaller_but_keeps_upstreams_ratios() {
        // The Preview page's carousel is deliberately smaller than the
        // Themes page's hero (less spare vertical budget -- see the module
        // doc), but every width-derived ratio to upstream is still exact,
        // and slice_h still keeps upstream's own height ratio.
        let g = BACKGROUND_GEOMETRY;
        assert!(g.expanded_w < THEME_GEOMETRY.expanded_w);
        assert!(g.expanded_h < THEME_GEOMETRY.expanded_h);
        assert!((g.slice_w / g.expanded_w - 108.0 / 768.0).abs() < 0.01);
        assert!((g.slice_h / g.expanded_h - 432.0 / 475.0).abs() < 0.01);
        assert!((g.skew / g.expanded_w - 28.0 / 768.0).abs() < 0.01);
    }
}

#[cfg(test)]
mod pointer_scroll_tests {
    use super::*;
    #[test]
    fn wheel_browses_and_settles_without_a_touch_activation() {
        let mut carousel = Carousel::new(THEME_GEOMETRY);
        assert!(carousel.scroll_by(THEME_GEOMETRY.item_step() * 1.6, 5, false));
        assert!((carousel.position() - 1.6).abs() < 0.001);
        assert!(carousel.scroll_by(0.0, 5, true));
        for _ in 0..100 { carousel.tick(16, 5); }
        assert_eq!(carousel.position(), 2.0);
        carousel.down(1, (200.0, 200.0), 100);
        assert!(!carousel.scroll_by(200.0, 5, true));
        carousel.cancel();
        carousel.scroll_by(10000.0, 5, true);
        assert_eq!(carousel.position(), 4.0);
        assert!(!carousel.scroll_by(f64::INFINITY, 5, true));
    }
}

/// Task 18.2: release motion uses the whole elapsed time and hands its
/// velocity to an interruptible, monotonic centering spring.
#[cfg(test)]
mod motion_tests {
    use super::*;

    const COUNT: usize = 30;

    /// A one-segment drag released `dt_ms` after it started, then the
    /// first (zero-length) tick that release causes.
    fn released(geometry: CarouselGeometry, start: usize, dx: f64, dt_ms: u32) -> Carousel {
        let mut carousel = Carousel::new(geometry);
        carousel.set_index(start);
        carousel.down(1, (284.0, 600.0), 0);
        carousel.motion(1, (284.0 + dx, 600.0), dt_ms, COUNT);
        carousel.up(1, (284.0 + dx, 600.0), dt_ms + 1, COUNT, 284.0, 200.0);
        carousel.tick(500, COUNT);
        carousel
    }

    fn center(carousel: &Carousel, reference: usize) -> f64 {
        carousel.geometry.reference_center(carousel.position(), reference as f64)
    }

    /// Reference-card centers after each tick of `cadence_ms`, keyed by wall
    /// time since the release.
    fn trajectory(mut carousel: Carousel, reference: usize, cadence_ms: u32) -> Vec<(u32, f64)> {
        let mut samples = vec![(0, center(&carousel, reference))];
        let mut now = 0;
        while carousel.is_animating() && now < 5000 {
            carousel.tick(cadence_ms, COUNT);
            now += cadence_ms;
            samples.push((now, center(&carousel, reference)));
        }
        assert!(!carousel.is_animating(), "motion must come to rest");
        assert_eq!(carousel.position().fract(), 0.0, "rest is a whole slot");
        samples
    }

    // (start index, finger dx, drag ms): fast flicks both ways, a moderate
    // coast, a release just above and one below the coast threshold, and
    // flicks into both catalogue ends.
    const RELEASES: [(usize, f64, u32); 7] = [
        (12, -60.0, 20),
        (12, 60.0, 20),
        (12, -24.0, 20),
        (12, -20.0, 100),
        (12, -12.0, 400),
        (1, 80.0, 20),
        (28, -80.0, 20),
    ];

    #[test]
    fn frame_cadence_does_not_change_the_wall_clock_trajectory() {
        for geometry in [THEME_GEOMETRY, BACKGROUND_GEOMETRY] {
            for (start, dx, dt) in RELEASES {
                let reference = trajectory(released(geometry, start, dx, dt), start, 1);
                let rest = reference.last().unwrap().1;
                for cadence in [8, 16, 33, 100, 200] {
                    let samples = trajectory(released(geometry, start, dx, dt), start, cadence);
                    assert_eq!(samples.last().unwrap().1, rest, "{start} {dx} {dt} @{cadence}ms rests elsewhere");
                    for (t, x) in samples {
                        let expected = reference.get(t as usize).map_or(rest, |sample| sample.1);
                        // Exact up to the spring's final snap onto its slot.
                        assert!((x - expected).abs() <= SETTLE_REST_PX + 1e-6,
                            "{start} {dx} {dt} @{cadence}ms t={t}: {x} vs {expected}");
                    }
                }
            }
        }
    }

    #[test]
    fn releases_approach_their_slot_without_reversing_or_leaving_the_catalogue() {
        for geometry in [THEME_GEOMETRY, BACKGROUND_GEOMETRY] {
            for (start, dx, dt) in RELEASES {
                let carousel = released(geometry, start, dx, dt);
                let speed = dx.signum();
                let samples = trajectory(carousel, start, 1);
                for pair in samples.windows(2) {
                    assert!((pair[1].1 - pair[0].1) * speed >= -1e-9,
                        "{start} {dx} {dt}: reversed at t={}", pair[1].0);
                }
                let low = geometry.reference_center((COUNT - 1) as f64, start as f64);
                let high = geometry.reference_center(0.0, start as f64);
                assert!(samples.iter().all(|&(_, x)| x >= low - 1e-9 && x <= high + 1e-9));
            }
        }
    }

    #[test]
    fn coasting_hands_its_exact_velocity_to_the_settle() {
        for geometry in [THEME_GEOMETRY, BACKGROUND_GEOMETRY] {
            for dx in [-60.0, 60.0, -24.0] {
                let mut carousel = released(geometry, 12, dx, 20);
                assert!(carousel.velocity != 0.0 && carousel.settle.is_none(), "{dx} should coast");
                let threshold = carousel.coast_threshold();
                while carousel.settle.is_none() {
                    carousel.tick(7, COUNT);
                }
                let settle = carousel.settle.unwrap();
                assert!((settle.velocity.abs() - threshold).abs() < 1e-6, "{dx}: {}", settle.velocity);
                assert_eq!(settle.velocity.signum(), dx.signum());
            }
        }
    }

    #[test]
    fn a_slow_release_keeps_its_small_velocity_and_a_hold_keeps_none() {
        for geometry in [THEME_GEOMETRY, BACKGROUND_GEOMETRY] {
            let carousel = released(geometry, 12, -12.0, 400);
            let settle = carousel.settle.expect("below the coast threshold settles at once");
            assert!((settle.velocity + 30.0).abs() < 1e-6, "12 px over 400 ms");
            // Stale: the finger held still past the age limit before lifting.
            let mut held = Carousel::new(geometry);
            held.set_index(12);
            held.down(1, (284.0, 600.0), 0);
            held.motion(1, (184.0, 600.0), 16, COUNT);
            held.up(1, (184.0, 600.0), 2016, COUNT, 284.0, 200.0);
            assert_eq!(held.settle.unwrap().velocity, 0.0);
        }
    }

    #[test]
    fn a_reversal_releases_in_the_direction_of_the_last_movement() {
        for geometry in [THEME_GEOMETRY, BACKGROUND_GEOMETRY] {
            let mut carousel = Carousel::new(geometry);
            carousel.set_index(12);
            carousel.down(1, (284.0, 600.0), 0);
            carousel.motion(1, (224.0, 600.0), 20, COUNT);
            carousel.motion(1, (254.0, 600.0), 40, COUNT);
            let at_release = carousel.position();
            carousel.up(1, (254.0, 600.0), 41, COUNT, 284.0, 200.0);
            assert!(carousel.velocity > 0.0, "the card follows the finger's last, rightward segment");
            let samples = trajectory(carousel, 12, 16);
            assert!(samples.windows(2).all(|pair| pair[1].1 >= pair[0].1 - 1e-9));
            assert!(samples.last().unwrap().1 >= geometry.reference_center(at_release, 12.0));
        }
    }

    #[test]
    fn a_long_hold_does_not_jump_the_first_frame_after_release() {
        for geometry in [THEME_GEOMETRY, BACKGROUND_GEOMETRY] {
            let mut carousel = Carousel::new(geometry);
            carousel.set_index(12);
            carousel.down(1, (284.0, 600.0), 0);
            carousel.motion(1, (184.0, 600.0), 16, COUNT);
            carousel.up(1, (184.0, 600.0), 2016, COUNT, 284.0, 200.0);
            let held = carousel.position();
            assert!(carousel.tick(2000, COUNT));
            assert_eq!(carousel.position(), held, "the hold's 2 s is not settle time");
            carousel.tick(16, COUNT);
            assert!(carousel.is_animating() && carousel.position() != held);
        }
    }

    #[test]
    fn a_new_touch_catches_the_card_where_it_is_drawn() {
        for geometry in [THEME_GEOMETRY, BACKGROUND_GEOMETRY] {
            for frames in [3, 40] {
                let mut carousel = released(geometry, 12, -60.0, 20);
                for _ in 0..frames {
                    carousel.tick(16, COUNT);
                }
                assert!(carousel.is_animating());
                let shown = carousel.position();
                carousel.down(2, (300.0, 600.0), 900);
                assert_eq!(carousel.position(), shown);
                assert!(!carousel.tick(16, COUNT), "a held finger stops the motion");
                assert_eq!(carousel.position(), shown);
                let reference = shown.round() as usize;
                let before = center(&carousel, reference);
                carousel.motion(2, (310.0, 600.0), 916, COUNT);
                assert!((center(&carousel, reference) - before - 10.0).abs() < 1e-6);
            }
        }
    }
}

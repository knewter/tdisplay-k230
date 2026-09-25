//! Home screen grid/dock geometry and hit-testing: pure layout functions in
//! the same style as `navigation.rs`'s drawer tile math, sized for a
//! webOS/Android/iOS-style rounded icon tile plus label, at a size and
//! spacing this panel and a finger can actually use comfortably (finding:
//! the first cut's 60px icons/138px rows left most of a 1232px-tall panel
//! blank -- see `docs/design/home-screen-polish.md` if that file exists, or
//! this module's own doc history otherwise).

/// Icons per row. This panel's 568x1232 aspect ratio (568:1232, about
/// 1:2.17) is close to a typical modern phone screen's, so this keeps the
/// same 4-column density most phone launchers settle on at that shape --
/// narrower than the drawer's 3-column list (which devotes most of a row's
/// width to a name label) because a Home tile is icon-first.
pub const COLUMNS: usize = 4;
/// Fixed quick-launch dock slots (webOS Quick Launch / Android hotseat
/// convention): a small, unscrolled row. Deliberately equal to `COLUMNS` so
/// dock icons line up under their grid columns, exactly like every
/// reference launcher's dock/hotseat does.
pub const DOCK_SLOTS: usize = 4;

const SIDE_MARGIN: f64 = 22.0;
const TILE_GAP: f64 = 18.0;

/// Vertical pitch of one grid row (icon plate + label + generous margin).
/// Fixed, not derived from a target row count at every call: a
/// degenerate/non-reference panel height should get *some* whole number of
/// rows at this same tile pitch rather than silently re-flowing to a
/// different tile size. At this panel's actual 1232px height it works out
/// to exactly 5 rows (`rows_per_page`): combined with `COLUMNS`, one page
/// holds 20 icons and the dock holds 4 more -- 24 icons resident at once,
/// matching `icon.rs::CACHE_LIMIT` exactly, so a fully populated Home page
/// plus its dock never evicts and re-decodes an icon mid-frame. 5 rows (not
/// 6) is also what leaves room for ~80-90px icon tiles with genuine
/// breathing room in the vertical space this panel's height actually has
/// once the top inset, page dots, and dock are reserved.
const ROW_HEIGHT: f64 = 184.0;
/// The compositor's own top-edge gesture band (`card-shell-policy.c`'s
/// default `edge_band = 48`): under `SWAY_K230_CARD_TOUCH_FIRST` (set for
/// every real session, see `nix/shell.nix`), a fresh touch-down with
/// `y < EDGE_BAND` is consumed by the shell's own pull-down-for-shade
/// gesture and never reaches this client at all -- confirmed against a real
/// compositor via headless QEMU touch injection, not inferred. Nothing
/// tappable by a *plain tap* may start above this line, though a drag whose
/// down started lower (e.g. rearranging an icon into the Remove pill) can
/// still cross into it, since ownership of an in-progress touch is decided
/// once, at its down point.
const EDGE_BAND: f64 = 48.0;
/// Rearrange mode's Done/Remove pills sit just below `EDGE_BAND`, with a
/// small margin so this stays correct even if the compositor's edge band
/// ever shifts by a pixel or two.
const PILL_TOP: f64 = EDGE_BAND + 4.0;
/// Finger-sized: 56px, matching the touch-target minimum every other
/// surface in this shell uses.
const PILL_HEIGHT: f64 = 56.0;
/// Space reserved above the grid for Home's own (minimal, non-interactive)
/// top inset and, only while rearranging, the Done/Remove pills -- which
/// must clear `EDGE_BAND` (above) to be reachable by a plain tap, plus a
/// small gap before the grid's own first row.
const GRID_TOP: f64 = PILL_TOP + PILL_HEIGHT + 12.0;
/// Height of the non-tappable page-dot row directly above the dock.
const DOTS_HEIGHT: f64 = 34.0;

/// Grid icon glyph size: comfortably inside the 72-96px "sized for a
/// finger" band this redesign targets, small enough that its rounded plate
/// (see `ICON_PLATE_SIZE`) still fits one grid column with real margin.
pub const ICON_SIZE: f64 = 80.0;
/// Padding between the icon glyph and its rounded plate's edge on every
/// side -- the plate is not the same size as the glyph so a webOS/iOS-style
/// "squircle" tile is visible even for icons with transparent edges.
const ICON_PLATE_PAD: f64 = 14.0;
pub const ICON_PLATE_SIZE: f64 = ICON_SIZE + ICON_PLATE_PAD * 2.0;
/// Height reserved for one line of the (bold, ellipsized) name label below
/// a grid icon's plate.
const LABEL_HEIGHT: f64 = 20.0;
/// Gap between an icon's plate and its label.
const ICON_LABEL_GAP: f64 = 8.0;

/// Dock icons read as the quick-launch row's own hierarchy step: visibly
/// larger than an ordinary grid icon (webOS Quick Launch and Android's
/// hotseat both do this), and unlabeled -- exactly like every reference
/// launcher's dock, which trades the name label for a bigger icon since a
/// person already knows their own four most-used apps by icon alone.
pub const DOCK_ICON_SIZE: f64 = 88.0;
const DOCK_PLATE_PAD: f64 = 10.0;
pub const DOCK_PLATE_SIZE: f64 = DOCK_ICON_SIZE + DOCK_PLATE_PAD * 2.0;
/// Height of the fixed dock band at the bottom of the panel: the dock
/// plate's own size plus symmetric vertical padding, so the translucent
/// dock panel reads as a deliberate quick-launch tray, not a cramped strip.
const DOCK_VPAD: f64 = 24.0;
const DOCK_HEIGHT: f64 = DOCK_PLATE_SIZE + DOCK_VPAD * 2.0;

/// Visual radius of the small "remove" badge rearrange mode draws at each
/// filled icon's top-left corner (iOS/webOS's jiggle-mode affordance).
pub const REMOVE_BADGE_RADIUS: f64 = 13.0;
/// The badge's actual hit-test radius: noticeably larger than its drawn
/// circle, so this stays a genuinely finger-sized target instead of one a
/// person has to aim a fingertip at precisely.
pub const REMOVE_BADGE_HIT_RADIUS: f64 = 22.0;

pub fn grid_top(_height: u32) -> f64 {
    GRID_TOP
}

pub fn dock_top(height: u32) -> f64 {
    f64::from(height) - DOCK_HEIGHT
}

pub fn dots_center_y(height: u32) -> f64 {
    dock_top(height) - DOTS_HEIGHT / 2.0
}

fn grid_bottom(height: u32) -> f64 {
    dock_top(height) - DOTS_HEIGHT
}

/// How many full tile rows fit in the space between the grid top and the
/// dots/dock band, at `ROW_HEIGHT`'s fixed pitch. Always at least 1, so a
/// degenerate (very short) panel still shows something rather than a
/// zero-capacity page. At this panel's actual 1232px height this is
/// exactly `ROWS` (5); see this module's top doc comment for why 5.
pub fn rows_per_page(height: u32) -> usize {
    let available = (grid_bottom(height) - GRID_TOP).max(0.0);
    ((available / ROW_HEIGHT).floor() as usize).max(1)
}

pub fn apps_per_page(height: u32) -> usize {
    COLUMNS * rows_per_page(height)
}

fn tile_width(width: u32) -> f64 {
    ((f64::from(width) - 2.0 * SIDE_MARGIN - (COLUMNS - 1) as f64 * TILE_GAP) / COLUMNS as f64)
        .max(0.0)
}

/// `slot` is the icon's position *within the current page* (0-based, row
/// major), not its absolute index across every page. This is the tile's
/// outer cell -- used for hit-testing and the rearrange-mode drop-target
/// highlight -- not where its icon plate is actually painted; see
/// [`tile_content`] for that (the plate and label sit centered within this
/// cell, not pinned to its top edge).
pub fn tile_rect(width: u32, height: u32, slot: usize) -> (f64, f64, f64, f64) {
    let w = tile_width(width);
    let column = slot % COLUMNS;
    let row = slot / COLUMNS;
    (
        SIDE_MARGIN + column as f64 * (w + TILE_GAP),
        grid_top(height) + row as f64 * ROW_HEIGHT,
        w,
        ROW_HEIGHT - TILE_GAP,
    )
}

/// Where a grid icon's rounded plate and label actually paint within its
/// tile cell: horizontally centered, and the icon+label block vertically
/// centered in the cell's height rather than pinned to its top edge -- a
/// tile cell is taller than an icon+label needs (see this module's top
/// comment), and top-pinning it is exactly what made the first cut's icons
/// read as "crammed at the top" of an otherwise-empty page.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct TileContent {
    pub plate_x: f64,
    pub plate_y: f64,
    pub plate_size: f64,
    pub label_y: f64,
}

pub fn tile_content(width: u32, height: u32, slot: usize) -> TileContent {
    let (x, y, w, h) = tile_rect(width, height, slot);
    let content_h = ICON_PLATE_SIZE + ICON_LABEL_GAP + LABEL_HEIGHT;
    let top = y + ((h - content_h) / 2.0).max(0.0);
    TileContent {
        plate_x: x + (w - ICON_PLATE_SIZE) / 2.0,
        plate_y: top,
        plate_size: ICON_PLATE_SIZE,
        label_y: top + ICON_PLATE_SIZE + ICON_LABEL_GAP,
    }
}

/// Which in-page slot, if any, a point lands on. `filled` bounds the search
/// to slots that actually hold an icon on this page (a tap past the last
/// filled slot, in an otherwise-valid grid cell, hits nothing).
pub fn slot_at(point: (f64, f64), width: u32, height: u32, filled: usize) -> Option<usize> {
    if !point.0.is_finite() || !point.1.is_finite() {
        return None;
    }
    let per_page = COLUMNS * rows_per_page(height);
    for slot in 0..filled.min(per_page) {
        let (x, y, w, h) = tile_rect(width, height, slot);
        if point.0 >= x && point.0 < x + w && point.1 >= y && point.1 < y + h {
            return Some(slot);
        }
    }
    None
}

fn dock_slot_width(width: u32) -> f64 {
    ((f64::from(width) - 2.0 * SIDE_MARGIN - (DOCK_SLOTS - 1) as f64 * TILE_GAP)
        / DOCK_SLOTS as f64)
        .max(0.0)
}

/// A dock slot's outer cell, spanning the dock band's full height -- unlike
/// the grid, a dock icon has no label, so [`dock_content`]'s plate centers
/// directly within this rect with no separate label allowance.
pub fn dock_rect(width: u32, height: u32, slot: usize) -> (f64, f64, f64, f64) {
    let w = dock_slot_width(width);
    (
        SIDE_MARGIN + slot as f64 * (w + TILE_GAP),
        dock_top(height),
        w,
        DOCK_HEIGHT,
    )
}

/// Where a dock icon's rounded plate actually paints: centered in its cell,
/// at [`DOCK_PLATE_SIZE`] -- visibly larger than a grid tile's plate, since
/// dock icons are meant to read as the quick-launch row's own hierarchy
/// step (see this module's `DOCK_ICON_SIZE` doc comment).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DockContent {
    pub plate_x: f64,
    pub plate_y: f64,
    pub plate_size: f64,
}

pub fn dock_content(width: u32, height: u32, slot: usize) -> DockContent {
    let (x, y, w, h) = dock_rect(width, height, slot);
    DockContent {
        plate_x: x + (w - DOCK_PLATE_SIZE) / 2.0,
        plate_y: y + (h - DOCK_PLATE_SIZE) / 2.0,
        plate_size: DOCK_PLATE_SIZE,
    }
}

pub fn dock_slot_at(point: (f64, f64), width: u32, height: u32) -> Option<usize> {
    if !point.0.is_finite() || !point.1.is_finite() {
        return None;
    }
    for slot in 0..DOCK_SLOTS {
        let (x, y, w, h) = dock_rect(width, height, slot);
        if point.0 >= x && point.0 < x + w && point.1 >= y && point.1 < y + h {
            return Some(slot);
        }
    }
    None
}

/// A location a pinned icon can occupy: a grid slot on a specific page, or a
/// dock slot (page-independent). Used both by hit-testing (where did this
/// touch land) and by rearrange-mode drop targets (where should this icon
/// go).
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum HomeSlot {
    Grid { page: usize, slot: usize },
    Dock { slot: usize },
}

/// The top-left corner of `slot`'s icon plate -- where rearrange mode draws
/// (and hit-tests) that icon's remove badge. Grid and dock plates have
/// different sizes/positions ([`tile_content`] vs [`dock_content`]), but
/// both anchor their badge at exactly this corner, matching iOS/webOS.
pub fn plate_top_left(width: u32, height: u32, slot: HomeSlot) -> (f64, f64) {
    match slot {
        HomeSlot::Grid { slot, .. } => {
            let content = tile_content(width, height, slot);
            (content.plate_x, content.plate_y)
        }
        HomeSlot::Dock { slot } => {
            let content = dock_content(width, height, slot);
            (content.plate_x, content.plate_y)
        }
    }
}

/// Whether `point` falls within `radius` of `center` -- used for the round
/// remove-badge hit test (a circular target reads more naturally against a
/// round badge than a bounding box would).
pub fn hits_circle(point: (f64, f64), center: (f64, f64), radius: f64) -> bool {
    if !point.0.is_finite() || !point.1.is_finite() {
        return false;
    }
    let dx = point.0 - center.0;
    let dy = point.1 - center.1;
    dx * dx + dy * dy <= radius * radius
}

/// Rearrange mode's contextual "Done" affordance: a finger-sized pill in
/// the top inset band, clear of the compositor's own top-edge gesture band
/// (`EDGE_BAND`) so a plain tap actually reaches it -- not permanent
/// chrome, it only exists while rearranging.
pub fn done_button_rect(width: u32) -> (f64, f64, f64, f64) {
    let w = 128.0;
    (f64::from(width) - SIDE_MARGIN - w, PILL_TOP, w, PILL_HEIGHT)
}

/// Rearrange mode's remove target, alongside the Done pill, in the same top
/// inset band so it never overlaps a grid row. Dragging an icon here is the
/// original remove gesture; the per-icon remove badge ([`plate_top_left`])
/// is the newer, more discoverable one -- both stay live at once.
pub fn remove_target_rect(_width: u32) -> (f64, f64, f64, f64) {
    (SIDE_MARGIN, PILL_TOP, 128.0, PILL_HEIGHT)
}

pub fn hits(point: (f64, f64), rect: (f64, f64, f64, f64)) -> bool {
    point.0.is_finite()
        && point.1.is_finite()
        && point.0 >= rect.0
        && point.0 < rect.0 + rect.2
        && point.1 >= rect.1
        && point.1 < rect.1 + rect.3
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn four_columns_hit_only_painted_tiles() {
        for slot in 0..7 {
            let (x, y, w, h) = tile_rect(568, 1232, slot);
            assert!(w >= 56.0 && h >= 56.0, "tile must clear the 56px touch target");
            assert_eq!(slot_at((x + w / 2.0, y + h / 2.0), 568, 1232, 7), Some(slot));
        }
        assert_eq!(slot_at((0.0, 0.0), 568, 1232, 7), None, "above the grid");
        let (x, y, w, _) = tile_rect(568, 1232, 6);
        assert_eq!(
            slot_at((x + w + 5.0, y + 5.0), 568, 1232, 7),
            None,
            "column gap between rows"
        );
    }

    #[test]
    fn slot_at_respects_filled_bound() {
        let (x, y, w, h) = tile_rect(568, 1232, 3);
        assert_eq!(slot_at((x + w / 2.0, y + h / 2.0), 568, 1232, 3), None, "slot 3 is unfilled");
        assert_eq!(slot_at((x + w / 2.0, y + h / 2.0), 568, 1232, 4), Some(3));
    }

    #[test]
    fn rows_per_page_is_bounded_and_targets_five_at_the_reference_height() {
        assert_eq!(rows_per_page(1232), 5, "one page + dock should total 24 icons, see top doc comment");
        assert_eq!(apps_per_page(1232), COLUMNS * 5);
        assert!(rows_per_page(50) >= 1, "a degenerate panel still has one row");
    }

    #[test]
    fn one_page_plus_dock_matches_the_icon_cache_bound() {
        // icon.rs::CACHE_LIMIT is 24; a fully populated page (apps_per_page)
        // plus a full dock (DOCK_SLOTS) must never exceed it, or a full
        // Home page would evict and re-decode an icon every frame.
        assert_eq!(apps_per_page(1232) + DOCK_SLOTS, 24);
    }

    #[test]
    fn icon_sizes_are_in_the_finger_sized_band() {
        assert!((72.0..=96.0).contains(&ICON_SIZE));
        assert!((72.0..=96.0).contains(&DOCK_ICON_SIZE));
        assert!(DOCK_ICON_SIZE > ICON_SIZE, "the dock reads as a distinct, larger hierarchy step");
    }

    #[test]
    fn tile_content_centers_the_plate_in_its_cell_not_at_the_top() {
        let (_, cell_y, _, cell_h) = tile_rect(568, 1232, 0);
        let content = tile_content(568, 1232, 0);
        assert!(content.plate_x > 0.0);
        assert!(content.plate_y > cell_y, "the plate must not be pinned to the cell's top edge");
        assert!(content.label_y > content.plate_y + content.plate_size);
        assert!(content.label_y + LABEL_HEIGHT < cell_y + cell_h, "label stays inside its own cell");
        assert_eq!(content.plate_size, ICON_PLATE_SIZE);
    }

    #[test]
    fn dock_content_centers_a_larger_plate_with_no_label_allowance() {
        let (_, cell_y, _, cell_h) = dock_rect(568, 1232, 0);
        let content = dock_content(568, 1232, 0);
        assert_eq!(content.plate_size, DOCK_PLATE_SIZE);
        assert!(content.plate_y > cell_y && content.plate_y + content.plate_size < cell_y + cell_h);
    }

    #[test]
    fn dock_slots_are_touch_sized_and_distinct() {
        for slot in 0..DOCK_SLOTS {
            let (x, y, w, h) = dock_rect(568, 1232, slot);
            assert!(w >= 56.0 && h >= 56.0);
            assert_eq!(dock_slot_at((x + w / 2.0, y + h / 2.0), 568, 1232), Some(slot));
        }
        let (grid_x, grid_y, _, _) = tile_rect(568, 1232, 0);
        assert_eq!(
            dock_slot_at((grid_x, grid_y), 568, 1232),
            None,
            "grid tiles are not dock hits"
        );
    }

    #[test]
    fn done_and_remove_targets_sit_in_the_top_inset_and_do_not_overlap() {
        let done = done_button_rect(568);
        let remove = remove_target_rect(568);
        assert!(done.3 >= 56.0, "Done clears the 56px touch target");
        assert!(remove.3 >= 56.0, "Remove clears the 56px touch target");
        assert!(done.1 + done.3 <= GRID_TOP, "Done stays above the grid");
        assert!(remove.1 + remove.3 <= GRID_TOP, "Remove stays above the grid");
        assert!(remove.0 + remove.2 <= done.0, "Remove and Done do not overlap");
        assert!(hits((done.0 + 4.0, done.1 + 4.0), done));
        assert!(!hits((done.0 + 4.0, done.1 + 4.0), remove));
    }

    #[test]
    fn done_and_remove_pills_clear_the_compositors_top_edge_gesture_band() {
        // A fresh tap starting at y < EDGE_BAND is consumed by the
        // compositor's own pull-down-for-shade gesture and never reaches
        // this client at all (confirmed against a real compositor via
        // headless QEMU touch injection) -- so a pill a person is meant to
        // *tap* must sit entirely below that line, not just above the grid.
        let done = done_button_rect(568);
        let remove = remove_target_rect(568);
        assert!(done.1 >= EDGE_BAND, "Done must clear the top-edge gesture band");
        assert!(remove.1 >= EDGE_BAND, "Remove must clear the top-edge gesture band");
    }

    #[test]
    fn dock_sits_below_the_grid_and_dots() {
        let grid_bottom_edge = tile_rect(568, 1232, (rows_per_page(1232) - 1) * COLUMNS).1
            + tile_rect(568, 1232, 0).3;
        assert!(dots_center_y(1232) >= grid_bottom_edge);
        assert!(dock_top(1232) > dots_center_y(1232));
    }

    #[test]
    fn remove_badge_sits_at_the_plates_own_corner_and_hit_radius_exceeds_visual_radius() {
        assert!(REMOVE_BADGE_HIT_RADIUS > REMOVE_BADGE_RADIUS);
        let slot = HomeSlot::Grid { page: 0, slot: 0 };
        let (bx, by) = plate_top_left(568, 1232, slot);
        let content = tile_content(568, 1232, 0);
        assert_eq!((bx, by), (content.plate_x, content.plate_y));
        assert!(hits_circle((bx + 5.0, by + 5.0), (bx, by), REMOVE_BADGE_HIT_RADIUS));
        assert!(!hits_circle((bx + 200.0, by), (bx, by), REMOVE_BADGE_HIT_RADIUS));
    }

    #[test]
    fn adjacent_remove_badges_do_not_overlap_each_other() {
        let (x0, y0) = plate_top_left(568, 1232, HomeSlot::Grid { page: 0, slot: 0 });
        let (x1, y1) = plate_top_left(568, 1232, HomeSlot::Grid { page: 0, slot: 1 });
        let dx = x1 - x0;
        let dy = y1 - y0;
        let distance = (dx * dx + dy * dy).sqrt();
        assert!(distance > 2.0 * REMOVE_BADGE_HIT_RADIUS, "neighboring badges must not overlap");
    }
}

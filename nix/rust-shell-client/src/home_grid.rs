//! Home screen grid/dock geometry and hit-testing: pure layout functions in
//! the same style as `navigation.rs`'s drawer tile math, sized for a
//! webOS/Android-style icon-plus-label tile instead of the drawer's wider
//! list row.

/// Icons per row. Chosen narrower than the drawer's 3-column list (which
/// devotes most of a row's width to a name label) because a Home tile is
/// icon-first: a 4-column grid at this panel's 568px width still keeps each
/// tile comfortably above the 56px touch-target minimum every other surface
/// in this shell uses.
pub const COLUMNS: usize = 4;
/// Fixed quick-launch dock slots (webOS Quick Launch / Android hotseat
/// convention): a small, unscrolled row, sized the same as one grid column
/// so dock and grid icons read as the same visual language.
pub const DOCK_SLOTS: usize = 4;

const SIDE_MARGIN: f64 = 20.0;
const TILE_GAP: f64 = 10.0;
/// Vertical pitch of one grid row (icon plate + label + breathing room).
const ROW_HEIGHT: f64 = 138.0;
/// Space reserved above the grid for Home's own (minimal, non-interactive)
/// top inset -- no title chrome, unlike the drawer/shade/settings panels,
/// since Home's whole point is to show the wallpaper.
const GRID_TOP: f64 = 72.0;
/// Height of the non-tappable page-dot row directly above the dock.
const DOTS_HEIGHT: f64 = 40.0;
/// Height of the fixed dock band at the bottom of the panel.
const DOCK_HEIGHT: f64 = 148.0;

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
/// dots/dock band. Always at least 1, so a degenerate (very short) panel
/// still shows something rather than a zero-capacity page.
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
/// major), not its absolute index across every page.
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

pub fn dock_rect(width: u32, height: u32, slot: usize) -> (f64, f64, f64, f64) {
    let w = dock_slot_width(width);
    (
        SIDE_MARGIN + slot as f64 * (w + TILE_GAP),
        dock_top(height) + 18.0,
        w,
        DOCK_HEIGHT - 36.0,
    )
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

/// Rearrange mode's contextual "Done" affordance: a small pill in the top
/// inset band, not permanent chrome (it only exists while rearranging).
pub fn done_button_rect(width: u32) -> (f64, f64, f64, f64) {
    let w = 108.0;
    (f64::from(width) - SIDE_MARGIN - w, 16.0, w, GRID_TOP - 28.0)
}

/// Rearrange mode's remove target, alongside the Done pill, in the same top
/// inset band so it never overlaps a grid row.
pub fn remove_target_rect(_width: u32) -> (f64, f64, f64, f64) {
    (SIDE_MARGIN, 16.0, 108.0, GRID_TOP - 28.0)
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
    fn rows_per_page_is_bounded_and_never_zero() {
        assert!(rows_per_page(1232) >= 1);
        assert!(rows_per_page(1232) <= 8);
        assert_eq!(apps_per_page(1232), COLUMNS * rows_per_page(1232));
        assert!(rows_per_page(50) >= 1, "a degenerate panel still has one row");
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
        assert!(done.1 + done.3 <= GRID_TOP, "Done stays above the grid");
        assert!(remove.1 + remove.3 <= GRID_TOP, "Remove stays above the grid");
        assert!(remove.0 + remove.2 <= done.0, "Remove and Done do not overlap");
        assert!(hits((done.0 + 4.0, done.1 + 4.0), done));
        assert!(!hits((done.0 + 4.0, done.1 + 4.0), remove));
    }

    #[test]
    fn dock_sits_below_the_grid_and_dots() {
        let grid_bottom_edge = tile_rect(568, 1232, (rows_per_page(1232) - 1) * COLUMNS).1
            + tile_rect(568, 1232, 0).3;
        assert!(dots_center_y(1232) >= grid_bottom_edge);
        assert!(dock_top(1232) > dots_center_y(1232));
    }
}

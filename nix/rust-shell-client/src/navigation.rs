//! Touch and pointer drawer navigation. The compositor reveals the panel; these
//! gestures begin only after the drawer owns a settled input region.

/// `docs/design/app-drawer-review.md`'s redesign: a 4-column grid, closer
/// to the Pixel launcher's own drawer on this panel's width (568px) than
/// the previous 3 columns. `SIDE_MARGIN` and `TILE_GAP` are deliberately
/// equal (both 24px) so the whole row reads as one evenly-spaced strip --
/// margin, gap, gap, gap, margin -- rather than a tighter inter-column gap
/// inside a wider outer border. At this width that divides out exactly:
/// `2*24 + 3*24 + 4*112 = 568`, so the grid is centered with no remainder
/// and no separate centering offset to compute.
pub const COLUMNS: usize = 4;

/// How many drawer grid columns fit `width`: `crate::reflow_columns` at
/// scale `1.0` -- more columns of this module's own 112px reference tile
/// width on a wider (HDMI) output, instead of `COLUMNS` staying fixed at 4
/// and each cell stretching into a wide, sparse tile (`feat/shell-
/// responsive`: the operator did not want an HDMI output's drawer to just
/// have four huge tiles). Scale is fixed at `1.0` here rather than `crate::
/// density_scale`'s own value on purpose: a grid's extra width should
/// become more cells, not bigger ones -- see `reflow_columns`'s own doc.
/// Pure and stateless -- unlike `home_grid`'s per-page layout, the drawer
/// has no persisted per-column data to keep in sync, only this live tile
/// geometry and the matching `tile_at` hit-test, both of which call this on
/// every use.
pub fn columns_for_width(width: u32) -> usize {
    crate::reflow_columns(width, 1.0, COLUMNS)
}
/// The cell's full vertical pitch: an icon, a small gap, a single-line
/// label, and the row's own share of vertical breathing room -- see
/// `render.rs`'s Drawer paint block for the exact split. Also `tile_at`'s
/// per-row tap-target height (the whole cell is tappable, not just the
/// icon).
pub const ROW_HEIGHT: f64 = 110.0;
pub const TILE_HEIGHT: f64 = ROW_HEIGHT;
/// A small safe-bottom margin now that the old "Swipe down to return to
/// cards" footer caption (which this space used to reserve room for) is
/// gone -- see `docs/design/app-drawer-review.md` §2. Kept as its own
/// named constant (not folded into a literal) because `tile_at`,
/// `max_scroll` and `service_ui::drawer_close_drag_zone` all need to agree
/// on exactly where the grid's own bottom edge is.
pub const GRID_BOTTOM_INSET: f64 = 24.0;
const TILE_GAP: f64 = 24.0;
const SIDE_MARGIN: f64 = 24.0;

/// The sheet's own top inset from the very edge of the screen -- a small
/// gap, not the old ~19%-of-height band, so the sheet fills nearly the
/// whole panel once open (`docs/design/app-drawer-review.md` §2: "filling
/// the screen from the top inset, with no black band above it"). Fixed in
/// pixels, not proportional to `height`, like this module's other
/// geometry constants -- this panel's physical size never changes.
pub fn panel_top(_height: u32) -> f64 {
    32.0
}

/// Height of the fixed top chrome below `panel_top`: the drag handle and
/// the pill-shaped search field, before the scrollable grid begins. See
/// `search_field_rect`/`handle_rect` for the exact split.
const TOP_CHROME_HEIGHT: f64 = 86.0;

pub fn list_top(height: u32) -> f64 {
    panel_top(height) + TOP_CHROME_HEIGHT
}

/// The drawer-drag's Cancel target (task 1: "A Cancel target at the top,
/// or releasing over the drawer area, cancels"): the drawer's own top
/// chrome band (handle + search field). While a long-press-drag is live,
/// the drawer's grid is hidden and Home shows through in its place (see
/// `main.rs`'s drag hand-off doc), so this top band is the one part of the
/// drawer's own surface that still reads as "the drawer" to release back
/// onto.
pub fn drag_cancel_zone_hit(point: (f64, f64), height: u32) -> bool {
    point.1.is_finite() && point.1 < list_top(height)
}

/// The small drag-handle indicator's rect, in absolute screen coordinates.
/// Purely decorative (`render.rs` paints it); the handle's own *hit* zone
/// for drag-to-close is the whole top-chrome band above the grid
/// (`service_ui::drawer_close_drag_zone`), matching Android's own "drag
/// anywhere on the sheet's top chrome to dismiss" convention now that this
/// chrome is compact and entirely interactive (handle + search), unlike
/// the old prose header that convention was narrowed away from.
pub fn handle_rect(width: u32, height: u32) -> (f64, f64, f64, f64) {
    let w = 40.0;
    (f64::from(width) / 2.0 - w / 2.0, panel_top(height) + 10.0, w, 4.0)
}

/// The pill-shaped "Search apps" field's rect, in absolute screen
/// coordinates -- both `render.rs` (painting it) and `service_ui`/`main.rs`
/// (hit-testing a tap to focus it) share this one geometry function.
pub fn search_field_rect(width: u32, height: u32) -> (f64, f64, f64, f64) {
    let x = SIDE_MARGIN;
    let y = panel_top(height) + 22.0;
    let w = f64::from(width) - 2.0 * SIDE_MARGIN;
    let h = 48.0;
    (x, y, w, h)
}

/// Whether `point` lands on the search field (a tap there focuses search
/// and opens the on-screen keyboard; see `main.rs`'s Drawer touch-down
/// handling).
pub fn search_field_hit(point: (f64, f64), width: u32, height: u32) -> bool {
    let (x, y, w, h) = search_field_rect(width, height);
    point.0 >= x && point.0 < x + w && point.1 >= y && point.1 < y + h
}

pub fn tile_rect(width: u32, height: u32, index: usize, scroll: f64) -> (f64, f64, f64, f64) {
    let columns = columns_for_width(width);
    let tile_width = ((f64::from(width) - 2.0 * SIDE_MARGIN - (columns - 1) as f64 * TILE_GAP)
        / columns as f64)
        .max(0.0);
    let column = index % columns;
    let row = index / columns;
    (
        SIDE_MARGIN + column as f64 * (tile_width + TILE_GAP),
        list_top(height) + row as f64 * ROW_HEIGHT - scroll,
        tile_width,
        TILE_HEIGHT,
    )
}

pub fn tile_at(
    point: (f64, f64),
    width: u32,
    height: u32,
    apps: usize,
    scroll: f64,
) -> Option<usize> {
    if !point.0.is_finite()
        || !point.1.is_finite()
        || point.1 < list_top(height)
        || point.1 >= f64::from(height) - GRID_BOTTOM_INSET
    {
        return None;
    }
    let content_y = point.1 + scroll - list_top(height);
    if content_y < 0.0 {
        return None;
    }
    let columns = columns_for_width(width);
    let row = (content_y / ROW_HEIGHT).floor() as usize;
    let first = row.saturating_mul(columns);
    for index in first..first.saturating_add(columns).min(apps) {
        let (x, y, w, h) = tile_rect(width, height, index, scroll);
        if point.0 >= x && point.0 < x + w && point.1 >= y && point.1 < y + h {
            return Some(index);
        }
    }
    None
}

fn max_scroll(width: u32, height: u32, apps: usize) -> f64 {
    let viewport = (f64::from(height) - GRID_BOTTOM_INSET - list_top(height)).max(0.0);
    let grid_rows = apps.div_ceil(columns_for_width(width));
    (grid_rows as f64 * ROW_HEIGHT - TILE_GAP - viewport).max(0.0)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DrawerAction {
    Launch(usize),
    Close,
}

/// A tile held at least this long, without exceeding the existing tap
/// slop/duration-independent gesture, is a long-press rather than a tap --
/// no longer "Add to Home" (removed; see [`DrawerNavigation::
/// take_long_press_drag`]'s own doc for what replaced it), but the same
/// threshold still gates when that drag arms. Matches
/// `home_pager::LONG_PRESS_MS` so a hold feels the same length whether it
/// is dragging from the drawer or rearranging on Home.
pub const LONG_PRESS_MS: u32 = 500;
/// A touch that has not moved past this many pixels from its down point is
/// still a long-press-drag candidate, not a scroll -- matches `up`'s own
/// pre-existing tap-slop literal (12.0), named here since
/// `take_long_press_drag` is new.
const LONG_PRESS_SLOP: f64 = 12.0;

#[derive(Clone, Copy, Debug)]
struct Contact {
    id: i32,
    start: (f64, f64),
    last: (f64, f64),
    start_scroll: f64,
    last_ms: u32,
    down_ms: u32,
    finger_velocity: f64,
    cancelled: bool,
    /// Set once this gesture's own `motion` has actually carried `scroll`
    /// away from the grid's own top (past 0.5px), and never cleared again.
    /// Gates `up`'s own release-only dismiss check below: without this, a
    /// gesture that scrolled down through the list and then reversed --
    /// ending back near the top with a large enough net downward travel
    /// from its *original* touch-down point -- could still read as
    /// "dy > 110 && scroll <= 0.5" and close the Drawer, even though the
    /// grid was never at rest at its top when this same continuous touch
    /// began scrolling away from it. Real scrolling away from the top must
    /// permanently disqualify the rest of that gesture from closing.
    scrolled_away: bool,
    /// Accumulated hold time for [`DrawerNavigation::take_long_press_drag`]
    /// -- independent of `down_ms`/`last_ms`, which are wall-clock touch
    /// timestamps a caller not driving `take_long_press_drag` every tick
    /// can still use for `up`'s own release-time long-press fallback.
    held_ms: u32,
    /// Set once this contact has been resolved by *either*
    /// `take_long_press_drag` (fired) or ordinary motion past tap slop --
    /// prevents re-arming a second drag off the same contact.
    long_fired: bool,
}

#[derive(Default)]
pub struct DrawerNavigation {
    pub scroll: f64,
    velocity: f64,
    contact: Option<Contact>,
}

impl DrawerNavigation {
    pub fn down(&mut self, id: i32, point: (f64, f64), time_ms: u32) -> bool {
        if let Some(contact) = self.contact.as_mut() {
            contact.cancelled = true;
            self.velocity = 0.0;
            return false;
        }
        self.velocity = 0.0; // touching a coasting list stops it immediately
        self.contact = Some(Contact {
            id,
            start: point,
            last: point,
            start_scroll: self.scroll,
            last_ms: time_ms,
            down_ms: time_ms,
            finger_velocity: 0.0,
            cancelled: false,
            scrolled_away: self.scroll > 0.5,
            held_ms: 0,
            long_fired: false,
        });
        true
    }

    pub fn motion(
        &mut self,
        id: i32,
        point: (f64, f64),
        time_ms: u32,
        width: u32,
        height: u32,
        rows: usize,
    ) -> bool {
        let Some(contact) = self.contact.as_mut() else {
            return false;
        };
        if contact.id != id || contact.cancelled || !point.0.is_finite() || !point.1.is_finite() {
            return false;
        }
        let elapsed = time_ms.wrapping_sub(contact.last_ms);
        if elapsed > 0 && elapsed < 1000 {
            contact.finger_velocity =
                ((point.1 - contact.last.1) * 1000.0 / f64::from(elapsed)).clamp(-3000.0, 3000.0);
        }
        contact.last = point;
        contact.last_ms = time_ms;
        let old = self.scroll;
        self.scroll = (contact.start_scroll - (point.1 - contact.start.1))
            .clamp(0.0, max_scroll(width, height, rows));
        if self.scroll > 0.5 {
            contact.scrolled_away = true;
        }
        (self.scroll - old).abs() >= 0.5
    }

    pub fn up(
        &mut self,
        id: i32,
        point: (f64, f64),
        time_ms: u32,
        width: u32,
        height: u32,
        apps: usize,
    ) -> Option<DrawerAction> {
        let contact = self.contact.take()?;
        if contact.id != id || contact.cancelled || !point.0.is_finite() || !point.1.is_finite() {
            self.velocity = 0.0;
            return None;
        }
        let dx = point.0 - contact.start.0;
        let dy = point.1 - contact.start.1;
        if dy > 110.0 && self.scroll <= 0.5 && !contact.scrolled_away {
            self.velocity = 0.0;
            return Some(DrawerAction::Close);
        }
        if dx.abs() <= 12.0 && dy.abs() <= 12.0 {
            let held_ms = time_ms.wrapping_sub(contact.down_ms);
            // A release this stationary but past `LONG_PRESS_MS` normally
            // never reaches here at all: `take_long_press_drag`, driven by
            // the caller's own tick loop, already fired and took
            // `self.contact` well before the finger lifted (see that
            // method's own doc), so `up` sees no contact and returns `None`
            // above. This `held_ms` guard only matters if a caller never
            // ticks this navigation model between `down` and `up` (e.g. a
            // host test driving `up` directly with no `tick` in between) --
            // in that case a long, stationary hold now resolves to nothing
            // rather than an old "Add to Home" pin, matching the drag-based
            // replacement's own resolution (nothing is placed until a drop).
            if held_ms < LONG_PRESS_MS {
                if let Some(index) = tile_at(point, width, height, apps, self.scroll) {
                    if tile_at(contact.start, width, height, apps, contact.start_scroll) == Some(index) {
                        return Some(DrawerAction::Launch(index));
                    }
                }
            }
        }
        if dy.abs() > 12.0 && time_ms.wrapping_sub(contact.last_ms) <= 100 {
            self.velocity = -contact.finger_velocity;
        }
        None
    }

    pub fn tick(&mut self, elapsed_ms: u32, width: u32, height: u32, rows: usize) -> bool {
        if self.contact.is_some() || self.velocity.abs() < 20.0 || elapsed_ms == 0 {
            return false;
        }
        let elapsed = elapsed_ms.min(50);
        let old = self.scroll;
        self.scroll = (self.scroll + self.velocity * f64::from(elapsed) / 1000.0)
            .clamp(0.0, max_scroll(width, height, rows));
        self.velocity *= 0.88_f64.powf(f64::from(elapsed) / 16.0);
        if self.scroll == old || self.velocity.abs() < 20.0 {
            self.velocity = 0.0;
        }
        (self.scroll - old).abs() >= 0.5
    }

    /// Wheel streams own their momentum; never keep an old touch fling running.
    pub fn scroll_by(&mut self, delta: f64, width: u32, height: u32, apps: usize) -> bool {
        if self.contact.is_some() || !delta.is_finite() { return false; }
        self.velocity = 0.0;
        let old = self.scroll;
        self.scroll = (old + delta).clamp(0.0, max_scroll(width, height, apps));
        self.scroll != old
    }

    pub fn coasting(&self) -> bool {
        self.velocity.abs() >= 20.0
    }

    /// Fires once, at `LONG_PRESS_MS`, with the *display* index of the tile
    /// a stationary touch is resting on -- task 1's "Long-press an app in
    /// the drawer, and the drawer immediately slides or fades away to
    /// reveal Home. The icon lifts and follows the finger", replacing the
    /// old release-only "Add to Home" pin. Driven by the caller's own tick
    /// loop (mirroring `home_screen::HomeScreen::tick`'s identical
    /// long-press timer) rather than detected at release, so the caller can
    /// begin a live drag (reveal Home, start following the finger) well
    /// before the finger lifts.
    ///
    /// Consumes this contact entirely once it fires (`self.contact` is set
    /// to `None`): the rest of this gesture is now owned by whatever the
    /// caller does with the returned index (typically
    /// `home_screen::HomeScreen::begin_external_drag`), not by this
    /// navigation model, so `motion`/`up` calls for the same touch id that
    /// follow are simply no-ops here (both already start with `let
    /// Some(contact) = ... else { return ... }`).
    ///
    /// A real drag/scroll preempts this exactly like the old release-time
    /// check did (past `LONG_PRESS_SLOP`), and firing requires the touch to
    /// have started on an actual tile, not empty space below the grid.
    ///
    /// Returns the tile's display index *and* the touch's own current
    /// point (its live position may already have moved up to
    /// `LONG_PRESS_SLOP` pixels from `down`) -- the caller passes that
    /// point straight into `home_screen::HomeScreen::begin_external_drag`
    /// so the lifted icon starts exactly where the finger already is,
    /// rather than snapping from the original touch-down point.
    pub fn take_long_press_drag(&mut self, elapsed_ms: u32, width: u32, height: u32, apps: usize) -> Option<(usize, (f64, f64))> {
        let contact = self.contact.as_mut()?;
        if contact.cancelled || contact.long_fired {
            return None;
        }
        if (contact.last.0 - contact.start.0).abs() > LONG_PRESS_SLOP
            || (contact.last.1 - contact.start.1).abs() > LONG_PRESS_SLOP
        {
            contact.long_fired = true; // a real scroll/close-drag preempts this
            return None;
        }
        contact.held_ms = contact.held_ms.saturating_add(elapsed_ms);
        if contact.held_ms < LONG_PRESS_MS {
            return None;
        }
        contact.long_fired = true;
        let index = tile_at(contact.start, width, height, apps, contact.start_scroll)?;
        let point = contact.last;
        self.contact = None;
        self.velocity = 0.0;
        Some((index, point))
    }

    pub fn pressed(&self, width: u32, height: u32, apps: usize) -> Option<usize> {
        let contact = self.contact.as_ref()?;
        if contact.cancelled
            || (contact.last.0 - contact.start.0).abs() > 12.0
            || (contact.last.1 - contact.start.1).abs() > 12.0
        {
            return None;
        }
        let start = tile_at(contact.start, width, height, apps, contact.start_scroll)?;
        (tile_at(contact.last, width, height, apps, self.scroll) == Some(start)).then_some(start)
    }

    pub fn cancel(&mut self) {
        self.contact = None;
        self.velocity = 0.0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tap(nav: &mut DrawerNavigation, point: (f64, f64), apps: usize) -> Option<DrawerAction> {
        assert!(nav.down(1, point, 10));
        nav.up(1, point, 30, 568, 1232, apps)
    }

    #[test]
    fn four_columns_hit_only_painted_tiles() {
        let mut nav = DrawerNavigation::default();
        for index in 0..7 {
            let (x, y, w, h) = tile_rect(568, 1232, index, 0.0);
            assert!(w >= 56.0 && h >= 56.0);
            assert_eq!(
                tap(&mut nav, (x + w / 2.0, y + h / 2.0), 7),
                Some(DrawerAction::Launch(index))
            );
        }
        let top = list_top(1232);
        // Computed from the real tile geometry rather than hand-picked
        // literals, so this stays correct across a column-count/margin
        // change instead of silently testing stale positions.
        let (tile0_x, _, tile0_w, _) = tile_rect(568, 1232, 0, 0.0);
        let (tile1_x, _, _, _) = tile_rect(568, 1232, 1, 0.0);
        let gap_x = (tile0_x + tile0_w + tile1_x) / 2.0;
        assert_eq!(
            tap(&mut nav, (gap_x, top + 30.0), 7),
            None,
            "column gap"
        );
        // Index 7 is beyond the 7-app catalog -- an unpainted slot in an
        // otherwise-populated row.
        let (empty_x, empty_y, empty_w, empty_h) = tile_rect(568, 1232, 7, 0.0);
        assert_eq!(
            tap(&mut nav, (empty_x + empty_w / 2.0, empty_y + empty_h / 2.0), 7),
            None,
            "empty eighth tile"
        );
        assert_eq!(
            tap(&mut nav, (100.0, top - 1.0), 7),
            None,
            "header is not a tile"
        );
        nav.down(2, (gap_x, top + 40.0), 50);
        assert_eq!(
            nav.up(2, (gap_x + 9.0, top + 40.0), 70, 568, 1232, 7),
            None,
            "gap-to-tile is not a tap"
        );
        nav.down(3, (100.0, top - 5.0), 80);
        assert_eq!(
            nav.up(3, (100.0, top + 5.0), 100, 568, 1232, 7),
            None,
            "header-to-tile is not a tap"
        );
        let (x, y, w, _) = tile_rect(568, 1232, 0, 0.0);
        nav.down(4, (x + w - 1.0, y + 40.0), 110);
        assert_eq!(
            nav.up(4, (x + w + 13.0, y + 40.0), 130, 568, 1232, 7),
            None,
            "tile-to-neighbor is not a tap"
        );
    }

    #[test]
    fn columns_for_width_reflows_wider_hdmi_outputs_but_never_shrinks() {
        // Exactly 4 at this panel's own design width -- pixel-identical to
        // today (`configure_preserves_aspect`'s own design band).
        assert_eq!(columns_for_width(568), COLUMNS);
        // Never fewer than the design's own 4, even below 568 (a configure
        // this narrow is already rejected before reaching here -- see
        // `lib.rs`'s `configure_size`/`configure_preserves_aspect` -- but
        // this stays a safe floor regardless).
        assert_eq!(columns_for_width(300), COLUMNS);
        // Wider (HDMI) outputs: this change's own capture evidence sizes,
        // `feat/shell-responsive`'s reflow instead of `feat/hdmi-pillarbox`'s
        // now-removed centered column.
        assert_eq!(columns_for_width(768), 5);
        assert_eq!(columns_for_width(1080), 8);
        assert_eq!(columns_for_width(1920), 14);
        // Monotonic: strictly wider never yields fewer columns.
        assert!(columns_for_width(1920) >= columns_for_width(1080));
        assert!(columns_for_width(1080) >= columns_for_width(768));
    }

    #[test]
    fn wide_hdmi_output_hits_every_reflowed_column_of_the_first_row() {
        // 1920x1080 landscape HDMI: `columns_for_width(1920)` columns
        // reflow into the same first row instead of 4 wide, sparse tiles.
        let width = 1920u32;
        let height = 1080u32;
        let columns = columns_for_width(width);
        assert!(columns > COLUMNS, "a wide output must gain columns, not just wider tiles");
        let mut nav = DrawerNavigation::default();
        for index in 0..columns {
            let (x, y, w, h) = tile_rect(width, height, index, 0.0);
            assert!(w > 0.0 && h > 0.0);
            assert!(x + w <= f64::from(width), "tile {index} must stay on-panel");
            assert!(nav.down(1, (x + w / 2.0, y + h / 2.0), 10));
            assert_eq!(
                nav.up(1, (x + w / 2.0, y + h / 2.0), 30, width, height, columns),
                Some(DrawerAction::Launch(index))
            );
        }
    }

    #[test]
    fn scrolled_grid_maps_row_and_clips_bottom() {
        let mut nav = DrawerNavigation {
            scroll: 160.0,
            ..DrawerNavigation::default()
        };
        let top = list_top(1232);
        // x=200 lands in column 1 of the 4-column grid (col0 [24,136),
        // col1 [160,272), col2 [296,408), col3 [432,544)); row 1 (content_y
        // 190 / ROW_HEIGHT 110 = 1) starts at index 4, so column 1 is
        // index 5.
        assert_eq!(
            tap(&mut nav, (200.0, top + 30.0), 60),
            Some(DrawerAction::Launch(5))
        );
        assert_eq!(
            tap(&mut nav, (200.0, 1210.0), 60),
            None,
            "footer is outside the grid"
        );
        assert_eq!(max_scroll(568, 1232, 7), 0.0);
        // 60 apps (15 rows) actually overflows this panel's viewport at the
        // new, shorter 110px row pitch -- 30 no longer does.
        assert!(max_scroll(568, 1232, 60) > 0.0);
    }

    #[test]
    fn pressed_clears_on_drag_second_finger_and_cancel() {
        let mut nav = DrawerNavigation::default();
        let (x, y, w, h) = tile_rect(568, 1232, 1, 0.0);
        let p = (x + w / 2.0, y + h / 2.0);
        nav.down(1, p, 0);
        assert_eq!(nav.pressed(568, 1232, 7), Some(1));
        nav.motion(1, (p.0, p.1 - 40.0), 20, 568, 1232, 30);
        assert_eq!(nav.pressed(568, 1232, 30), None);
        nav.cancel();
        nav.down(2, p, 30);
        assert!(!nav.down(3, p, 31));
        assert_eq!(nav.pressed(568, 1232, 7), None);
        assert_eq!(nav.up(2, p, 40, 568, 1232, 7), None);
    }

    #[test]
    fn drag_follows_reverses_and_flick_stops_on_new_contact() {
        let mut nav = DrawerNavigation::default();
        // 60 apps (15 rows) actually overflows the viewport at the new,
        // shorter 110px row pitch -- 30 no longer does, so this drag would
        // otherwise clamp at 0 the whole time.
        let apps = 60;
        let top = list_top(1232);
        nav.down(1, (120.0, top + 180.0), 0);
        assert!(nav.motion(1, (120.0, top + 80.0), 25, 568, 1232, apps));
        assert_eq!(nav.scroll, 100.0);
        assert!(nav.motion(1, (120.0, top + 100.0), 40, 568, 1232, apps));
        assert_eq!(nav.scroll, 80.0);
        assert_eq!(nav.up(1, (120.0, top + 100.0), 41, 568, 1232, apps), None);
        assert!(nav.coasting());
        nav.down(2, (120.0, top + 100.0), 50);
        assert!(!nav.coasting());
        nav.cancel();
        nav.down(3, (120.0, top + 180.0), 100);
        nav.motion(3, (120.0, top + 80.0), 125, 568, 1232, apps);
        nav.up(3, (120.0, top + 80.0), 400, 568, 1232, apps);
        assert!(
            !nav.coasting(),
            "held finger cannot reuse old flick velocity"
        );
    }

    #[test]
    fn a_held_tile_release_with_no_ticking_now_resolves_to_nothing() {
        // Long-press-to-pin is gone; without a caller driving
        // `take_long_press_drag` (see the test below for that path), a
        // long stationary hold simply does nothing on release.
        let mut nav = DrawerNavigation::default();
        let (x, y, w, h) = tile_rect(568, 1232, 2, 0.0);
        let point = (x + w / 2.0, y + h / 2.0);
        assert!(nav.down(1, point, 0));
        assert_eq!(nav.up(1, point, LONG_PRESS_MS, 568, 1232, 7), None);
    }

    #[test]
    fn take_long_press_drag_fires_once_at_the_threshold_and_consumes_the_contact() {
        let mut nav = DrawerNavigation::default();
        let (x, y, w, h) = tile_rect(568, 1232, 2, 0.0);
        let point = (x + w / 2.0, y + h / 2.0);
        nav.down(1, point, 0);
        assert_eq!(nav.take_long_press_drag(LONG_PRESS_MS - 16, 568, 1232, 7), None, "not yet at the threshold");
        assert_eq!(nav.take_long_press_drag(16, 568, 1232, 7), Some((2, point)), "fires once the threshold is crossed");
        // The contact is now consumed: a second call, and an ordinary
        // `up`/`motion` for the same touch, all see nothing.
        assert_eq!(nav.take_long_press_drag(16, 568, 1232, 7), None);
        assert_eq!(nav.up(1, point, 1000, 568, 1232, 7), None);
    }

    #[test]
    fn moving_past_slop_before_the_threshold_cancels_the_long_press_drag() {
        let mut nav = DrawerNavigation::default();
        let (x, y, w, h) = tile_rect(568, 1232, 2, 0.0);
        let point = (x + w / 2.0, y + h / 2.0);
        nav.down(1, point, 0);
        nav.motion(1, (point.0 + 20.0, point.1), 16, 568, 1232, 7);
        assert_eq!(
            nav.take_long_press_drag(LONG_PRESS_MS, 568, 1232, 7),
            None,
            "a real scroll preempts the long-press drag"
        );
    }

    #[test]
    fn a_quick_tap_still_launches_even_though_it_could_still_be_ticked() {
        let mut nav = DrawerNavigation::default();
        let (x, y, w, h) = tile_rect(568, 1232, 2, 0.0);
        let point = (x + w / 2.0, y + h / 2.0);
        nav.down(1, point, 0);
        assert_eq!(nav.take_long_press_drag(LONG_PRESS_MS - 100, 568, 1232, 7), None);
        assert_eq!(
            nav.up(1, point, LONG_PRESS_MS - 1, 568, 1232, 7),
            Some(DrawerAction::Launch(2))
        );
    }

    #[test]
    fn drag_cancel_zone_is_the_drawers_own_top_chrome_band() {
        let height = 1232;
        assert!(drag_cancel_zone_hit((100.0, 10.0), height));
        assert!(!drag_cancel_zone_hit((100.0, list_top(height) + 5.0), height));
    }

    #[test]
    fn a_quick_tap_still_launches() {
        let mut nav = DrawerNavigation::default();
        let (x, y, w, h) = tile_rect(568, 1232, 2, 0.0);
        let point = (x + w / 2.0, y + h / 2.0);
        assert!(nav.down(1, point, 0));
        assert_eq!(
            nav.up(1, point, LONG_PRESS_MS - 1, 568, 1232, 7),
            Some(DrawerAction::Launch(2))
        );
    }

    #[test]
    fn downward_dismiss_is_distinct_from_app_tap() {
        let mut nav = DrawerNavigation::default();
        let top = list_top(1232);
        nav.down(1, (100.0, top - 30.0), 30);
        nav.motion(1, (100.0, top + 110.0), 80, 568, 1232, 7);
        assert_eq!(
            nav.up(1, (100.0, top + 110.0), 85, 568, 1232, 7),
            Some(DrawerAction::Close)
        );
    }

    /// Reported bug: "when i swipe down in the app drawer to scroll back
    /// up, it closes the drawer". One held touch, starting inside the grid
    /// while it is at its own top: first the finger drags *up* to scroll
    /// down through the list (ordinary scrolling, ends with `scroll`
    /// meaningfully away from 0), then -- without lifting -- reverses and
    /// drags back *down*, all the way past the original touch-down point
    /// (net downward travel from `start` well past the 110px dismiss
    /// threshold, matching a real "scroll back up" swipe). The list must
    /// keep scrolling for the gesture's entire duration; it must never
    /// convert into a close, even though the release point reads as a big
    /// net downward drag and the grid is back at (or near) its own top by
    /// the time the finger lifts.
    #[test]
    fn scrolling_away_from_the_top_then_reversing_never_closes_within_one_gesture() {
        let mut nav = DrawerNavigation::default();
        let apps = 200; // enough rows that 200px of scroll is not already clamped away
        let top = list_top(1232);
        let start = (100.0, top + 10.0);
        assert!(nav.down(1, start, 0));

        // Scroll down through the list: drag up 200px.
        assert!(nav.motion(1, (100.0, top + 10.0 - 200.0), 40, 568, 1232, apps));
        assert!(nav.scroll > 100.0, "actually scrolled away from the top");

        // Now reverse, without lifting, and drag back down past the
        // original start point -- the exact "swipe down to scroll back
        // up" gesture from the bug report.
        assert!(nav.motion(1, (100.0, top + 10.0 + 150.0), 90, 568, 1232, apps));
        // The grid has scrolled back to (or past, and clamped at) its own
        // top by now...
        assert!(nav.scroll <= 0.5, "back at the top after reversing");
        // ...but this must not read as a dismiss on release: the net
        // downward travel from the *original* start point is 150px, past
        // the old unconditional 110px threshold, which is exactly what
        // made the un-fixed release-only check misfire.
        assert_eq!(
            nav.up(1, (100.0, top + 10.0 + 150.0), 95, 568, 1232, apps),
            None,
            "a gesture that scrolled away from the top must never convert into a close"
        );
    }

    /// The same reversal, but starting truly at rest at the top (no prior
    /// scroll in this gesture) and dragging straight down past the
    /// threshold: this is the legitimate dismiss the fix above must not
    /// have broken.
    #[test]
    fn a_straight_downward_drag_from_the_top_still_dismisses() {
        let mut nav = DrawerNavigation::default();
        let top = list_top(1232);
        let start = (100.0, top + 10.0);
        assert!(nav.down(1, start, 0));
        nav.motion(1, (100.0, top + 10.0 + 150.0), 40, 568, 1232, 7);
        assert_eq!(
            nav.up(1, (100.0, top + 10.0 + 150.0), 45, 568, 1232, 7),
            Some(DrawerAction::Close)
        );
    }

    #[test]
    fn search_field_hit_is_bounded_to_its_own_pill_and_above_the_grid() {
        let (x, y, w, h) = search_field_rect(568, 1232);
        assert!(y + h < list_top(1232), "the field sits above the grid");
        assert!(search_field_hit((x + 4.0, y + 4.0), 568, 1232), "inside");
        assert!(
            search_field_hit((x + w - 1.0, y + h - 1.0), 568, 1232),
            "inside, near the far edge"
        );
        assert!(!search_field_hit((x - 1.0, y), 568, 1232), "left of it");
        assert!(!search_field_hit((x, y + h), 568, 1232), "below it");
        assert!(
            !search_field_hit((x, list_top(1232) + 5.0), 568, 1232),
            "inside the grid, not the field"
        );
    }

    #[test]
    fn handle_rect_is_centered_above_the_search_field() {
        let (hx, hy, hw, _) = handle_rect(568, 1232);
        let (_, sy, _, _) = search_field_rect(568, 1232);
        assert!(hy < sy, "the handle sits above the search field");
        assert!(
            (hx + hw / 2.0 - f64::from(568) / 2.0).abs() < 0.01,
            "the handle is horizontally centered"
        );
    }

    #[test]
    fn wheel_bounds_and_touch_ownership() {
        let mut nav = DrawerNavigation::default();
        assert!(nav.scroll_by(100.0, 568, 1232, 100));
        assert_eq!(nav.scroll, 100.0);
        assert!(!nav.scroll_by(f64::NAN, 568, 1232, 100));
        nav.down(1, (200.0, 200.0), 0);
        assert!(!nav.scroll_by(200.0, 568, 1232, 100));
        nav.cancel();
        nav.scroll_by(-10000.0, 568, 1232, 100);
        assert_eq!(nav.scroll, 0.0);
        nav.scroll_by(10000.0, 568, 1232, 100);
        assert_eq!(nav.scroll, max_scroll(568, 1232, 100));
        assert!(!nav.tick(16, 568, 1232, 100));
    }
}

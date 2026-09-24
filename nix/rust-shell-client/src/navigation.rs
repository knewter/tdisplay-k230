//! Touch-only drawer navigation. The compositor reveals the panel; these
//! gestures begin only after the drawer owns a settled input region.

pub const COLUMNS: usize = 3;
pub const TILE_HEIGHT: f64 = 148.0;
pub const ROW_HEIGHT: f64 = 160.0;
pub const GRID_BOTTOM_INSET: f64 = 72.0;
const TILE_GAP: f64 = 12.0;
const SIDE_MARGIN: f64 = 24.0;

pub fn list_top(height: u32) -> f64 {
    f64::from(height) * 0.19 + 181.0
}

pub fn tile_rect(width: u32, height: u32, index: usize, scroll: f64) -> (f64, f64, f64, f64) {
    let tile_width = ((f64::from(width) - 2.0 * SIDE_MARGIN - (COLUMNS - 1) as f64 * TILE_GAP)
        / COLUMNS as f64)
        .max(0.0);
    let column = index % COLUMNS;
    let row = index / COLUMNS;
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
    let row = (content_y / ROW_HEIGHT).floor() as usize;
    let first = row.saturating_mul(COLUMNS);
    for index in first..first.saturating_add(COLUMNS).min(apps) {
        let (x, y, w, h) = tile_rect(width, height, index, scroll);
        if point.0 >= x && point.0 < x + w && point.1 >= y && point.1 < y + h {
            return Some(index);
        }
    }
    None
}

fn max_scroll(height: u32, apps: usize) -> f64 {
    let viewport = (f64::from(height) - GRID_BOTTOM_INSET - list_top(height)).max(0.0);
    let grid_rows = apps.div_ceil(COLUMNS);
    (grid_rows as f64 * ROW_HEIGHT - TILE_GAP - viewport).max(0.0)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DrawerAction {
    Launch(usize),
    Close,
}

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
        });
        true
    }

    pub fn motion(
        &mut self,
        id: i32,
        point: (f64, f64),
        time_ms: u32,
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
            .clamp(0.0, max_scroll(height, rows));
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
        if dy > 110.0 && self.scroll <= 0.5 {
            self.velocity = 0.0;
            return Some(DrawerAction::Close);
        }
        if dx.abs() <= 12.0 && dy.abs() <= 12.0 && time_ms.wrapping_sub(contact.down_ms) < 800 {
            if let Some(index) = tile_at(point, width, height, apps, self.scroll) {
                return Some(DrawerAction::Launch(index));
            }
        }
        if dy.abs() > 12.0 && time_ms.wrapping_sub(contact.last_ms) <= 100 {
            self.velocity = -contact.finger_velocity;
        }
        None
    }

    pub fn tick(&mut self, elapsed_ms: u32, height: u32, rows: usize) -> bool {
        if self.contact.is_some() || self.velocity.abs() < 20.0 || elapsed_ms == 0 {
            return false;
        }
        let elapsed = elapsed_ms.min(50);
        let old = self.scroll;
        self.scroll = (self.scroll + self.velocity * f64::from(elapsed) / 1000.0)
            .clamp(0.0, max_scroll(height, rows));
        self.velocity *= 0.88_f64.powf(f64::from(elapsed) / 16.0);
        if self.scroll == old || self.velocity.abs() < 20.0 {
            self.velocity = 0.0;
        }
        (self.scroll - old).abs() >= 0.5
    }

    pub fn coasting(&self) -> bool {
        self.velocity.abs() >= 20.0
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
    fn three_columns_hit_only_painted_tiles() {
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
        assert_eq!(tap(&mut nav, (190.0, top + 30.0), 7), None, "column gap");
        assert_eq!(
            tap(&mut nav, (280.0, top + ROW_HEIGHT * 2.0 + 30.0), 7),
            None,
            "empty eighth tile"
        );
        assert_eq!(
            tap(&mut nav, (100.0, top - 1.0), 7),
            None,
            "header is not a tile"
        );
    }

    #[test]
    fn scrolled_grid_maps_row_and_clips_bottom() {
        let mut nav = DrawerNavigation {
            scroll: 160.0,
            ..DrawerNavigation::default()
        };
        let top = list_top(1232);
        assert_eq!(
            tap(&mut nav, (278.0, top + 30.0), 30),
            Some(DrawerAction::Launch(4))
        );
        assert_eq!(
            tap(&mut nav, (278.0, 1210.0), 30),
            None,
            "footer is outside the grid"
        );
        assert_eq!(max_scroll(1232, 7), 0.0);
        assert!(max_scroll(1232, 30) > 0.0);
    }

    #[test]
    fn pressed_clears_on_drag_second_finger_and_cancel() {
        let mut nav = DrawerNavigation::default();
        let (x, y, w, h) = tile_rect(568, 1232, 1, 0.0);
        let p = (x + w / 2.0, y + h / 2.0);
        nav.down(1, p, 0);
        assert_eq!(nav.pressed(568, 1232, 7), Some(1));
        nav.motion(1, (p.0, p.1 - 40.0), 20, 1232, 30);
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
        let top = list_top(1232);
        nav.down(1, (120.0, top + 180.0), 0);
        assert!(nav.motion(1, (120.0, top + 80.0), 25, 1232, 30));
        assert_eq!(nav.scroll, 100.0);
        assert!(nav.motion(1, (120.0, top + 100.0), 40, 1232, 30));
        assert_eq!(nav.scroll, 80.0);
        assert_eq!(nav.up(1, (120.0, top + 100.0), 41, 568, 1232, 30), None);
        assert!(nav.coasting());
        nav.down(2, (120.0, top + 100.0), 50);
        assert!(!nav.coasting());
        nav.cancel();
        nav.down(3, (120.0, top + 180.0), 100);
        nav.motion(3, (120.0, top + 80.0), 125, 1232, 30);
        nav.up(3, (120.0, top + 80.0), 400, 568, 1232, 30);
        assert!(
            !nav.coasting(),
            "held finger cannot reuse old flick velocity"
        );
    }

    #[test]
    fn downward_dismiss_is_distinct_from_app_tap() {
        let mut nav = DrawerNavigation::default();
        let top = list_top(1232);
        nav.down(1, (100.0, top - 30.0), 30);
        nav.motion(1, (100.0, top + 110.0), 80, 1232, 7);
        assert_eq!(
            nav.up(1, (100.0, top + 110.0), 85, 568, 1232, 7),
            Some(DrawerAction::Close)
        );
    }
}

//! Touch-only drawer navigation. The compositor reveals the panel; these
//! gestures begin only after the drawer owns a settled input region.

pub const ROW_HEIGHT: f64 = 94.0;
pub const ROW_VISIBLE_HEIGHT: f64 = 82.0;

pub fn list_top(height: u32) -> f64 {
    f64::from(height) * 0.19 + 144.0
}

fn max_scroll(height: u32, rows: usize) -> f64 {
    let viewport = (f64::from(height) - 28.0 - list_top(height)).max(0.0);
    (rows as f64 * ROW_HEIGHT - viewport).max(0.0)
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
        height: u32,
        rows: usize,
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
            let top = list_top(height);
            if point.1 >= top && point.1 < f64::from(height) - 28.0 {
                let offset = point.1 - top + self.scroll;
                let index = (offset / ROW_HEIGHT).floor() as usize;
                if index < rows && offset % ROW_HEIGHT < ROW_VISIBLE_HEIGHT {
                    return Some(DrawerAction::Launch(index));
                }
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

    pub fn cancel(&mut self) {
        self.contact = None;
        self.velocity = 0.0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tap_maps_visible_row_after_scroll_and_ignores_gap() {
        let mut nav = DrawerNavigation {
            scroll: 188.0,
            ..DrawerNavigation::default()
        };
        let top = list_top(1232);
        nav.down(1, (100.0, top + 20.0), 0);
        assert_eq!(
            nav.up(1, (100.0, top + 20.0), 30, 1232, 30),
            Some(DrawerAction::Launch(2))
        );
        nav.down(2, (100.0, top + 88.0), 40);
        assert_eq!(nav.up(2, (100.0, top + 88.0), 60, 1232, 30), None);
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
        assert_eq!(nav.up(1, (120.0, top + 100.0), 41, 1232, 30), None);
        assert!(nav.coasting());
        nav.down(2, (120.0, top + 100.0), 50);
        assert!(!nav.coasting());
        nav.cancel();
        nav.down(3, (120.0, top + 180.0), 100);
        nav.motion(3, (120.0, top + 80.0), 125, 1232, 30);
        nav.up(3, (120.0, top + 80.0), 400, 1232, 30);
        assert!(
            !nav.coasting(),
            "a held finger must not reuse an old flick velocity"
        );
    }

    #[test]
    fn close_cancel_and_second_finger_never_launch() {
        let mut nav = DrawerNavigation::default();
        let top = list_top(1232);
        nav.down(1, (100.0, top + 20.0), 0);
        assert!(!nav.down(2, (100.0, top + 20.0), 1));
        assert_eq!(nav.up(1, (100.0, top + 20.0), 20, 1232, 4), None);
        nav.down(3, (100.0, top - 30.0), 30);
        nav.motion(3, (100.0, top + 110.0), 80, 1232, 4);
        assert_eq!(
            nav.up(3, (100.0, top + 110.0), 85, 1232, 4),
            Some(DrawerAction::Close)
        );
    }
}

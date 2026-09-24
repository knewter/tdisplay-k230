//! Testable state boundaries for the opt-in Rust shell client.

pub mod appearance;
pub mod background_decode;
pub mod catalog;
pub mod icon;
pub mod navigation;
pub mod protocol;
pub mod render;
pub mod service_data;
pub mod service_ui;
pub mod theme_catalog;
pub mod theme_ui;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Route {
    Drawer,
    Shade,
    Settings,
    Hide,
}

impl Route {
    pub fn parse(bytes: &[u8]) -> Option<Self> {
        match bytes {
            b"drawer\n" => Some(Self::Drawer),
            b"shade\n" => Some(Self::Shade),
            b"settings\n" => Some(Self::Settings),
            b"hide\n" => Some(Self::Hide),
            _ => None,
        }
    }
}

pub fn frame_bytes(width: u32, height: u32) -> Option<usize> {
    if !(300..=1024).contains(&width) || !(600..=2048).contains(&height) {
        return None;
    }
    usize::try_from(width)
        .ok()?
        .checked_mul(usize::try_from(height).ok()?)?
        .checked_mul(4)
}

/// Accept only panel-sized bounded configurations. A rejected compositor
/// resize leaves the last valid geometry untouched.
pub fn configure_size(current: &mut (u32, u32), width: u32, height: u32) -> Option<bool> {
    frame_bytes(width, height)?;
    let changed = *current != (width, height);
    *current = (width, height);
    Some(changed)
}

/// The renderer may repaint only a slot the compositor has released. With
/// all three slots busy it defers the new frame instead of growing without
/// bound or writing memory still owned by the compositor.
pub fn released_slot(available: &[bool]) -> Option<usize> {
    available.iter().position(|released| *released)
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct TouchTrace {
    pub id: Option<i32>,
    pub position: (f64, f64),
    pub moves: u32,
    pub cancelled: bool,
}

impl TouchTrace {
    pub fn down(&mut self, id: i32, position: (f64, f64)) -> bool {
        if self.id.is_some() {
            self.cancel();
            return false;
        }
        self.id = Some(id);
        self.position = position;
        self.moves = 0;
        self.cancelled = false;
        true
    }

    pub fn motion(&mut self, id: i32, position: (f64, f64)) -> bool {
        if self.id != Some(id) || self.cancelled {
            return false;
        }
        self.position = position;
        self.moves += 1;
        true
    }

    pub fn up(&mut self, id: i32) -> bool {
        if self.id != Some(id) || self.cancelled {
            return false;
        }
        self.id = None;
        true
    }

    pub fn cancel(&mut self) {
        self.id = None;
        self.cancelled = true;
    }
}

/// ARGB8888 on little-endian Linux is byte-ordered BGRA. The upper strip is
/// transparent so a card scene behind the overlay remains visibly real.
pub fn render_probe(canvas: &mut [u8], width: u32, height: u32, route: Route, touch: TouchTrace) {
    let w = width as usize;
    let h = height as usize;
    if canvas.len() != w.saturating_mul(h).saturating_mul(4) {
        return;
    }
    let top = h / 5;
    for y in 0..h {
        for x in 0..w {
            let index = (y * w + x) * 4;
            let (r, g, b, a) = if y < top {
                (0, 0, 0, 0)
            } else if y < top + 12 {
                (75, 210, 178, 255)
            } else {
                let band = ((y - top) / 88) % 2;
                let tint = match route {
                    Route::Drawer => (28, 49, 62),
                    Route::Shade => (47, 42, 69),
                    Route::Settings => (47, 61, 43),
                    Route::Hide => (0, 0, 0),
                };
                (tint.0 + band * 7, tint.1 + band * 7, tint.2 + band * 7, 255)
            };
            canvas[index..index + 4].copy_from_slice(&[b as u8, g as u8, r as u8, a as u8]);
        }
    }
    if touch.id.is_some() && !touch.cancelled {
        let cx = touch.position.0.round() as i32;
        let cy = touch.position.1.round() as i32;
        for y in (cy - 12).max(0)..=(cy + 12).min(height as i32 - 1) {
            for x in (cx - 12).max(0)..=(cx + 12).min(width as i32 - 1) {
                if (x - cx).abs() > 2 && (y - cy).abs() > 2 {
                    continue;
                }
                let index = (y as usize * w + x as usize) * 4;
                canvas[index..index + 4].copy_from_slice(&[255, 255, 255, 255]);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn routes_are_exact_and_bounded() {
        assert_eq!(Route::parse(b"drawer\n"), Some(Route::Drawer));
        assert_eq!(Route::parse(b"shade\n"), Some(Route::Shade));
        assert_eq!(Route::parse(b"settings\n"), Some(Route::Settings));
        assert_eq!(Route::parse(b"drawer extra\n"), None);
        assert_eq!(Route::parse(b"drawer"), None);
    }

    #[test]
    fn configure_size_is_bounded() {
        assert_eq!(frame_bytes(568, 1232), Some(2_799_104));
        assert_eq!(frame_bytes(1025, 1232), None);
        assert_eq!(frame_bytes(568, 2049), None);
        assert_eq!(frame_bytes(0, 1232), None);
        assert_eq!(frame_bytes(568, 99_999), None);
        let mut geometry = (568, 1232);
        assert_eq!(configure_size(&mut geometry, 568, 1232), Some(false));
        assert_eq!(configure_size(&mut geometry, 600, 1200), Some(true));
        assert_eq!(geometry, (600, 1200));
        assert_eq!(configure_size(&mut geometry, 600, 99_999), None);
        assert_eq!(geometry, (600, 1200));
    }

    #[test]
    fn touch_cancel_does_not_turn_into_tap() {
        let mut touch = TouchTrace::default();
        assert!(touch.down(1, (30.0, 40.0)));
        assert!(touch.motion(1, (35.0, 42.0)));
        touch.cancel();
        assert!(!touch.up(1));
        assert!(!touch.motion(1, (40.0, 44.0)));
        assert!(touch.down(2, (50.0, 60.0)));
        assert!(touch.up(2));
    }

    #[test]
    fn buffer_release_gate() {
        assert_eq!(released_slot(&[false, false, false]), None);
        assert_eq!(released_slot(&[false, true, false]), Some(1));
        assert_eq!(released_slot(&[]), None);
    }

    #[test]
    fn render_distinguishes_route_and_touch() {
        let mut drawer = vec![0; frame_bytes(568, 1232).unwrap()];
        render_probe(&mut drawer, 568, 1232, Route::Drawer, TouchTrace::default());
        assert_eq!(&drawer[0..4], &[0, 0, 0, 0]);
        let mut shade = drawer.clone();
        render_probe(&mut shade, 568, 1232, Route::Shade, TouchTrace::default());
        assert_ne!(drawer, shade);
    }
}

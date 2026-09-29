//! Testable state boundaries for the opt-in Rust shell client.

pub mod app_watch;
pub mod appearance;
pub mod background_decode;
pub mod catalog;
pub mod home_grid;
pub mod home_pager;
pub mod home_screen;
pub mod home_state;
pub mod home_widgets;
pub mod icon;
pub mod navigation;
pub mod pipewire_ipc;
pub mod protocol;
pub mod render;
pub mod service_data;
pub mod service_ui;
pub mod slider;
pub mod splash;
pub mod sway_ipc;
pub mod theme_carousel;
pub mod theme_catalog;
pub mod theme_thumbnails;
pub mod theme_ui;
pub mod video_status;
pub mod video_visibility;
pub mod video_wallpaper;
pub mod volume;
pub mod wifi_settings;
pub mod wifi_ui;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Route {
    Drawer,
    Shade,
    Settings,
    Power,
    Hide,
}

impl Route {
    pub fn parse(bytes: &[u8]) -> Option<Self> {
        match bytes {
            b"drawer\n" => Some(Self::Drawer),
            b"shade\n" => Some(Self::Shade),
            b"settings\n" => Some(Self::Settings),
            b"power\n" => Some(Self::Power),
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

/// The 568x1232 design aspect ratio every full-panel layer surface
/// (wallpaper, home, the drawer/shade/settings overlay -- all three
/// `LayerShellHandler::configure` branches) is authored against, and every
/// page painted onto them scales to fill via
/// `cr.scale(width / 568.0, height / 1232.0)` (see `render::paint_wifi` and
/// its siblings). That scale is only *uniform* -- the only kind that does
/// not squash or stretch glyphs and buttons -- when a `configure`'s own
/// aspect ratio stays close to this one.
const DESIGN_ASPECT: f64 = 568.0 / 1232.0;

/// Whether a proposed `(width, height)` keeps that uniform scale. Generous
/// (10%) so a real, legitimate proportional resize (a different physical
/// panel or a host/QEMU capture at a different resolution, same aspect --
/// `render::hit_uses_rendered_output_scale`'s own 390x844 case, ratio
/// 0.4621 against this constant's 0.4610) still passes, while a shrink
/// confined to one axis does not.
///
/// This exists as an independent, defense-in-depth check alongside
/// `set_exclusive_zone(-1)` on all three surfaces (`ensure_layer`'s own
/// doc): that request is what stops the compositor from ever proposing a
/// keyboard-exclusive-zone-driven single-axis shrink in the first place,
/// but `LayerShellHandler::configure` calls this too, so a client bug that
/// somehow reintroduced a `0` exclusive zone would still get caught here
/// rather than silently squashing the page again the way `wvkbd` did on
/// real glass, 2026-09-28 (`/tmp/coherent-settings.png`): the reported
/// configured height (keyboard top) was about 775, giving a ratio of
/// roughly 0.73 against this constant's 0.46 -- about 59% off, far outside
/// the 10% band below.
/// The width of a centered, design-aspect column filling `height`, when a
/// `(width, height)` configure is a whole output that is too wide for the
/// portrait design (an HDMI monitor rather than the 568x1232 panel). The
/// caller then asks the compositor for that narrower size, anchored top and
/// bottom only, so the shell draws pillarboxed at a uniform scale instead of
/// rejecting the output and leaving it black. `None` when the configure
/// already keeps the design aspect or is taller than it.
pub fn pillarbox_width(width: u32, height: u32) -> Option<u32> {
    if width == 0 || height == 0 || configure_preserves_aspect(width, height) {
        return None;
    }
    let ratio = f64::from(width) / f64::from(height);
    if ratio <= DESIGN_ASPECT {
        return None;
    }
    let column = (f64::from(height) * DESIGN_ASPECT).round() as u32;
    (column > 0 && column < width).then_some(column)
}

pub fn configure_preserves_aspect(width: u32, height: u32) -> bool {
    if width == 0 || height == 0 {
        return false;
    }
    let ratio = f64::from(width) / f64::from(height);
    ((ratio / DESIGN_ASPECT) - 1.0).abs() <= 0.10
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
                    Route::Power => (47, 42, 69),
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
        assert_eq!(Route::parse(b"power\n"), Some(Route::Power));
        assert_eq!(Route::parse(b"drawer extra\n"), None);
        assert_eq!(Route::parse(b"drawer"), None);
    }

    #[test]
    fn pillarbox_width_fits_landscape_outputs() {
        assert_eq!(pillarbox_width(568, 1232), None);
        assert_eq!(pillarbox_width(1024, 768), Some(354));
        assert_eq!(pillarbox_width(1920, 1080), Some(498));
        assert!(configure_preserves_aspect(354, 768));
        assert!(configure_preserves_aspect(498, 1080));
        assert_eq!(pillarbox_width(300, 1232), None);
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
    fn configure_preserves_aspect_accepts_uniform_resize_only() {
        // The panel's own native size.
        assert!(configure_preserves_aspect(568, 1232));
        // A proportional host/QEMU capture at a different resolution --
        // `render`'s own `hit_uses_rendered_output_scale` test case.
        assert!(configure_preserves_aspect(390, 844));
        // The real-board regression this guards (2026-09-28): wvkbd's
        // exclusive zone shrinking only the height, width unchanged.
        assert!(!configure_preserves_aspect(568, 775));
        assert!(!configure_preserves_aspect(568, 832));
        // Symmetric: a width-only shrink must be rejected too, not just a
        // height-only one.
        assert!(!configure_preserves_aspect(300, 1232));
        // Bounds/degenerate input.
        assert!(!configure_preserves_aspect(0, 1232));
        assert!(!configure_preserves_aspect(568, 0));
        // Just inside vs. clearly outside the 10% band.
        assert!(configure_preserves_aspect(568, 1120));
        assert!(!configure_preserves_aspect(568, 1100));
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

pub mod runtime_trace;

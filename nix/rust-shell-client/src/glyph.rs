//! The shell's own stroked icon set (visual language §11): one monochrome
//! style for Settings rows, the Shade and the drawer search, drawn as cairo
//! paths on a 24-unit grid. Strokes are 3 px with round caps and joins at
//! 48 px (rows) and scale with the box, never below 2 px for the small
//! inline glyphs at the slider ends. Theme icons for apps are not these.
use crate::render::color;
use cairo::{Context, LineCap, LineJoin};
use std::f64::consts::{FRAC_PI_4, PI, TAU};

/// The row icon box at 100%, in design pixels.
pub const ROW: f64 = 48.0;
/// The drawer icon box.
pub const DRAWER: f64 = 64.0;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Glyph {
    Wifi,
    /// Brightness; the small sun marks the dim end of a slider.
    Sun,
    SunSmall,
    Speaker,
    SpeakerMuted,
    Keyboard,
    Motion,
    KeyBacklight,
    Reboot,
    Power,
    Search,
    /// Cellular signal; the shade's lit-bar form is `paint_signal`.
    Signal,
    /// Location; the shade's fix form is `paint_location`.
    Location,
    /// Date & time: a clock face.
    Clock,
    /// About: a circled "i".
    Info,
}

impl Glyph {
    pub const ALL: [Glyph; 15] = [
        Glyph::Wifi,
        Glyph::Sun,
        Glyph::SunSmall,
        Glyph::Speaker,
        Glyph::SpeakerMuted,
        Glyph::Keyboard,
        Glyph::Motion,
        Glyph::KeyBacklight,
        Glyph::Reboot,
        Glyph::Power,
        Glyph::Search,
        Glyph::Signal,
        Glyph::Location,
        Glyph::Clock,
        Glyph::Info,
    ];
}

/// The stroke width for a `size` px box: 3 px at the 48 px row size.
pub fn stroke_width(size: f64) -> f64 {
    (3.0 * size / ROW).max(2.0)
}

/// Paints `glyph` into the `size` px square whose top-left is `(x, y)`.
pub fn paint(cr: &Context, glyph: Glyph, x: f64, y: f64, size: f64, rgb: u32, alpha: f64) {
    let _ = cr.save();
    cr.translate(x, y);
    let unit = size / 24.0;
    cr.scale(unit, unit);
    cr.set_line_width(stroke_width(size) / unit);
    cr.set_line_cap(LineCap::Round);
    cr.set_line_join(LineJoin::Round);
    color(cr, rgb, alpha);
    cr.new_path();
    match glyph {
        Glyph::Wifi => {
            for radius in [5.0, 10.0, 15.0] {
                cr.new_sub_path();
                cr.arc(12.0, 20.0, radius * 0.95, PI + FRAC_PI_4, TAU - FRAC_PI_4);
            }
            let _ = cr.stroke();
            cr.arc(12.0, 19.5, 1.6, 0.0, TAU);
            let _ = cr.fill();
        }
        Glyph::Sun | Glyph::SunSmall => {
            let (core, inner, outer) = if glyph == Glyph::Sun { (4.5, 7.5, 10.0) } else { (3.0, 6.0, 7.5) };
            cr.arc(12.0, 12.0, core, 0.0, TAU);
            for i in 0..8 {
                let angle = f64::from(i) * FRAC_PI_4;
                cr.move_to(12.0 + angle.cos() * inner, 12.0 + angle.sin() * inner);
                cr.line_to(12.0 + angle.cos() * outer, 12.0 + angle.sin() * outer);
            }
            let _ = cr.stroke();
        }
        Glyph::Speaker | Glyph::SpeakerMuted => {
            cr.move_to(3.5, 9.0);
            cr.line_to(7.5, 9.0);
            cr.line_to(12.5, 4.5);
            cr.line_to(12.5, 19.5);
            cr.line_to(7.5, 15.0);
            cr.line_to(3.5, 15.0);
            cr.close_path();
            if glyph == Glyph::SpeakerMuted {
                cr.move_to(16.0, 9.0);
                cr.line_to(21.0, 15.0);
                cr.move_to(21.0, 9.0);
                cr.line_to(16.0, 15.0);
            } else {
                for radius in [4.0, 8.0] {
                    cr.new_sub_path();
                    cr.arc(12.5, 12.0, radius, -0.75, 0.75);
                }
            }
            let _ = cr.stroke();
        }
        Glyph::Keyboard => {
            rounded_path(cr, 2.0, 6.0, 20.0, 12.0, 2.0);
            for row in [9.5, 12.5] {
                for col in [6.0, 10.0, 14.0, 18.0] {
                    cr.move_to(col, row);
                    cr.line_to(col, row);
                }
            }
            cr.move_to(8.0, 15.5);
            cr.line_to(16.0, 15.5);
            let _ = cr.stroke();
        }
        Glyph::Motion => {
            cr.arc(15.5, 12.0, 5.0, 0.0, TAU);
            for (y, from) in [(8.0, 5.0), (12.0, 2.5), (16.0, 5.0)] {
                cr.move_to(from, y);
                cr.line_to(8.0, y);
            }
            let _ = cr.stroke();
        }
        Glyph::KeyBacklight => {
            rounded_path(cr, 6.0, 11.0, 12.0, 10.0, 2.0);
            cr.move_to(12.0, 2.5);
            cr.line_to(12.0, 6.0);
            cr.move_to(5.0, 4.5);
            cr.line_to(7.0, 7.5);
            cr.move_to(19.0, 4.5);
            cr.line_to(17.0, 7.5);
            cr.move_to(10.0, 17.0);
            cr.line_to(14.0, 17.0);
            let _ = cr.stroke();
        }
        Glyph::Reboot => {
            // A ring open at the top, with an arrowhead where it ends,
            // pointing on round (clockwise).
            let end = -PI / 2.0 - 0.35;
            cr.arc(12.0, 13.0, 8.0, -PI / 2.0 + 0.35, end + TAU);
            let _ = cr.stroke();
            let (ex, ey) = (12.0 + 8.0 * end.cos(), 13.0 + 8.0 * end.sin());
            cr.move_to(ex - 1.5, ey - 4.5);
            cr.line_to(ex + 3.0, ey);
            cr.line_to(ex - 1.5, ey + 4.5);
            let _ = cr.stroke();
        }
        Glyph::Power => {
            cr.arc(12.0, 13.0, 8.0, -PI / 2.0 + 0.7, -PI / 2.0 - 0.7 + TAU);
            cr.move_to(12.0, 2.5);
            cr.line_to(12.0, 11.0);
            let _ = cr.stroke();
        }
        Glyph::Search => {
            cr.arc(10.0, 10.0, 6.5, 0.0, TAU);
            cr.move_to(15.0, 15.0);
            cr.line_to(21.0, 21.0);
            let _ = cr.stroke();
        }
        Glyph::Signal => signal_path(cr),
        Glyph::Location => pin_path(cr),
        Glyph::Clock => {
            cr.arc(12.0, 12.0, 9.0, 0.0, TAU);
            cr.move_to(12.0, 6.5);
            cr.line_to(12.0, 12.0);
            cr.line_to(16.0, 14.5);
            let _ = cr.stroke();
        }
        Glyph::Info => {
            cr.arc(12.0, 12.0, 9.0, 0.0, TAU);
            cr.move_to(12.0, 11.0);
            cr.line_to(12.0, 17.0);
            let _ = cr.stroke();
            cr.arc(12.0, 7.6, 1.3, 0.0, TAU);
            let _ = cr.fill();
        }
    }
    let _ = cr.restore();
}

/// Four bars rising to the right, each stroked as a round-capped line.
fn signal_path(cr: &Context) {
    for (i, height) in [5.0, 9.0, 14.0, 19.0].into_iter().enumerate() {
        let x = 4.0 + i as f64 * 5.5;
        cr.move_to(x, 21.0);
        cr.line_to(x, 21.0 - height);
    }
    let _ = cr.stroke();
}

/// The map pin's outline: a ring on a tip, with a dot inside.
fn pin_path(cr: &Context) {
    cr.new_path();
    pin_outline(cr);
    cr.close_path();
    let _ = cr.stroke();
    cr.arc(12.0, 9.5, 2.0, 0.0, TAU);
    let _ = cr.fill();
}

fn pin_outline(cr: &Context) {
    let (cx, cy, r): (f64, f64, f64) = (12.0, 9.5, 7.0);
    let tangent = (r / (22.0 - cy)).acos();
    let (left, right) = (PI / 2.0 + tangent, PI / 2.0 - tangent + TAU);
    cr.move_to(12.0, 22.0);
    cr.line_to(cx + r * left.cos(), cy + r * left.sin());
    cr.arc(cx, cy, r, left, right);
    cr.line_to(12.0, 22.0);
}

/// The shade's signal glyph: `lit` of four bars at full strength and the rest
/// faint; `no_service` draws all four faint under a slash.
pub fn paint_signal(cr: &Context, lit: u8, no_service: bool, x: f64, y: f64, size: f64, rgb: u32) {
    let _ = cr.save();
    cr.translate(x, y);
    let unit = size / 24.0;
    cr.scale(unit, unit);
    cr.set_line_width(stroke_width(size) / unit);
    cr.set_line_cap(LineCap::Round);
    cr.set_line_join(LineJoin::Round);
    for i in 0..4u8 {
        let lit_bar = !no_service && i < lit;
        color(cr, rgb, if lit_bar { 1.0 } else { 0.3 });
        let height = [5.0, 9.0, 14.0, 19.0][usize::from(i)];
        let bar_x = 4.0 + f64::from(i) * 5.5;
        cr.move_to(bar_x, 21.0);
        cr.line_to(bar_x, 21.0 - height);
        let _ = cr.stroke();
    }
    if no_service {
        color(cr, rgb, 1.0);
        cr.move_to(3.0, 3.0);
        cr.line_to(21.0, 21.0);
        let _ = cr.stroke();
    }
    let _ = cr.restore();
}

/// The shade's location glyph: a solid pin once there is a fix, an outline
/// while searching.
pub fn paint_location(cr: &Context, fix: bool, x: f64, y: f64, size: f64, rgb: u32) {
    let _ = cr.save();
    cr.translate(x, y);
    let unit = size / 24.0;
    cr.scale(unit, unit);
    cr.set_line_width(stroke_width(size) / unit);
    cr.set_line_cap(LineCap::Round);
    cr.set_line_join(LineJoin::Round);
    color(cr, rgb, 1.0);
    if fix {
        cr.new_path();
        pin_outline(cr);
        cr.close_path();
        cr.new_sub_path();
        cr.arc(12.0, 9.5, 2.6, 0.0, TAU);
        cr.set_fill_rule(cairo::FillRule::EvenOdd);
        let _ = cr.fill_preserve();
        let _ = cr.stroke();
    } else {
        color(cr, rgb, 0.7);
        pin_path(cr);
    }
    let _ = cr.restore();
}

fn rounded_path(cr: &Context, x: f64, y: f64, w: f64, h: f64, r: f64) {
    cr.new_sub_path();
    cr.arc(x + w - r, y + r, r, -PI / 2.0, 0.0);
    cr.arc(x + w - r, y + h - r, r, 0.0, PI / 2.0);
    cr.arc(x + r, y + h - r, r, PI / 2.0, PI);
    cr.arc(x + r, y + r, r, PI, 1.5 * PI);
    cr.close_path();
}

#[cfg(test)]
mod tests {
    use super::*;
    use cairo::{Format, ImageSurface};

    /// Inked pixels inside the box, and whether any ink fell outside it.
    fn ink(glyph: Glyph, size: f64) -> (usize, bool) {
        let pad = 8;
        let side = size as i32 + pad * 2;
        let mut surface = ImageSurface::create(Format::ARgb32, side, side).unwrap();
        {
            let cr = Context::new(&surface).unwrap();
            paint(&cr, glyph, f64::from(pad), f64::from(pad), size, 0xffffff, 1.0);
        }
        surface.flush();
        let stride = surface.stride() as usize;
        let data = surface.data().unwrap();
        let (mut inside, mut outside) = (0, false);
        for y in 0..side as usize {
            for x in 0..side as usize {
                if data[y * stride + x * 4 + 3] < 32 {
                    continue;
                }
                let inner = |v: usize| v >= pad as usize && v < pad as usize + size as usize;
                if inner(x) && inner(y) {
                    inside += 1;
                } else {
                    outside = true;
                }
            }
        }
        (inside, outside)
    }

    #[test]
    fn every_glyph_inks_its_box_at_the_row_and_drawer_sizes_and_stays_inside() {
        for size in [ROW, DRAWER] {
            for glyph in Glyph::ALL {
                let (inside, outside) = ink(glyph, size);
                let area = size * size;
                assert!(inside as f64 > area * 0.04, "{glyph:?} at {size}: only {inside} inked pixels");
                assert!((inside as f64) < area * 0.5, "{glyph:?} at {size}: {inside} inked pixels is not a stroke");
                assert!(!outside, "{glyph:?} at {size} draws outside its box");
            }
        }
    }

    #[test]
    fn the_stroke_is_three_pixels_at_the_row_size_and_never_under_two() {
        assert_eq!(stroke_width(ROW), 3.0);
        assert_eq!(stroke_width(DRAWER), 4.0);
        assert_eq!(stroke_width(20.0), 2.0);
    }

    #[test]
    fn the_glyphs_are_distinct() {
        let frames: Vec<Vec<u8>> = Glyph::ALL
            .iter()
            .map(|glyph| {
                let mut surface = ImageSurface::create(Format::ARgb32, 48, 48).unwrap();
                {
                    let cr = Context::new(&surface).unwrap();
                    paint(&cr, *glyph, 0.0, 0.0, ROW, 0xffffff, 1.0);
                }
                surface.flush();
                let frame = surface.data().unwrap().to_vec();
                frame
            })
            .collect();
        for (i, a) in frames.iter().enumerate() {
            for b in &frames[i + 1..] {
                assert_ne!(a, b);
            }
        }
    }
}

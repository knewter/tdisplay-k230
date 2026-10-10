//! Testable state boundaries for the opt-in Rust shell client.

pub mod app_actions;
pub mod app_watch;
pub mod appearance;
pub mod background_decode;
pub mod catalog;
pub mod evidence_render;
pub mod help;
pub mod home_grid;
pub mod home_pager;
pub mod home_screen;
pub mod home_state;
pub mod home_widgets;
pub mod icon;
pub mod navigation;
pub mod pipewire_ipc;
pub mod pointer_input;
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
    Help,
    Hide,
}

impl Route {
    pub fn parse(bytes: &[u8]) -> Option<Self> {
        match bytes {
            b"drawer\n" => Some(Self::Drawer),
            b"shade\n" => Some(Self::Shade),
            b"settings\n" => Some(Self::Settings),
            b"power\n" => Some(Self::Power),
            b"help\n" => Some(Self::Help),
            b"hide\n" => Some(Self::Hide),
            _ => None,
        }
    }
}

pub fn frame_bytes(width: u32, height: u32) -> Option<usize> {
    // Upper bounds widened from the original panel-only 300..=1024 (width)
    // to 300..=2048 on both axes for `feat/shell-responsive`: a whole HDMI
    // output is now accepted at its own full size (1920x1080 landscape,
    // 1080x1920 rotated portrait) instead of being pillarboxed down to a
    // design-aspect column (see `configure_preserves_aspect`'s doc and
    // `main.rs`'s `is_whole_output`). 2048 stays a real, if generous,
    // sanity bound -- nothing this shell targets exceeds it.
    if !(300..=2048).contains(&width) || !(600..=2048).contains(&height) {
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
///
/// A configure failing this check is no longer automatically rejected --
/// `main.rs`'s three `LayerShellHandler::configure` branches also accept it
/// when `is_whole_output` reports the compositor handed the surface its
/// entire output (an HDMI monitor's own size, at any aspect: 1920x1080
/// landscape, 1080x1920 rotated portrait). That is the *other* legitimate
/// case this constant alone cannot distinguish from a keyboard-exclusive-
/// zone squish: both change the aspect ratio, but only a squish leaves the
/// surface smaller than the output it sits on. `feat/hdmi-pillarbox`
/// (2026-09-29, commit 4c2eb57c) used to route the whole-output case
/// through `pillarbox_width` (removed by `feat/shell-responsive`, same
/// day) into a centered design-aspect column instead -- the operator did
/// not want that: a wide monitor should fill, not letterbox. See
/// `openspec/changes/the-shell-adapts-to-output-resolution/design.md` for
/// the fuller rationale and what still does not reflow (Settings' fixed
/// pixel offsets, `paint_wifi`'s own uniform-ish `cr.scale`).
pub fn configure_preserves_aspect(width: u32, height: u32) -> bool {
    if width == 0 || height == 0 {
        return false;
    }
    let ratio = f64::from(width) / f64::from(height);
    ((ratio / DESIGN_ASPECT) - 1.0).abs() <= 0.10
}

/// The design's own reference size: every fixed-pixel constant in
/// `home_grid.rs`, `navigation.rs`, and `render.rs`'s Settings row rhythm
/// was authored against a panel exactly this size, at `density_scale`'s own
/// `1.0`.
pub const DESIGN_WIDTH: f64 = 568.0;
pub const DESIGN_HEIGHT: f64 = 1232.0;

/// How much bigger content should paint on a surface denser/taller than the
/// 568x1232 design, so a large HDMI output's text/controls don't read as
/// tiny just because they're drawn at the same pixel size as this panel's
/// own physical DPI. `min(w, h)` against each axis's own design length (not
/// physical DPI, which this client has no reliable way to read from the
/// compositor) so a surface that is wide but *not* tall (1920x1080
/// landscape, shorter than the 1232-design height) does not get scaled up
/// on the strength of its width alone -- see `reflow_columns`'s own doc for
/// why width alone already gives that case more columns instead. Clamped
/// to `[1.0, 2.0]`: never *shrinks* content below the panel's own native
/// size (this must stay `1.0` there, for pixel-identical output), and never
/// grows it past 2x, past which point a Settings row would be larger than
/// this design was ever laid out to comfortably hold.
pub fn density_scale(width: u32, height: u32) -> f64 {
    if width == 0 || height == 0 {
        return 1.0;
    }
    let scale = (f64::from(width) / DESIGN_WIDTH).min(f64::from(height) / DESIGN_HEIGHT);
    scale.clamp(1.0, 2.0)
}

/// How many `base_columns`-pitch columns (as authored at `DESIGN_WIDTH`,
/// `scale` `1.0`) fit `width` at a given `scale`, rounded to the nearest
/// whole column and never fewer than `base_columns` -- a configure this
/// narrow is already rejected before any caller reaches this (`configure_
/// size`/`configure_preserves_aspect`), but this stays a safe floor
/// regardless. Shared by `navigation::columns_for_width` (the Drawer) and
/// `home_grid::columns_for_width` (Home's grid), both called with `scale`
/// fixed at `1.0`: reflow there is deliberately just "more columns of the
/// same pixel size," not "fewer, bigger columns," because unlike Settings'
/// single centered content column, a grid's whole point is to use width as
/// more cells, not as bigger cells with wasted gaps between them.
pub fn reflow_columns(width: u32, scale: f64, base_columns: usize) -> usize {
    if base_columns == 0 {
        return 0;
    }
    let safe_scale = if scale > 0.0 { scale } else { 1.0 };
    let scaled = (f64::from(width) / (safe_scale * DESIGN_WIDTH) * base_columns as f64).round();
    (scaled as usize).max(base_columns)
}

/// Settings' own centered content column: `(scale, x_offset)`, both design
/// units against the surface's real `(width, height)`. `scale` is `density_
/// scale`'s own value (so Settings' rows/text genuinely get bigger on a
/// dense/tall output, not just re-centered); the column's own width is the
/// design's `568` at that scale, capped to the real surface width so an
/// unexpectedly narrow surface never gets a column wider than itself.
/// `main.rs`'s `panel_intent` and `render.rs`'s `scene` both call this --
/// never recompute the transform independently in one without the other,
/// or a tap and its paint drift apart.
pub fn settings_content_transform(width: u32, height: u32) -> (f64, f64) {
    let scale = density_scale(width, height);
    let content_w = (DESIGN_WIDTH * scale).min(f64::from(width));
    let x = (f64::from(width) - content_w) / 2.0;
    (scale, x)
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
                    Route::Power | Route::Help => (47, 42, 69),
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
        assert_eq!(Route::parse(b"help\n"), Some(Route::Help));
        assert_eq!(Route::parse(b"drawer extra\n"), None);
        assert_eq!(Route::parse(b"drawer"), None);
    }

    #[test]
    fn frame_bytes_accepts_hdmi_whole_output_sizes() {
        // The four resolutions this change's own capture evidence covers
        // (docs/evidence/shell-responsive/): the native panel, plus
        // rotated-portrait and landscape HDMI outputs at two sizes each.
        assert_eq!(frame_bytes(568, 1232), Some(2_799_104));
        assert_eq!(frame_bytes(768, 1024), Some(3_145_728));
        assert_eq!(frame_bytes(1080, 1920), Some(8_294_400));
        assert_eq!(frame_bytes(1920, 1080), Some(8_294_400));
    }

    #[test]
    fn density_scale_is_pixel_identical_at_native_and_bounded_above() {
        // The panel itself, and any surface no denser than it on either
        // axis, must stay at exactly 1.0 -- this is the "568x1232 stays
        // pixel-identical" guarantee every scaled-content caller relies on.
        assert_eq!(density_scale(568, 1232), 1.0);
        assert_eq!(density_scale(768, 1024), 1.0, "shorter than design height clamps up to 1.0");
        // Landscape HDMI: shorter than the design height, so the *height*
        // ratio (which is what wins the `min`) pulls this to exactly 1.0
        // even though the surface is far wider than the panel.
        assert_eq!(density_scale(1920, 1080), 1.0);
        // Rotated-portrait HDMI: taller and narrower than landscape, so the
        // height ratio (1920/1232) wins and is genuinely > 1.0.
        assert!((density_scale(1080, 1920) - 1920.0 / 1232.0).abs() < 1e-9);
        // Upper bound: an extremely tall/dense surface never scales past 2x.
        assert_eq!(density_scale(4000, 4000), 2.0);
        // Degenerate input never panics or divides by zero.
        assert_eq!(density_scale(0, 1232), 1.0);
        assert_eq!(density_scale(568, 0), 1.0);
    }

    #[test]
    fn reflow_columns_matches_base_at_design_width_and_only_grows() {
        assert_eq!(reflow_columns(568, 1.0, 4), 4);
        assert_eq!(reflow_columns(300, 1.0, 4), 4, "never fewer than the base");
        assert_eq!(reflow_columns(768, 1.0, 4), 5);
        assert_eq!(reflow_columns(1080, 1.0, 4), 8);
        assert_eq!(reflow_columns(1920, 1.0, 4), 14);
        // A larger scale (bigger tiles) needs more real width per column,
        // so it yields fewer columns than the same width at scale 1.0.
        assert!(reflow_columns(1080, 1.6, 4) < reflow_columns(1080, 1.0, 4));
    }

    #[test]
    fn settings_content_transform_fills_the_panel_at_native_size() {
        // 568x1232: scale 1.0, no horizontal offset -- the content column
        // is exactly the panel, unchanged from before this transform
        // existed.
        assert_eq!(settings_content_transform(568, 1232), (1.0, 0.0));
        // A wide landscape output gets a centered, still-568-wide column
        // rather than stretching edge to edge.
        let (scale, x) = settings_content_transform(1920, 1080);
        assert_eq!(scale, 1.0);
        assert!((x - (1920.0 - 568.0) / 2.0).abs() < 1e-9);
        // A tall, denser output scales the column up (bigger content) and
        // still centers whatever width that scaled column occupies.
        let (scale, x) = settings_content_transform(1080, 1920);
        assert!(scale > 1.0);
        let content_w = 568.0 * scale;
        assert!(content_w <= 1080.0);
        assert!((x - (1080.0 - content_w) / 2.0).abs() < 1e-9);
        // Pathologically narrow: the column is capped to the real width
        // (never wider than the surface itself), with no offset left over.
        let (scale, x) = settings_content_transform(300, 1232);
        assert_eq!(scale, 1.0);
        assert_eq!(x, 0.0);
    }

    #[test]
    fn configure_size_is_bounded() {
        assert_eq!(frame_bytes(568, 1232), Some(2_799_104));
        assert_eq!(frame_bytes(2049, 1232), None);
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

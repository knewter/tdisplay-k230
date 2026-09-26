//! Cairo/Pango software scene for the opt-in shell client.
//! This first view uses real desktop names and explicit fallback artwork.
use crate::{
    appearance::{AppearanceSnapshot, AppearanceToken, Brush},
    catalog::AppEntry,
    home_grid::{self, HomeSlot},
    home_screen::HomeScreen,
    icon::IconCache,
    navigation::{list_top, tile_rect, COLUMNS, GRID_BOTTOM_INSET, ROW_HEIGHT},
    service_data::{Control, ControlValue, Priority},
    service_ui::{ServiceView, NOTIFICATION_ROW, NOTIFICATION_TOP},
    theme_carousel,
    theme_catalog::BackgroundKind,
    theme_thumbnails::{ThemeThumbnailCache, ThumbnailKey, Variant},
    theme_ui::{
        background_display_label, ThemeImageKey, ThemeImageWorker, ThemePage, ThemeView,
        BACKGROUND_CAROUSEL_TOP, THEME_CAROUSEL_TOP,
    },
    wifi_settings::Security,
    wifi_ui::{all_networks, Page as WifiPage, WifiPublic},
    Route,
};
use cairo::{Context, Format, ImageSurface, LinearGradient, Operator};
use pango::{EllipsizeMode, FontDescription};
use std::{fs::File, path::Path};

/// The one system font family used by every label this renderer draws.
/// `nix/card-shell/render.h` names the same literal (`CARD_SHELL_FONT_FAMILY`)
/// for the C card deck, so the two renderers that composite into one frame
/// never drift onto different fallback faces (finding P1-1 of
/// `docs/design/webos-polish-review.md`). This is deliberately "DejaVu Sans",
/// not the design study's IBM Plex family: `nix/shell.nix` ships only
/// `pkgs.dejavu_fonts` on the image ("One family is enough"), so DejaVu is
/// the only face guaranteed present, and pulling in a new font package is a
/// blob-inventory / image-size change out of scope for a rendering-only fix.
pub const FONT_FAMILY: &str = "DejaVu Sans";

fn color(cr: &Context, rgb: u32, alpha: f64) {
    cr.set_source_rgba(
        f64::from((rgb >> 16) & 255) / 255.0,
        f64::from((rgb >> 8) & 255) / 255.0,
        f64::from(rgb & 255) / 255.0,
        alpha,
    );
}

/// Alpha for the full-screen tray backdrop (Shade/Settings), as a pure
/// function of `progress` -- the panel's revealed fraction `p` in `[0, 1]`,
/// which is also exactly the visible-height fraction of the panel (its
/// screen-space top edge sits at `-(1-p) * panel_h`, so the portion above
/// y=0 is clipped and the visible slice is `p * panel_h` of `panel_h`).
/// The curve is a smoothstep ease-in-out (`3p^2 - 2p^3`) rather than linear,
/// so the dim reads as a fade tied to the drag instead of a pop, matching
/// the panel's own reveal at every instant -- live during the drag and
/// during the open/close/cancel settle alike, since both drive the same
/// `progress` value. `target` is the existing fully-open alpha (0.35).
fn tray_backdrop_alpha(progress: f64, target: f64) -> f64 {
    let p = progress.clamp(0.0, 1.0);
    let eased = p * p * (3.0 - 2.0 * p);
    eased * target
}

/// Paints the stationary, eased tray backdrop straight into an ARGB32
/// (premultiplied, byte order B/G/R/A) canvas that has already had the
/// panel's own opaque pixels composited onto it -- `RendererCache::draw`'s
/// shifted copy of `static_pixels`, or `render_candidate_overlay`'s own
/// fresh bake (always effectively at `progress: 1.0`, the only progress it
/// is ever used at -- see its own doc). Filling only pixels the panel left
/// transparent, rather than the whole canvas, is what keeps this correct
/// regardless of which of those two produced `canvas`: it dims exactly the
/// live deck behind the tray without ever touching the panel's own already-
/// opaque pixels. Cheap on purpose: no Cairo call and no per-pixel float
/// math -- black premultiplies to `(0, 0, 0, alpha)` at any alpha, so this
/// is one straight byte-only pass, no allocation.
fn apply_tray_backdrop(canvas: &mut [u8], route: Route, progress: f64) {
    if !matches!(route, Route::Settings | Route::Shade) {
        return;
    }
    let alpha_byte = (tray_backdrop_alpha(progress, 0.35) * 255.0).round() as u8;
    if alpha_byte == 0 {
        return;
    }
    for pixel in canvas.chunks_exact_mut(4) {
        if pixel[3] == 0 {
            pixel[3] = alpha_byte;
        }
    }
}

fn brush_color(value: &str) -> Option<(f64, f64, f64, f64)> {
    let hex = value.strip_prefix('#')?;
    if hex.len() != 8 {
        return None;
    }
    let byte = |at| u8::from_str_radix(&hex[at..at + 2], 16).ok();
    Some((
        f64::from(byte(2)?) / 255.0,
        f64::from(byte(4)?) / 255.0,
        f64::from(byte(6)?) / 255.0,
        f64::from(byte(0)?) / 255.0,
    ))
}

fn theme_brush<'a>(
    theme: Option<&'a AppearanceSnapshot>,
    section: &str,
    key: &str,
) -> Option<&'a Brush> {
    match theme?.token(section, key)? {
        AppearanceToken::Brush(brush) => Some(brush),
        _ => None,
    }
}

fn fill_brush(cr: &Context, brush: &Brush, x: f64, y: f64, w: f64, h: f64) -> bool {
    let Some(gradient) = brush_gradient(brush, x, y, w, h) else {
        return false;
    };
    if cr.set_source(&gradient).is_err() {
        return false;
    }
    cr.rectangle(x, y, w, h);
    cr.fill().is_ok()
}

fn brush_gradient(brush: &Brush, x: f64, y: f64, w: f64, h: f64) -> Option<LinearGradient> {
    let radians = brush.angle_degrees.to_radians();
    let dx = radians.cos() * w / 2.0;
    let dy = radians.sin() * h / 2.0;
    let gradient = LinearGradient::new(
        x + w / 2.0 - dx,
        y + h / 2.0 - dy,
        x + w / 2.0 + dx,
        y + h / 2.0 + dy,
    );
    for stop in &brush.stops {
        let (r, g, b, a) = brush_color(&stop.argb)?;
        gradient.add_color_stop_rgba(stop.offset, r, g, b, a * brush.alpha);
    }
    Some(gradient)
}

fn overlay_brush(
    cr: &Context,
    brush: Option<&Brush>,
    x: f64,
    y: f64,
    w: f64,
    h: f64,
    alpha: f64,
    fallback: u32,
) {
    if let Some(gradient) = brush.and_then(|brush| brush_gradient(brush, x, y, w, h)) {
        if cr.set_source(&gradient).is_ok() {
            let _ = cr.paint_with_alpha(alpha);
            return;
        }
    }
    color(cr, fallback, alpha);
    let _ = cr.paint();
}

fn brush_rgb(theme: Option<&AppearanceSnapshot>, section: &str, key: &str, fallback: u32) -> u32 {
    let Some(brush) = theme_brush(theme, section, key) else {
        return fallback;
    };
    let Some((r, g, b, _)) = brush.stops.first().and_then(|stop| brush_color(&stop.argb)) else {
        return fallback;
    };
    ((r * 255.0) as u32) << 16 | ((g * 255.0) as u32) << 8 | (b * 255.0) as u32
}

fn palette_rgb_or(theme: Option<&AppearanceSnapshot>, key: &str, fallback: u32) -> u32 {
    let Some(value) = theme.and_then(|snapshot| snapshot.palette_color(key)) else {
        return fallback;
    };
    u32::from(value.red) << 16 | u32::from(value.green) << 8 | u32::from(value.blue)
}

/// The icon theme name a given appearance resolves to -- the same lookup
/// `RendererCache::set_appearance` already did inline, factored out so
/// `render_candidate_overlay` can resolve the *candidate*'s own icon
/// theme without disturbing `self.icons`.
fn icon_theme_name_for(theme: Option<&AppearanceSnapshot>) -> String {
    let configured = std::env::var("K230_ICON_THEME").ok();
    theme
        .and_then(|value| value.icon_theme.as_deref())
        .or(configured.as_deref())
        .unwrap_or("hicolor")
        .to_owned()
}

#[derive(Clone, Copy)]
struct VisualStyle {
    text: u32,
    muted: u32,
    accent: u32,
    error: u32,
}

fn visual_style(theme: Option<&AppearanceSnapshot>, section: &str) -> VisualStyle {
    let text = brush_rgb(
        theme,
        section,
        "text",
        palette_rgb_or(theme, "foreground", 0xf4f7f8),
    );
    // `muted` is a decorative swatch in both pinned Catppuccin variants;
    // `light_foreground` is the authored readable secondary text role.
    let muted = palette_rgb_or(
        theme,
        "light_foreground",
        palette_rgb_or(theme, "foreground", 0xc8d7dd),
    );
    let accent = brush_rgb(
        theme,
        section,
        if section == "notifications" {
            "countdown"
        } else {
            "selected-text"
        },
        palette_rgb_or(theme, "accent", 0x78d7cb),
    );
    VisualStyle {
        text,
        muted,
        accent,
        error: palette_rgb_or(theme, "red", 0xf4b9a6),
    }
}

fn text_weight(
    cr: &Context,
    value: &str,
    x: f64,
    y: f64,
    width: f64,
    size: f64,
    rgb: u32,
    weight: pango::Weight,
) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(size * f64::from(pango::SCALE));
    font.set_weight(weight);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
    layout.set_ellipsize(EllipsizeMode::End);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

fn text(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    text_weight(cr, value, x, y, width, size, rgb, pango::Weight::Normal);
}

/// A third weight tier between `text()` and `heading()` (finding P1-1), for
/// section-eyebrow labels like "YOUR DEVICE" or "Device controls" that
/// should read as a distinct hierarchy step, not plain body text nor a
/// heading. DejaVu Sans ships only Book/Bold faces, so fontconfig/Pango
/// synthesize this via partial emboldening rather than a true medium
/// instance; that is an accepted, low-risk approximation given the image
/// deliberately carries one font family (see `FONT_FAMILY`).
fn medium(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    text_weight(cr, value, x, y, width, size, rgb, pango::Weight::Medium);
}

fn heading(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    text_weight(cr, value, x, y, width, size, rgb, pango::Weight::Bold);
}

/// Vertical rhythm for the Settings screen's four capability rows (finding
/// P0-4 of `docs/design/webos-polish-review.md`): one row height plus one
/// gap, computed from `index`, in place of five independent hand-typed `y`
/// constants that drifted out of sync with each other.
/// `service_ui::hit` mirrors these exact numbers for touch regions --
/// keep the two in lockstep if this rhythm ever changes.
pub const SETTINGS_ROW_FIRST_Y: f64 = 162.0;
pub const SETTINGS_ROW_H: f64 = 110.0;
pub const SETTINGS_ROW_GAP: f64 = 16.0;
pub const SETTINGS_ROW_COUNT: u32 = 4;
pub const SETTINGS_POWER_CARD_H: f64 = 70.0;

pub fn settings_row_y(index: u32) -> f64 {
    SETTINGS_ROW_FIRST_Y + f64::from(index) * (SETTINGS_ROW_H + SETTINGS_ROW_GAP)
}

/// The bottom edge of `count` stacked settings rows, i.e. where any content
/// that follows the row list (the Power section) should begin.
pub fn settings_rows_bottom(count: u32) -> f64 {
    if count == 0 {
        return SETTINGS_ROW_FIRST_Y;
    }
    settings_row_y(count - 1) + SETTINGS_ROW_H
}

/// The Power section and, when present, the power confirmation dialog are
/// themselves positioned relative to the row rhythm above rather than as
/// independent literals, so nothing in the Settings screen is a hand-typed
/// offset any more.
#[derive(Clone, Copy)]
pub struct SettingsLayout {
    pub power_heading_y: f64,
    pub reboot_y: f64,
    pub poweroff_y: f64,
    pub poweroff_bottom: f64,
}

pub fn settings_layout() -> SettingsLayout {
    let rows_bottom = settings_rows_bottom(SETTINGS_ROW_COUNT);
    let power_heading_y = rows_bottom + 22.0;
    let reboot_y = power_heading_y + 28.0;
    let poweroff_y = reboot_y + SETTINGS_POWER_CARD_H + SETTINGS_ROW_GAP;
    SettingsLayout {
        power_heading_y,
        reboot_y,
        poweroff_y,
        poweroff_bottom: poweroff_y + SETTINGS_POWER_CARD_H,
    }
}

#[derive(Clone, Copy)]
pub struct SettingsConfirmLayout {
    pub label_y: f64,
    pub card_y: f64,
    pub bottom: f64,
}

/// The power confirmation dialog, positioned `after` whatever content
/// precedes it (the Power section's bottom edge).
pub fn settings_confirm_layout(after: f64) -> SettingsConfirmLayout {
    let label_y = after + 14.0;
    let card_y = label_y + 28.0;
    SettingsConfirmLayout {
        label_y,
        card_y,
        bottom: card_y + 110.0,
    }
}

/// Size a secondary panel to its content instead of a full-height sheet
/// (finding P0-2): `natural` is the content's own bottom edge, clamped to a
/// minimum so short content still reads as a panel and to the available
/// height so it never overflows the screen.
pub fn content_sized_panel_h(natural: f64, available_h: f64, min_h: f64) -> f64 {
    natural.max(min_h).min(available_h)
}

fn centered_label(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(size * f64::from(pango::SCALE));
    font.set_weight(pango::Weight::Bold);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
    layout.set_alignment(pango::Alignment::Center);
    layout.set_ellipsize(EllipsizeMode::End);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

fn rounded(cr: &Context, x: f64, y: f64, w: f64, h: f64, r: f64) {
    cr.new_sub_path();
    cr.arc(x + w - r, y + r, r, -std::f64::consts::FRAC_PI_2, 0.0);
    cr.arc(x + w - r, y + h - r, r, 0.0, std::f64::consts::FRAC_PI_2);
    cr.arc(
        x + r,
        y + h - r,
        r,
        std::f64::consts::FRAC_PI_2,
        std::f64::consts::PI,
    );
    cr.arc(
        x + r,
        y + r,
        r,
        std::f64::consts::PI,
        3.0 * std::f64::consts::FRAC_PI_2,
    );
    cr.close_path();
}

/// A small rotating-arc "loading" spinner, centered at `(cx, cy)`. `phase`
/// (0.0..1.0, wrapping) drives the rotation -- callers advance it on a slow,
/// deliberately throttled cadence (`main.rs`'s `THEME_PULSE_INTERVAL`), not
/// every render, so this is genuinely an animation the render loop redraws
/// *for* (goal: "render only while something actually changes"), never a
/// disguised idle poll. Used for every pending-decode affordance the theme
/// chooser paints: an unresolved carousel thumbnail, a preparing still
/// preview, and a background/theme confirm still waiting on its reply.
fn spinner(cr: &Context, cx: f64, cy: f64, radius: f64, phase: f64, rgb: u32) {
    if radius <= 0.0 {
        return;
    }
    let start = phase.fract().abs() * std::f64::consts::TAU;
    let sweep = 1.6; // a partial ring, not a full circle, so rotation reads clearly
    let _ = cr.save();
    cr.set_line_width((radius * 0.22).max(1.5));
    cr.set_line_cap(cairo::LineCap::Round);
    color(cr, rgb, 0.85);
    cr.new_sub_path();
    cr.arc(cx, cy, radius, start, start + sweep);
    let _ = cr.stroke();
    let _ = cr.restore();
}

fn service_card(
    cr: &Context,
    theme: Option<&AppearanceSnapshot>,
    section: &str,
    x: f64,
    y: f64,
    w: f64,
    h: f64,
    selected: bool,
) {
    let _ = cr.save();
    rounded(cr, x, y, w, h, 16.0);
    cr.clip();
    let brush = theme_brush(
        theme,
        section,
        if selected {
            "selected-background"
        } else {
            "background"
        },
    )
    .or_else(|| theme_brush(theme, "menu", "background"));
    if !brush.is_some_and(|brush| fill_brush(cr, brush, x, y, w, h)) {
        color(cr, 0x263946, 1.0);
        cr.paint().ok();
    }
    let tint = if selected {
        "selected-fill-alpha"
    } else {
        "normal-fill-alpha"
    };
    let alpha = match theme.and_then(|snapshot| snapshot.token("controls", tint)) {
        Some(AppearanceToken::Number(value)) => value.clamp(0.04, 0.35),
        _ => {
            if selected {
                0.18
            } else {
                0.08
            }
        }
    };
    overlay_brush(
        cr,
        theme_brush(theme, "controls", "normal-color"),
        x,
        y,
        w,
        h,
        alpha,
        0x78929d,
    );
    let _ = cr.restore();

    if let Some(border) = theme_brush(
        theme,
        section,
        if selected {
            "selected-border"
        } else {
            "border"
        },
    ) {
        if let Some(gradient) = brush_gradient(border, x, y, w, h) {
            rounded(cr, x + 0.75, y + 0.75, w - 1.5, h - 1.5, 15.25);
            cr.set_line_width(1.5);
            if cr.set_source(&gradient).is_ok() {
                let _ = cr.stroke();
            }
        }
    }
}

fn control_text(control: &Control) -> String {
    match &control.value {
        Some(ControlValue::Percent(value)) => format!("{} · {value}%", control.label),
        Some(ControlValue::Text(value)) => format!("{} · {value}", control.label),
        Some(ControlValue::Boolean(value)) => {
            format!("{} · {}", control.label, if *value { "on" } else { "off" })
        }
        None => control.label.clone(),
    }
}

/// The decode target size for a cached thumbnail variant under a given
/// carousel's own geometry (see `theme_thumbnails.rs`'s "Two geometries, so
/// two sizes per variant"): `Expanded` decodes at the centered slice's own
/// size, `Slice` at a fully-collapsed side slice's size.
fn variant_size(geometry: &theme_carousel::CarouselGeometry, variant: Variant) -> (u32, u32) {
    match variant {
        Variant::Expanded => (geometry.expanded_w.round() as u32, geometry.expanded_h.round() as u32),
        Variant::Slice => (geometry.slice_w.round() as u32, geometry.slice_h.round() as u32),
    }
}

/// Paints one Quattro-style Cover Flow carousel: `ids[position.round()]`
/// expanded and centered, its shingled skewed neighbors fanned either side.
/// Shared by the theme carousel (List page) and a theme's background
/// carousel (Preview page) -- both are the same component upstream too
/// (`ImagePicker.qml`, shared by `omarchy-theme-switcher` and
/// `omarchy-theme-bg-switcher`).
#[allow(clippy::too_many_arguments)]
fn paint_carousel(
    cr: &Context,
    theme: Option<&AppearanceSnapshot>,
    dim_color: u32,
    style: VisualStyle,
    thumbnails: Option<&ThemeThumbnailCache>,
    geometry: &theme_carousel::CarouselGeometry,
    position: f64,
    ids: &[&str],
    center_x: f64,
    top_y: f64,
    pressed: Option<usize>,
    busy: Option<usize>,
    pulse_phase: f64,
) {
    if ids.is_empty() {
        return;
    }
    let centered = position.round().clamp(0.0, (ids.len() - 1) as f64) as usize;
    let skew = geometry.skew;
    for slice in theme_carousel::visible_slices(geometry, position, ids.len(), center_x, top_y) {
        let Some(id) = ids.get(slice.index) else {
            continue;
        };
        // Upstream's mask shape (`ImagePicker.qml` lines 463-489): the top
        // edge is inset by `skew` on the left, the bottom edge by `skew` on
        // the right, so the slice leans like every other slice in the row.
        let top_left = skew;
        let top_right = slice.width;
        let bottom_right = slice.width - skew;
        let bottom_left = 0.0;
        let parallelogram = |cr: &Context| {
            cr.move_to(slice.x + top_left, slice.y);
            cr.line_to(slice.x + top_right, slice.y);
            cr.line_to(slice.x + bottom_right, slice.y + slice.height);
            cr.line_to(slice.x + bottom_left, slice.y + slice.height);
            cr.close_path();
        };
        let _ = cr.save();
        parallelogram(cr);
        cr.clip();
        // A slice nearer the centered position blends toward the wide
        // "Expanded" crop; a distant one uses the narrow "Slice" crop. See
        // `theme_thumbnails.rs` for why only these two are ever decoded.
        let variant = if slice.blend < 0.5 {
            Variant::Expanded
        } else {
            Variant::Slice
        };
        let image = thumbnails.and_then(|cache| cache.get(id, variant));
        if let Some(image) = image {
            let iw = f64::from(image.width());
            let ih = f64::from(image.height());
            if iw > 0.0 && ih > 0.0 {
                let _ = cr.save();
                cr.translate(slice.x, slice.y);
                cr.scale(slice.width / iw, slice.height / ih);
                if cr.set_source_surface(image, 0.0, 0.0).is_ok() {
                    let _ = cr.paint();
                }
                let _ = cr.restore();
            }
        } else {
            color(cr, palette_rgb_or(theme, "background", 0x1b2830), 1.0);
            let _ = cr.paint();
        }
        // Dims a non-centered slice, fading out as it nears the centered
        // position -- upstream's `Util.alpha(root.dimColor, item.selected ?
        // 0 : 0.42)`, continuous here instead of a hard boolean.
        color(cr, dim_color, 0.42 * slice.blend);
        let _ = cr.paint();
        // A slice with no decoded thumbnail yet gets a spinner instead of a
        // silent flat fill, so a slow decode (goal: never a frozen-looking
        // UI) reads as "loading", not "missing" or "broken".
        if image.is_none() {
            spinner(
                cr,
                slice.x + slice.width / 2.0,
                slice.y + slice.height / 2.0,
                (slice.width.min(slice.height) * 0.16).max(6.0),
                pulse_phase,
                style.accent,
            );
        }
        let _ = cr.restore(); // drop the clip

        let selected = slice.index == centered;
        parallelogram(cr);
        cr.set_line_width(if selected { 3.0 } else { 1.0 });
        color(
            cr,
            if selected { style.accent } else { style.muted },
            if selected { 1.0 } else { 0.5 },
        );
        let _ = cr.stroke();

        // Immediate, same-frame feedback for a tap in flight: a tinted wash
        // over the slice the finger is currently down on (cleared the
        // instant it becomes a drag or the touch ends -- see
        // `Carousel::pressed`), or, once that tap has been confirmed and is
        // waiting on its reply, a spinner in place of the wash.
        if Some(slice.index) == busy {
            let _ = cr.save();
            parallelogram(cr);
            cr.clip();
            spinner(
                cr,
                slice.x + slice.width / 2.0,
                slice.y + slice.height / 2.0,
                (slice.width.min(slice.height) * 0.22).max(8.0),
                pulse_phase,
                style.accent,
            );
            let _ = cr.restore();
        } else if Some(slice.index) == pressed {
            parallelogram(cr);
            color(cr, style.accent, 0.28);
            let _ = cr.fill();
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn paint_theme_chooser(
    cr: &Context,
    w: f64,
    h: f64,
    view: &ThemeView,
    theme: Option<&AppearanceSnapshot>,
    // The still-image decode worker (`poll_theme_image`/`ThemeImageKey`)
    // that used to feed a large "screen crop" preview on a now-removed
    // separate Preview page is left wired up in `RendererCache` (task:
    // tap-to-apply, 2026-09-25) rather than torn out in the same change --
    // both carousels already show their own thumbnails via `thumbnails`
    // below, so neither parameter is painted here any more. Pruning the
    // now-unused worker itself is a follow-up, named in this task's own
    // evidence rather than done silently here.
    _preview_image: Option<&ImageSurface>,
    _preview_error: bool,
    thumbnails: Option<&ThemeThumbnailCache>,
    pulse_phase: f64,
) {
    let style = visual_style(theme, "image-picker");
    if let Some(brush) = theme_brush(theme, "image-picker", "background") {
        let _ = fill_brush(cr, brush, 0.0, 0.0, w, h);
    }
    // Upstream's `dimColor: Color.background` -- tints unselected carousel
    // slices, not the panel's own background wash above.
    let dim_color = palette_rgb_or(theme, "background", 0x0b1216);
    text(cr, "‹ Settings", 28.0, 42.0, 185.0, 22.0, style.accent);
    text(cr, "Close", w - 115.0, 42.0, 90.0, 21.0, style.accent);
    if view.page != ThemePage::List {
        return;
    }
    // Task: tap-to-apply (2026-09-25, user decision: "tap theme in the
    // theme picker, apply immediately, so i can compare them easily").
    // There is only one chooser page now: the theme carousel, the active
    // theme's own background carousel below it, and a plain-text "Current
    // theme"/"Current background" marker under whichever slice of each is
    // centred and durably active -- no separate Preview page, no
    // Apply/Cancel footer. A tap on the *centred* slice of either carousel
    // applies immediately (`Carousel::up`'s own `Confirm`-only-when-
    // centred rule; see `theme_ui::ThemeView::tap_theme`/`tap_background`);
    // dragging only ever recentres.
    heading(cr, "Themes", 28.0, 84.0, w - 56.0, 26.0, style.text);
    text(
        cr,
        "Drag to browse · tap the centre to apply",
        28.0,
        112.0,
        w - 56.0,
        16.0,
        style.muted,
    );
    match &view.list {
        Some(list) if !list.themes.is_empty() => {
            let center_x = w / 2.0;
            let ids: Vec<&str> = list.themes.iter().map(|t| t.id.as_str()).collect();
            let centered = view
                .theme_position
                .round()
                .clamp(0.0, (list.themes.len() - 1) as f64) as usize;
            // A tap on the centred slice submits a request through
            // `ThemeView::tap_theme`/`advance` and stays `view.pending`
            // until it settles (a `Preview` round trip for a cold
            // generation, or straight to `Activate` for one this process
            // already learned via prepare-ahead/`known_generations`); for
            // as long as that request targets this slice specifically
            // (`ThemeView::applying_theme_index`), it shows a spinner
            // instead of going quiet. Once a warm theme's own optimistic
            // show adopts a matching pre-render, the tapped slice already
            // *looks* applied and the spinner correctly stops (see
            // `show_theme_optimistically`'s own doc for why the pre-
            // rendered frame -- computed with nothing pending -- is
            // exactly right for that moment, not stale).
            paint_carousel(
                cr,
                theme,
                dim_color,
                style,
                thumbnails,
                &theme_carousel::THEME_GEOMETRY,
                view.theme_position,
                &ids,
                center_x,
                THEME_CAROUSEL_TOP,
                view.theme_pressed,
                view.applying_theme_index(),
                pulse_phase,
            );
            let entry = &list.themes[centered];
            let is_current = list.active.id.as_deref() == Some(entry.id.as_str());
            let label_y = THEME_CAROUSEL_TOP + theme_carousel::THEME_GEOMETRY.expanded_h + 12.0;
            heading(cr, &entry.label, 28.0, label_y, w - 56.0, 24.0, style.text);
            let status = if is_current {
                "Current theme"
            } else {
                match entry.origin {
                    crate::theme_catalog::ThemeOrigin::Builtin => "Built in",
                    crate::theme_catalog::ThemeOrigin::User => "User theme",
                }
            };
            text(cr, status, 28.0, label_y + 26.0, w - 56.0, 16.0, style.muted);
        }
        Some(_) => {
            text(
                cr,
                "No themes available",
                28.0,
                THEME_CAROUSEL_TOP + 22.0,
                w - 56.0,
                20.0,
                style.muted,
            );
        }
        None => {
            text(
                cr,
                "Loading themes",
                28.0,
                THEME_CAROUSEL_TOP + 22.0,
                w - 56.0,
                20.0,
                style.muted,
            );
        }
    }
    // `view.preview` is the *active* theme's own detail (see `ThemeView`'s
    // own doc) -- this background carousel always reflects whichever
    // theme is currently, durably active, not whatever the theme carousel
    // above happens to be centred on mid-browse; it updates only once a
    // tapped theme's own activation actually settles.
    heading(
        cr,
        "Backgrounds",
        28.0,
        BACKGROUND_CAROUSEL_TOP - 30.0,
        w - 56.0,
        22.0,
        style.text,
    );
    match view.preview.as_ref() {
        Some(preview) if !preview.backgrounds.is_empty() => {
            let center_x = w / 2.0;
            let ids: Vec<&str> = preview.backgrounds.iter().map(|b| b.id.as_str()).collect();
            let centered = view
                .background_position
                .round()
                .clamp(0.0, (preview.backgrounds.len() - 1) as f64) as usize;
            paint_carousel(
                cr,
                theme,
                dim_color,
                style,
                thumbnails,
                &theme_carousel::BACKGROUND_GEOMETRY,
                view.background_position,
                &ids,
                center_x,
                BACKGROUND_CAROUSEL_TOP,
                view.background_pressed,
                view.applying_background_index(),
                pulse_phase,
            );
            let background = &preview.backgrounds[centered];
            let label_y =
                BACKGROUND_CAROUSEL_TOP + theme_carousel::BACKGROUND_GEOMETRY.expanded_h + 12.0;
            heading(
                cr,
                &background_display_label(&background.label),
                28.0,
                label_y,
                w - 56.0,
                24.0,
                style.text,
            );
            let status = if background.kind == BackgroundKind::Video {
                "Video unavailable"
            } else if background.selected {
                "Current background"
            } else {
                "Tap to apply"
            };
            text(
                cr,
                status,
                28.0,
                label_y + 26.0,
                w - 56.0,
                16.0,
                if background.kind == BackgroundKind::Video {
                    style.error
                } else {
                    style.muted
                },
            );
        }
        Some(_) => {
            text(
                cr,
                "No backgrounds available",
                28.0,
                BACKGROUND_CAROUSEL_TOP + 22.0,
                w - 56.0,
                20.0,
                style.muted,
            );
        }
        None => {
            text(
                cr,
                "Loading backgrounds",
                28.0,
                BACKGROUND_CAROUSEL_TOP + 22.0,
                w - 56.0,
                20.0,
                style.muted,
            );
        }
    }
    // A single pending/error/message line anchors below the background
    // carousel's own fixed-height content. Unlike the removed Preview
    // page's own Apply/Cancel footer, none of this needs a live overlay
    // painted outside the cached body: `RendererCache::set_theme_view`
    // still calls `invalidate()` unconditionally on every `ThemeView`
    // change (including a `pending` transition or a pulse tick), so the
    // ordinary rebuild path already repaints it fresh every time -- the
    // only frame that ever skips a fresh rebuild is an *adopted*
    // pre-render, and by the exact moment one is adopted (Optimistic
    // Apply's own `show_theme_optimistically`) the applied theme already
    // looks done, so a stale "nothing pending" snapshot baked into that
    // one frame is correct, not stale (board evidence, 2026-09-28, in
    // this task's own evidence doc).
    let message_y = (BACKGROUND_CAROUSEL_TOP + theme_carousel::BACKGROUND_GEOMETRY.expanded_h
        + 64.0)
        .min(h - 30.0);
    if view.pending.is_some() {
        text(cr, "Preparing…", 28.0, message_y, w - 56.0, 18.0, style.muted);
    }
    if let Some(error) = &view.error {
        text(cr, error, 28.0, message_y, w - 56.0, 17.0, style.error);
    }
    if let Some(message) = &view.message {
        text(cr, message, 28.0, message_y, w - 56.0, 17.0, style.muted);
    }
}

#[derive(Clone, Copy)]
pub struct RenderParams {
    pub width: u32,
    pub height: u32,
    pub route: Route,
    pub progress: f64,
    pub scroll: f64,
}

/// The Entry page's `view.message` is reused for informational text ("Saved
/// for automatic reconnect", "Network forgotten") as well as genuine
/// connect failures; only the latter gets the elevated P0-3 banner.
fn entry_error_message(view: &WifiPublic) -> Option<&str> {
    if view.page != WifiPage::Entry {
        return None;
    }
    view.message.as_deref().filter(|message| {
        !(view.pending || message.starts_with("Saved") || message.starts_with("Network forgotten"))
    })
}

fn paint_wifi(
    cr: &Context,
    view: &WifiPublic,
    theme: Option<&AppearanceSnapshot>,
    width: f64,
    height: f64,
) {
    // Touch coordinates and artwork share a 568×1232 reference layout.
    let _ = cr.save();
    cr.scale(width / 568.0, height / 1232.0);
    let style = visual_style(theme, "controls");
    text(
        cr,
        if view.page == WifiPage::List {
            "‹ Settings"
        } else {
            "‹ Networks"
        },
        28.0,
        45.0,
        180.0,
        23.0,
        style.accent,
    );
    heading(cr, "Wi-Fi", 28.0, 105.0, 360.0, 38.0, style.text);
    match view.page {
        WifiPage::Closed => {}
        WifiPage::List => {
            text(cr, "Refresh", 420.0, 45.0, 125.0, 22.0, style.accent);
            service_card(cr, theme, "controls", 24.0, 150.0, 520.0, 116.0, false);
            text(
                cr,
                "Current connection",
                42.0,
                168.0,
                470.0,
                16.0,
                style.muted,
            );
            text(
                cr,
                view.snapshot
                    .as_ref()
                    .and_then(|s| s.current.as_deref())
                    .unwrap_or("Not connected"),
                42.0,
                199.0,
                460.0,
                24.0,
                style.text,
            );
            let saved = view.snapshot.as_ref().map_or(0, |s| s.saved.len());
            text(
                cr,
                &format!("{saved} saved  ·  tap a network to connect"),
                42.0,
                235.0,
                470.0,
                15.0,
                style.muted,
            );
            text(
                cr,
                "Saved and nearby",
                28.0,
                304.0,
                480.0,
                19.0,
                style.muted,
            );
            let _ = cr.save();
            cr.rectangle(20.0, 338.0, 528.0, 814.0);
            cr.clip();
            if let Some(snapshot) = &view.snapshot {
                let rows = all_networks(snapshot);
                for (index, item) in rows.iter().enumerate() {
                    let y = 338.0 + index as f64 * 88.0 - view.scroll;
                    if !(-88.0..1152.0).contains(&y) {
                        continue;
                    }
                    service_card(cr, theme, "controls", 24.0, y, 520.0, 78.0, false);
                    text(cr, &item.ssid, 42.0, y + 13.0, 350.0, 21.0, style.text);
                    let status = if snapshot.current.as_ref() == Some(&item.ssid) {
                        "Connected"
                    } else if snapshot.saved.iter().any(|saved| saved.ssid == item.ssid) {
                        "Saved"
                    } else {
                        match item.security {
                            Security::Open => "Open",
                            Security::Wpa2Psk => "Password",
                            Security::Unsupported => "Unsupported",
                        }
                    };
                    text(cr, status, 42.0, y + 45.0, 430.0, 16.0, style.muted);
                    text(cr, "›", 492.0, y + 22.0, 30.0, 25.0, style.accent);
                }
                if rows.is_empty() && !view.pending {
                    text(
                        cr,
                        "No networks found. Tap Refresh.",
                        42.0,
                        370.0,
                        470.0,
                        21.0,
                        style.muted,
                    );
                }
            } else {
                text(
                    cr,
                    "Scanning nearby networks…",
                    42.0,
                    370.0,
                    470.0,
                    21.0,
                    style.muted,
                );
            }
            let _ = cr.restore();
        }
        WifiPage::Entry => {
            if let Some(selected) = &view.selected {
                service_card(cr, theme, "controls", 24.0, 150.0, 520.0, 108.0, true);
                text(cr, &selected.ssid, 42.0, 172.0, 470.0, 25.0, style.text);
                text(
                    cr,
                    match selected.security {
                        Security::Open => "Open network · no password needed",
                        Security::Wpa2Psk if view.use_saved => "WPA2-Personal · saved credential",
                        Security::Wpa2Psk => "WPA2-Personal · password required",
                        Security::Unsupported => "Unsupported",
                    },
                    42.0,
                    214.0,
                    470.0,
                    17.0,
                    style.muted,
                );
                if selected.security == Security::Wpa2Psk {
                    text(
                        cr,
                        if view.use_saved {
                            "Saved password"
                        } else {
                            "Password"
                        },
                        28.0,
                        281.0,
                        500.0,
                        18.0,
                        style.muted,
                    );
                    service_card(cr, theme, "controls", 24.0, 310.0, 520.0, 90.0, false);
                    let mask = "•".repeat(view.password_len.min(22));
                    text(
                        cr,
                        if view.use_saved {
                            "Stored securely; no re-entry needed"
                        } else if mask.is_empty() {
                            "Tap keys to enter password"
                        } else {
                            &mask
                        },
                        42.0,
                        337.0,
                        464.0,
                        25.0,
                        style.text,
                    );
                    if !view.use_saved {
                        text(
                            cr,
                            &format!("{} / 63", view.password_len),
                            445.0,
                            369.0,
                            75.0,
                            15.0,
                            style.muted,
                        );
                    }
                }
                if view
                    .snapshot
                    .as_ref()
                    .is_some_and(|s| s.saved.iter().any(|n| n.ssid == selected.ssid))
                {
                    if view.use_saved && selected.security == Security::Wpa2Psk {
                        service_card(cr, theme, "controls", 24.0, 414.0, 250.0, 62.0, false);
                        text(
                            cr,
                            "Change password…",
                            42.0,
                            432.0,
                            225.0,
                            18.0,
                            style.accent,
                        );
                    }
                    service_card(cr, theme, "controls", 294.0, 414.0, 250.0, 62.0, false);
                    text(
                        cr,
                        "Forget network…",
                        314.0,
                        432.0,
                        215.0,
                        18.0,
                        style.error,
                    );
                }
                // A rejected password used to sit as a single line of colored
                // text between the numeric row and the Cancel/Connect
                // buttons -- easy to miss in what otherwise reads as dead
                // space (finding P0-3). Give it its own elevated,
                // border-accented banner directly under the field it
                // refers to instead.
                if selected.security == Security::Wpa2Psk && !view.use_saved {
                    if let Some(message) = entry_error_message(view) {
                        let show_saved_buttons = view.snapshot.as_ref().is_some_and(|s| {
                            s.saved.iter().any(|n| n.ssid == selected.ssid)
                        });
                        let banner_y = if show_saved_buttons { 486.0 } else { 408.0 };
                        service_card(cr, theme, "controls", 24.0, banner_y, 520.0, 64.0, false);
                        rounded(cr, 24.75, banner_y + 0.75, 518.5, 62.5, 15.25);
                        cr.set_line_width(1.5);
                        color(cr, style.error, 0.85);
                        let _ = cr.stroke();
                        text(cr, "!", 40.0, banner_y + 17.0, 30.0, 28.0, style.error);
                        text(cr, message, 78.0, banner_y + 21.0, 448.0, 19.0, style.error);
                    }
                }
            }
            if !view.use_saved
                && view
                    .selected
                    .as_ref()
                    .is_some_and(|s| s.security == Security::Wpa2Psk)
            {
                let rows = [
                    if view.symbols {
                        "!@#$%^&*()"
                    } else {
                        "1234567890"
                    },
                    if view.symbols {
                        "-_=+[]{};:"
                    } else {
                        "qwertyuiop"
                    },
                    if view.symbols {
                        "'\"\\|/?.<>"
                    } else {
                        "asdfghjkl"
                    },
                    if view.symbols { "~`,zxcv" } else { "zxcvbnm" },
                ];
                for (row, keys) in rows.iter().enumerate() {
                    let y = 530.0 + row as f64 * 90.0;
                    let (left, right) = if row == 2 {
                        (28.0, 540.0)
                    } else if row == 3 {
                        (74.0, 494.0)
                    } else {
                        (18.0, 550.0)
                    };
                    let cell = (right - left) / keys.chars().count() as f64;
                    for (index, ch) in keys.chars().enumerate() {
                        let x = left + index as f64 * cell;
                        service_card(cr, theme, "controls", x + 2.0, y, cell - 4.0, 76.0, false);
                        text(
                            cr,
                            &ch.to_string(),
                            x + cell * 0.35,
                            y + 23.0,
                            cell * 0.6,
                            26.0,
                            style.text,
                        );
                    }
                }
                service_card(cr, theme, "controls", 18.0, 800.0, 52.0, 76.0, false);
                text(cr, "⇧", 28.0, 820.0, 40.0, 28.0, style.accent);
                service_card(cr, theme, "controls", 498.0, 800.0, 52.0, 76.0, false);
                text(cr, "Del", 504.0, 824.0, 44.0, 18.0, style.accent);
                service_card(cr, theme, "controls", 18.0, 890.0, 112.0, 76.0, false);
                text(
                    cr,
                    if view.symbols { "ABC" } else { "?123" },
                    38.0,
                    913.0,
                    90.0,
                    22.0,
                    style.accent,
                );
                service_card(cr, theme, "controls", 136.0, 890.0, 278.0, 76.0, false);
                text(cr, "space", 222.0, 914.0, 110.0, 20.0, style.muted);
                service_card(cr, theme, "controls", 420.0, 890.0, 130.0, 76.0, false);
                text(cr, "Delete", 445.0, 917.0, 85.0, 18.0, style.accent);
            }
            service_card(cr, theme, "controls", 24.0, 1120.0, 250.0, 88.0, false);
            service_card(cr, theme, "controls", 294.0, 1120.0, 250.0, 88.0, true);
            text(cr, "Cancel", 90.0, 1147.0, 145.0, 25.0, style.muted);
            text(cr, "Connect", 351.0, 1147.0, 145.0, 25.0, style.accent);
        }
        WifiPage::Connecting => {
            service_card(cr, theme, "controls", 24.0, 220.0, 520.0, 210.0, true);
            text(cr, "Connecting…", 42.0, 260.0, 460.0, 31.0, style.text);
            text(
                cr,
                "Checking association, then saving for reconnect",
                42.0,
                324.0,
                460.0,
                19.0,
                style.muted,
            );
            service_card(cr, theme, "controls", 24.0, 1010.0, 520.0, 110.0, false);
            text(
                cr,
                "Cancel connection",
                135.0,
                1047.0,
                310.0,
                25.0,
                style.accent,
            );
        }
        WifiPage::ForgetConfirm => {
            service_card(cr, theme, "controls", 24.0, 230.0, 520.0, 210.0, true);
            text(
                cr,
                "Forget saved network?",
                42.0,
                270.0,
                470.0,
                27.0,
                style.text,
            );
            text(
                cr,
                "It will not reconnect automatically.",
                42.0,
                326.0,
                470.0,
                19.0,
                style.muted,
            );
            service_card(cr, theme, "controls", 24.0, 850.0, 250.0, 110.0, false);
            service_card(cr, theme, "controls", 294.0, 850.0, 250.0, 110.0, true);
            text(cr, "Keep", 101.0, 886.0, 140.0, 25.0, style.muted);
            text(cr, "Forget", 360.0, 886.0, 140.0, 25.0, style.error);
        }
    }
    // The Entry page's rejected-password case already got its own elevated
    // banner above (finding P0-3); do not also repeat it as a second,
    // lower-emphasis line down here.
    let already_shown = view.page == WifiPage::Entry && entry_error_message(view).is_some();
    if !already_shown {
        if let Some(message) = &view.message {
            let y = match view.page {
                WifiPage::List => 1163.0,
                WifiPage::Entry => 1020.0,
                WifiPage::Connecting | WifiPage::ForgetConfirm => 480.0,
                WifiPage::Closed => 0.0,
            };
            let color = if view.pending
                || message.starts_with("Saved")
                || message.starts_with("Network forgotten")
            {
                style.muted
            } else {
                style.error
            };
            if y > 0.0 {
                text(cr, message, 30.0, y, 506.0, 18.0, color);
            }
        }
    }
    let _ = cr.restore();
}

/// Where the Settings screen's own content (rows, Power section, and any
/// confirm dialog or message) naturally ends, feeding `content_sized_panel_h`
/// (finding P0-2) instead of always filling the screen.
fn settings_content_bottom(services: Option<&ServiceView>) -> f64 {
    const EMPTY_BOTTOM: f64 = 177.0 + 20.0 + 24.0;
    let Some(view) = services else {
        return EMPTY_BOTTOM;
    };
    if view.settings.is_none() {
        return EMPTY_BOTTOM;
    }
    let mut bottom = settings_layout().poweroff_bottom;
    if view.confirmation.is_some() {
        bottom = settings_confirm_layout(bottom).bottom;
    }
    if view.message.is_some() {
        bottom += 56.0;
    }
    bottom + 32.0
}

/// Wi-Fi's List page is a plain scrollable row list, like Settings and
/// Themes; content-size it the same way. The Entry/Connecting/ForgetConfirm
/// dialogs are fixed, footer- and keyboard-anchored layouts where every
/// literal `y` assumes the full screen height -- re-anchoring all of them to
/// a shrunk panel is real surgery on `paint_wifi` with no evidence citing
/// those specific pages as offenders, so they are left at full height here
/// (`f64::MAX` clamps to the available height with no visible change).
fn wifi_content_bottom(view: &WifiPublic) -> f64 {
    match view.page {
        WifiPage::List => {
            let rows = view.snapshot.as_ref().map_or(0, |s| all_networks(s).len());
            338.0 + rows as f64 * 88.0 + 24.0
        }
        WifiPage::Entry | WifiPage::Connecting | WifiPage::ForgetConfirm | WifiPage::Closed => {
            f64::MAX
        }
    }
}

/// Themes' one List page (task: tap-to-apply, 2026-09-25 -- there is no
/// longer a separate Preview page) is content-sized the same way as
/// Wi-Fi's: both carousels plus their labels and the pending/error/
/// message line below them, matching `paint_theme_chooser`'s own fixed
/// layout exactly.
fn theme_chooser_content_bottom(view: &ThemeView) -> f64 {
    match view.page {
        ThemePage::List => {
            BACKGROUND_CAROUSEL_TOP + theme_carousel::BACKGROUND_GEOMETRY.expanded_h + 100.0
        }
        ThemePage::Controls => f64::MAX,
    }
}

/// The effective panel height for whatever is currently showing under
/// `Route::Settings` -- the plain controls screen, the Wi-Fi flow, or the
/// theme chooser -- content-sized per finding P0-2 instead of the full
/// screen height regardless of what is actually on it.
fn settings_panel_h(
    available_h: f64,
    chooser: Option<&ThemeView>,
    services: Option<&ServiceView>,
) -> f64 {
    const MIN_PANEL_H: f64 = 420.0;
    if let Some(view) = services
        .and_then(|s| s.wifi.as_ref())
        .filter(|v| v.page != WifiPage::Closed)
    {
        return content_sized_panel_h(wifi_content_bottom(view), available_h, MIN_PANEL_H);
    }
    if let Some(view) = chooser.filter(|v| v.page != ThemePage::Controls) {
        return content_sized_panel_h(
            theme_chooser_content_bottom(view),
            available_h,
            MIN_PANEL_H,
        );
    }
    content_sized_panel_h(settings_content_bottom(services), available_h, MIN_PANEL_H)
}

fn scene(
    cr: &Context,
    params: RenderParams,
    apps: &[AppEntry],
    icons: &mut IconCache,
    theme: Option<&AppearanceSnapshot>,
    services: Option<&ServiceView>,
    chooser: Option<&ThemeView>,
    preview_image: Option<&ImageSurface>,
    preview_error: bool,
    thumbnails: Option<&ThemeThumbnailCache>,
    pressed: Option<usize>,
) {
    let RenderParams {
        width,
        height,
        route,
        progress,
        scroll,
    } = params;
    let w = f64::from(width);
    let h = f64::from(height);
    cr.set_operator(Operator::Source);
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.0);
    let _ = cr.paint();
    cr.set_operator(Operator::Over);

    let panel_y = if route == Route::Drawer {
        h * 0.19
    } else {
        0.0
    };
    // Secondary panels are sized to their own content and capped, rather
    // than always filling the remaining screen height regardless of how
    // little is on them (finding P0-2). Drawer keeps its existing full-bleed
    // grid -- its captures show it filling the space in ordinary use, and
    // it is not among the offending screens this finding cites.
    let panel_h = match route {
        Route::Shade => h * 0.65,
        Route::Settings => settings_panel_h(h - panel_y, chooser, services),
        _ => h - panel_y,
    };
    // No backdrop dim is painted here. `scene()` shapes the panel's *opaque*
    // content only; `RendererCache::draw` always calls this at a fixed
    // `progress: 1.0` and then cheaply row-shifts the resulting bitmap for
    // whatever the live drag/settle progress actually is (see its own doc
    // comment) -- so anything painted here, at any alpha, would be dragged
    // along by that same shift instead of staying put on screen. That was
    // the reported bug: a dim rect baked in here translated with the panel
    // and only ever covered a shrinking sliver of the screen instead of a
    // stationary, live-eased fade. `RendererCache::draw` now paints the
    // full-screen backdrop itself, in screen space, after the shift, using
    // the caller's actual per-frame `progress` -- see `tray_backdrop_alpha`.
    let hidden = 1.0 - progress.clamp(0.0, 1.0);
    cr.translate(
        0.0,
        if route == Route::Drawer {
            hidden * panel_h
        } else {
            -hidden * panel_h
        },
    );
    let section = match route {
        Route::Drawer => "launcher",
        Route::Shade => "notifications",
        Route::Settings => "controls",
        Route::Hide => "launcher",
    };
    let style = visual_style(theme, section);
    let panel_brush = theme_brush(theme, section, "background").or_else(|| {
        (route == Route::Settings)
            .then(|| theme_brush(theme, "menu", "background"))
            .flatten()
    });
    if matches!(route, Route::Drawer | Route::Shade | Route::Settings) {
        // Preserve the authored translucent brush over an opaque theme
        // plate, rather than letting live card text ghost through apps.
        // Originally Drawer-only; any theme can author sub-1.0 alpha on
        // `notifications`/`controls` backgrounds just as easily as on
        // `launcher`, so the same guard now covers Shade and Settings
        // (finding P1-5).
        color(cr, palette_rgb_or(theme, "background", 0x1e1e2e), 1.0);
        cr.rectangle(0.0, panel_y, w, panel_h);
        let _ = cr.fill();
    }
    if !panel_brush.is_some_and(|brush| fill_brush(cr, brush, 0.0, panel_y, w, panel_h)) {
        let gradient = LinearGradient::new(0.0, panel_y, w, panel_y + panel_h);
        gradient.add_color_stop_rgb(0.0, 0.075, 0.12, 0.17);
        gradient.add_color_stop_rgb(1.0, 0.12, 0.19, 0.24);
        cr.rectangle(0.0, panel_y, w, panel_h);
        let _ = cr.set_source(&gradient);
        let _ = cr.fill();
    }
    if !theme_brush(theme, section, "border")
        .is_some_and(|brush| fill_brush(cr, brush, 0.0, panel_y, w, 2.0))
    {
        color(cr, style.accent, 1.0);
        cr.rectangle(0.0, panel_y, w, 2.0);
        let _ = cr.fill();
    }
    // Whatever content-sizing (Settings) or the fixed Shade cap leaves
    // beneath the panel is the live deck, not empty air; `RendererCache::
    // draw` dims it with a stationary, live-eased backdrop rather than
    // either an opaque void or an undimmed, jarring reveal (finding P0-2).
    // Nothing is painted here -- see this function's own doc above.
    if matches!(route, Route::Drawer | Route::Shade) {
        rounded(cr, w / 2.0 - 36.0, panel_y + 11.0, 72.0, 6.0, 3.0);
        color(cr, style.accent, 0.82);
        let _ = cr.fill();
    }
    let title = match route {
        Route::Drawer => "All apps",
        Route::Shade => "Notifications",
        Route::Settings => "Settings",
        Route::Hide => return,
    };
    if route == Route::Drawer {
        medium(
            cr,
            "YOUR DEVICE",
            28.0,
            panel_y + 44.0,
            w - 56.0,
            15.0,
            style.muted,
        );
        heading(cr, title, 28.0, panel_y + 76.0, w - 56.0, 40.0, style.text);
    } else if !(route == Route::Settings
        && (chooser.is_some_and(|view| view.page != ThemePage::Controls)
            || services
                .and_then(|s| s.wifi.as_ref())
                .is_some_and(|view| view.page != WifiPage::Closed)))
    {
        heading(cr, title, 28.0, panel_y + 32.0, w - 56.0, 40.0, style.text);
    }
    match route {
        Route::Drawer => {
            text(
                cr,
                "Everything installed, one upward pull away.",
                28.0,
                panel_y + 130.0,
                w - 56.0,
                18.0,
                style.muted,
            );
            let row_start = list_top(height);
            let _ = cr.save();
            cr.rectangle(
                0.0,
                row_start,
                w,
                (h - GRID_BOTTOM_INSET - row_start).max(0.0),
            );
            cr.clip();
            let first = (scroll / ROW_HEIGHT).floor().max(0.0) as usize * COLUMNS;
            for (index, app) in apps.iter().enumerate().skip(first).take(21) {
                let (x, y, tile_w, tile_h) = tile_rect(width, height, index, scroll);
                if y >= h - GRID_BOTTOM_INSET || tile_w <= 0.0 {
                    break;
                }
                service_card(
                    cr,
                    theme,
                    "menu",
                    x,
                    y,
                    tile_w,
                    tile_h,
                    pressed == Some(index),
                );
                if pressed == Some(index) {
                    rounded(cr, x + 2.0, y + 2.0, tile_w - 4.0, tile_h - 4.0, 14.0);
                    cr.set_line_width(3.0);
                    color(cr, style.accent, 1.0);
                    let _ = cr.stroke();
                }
                let icon_x = x + (tile_w - 58.0) / 2.0;
                service_card(cr, theme, "launcher", icon_x, y + 17.0, 58.0, 58.0, true);
                let painted = app
                    .icon
                    .as_deref()
                    .is_some_and(|icon| icons.paint(cr, icon, 50, icon_x + 4.0, y + 21.0));
                if !painted {
                    let initial = app
                        .name
                        .chars()
                        .next()
                        .unwrap_or('?')
                        .to_uppercase()
                        .to_string();
                    centered_label(
                        cr,
                        &initial,
                        icon_x + 4.0,
                        y + 30.0,
                        50.0,
                        27.0,
                        style.accent,
                    );
                }
                centered_label(
                    cr,
                    &app.name,
                    x + 8.0,
                    y + 94.0,
                    tile_w - 16.0,
                    20.0,
                    brush_rgb(theme, "menu", "text", style.text),
                );
            }
            let _ = cr.restore();
            if apps.is_empty() {
                text(
                    cr,
                    "No installed apps are available",
                    28.0,
                    row_start + 18.0,
                    w - 56.0,
                    21.0,
                    style.muted,
                );
            }
            // One gesture-hint typography across Drawer/Shade/deck: sentence
            // case, muted, size 14 (finding P1-2); `nix/card-shell/adapter.c`'s
            // "Swipe up for apps" matches this same treatment.
            text(
                cr,
                "Swipe down to return to cards",
                88.0,
                h - 43.0,
                w - 176.0,
                14.0,
                style.muted,
            );
        }
        Route::Shade => {
            text(cr, "Settings", w - 150.0, 46.0, 126.0, 20.0, style.accent);
            text(
                cr,
                "Swipe up above the list to close",
                28.0,
                86.0,
                w - 56.0,
                15.0,
                style.muted,
            );
            let items = services.and_then(|view| view.notifications.as_ref());
            let count = items.map_or(0, |snapshot| snapshot.count);
            text(
                cr,
                // Singular form (finding P1-4): "1 notifications" read as a
                // bug on the one screen where the number is always visible.
                if count == 1 {
                    "1 notification".to_string()
                } else {
                    format!("{count} notifications")
                }
                .as_str(),
                28.0,
                112.0,
                w - 220.0,
                19.0,
                style.muted,
            );
            if count > 0 {
                text(
                    cr,
                    "Dismiss all",
                    w - 166.0,
                    143.0,
                    140.0,
                    17.0,
                    style.accent,
                );
            }
            // The preview tile repeated whatever the top history row already
            // shows -- identical text for one notification, or a
            // contentless "No active preview" sitting directly above a full
            // history list (finding P1-4). webOS kept banners (ephemeral)
            // and the dashboard (persistent history) as two different
            // objects; here, show the tile only when there is no history to
            // display it alongside.
            let show_preview = items.is_none() || count == 0;
            if show_preview {
                service_card(
                    cr,
                    theme,
                    "notifications",
                    24.0,
                    186.0,
                    w - 48.0,
                    72.0,
                    false,
                );
                if let Some(preview) = items.and_then(|snapshot| snapshot.preview.as_ref()) {
                    let painted = preview
                        .icon
                        .as_deref()
                        .is_some_and(|icon| icons.paint(cr, icon, 38, 42.0, 203.0));
                    if !painted {
                        text(
                            cr,
                            &preview
                                .source
                                .chars()
                                .next()
                                .unwrap_or('?')
                                .to_uppercase()
                                .to_string(),
                            51.0,
                            209.0,
                            30.0,
                            21.0,
                            style.text,
                        );
                    }
                    text(
                        cr,
                        &preview.source,
                        94.0,
                        197.0,
                        w - 132.0,
                        17.0,
                        style.accent,
                    );
                    text(
                        cr,
                        &preview.summary,
                        94.0,
                        220.0,
                        w - 132.0,
                        21.0,
                        style.text,
                    );
                } else {
                    let empty = if items.is_none() {
                        "Loading preview"
                    } else {
                        "No new notifications"
                    };
                    text(cr, empty, 42.0, 211.0, w - 84.0, 20.0, style.muted);
                }
            }
            if let Some(error) = services.and_then(|view| view.notification_error.as_deref()) {
                text(
                    cr,
                    error,
                    28.0,
                    NOTIFICATION_TOP + 14.0,
                    w - 56.0,
                    18.0,
                    style.error,
                );
            } else if let Some(items) = items {
                let _ = cr.save();
                cr.rectangle(
                    0.0,
                    NOTIFICATION_TOP,
                    w,
                    (panel_h - NOTIFICATION_TOP - 24.0).max(0.0),
                );
                cr.clip();
                let offset = services.map_or(0.0, |view| view.notification_scroll);
                for (index, event) in items.events.iter().enumerate() {
                    let y = NOTIFICATION_TOP + index as f64 * NOTIFICATION_ROW - offset;
                    if y + NOTIFICATION_ROW < NOTIFICATION_TOP || y >= panel_h - 24.0 {
                        continue;
                    }
                    let drag = services
                        .and_then(|view| view.notification_swipe.as_ref())
                        .filter(|swipe| {
                            swipe.row_index == index
                                && swipe.event_id == event.id
                                && event.dismissible
                                && event.priority != Priority::Critical
                        })
                        .map_or(0.0, |swipe| swipe.offset);
                    if drag.abs() >= 18.0 {
                        text(
                            cr,
                            "Dismiss",
                            if drag > 0.0 { 36.0 } else { w - 128.0 },
                            y + 44.0,
                            96.0,
                            18.0,
                            style.error,
                        );
                    }
                    let _ = cr.save();
                    cr.translate(drag, 0.0);
                    service_card(
                        cr,
                        theme,
                        "notifications",
                        24.0,
                        y,
                        w - 48.0,
                        NOTIFICATION_ROW - 8.0,
                        false,
                    );
                    let painted = event
                        .icon
                        .as_deref()
                        .is_some_and(|icon| icons.paint(cr, icon, 38, 40.0, y + 15.0));
                    if !painted {
                        text(
                            cr,
                            &event
                                .source
                                .chars()
                                .next()
                                .unwrap_or('?')
                                .to_uppercase()
                                .to_string(),
                            48.0,
                            y + 19.0,
                            36.0,
                            22.0,
                            style.text,
                        );
                    }
                    text(
                        cr,
                        &event.source,
                        92.0,
                        y + 13.0,
                        w - 132.0,
                        16.0,
                        style.accent,
                    );
                    text(
                        cr,
                        &event.summary,
                        92.0,
                        y + 39.0,
                        w - 132.0,
                        21.0,
                        style.text,
                    );
                    text(
                        cr,
                        &event.body,
                        92.0,
                        y + 71.0,
                        w - 132.0,
                        15.0,
                        style.muted,
                    );
                    if let Some(error) = &event.error {
                        text(cr, error, 92.0, y + 90.0, w - 132.0, 14.0, style.error);
                    }
                    let _ = cr.restore();
                }
                let _ = cr.restore();
            } else {
                text(
                    cr,
                    "Loading notifications",
                    28.0,
                    NOTIFICATION_TOP + 14.0,
                    w - 56.0,
                    19.0,
                    style.muted,
                );
            }
            if let Some(message) = services.and_then(|view| view.message.as_deref()) {
                service_card(
                    cr,
                    theme,
                    "notifications",
                    24.0,
                    panel_h - 73.0,
                    w - 48.0,
                    49.0,
                    false,
                );
                text(
                    cr,
                    message,
                    42.0,
                    panel_h - 62.0,
                    w - 84.0,
                    16.0,
                    style.error,
                );
            }
        }
        Route::Settings => {
            if let Some(view) = services
                .and_then(|s| s.wifi.as_ref())
                .filter(|v| v.page != WifiPage::Closed)
            {
                paint_wifi(cr, view, theme, w, h);
                return;
            }
            if let Some(view) = chooser.filter(|view| view.page != ThemePage::Controls) {
                paint_theme_chooser(
                    cr,
                    w,
                    h,
                    view,
                    theme,
                    preview_image,
                    preview_error,
                    thumbnails,
                    view.pulse_phase,
                );
                return;
            }
            text(cr, "Done", w - 114.0, 46.0, 90.0, 20.0, style.accent);
            medium(
                cr,
                "Device controls",
                28.0,
                112.0,
                w - 56.0,
                19.0,
                style.muted,
            );
            text(cr, "Themes ›", w - 164.0, 113.0, 140.0, 20.0, style.accent);
            if let Some(settings) = services.and_then(|view| view.settings.as_ref()) {
                for (index, (name, control)) in [
                    ("Wi-Fi ›", &settings.network),
                    ("Brightness", &settings.brightness),
                    ("Keyboard", &settings.keyboard),
                    ("Motion", &settings.motion),
                ]
                .into_iter()
                .enumerate()
                {
                    let y = settings_row_y(index as u32);
                    service_card(cr, theme, "controls", 24.0, y, w - 48.0, SETTINGS_ROW_H, false);
                    text(cr, name, 42.0, y + 15.0, w - 84.0, 17.0, style.accent);
                    text(
                        cr,
                        &control_text(control),
                        42.0,
                        y + 43.0,
                        w - 90.0,
                        19.0,
                        style.text,
                    );
                    if name == "Keyboard" && services.is_some_and(|view| view.keyboard_gesture_hint)
                    {
                        text(
                            cr,
                            "Two fingers up at bottom to show;",
                            42.0,
                            y + 72.0,
                            w - 90.0,
                            14.0,
                            style.muted,
                        );
                        text(
                            cr,
                            "drag the handle down to hide.",
                            42.0,
                            y + 89.0,
                            w - 90.0,
                            14.0,
                            style.muted,
                        );
                    } else if let Some(detail) = &control.detail {
                        text(cr, detail, 42.0, y + 76.0, w - 90.0, 14.0, style.muted);
                    }
                }
                if settings.brightness.state == crate::service_data::ControlState::Writable {
                    text(
                        cr,
                        "−       +",
                        w - 162.0,
                        settings_row_y(1) + 40.0,
                        130.0,
                        25.0,
                        style.accent,
                    );
                }
            } else {
                text(
                    cr,
                    services
                        .and_then(|view| view.settings_error.as_deref())
                        .unwrap_or("Loading settings"),
                    28.0,
                    177.0,
                    w - 56.0,
                    20.0,
                    style.muted,
                );
            }
            // Power heading/actions and the confirm dialog are positioned
            // relative to the row rhythm above (finding P0-4), not as
            // independent literals that stay correct only by coincidence.
            let layout = settings_layout();
            if services.and_then(|view| view.settings.as_ref()).is_some() {
                text(
                    cr,
                    "Power",
                    28.0,
                    layout.power_heading_y,
                    w - 56.0,
                    19.0,
                    style.muted,
                );
                service_card(
                    cr,
                    theme,
                    "controls",
                    24.0,
                    layout.reboot_y,
                    w - 48.0,
                    SETTINGS_POWER_CARD_H,
                    false,
                );
                text(
                    cr,
                    "Reboot…",
                    42.0,
                    layout.reboot_y + 20.0,
                    w - 84.0,
                    23.0,
                    style.text,
                );
                service_card(
                    cr,
                    theme,
                    "controls",
                    24.0,
                    layout.poweroff_y,
                    w - 48.0,
                    SETTINGS_POWER_CARD_H,
                    false,
                );
                text(
                    cr,
                    "Power off…",
                    42.0,
                    layout.poweroff_y + 20.0,
                    w - 84.0,
                    23.0,
                    style.text,
                );
            }
            if let Some(confirm) = services.and_then(|view| view.confirmation.as_ref()) {
                let confirm_layout = settings_confirm_layout(layout.poweroff_bottom);
                text(
                    cr,
                    &confirm.label,
                    28.0,
                    confirm_layout.label_y,
                    w - 56.0,
                    19.0,
                    style.text,
                );
                service_card(
                    cr,
                    theme,
                    "controls",
                    24.0,
                    confirm_layout.card_y,
                    w - 48.0,
                    110.0,
                    true,
                );
                let button_y = confirm_layout.card_y + 33.0;
                text(cr, "Cancel", 45.0, button_y, w / 2.0 - 45.0, 23.0, style.muted);
                text(
                    cr,
                    "Confirm",
                    w / 2.0 + 20.0,
                    button_y,
                    w / 2.0 - 45.0,
                    23.0,
                    style.error,
                );
            }
            if let Some(message) = services.and_then(|view| view.message.as_deref()) {
                let after = services
                    .and_then(|view| view.confirmation.as_ref())
                    .map_or(layout.poweroff_bottom, |_| {
                        settings_confirm_layout(layout.poweroff_bottom).bottom
                    });
                text(cr, message, 28.0, after + 14.0, w - 56.0, 17.0, style.muted);
            }
        }
        Route::Hide => {}
    }
}

fn app_by_id<'a>(apps: &'a [AppEntry], id: &str) -> Option<&'a AppEntry> {
    apps.iter().find(|app| app.id == id)
}

/// Label legibility over any wallpaper (Home has no opaque panel behind it,
/// unlike every other surface this shell paints -- see `paint_home`'s own
/// doc comment): a soft dark shadow pass behind the themed label text, not
/// just the plain themed color alone.
fn shadowed_label(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(size * f64::from(pango::SCALE));
    font.set_weight(pango::Weight::Bold);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
    layout.set_alignment(pango::Alignment::Center);
    layout.set_ellipsize(EllipsizeMode::End);
    color(cr, 0x000000, 0.55);
    cr.move_to(x, y + 1.4);
    pangocairo::functions::show_layout(cr, &layout);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// Paints one icon's rounded "squircle" plate (webOS/iOS-style tile) and its
/// resolved app icon, or an initial-letter fallback matching the drawer's
/// own fallback, centered within the plate. Shared by grid and dock icons,
/// which differ only in plate/icon size and whether a label follows.
/// `pressed` reuses `service_card`'s own selected-state theming for the
/// tap highlight, instead of a separately hand-drawn ring, so a pressed
/// icon picks up exactly the same themed feedback every other tappable
/// surface in this shell already does.
fn paint_icon_plate(
    cr: &Context,
    theme: Option<&AppearanceSnapshot>,
    icons: &mut IconCache,
    app: &AppEntry,
    plate_x: f64,
    plate_y: f64,
    plate_size: f64,
    icon_size: f64,
    pressed: bool,
) {
    let style = visual_style(theme, "launcher");
    // Guards against inheriting a stray current point from whatever was
    // painted just before this tile (see `paint_remove_badge`'s own note):
    // `service_card`'s themed border stroke builds a path via `rounded()`
    // before checking whether its gradient source could actually be set,
    // so a failed `set_source` on one tile could otherwise leave a
    // dangling line into the next.
    cr.new_path();
    service_card(cr, theme, "launcher", plate_x, plate_y, plate_size, plate_size, pressed);
    let icon_x = plate_x + (plate_size - icon_size) / 2.0;
    let icon_y = plate_y + (plate_size - icon_size) / 2.0;
    let painted = app
        .icon
        .as_deref()
        .is_some_and(|icon| icons.paint(cr, icon, icon_size as i32, icon_x, icon_y));
    if !painted {
        let initial = app.name.chars().next().unwrap_or('?').to_uppercase().to_string();
        centered_label(
            cr,
            &initial,
            plate_x,
            plate_y + plate_size / 2.0 - icon_size * 0.27,
            plate_size,
            icon_size * 0.55,
            style.accent,
        );
    }
}

/// Rearrange mode's per-icon remove badge (iOS/webOS's jiggle-mode
/// affordance): a small red circle with a white "remove" bar, anchored at
/// the icon plate's top-left corner. Its drawn size is smaller than its
/// actual hit target (`home_grid::REMOVE_BADGE_HIT_RADIUS`) -- a visually
/// heavier badge would crowd a tightly packed grid, but the tap target
/// underneath it still needs to be finger-sized.
fn paint_remove_badge(cr: &Context, theme: Option<&AppearanceSnapshot>, corner: (f64, f64)) {
    let style = visual_style(theme, "launcher");
    let radius = home_grid::REMOVE_BADGE_RADIUS;
    let (cx, cy) = corner;
    let _ = cr.save();
    // `cairo_arc` draws an implicit connecting line from any leftover
    // current point (e.g. a themed border path a preceding `service_card`
    // call built but never stroked, if its gradient source failed to set)
    // to this arc's start -- an explicit fresh path guarantees this badge
    // never inherits a stray line from whatever was painted just before it.
    cr.new_path();
    cr.arc(cx, cy, radius, 0.0, std::f64::consts::TAU);
    color(cr, style.error, 0.96);
    let _ = cr.fill_preserve();
    color(cr, 0xffffff, 0.9);
    cr.set_line_width(1.5);
    let _ = cr.stroke();
    cr.move_to(cx - radius * 0.45, cy);
    cr.line_to(cx + radius * 0.45, cy);
    cr.set_line_width(2.2);
    cr.set_line_cap(cairo::LineCap::Round);
    color(cr, 0xffffff, 1.0);
    let _ = cr.stroke();
    let _ = cr.restore();
}

/// Rearrange mode's visible drop-target highlight: the whole cell the
/// dragged icon would land on if released right now, not just its own
/// (much smaller) plate, so the target reads clearly at a glance while a
/// finger is covering the icon itself.
fn paint_drop_target(cr: &Context, theme: Option<&AppearanceSnapshot>, rect: (f64, f64, f64, f64)) {
    let style = visual_style(theme, "launcher");
    let (x, y, w, h) = rect;
    cr.new_path();
    rounded(cr, x, y, w, h, 22.0);
    color(cr, style.accent, 0.20);
    let _ = cr.fill_preserve();
    color(cr, style.accent, 0.7);
    cr.set_line_width(2.0);
    let _ = cr.stroke();
}

/// Paints the Home screen: the pinned-icon grid for the pager's current
/// (possibly mid-drag) page, the non-tappable page-count dots, the
/// translucent quick-launch dock, and -- only while `home.rearranging` --
/// the Done/Remove affordances, each filled icon's remove badge, the live
/// drop-target highlight, and any icon currently being dragged.
/// Deliberately paints nothing opaque outside those elements: this surface
/// sits on `Layer::Bottom`, directly above the existing wallpaper layer,
/// and relies on that layer showing through everywhere Home itself has no
/// content -- which is exactly why every label here gets its own shadow
/// pass ([`shadowed_label`]) instead of relying on an opaque backing.
pub fn paint_home(
    cr: &Context,
    width: u32,
    height: u32,
    theme: Option<&AppearanceSnapshot>,
    home: &HomeScreen,
    apps: &[AppEntry],
    icons: &mut IconCache,
) {
    cr.set_operator(Operator::Source);
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.0);
    let _ = cr.paint();
    cr.set_operator(Operator::Over);
    let style = visual_style(theme, "launcher");

    let page_count = home.page_count();
    let position = home.pager.position();
    let page_width = f64::from(width);
    let pressed = home.pressed(width, height);
    let dragged_slot = home.drag.map(|(slot, _)| slot);
    let drop_target = home.drop_target(width, height);
    let show_drop_target = home.rearranging && drop_target.is_some() && drop_target != dragged_slot;
    for offset in [-1i64, 0, 1] {
        let page = position.round() as i64 + offset;
        if page < 0 || page as usize >= page_count {
            continue;
        }
        let page = page as usize;
        let shift = (page as f64 - position) * page_width;
        // Only the two pages nearest the settled position are ever close
        // enough to be on-panel during a drag; skip painting the rest to
        // keep this bounded regardless of how many pages exist.
        if shift.abs() > page_width + 1.0 {
            continue;
        }
        let _ = cr.save();
        cr.translate(shift, 0.0);
        if show_drop_target {
            if let Some(HomeSlot::Grid { page: target_page, slot }) = drop_target {
                if target_page == page {
                    paint_drop_target(cr, theme, home_grid::tile_rect(width, height, slot));
                }
            }
        }
        if let Some(row) = home.layout.pages.get(page) {
            for (slot, entry) in row.iter().enumerate() {
                let Some(id) = entry else { continue };
                let this_slot = HomeSlot::Grid { page, slot };
                if home.drag.is_some_and(|(dragged, _)| dragged == this_slot) {
                    continue; // painted last, floating at the finger instead
                }
                let Some(app) = app_by_id(apps, id) else { continue };
                let content = home_grid::tile_content(width, height, slot);
                paint_icon_plate(
                    cr,
                    theme,
                    icons,
                    app,
                    content.plate_x,
                    content.plate_y,
                    content.plate_size,
                    home_grid::ICON_SIZE,
                    pressed == Some(this_slot),
                );
                shadowed_label(
                    cr,
                    &app.name,
                    content.plate_x,
                    content.label_y,
                    content.plate_size,
                    15.0,
                    brush_rgb(theme, "launcher", "text", style.text),
                );
                if home.rearranging {
                    paint_remove_badge(cr, theme, (content.plate_x, content.plate_y));
                }
            }
        }
        let _ = cr.restore();
    }

    if page_count > 1 {
        let dot_y = home_grid::dots_center_y(height);
        let spacing = 22.0;
        let start_x = f64::from(width) / 2.0 - spacing * (page_count as f64 - 1.0) / 2.0;
        for page in 0..page_count {
            let cx = start_x + spacing * page as f64;
            let active = (position - page as f64).abs() < 0.5;
            if active {
                // The active page reads as a short pill, not just a bigger
                // dot -- a subtle, common refinement over a plain dot row
                // that still costs nothing extra to hit-test (dots are
                // purely decorative; nothing here is tappable).
                rounded(cr, cx - 9.0, dot_y - 3.5, 18.0, 7.0, 3.5);
                color(cr, style.accent, 0.95);
                let _ = cr.fill();
            } else {
                cr.arc(cx, dot_y, 3.5, 0.0, std::f64::consts::TAU);
                color(cr, style.text, 0.38);
                let _ = cr.fill();
            }
        }
    }

    // The dock: a translucent themed tray (matching the "launcher" section's
    // own background/border brushes, exactly like every other floating
    // panel this shell draws via `service_card`) holding its own, visibly
    // larger, unlabeled icon plates -- webOS Quick Launch / Android hotseat
    // convention, not a flat solid-color bar.
    let dock_band = (
        12.0,
        home_grid::dock_top(height) + 6.0,
        f64::from(width) - 24.0,
        f64::from(height) - home_grid::dock_top(height) - 18.0,
    );
    service_card(cr, theme, "launcher", dock_band.0, dock_band.1, dock_band.2, dock_band.3, false);
    for slot in 0..home_grid::DOCK_SLOTS {
        let Some(id) = home.layout.dock.get(slot).and_then(Option::as_deref) else {
            continue;
        };
        let this_slot = HomeSlot::Dock { slot };
        if home.drag.is_some_and(|(dragged, _)| dragged == this_slot) {
            continue;
        }
        let Some(app) = app_by_id(apps, id) else { continue };
        let content = home_grid::dock_content(width, height, slot);
        if show_drop_target && drop_target == Some(this_slot) {
            paint_drop_target(cr, theme, home_grid::dock_rect(width, height, slot));
        }
        paint_icon_plate(
            cr,
            theme,
            icons,
            app,
            content.plate_x,
            content.plate_y,
            content.plate_size,
            home_grid::DOCK_ICON_SIZE,
            pressed == Some(this_slot),
        );
        if home.rearranging {
            paint_remove_badge(cr, theme, (content.plate_x, content.plate_y));
        }
    }

    if home.rearranging {
        let done = home_grid::done_button_rect(width);
        service_card(cr, theme, "controls", done.0, done.1, done.2, done.3, false);
        centered_label(cr, "Done", done.0, done.1 + done.3 / 2.0 - 12.0, done.2, 24.0, style.accent);
        let remove = home_grid::remove_target_rect(width);
        // A drag hovering directly over Remove gets the same "selected"
        // themed treatment as any other armed control in this shell, so the
        // pending delete is obvious before the finger lifts.
        let over_remove = home
            .drag
            .is_some_and(|(_, point)| home_grid::hits(point, remove));
        service_card(cr, theme, "controls", remove.0, remove.1, remove.2, remove.3, over_remove);
        centered_label(cr, "Remove", remove.0, remove.1 + remove.3 / 2.0 - 12.0, remove.2, 24.0, style.error);
    }

    if let Some((slot, point)) = home.drag {
        let id = home.layout.get(slot).map(str::to_string);
        if let Some(id) = id {
            if let Some(app) = app_by_id(apps, &id) {
                // A dragged icon lifts slightly larger than its resting
                // plate (matching iOS/webOS's jiggle-mode "pick up" scale)
                // and always shows its label, regardless of whether it
                // started in the grid or the dock, so what is being moved
                // stays legible under the finger.
                let plate_size = home_grid::ICON_PLATE_SIZE * 1.08;
                let icon_size = home_grid::ICON_SIZE * 1.08;
                let plate_x = point.0 - plate_size / 2.0;
                let plate_y = point.1 - plate_size / 2.0;
                paint_icon_plate(cr, theme, icons, app, plate_x, plate_y, plate_size, icon_size, true);
                shadowed_label(
                    cr,
                    &app.name,
                    plate_x,
                    plate_y + plate_size + 8.0,
                    plate_size,
                    15.0,
                    brush_rgb(theme, "launcher", "text", style.text),
                );
            }
        }
    }
}

pub fn draw_shm(
    canvas: &mut [u8],
    width: u32,
    height: u32,
    route: Route,
    apps: &[AppEntry],
    progress: f64,
) -> Result<(), String> {
    draw_shm_with_icons(
        canvas,
        RenderParams {
            width,
            height,
            route,
            progress,
            scroll: 0.0,
        },
        apps,
        &mut IconCache::new(),
        None,
        None,
        None,
        None,
        false,
        None,
        None,
    )
}

fn draw_shm_with_icons(
    canvas: &mut [u8],
    params: RenderParams,
    apps: &[AppEntry],
    icons: &mut IconCache,
    theme: Option<&AppearanceSnapshot>,
    services: Option<&ServiceView>,
    chooser: Option<&ThemeView>,
    preview_image: Option<&ImageSurface>,
    preview_error: bool,
    thumbnails: Option<&ThemeThumbnailCache>,
    pressed: Option<usize>,
) -> Result<(), String> {
    let RenderParams { width, height, .. } = params;
    let stride = width.checked_mul(4).ok_or("invalid stride")?;
    if canvas.len() != usize::try_from(stride).unwrap_or(usize::MAX) * height as usize {
        return Err("invalid canvas length".into());
    }
    // The Cairo surface and context are dropped before this borrowed SHM
    // canvas can be attached to Wayland. The slice stays allocated throughout.
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(
            canvas.as_mut_ptr(),
            Format::ARgb32,
            width as i32,
            height as i32,
            stride as i32,
        )
    }
    .map_err(|error| error.to_string())?;
    let cr = Context::new(&surface).map_err(|error| error.to_string())?;
    scene(
        &cr,
        params,
        apps,
        icons,
        theme,
        services,
        chooser,
        preview_image,
        preview_error,
        thumbnails,
        pressed,
    );
    drop(cr);
    surface.flush();
    Ok(())
}

/// Renders Home directly into a borrowed SHM canvas -- the `Layer::Bottom`
/// surface's own draw path, parallel to `draw_shm_with_icons` for the
/// Drawer/Shade/Settings overlay above it.
fn draw_home_shm(
    canvas: &mut [u8],
    width: u32,
    height: u32,
    apps: &[AppEntry],
    icons: &mut IconCache,
    theme: Option<&AppearanceSnapshot>,
    home: &HomeScreen,
) -> Result<(), String> {
    let stride = width.checked_mul(4).ok_or("invalid stride")?;
    if canvas.len() != usize::try_from(stride).unwrap_or(usize::MAX) * height as usize {
        return Err("invalid canvas length".into());
    }
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(
            canvas.as_mut_ptr(),
            Format::ARgb32,
            width as i32,
            height as i32,
            stride as i32,
        )
    }
    .map_err(|error| error.to_string())?;
    let cr = Context::new(&surface).map_err(|error| error.to_string())?;
    paint_home(&cr, width, height, theme, home, apps, icons);
    drop(cr);
    surface.flush();
    Ok(())
}

pub fn export_png(
    path: &Path,
    width: u32,
    height: u32,
    route: Route,
    apps: &[AppEntry],
) -> Result<(), String> {
    let surface = ImageSurface::create(Format::ARgb32, width as i32, height as i32)
        .map_err(|error| error.to_string())?;
    let cr = Context::new(&surface).map_err(|error| error.to_string())?;
    scene(
        &cr,
        RenderParams {
            width,
            height,
            route,
            progress: 1.0,
            scroll: 0.0,
        },
        apps,
        &mut IconCache::new(),
        None,
        None,
        None,
        None,
        false,
        None,
        None,
    );
    drop(cr);
    let mut file = File::create(path).map_err(|error| error.to_string())?;
    surface
        .write_to_png(&mut file)
        .map_err(|error| error.to_string())?;
    Ok(())
}

/// A route/geometry/catalog-generation scene is shaped once. Finger updates
/// translate the finished ARGB pixels into a released Wayland SHM canvas.
#[derive(Default)]
pub struct RendererCache {
    route: Option<Route>,
    width: u32,
    height: u32,
    static_pixels: Vec<u8>,
    rebuilds: u64,
    icons: IconCache,
    scroll: f64,
    pressed: Option<usize>,
    theme: Option<AppearanceSnapshot>,
    services: Option<ServiceView>,
    chooser: Option<ThemeView>,
    preview_worker: ThemeImageWorker,
    preview_key: Option<ThemeImageKey>,
    preview_requested: Option<ThemeImageKey>,
    preview_surface: Option<ImageSurface>,
    preview_error: bool,
    thumbnails: ThemeThumbnailCache,
    /// Bumped by every change to `services`/`chooser`/`pressed`/
    /// `preview_surface`/`preview_error`/`thumbnails` -- everything
    /// `render_candidate_overlay` reads from `self` besides the theme it
    /// is explicitly given -- and *only* those. Deliberately not bumped by
    /// `set_appearance`/`set_icon_theme`: those are exactly what a
    /// candidate pre-render is expected to differ from `self.theme` on.
    /// The caller (`ShellClient`'s own optimistic-apply pre-render) reads
    /// this before and after computing a pre-render; a mismatch means
    /// something this render actually depends on changed underneath it,
    /// and the pre-render must be treated as stale.
    content_generation: u64,
}

/// Whether two `ThemeView`s would make the *pre-render freshness check*
/// (`content_generation`, above) treat a computed candidate as stale --
/// deliberately a narrower question than whether `paint_theme_chooser`'s
/// own cached body would actually paint differently. `pending`/
/// `pending_id`/`error`/`message`/`pulse_phase` are excluded on purpose:
/// an Apply tap's own `pending` transition, or the busy spinner's own
/// pulse tick, must not by itself mark a computed pre-render stale (board
/// evidence, 2026-09-28: exactly this was why `optimistic-apply
/// prerendered` was computed twice roughly one pulse interval apart, and
/// still `prerendered=false` at the tap itself). This is safe precisely
/// because none of those excluded fields is what makes the *adopted*
/// pre-render frame correct at the moment it is shown -- see
/// `paint_theme_chooser`'s own doc. `theme_position`/`background_
/// position` use the same small tolerance `RendererCache::draw`'s own
/// `scroll` check already does, so a settle animation converging by a
/// fraction of a pixel does not itself count either.
fn theme_view_cache_key_differs(old: &ThemeView, new: &ThemeView) -> bool {
    old.page != new.page
        || old.list != new.list
        || old.preview != new.preview
        || (old.theme_position - new.theme_position).abs() >= 0.25
        || (old.background_position - new.background_position).abs() >= 0.25
        || old.theme_pressed != new.theme_pressed
        || old.background_pressed != new.background_pressed
}

impl RendererCache {
    pub fn content_generation(&self) -> u64 {
        self.content_generation
    }

    pub fn set_theme_view(&mut self, view: ThemeView) {
        if self
            .chooser
            .as_ref()
            .is_none_or(|old| theme_view_cache_key_differs(old, &view))
        {
            self.content_generation = self.content_generation.wrapping_add(1);
        }
        self.chooser = Some(view);
        // `invalidate()` stays unconditional: a live `draw()` call still
        // rebuilds `static_pixels` on every theme_view change exactly as
        // before this task (correctness for the cached body itself is
        // unaffected by this function; only `content_generation` -- read
        // solely by Optimistic Apply's own pre-render freshness check --
        // is now selective).
        self.invalidate();
    }
    /// Nonblocking dispatch hook. Only a selected staged still is decoded;
    /// the one-entry worker cache and result channel bound memory and work.
    ///
    /// Task: tap-to-apply (2026-09-25) removed the separate Preview page
    /// this fed -- a large "screen crop" still preview of the selected
    /// background, distinct from the small per-slice thumbnails
    /// `ThemeThumbnailCache` already decodes for both carousels on the
    /// one remaining List page. Nothing paints this any more (see
    /// `paint_theme_chooser`'s own doc), so `desired` is now always
    /// `None`: a deliberate no-op that never requests a decode, rather
    /// than wasted background CPU/memory work for a surface nobody shows.
    /// `preview_worker`/`preview_key`/`preview_requested`/
    /// `preview_surface`/`ThemeImageWorker`/`ThemeImageKey` are left in
    /// place rather than torn out in the same change; a follow-up can
    /// remove this whole method and its fields outright.
    pub fn poll_theme_image(&mut self, _width: u32, _height: u32) -> bool {
        let desired: Option<ThemeImageKey> = None;
        let mut changed = false;
        if desired != self.preview_key {
            self.preview_key = desired.clone();
            self.preview_surface = None;
            self.preview_error = false;
            self.invalidate();
            changed = true;
        }
        for _ in 0..2 {
            let Some(reply) = self.preview_worker.try_recv() else {
                break;
            };
            if self.preview_requested.as_ref() == Some(&reply.key) {
                self.preview_requested = None;
            }
            if self.preview_key.as_ref() != Some(&reply.key) {
                continue; // Cancelled preview or another generation won.
            }
            let pixels = match reply.pixels {
                Ok(pixels) => Some(pixels),
                Err(_) => None,
            };
            self.preview_surface = pixels.and_then(|pixels| {
                ImageSurface::create_for_data(
                    pixels,
                    Format::ARgb32,
                    reply.key.width as i32,
                    reply.key.height as i32,
                    (reply.key.width * 4) as i32,
                )
                .ok()
            });
            self.preview_error = self.preview_surface.is_none();
            self.invalidate();
            changed = true;
        }
        if let Some(key) = desired.as_ref() {
            if self.preview_surface.is_none()
                && !self.preview_error
                && self.preview_requested.as_ref() != Some(key)
                && self.preview_worker.try_request(key.clone())
            {
                self.preview_requested = Some(key.clone());
            }
        }
        if changed {
            self.content_generation = self.content_generation.wrapping_add(1);
        }
        changed
    }
    /// Requests both cached-bitmap variants (see `theme_thumbnails.rs`) for
    /// every carousel entry within `theme_carousel::NEARBY_LIMIT` of the
    /// carousel's current position: each nearby catalog entry with preview
    /// art while the list page is open, or each nearby still background
    /// while the preview page is open. Unlike the single live wallpaper
    /// preview above, these bitmaps are cached forever once decoded, so
    /// re-requesting an already-ready (id, variant) is a no-op
    /// (`ThemeThumbnailCache::request`); only newly-nearby entries actually
    /// queue a decode.
    pub fn poll_theme_thumbnails(&mut self) -> bool {
        let changed = self.thumbnails.poll();
        if changed {
            self.content_generation = self.content_generation.wrapping_add(1);
            self.invalidate();
        }
        let Some(chooser) = self.chooser.as_ref() else {
            return changed;
        };
        match chooser.page {
            ThemePage::List => {
                // Theme and background thumbnails are requested
                // independently below -- neither `chooser.list` nor
                // `chooser.preview` being absent should skip the other
                // (board evidence would otherwise show a background
                // carousel that never gets its own art whenever its own
                // detail loads before, or without, a fresh theme list).
                if let Some(list) = chooser.list.as_ref() {
                // `visible_slices` is sorted ascending by paint z-order --
                // farthest neighbor first, the centered slice last -- which
                // is the right order to *paint* (so the centered slice ends
                // up on top) but the wrong order to *request decodes* in:
                // the bounded worker queue (`theme_thumbnails::QUEUE`) means
                // whichever ids get `request()`-ed first each frame claim
                // its few slots, so painting order left the one slice a
                // user actually sees at rest -- the centered one -- decoding
                // *last* of every nearby id. That went unnoticed at the
                // smaller pre-hero size (every decode was fast enough not to
                // matter); the Themes hero's much larger `Expanded` bitmap
                // makes a single decode slow enough under software
                // (Pixman/Cairo, no GPU) decode that request order is worth
                // getting right. `.rev()` here requests centered-outward
                // instead, with no effect on `paint_carousel`'s own separate
                // (unreversed) call to `visible_slices` for paint order.
                for slice in theme_carousel::visible_slices(
                    &theme_carousel::THEME_GEOMETRY,
                    chooser.theme_position,
                    list.themes.len(),
                    0.0,
                    0.0,
                )
                .into_iter()
                .rev()
                {
                    let Some(entry) = list.themes.get(slice.index) else {
                        continue;
                    };
                    if let Some(path) = &entry.preview_path {
                        for variant in [Variant::Expanded, Variant::Slice] {
                            let (width, height) =
                                variant_size(&theme_carousel::THEME_GEOMETRY, variant);
                            self.thumbnails.request(ThumbnailKey {
                                id: entry.id.clone(),
                                path: path.clone(),
                                variant,
                                width,
                                height,
                            });
                        }
                    }
                }
                }
                // Task: tap-to-apply (2026-09-25) put the active theme's own
                // background carousel on this same List page, below the
                // theme carousel -- its nearby thumbnails are requested
                // here too now, rather than only while a now-removed
                // separate Preview page was open. Independent of the
                // `list` block above -- see this function's own doc.
                if let Some(preview) = chooser.preview.as_ref() {
                    for slice in theme_carousel::visible_slices(
                        &theme_carousel::BACKGROUND_GEOMETRY,
                        chooser.background_position,
                        preview.backgrounds.len(),
                        0.0,
                        0.0,
                    )
                    .into_iter()
                    .rev()
                    {
                        let Some(background) = preview.backgrounds.get(slice.index) else {
                            continue;
                        };
                        if background.kind == BackgroundKind::Image {
                            for variant in [Variant::Expanded, Variant::Slice] {
                                let (width, height) =
                                    variant_size(&theme_carousel::BACKGROUND_GEOMETRY, variant);
                                self.thumbnails.request(ThumbnailKey {
                                    id: background.id.clone(),
                                    path: background.path.clone(),
                                    variant,
                                    width,
                                    height,
                                });
                            }
                        }
                    }
                }
            }
            ThemePage::Controls => {}
        }
        changed
    }

    /// Whether some carousel slice within `theme_carousel::NEARBY_LIMIT`
    /// still has an unresolved bitmap (queued, or dropped by a full worker
    /// queue and waiting on a future `poll_theme_thumbnails` retry).
    ///
    /// This says only whether the event loop should keep *polling*
    /// (`main.rs` shortens its `libc::poll` timeout while this is true, so a
    /// completed decode is drained promptly) -- it must never by itself
    /// force a redraw. `poll_theme_thumbnails` is already called
    /// unconditionally every loop iteration regardless of this value, so
    /// retries and channel draining happen either way; only its own
    /// `changed` return value (a decode actually completed, or one of this
    /// module's caches actually changed) should ever set `dirty`. A caller
    /// that instead redraws a fully unchanged frame just because this is
    /// true is the idle-redraw bug this doc used to justify: a continuous
    /// full re-render at rest while thumbnails were still decoding,
    /// competing for the same single core the decode itself needed. The
    /// loading spinner this module's caller paints for a pending slice
    /// (`render.rs::paint_carousel`) is instead animated by `ThemeView::
    /// pulse_phase`, advanced on `main.rs`'s own throttled cadence.
    pub fn theme_thumbnails_pending(&self) -> bool {
        let Some(chooser) = self.chooser.as_ref() else {
            return false;
        };
        match chooser.page {
            ThemePage::List => {
                let themes_pending = chooser.list.as_ref().is_some_and(|list| {
                    theme_carousel::visible_slices(
                        &theme_carousel::THEME_GEOMETRY,
                        chooser.theme_position,
                        list.themes.len(),
                        0.0,
                        0.0,
                    )
                    .into_iter()
                    .filter_map(|slice| list.themes.get(slice.index))
                    .filter(|entry| entry.preview_path.is_some())
                    .any(|entry| {
                        !self.thumbnails.is_resolved(&entry.id, Variant::Expanded)
                            || !self.thumbnails.is_resolved(&entry.id, Variant::Slice)
                    })
                });
                // Task: tap-to-apply (2026-09-25) -- the active theme's own
                // background carousel sits on this same page now; its
                // nearby thumbnails count toward "still decoding" too.
                let backgrounds_pending = chooser.preview.as_ref().is_some_and(|preview| {
                    theme_carousel::visible_slices(
                        &theme_carousel::BACKGROUND_GEOMETRY,
                        chooser.background_position,
                        preview.backgrounds.len(),
                        0.0,
                        0.0,
                    )
                    .into_iter()
                    .filter_map(|slice| preview.backgrounds.get(slice.index))
                    .filter(|background| background.kind == BackgroundKind::Image)
                    .any(|background| {
                        !self.thumbnails.is_resolved(&background.id, Variant::Expanded)
                            || !self.thumbnails.is_resolved(&background.id, Variant::Slice)
                    })
                });
                themes_pending || backgrounds_pending
            }
            ThemePage::Controls => false,
        }
    }

    /// Always `false` now: `poll_theme_image` (above) is a deliberate
    /// no-op since task: tap-to-apply (2026-09-25) removed the separate
    /// Preview page its single "Selected background" still image used to
    /// feed. Kept, rather than removed, only so `main.rs`'s existing
    /// pulse-gating call sites need no further change.
    pub fn theme_preview_image_pending(&self) -> bool {
        false
    }

    pub fn set_services(&mut self, services: ServiceView) {
        self.services = Some(services);
        self.content_generation = self.content_generation.wrapping_add(1);
        self.invalidate();
    }
    pub fn set_drawer_pressed(&mut self, pressed: Option<usize>) -> bool {
        if self.pressed != pressed {
            self.pressed = pressed;
            self.content_generation = self.content_generation.wrapping_add(1);
            self.invalidate();
            return true;
        }
        false
    }
    pub fn set_appearance(&mut self, theme: Option<AppearanceSnapshot>) {
        let name = icon_theme_name_for(theme.as_ref());
        self.icons.set_theme(&name);
        self.theme = theme;
        self.invalidate();
    }
    pub fn invalidate(&mut self) {
        self.route = None;
        self.static_pixels.clear();
    }

    pub fn rebuild_count(&self) -> u64 {
        self.rebuilds
    }

    pub fn set_icon_theme(&mut self, theme: &str) {
        self.icons.set_theme(theme);
        self.invalidate();
    }

    /// Renders the full overlay/settings scene *for `theme`* -- which need
    /// not be, and for the optimistic-apply pre-render never is, `self`'s
    /// own live `self.theme` -- entirely off `self`'s own persistent cache
    /// (`static_pixels`/`route`/`self.icons`): a fresh `IconCache` pays its
    /// own lazy icon-decode cost independently, and nothing here is
    /// written back to `self`. Every *other* input `draw_shm_with_icons`
    /// needs (`services`/`chooser`/`pressed`/`preview_surface`/
    /// `preview_error`/`thumbnails`) is read live from `self`, which is
    /// exactly what makes this safe to call well ahead of when `theme`
    /// might actually be applied: the caller records `content_generation()`
    /// alongside the result, and must discard it once that counter no
    /// longer matches (see `content_generation`'s own doc) rather than
    /// re-checking every one of these fields itself.
    pub fn render_candidate_overlay(
        &self,
        theme: Option<&AppearanceSnapshot>,
        route: Route,
        width: u32,
        height: u32,
        apps: &[AppEntry],
    ) -> Result<Vec<u8>, String> {
        let size = usize::try_from(width)
            .ok()
            .and_then(|w| w.checked_mul(height as usize))
            .and_then(|pixels| pixels.checked_mul(4))
            .ok_or("invalid candidate overlay geometry")?;
        let mut icons = IconCache::new();
        icons.set_theme(&icon_theme_name_for(theme));
        let mut pixels = vec![0u8; size];
        draw_shm_with_icons(
            &mut pixels,
            RenderParams {
                width,
                height,
                route,
                progress: 1.0,
                // `draw()`'s own rebuild call always passes 0.0 here for
                // every route but Drawer (`self.nav.scroll` otherwise);
                // Optimistic Apply's pre-render only ever targets
                // `Route::Settings` (the theme chooser's own route), so
                // this matches exactly, deliberately, rather than reading
                // `self.scroll`, which could still hold a stale Drawer
                // value while Settings is the live route.
                scroll: 0.0,
            },
            apps,
            &mut icons,
            theme,
            self.services.as_ref(),
            self.chooser.as_ref(),
            self.preview_surface.as_ref(),
            self.preview_error,
            Some(&self.thumbnails),
            self.pressed,
        )?;
        // Matches `draw()`'s own post-shift backdrop pass exactly (same
        // `progress: 1.0` this bake just used), so a later `adopt_
        // prerendered_overlay` of these bytes is indistinguishable from a
        // fresh `draw()` at rest -- see `apply_tray_backdrop`'s own doc.
        apply_tray_backdrop(&mut pixels, route, 1.0);
        Ok(pixels)
    }

    /// Adopts an overlay raster `render_candidate_overlay` already
    /// computed, as though it had just been rebuilt normally -- the
    /// counterpart to that method's own doc: the caller has already
    /// checked `content_generation()` still matches what it was when the
    /// raster was computed. `draw()`'s own next call then sees
    /// `self.route`/`width`/`height`/`scroll` all already matching and
    /// takes its cheap cached-shift-and-copy path instead of rebuilding.
    pub fn adopt_prerendered_overlay(
        &mut self,
        theme: Option<AppearanceSnapshot>,
        route: Route,
        width: u32,
        height: u32,
        pixels: Vec<u8>,
    ) {
        self.icons.set_theme(&icon_theme_name_for(theme.as_ref()));
        self.theme = theme;
        self.static_pixels = pixels;
        self.route = Some(route);
        self.width = width;
        self.height = height;
        self.scroll = 0.0;
    }

    /// Full-output opaque scene behind Sway's live deck. The selected still
    /// image, when available, is composited by the wallpaper layer owner.
    pub fn draw_wallpaper(&self, canvas: &mut [u8], width: u32, height: u32) -> Result<(), String> {
        let size = usize::try_from(width)
            .ok()
            .and_then(|w| w.checked_mul(height as usize))
            .and_then(|pixels| pixels.checked_mul(4))
            .ok_or("invalid wallpaper geometry")?;
        if canvas.len() != size {
            return Err("invalid wallpaper canvas".into());
        }
        let surface = unsafe {
            ImageSurface::create_for_data_unsafe(
                canvas.as_mut_ptr(),
                Format::ARgb32,
                width as i32,
                height as i32,
                (width * 4) as i32,
            )
        }
        .map_err(|e| e.to_string())?;
        let cr = Context::new(&surface).map_err(|e| e.to_string())?;
        cr.set_operator(Operator::Source);
        color(
            &cr,
            palette_rgb_or(self.theme.as_ref(), "background", 0x1e1e2e),
            1.0,
        );
        cr.paint().map_err(|e| e.to_string())?;
        cr.set_operator(Operator::Over);
        if let Some(brush) = theme_brush(self.theme.as_ref(), "launcher", "background") {
            let _ = fill_brush(&cr, brush, 0.0, 0.0, width as f64, height as f64);
        }
        drop(cr);
        surface.flush();
        Ok(())
    }

    pub fn draw(
        &mut self,
        canvas: &mut [u8],
        params: RenderParams,
        apps: &[AppEntry],
    ) -> Result<(), String> {
        let RenderParams {
            width,
            height,
            route,
            progress,
            scroll,
        } = params;
        let size = usize::try_from(width)
            .ok()
            .and_then(|w| w.checked_mul(height as usize))
            .and_then(|pixels| pixels.checked_mul(4))
            .ok_or("invalid cache geometry")?;
        if canvas.len() != size {
            return Err("invalid canvas length".into());
        }
        self.poll_theme_image(width, height);
        self.poll_theme_thumbnails();
        if self.route != Some(route)
            || self.width != width
            || self.height != height
            || (self.scroll - scroll).abs() >= 0.25
        {
            let mut painted = vec![0; size];
            draw_shm_with_icons(
                &mut painted,
                RenderParams {
                    progress: 1.0,
                    ..params
                },
                apps,
                &mut self.icons,
                self.theme.as_ref(),
                self.services.as_ref(),
                self.chooser.as_ref(),
                self.preview_surface.as_ref(),
                self.preview_error,
                Some(&self.thumbnails),
                self.pressed,
            )?;
            self.static_pixels = painted;
            self.width = width;
            self.height = height;
            self.route = Some(route);
            self.scroll = scroll;
            self.rebuilds += 1;
        }
        canvas.fill(0);
        let panel_height = if route == Route::Shade {
            f64::from(height) * 0.65
        } else {
            f64::from(height) * if route == Route::Drawer { 0.81 } else { 1.0 }
        };
        let hidden = 1.0 - progress.clamp(0.0, 1.0);
        let shift =
            (hidden * panel_height).round() as i32 * if route == Route::Drawer { 1 } else { -1 };
        let row_bytes = width as usize * 4;
        for source_y in 0..height as i32 {
            let target_y = source_y + shift;
            if target_y < 0 || target_y >= height as i32 {
                continue;
            }
            let source = source_y as usize * row_bytes;
            let target = target_y as usize * row_bytes;
            canvas[target..target + row_bytes]
                .copy_from_slice(&self.static_pixels[source..source + row_bytes]);
        }
        apply_tray_backdrop(canvas, route, progress);
        // Task: tap-to-apply (2026-09-25) removed the Preview page's own
        // Apply/Cancel footer entirely, along with the live-overlay paint
        // that used to keep it correct on top of a cached/pre-rendered
        // body (`paint_preview_footer_status`, removed the same task).
        // The single List page's own busy spinner and pending/error/
        // message line are baked straight into `static_pixels` by the
        // ordinary rebuild above instead: `set_theme_view` still calls
        // `invalidate()` unconditionally on every `ThemeView` change, so
        // nothing here needs a second, live paint pass any more. See
        // `paint_theme_chooser`'s own doc for why an *adopted* pre-render
        // (the one case that skips a fresh rebuild) is still correct at
        // the exact moment it is shown.
        Ok(())
    }

    /// Renders Home's `Layer::Bottom` surface. Unlike [`Self::draw`], there
    /// is no reveal-progress slide-in to cache/shift here -- Home is always
    /// mapped, its own pager/drag animation already lives in `HomeScreen`,
    /// and this simply repaints straight into the caller's buffer whenever
    /// `main.rs` decides Home is dirty.
    pub fn draw_home(
        &mut self,
        canvas: &mut [u8],
        width: u32,
        height: u32,
        apps: &[AppEntry],
        home: &HomeScreen,
    ) -> Result<(), String> {
        draw_home_shm(canvas, width, height, apps, &mut self.icons, self.theme.as_ref(), home)
    }
}

#[cfg(test)]
mod layout_tests {
    use super::*;

    #[test]
    fn settings_row_y_uses_one_height_and_one_gap() {
        assert_eq!(settings_row_y(0), 162.0);
        assert_eq!(settings_row_y(1), 288.0);
        assert_eq!(settings_row_y(2), 414.0);
        assert_eq!(settings_row_y(3), 540.0);
    }

    #[test]
    fn settings_rows_bottom_is_the_last_row_end() {
        assert_eq!(settings_rows_bottom(0), SETTINGS_ROW_FIRST_Y);
        assert_eq!(settings_rows_bottom(1), 272.0);
        assert_eq!(settings_rows_bottom(4), 650.0);
    }

    #[test]
    fn settings_layout_cascades_from_the_row_rhythm() {
        let layout = settings_layout();
        assert_eq!(layout.power_heading_y, 672.0);
        assert_eq!(layout.reboot_y, 700.0);
        assert_eq!(layout.poweroff_y, 786.0);
        assert_eq!(layout.poweroff_bottom, 856.0);
    }

    #[test]
    fn settings_confirm_layout_follows_whatever_precedes_it() {
        let confirm = settings_confirm_layout(856.0);
        assert_eq!(confirm.label_y, 870.0);
        assert_eq!(confirm.card_y, 898.0);
        assert_eq!(confirm.bottom, 1008.0);
    }

    #[test]
    fn content_sized_panel_h_clamps_short_and_long_content() {
        // Short content still reads as a panel, not a sliver.
        assert_eq!(content_sized_panel_h(300.0, 1232.0, 500.0), 500.0);
        // Ordinary content is used as-is.
        assert_eq!(content_sized_panel_h(900.0, 1232.0, 500.0), 900.0);
        // Content taller than the screen never overflows it.
        assert_eq!(content_sized_panel_h(4000.0, 1232.0, 500.0), 1232.0);
        // The available height doubles as a hard cap even below the minimum,
        // so a panel is never asked to be taller than the screen itself.
        assert_eq!(content_sized_panel_h(300.0, 400.0, 500.0), 400.0);
    }

    #[test]
    fn tray_backdrop_alpha_is_zero_closed_and_target_open() {
        assert_eq!(tray_backdrop_alpha(0.0, 0.35), 0.0);
        assert_eq!(tray_backdrop_alpha(1.0, 0.35), 0.35);
        // Progress is a fraction; anything outside [0, 1] clamps rather than
        // over/undershooting the backdrop (a settle overshoot must never
        // pop past the authored target or go negative).
        assert_eq!(tray_backdrop_alpha(-0.4, 0.35), 0.0);
        assert_eq!(tray_backdrop_alpha(1.4, 0.35), 0.35);
    }

    #[test]
    fn tray_backdrop_alpha_is_monotonic_in_progress() {
        let samples: Vec<f64> = (0..=20)
            .map(|step| tray_backdrop_alpha(f64::from(step) / 20.0, 0.35))
            .collect();
        for pair in samples.windows(2) {
            assert!(
                pair[1] >= pair[0],
                "alpha must never decrease as the tray reveals further: {samples:?}"
            );
        }
    }

    #[test]
    fn tray_backdrop_alpha_eases_in_and_out_around_the_midpoint() {
        // Smoothstep (3p^2 - 2p^3) is symmetric about p=0.5 and flatter than
        // linear near both ends -- an ease-in-out, not a pop or a straight
        // ramp. Exactly half of the target at the midpoint...
        let mid = tray_backdrop_alpha(0.5, 0.35);
        assert!((mid - 0.175).abs() < 1e-9);
        // ...and below the linear diagonal near the start (slow ease-in)
        // and above it near the end (slow ease-out into full alpha).
        let near_start = tray_backdrop_alpha(0.1, 0.35);
        assert!(near_start < 0.35 * 0.1);
        let near_end = tray_backdrop_alpha(0.9, 0.35);
        assert!(near_end > 0.35 * 0.9);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::appearance::{BrushStop, PaletteColor, PaletteValue};
    use crate::service_data::{
        Control, ControlState, NotificationEvent, NotificationPreview, NotificationSnapshot,
        Priority, SettingsSnapshot,
    };
    use crate::service_ui::NotificationSwipe;
    use crate::theme_catalog::{
        ActiveTheme, BackgroundChoice, Compatibility, ThemeEntry, ThemeList, ThemeOrigin,
        ThemePreview, ThemeRequest,
    };
    use std::collections::BTreeMap;
    use std::path::PathBuf;

    // Host-only visual review reads the actual immutable generation emitted by
    // `theme_activate.py --prepare-only`; production parsing stays in appearance.rs.
    fn visual_generation(path: &Path) -> AppearanceSnapshot {
        let appearance: serde_json::Value =
            serde_json::from_slice(&std::fs::read(path.join("appearance.json")).unwrap()).unwrap();
        let report: serde_json::Value =
            serde_json::from_slice(&std::fs::read(path.join("report.json")).unwrap()).unwrap();
        let generation = path.file_name().unwrap().to_str().unwrap();
        assert_eq!(appearance["generation"].as_str(), Some(generation));
        assert_eq!(report["generation"].as_str(), Some(generation));
        let palette = report["palette"]
            .as_object()
            .unwrap()
            .iter()
            .filter_map(|(key, value)| {
                let hex = value.as_str()?.strip_prefix('#')?;
                if hex.len() != 6 {
                    return None;
                }
                let number = u32::from_str_radix(hex, 16).ok()?;
                Some((
                    key.clone(),
                    PaletteValue::Color(PaletteColor {
                        red: (number >> 16) as u8,
                        green: (number >> 8) as u8,
                        blue: number as u8,
                        alpha: 255,
                    }),
                ))
            })
            .collect();
        let sections = appearance["sections"]
            .as_object()
            .unwrap()
            .iter()
            .map(|(section, values)| {
                let tokens = values
                    .as_object()
                    .unwrap()
                    .iter()
                    .filter_map(|(key, value)| {
                        let token = match value["kind"].as_str()? {
                            "brush" => AppearanceToken::Brush(Brush {
                                stops: value["stops"]
                                    .as_array()?
                                    .iter()
                                    .map(|stop| BrushStop {
                                        offset: stop["offset"].as_f64().unwrap(),
                                        argb: stop["argb"].as_str().unwrap().into(),
                                    })
                                    .collect(),
                                angle_degrees: value["angle_degrees"].as_f64().unwrap(),
                                alpha: value["alpha"].as_f64().unwrap(),
                            }),
                            "number" => AppearanceToken::Number(value["value"].as_f64()?),
                            _ => return None,
                        };
                        Some((key.clone(), token))
                    })
                    .collect();
                (section.clone(), tokens)
            })
            .collect();
        AppearanceSnapshot {
            generation: generation.into(),
            path: path.into(),
            icon_theme: appearance["icon_theme"].as_str().map(str::to_owned),
            background: None,
            selected_background: None,
            backgrounds: vec![],
            palette,
            sections,
            applied: vec![],
            unavailable: vec![],
            unknown: vec![],
        }
    }

    #[test]
    fn themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles() {
        let brush = |first: &str, second: &str| {
            AppearanceToken::Brush(Brush {
                stops: vec![
                    BrushStop {
                        offset: 0.0,
                        argb: first.into(),
                    },
                    BrushStop {
                        offset: 1.0,
                        argb: second.into(),
                    },
                ],
                angle_degrees: 35.0,
                alpha: 1.0,
            })
        };
        let palette_color = |red, green, blue| {
            PaletteValue::Color(PaletteColor {
                red,
                green,
                blue,
                alpha: 255,
            })
        };
        let mut snapshot = AppearanceSnapshot {
            generation: "0123456789abcdef01234567".into(),
            path: "/tmp/public-visual-fixture".into(),
            icon_theme: None,
            background: None,
            selected_background: None,
            backgrounds: vec![],
            palette: BTreeMap::from([
                ("foreground".into(), palette_color(244, 247, 248)),
                ("muted".into(), palette_color(192, 206, 218)),
                ("accent".into(), palette_color(255, 194, 122)),
                ("red".into(), palette_color(244, 145, 130)),
            ]),
            sections: BTreeMap::from([
                (
                    "launcher".into(),
                    BTreeMap::from([
                        ("background".into(), brush("#ff172738", "#ff27394e")),
                        (
                            "selected-background".into(),
                            brush("#ff304d60", "#ff3c5264"),
                        ),
                        ("border".into(), brush("#ff78d7cb", "#ffffc27a")),
                        ("selected-border".into(), brush("#ffffc27a", "#ff78d7cb")),
                        ("text".into(), brush("#fff4f7f8", "#fff4f7f8")),
                        ("selected-text".into(), brush("#ffffc27a", "#ffffc27a")),
                    ]),
                ),
                (
                    "menu".into(),
                    BTreeMap::from([
                        ("background".into(), brush("#ff263946", "#ff314b59")),
                        ("border".into(), brush("#ff78d7cb", "#ffffc27a")),
                        ("text".into(), brush("#fff4f7f8", "#fff4f7f8")),
                    ]),
                ),
                (
                    "notifications".into(),
                    BTreeMap::from([
                        ("background".into(), brush("#ff172738", "#ff27394e")),
                        ("border".into(), brush("#ff78d7cb", "#ffffc27a")),
                        ("text".into(), brush("#fff4f7f8", "#fff4f7f8")),
                        ("countdown".into(), brush("#ffffc27a", "#ffffc27a")),
                    ]),
                ),
                (
                    "controls".into(),
                    BTreeMap::from([
                        ("normal-color".into(), brush("#ffb8d6e1", "#ffb8d6e1")),
                        ("normal-fill-alpha".into(), AppearanceToken::Number(0.10)),
                        ("selected-fill-alpha".into(), AppearanceToken::Number(0.22)),
                        ("selected-border".into(), brush("#ff78d7cb", "#ffffc27a")),
                    ]),
                ),
                (
                    "image-picker".into(),
                    BTreeMap::from([
                        ("text".into(), brush("#fff4f7f8", "#fff4f7f8")),
                        ("selected-border".into(), brush("#ff78d7cb", "#ffffc27a")),
                    ]),
                ),
            ]),
            applied: vec![],
            unavailable: vec![],
            unknown: vec![],
        };
        if let Some(path) = std::env::var_os("K230_VISUAL_GENERATION_DIR") {
            snapshot = visual_generation(Path::new(&path));
        }
        let apps = vec![
            AppEntry {
                id: "fixture.desktop".into(),
                name: "Terminal".into(),
                icon: Some("terminal-app".into()),
            },
            AppEntry {
                id: "monitor.desktop".into(),
                name: "Monitor".into(),
                icon: Some("system-monitor-app".into()),
            },
            AppEntry {
                id: "video.desktop".into(),
                name: "Video".into(),
                icon: None,
            },
            AppEntry {
                id: "files.desktop".into(),
                name: "Files".into(),
                icon: None,
            },
            AppEntry {
                id: "editor.desktop".into(),
                name: "Editor".into(),
                icon: None,
            },
            AppEntry {
                id: "help.desktop".into(),
                name: "Help".into(),
                icon: None,
            },
            AppEntry {
                id: "foot-server.desktop".into(),
                name: "Foot Server".into(),
                icon: None,
            },
        ];
        let unavailable = Control {
            state: ControlState::Unavailable,
            value: None,
            label: "Unavailable".into(),
            detail: Some("Open setup to continue".into()),
            action: None,
        };
        let services = ServiceView {
            settings: Some(SettingsSnapshot {
                network: unavailable.clone(),
                brightness: unavailable.clone(),
                keyboard: unavailable.clone(),
                motion: unavailable,
            }),
            notifications: Some(NotificationSnapshot {
                count: 1,
                preview: Some(NotificationPreview {
                    id: 1,
                    source: "System".into(),
                    icon: Some("system-settings".into()),
                    summary: "Connection needs attention".into(),
                    priority: Priority::Important,
                    ongoing: false,
                }),
                events: vec![NotificationEvent {
                    id: 1,
                    source: "System".into(),
                    icon: Some("system-settings".into()),
                    summary: "Connection needs attention".into(),
                    body: "Open Settings for details".into(),
                    priority: Priority::Important,
                    timestamp: 0,
                    error: None,
                    dismissible: true,
                    action_available: false,
                }],
            }),
            ..ServiceView::default()
        };
        let actual_report: Option<serde_json::Value> =
            std::fs::read(snapshot.path.join("report.json"))
                .ok()
                .and_then(|bytes| serde_json::from_slice(&bytes).ok());
        let theme_id = actual_report
            .as_ref()
            .and_then(|report| report["name"].as_str())
            .unwrap_or("fixture-night");
        let theme_label = if theme_id == "catppuccin-latte" {
            "Catppuccin Latte"
        } else if theme_id == "catppuccin" {
            "Catppuccin"
        } else {
            "Fixture Night"
        };
        let preview_palette = ["accent", "background", "foreground"]
            .into_iter()
            .filter_map(|key| {
                snapshot.palette_color(key).map(|value| {
                    (
                        key.into(),
                        format!("#{:02x}{:02x}{:02x}", value.red, value.green, value.blue),
                    )
                })
            })
            .collect();
        let background_id = actual_report
            .as_ref()
            .and_then(|report| report["selected_background"].as_str())
            .unwrap_or("fixture-still");
        let background_label = Path::new(background_id)
            .file_name()
            .unwrap()
            .to_string_lossy()
            .to_string();
        // Exercise the same per-theme thumbnail path a real generation
        // takes: the theme's staged background, when one is actually on
        // disk (K230_VISUAL_GENERATION_DIR fixtures), else no thumbnail.
        let preview_path = snapshot
            .path
            .join("theme")
            .join(background_id)
            .canonicalize()
            .ok();
        let theme_entry = ThemeEntry {
            id: theme_id.into(),
            name: theme_label.into(),
            label: theme_label.into(),
            origin: ThemeOrigin::Builtin,
            preview_path,
        };
        // Task: tap-to-apply (2026-09-25) folded the separate Preview
        // page's own background carousel into this same view
        // (`ThemeView::preview`, now the *active* theme's own detail
        // shown alongside the theme carousel, not a distinct page).
        let chooser = ThemeView {
            page: ThemePage::List,
            list: Some(ThemeList {
                themes: vec![
                    theme_entry.clone(),
                    ThemeEntry {
                        id: "fixture-dawn".into(),
                        name: "Fixture Dawn".into(),
                        label: "Fixture Dawn".into(),
                        origin: ThemeOrigin::User,
                        preview_path: None,
                    },
                ],
                active: ActiveTheme {
                    id: Some(theme_entry.id.clone()),
                    generation: None,
                },
            }),
            preview: Some(ThemePreview {
                theme: theme_entry,
                generation: snapshot.generation.clone(),
                appearance_path: snapshot.path.join("appearance.json"),
                palette: preview_palette,
                icon_theme: snapshot.icon_theme.clone(),
                backgrounds: vec![BackgroundChoice {
                    id: background_id.into(),
                    label: background_label,
                    kind: BackgroundKind::Image,
                    path: snapshot.path.join("theme").join(background_id),
                    selected: true,
                    decode_status: "fixture".into(),
                }],
                compatibility: Compatibility {
                    applied: vec!["shell".into()],
                    unavailable: vec![],
                    unknown: vec![],
                },
                activated: false,
                app_appearance: None,
            }),
            ..ThemeView::default()
        };
        let mut renderer = RendererCache::default();
        renderer.set_services(services);
        renderer.set_appearance(Some(snapshot));
        let output = std::env::var_os("K230_VISUAL_FIXTURE_DIR").map(std::path::PathBuf::from);
        if let Some(directory) = &output {
            std::fs::create_dir_all(directory).unwrap();
        }
        for (name, route, theme_view) in [
            ("drawer", Route::Drawer, None),
            ("shade", Route::Shade, None),
            ("settings", Route::Settings, None),
            // Task: tap-to-apply (2026-09-25) merged the old "themes"
            // (theme carousel only) and "preview" (background carousel
            // only, its own separate page) fixtures into this one --
            // `chooser` now carries both the theme list and the active
            // theme's own background detail at once.
            ("themes", Route::Settings, Some(chooser)),
        ] {
            if let Some(view) = theme_view {
                renderer.set_theme_view(view);
            }
            // `K230_VISUAL_REQUIRE_BACKGROUND` used to require the
            // separate Preview page's own full-image still decode to
            // finish before capturing that fixture; task: tap-to-apply
            // (2026-09-25) removed that page and made `poll_theme_image`
            // a permanent no-op (see its own doc), so nothing here still
            // waits on a decode -- both carousels' own thumbnails
            // (`thumbnails.request`) render synchronously as fixture
            // artwork or a placeholder either way, exactly like every
            // other route captured in this same loop.
            let mut frame = vec![0; 568 * 1232 * 4];
            renderer
                .draw(
                    &mut frame,
                    RenderParams {
                        width: 568,
                        height: 1232,
                        route,
                        progress: 1.0,
                        scroll: 0.0,
                    },
                    &apps,
                )
                .unwrap();
            assert_eq!(frame.len(), 568 * 1232 * 4);
            if route == Route::Drawer {
                assert_eq!(
                    frame[(600 * 568 + 10) * 4 + 3],
                    255,
                    "drawer panel must be opaque after theme composition"
                );
                assert_eq!(
                    &frame[0..4],
                    &[0, 0, 0, 0],
                    "live deck stays visible above drawer"
                );
            }
            if let Some(directory) = &output {
                let surface = unsafe {
                    ImageSurface::create_for_data_unsafe(
                        frame.as_mut_ptr(),
                        Format::ARgb32,
                        568,
                        1232,
                        568 * 4,
                    )
                }
                .unwrap();
                surface
                    .write_to_png(&mut File::create(directory.join(format!("{name}.png"))).unwrap())
                    .unwrap();
            }
        }
        if std::env::var_os("K230_VISUAL_REQUIRE_ICONS").is_some() {
            assert!(
                renderer.icons.decode_count() >= 2,
                "selected icon theme must resolve public app icons"
            );
        }
    }

    #[test]
    fn theme_list_preview_and_scroll_paint_distinct_handheld_scenes() {
        let mut renderer = RendererCache::default();
        let params = RenderParams {
            width: 568,
            height: 1232,
            route: Route::Settings,
            progress: 1.0,
            scroll: 0.0,
        };
        let mut controls = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut controls, params, &[]).unwrap();
        let entry = ThemeEntry {
            id: "fixture-night".into(),
            name: "Fixture Night".into(),
            label: "Fixture Night".into(),
            origin: ThemeOrigin::Builtin,
            preview_path: None,
        };
        let mut view = ThemeView {
            page: ThemePage::List,
            list: Some(ThemeList {
                themes: (0..18)
                    .map(|index| ThemeEntry {
                        id: format!("fixture-{index}"),
                        label: format!("Fixture {index}"),
                        ..entry.clone()
                    })
                    .collect(),
                active: ActiveTheme {
                    id: Some("fixture-0".into()),
                    generation: None,
                },
            }),
            ..ThemeView::default()
        };
        renderer.set_theme_view(view.clone());
        let mut list = vec![0; controls.len()];
        renderer.draw(&mut list, params, &[]).unwrap();
        assert_ne!(list, controls);
        view.theme_position = 9.0;
        renderer.set_theme_view(view.clone());
        let mut scrolled = vec![0; controls.len()];
        renderer.draw(&mut scrolled, params, &[]).unwrap();
        assert_ne!(list, scrolled);
        // Browsing the carousel leaves the header unchanged while
        // repainting the carousel band and its name label below it. Row
        // bound follows `THEME_CAROUSEL_TOP` (132.0, task: tap-to-apply,
        // 2026-09-25 moved this up from 204.0 to leave room for the
        // background carousel below).
        assert_eq!(&list[..568 * 128 * 4], &scrolled[..568 * 128 * 4]);
        let wallpaper =
            std::env::temp_dir().join(format!("k230-theme-screen-crop-{}.png", std::process::id()));
        image::RgbaImage::from_fn(80, 160, |_, y| {
            if y < 80 {
                image::Rgba([220, 40, 30, 255])
            } else {
                image::Rgba([20, 80, 220, 255])
            }
        })
        .save(&wallpaper)
        .unwrap();
        // Task: tap-to-apply (2026-09-25) removed the separate Preview
        // page; the active theme's own background carousel now paints on
        // this same `ThemePage::List` page whenever `view.preview` is
        // set, so `view.page` stays `List` here.
        view.background_position = 0.0;
        view.preview = Some(ThemePreview {
            theme: entry,
            generation: "fixture-generation".into(),
            appearance_path: "/tmp/fixture-appearance.json".into(),
            palette: BTreeMap::from([
                ("background".into(), "#223344".into()),
                ("accent".into(), "#88ccbb".into()),
            ]),
            icon_theme: Some("hicolor".into()),
            backgrounds: vec![
                BackgroundChoice {
                    id: "fixture-still".into(),
                    label: "Still scene".into(),
                    kind: BackgroundKind::Image,
                    path: wallpaper.canonicalize().unwrap(),
                    selected: true,
                    decode_status: "unverified".into(),
                },
                BackgroundChoice {
                    id: "fixture-motion".into(),
                    label: "Motion scene".into(),
                    kind: BackgroundKind::Video,
                    path: "/tmp/fixture.webm".into(),
                    selected: false,
                    decode_status: "unverified".into(),
                },
            ],
            compatibility: Compatibility {
                applied: vec!["launcher".into()],
                unavailable: vec![],
                unknown: vec![],
            },
            activated: false,
            app_appearance: None,
        });
        renderer.set_theme_view(view);
        let mut preview = vec![0; controls.len()];
        // No decode to wait on any more (`poll_theme_image` is a
        // deliberate no-op, see its own doc) -- the background carousel's
        // own thumbnails and name/status text paint synchronously, same
        // as the theme carousel above.
        renderer.draw(&mut preview, params, &[]).unwrap();
        assert_ne!(preview, list);
        if let Ok(path) = std::env::var("K230_THEME_FIXTURE_PNG") {
            let surface = unsafe {
                ImageSurface::create_for_data_unsafe(
                    preview.as_mut_ptr(),
                    Format::ARgb32,
                    568,
                    1232,
                    568 * 4,
                )
            }
            .unwrap();
            let mut file = File::create(path).unwrap();
            surface.write_to_png(&mut file).unwrap();
        }
        std::fs::remove_file(wallpaper).unwrap();
    }

    #[test]
    fn pressed_and_activating_states_change_painted_pixels() {
        // Goal 1 (immediate feedback): a tapped-and-held slice must look
        // different within the same frame, and the tapped slice itself
        // must look visibly busy while its own request is in flight --
        // both painted straight from `ThemeView` fields (via `ThemeView::
        // applying_theme_index`/`applying_background_index`), no decode/
        // worker needed, so this is a synchronous, deterministic
        // pixel-diff check.
        let mut renderer = RendererCache::default();
        let entry = ThemeEntry {
            id: "fixture-a".into(),
            name: "Fixture A".into(),
            label: "Fixture A".into(),
            origin: ThemeOrigin::Builtin,
            preview_path: None,
        };
        let params = RenderParams {
            width: 568,
            height: 1232,
            route: Route::Settings,
            progress: 1.0,
            scroll: 0.0,
        };
        let list_view = ThemeView {
            page: ThemePage::List,
            list: Some(ThemeList {
                themes: (0..5)
                    .map(|index| ThemeEntry {
                        id: format!("fixture-{index}"),
                        label: format!("Fixture {index}"),
                        ..entry.clone()
                    })
                    .collect(),
                active: ActiveTheme {
                    id: Some("fixture-0".into()),
                    generation: None,
                },
            }),
            ..ThemeView::default()
        };
        renderer.set_theme_view(list_view.clone());
        let mut unpressed = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut unpressed, params, &[]).unwrap();

        renderer.set_theme_view(ThemeView {
            theme_pressed: Some(0),
            ..list_view
        });
        let mut pressed = vec![0; unpressed.len()];
        renderer.draw(&mut pressed, params, &[]).unwrap();
        assert_ne!(
            unpressed, pressed,
            "a pressed centered slice must paint differently from an unpressed one"
        );

        let preview = ThemePreview {
            theme: entry,
            generation: "fixture-generation".into(),
            appearance_path: "/tmp/fixture-appearance.json".into(),
            palette: BTreeMap::new(),
            icon_theme: None,
            backgrounds: vec![BackgroundChoice {
                id: "fixture-bg".into(),
                label: "Still".into(),
                kind: BackgroundKind::Image,
                path: "/tmp/nonexistent-fixture-bg.png".into(),
                selected: true,
                decode_status: "unverified".into(),
            }],
            compatibility: Compatibility {
                applied: vec![],
                unavailable: vec![],
                unknown: vec![],
            },
            activated: false,
            app_appearance: None,
        };
        let preview_view = ThemeView {
            page: ThemePage::List,
            preview: Some(preview),
            pending: None,
            ..ThemeView::default()
        };
        renderer.set_theme_view(preview_view.clone());
        let mut idle_footer = vec![0; unpressed.len()];
        renderer.draw(&mut idle_footer, params, &[]).unwrap();

        renderer.set_theme_view(ThemeView {
            pending: Some(ThemeRequest::Activate {
                theme_id: "fixture-a".into(),
                expected_generation: "fixture-generation".into(),
                background_id: Some("fixture-bg".into()),
            }),
            ..preview_view
        });
        let mut activating_footer = vec![0; unpressed.len()];
        renderer.draw(&mut activating_footer, params, &[]).unwrap();
        assert_ne!(
            idle_footer, activating_footer,
            "a pending Activate targeting the centred background slice must paint it visibly busy"
        );
    }

    #[test]
    fn pending_thumbnails_do_not_by_themselves_report_a_change() {
        // The idle-redraw fix (see `main.rs`'s own doc on
        // `THEME_PULSE_INTERVAL` and `theme_thumbnails_pending`): a caller
        // may keep *polling* while `theme_thumbnails_pending()` is true, but
        // must never redraw on that alone -- only `poll_theme_thumbnails`'s
        // own `changed` return value (something actually arrived) may mark
        // a frame dirty. This is exactly the invariant that makes it safe
        // for `main.rs` to stop forcing `dirty = true` merely because
        // something is pending.
        let entry = ThemeEntry {
            id: "fixture-pending".into(),
            name: "Fixture Pending".into(),
            label: "Fixture Pending".into(),
            origin: ThemeOrigin::Builtin,
            preview_path: Some(std::env::temp_dir().join(format!(
                "k230-theme-thumb-pending-{}-{}.png",
                std::process::id(),
                line!()
            ))),
        };
        image::RgbaImage::from_pixel(24, 24, image::Rgba([1, 1, 1, 255]))
            .save(entry.preview_path.as_ref().unwrap())
            .unwrap();
        let path = entry.preview_path.clone().unwrap().canonicalize().unwrap();
        let mut renderer = RendererCache::default();
        renderer.set_theme_view(ThemeView {
            page: ThemePage::List,
            list: Some(ThemeList {
                themes: vec![ThemeEntry {
                    preview_path: Some(path),
                    ..entry
                }],
                active: ActiveTheme {
                    id: None,
                    generation: None,
                },
            }),
            ..ThemeView::default()
        });
        // This very call is what first issues the decode request (see
        // `poll_theme_thumbnails`'s own doc): nothing can have arrived on
        // the reply channel yet, so `changed` must be false here even
        // though the entry is (correctly) still pending.
        assert!(renderer.theme_thumbnails_pending());
        assert!(
            !renderer.poll_theme_thumbnails(),
            "issuing a decode request must not itself report a change"
        );
        // And immediately calling it again, before the worker thread has
        // plausibly finished a real decode, must still report no change --
        // repeated polling alone is never a reason to redraw.
        assert!(
            !renderer.poll_theme_thumbnails(),
            "polling again with nothing new must still report no change"
        );
    }

    /// A theme's own preview image (or a representative background, chosen
    /// upstream by `tools/theme_catalog.py`) paints as a thumbnail beside
    /// its list row, and a background's own asset paints the same way
    /// beside its row on the preview page -- the touch counterpart to
    /// Omarchy's per-theme `preview.png` carousel art.
    #[test]
    fn list_and_background_rows_paint_their_own_thumbnail_once_decoded() {
        let stamp = format!("{}-{}", std::process::id(), line!());
        let theme_thumb = std::env::temp_dir().join(format!("k230-theme-thumb-list-{stamp}.png"));
        let background_thumb =
            std::env::temp_dir().join(format!("k230-theme-thumb-bg-{stamp}.png"));
        image::RgbaImage::from_pixel(48, 48, image::Rgba([210, 60, 20, 255]))
            .save(&theme_thumb)
            .unwrap();
        image::RgbaImage::from_pixel(48, 48, image::Rgba([20, 60, 210, 255]))
            .save(&background_thumb)
            .unwrap();
        let params = RenderParams {
            width: 568,
            height: 1232,
            route: Route::Settings,
            progress: 1.0,
            scroll: 0.0,
        };

        let mut without_art = RendererCache::default();
        let bare_entry = ThemeEntry {
            id: "fixture-bare".into(),
            name: "Fixture Bare".into(),
            label: "Fixture Bare".into(),
            origin: ThemeOrigin::Builtin,
            preview_path: None,
        };
        without_art.set_theme_view(ThemeView {
            page: ThemePage::List,
            list: Some(ThemeList {
                themes: vec![bare_entry],
                active: ActiveTheme {
                    id: None,
                    generation: None,
                },
            }),
            ..ThemeView::default()
        });
        let mut bare_frame = vec![0; 568 * 1232 * 4];
        without_art.draw(&mut bare_frame, params, &[]).unwrap();

        let mut renderer = RendererCache::default();
        let illustrated_entry = ThemeEntry {
            id: "fixture-bare".into(),
            name: "Fixture Bare".into(),
            label: "Fixture Bare".into(),
            origin: ThemeOrigin::Builtin,
            preview_path: Some(theme_thumb.canonicalize().unwrap()),
        };
        renderer.set_theme_view(ThemeView {
            page: ThemePage::List,
            list: Some(ThemeList {
                themes: vec![illustrated_entry.clone()],
                active: ActiveTheme {
                    id: None,
                    generation: None,
                },
            }),
            ..ThemeView::default()
        });
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while renderer.thumbnails.get("fixture-bare", Variant::Expanded).is_none() && std::time::Instant::now() < deadline
        {
            renderer.poll_theme_thumbnails();
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert!(renderer.thumbnails.get("fixture-bare", Variant::Expanded).is_some());
        let mut illustrated_list_frame = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut illustrated_list_frame, params, &[]).unwrap();
        assert_ne!(
            bare_frame, illustrated_list_frame,
            "a theme's own preview art must change the painted list row"
        );

        renderer.set_theme_view(ThemeView {
            page: ThemePage::List,
            preview: Some(ThemePreview {
                theme: illustrated_entry,
                generation: "fixture-generation".into(),
                appearance_path: "/tmp/fixture-appearance.json".into(),
                palette: BTreeMap::new(),
                icon_theme: None,
                backgrounds: vec![BackgroundChoice {
                    id: "fixture-background".into(),
                    label: "1-scene.png".into(),
                    kind: BackgroundKind::Image,
                    path: background_thumb.canonicalize().unwrap(),
                    selected: true,
                    decode_status: "unverified".into(),
                }],
                compatibility: Compatibility {
                    applied: vec![],
                    unavailable: vec![],
                    unknown: vec![],
                },
                activated: false,
                app_appearance: None,
            }),
            ..ThemeView::default()
        });
        let mut bare_preview_frame = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut bare_preview_frame, params, &[]).unwrap();
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while renderer.thumbnails.get("fixture-background", Variant::Expanded).is_none()
            && std::time::Instant::now() < deadline
        {
            renderer.poll_theme_thumbnails();
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert!(renderer.thumbnails.get("fixture-background", Variant::Expanded).is_some());
        let mut illustrated_preview_frame = vec![0; 568 * 1232 * 4];
        renderer
            .draw(&mut illustrated_preview_frame, params, &[])
            .unwrap();
        assert_ne!(
            bare_preview_frame, illustrated_preview_frame,
            "a background's own asset must change the painted row once decoded"
        );

        std::fs::remove_file(theme_thumb).unwrap();
        std::fs::remove_file(background_thumb).unwrap();
    }

    #[test]
    fn poll_theme_image_is_a_permanent_no_op_since_tap_to_apply() {
        // Task: tap-to-apply (2026-09-25) removed the separate Preview
        // page's own single large "screen crop" still preview -- both
        // carousels on the one remaining List page show their own
        // thumbnails via `ThemeThumbnailCache`/`poll_theme_thumbnails`
        // instead (see `list_and_background_rows_paint_their_own_
        // thumbnail_once_decoded`, above). `poll_theme_image` is kept,
        // rather than torn out, purely so existing call sites need no
        // further change -- this pins down that it never requests a
        // decode or reports a change, for any `ThemeView`, replacing the
        // old cancel-race regression test this same function used to
        // need (a stale decode racing a since-cancelled selection can no
        // longer surface: nothing is ever requested to race).
        let entry = ThemeEntry {
            id: "fixture".into(),
            name: "Fixture".into(),
            label: "Fixture".into(),
            origin: ThemeOrigin::Builtin,
            preview_path: None,
        };
        let mut renderer = RendererCache::default();
        renderer.set_theme_view(ThemeView {
            page: ThemePage::List,
            preview: Some(ThemePreview {
                theme: entry,
                generation: "fixture-generation".into(),
                appearance_path: "/tmp/fixture-appearance.json".into(),
                palette: BTreeMap::new(),
                icon_theme: None,
                backgrounds: vec![BackgroundChoice {
                    id: "still".into(),
                    label: "1-still.png".into(),
                    kind: BackgroundKind::Image,
                    path: "/tmp/nonexistent-fixture-still.png".into(),
                    selected: true,
                    decode_status: "unverified".into(),
                }],
                compatibility: Compatibility {
                    applied: vec![],
                    unavailable: vec![],
                    unknown: vec![],
                },
                activated: false,
                app_appearance: None,
            }),
            ..ThemeView::default()
        });
        assert!(!renderer.poll_theme_image(568, 1232));
        assert!(renderer.preview_key.is_none());
        assert!(renderer.preview_requested.is_none());
        assert!(renderer.preview_surface.is_none());
    }

    #[test]
    fn settings_power_rows_require_a_loaded_capability_snapshot() {
        let mut renderer = RendererCache::default();
        let params = RenderParams {
            width: 568,
            height: 1232,
            route: Route::Settings,
            progress: 1.0,
            scroll: 0.0,
        };
        let mut loading = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut loading, params, &[]).unwrap();
        let unavailable = Control {
            state: ControlState::Unavailable,
            value: None,
            label: "Unavailable".into(),
            detail: None,
            action: None,
        };
        let view = ServiceView {
            settings: Some(SettingsSnapshot {
                network: unavailable.clone(),
                brightness: unavailable.clone(),
                keyboard: unavailable.clone(),
                motion: unavailable,
            }),
            ..ServiceView::default()
        };
        renderer.set_services(view);
        let mut loaded = vec![0; loading.len()];
        renderer.draw(&mut loaded, params, &[]).unwrap();
        let row = 770 * 568 * 4;
        assert_ne!(&loading[row..row + 568 * 4], &loaded[row..row + 568 * 4]);
    }

    #[test]
    fn notification_target_error_changes_visible_history_row() {
        let mut renderer = RendererCache::default();
        let params = RenderParams {
            width: 568,
            height: 1232,
            route: Route::Shade,
            progress: 1.0,
            scroll: 0.0,
        };
        let event = NotificationEvent {
            id: 7,
            source: "Terminal".into(),
            icon: None,
            summary: "Ready".into(),
            body: "Body".into(),
            priority: Priority::Ordinary,
            timestamp: 0,
            error: None,
            dismissible: true,
            action_available: false,
        };
        let mut view = ServiceView {
            notifications: Some(NotificationSnapshot {
                count: 1,
                events: vec![event],
                preview: None,
            }),
            ..ServiceView::default()
        };
        renderer.set_services(view.clone());
        let mut normal = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut normal, params, &[]).unwrap();
        view.notifications.as_mut().unwrap().events[0].error = Some("target-unavailable".into());
        renderer.set_services(view);
        let mut failed = vec![0; normal.len()];
        renderer.draw(&mut failed, params, &[]).unwrap();
        let region = (355 * 568 * 4)..(375 * 568 * 4);
        assert!(normal[region.clone()] != failed[region]);
    }

    #[test]
    fn shade_backdrop_fades_full_screen_and_stays_put_at_partial_drag() {
        // Regression coverage for the reported bug: the dim backdrop used to
        // be drawn in the panel's own (translated) coordinate frame, so it
        // slid with the drag and only covered whatever sliver of the screen
        // happened to still land below the panel's *current* on-screen
        // position -- at a partial reveal that left a hard, undimmed edge
        // near the bottom of the screen instead of a uniform fade. These
        // pixels are captured directly from `scene()` via a real Cairo
        // surface (host build evidence; no board or QEMU involved), at a
        // handful of drag fractions standing in for live frames during a
        // pull-down.
        let mut renderer = RendererCache::default();
        // Alpha is stored premultiplied by Cairo; on a fully transparent
        // destination (Route::Shade's own clear-to-transparent paint) the
        // stored byte is just round(alpha * 255).
        let expected_byte =
            |progress: f64| (tray_backdrop_alpha(progress, 0.35) * 255.0).round() as i64;
        // Shade's panel is capped at 0.65 * height (see `panel_h` above), so
        // y=1000 of 1232 sits below the panel at every progress in this
        // sweep -- it is backdrop-only, never the panel's own background.
        let pixel_alpha = |frame: &[u8]| -> i64 {
            let index = (1000 * 568 + 280) * 4;
            i64::from(frame[index + 3])
        };
        let mut previous = -1i64;
        for tenths in 0..=10 {
            let progress = f64::from(tenths) / 10.0;
            let mut frame = vec![0; 568 * 1232 * 4];
            renderer
                .draw(
                    &mut frame,
                    RenderParams {
                        width: 568,
                        height: 1232,
                        route: Route::Shade,
                        progress,
                        scroll: 0.0,
                    },
                    &[],
                )
                .unwrap();
            let actual = pixel_alpha(&frame);
            // Eased alpha, tracked live at this exact fraction -- no pop.
            assert!(
                (actual - expected_byte(progress)).abs() <= 1,
                "progress {progress}: expected ~{}, got {actual}",
                expected_byte(progress)
            );
            // Monotonic: the backdrop only ever deepens as the tray reveals
            // further, whether mid-drag or mid-settle.
            assert!(actual >= previous, "alpha regressed at progress {progress}");
            previous = actual;
        }
        // At progress=0 there is no pop: the backdrop starts fully clear.
        let mut closed = vec![0; 568 * 1232 * 4];
        renderer
            .draw(
                &mut closed,
                RenderParams {
                    width: 568,
                    height: 1232,
                    route: Route::Shade,
                    progress: 0.0,
                    scroll: 0.0,
                },
                &[],
            )
            .unwrap();
        assert_eq!(pixel_alpha(&closed), 0);
        // At a partial drag the old bug left a hard, undimmed edge near the
        // bottom of the screen because the dim rectangle translated with
        // the panel and only ever covered a shrinking sliver above it; the
        // fixed backdrop instead dims uniformly all the way to the bottom.
        let mut partial = vec![0; 568 * 1232 * 4];
        renderer
            .draw(
                &mut partial,
                RenderParams {
                    width: 568,
                    height: 1232,
                    route: Route::Shade,
                    progress: 0.3,
                    scroll: 0.0,
                },
                &[],
            )
            .unwrap();
        let bottom_edge_index = (1220 * 568 + 280) * 4;
        assert!(
            partial[bottom_edge_index + 3] > 0,
            "backdrop must reach the bottom edge of the screen at a partial drag, not stop short"
        );
    }

    #[test]
    fn notification_swipe_moves_only_a_dismissible_row_and_reverses() {
        let mut renderer = RendererCache::default();
        let params = RenderParams {
            width: 568,
            height: 1232,
            route: Route::Shade,
            progress: 1.0,
            scroll: 0.0,
        };
        let mut view = ServiceView {
            notifications: Some(NotificationSnapshot {
                count: 1,
                preview: None,
                events: vec![NotificationEvent {
                    id: 3,
                    source: "System".into(),
                    icon: None,
                    summary: "Ready".into(),
                    body: "Message".into(),
                    priority: Priority::Ordinary,
                    timestamp: 0,
                    error: None,
                    dismissible: true,
                    action_available: false,
                }],
            }),
            ..ServiceView::default()
        };
        let mut baseline = vec![0; 568 * 1232 * 4];
        renderer.set_services(view.clone());
        renderer.draw(&mut baseline, params, &[]).unwrap();
        view.notification_swipe = Some(NotificationSwipe {
            event_id: 3,
            row_index: 0,
            offset: 100.0,
        });
        renderer.set_services(view.clone());
        let mut moved = vec![0; baseline.len()];
        renderer.draw(&mut moved, params, &[]).unwrap();
        assert_ne!(moved, baseline);
        view.notification_swipe.as_mut().unwrap().offset = 0.0;
        renderer.set_services(view.clone());
        let mut reversed = vec![0; baseline.len()];
        renderer.draw(&mut reversed, params, &[]).unwrap();
        assert_eq!(reversed, baseline);
        view.notifications.as_mut().unwrap().events[0].dismissible = false;
        renderer.set_services(view.clone());
        let mut critical = vec![0; baseline.len()];
        renderer.draw(&mut critical, params, &[]).unwrap();
        view.notification_swipe.as_mut().unwrap().offset = 100.0;
        renderer.set_services(view);
        let mut attempted = vec![0; baseline.len()];
        renderer.draw(&mut attempted, params, &[]).unwrap();
        assert_eq!(attempted, critical);
    }

    #[test]
    fn broker_preview_uses_its_named_app_icon() {
        let root = std::env::temp_dir().join(format!("k230-preview-icon-{}", std::process::id()));
        let apps_dir = root.join("icons/hicolor/scalable/apps");
        std::fs::create_dir_all(&apps_dir).unwrap();
        std::fs::write(root.join("icons/hicolor/index.theme"), "[Icon Theme]\nName=hicolor\nDirectories=scalable/apps\n[scalable/apps]\nSize=48\nType=Scalable\nMinSize=16\nMaxSize=128\n").unwrap();
        std::fs::write(apps_dir.join("fixture-preview.svg"), "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"48\" height=\"48\"><rect width=\"48\" height=\"48\" fill=\"#e85631\"/></svg>").unwrap();
        let mut renderer = RendererCache::default();
        renderer.set_icon_theme("hicolor");
        renderer.icons.use_fixture_root(root.clone());
        let view = ServiceView {
            notifications: Some(NotificationSnapshot {
                count: 0,
                events: vec![],
                preview: Some(NotificationPreview {
                    id: 7,
                    source: "Terminal".into(),
                    icon: Some("fixture-preview".into()),
                    summary: "Ready".into(),
                    priority: Priority::Ordinary,
                    ongoing: false,
                }),
            }),
            ..ServiceView::default()
        };
        renderer.set_services(view);
        let mut frame = vec![0; 568 * 1232 * 4];
        renderer
            .draw(
                &mut frame,
                RenderParams {
                    width: 568,
                    height: 1232,
                    route: Route::Shade,
                    progress: 1.0,
                    scroll: 0.0,
                },
                &[],
            )
            .unwrap();
        assert_eq!(renderer.icons.decode_count(), 1);
        let pixel = (220 * 568 + 59) * 4;
        assert!(
            frame[pixel + 2] > 160,
            "preview app icon red channel absent"
        );
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn authored_launcher_brush_changes_live_renderer_pixels() {
        let mut sections = BTreeMap::new();
        sections.insert(
            "launcher".into(),
            BTreeMap::from([(
                "background".into(),
                AppearanceToken::Brush(Brush {
                    stops: vec![BrushStop {
                        offset: 0.0,
                        argb: "#ffff0000".into(),
                    }],
                    angle_degrees: 0.0,
                    alpha: 1.0,
                }),
            )]),
        );
        let snapshot = AppearanceSnapshot {
            generation: "0123456789abcdef01234567".into(),
            path: "/tmp/test-generation".into(),
            icon_theme: Some("hicolor".into()),
            background: None,
            selected_background: None,
            backgrounds: vec![],
            palette: BTreeMap::new(),
            sections,
            applied: vec![],
            unavailable: vec![],
            unknown: vec![],
        };
        let mut renderer = RendererCache::default();
        let mut frame = vec![0; 568 * 1232 * 4];
        renderer.set_appearance(Some(snapshot));
        renderer
            .draw(
                &mut frame,
                RenderParams {
                    width: 568,
                    height: 1232,
                    route: Route::Drawer,
                    progress: 1.0,
                    scroll: 0.0,
                },
                &[],
            )
            .unwrap();
        let pixel = (900 * 568 + 280) * 4;
        assert_eq!(&frame[pixel..pixel + 4], &[0, 0, 255, 255]);
        assert_eq!(&frame[0..4], &[0, 0, 0, 0]);
        renderer.draw_wallpaper(&mut frame, 568, 1232).unwrap();
        assert_eq!(&frame[0..4], &[0, 0, 255, 255]);
    }

    #[test]
    fn drawer_keeps_live_scene_above_opaque_panel() {
        let apps = vec![AppEntry {
            id: "foot.desktop".into(),
            name: "Terminal".into(),
            icon: Some("foot".into()),
        }];
        let mut frame = vec![0; 568 * 1232 * 4];
        draw_shm(&mut frame, 568, 1232, Route::Drawer, &apps, 1.0).unwrap();
        assert_eq!(&frame[0..4], &[0, 0, 0, 0]);
        let panel_pixel = (900 * 568 + 280) * 4;
        assert_eq!(frame[panel_pixel + 3], 255);
        assert!(draw_shm(&mut frame[..100], 568, 1232, Route::Drawer, &apps, 1.0).is_err());
        draw_shm(&mut frame, 568, 1232, Route::Drawer, &apps, 0.0).unwrap();
        assert_eq!(frame[panel_pixel + 3], 0);
    }

    #[test]
    fn finger_progress_reuses_shaped_scene() {
        let apps = vec![AppEntry {
            id: "foot.desktop".into(),
            name: "Terminal".into(),
            icon: Some("foot".into()),
        }];
        let mut cache = RendererCache::default();
        let mut frame = vec![0; 568 * 1232 * 4];
        let params = RenderParams {
            width: 568,
            height: 1232,
            route: Route::Drawer,
            progress: 0.2,
            scroll: 0.0,
        };
        cache.draw(&mut frame, params, &apps).unwrap();
        let partial = frame.clone();
        cache
            .draw(
                &mut frame,
                RenderParams {
                    progress: 0.8,
                    ..params
                },
                &apps,
            )
            .unwrap();
        assert_ne!(frame, partial);
        assert_eq!(cache.rebuild_count(), 1);
        cache.invalidate();
        cache
            .draw(
                &mut frame,
                RenderParams {
                    progress: 1.0,
                    ..params
                },
                &apps,
            )
            .unwrap();
        assert_eq!(cache.rebuild_count(), 2);
    }

    #[test]
    fn drawer_uses_absolute_svg_app_icon() {
        let icon = std::env::temp_dir().join(format!(
            "k230-rust-render-icon-{}-{}.svg",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::write(&icon, "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"48\" height=\"48\"><rect width=\"48\" height=\"48\" fill=\"#e85631\"/></svg>").unwrap();
        let apps = vec![AppEntry {
            id: "foot.desktop".into(),
            name: "Terminal".into(),
            icon: Some(icon.to_string_lossy().into_owned()),
        }];
        let mut frame = vec![0; 568 * 1232 * 4];
        draw_shm(&mut frame, 568, 1232, Route::Drawer, &apps, 1.0).unwrap();
        let (x, y, tile_w, _) = tile_rect(568, 1232, 0, 0.0);
        let pixel = ((y as usize + 46) * 568 + (x + tile_w / 2.0) as usize) * 4;
        assert!(frame[pixel + 2] > 160, "actual SVG red channel absent");
        assert!(frame[pixel] < 80, "actual SVG blue channel absent");
        std::fs::remove_file(icon).unwrap();
    }

    #[test]
    fn default_renderer_resolves_named_icon() {
        let root = std::env::temp_dir().join(format!(
            "k230-rust-render-theme-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let apps_dir = root.join("icons/hicolor/scalable/apps");
        std::fs::create_dir_all(&apps_dir).unwrap();
        std::fs::write(root.join("icons/hicolor/index.theme"), "[Icon Theme]\nName=hicolor\nDirectories=scalable/apps\n[scalable/apps]\nSize=48\nType=Scalable\nMinSize=16\nMaxSize=128\n").unwrap();
        std::fs::write(apps_dir.join("fixture.svg"), "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"48\" height=\"48\"><rect width=\"48\" height=\"48\" fill=\"#e85631\"/></svg>").unwrap();
        let mut cache = RendererCache::default();
        cache.set_icon_theme("hicolor");
        cache.icons.use_fixture_root(root.clone());
        let apps = vec![AppEntry {
            id: "fixture.desktop".into(),
            name: "Fixture".into(),
            icon: Some("fixture".into()),
        }];
        let mut frame = vec![0; 568 * 1232 * 4];
        cache
            .draw(
                &mut frame,
                RenderParams {
                    width: 568,
                    height: 1232,
                    route: Route::Drawer,
                    progress: 1.0,
                    scroll: 0.0,
                },
                &apps,
            )
            .unwrap();
        assert_eq!(cache.icons.decode_count(), 1);
        let (x, y, tile_w, _) = tile_rect(568, 1232, 0, 0.0);
        let pixel = ((y as usize + 46) * 568 + (x + tile_w / 2.0) as usize) * 4;
        assert!(frame[pixel + 2] > 160, "named SVG red channel absent");
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn scrolling_repaints_clipped_rows_but_keeps_header() {
        let apps = (0..30)
            .map(|index| AppEntry {
                id: format!("app{index}.desktop"),
                name: format!("App {index}"),
                icon: None,
            })
            .collect::<Vec<_>>();
        let params = RenderParams {
            width: 568,
            height: 1232,
            route: Route::Drawer,
            progress: 1.0,
            scroll: 0.0,
        };
        let mut cache = RendererCache::default();
        let mut frame = vec![0; 568 * 1232 * 4];
        cache.draw(&mut frame, params, &apps).unwrap();
        let before = frame.clone();
        cache
            .draw(
                &mut frame,
                RenderParams {
                    scroll: 188.0,
                    ..params
                },
                &apps,
            )
            .unwrap();
        assert_eq!(
            &frame[300 * 568 * 4..301 * 568 * 4],
            &before[300 * 568 * 4..301 * 568 * 4]
        );
        assert_ne!(
            &frame[400 * 568 * 4..460 * 568 * 4],
            &before[400 * 568 * 4..460 * 568 * 4]
        );
        assert_eq!(cache.rebuild_count(), 2);
    }

    #[test]
    fn pressed_grid_tile_has_visible_non_color_border_without_affecting_neighbor() {
        let apps = (0..3)
            .map(|index| AppEntry {
                id: format!("fixture-{index}.desktop"),
                name: format!("Fixture {index}"),
                icon: None,
            })
            .collect::<Vec<_>>();
        let params = RenderParams {
            width: 568,
            height: 1232,
            route: Route::Drawer,
            progress: 1.0,
            scroll: 0.0,
        };
        let mut renderer = RendererCache::default();
        let mut before = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut before, params, &apps).unwrap();
        assert!(renderer.set_drawer_pressed(Some(1)));
        let mut after = vec![0; before.len()];
        renderer.draw(&mut after, params, &apps).unwrap();
        let (x, y, width, _) = tile_rect(568, 1232, 1, 0.0);
        let border = ((y as usize + 3) * 568 + (x + width / 2.0) as usize) * 4;
        assert_ne!(&before[border..border + 4], &after[border..border + 4]);
        let (other_x, other_y, other_width, _) = tile_rect(568, 1232, 0, 0.0);
        let other = ((other_y as usize + 3) * 568 + (other_x + other_width / 2.0) as usize) * 4;
        assert_eq!(&before[other..other + 4], &after[other..other + 4]);
        assert!(renderer.set_drawer_pressed(None));
    }

    fn fixture_theme(generation: &str, background: (u8, u8, u8)) -> AppearanceSnapshot {
        let (red, green, blue) = background;
        // An explicit `controls` (Route::Settings's own `section`)
        // background brush, not just the palette's own "background" role:
        // without one, `scene()`'s panel fill falls through to a fixed,
        // theme-independent gradient fallback (no card/controls/menu
        // brush authored), which would make two differently-paletted
        // fixture themes paint byte-identical panels -- exactly the
        // false negative this fixture exists to avoid in tests that
        // assert two themes' own frames differ.
        AppearanceSnapshot {
            generation: generation.into(),
            path: PathBuf::from("/tmp/fixture-generation"),
            icon_theme: None,
            background: None,
            selected_background: None,
            backgrounds: vec![],
            palette: BTreeMap::from([(
                "background".into(),
                PaletteValue::Color(PaletteColor {
                    red,
                    green,
                    blue,
                    alpha: 255,
                }),
            )]),
            sections: BTreeMap::from([(
                "controls".into(),
                BTreeMap::from([(
                    "background".into(),
                    AppearanceToken::Brush(Brush {
                        stops: vec![BrushStop {
                            offset: 0.0,
                            argb: format!("#ff{red:02x}{green:02x}{blue:02x}"),
                        }],
                        angle_degrees: 0.0,
                        alpha: 1.0,
                    }),
                )]),
            )]),
            applied: vec![],
            unavailable: vec![],
            unknown: vec![],
        }
    }

    const SETTINGS_PARAMS: RenderParams = RenderParams {
        width: 568,
        height: 1232,
        route: Route::Settings,
        progress: 1.0,
        scroll: 0.0,
    };

    #[test]
    fn content_generation_bumps_on_content_changes_but_not_on_appearance_changes() {
        // Optimistic Apply's own pre-render freshness check (task: pre-
        // render at prepare time) trusts this counter to mean "nothing
        // render_candidate_overlay read besides the theme itself changed
        // since it was computed." Prove both halves of that: it must bump
        // for the things a candidate render legitimately depends on
        // (theme_view/services/pressed), and must *not* bump merely
        // because the live appearance/icon theme changed -- a candidate
        // render is expected to differ from that on purpose.
        let mut renderer = RendererCache::default();
        let baseline = renderer.content_generation();

        renderer.set_theme_view(ThemeView::default());
        assert_ne!(renderer.content_generation(), baseline);
        let after_theme_view = renderer.content_generation();

        renderer.set_services(ServiceView::default());
        assert_ne!(renderer.content_generation(), after_theme_view);
        let after_services = renderer.content_generation();

        assert!(renderer.set_drawer_pressed(Some(2)));
        assert_ne!(renderer.content_generation(), after_services);
        let after_pressed = renderer.content_generation();
        // Setting the same pressed index again is not a change; the
        // return value already says so, and the counter must agree.
        assert!(!renderer.set_drawer_pressed(Some(2)));
        assert_eq!(renderer.content_generation(), after_pressed);

        renderer.set_appearance(Some(fixture_theme(
            "aaaaaaaaaaaaaaaaaaaaaaaa",
            (10, 20, 30),
        )));
        assert_eq!(renderer.content_generation(), after_pressed);
        renderer.set_icon_theme("hicolor");
        assert_eq!(renderer.content_generation(), after_pressed);
    }

    #[test]
    fn render_candidate_overlay_never_mutates_the_live_cache() {
        // The whole point of a separate method (rather than calling
        // set_appearance + draw + set_appearance-back): the live
        // renderer's own theme/cache must be provably untouched by
        // computing a candidate's own frame, however different that
        // candidate's colors are, so nothing can flash the wrong theme
        // before Apply.
        let mut renderer = RendererCache::default();
        renderer.set_appearance(Some(fixture_theme(
            "aaaaaaaaaaaaaaaaaaaaaaaa",
            (10, 20, 30),
        )));
        let mut baseline = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut baseline, SETTINGS_PARAMS, &[]).unwrap();
        let rebuilds_before = renderer.rebuild_count();

        let candidate = fixture_theme("bbbbbbbbbbbbbbbbbbbbbbbb", (200, 100, 50));
        let _ = renderer
            .render_candidate_overlay(Some(&candidate), Route::Settings, 568, 1232, &[])
            .unwrap();

        // The live cache's own theme is untouched: a fresh draw with the
        // exact same live params reuses the cache (no extra rebuild) and
        // produces byte-identical pixels to the pre-candidate baseline.
        assert_eq!(renderer.rebuild_count(), rebuilds_before);
        let mut after = vec![0; baseline.len()];
        renderer.draw(&mut after, SETTINGS_PARAMS, &[]).unwrap();
        assert_eq!(baseline, after);
    }

    #[test]
    fn adopt_prerendered_overlay_is_a_cache_hit_with_the_candidates_own_pixels() {
        let mut renderer = RendererCache::default();
        renderer.set_appearance(Some(fixture_theme(
            "aaaaaaaaaaaaaaaaaaaaaaaa",
            (10, 20, 30),
        )));
        let mut before = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut before, SETTINGS_PARAMS, &[]).unwrap();

        let candidate = fixture_theme("bbbbbbbbbbbbbbbbbbbbbbbb", (200, 100, 50));
        let pixels = renderer
            .render_candidate_overlay(Some(&candidate), Route::Settings, 568, 1232, &[])
            .unwrap();
        // Distinct from the live (still-active) theme's own frame -- the
        // whole point of pre-rendering a different theme.
        assert_ne!(pixels, before);

        renderer.adopt_prerendered_overlay(
            Some(candidate),
            Route::Settings,
            568,
            1232,
            pixels.clone(),
        );
        let rebuilds_after_adopt = renderer.rebuild_count();
        let mut shown = vec![0; before.len()];
        renderer.draw(&mut shown, SETTINGS_PARAMS, &[]).unwrap();
        // Adopting seeded route/width/height/scroll to already match this
        // exact draw call, so it is a cache hit (no rebuild) ...
        assert_eq!(renderer.rebuild_count(), rebuilds_after_adopt);
        // ... and the shown frame is exactly the pre-rendered candidate's
        // own pixels, not a fresh (possibly different) rebuild of it.
        assert_eq!(shown, pixels);
    }

    fn fixture_preview(generation: &str) -> ThemePreview {
        ThemePreview {
            theme: ThemeEntry {
                id: "fixture".into(),
                name: "Fixture".into(),
                label: "Fixture".into(),
                origin: ThemeOrigin::Builtin,
                preview_path: None,
            },
            generation: generation.into(),
            appearance_path: PathBuf::from("/tmp/fixture-appearance.json"),
            palette: BTreeMap::new(),
            icon_theme: None,
            backgrounds: vec![],
            compatibility: Compatibility {
                applied: vec![],
                unavailable: vec![],
                unknown: vec![],
            },
            activated: false,
            app_appearance: None,
        }
    }

    #[test]
    fn a_pending_only_theme_view_change_does_not_bump_content_generation() {
        // The other half of the freshness contract (see
        // `content_generation_bumps_on_content_changes_but_not_on_
        // appearance_changes`): an Apply tap's own `pending` transition,
        // or the busy spinner's own `pulse_phase`, must not bump
        // `content_generation`, even though both *are* baked into the
        // ordinary cached body (`set_theme_view`'s own `invalidate()`
        // still runs unconditionally -- see its doc). `content_
        // generation` is read only by the pre-render freshness check,
        // which must judge a computed candidate by what a person will
        // eventually tap, not by an unrelated pulse tick in between.
        // Board evidence, 2026-09-28: this exact gap was why a computed
        // pre-render always went stale before a person's own Apply tap
        // could ever reach it.
        let mut renderer = RendererCache::default();
        let view = ThemeView {
            page: ThemePage::List,
            preview: Some(fixture_preview("aaaaaaaaaaaaaaaaaaaaaaaa")),
            ..ThemeView::default()
        };
        renderer.set_theme_view(view.clone());
        let baseline = renderer.content_generation();

        let mut applying = view.clone();
        applying.pending = Some(ThemeRequest::Activate {
            theme_id: "fixture".into(),
            expected_generation: "aaaaaaaaaaaaaaaaaaaaaaaa".into(),
            background_id: None,
        });
        applying.pulse_phase = 0.5;
        renderer.set_theme_view(applying);
        assert_eq!(renderer.content_generation(), baseline);

        // A genuine content change (a different preview generation) still
        // bumps it, same as before this task.
        let mut different = view;
        different.preview = Some(fixture_preview("bbbbbbbbbbbbbbbbbbbbbbbb"));
        renderer.set_theme_view(different);
        assert_ne!(renderer.content_generation(), baseline);
    }

    #[test]
    fn a_theme_view_change_after_adopting_still_rebuilds_and_shows_pending() {
        // Adopting a pre-render (`show_theme_optimistically`'s own path)
        // bypasses a rebuild for exactly one `draw()` -- the frame that
        // shows the tapped theme as already applied, correctly with
        // nothing pending baked in (see `paint_theme_chooser`'s own doc
        // for why that is correct, not stale). But any *subsequent*
        // `ThemeView` change -- here, `pending` flipping back to `Some`
        // once the real commit machinery notices this generation is not
        // yet durably active -- must still force an ordinary rebuild via
        // `set_theme_view`'s own unconditional `invalidate()`, so the
        // panel never gets stuck showing the adopted candidate's frozen
        // pixels while the live state has moved on.
        let mut renderer = RendererCache::default();
        let mut view = ThemeView {
            page: ThemePage::List,
            preview: Some(fixture_preview("bbbbbbbbbbbbbbbbbbbbbbbb")),
            ..ThemeView::default()
        };
        renderer.set_theme_view(view.clone());

        let candidate = fixture_theme("bbbbbbbbbbbbbbbbbbbbbbbb", (200, 100, 50));
        let pixels = renderer
            .render_candidate_overlay(Some(&candidate), Route::Settings, 568, 1232, &[])
            .unwrap();
        renderer.adopt_prerendered_overlay(Some(candidate), Route::Settings, 568, 1232, pixels);

        let mut idle = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut idle, SETTINGS_PARAMS, &[]).unwrap();

        // Tap Apply: exactly the change board evidence showed must not
        // invalidate a matching pre-render.
        view.pending = Some(ThemeRequest::Activate {
            theme_id: "fixture".into(),
            expected_generation: "bbbbbbbbbbbbbbbbbbbbbbbb".into(),
            background_id: None,
        });
        let generation_before = renderer.content_generation();
        renderer.set_theme_view(view);
        assert_eq!(
            renderer.content_generation(),
            generation_before,
            "a pending-only change must not itself invalidate the pre-render"
        );

        let mut activating = vec![0; idle.len()];
        renderer.draw(&mut activating, SETTINGS_PARAMS, &[]).unwrap();
        assert_ne!(
            idle, activating,
            "a ThemeView change after adopting a pre-render must still \
             force a fresh rebuild reflecting the new pending state"
        );
    }
}

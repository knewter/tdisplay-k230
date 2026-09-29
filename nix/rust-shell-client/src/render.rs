//! Cairo/Pango software scene for the opt-in shell client.
//! This first view uses real desktop names and explicit fallback artwork.
use crate::{
    appearance::{AppearanceSnapshot, AppearanceToken, Brush},
    catalog::{terminal_like, AppEntry},
    home_grid::{self, HomeSlot},
    home_screen::{DragSource, HomeScreen, WidgetPickerPage},
    home_state::{HomeItem, WidgetKind},
    home_widgets::weather::WeatherDisplay,
    icon::IconCache,
    navigation::{
        self, list_top, panel_top, search_field_rect, search_keyboard_top, tile_rect, COLUMNS,
        GRID_BOTTOM_INSET, ROW_HEIGHT, SEARCH_KEYBOARD_HEIGHT,
    },
    pipewire_ipc::GraphSnapshot,
    service_data::{Control, ControlState, ControlValue, Priority},
    service_ui::{
        filter_app_indices, DrawerSearch, ServiceView, NOTIFICATION_ROW, NOTIFICATION_TOP,
        SETTINGS_VOLUME_ROW, SHADE_SLIDER_H, SHADE_SLIDER_TOP, SHADE_VOLUME_H, SHADE_VOLUME_TOP,
    },
    slider,
    volume::{self, Hud},
    splash::SplashStatus,
    theme_carousel,
    theme_catalog::BackgroundKind,
    theme_thumbnails::{bounded_working_set, ThemeThumbnailCache, ThumbnailKey, Variant},
    theme_ui::{
        background_display_label, ThemeImageKey, ThemeImageWorker, ThemePage, ThemeView,
        BACKGROUND_CAROUSEL_TOP, THEME_CAROUSEL_TOP,
    },
    wifi_settings::Security,
    wifi_ui::{all_networks, entry_buttons_rect, Page as WifiPage, WifiPublic},
    Route,
};
use cairo::{Context, Format, ImageSurface, LinearGradient, Operator};
use pango::{Alignment, EllipsizeMode, FontDescription};
use std::{fs::File, path::Path};

/// The one system font family used by every ordinary label this renderer
/// draws. `nix/card-shell/render.h` names the same literal
/// (`CARD_SHELL_FONT_FAMILY`) for the C card deck, so the two renderers
/// that composite into one frame never drift onto different fallback faces
/// (finding P1-1 of `docs/design/webos-polish-review.md`). This is
/// deliberately "DejaVu Sans", not the design study's IBM Plex family:
/// `nix/shell.nix` ships `pkgs.dejavu_fonts` on the image for exactly this,
/// so DejaVu is the one face every ordinary label can rely on. See
/// [`CLOCK_FONT_FAMILY`] for the one deliberate exception.
pub const FONT_FAMILY: &str = "DejaVu Sans";

/// The Clock widget's own display face, for its Bubble/Thin styles only
/// (`home-widget-design`, board review round 2: "browse the web find dope
/// clock widgets" -- see `docs/design/clock-widget-research.md`). DejaVu
/// Sans has only a Book/Bold pair; a hero numeral reads far better with a
/// real Thin-to-Black weight range, which `nix/shell.nix`'s
/// `clockDisplayFont` ships as one extracted file (`Inter.ttc`, the classic
/// **static** collection, not the variable font -- `pango-sys` at this
/// repo's pinned version has no binding for
/// `pango_font_description_set_variations` at all, confirmed directly, so
/// the variable weight axis is not reachable from this client). The Dot
/// matrix style draws its own procedural dots and needs no font; Analog's
/// only text is its date caption, which intentionally stays on
/// [`FONT_FAMILY`] like every other caption in this shell.
pub const CLOCK_FONT_FAMILY: &str = "Inter";

/// The drawer grid's own icon geometry (`docs/design/app-drawer-review.md`):
/// a 64px icon (no plate/box around it -- see `paint_drawer`), single-line
/// 14px label below.
pub const DRAWER_ICON_SIZE: i32 = 64;
/// The icon's own width in the grid math (a plain `f64` copy of
/// `DRAWER_ICON_SIZE`, since `IconCache::paint`/`paint_label` want
/// different numeric types for size).
pub const DRAWER_ICON_CARD: f64 = DRAWER_ICON_SIZE as f64;
/// Single-line app-name label font size -- 13-14px per the redesign.
pub const DRAWER_LABEL_SIZE: f64 = 14.0;

pub(crate) fn color(cr: &Context, rgb: u32, alpha: f64) {
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
    if !matches!(route, Route::Settings | Route::Shade | Route::Power) {
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
/// Wi-Fi, Brightness, Volume, Keyboard, Motion -- Volume (row 2, task:
/// "in Settings") sits directly after Brightness; Keyboard/Motion shifted
/// down one row each to make room, same rhythm cascade `settings_layout`'s
/// own doc already describes.
pub const SETTINGS_ROW_COUNT: u32 = 5;
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

/// A cheap vector sun glyph -- a filled disc plus a few short rays -- for
/// each end of the brightness slider (task: "a sun icon at each end if
/// cheap"). No new image asset: this is a handful of `arc`/`line_to`
/// calls, in the same spirit as `rounded`'s own plain-cairo shapes
/// elsewhere in this file.
fn paint_sun(cr: &Context, cx: f64, cy: f64, r: f64, rgb: u32, alpha: f64) {
    color(cr, rgb, alpha);
    cr.new_sub_path();
    cr.arc(cx, cy, r * 0.5, 0.0, std::f64::consts::TAU);
    let _ = cr.fill();
    cr.set_line_width(2.0);
    for i in 0..8 {
        let angle = f64::from(i) * std::f64::consts::FRAC_PI_4;
        let (dx, dy) = (angle.cos(), angle.sin());
        cr.move_to(cx + dx * r * 0.7, cy + dy * r * 0.7);
        cr.line_to(cx + dx * r, cy + dy * r);
    }
    color(cr, rgb, alpha);
    let _ = cr.stroke();
}

/// The shared Material-3-style brightness slider: a full-width track (a
/// thick "active" portion up to the thumb, a dimmer "inactive" rest) plus
/// a round thumb, and a sun glyph at each end -- one component
/// (task: "reuse one component for both") the Settings row and the
/// Shade's own header both call, so the two can never visually drift
/// apart. `center_y` is where the track and thumb sit vertically; the
/// track's own left/right x comes from `slider::track_bounds`, the same
/// numbers touch dispatch (`main.rs`) computes a drag's bounds from.
/// Draws nothing (not even a disabled ghost) when the control carries no
/// percent value -- callers already gate this on `ControlState::
/// Writable`, matching the row's own pre-slider behavior of showing
/// nothing extra when unavailable.
/// The track/thumb every slider in this shell shares -- factored out of
/// `paint_slider` (task: "reuse one component for both") so the volume
/// slider (`paint_volume_slider`, a different end-glyph but the identical
/// track math and touch geometry `slider::track_bounds`/`x_at_value`
/// already define) can never visually drift from the brightness one.
fn paint_slider_track(cr: &Context, style: VisualStyle, w: f64, center_y: f64, percent: u8) {
    let (left, right) = slider::track_bounds(w);
    let track_h = 14.0;
    let thumb_r = 17.0;
    let thumb_x = slider::x_at_value(percent, left, right);
    // Inactive track, full width.
    rounded(cr, left, center_y - track_h / 2.0, right - left, track_h, track_h / 2.0);
    color(cr, style.muted, 0.35);
    let _ = cr.fill();
    // Active (thumb-ward) portion. A minimum width keeps the rounded cap
    // visible even at the slider's own floor, instead of a sliver.
    let active_w = (thumb_x - left).max(track_h);
    rounded(cr, left, center_y - track_h / 2.0, active_w, track_h, track_h / 2.0);
    color(cr, style.accent, 1.0);
    let _ = cr.fill();
    cr.new_sub_path();
    cr.arc(thumb_x, center_y, thumb_r, 0.0, std::f64::consts::TAU);
    color(cr, style.accent, 1.0);
    let _ = cr.fill();
    cr.new_sub_path();
    cr.arc(thumb_x, center_y, thumb_r * 0.4, 0.0, std::f64::consts::TAU);
    color(cr, style.text, 0.9);
    let _ = cr.fill();
}

fn paint_slider(cr: &Context, style: VisualStyle, w: f64, center_y: f64, control: &Control) {
    let Some(ControlValue::Percent(percent)) = &control.value else {
        return;
    };
    let percent = *percent;
    let (left, right) = slider::track_bounds(w);
    paint_sun(cr, left - 30.0, center_y, 11.0, style.muted, 0.8);
    paint_sun(cr, right + 30.0, center_y, 15.0, style.accent, 1.0);
    paint_slider_track(cr, style, w, center_y, percent);
}

/// A cheap vector speaker glyph for the volume slider's own left end,
/// which doubles as the mute toggle (task: "a speaker icon that toggles
/// mute when tapped", `service_ui::volume_icon_tap_zone` owns the hit
/// test for this same glyph's position). A filled speaker-cone
/// polygon plus two short arcs (sound waves) when unmuted; muted swaps
/// the waves for a single diagonal slash through the cone, the same
/// "struck-through" convention Android's own muted speaker glyph uses.
/// No new image asset, same spirit as `paint_sun`.
fn paint_speaker(cr: &Context, cx: f64, cy: f64, r: f64, rgb: u32, alpha: f64, muted: bool) {
    color(cr, rgb, alpha);
    let body_w = r * 0.6;
    let body_h = r * 0.85;
    cr.move_to(cx - r, cy - body_h * 0.35);
    cr.line_to(cx - r + body_w, cy - body_h * 0.35);
    cr.line_to(cx - r + body_w + r * 0.55, cy - body_h);
    cr.line_to(cx - r + body_w + r * 0.55, cy + body_h);
    cr.line_to(cx - r + body_w, cy + body_h * 0.35);
    cr.line_to(cx - r, cy + body_h * 0.35);
    cr.close_path();
    let _ = cr.fill();
    cr.set_line_width(2.0);
    let cone_tip_x = cx - r + body_w + r * 0.55;
    if muted {
        cr.move_to(cone_tip_x - r * 0.1, cy - r * 0.7);
        cr.line_to(cone_tip_x + r * 0.7, cy + r * 0.7);
        color(cr, rgb, alpha);
        let _ = cr.stroke();
    } else {
        for radius in [r * 0.5, r * 0.85] {
            cr.new_sub_path();
            cr.arc(cone_tip_x, cy, radius, -0.6, 0.6);
            color(cr, rgb, alpha);
            let _ = cr.stroke();
        }
    }
}

/// The volume slider: `paint_slider_track` shared with brightness, plus a
/// speaker glyph (the mute toggle) at the track's left end and nothing at
/// the right end -- Android's own volume slider has no second icon.
/// `percent` is exactly what should be painted right now, already `0`
/// while muted (`volume::VolumeState::displayed_percent`'s job, not this
/// function's -- this never re-derives mute from the percent itself).
fn paint_volume_slider(cr: &Context, style: VisualStyle, w: f64, center_y: f64, percent: u8, muted: bool) {
    let (left, _right) = slider::track_bounds(w);
    let icon_rgb = if muted { style.muted } else { style.accent };
    paint_speaker(cr, left - 30.0, center_y, 15.0, icon_rgb, 1.0, muted);
    paint_slider_track(cr, style, w, center_y, percent);
}

/// The graph's current default sink, if the PipeWire monitor has reported
/// one yet -- the single source both the Shade and Settings volume rows
/// paint from, and what `main.rs`'s touch dispatch targets a slider write
/// against.
fn default_sink(audio: Option<&GraphSnapshot>) -> Option<&crate::pipewire_ipc::Sink> {
    audio?.sinks.iter().find(|sink| sink.is_default)
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
    // Put acknowledgement next to the row being changed, above the images.
    // This remains visible even when the bottom status line is near the edge.
    let background_feedback = if view.error.is_some() {
        Some(("Could not apply", style.error))
    } else if view.applying_background_index().is_some() {
        Some(("Applying…", style.accent))
    } else if view.message.as_deref().is_some_and(|s| s.starts_with("Background applied")) {
        Some(("Applied to Home", style.accent))
    } else { None };
    if let Some((message, color)) = background_feedback {
        text(cr, message, w / 2.0, BACKGROUND_CAROUSEL_TOP - 30.0,
            w / 2.0 - 28.0, 20.0, color);
    }
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
            let status = if view.applying_background_index() == Some(centered) {
                "Applying to Home…"
            } else if background.kind == BackgroundKind::Video {
                "Video unavailable"
            } else if background.selected {
                "Current background on Home"
            } else {
                "Tap to use on Home"
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
    if let Some(error) = &view.error {
        text(cr, error, 28.0, message_y, w - 56.0, 17.0, style.error);
    } else if view.pending.is_some() {
        text(cr, "Preparing…", 28.0, message_y, w - 56.0, 18.0, style.muted);
    } else if let Some(message) = &view.message {
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

/// Bundles `RendererCache::draw_splash`'s arguments (otherwise 8, over
/// clippy's `too_many_arguments` threshold), matching this file's own
/// `RenderParams` convention.
#[derive(Clone, Copy)]
pub struct SplashParams<'a> {
    pub width: u32,
    pub height: u32,
    pub name: &'a str,
    pub icon: Option<&'a str>,
    pub status: SplashStatus,
    pub icon_alpha: f64,
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
                            "Type the password"
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
            // The password field takes real keyboard focus and types through
            // the system keyboard (wvkbd) like every other text field in the
            // shell, instead of drawing its own keys here -- see
            // openspec/changes/the-handheld-configures-wifi-from-settings.
            // `entry_buttons_rect` keeps Cancel/Connect above whatever
            // height of the screen the raised keyboard currently reserves
            // (`view.keyboard_inset`), matching `wifi_ui::target`'s own hit
            // region exactly.
            let (button_top, _) = entry_buttons_rect(view.keyboard_inset);
            service_card(cr, theme, "controls", 24.0, button_top, 250.0, 88.0, false);
            service_card(cr, theme, "controls", 294.0, button_top, 250.0, 88.0, true);
            text(cr, "Cancel", 90.0, button_top + 27.0, 145.0, 25.0, style.muted);
            text(cr, "Connect", 351.0, button_top + 27.0, 145.0, 25.0, style.accent);
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
                // Anchored to the (possibly keyboard-raised) button row
                // rather than a fixed offset, so this never ends up
                // beneath the system keyboard -- see `entry_buttons_rect`.
                WifiPage::Entry => entry_buttons_rect(view.keyboard_inset).0 - 100.0,
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
/// screen height regardless of what is actually on it. `content_scale`
/// (`crate::density_scale`'s own value) scales the *natural* content
/// height too, not just the caps: on a tall/dense HDMI output, Settings'
/// rows genuinely paint bigger (see `scene`'s content transform), so the
/// panel that contains them must grow with them, or a real
/// `feat/shell-responsive` regression -- a tall output showing a short,
/// content-sized "stub" panel floating over empty space below it -- comes
/// right back. Content-sized, not screen-filling, remains the deliberate
/// choice (finding P0-2): this only makes "content-sized" track the
/// content's own real on-screen size.
fn settings_panel_h(
    available_h: f64,
    chooser: Option<&ThemeView>,
    services: Option<&ServiceView>,
    content_scale: f64,
) -> f64 {
    let min_panel_h = 420.0 * content_scale;
    if let Some(view) = services
        .and_then(|s| s.wifi.as_ref())
        .filter(|v| v.page != WifiPage::Closed)
    {
        return content_sized_panel_h(wifi_content_bottom(view) * content_scale, available_h, min_panel_h);
    }
    if let Some(view) = chooser.filter(|v| v.page != ThemePage::Controls) {
        return content_sized_panel_h(
            theme_chooser_content_bottom(view) * content_scale,
            available_h,
            min_panel_h,
        );
    }
    content_sized_panel_h(settings_content_bottom(services) * content_scale, available_h, min_panel_h)
}

/// The one distance a route's top-anchored sheet travels between fully
/// hidden and fully shown -- what `RendererCache::draw`'s row-shift moves
/// the baked bitmap by, and (new) what a live close-drag's finger travel is
/// measured against, so the two can never drift apart into a drag that
/// tracks the finger at the wrong rate. Shade and Drawer are fixed
/// fractions of the screen; Settings reuses its own real, content-sized
/// `settings_panel_h` rather than the full screen height a naive "same as
/// everything else" default would give it (previously the case here, but
/// dormant: nothing ever drove a live Settings progress before the close
/// drag this doc references was added, so the mismatch never painted).
pub fn panel_travel_height(
    route: Route,
    width: u32,
    height: u32,
    chooser: Option<&ThemeView>,
    services: Option<&ServiceView>,
) -> f64 {
    let h = f64::from(height);
    match route {
        Route::Shade => h * 0.65,
        // Fills nearly the whole screen from its own small top inset
        // (`navigation::panel_top`), not the old ~19%-of-height band --
        // `docs/design/app-drawer-review.md` §2: "filling the screen from
        // the top inset, with no black band above it."
        Route::Drawer => h - navigation::panel_top(height),
        Route::Settings => settings_panel_h(h, chooser, services, crate::density_scale(width, height)),
        Route::Power => power_panel_h(h, services),
        Route::Hide => h,
    }
}

pub const POWER_REBOOT_Y: f64 = 132.0;
pub const POWER_OFF_Y: f64 = 218.0;
pub const POWER_CANCEL_Y: f64 = 304.0;
pub const POWER_CONFIRM_Y: f64 = 432.0;
pub const POWER_BUTTON_H: f64 = 68.0;

fn power_panel_h(available_h: f64, services: Option<&ServiceView>) -> f64 {
    let natural: f64 = if services.is_some_and(|view| view.confirmation.is_some()) {
        530.0
    } else {
        402.0
    };
    natural.min(available_h)
}

/// Rounds only the top two corners, leaving the bottom edge square -- the
/// Drawer's own sheet shape: bottom-anchored, its bottom edge sits at or
/// past the physical screen edge, where a rounded corner would never be
/// visible anyway.
fn rounded_top(cr: &Context, x: f64, y: f64, w: f64, h: f64, r: f64) {
    cr.new_sub_path();
    cr.arc(
        x + r,
        y + r,
        r,
        std::f64::consts::PI,
        3.0 * std::f64::consts::FRAC_PI_2,
    );
    cr.arc(x + w - r, y + r, r, -std::f64::consts::FRAC_PI_2, 0.0);
    cr.line_to(x + w, y + h);
    cr.line_to(x, y + h);
    cr.close_path();
}

/// One frame's worth of Drawer catalog + search state, exactly as needed
/// to know what the grid should show and whether the keyboard is up --
/// `render::paint_drawer`'s own input, separate from the persistent
/// `DrawerGridCache` it also takes (that one remembers the *painted*
/// result across frames; this one is recomputed fresh every call, which is
/// cheap -- see `service_ui::filter_app_indices`'s own doc).
struct DrawerContent<'a> {
    /// The catalog, filtered and in display order -- already computed by
    /// the caller via `service_ui::filter_app_indices` so both the touch
    /// layer (`main.rs`) and the paint layer agree on what "index 3" means
    /// without either recomputing the filter independently.
    apps: Vec<&'a AppEntry>,
    search: &'a DrawerSearch,
}

/// A pre-rendered bitmap of the drawer grid's *entire* filtered content
/// (every row, not just the visible ones), rebuilt only when what it would
/// paint actually changes -- the filtered catalog, the active theme, the
/// panel width, or the search query. Scrolling changes none of those, so
/// an ordinary scroll/fling frame reuses this bitmap unchanged and
/// `paint_drawer` only blits the visible slice, instead of repainting
/// every tile every frame -- `docs/design/app-drawer-review.md`'s
/// performance section, "pre-render the whole grid ... into a cached
/// buffer whenever the catalog, theme or search changes."
#[derive(Default)]
pub struct DrawerGridCache {
    key: Option<DrawerGridKey>,
    surface: Option<ImageSurface>,
    content_height: f64,
    /// Bumped on every real rebuild -- test-only observability, the same
    /// role `IconCache::decode_count`/`RendererCache::rebuild_count`
    /// already play for their own caches.
    rebuilds: u64,
}

#[derive(Clone, PartialEq)]
struct DrawerGridKey {
    /// Cloned display list, not indices into the live catalog: a rescan
    /// that changes an app's icon/name at the same catalog index must
    /// still invalidate this cache, which a plain index/length comparison
    /// would miss.
    apps: Vec<AppEntry>,
    theme_generation: Option<String>,
    width: u32,
    query: String,
}

impl DrawerGridCache {
    #[cfg(test)]
    pub(crate) fn rebuilds(&self) -> u64 {
        self.rebuilds
    }

    /// Ensures the cached bitmap matches `content`/`theme`/`width`,
    /// rebuilding it first if not, then returns it alongside its content
    /// height (rows painted * `ROW_HEIGHT`). The bitmap is in *content*
    /// space: row 0 starts at bitmap `y = 0`, regardless of live scroll --
    /// `paint_drawer` positions the blit using the caller's own `scroll`.
    fn ensure(
        &mut self,
        content: &DrawerContent,
        theme: Option<&AppearanceSnapshot>,
        width: u32,
        height: u32,
        icons: &mut IconCache,
    ) -> (&ImageSurface, f64) {
        let theme_generation = theme.map(|snapshot| snapshot.generation.clone());
        let fresh = self.key.as_ref().is_some_and(|key| {
            key.width == width
                && key.theme_generation == theme_generation
                && key.query == content.search.query
                && key.apps.len() == content.apps.len()
                && key.apps.iter().zip(content.apps.iter()).all(|(a, b)| a == *b)
        });
        if !fresh {
            let rows = content.apps.len().div_ceil(COLUMNS).max(1);
            let content_height = (rows as f64 * ROW_HEIGHT).max(1.0);
            let surface = ImageSurface::create(
                Format::ARgb32,
                (width.max(1)) as i32,
                content_height.ceil() as i32,
            )
            .unwrap_or_else(|_| {
                ImageSurface::create(Format::ARgb32, 1, 1).expect("1x1 fallback surface")
            });
            if let Ok(cr) = Context::new(&surface) {
                // Passing `list_top(height)` as `tile_rect`'s own `scroll`
                // cancels the header offset out of its `y` formula,
                // leaving pure content-space row coordinates (row 0 at
                // bitmap y=0) with no separate formula to keep in sync.
                let offset = list_top(height);
                for (index, app) in content.apps.iter().enumerate() {
                    let (x, y, tile_w, _) = tile_rect(width, height, index, offset);
                    paint_drawer_tile(&cr, theme, icons, x, y, tile_w, app);
                }
            }
            self.surface = Some(surface);
            self.content_height = content_height;
            self.key = Some(DrawerGridKey {
                apps: content.apps.iter().map(|app| (*app).clone()).collect(),
                theme_generation,
                width,
                query: content.search.query.clone(),
            });
            self.rebuilds = self.rebuilds.wrapping_add(1);
        }
        (
            self.surface.as_ref().expect("just ensured"),
            self.content_height,
        )
    }
}

/// One tile's worth of content: an icon (no plate/box around it -- the
/// redesign's own "just the icon, with its label below, on the sheet
/// surface") and a single-line ellipsized label. Icon fallback (no
/// resolvable icon) is a round, theme-tinted circle with the app's
/// initial -- rare in practice (`docs/evidence/app-drawer/`'s real-icon
/// screenshots), but still legible and on-theme when it happens.
fn paint_drawer_tile(
    cr: &Context,
    theme: Option<&AppearanceSnapshot>,
    icons: &mut IconCache,
    x: f64,
    y: f64,
    cell_w: f64,
    app: &AppEntry,
) {
    let style = visual_style(theme, "launcher");
    let icon_x = x + (cell_w - DRAWER_ICON_CARD) / 2.0;
    let icon_y = y + 8.0;
    let mut painted = app
        .icon
        .as_deref()
        .is_some_and(|icon| icons.paint(cr, icon, DRAWER_ICON_SIZE, icon_x, icon_y));
    // Board finding (2026-09-27): `Icon=mpv` (Video) and `Icon=foot`
    // (Terminal) name real applications the bundled Yaru-based theme does
    // not cover at all -- not a harness gap, a genuine resolution miss.
    // Before falling all the way back to a plain letter circle, a
    // terminal emulator or an app that runs inside one
    // (`catalog::terminal_like`) gets one more try against a generic
    // icon name real desktop themes do cover.
    if !painted && terminal_like(&app.path) {
        painted = icons.paint(cr, "utilities-terminal", DRAWER_ICON_SIZE, icon_x, icon_y);
    }
    if !painted {
        // A tonal-container circle, not a faint tint: a low-alpha accent
        // over this sheet's own dark background read as "dark and flat"
        // (coordinator finding) rather than an intentional coloured
        // badge, so this uses a much stronger fill of the theme's own
        // accent colour, with the initial in a bright, guaranteed-
        // contrasting colour on top (`style.text`, not the accent again --
        // accent-on-accent would fight the very contrast a tonal
        // container needs).
        let radius = DRAWER_ICON_CARD / 2.0;
        let cx = icon_x + radius;
        let cy = icon_y + radius;
        cr.new_sub_path();
        cr.arc(cx, cy, radius, 0.0, 2.0 * std::f64::consts::PI);
        color(cr, style.accent, 0.55);
        let _ = cr.fill();
        let initial = app
            .name
            .chars()
            .next()
            .unwrap_or('?')
            .to_uppercase()
            .to_string();
        icons.paint_label(
            cr,
            &initial,
            (icon_x, icon_y + (DRAWER_ICON_CARD - 24.0) / 2.0),
            DRAWER_ICON_CARD,
            24.0,
            style.text,
        );
    }
    let label_y = icon_y + DRAWER_ICON_CARD + 6.0;
    icons.paint_label(
        cr,
        &app.name,
        (x + 4.0, label_y),
        (cell_w - 8.0).max(1.0),
        DRAWER_LABEL_SIZE,
        brush_rgb(theme, "menu", "text", style.text),
    );
}

/// Renders the drawer's slim top handle, its pill-shaped search field, and
/// -- while focused -- the compact search keyboard beneath it. Drawn
/// directly every frame (cheap: a handful of small fixed-position shapes,
/// unrelated to the app grid's own size), never through `DrawerGridCache`.
fn paint_drawer_chrome(
    cr: &Context,
    theme: Option<&AppearanceSnapshot>,
    width: u32,
    height: u32,
    search: &DrawerSearch,
) {
    let style = visual_style(theme, "launcher");
    let (hx, hy, hw, hh) = navigation::handle_rect(width, height);
    rounded(cr, hx, hy, hw, hh, hh / 2.0);
    color(cr, style.accent, 0.7);
    let _ = cr.fill();

    let (sx, sy, sw, sh) = search_field_rect(width, height);
    rounded(cr, sx, sy, sw, sh, sh / 2.0);
    // A flat colour, not a gradient brush: a rounded-pill path is already
    // current here (`rounded` above), and `fill_brush` would clobber it
    // with its own plain rectangle before filling, same reasoning as the
    // sheet background below.
    color(
        cr,
        brush_rgb(theme, "launcher", "search", palette_rgb_or(theme, "surface2", 0x2a2f3a)),
        1.0,
    );
    let _ = cr.fill();
    let label = if search.query.is_empty() {
        "Search apps"
    } else {
        search.query.as_str()
    };
    let label_color = if search.query.is_empty() {
        style.muted
    } else {
        style.text
    };
    text(cr, label, sx + 22.0, sy + sh / 2.0 - 9.0, sw - 44.0, 18.0, label_color);

    if search.focused {
        let ky = search_keyboard_top(height);
        color(cr, palette_rgb_or(theme, "surface1", 0x1a1e26), 1.0);
        cr.rectangle(0.0, ky, f64::from(width), SEARCH_KEYBOARD_HEIGHT);
        let _ = cr.fill();
        paint_search_keyboard(cr, theme, width, height, &style);
    }
}

fn paint_search_keyboard(
    cr: &Context,
    theme: Option<&AppearanceSnapshot>,
    width: u32,
    height: u32,
    style: &VisualStyle,
) {
    for row in 0..3 {
        for (ch, x, y, w, h) in navigation::keyboard_row_keys(row, width, height) {
            service_card(cr, theme, "controls", x + 2.0, y, (w - 4.0).max(1.0), h, false);
            centered_label(cr, &ch.to_string(), x, y + h / 2.0 - 12.0, w, 22.0, style.text);
        }
    }
    let (left, right, side_w, y, h) = navigation::keyboard_control_row(width, height);
    service_card(cr, theme, "controls", left, y, side_w, h, false);
    centered_label(cr, "⌫", left, y + h / 2.0 - 12.0, side_w, 22.0, style.text);
    let space_w = (right - side_w) - (left + side_w);
    service_card(cr, theme, "controls", left + side_w, y, space_w, h, false);
    centered_label(cr, "space", left + side_w, y + h / 2.0 - 9.0, space_w, 18.0, style.muted);
    service_card(cr, theme, "controls", right - side_w, y, side_w, h, false);
    centered_label(cr, "Done", right - side_w, y + h / 2.0 - 9.0, side_w, 18.0, style.accent);
}

/// The Drawer's whole paint: opaque themed sheet with rounded top corners,
/// the handle/search chrome, and the (cached) grid, scrolled into view by
/// blitting one slice of `DrawerGridCache` rather than repainting every
/// tile -- see that struct's own doc.
#[allow(clippy::too_many_arguments)]
fn paint_drawer(
    cr: &Context,
    width: u32,
    height: u32,
    progress: f64,
    scroll: f64,
    apps: &[AppEntry],
    icons: &mut IconCache,
    theme: Option<&AppearanceSnapshot>,
    search: &DrawerSearch,
    grid_cache: &mut DrawerGridCache,
    pressed: Option<usize>,
) {
    let w = f64::from(width);
    let h = f64::from(height);
    let panel_y = panel_top(height);
    let radius = 28.0;
    // `RendererCache::draw` always calls this at a fixed `progress: 1.0`
    // and does its own cheap post-bake row-shift for the live drag/settle
    // progress instead (see `scene`'s own doc); this translate only
    // matters for a direct caller (`draw_shm`/`export_png`, or a test)
    // that passes some other `progress` straight through.
    let hidden = 1.0 - progress.clamp(0.0, 1.0);
    cr.translate(0.0, hidden * (h - panel_y));

    let style = visual_style(theme, "launcher");
    // A flat opaque colour (`docs/design/app-drawer-review.md` §2: "an
    // opaque theme surface colour"), not a gradient brush: `fill_brush`
    // issues its own plain-rectangle path internally, which would
    // overwrite the rounded-top path just set below before filling it.
    rounded_top(cr, 0.0, panel_y, w, h - panel_y, radius);
    color(
        cr,
        brush_rgb(theme, "launcher", "background", palette_rgb_or(theme, "background", 0x1e1e2e)),
        1.0,
    );
    let _ = cr.fill();

    paint_drawer_chrome(cr, theme, width, height, search);

    let matched: Vec<usize> = filter_app_indices(apps, &search.query);
    let content = DrawerContent {
        apps: matched.iter().filter_map(|&i| apps.get(i)).collect(),
        search,
    };
    let row_start = list_top(height);
    let bottom = if search.focused {
        search_keyboard_top(height)
    } else {
        h - GRID_BOTTOM_INSET
    };
    let (grid_surface, content_height) = grid_cache.ensure(&content, theme, width, height, icons);
    let _ = cr.save();
    cr.rectangle(0.0, row_start, w, (bottom - row_start).max(0.0));
    cr.clip();
    let max_scroll = (content_height - (bottom - row_start)).max(0.0);
    let clamped_scroll = scroll.clamp(0.0, max_scroll);
    if cr
        .set_source_surface(grid_surface, 0.0, row_start - clamped_scroll)
        .is_ok()
    {
        let _ = cr.paint();
    }
    let _ = cr.restore();

    if let Some(display_index) = pressed {
        // `pressed` is already a *display* (filtered) index -- the same
        // one `tile_rect`/`tile_at` use everywhere else -- so its position
        // is just this call, no re-mapping through `matched` needed.
        let (x, y, tile_w, _) = tile_rect(width, height, display_index, clamped_scroll);
        if y + ROW_HEIGHT > row_start && y < bottom {
            let cx = x + tile_w / 2.0;
            let cy = y + 8.0 + DRAWER_ICON_CARD / 2.0;
            cr.new_sub_path();
            cr.arc(cx, cy, DRAWER_ICON_CARD / 2.0 + 8.0, 0.0, 2.0 * std::f64::consts::PI);
            color(cr, style.accent, 0.22);
            let _ = cr.fill();
        }
    }

    if content.apps.is_empty() {
        let message = if search.query.is_empty() {
            "No installed apps are available"
        } else {
            "No apps match your search"
        };
        text(cr, message, 28.0, row_start + 18.0, w - 56.0, 21.0, style.muted);
    }
}

#[allow(clippy::too_many_arguments)]
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
    search: &DrawerSearch,
    grid_cache: &mut DrawerGridCache,
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

    if route == Route::Drawer {
        paint_drawer(
            cr, width, height, progress, scroll, apps, icons, theme, search, grid_cache, pressed,
        );
        return;
    }

    // The Drawer (a bottom-anchored, full-bleed sheet with its own
    // top-inset formula) already returned via `paint_drawer` above; every
    // other route is top-anchored at `panel_y = 0.0`.
    let panel_y = 0.0;
    // Secondary panels are sized to their own content and capped, rather
    // than always filling the remaining screen height regardless of how
    // little is on them (finding P0-2).
    let panel_h = match route {
        Route::Shade => h * 0.65,
        Route::Settings => settings_panel_h(h - panel_y, chooser, services, crate::density_scale(width, height)),
        Route::Power => power_panel_h(h - panel_y, services),
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
    cr.translate(0.0, -hidden * panel_h);
    let section = match route {
        Route::Drawer => "launcher",
        Route::Shade => "notifications",
        Route::Settings => "controls",
        Route::Power => "controls",
        Route::Hide => "launcher",
    };
    let style = visual_style(theme, section);
    let panel_brush = theme_brush(theme, section, "background").or_else(|| {
        matches!(route, Route::Settings | Route::Power)
            .then(|| theme_brush(theme, "menu", "background"))
            .flatten()
    });
    if matches!(route, Route::Shade | Route::Settings | Route::Power) {
        // Preserve the authored translucent brush over an opaque theme
        // plate, rather than letting live card text ghost through apps.
        // Any theme can author sub-1.0 alpha on `notifications`/`controls`
        // backgrounds (finding P1-5). The Drawer's own equivalent guard
        // lives in `paint_drawer` now.
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
    if route == Route::Shade {
        rounded(cr, w / 2.0 - 36.0, panel_y + 11.0, 72.0, 6.0, 3.0);
        color(cr, style.accent, 0.82);
        let _ = cr.fill();
    }
    let title = match route {
        // Unreachable: `Route::Drawer` already returned above via
        // `paint_drawer`. Kept as a plain, harmless value (not a panic)
        // rather than trying to prove that to the compiler, which does
        // not know this function's own early return makes it impossible.
        Route::Drawer => "All apps",
        Route::Shade => "Notifications",
        Route::Settings => "Settings",
        Route::Power => "Power",
        Route::Hide => return,
    };
    if !(route == Route::Settings
        && (chooser.is_some_and(|view| view.page != ThemePage::Controls)
            || services
                .and_then(|s| s.wifi.as_ref())
                .is_some_and(|view| view.page != WifiPage::Closed)))
    {
        heading(cr, title, 28.0, panel_y + 32.0, w - 56.0, 40.0, style.text);
    }
    match route {
        Route::Drawer => {}
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
            // The shared brightness slider (task: "brightness should be a
            // slider" -- Android puts one at the top of its own quick
            // settings shade; `docs/design/shell-polish-review-2026-09.md`
            // asked for the same here). Only drawn when writable, exactly
            // like the Settings row below -- `service_ui::slider_band`
            // mirrors this same writable gate for touch dispatch.
            if let Some(settings) = services.and_then(|view| view.settings.as_ref()) {
                if settings.brightness.state == ControlState::Writable {
                    paint_slider(
                        cr,
                        style,
                        w,
                        SHADE_SLIDER_TOP + SHADE_SLIDER_H / 2.0,
                        &settings.brightness,
                    );
                }
            }
            // The volume slider (task: "volume slider in the shade under
            // the brightness slider"), directly beneath it -- only drawn
            // once the PipeWire monitor has reported a default sink,
            // exactly like brightness's own writable gate above;
            // `service_ui::volume_slider_band` mirrors this same
            // availability gate for touch dispatch.
            if let Some(sink) = default_sink(services.and_then(|view| view.audio.as_ref())) {
                paint_volume_slider(
                    cr,
                    style,
                    w,
                    SHADE_VOLUME_TOP + SHADE_VOLUME_H / 2.0,
                    volume::linear_to_percent(sink.linear_volume),
                    sink.muted,
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
                    262.0,
                    w - 48.0,
                    72.0,
                    false,
                );
                if let Some(preview) = items.and_then(|snapshot| snapshot.preview.as_ref()) {
                    let painted = preview
                        .icon
                        .as_deref()
                        .is_some_and(|icon| icons.paint(cr, icon, 38, 42.0, 279.0));
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
                            285.0,
                            30.0,
                            21.0,
                            style.text,
                        );
                    }
                    text(
                        cr,
                        &preview.source,
                        94.0,
                        273.0,
                        w - 132.0,
                        17.0,
                        style.accent,
                    );
                    text(
                        cr,
                        &preview.summary,
                        94.0,
                        296.0,
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
                    text(cr, empty, 42.0, 287.0, w - 84.0, 20.0, style.muted);
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
            // The row cards/sliders/Power section below are Settings' own
            // scrollable body, not header chrome -- centered and scaled by
            // `crate::settings_content_transform` (the same `(scale, x)`
            // `service_ui::panel_intent`'s Settings arm uses to map a tap
            // back before its own identical row-rhythm checks) so a wide
            // HDMI output gets a comfortable, design-width-proportioned
            // column instead of rows stretched edge to edge, and a tall one
            // gets genuinely bigger rows/text (via `settings_panel_h`'s own
            // matching `content_scale`) instead of a short stub panel over
            // empty space. `w` is shadowed to the design width for exactly
            // this block, so every existing `w`-relative literal below
            // keeps its original, already-correct proportions -- only the
            // surrounding transform decides their real on-screen size and
            // position, not a rewrite of the literals themselves.
            let (content_scale, content_x) = crate::settings_content_transform(width, height);
            let _ = cr.save();
            cr.translate(content_x, 0.0);
            cr.scale(content_scale, content_scale);
            let w = crate::DESIGN_WIDTH;
            if let Some(settings) = services.and_then(|view| view.settings.as_ref()) {
                // Row numbers are explicit, not a plain `enumerate()`,
                // because row 2 (Volume) is painted separately below --
                // its data comes from the PipeWire monitor
                // (`GraphSnapshot`), not `k230-settings`, so there is no
                // `Control` to hand this generic loop.
                for (row, name, control) in [
                    (0u32, "Wi-Fi ›", &settings.network),
                    (1, "Brightness", &settings.brightness),
                    (3, "Keyboard", &settings.keyboard),
                    (4, "Motion", &settings.motion),
                ] {
                    let y = settings_row_y(row);
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
                if settings.brightness.state == ControlState::Writable {
                    // Material-3-style slider (task: "brightness should
                    // be a slider"), replacing the old stepper -- the
                    // touch target is the whole row (`slider_band` in
                    // `service_ui.rs` mirrors this same row rhythm), well
                    // past the "at least about 56 px tall" ask.
                    paint_slider(cr, style, w, settings_row_y(1) + 86.0, &settings.brightness);
                }
                // Volume row (task: "in Settings"): row 2, directly after
                // Brightness. The device name doubles as the entry point
                // into the device picker -- one picker UI (the HUD's own
                // expanded panel), not two (design.md's "one picker, two
                // entry points").
                let volume_y = settings_row_y(SETTINGS_VOLUME_ROW);
                service_card(cr, theme, "controls", 24.0, volume_y, w - 48.0, SETTINGS_ROW_H, false);
                text(cr, "Volume", 42.0, volume_y + 15.0, w - 84.0, 17.0, style.accent);
                if let Some(sink) = default_sink(services.and_then(|view| view.audio.as_ref())) {
                    let percent = volume::linear_to_percent(sink.linear_volume);
                    let label = if sink.muted {
                        "Muted".to_string()
                    } else {
                        format!("{percent}%")
                    };
                    text(cr, &label, 42.0, volume_y + 43.0, w - 90.0, 19.0, style.text);
                    text(
                        cr,
                        &format!("{} · tap to change output", sink.description),
                        42.0,
                        volume_y + 76.0,
                        w - 90.0,
                        14.0,
                        style.muted,
                    );
                    paint_volume_slider(cr, style, w, volume_y + 86.0, percent, sink.muted);
                } else {
                    text(
                        cr,
                        services
                            .and_then(|view| view.audio_error.as_deref())
                            .unwrap_or("No audio device found"),
                        42.0,
                        volume_y + 43.0,
                        w - 90.0,
                        19.0,
                        style.muted,
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
            let _ = cr.restore();
        }
        Route::Power => {
            text(
                cr, "Choose what happens next", 28.0, 91.0, w - 56.0, 20.0, style.muted,
            );
            for (label, y) in [
                ("Restart…", POWER_REBOOT_Y),
                ("Power off…", POWER_OFF_Y),
                ("Cancel", POWER_CANCEL_Y),
            ] {
                service_card(
                    cr, theme, "controls", 24.0, y, w - 48.0, POWER_BUTTON_H, false,
                );
                text(cr, label, 44.0, y + 19.0, w - 88.0, 24.0, style.text);
            }
            if let Some(confirm) = services.and_then(|view| view.confirmation.as_ref()) {
                text(cr, &confirm.label, 28.0, 401.0, w - 56.0, 19.0, style.text);
                service_card(
                    cr, theme, "controls", 24.0, POWER_CONFIRM_Y,
                    w - 48.0, POWER_BUTTON_H, true,
                );
                text(
                    cr, "Cancel", 44.0, POWER_CONFIRM_Y + 19.0,
                    w / 2.0 - 44.0, 22.0, style.muted,
                );
                text(
                    cr, "Confirm", w / 2.0 + 20.0, POWER_CONFIRM_Y + 19.0,
                    w / 2.0 - 44.0, 22.0, style.error,
                );
            }
            if let Some(message) = services.and_then(|view| view.message.as_deref()) {
                let y = if services.is_some_and(|view| view.confirmation.is_some()) {
                    507.0
                } else {
                    385.0
                };
                text(cr, message, 28.0, y, w - 56.0, 17.0, style.muted);
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
/// finger is covering the icon itself. `fits` distinguishes an ordinary
/// accepting target (theme accent) from a "no room here" one (task 1: "a
/// clear 'no room here' indication") a multi-cell widget's drag is
/// currently hovering somewhere its span cannot actually land -- the
/// theme's own error role, plus a dashed rather than solid outline, reads
/// as "cannot drop" at a glance without needing a second color the theme
/// may not define distinctly from its accent.
fn paint_drop_target(cr: &Context, theme: Option<&AppearanceSnapshot>, rect: (f64, f64, f64, f64), fits: bool) {
    let style = visual_style(theme, "launcher");
    let (x, y, w, h) = rect;
    let rgb = if fits { style.accent } else { style.error };
    cr.new_path();
    rounded(cr, x, y, w, h, 22.0);
    color(cr, rgb, if fits { 0.20 } else { 0.14 });
    let _ = cr.fill_preserve();
    color(cr, rgb, 0.7);
    cr.set_line_width(2.0);
    if !fits {
        cr.set_dash(&[6.0, 5.0], 0.0);
    }
    let _ = cr.stroke();
    cr.set_dash(&[], 0.0);
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
/// Paints one grid or dock plate's *content* for whatever kind of
/// [`HomeItem`] occupies it: an app's icon (unchanged from before this
/// change), a folder's 2x2 mini-icon preview, or -- grid-only, since a
/// widget's span never fits a dock cell -- a widget is painted separately
/// by [`paint_widget_card`], not through this function at all.
#[allow(clippy::too_many_arguments)]
fn paint_item_plate(
    cr: &Context,
    theme: Option<&AppearanceSnapshot>,
    icons: &mut IconCache,
    apps: &[AppEntry],
    item: &HomeItem,
    plate_x: f64,
    plate_y: f64,
    plate_size: f64,
    icon_size: f64,
    pressed: bool,
) {
    match item {
        HomeItem::App { id } => {
            if let Some(app) = app_by_id(apps, id) {
                paint_icon_plate(cr, theme, icons, app, plate_x, plate_y, plate_size, icon_size, pressed);
            }
        }
        HomeItem::Folder(folder) => {
            cr.new_path();
            service_card(cr, theme, "launcher", plate_x, plate_y, plate_size, plate_size, pressed);
            for (index, rect) in home_grid::folder_mini_icon_rects(plate_x, plate_y, plate_size).into_iter().enumerate() {
                let (x, y, w, h) = rect;
                if let Some(id) = folder.apps.get(index) {
                    if let Some(app) = app_by_id(apps, id) {
                        let mini = w.min(h);
                        let mini_x = x + (w - mini) / 2.0;
                        let mini_y = y + (h - mini) / 2.0;
                        if !app.icon.as_deref().is_some_and(|icon| icons.paint(cr, icon, mini as i32, mini_x, mini_y)) {
                            rounded(cr, x, y, w, h, 4.0);
                            color(cr, brush_rgb(theme, "launcher", "text", 0xf4f7f8), 0.35);
                            let _ = cr.fill();
                        }
                    }
                }
            }
        }
        HomeItem::Widget { .. } => {} // never reached in the dock; grid widgets go through paint_widget_card
    }
}

/// `rgb`'s three channels as `0.0..=1.0` floats -- the gradient stop helper
/// every other themed gradient in this file (`brush_gradient`) already
/// wants.
fn rgb_floats(rgb: u32) -> (f64, f64, f64) {
    (f64::from((rgb >> 16) & 255) / 255.0, f64::from((rgb >> 8) & 255) / 255.0, f64::from(rgb & 255) / 255.0)
}

/// This color's approximate relative luminance (Rec. 709 coefficients), in
/// `0.0..=1.0`.
fn relative_luminance(rgb: u32) -> f64 {
    let (r, g, b) = rgb_floats(rgb);
    0.2126 * r + 0.7152 * g + 0.0722 * b
}

/// The halo color a glyph painted in `rgb` should use for legibility
/// directly on the wallpaper, with no card behind it (board review, round
/// 2: "the widgets don't have to have a background... use a soft text
/// shadow or glow computed from the theme (dark text gets a light halo,
/// light text gets a dark shadow)"). Computed from the glyph's own
/// resolved color's luminance, never a hardcoded shadow color that ignores
/// whether the active theme is dark or light.
fn glow_for(rgb: u32) -> u32 {
    if relative_luminance(rgb) > 0.5 {
        0x000000
    } else {
        0xffffff
    }
}

/// A cheap stand-in for a Gaussian blur (Cairo's toy API has none): draws
/// `layout` again at `samples` points evenly spaced around a circle of
/// `radius`, each at `alpha`, before the caller draws the real glyph on top
/// at full opacity. This is this shell's only legibility mechanism for text
/// painted directly on the wallpaper.
#[allow(clippy::too_many_arguments)]
fn draw_layout_halo(cr: &Context, layout: &pango::Layout, x: f64, y: f64, glow_rgb: u32, radius: f64, samples: u32, alpha: f64) {
    let tau = std::f64::consts::TAU;
    for i in 0..samples {
        let angle = f64::from(i) * tau / f64::from(samples.max(1));
        let dx = angle.cos() * radius;
        let dy = angle.sin() * radius;
        color(cr, glow_rgb, alpha);
        cr.move_to(x + dx, y + dy);
        pangocairo::functions::show_layout(cr, layout);
    }
}

/// A soft, roughly circular ambient backdrop behind a small graphic element
/// (a glyph, a ring, an outline icon) -- the non-text equivalent of
/// [`draw_layout_halo`], for the same "no card, legibility comes from a
/// halo/glow" reason (board review, round 2, also: "a very faint local
/// scrim only behind small text if contrast demands it" -- applied here to
/// small graphics rather than text).
fn draw_soft_backdrop(cr: &Context, cx: f64, cy: f64, radius: f64, glow_rgb: u32, alpha: f64) {
    cr.new_path();
    cr.arc(cx, cy, radius, 0.0, std::f64::consts::TAU);
    color(cr, glow_rgb, alpha);
    let _ = cr.fill();
}

/// One hero numeral/line, drawn straight on the wallpaper: a theme-derived
/// halo ([`glow_for`]/[`draw_layout_halo`]) for legibility, then the real
/// glyph on top at full opacity. `centered`, when set, centers within
/// `[x, x+width]` instead of left-aligning at `x` (`width` is read only
/// when `centered`).
#[allow(clippy::too_many_arguments)]
fn hero_glow(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32, weight: pango::Weight, centered: bool, font_family: &str) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(font_family);
    font.set_absolute_size(size * f64::from(pango::SCALE));
    font.set_weight(weight);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    if centered {
        layout.set_width((width * f64::from(pango::SCALE)) as i32);
        layout.set_alignment(pango::Alignment::Center);
    }
    draw_layout_halo(cr, &layout, x, y, glow_for(rgb), (size * 0.05).max(2.0), 8, 0.30);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// A small, letter-spaced, uppercase caption line (task: "the date beneath
/// in a small caps/label style"), haloed the same way [`hero_glow`] is --
/// DejaVu Sans has no true small-caps feature this toy Cairo/Pango setup
/// can request, so this fakes the same "eyebrow label" read with
/// `.to_uppercase()` plus a thin space (`\u{2009}`) inserted between every
/// character for visible tracking.
#[allow(clippy::too_many_arguments)]
fn caption_glow(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32, centered: bool) {
    let tracked: String = value.to_uppercase().chars().flat_map(|ch| [ch, '\u{2009}']).collect();
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(size * f64::from(pango::SCALE));
    font.set_weight(pango::Weight::Bold);
    layout.set_font_description(Some(&font));
    layout.set_text(tracked.trim_end());
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
    layout.set_ellipsize(EllipsizeMode::End);
    if centered {
        layout.set_alignment(pango::Alignment::Center);
    }
    draw_layout_halo(cr, &layout, x, y, glow_for(rgb), 2.0, 8, 0.35);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// A small centered number/label (the battery ring's percentage, a
/// forecast column's temperature), haloed the same way -- distinct from
/// the top-level `centered_label` (used by panels that still have their
/// own opaque backing, e.g. the folder overlay/picker sheet, where a halo
/// would be redundant).
fn centered_glow(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(size * f64::from(pango::SCALE));
    font.set_weight(pango::Weight::Bold);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
    layout.set_alignment(pango::Alignment::Center);
    draw_layout_halo(cr, &layout, x, y, glow_for(rgb), 2.0, 8, 0.35);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// 5x7 dot-matrix digit bitmaps (row-major, `'1'` = a lit dot) -- the
/// classic LED-scoreboard glyph shape, a generic and ubiquitous pattern
/// (not any specific branded typeface), drawn with plain Cairo circles, no
/// font file at all (task: "The dot-matrix style can be drawn
/// procedurally").
const DOT_DIGITS: [[&str; 7]; 10] = [
    ["01110", "10001", "10011", "10101", "11001", "10001", "01110"], // 0
    ["00100", "01100", "00100", "00100", "00100", "00100", "01110"], // 1
    ["01110", "10001", "00001", "00010", "00100", "01000", "11111"], // 2
    ["11111", "00010", "00100", "00010", "00001", "10001", "01110"], // 3
    ["00010", "00110", "01010", "10010", "11111", "00010", "00010"], // 4
    ["11111", "10000", "11110", "00001", "00001", "10001", "01110"], // 5
    ["00110", "01000", "10000", "11110", "10001", "10001", "01110"], // 6
    ["11111", "00001", "00010", "00100", "01000", "01000", "01000"], // 7
    ["01110", "10001", "10001", "01110", "10001", "10001", "01110"], // 8
    ["01110", "10001", "10001", "01111", "00001", "00010", "01100"], // 9
];
/// A 2-column colon glyph, in the same 7-row grid the digits use.
const DOT_COLON: [&str; 7] = ["00", "00", "01", "00", "01", "00", "00"];

/// One dot-matrix character's dots, `cols` wide, top-left at `(x0, y0)` in
/// `pitch`-spaced dot centers, each a small soft-haloed filled circle.
#[allow(clippy::too_many_arguments)]
fn draw_dot_matrix_glyph(cr: &Context, rows: &[&str], cols: usize, x0: f64, y0: f64, pitch: f64, radius: f64, rgb: u32) {
    let glow = glow_for(rgb);
    for (row_index, row) in rows.iter().enumerate() {
        for (col_index, ch) in row.chars().enumerate() {
            if col_index >= cols || ch != '1' {
                continue;
            }
            let cx = x0 + (col_index as f64 + 0.5) * pitch;
            let cy = y0 + (row_index as f64 + 0.5) * pitch;
            draw_soft_backdrop(cr, cx, cy, radius * 1.9, glow, 0.16);
            cr.new_path();
            cr.arc(cx, cy, radius, 0.0, std::f64::consts::TAU);
            color(cr, rgb, 0.95);
            let _ = cr.fill();
        }
    }
}

/// Draws `"HH"`/`"MM"` as a Nothing-OS-style dot-matrix readout, centered
/// within `(x, y, w, h)`: digits in `digit_rgb`, the colon in `accent_rgb`
/// (task: "Use theme colours tastefully: an accent for one element and the
/// foreground for the rest").
#[allow(clippy::too_many_arguments)]
fn draw_dot_matrix_time(cr: &Context, hour_text: &str, minute_text: &str, x: f64, y: f64, w: f64, h: f64, digit_rgb: u32, accent_rgb: u32) {
    let chars: Vec<(char, usize, u32)> = hour_text
        .chars()
        .map(|ch| (ch, 5, digit_rgb))
        .chain(std::iter::once((':', 2, accent_rgb)))
        .chain(minute_text.chars().map(|ch| (ch, 5, digit_rgb)))
        .collect();
    let gap_cols = 1.0;
    let total_cols: f64 =
        chars.iter().map(|(_, cols, _)| *cols as f64).sum::<f64>() + gap_cols * (chars.len().saturating_sub(1)) as f64;
    let pitch = (w / total_cols.max(1.0)).min(h / 7.0);
    let radius = pitch * 0.34;
    let block_w = total_cols * pitch;
    let block_h = 7.0 * pitch;
    let mut cursor_x = x + (w - block_w) / 2.0;
    let block_y = y + (h - block_h) / 2.0;
    for (ch, cols, rgb) in chars {
        if ch == ':' {
            draw_dot_matrix_glyph(cr, &DOT_COLON, cols, cursor_x, block_y, pitch, radius, rgb);
        } else if let Some(digit) = ch.to_digit(10) {
            draw_dot_matrix_glyph(cr, &DOT_DIGITS[digit as usize], cols, cursor_x, block_y, pitch, radius, rgb);
        }
        cursor_x += (cols as f64 + gap_cols) * pitch;
    }
}

/// One subpath of a simple three-lobe cloud silhouette (three overlapping
/// circles plus a rounded base) -- callers fill the whole thing in one
/// pass, so the overlaps read as a single solid blob, not three visible
/// circles.
fn cloud_shape(cr: &Context, cx: f64, cy: f64, w: f64, h: f64) {
    let top = cy - h * 0.12;
    cr.new_path();
    cr.arc(cx - w * 0.22, top + h * 0.14, h * 0.30, 0.0, std::f64::consts::TAU);
    cr.new_sub_path();
    cr.arc(cx + w * 0.06, top - h * 0.02, h * 0.38, 0.0, std::f64::consts::TAU);
    cr.new_sub_path();
    cr.arc(cx + w * 0.32, top + h * 0.16, h * 0.26, 0.0, std::f64::consts::TAU);
    cr.new_sub_path();
    rounded(cr, cx - w * 0.40, top, w * 0.78, h * 0.36, h * 0.18);
}

/// Draws one of `home_widgets::weather::condition_glyph`'s glyph keys as a
/// small vector icon, centered at `(cx, cy)` within roughly `size` square,
/// over a soft ambient backdrop for contrast against the wallpaper --
/// sun/cloud/rain/snow/fog/storm (task: "a condition icon drawn nicely...
/// vector sun/cloud/rain/snow/fog/thunder glyphs drawn with Cairo").
fn draw_weather_glyph(cr: &Context, glyph: &str, cx: f64, cy: f64, size: f64, style: &VisualStyle) {
    let tau = std::f64::consts::TAU;
    let _ = cr.save();
    draw_soft_backdrop(cr, cx, cy, size * 0.62, glow_for(style.text), 0.16);
    match glyph {
        "sun" => {
            let r = size * 0.26;
            cr.new_path();
            cr.arc(cx, cy, r, 0.0, tau);
            color(cr, style.accent, 0.95);
            let _ = cr.fill();
            cr.set_line_width(size * 0.05);
            cr.set_line_cap(cairo::LineCap::Round);
            color(cr, style.accent, 0.8);
            for i in 0..8 {
                let angle = f64::from(i) * tau / 8.0;
                let (inner, outer) = (r * 1.4, r * 1.85);
                cr.new_path();
                cr.move_to(cx + angle.cos() * inner, cy + angle.sin() * inner);
                cr.line_to(cx + angle.cos() * outer, cy + angle.sin() * outer);
                let _ = cr.stroke();
            }
        }
        "fog" => {
            cr.set_line_width(size * 0.09);
            cr.set_line_cap(cairo::LineCap::Round);
            color(cr, style.text, 0.7);
            for (index, spread) in [0.62, 0.82, 0.5].into_iter().enumerate() {
                let row_y = cy - size * 0.22 + f64::from(index as i32) * size * 0.22;
                cr.new_path();
                cr.move_to(cx - size * spread / 2.0, row_y);
                cr.line_to(cx + size * spread / 2.0, row_y);
                let _ = cr.stroke();
            }
        }
        "storm" => {
            cloud_shape(cr, cx, cy - size * 0.10, size, size * 0.62);
            color(cr, style.text, 0.85);
            let _ = cr.fill();
            cr.new_path();
            let bx = cx + size * 0.02;
            let by = cy + size * 0.14;
            cr.move_to(bx + size * 0.08, by - size * 0.02);
            cr.line_to(bx - size * 0.10, by + size * 0.20);
            cr.line_to(bx + size * 0.02, by + size * 0.20);
            cr.line_to(bx - size * 0.10, by + size * 0.44);
            cr.line_to(bx + size * 0.16, by + size * 0.14);
            cr.line_to(bx + size * 0.02, by + size * 0.14);
            cr.close_path();
            color(cr, style.accent, 0.95);
            let _ = cr.fill();
        }
        "snow" => {
            cloud_shape(cr, cx, cy - size * 0.10, size, size * 0.62);
            color(cr, style.text, 0.85);
            let _ = cr.fill();
            cr.set_line_width(size * 0.045);
            cr.set_line_cap(cairo::LineCap::Round);
            color(cr, style.accent, 0.9);
            for dx in [-0.22, 0.0, 0.22] {
                let sx = cx + size * dx;
                let sy = cy + size * 0.30;
                for i in 0..3 {
                    let angle = f64::from(i) * std::f64::consts::PI / 3.0;
                    let r = size * 0.08;
                    cr.new_path();
                    cr.move_to(sx - angle.cos() * r, sy - angle.sin() * r);
                    cr.line_to(sx + angle.cos() * r, sy + angle.sin() * r);
                    let _ = cr.stroke();
                }
            }
        }
        "rain" => {
            cloud_shape(cr, cx, cy - size * 0.10, size, size * 0.62);
            color(cr, style.text, 0.85);
            let _ = cr.fill();
            cr.set_line_width(size * 0.05);
            cr.set_line_cap(cairo::LineCap::Round);
            color(cr, style.accent, 0.9);
            for dx in [-0.22, 0.0, 0.22] {
                let bx = cx + size * dx;
                let by = cy + size * 0.24;
                cr.new_path();
                cr.move_to(bx, by);
                cr.line_to(bx - size * 0.07, by + size * 0.22);
                let _ = cr.stroke();
            }
        }
        // "cloud" and anything unrecognized both land here, matching
        // `condition_glyph`'s own fallback-to-a-sensible-default contract.
        "cloud" => {
            cloud_shape(cr, cx, cy, size, size * 0.72);
            color(cr, style.text, 0.85);
            let _ = cr.fill();
        }
        _ => {
            cr.new_path();
            cr.arc(cx, cy, size * 0.26, 0.0, tau);
            color(cr, style.accent, 0.9);
            let _ = cr.fill();
        }
    }
    let _ = cr.restore();
}

/// A simple lightning-bolt polygon, for the Battery widget's charging
/// indicator (task: "a charging bolt").
fn draw_bolt(cr: &Context, cx: f64, cy: f64, size: f64, rgb: u32) {
    cr.new_path();
    cr.move_to(cx + size * 0.10, cy - size * 0.50);
    cr.line_to(cx - size * 0.28, cy + size * 0.06);
    cr.line_to(cx - size * 0.02, cy + size * 0.06);
    cr.line_to(cx - size * 0.14, cy + size * 0.50);
    cr.line_to(cx + size * 0.30, cy - size * 0.10);
    cr.line_to(cx + size * 0.02, cy - size * 0.10);
    cr.close_path();
    color(cr, rgb, 1.0);
    let _ = cr.fill();
}

/// The Battery widget's ring: a soft ambient backdrop, a muted full-circle
/// track, and an accent arc for the live percentage, matching every
/// reference launcher's battery widget convention -- clockwise from the
/// top (task: "a clean ring or bar, percentage, and a charging bolt"). The
/// percentage label and the charging badge are painted by the caller
/// ([`ring_percent_label`], and a small badge circle respectively), not
/// this function, so this stays a pure "draw the ring itself" primitive.
fn draw_battery_ring(cr: &Context, cx: f64, cy: f64, radius: f64, percent: u8, style: &VisualStyle) {
    let tau = std::f64::consts::TAU;
    draw_soft_backdrop(cr, cx, cy, radius * 1.18, glow_for(style.text), 0.14);
    let start = -std::f64::consts::FRAC_PI_2;
    let sweep = tau * (f64::from(percent.min(100)) / 100.0);
    let line_width = (radius * 0.20).max(4.0);
    cr.set_line_cap(cairo::LineCap::Round);
    cr.new_path();
    cr.arc(cx, cy, radius, 0.0, tau);
    color(cr, style.text, 0.22);
    cr.set_line_width(line_width);
    let _ = cr.stroke();
    if sweep > 0.001 {
        cr.new_path();
        cr.arc(cx, cy, radius, start, start + sweep);
        color(cr, style.accent, 0.95);
        cr.set_line_width(line_width);
        let _ = cr.stroke();
    }
}

/// The battery ring's own percentage label, large and vertically centered
/// inside the ring (coordinator review: "put the percentage INSIDE the
/// ring (large, centred)"), haloed like [`centered_glow`] (which this just
/// wraps) since nothing but the wallpaper sits behind it. `y` is offset by
/// an empirical fraction of the chosen font size for vertical centering --
/// the same approximation every other hand-positioned label in this
/// renderer already uses, rather than pulling in exact Pango ink-extent
/// measurement for one label.
fn ring_percent_label(cr: &Context, value: &str, cx: f64, cy: f64, radius: f64, rgb: u32) {
    let size = (radius * 0.68).max(13.0);
    let width = radius * 1.9;
    centered_glow(cr, value, cx - width / 2.0, cy - size * 0.42, width, size, rgb);
}

/// A muted outline battery glyph (rounded body plus a small terminal nub),
/// over a soft ambient backdrop, for the "No battery info" absent state --
/// an outline reads as "nothing connected" rather than an error, matching
/// the task's own "clean... tasteful" ask.
fn draw_battery_outline(cr: &Context, x: f64, y: f64, w: f64, h: f64, rgb: u32) {
    let _ = cr.save();
    draw_soft_backdrop(cr, x + w / 2.0, y + h / 2.0, w.max(h) * 0.62, glow_for(rgb), 0.14);
    cr.set_line_width(3.0);
    rounded(cr, x, y, w, h, h * 0.28);
    color(cr, rgb, 0.7);
    let _ = cr.stroke();
    let nub_w = w * 0.12;
    let nub_h = h * 0.4;
    rounded(cr, x + w - 1.0, y + (h - nub_h) / 2.0, nub_w, nub_h, nub_h * 0.3);
    color(cr, rgb, 0.7);
    let _ = cr.fill();
    let _ = cr.restore();
}

/// Draws an analog clock face -- ticks, an hour hand, and an accent minute
/// hand, deliberately with **no dial fill or ring** (board review, round 2,
/// after `docs/design/clock-widget-research.md`'s Braun/Dieter Rams survey:
/// "a minimal, Braun-like face with no dial background, just markers and
/// hands"). The two hands get the same halo treatment text gets
/// ([`glow_for`]), since they are this widget's own thin strokes most
/// likely to vanish against a busy wallpaper; the twelve tick marks stay
/// plain (already short and given extra opacity of their own -- haloing
/// all twelve would read as clutter, not polish).
fn draw_analog_clock(cr: &Context, cx: f64, cy: f64, radius: f64, hour: i32, minute: i32, style: &VisualStyle) {
    let tau = std::f64::consts::TAU;
    let _ = cr.save();
    for i in 0..12 {
        let angle = f64::from(i) * tau / 12.0 - std::f64::consts::FRAC_PI_2;
        let major = i % 3 == 0;
        let inner = radius * if major { 0.78 } else { 0.86 };
        let outer = radius * 0.94;
        cr.new_path();
        cr.move_to(cx + angle.cos() * inner, cy + angle.sin() * inner);
        cr.line_to(cx + angle.cos() * outer, cy + angle.sin() * outer);
        cr.set_line_width(if major { 3.0 } else { 1.4 });
        color(cr, style.text, if major { 0.85 } else { 0.55 });
        let _ = cr.stroke();
    }
    let hour_angle = ((f64::from(hour % 12)) + f64::from(minute) / 60.0) * tau / 12.0 - std::f64::consts::FRAC_PI_2;
    let minute_angle = f64::from(minute) * tau / 60.0 - std::f64::consts::FRAC_PI_2;
    cr.set_line_cap(cairo::LineCap::Round);
    let hour_tip = (cx + hour_angle.cos() * radius * 0.48, cy + hour_angle.sin() * radius * 0.48);
    let minute_tip = (cx + minute_angle.cos() * radius * 0.74, cy + minute_angle.sin() * radius * 0.74);
    for (halo_radius, tip, width, rgb) in [(3.0, hour_tip, 5.0, style.text), (3.0, minute_tip, 3.5, style.accent)] {
        let glow = glow_for(rgb);
        for (dx, dy) in [(-halo_radius, 0.0), (halo_radius, 0.0), (0.0, -halo_radius), (0.0, halo_radius)] {
            cr.new_path();
            cr.move_to(cx + dx, cy + dy);
            cr.line_to(tip.0 + dx, tip.1 + dy);
            color(cr, glow, 0.35);
            cr.set_line_width(width);
            let _ = cr.stroke();
        }
    }
    cr.new_path();
    cr.move_to(cx, cy);
    cr.line_to(hour_tip.0, hour_tip.1);
    cr.set_line_width(5.0);
    color(cr, style.text, 1.0);
    let _ = cr.stroke();
    cr.new_path();
    cr.move_to(cx, cy);
    cr.line_to(minute_tip.0, minute_tip.1);
    cr.set_line_width(3.5);
    color(cr, style.accent, 1.0);
    let _ = cr.stroke();
    cr.new_path();
    cr.arc(cx, cy, 4.0, 0.0, tau);
    color(cr, style.accent, 1.0);
    let _ = cr.fill();
    let _ = cr.restore();
}

/// Paints a widget's whole content, straight on the wallpaper -- no card,
/// no surface fill, no border (board review, round 2: "the widgets don't
/// have to have a background like they do"); legibility instead comes from
/// a theme-derived halo/glow behind each glyph ([`glow_for`]/
/// [`draw_layout_halo`]/[`draw_soft_backdrop`]). Four selectable clock
/// styles (`docs/design/clock-widget-research.md`: Bubble/Thin/Dot matrix/
/// Analog), a battery ring, or a weather readout with a condition glyph and
/// short forecast strip. Cheap: no per-frame rasterization beyond ordinary
/// Cairo paths and Pango text layout, and the content itself
/// (`home.battery`/`home.weather`) is only ever refreshed by the caller's
/// own poll/cache timers, never recomputed here -- `home_screen::
/// HomeScreen`'s own docs on those fields cover the caching/throttling;
/// this function only ever reads their current value.
fn paint_widget_card(cr: &Context, style: &VisualStyle, kind: WidgetKind, rect: (f64, f64, f64, f64), home: &HomeScreen) {
    let (x, y, w, h) = rect;
    cr.new_path();
    let pad = 22.0;
    match kind {
        WidgetKind::Clock | WidgetKind::ClockMinimal | WidgetKind::ClockDotMatrix => {
            let (hour_text, minute_text, date_text) = match crate::home_widgets::clock::now_local() {
                Some(now) => (format!("{:02}", now.hour), format!("{:02}", now.minute), crate::home_widgets::clock::format_date(now)),
                None => ("--".to_string(), "--".to_string(), String::new()),
            };
            match kind {
                WidgetKind::Clock => {
                    // "Bubble": Pixel's heavy two-line lock clock -- both
                    // lines the same very heavy weight and the same color,
                    // centered, so the pair reads as one mass
                    // (`docs/design/clock-widget-research.md` #1/#7).
                    let line_size = h * 0.30;
                    hero_glow(cr, &hour_text, x, y + h * 0.05, w, line_size, style.text, pango::Weight::Heavy, true, CLOCK_FONT_FAMILY);
                    hero_glow(cr, &minute_text, x, y + h * 0.39, w, line_size, style.text, pango::Weight::Heavy, true, CLOCK_FONT_FAMILY);
                }
                WidgetKind::ClockMinimal => {
                    // "Thin": a real thin weight, not a shrunk bold
                    // (research #2/#9/#12).
                    let time_text = format!("{hour_text}:{minute_text}");
                    let line_size = h * 0.32;
                    hero_glow(cr, &time_text, x, y + h * 0.34, w, line_size, style.text, pango::Weight::Thin, true, CLOCK_FONT_FAMILY);
                }
                WidgetKind::ClockDotMatrix => {
                    // "Dot matrix": Nothing OS's Ndot (research #4), drawn
                    // procedurally -- no font at all.
                    draw_dot_matrix_time(cr, &hour_text, &minute_text, x + pad * 0.5, y, w - pad, h * 0.72, style.text, style.accent);
                }
                _ => unreachable!("matched above"),
            }
            caption_glow(cr, &date_text, x, y + h * 0.84, w, 17.0, style.accent, true);
        }
        WidgetKind::ClockAnalog => {
            let (hour, minute, date_text) = match crate::home_widgets::clock::now_local() {
                Some(now) => (now.hour, now.minute, crate::home_widgets::clock::format_date(now)),
                None => (0, 0, String::new()),
            };
            let cx = x + w / 2.0;
            let cy = y + h * 0.42;
            let radius = (w / 2.0 - pad).min(h * 0.34);
            draw_analog_clock(cr, cx, cy, radius, hour, minute, style);
            caption_glow(cr, &date_text, x + pad, y + h * 0.86, w - pad * 2.0, 15.0, style.accent, true);
        }
        WidgetKind::Battery => {
            caption_glow(cr, "Battery", x + pad, y + pad * 0.7, w - pad * 2.0, 13.0, style.text, false);
            match &home.battery {
                crate::home_widgets::battery::BatteryState::Present { percent, .. } => {
                    let cx = x + w / 2.0;
                    let cy = y + h * 0.55;
                    let radius = (w / 2.0 - pad * 1.3).min(h * 0.28) * 0.7;
                    draw_battery_ring(cr, cx, cy, radius, *percent, style);
                    ring_percent_label(cr, &format!("{percent}%"), cx, cy, radius, style.text);
                    if home.battery.is_charging() {
                        let badge_r = radius * 0.40;
                        let bx = cx + radius * 0.68;
                        let by = cy - radius * 0.68;
                        draw_soft_backdrop(cr, bx, by, badge_r * 1.5, glow_for(style.accent), 0.20);
                        cr.new_path();
                        cr.arc(bx, by, badge_r, 0.0, std::f64::consts::TAU);
                        color(cr, style.accent, 0.95);
                        let _ = cr.fill();
                        draw_bolt(cr, bx, by, badge_r * 1.25, glow_for(style.accent));
                    }
                }
                crate::home_widgets::battery::BatteryState::Absent => {
                    let glyph_w = w * 0.30;
                    let glyph_h = glyph_w * 0.52;
                    draw_battery_outline(cr, x + (w - glyph_w) / 2.0, y + h * 0.36, glyph_w, glyph_h, style.text);
                    caption_glow(cr, "No battery info", x + pad, y + h * 0.68, w - pad * 2.0, 13.0, style.text, true);
                }
            }
        }
        WidgetKind::Weather => {
            let (glyph, temp_c, location, high_c, low_c, forecast): (String, Option<i32>, String, Option<i32>, Option<i32>, Vec<crate::home_widgets::weather::ForecastEntry>) =
                match &home.weather {
                    WeatherDisplay::Fresh(snapshot) | WeatherDisplay::Stale(snapshot) => (
                        crate::home_widgets::weather::condition_glyph(&snapshot.condition).to_string(),
                        Some(snapshot.temperature_c),
                        snapshot.location.clone(),
                        Some(snapshot.high_c),
                        Some(snapshot.low_c),
                        snapshot.forecast.clone(),
                    ),
                    WeatherDisplay::Unavailable => ("sun".to_string(), None, String::new(), None, None, Vec::new()),
                };
            if !location.is_empty() {
                caption_glow(cr, &location, x + pad, y + pad * 0.6, w - pad * 2.0, 12.0, style.text, false);
            }
            draw_weather_glyph(cr, &glyph, x + w - pad - 26.0, y + pad + 22.0, 56.0, style);
            match temp_c {
                Some(value) => hero_glow(cr, &format!("{value}°"), x + pad, y + h * 0.22, w, h * 0.24, style.text, pango::Weight::Bold, false, FONT_FAMILY),
                None => hero_glow(cr, "--", x + pad, y + h * 0.22, w, h * 0.24, style.text, pango::Weight::Bold, false, FONT_FAMILY),
            }
            match (high_c, low_c) {
                (Some(high), Some(low)) => {
                    caption_glow(cr, &format!("H:{high}° L:{low}°"), x + pad, y + h * 0.52, w - pad * 2.0, 13.0, style.text, false);
                }
                _ => caption_glow(cr, "No data", x + pad, y + h * 0.52, w - pad * 2.0, 13.0, style.text, false),
            }
            // A short forecast strip (task: "a small 3-5 hour... forecast
            // strip"); this card's own 2x2 width comfortably fits 3
            // columns at a legible size, with generous vertical room.
            let shown: Vec<_> = forecast.iter().take(3).collect();
            if !shown.is_empty() {
                let strip_y = y + h - pad - 90.0;
                let col_w = (w - pad * 2.0) / shown.len().max(1) as f64;
                for (index, entry) in shown.iter().enumerate() {
                    let col_x = x + pad + col_w * index as f64;
                    caption_glow(cr, &entry.label, col_x, strip_y, col_w, 13.0, style.text, true);
                    let entry_glyph = crate::home_widgets::weather::condition_glyph(&entry.condition);
                    draw_weather_glyph(cr, entry_glyph, col_x + col_w / 2.0, strip_y + 38.0, 32.0, style);
                    centered_glow(cr, &format!("{}°", entry.temp_c), col_x, strip_y + 60.0, col_w, 17.0, style.text);
                }
            }
        }
    }
}

/// Paints Home's open-folder overlay (task 5): a dim scrim so the card
/// reads clearly over Home's own wallpaper/icons, the folder's editable
/// name, and its member apps in a small grid. Renaming's actual
/// system-keyboard wiring is not connected yet (see `home_screen::
/// OpenFolder`'s own doc) -- this just shows whichever of `folder.name`/
/// `open.name_buffer` is currently live.
fn paint_open_folder(
    cr: &Context,
    width: u32,
    height: u32,
    theme: Option<&AppearanceSnapshot>,
    icons: &mut IconCache,
    apps: &[AppEntry],
    home: &HomeScreen,
) {
    let Some(open) = home.open_folder.as_ref() else { return };
    let Some(HomeItem::Folder(folder)) = home.layout.get(open.slot) else { return };
    let style = visual_style(theme, "launcher");
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.5);
    let _ = cr.paint();
    let (cx, cy, cw, ch) = home_grid::folder_overlay_rect_inset(width, height, home.keyboard_inset);
    service_card(cr, theme, "launcher", cx, cy, cw, ch, false);
    let name_rect = home_grid::folder_name_rect_inset(width, height, home.keyboard_inset);
    let display_name = if open.editing_name { open.name_buffer.as_str() } else { folder.name.as_str() };
    let shown_name = if display_name.is_empty() { " " } else { display_name };
    centered_label(cr, shown_name, name_rect.0, name_rect.1 + name_rect.3 / 2.0 - 14.0, name_rect.2, 26.0, style.accent);
    // A member currently being dragged back out of this folder (task 3)
    // paints only as the floating lifted icon, not also here in its grid.
    let dragged_from_this_folder = home.drag.as_ref().and_then(|(source, _)| match source {
        DragSource::FromFolder { folder: slot, app_id } if *slot == open.slot => Some(app_id.as_str()),
        _ => None,
    });
    for (index, id) in folder.apps.iter().enumerate() {
        if Some(id.as_str()) == dragged_from_this_folder {
            continue;
        }
        let (x, y, w, _h) = home_grid::folder_app_rect_inset(width, height, index, home.keyboard_inset);
        let plate_size = w.min(home_grid::ICON_PLATE_SIZE);
        let plate_x = x + (w - plate_size) / 2.0;
        if let Some(app) = app_by_id(apps, id) {
            paint_icon_plate(cr, theme, icons, app, plate_x, y, plate_size, plate_size * 0.72, false);
            shadowed_label(cr, &app.name, x, y + plate_size + 6.0, w, 14.0, brush_rgb(theme, "launcher", "text", style.text));
        }
    }
}

/// Paints the widget-picker sheet (coordinator follow-up: long-press empty
/// Home space). A dim scrim plus a card of rows, sharing `home_grid`'s
/// `picker_row_rect` geometry with `home_screen`'s own hit-testing so a
/// tap always lands exactly where a row is drawn.
fn paint_widget_picker(cr: &Context, width: u32, height: u32, theme: Option<&AppearanceSnapshot>, home: &HomeScreen) {
    let Some(picker) = home.widget_picker else { return };
    let style = visual_style(theme, "launcher");
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.5);
    let _ = cr.paint();
    let (cx, cy, cw, ch) = home_grid::picker_rect(width, height);
    service_card(cr, theme, "launcher", cx, cy, cw, ch, false);
    // Only the Widgets page's rows get a live-rendered preview thumbnail
    // (task: "Show the widgets rendered in the picker previews as well") --
    // Menu/HomeSettings rows have no widget of their own to preview.
    let previews: &[WidgetKind] = if picker.page == WidgetPickerPage::Widgets { &WidgetKind::ALL } else { &[] };
    let rows: Vec<(String, String)> = match picker.page {
        WidgetPickerPage::Menu => vec![
            ("Widgets".to_string(), "Clock, battery, weather".to_string()),
            ("Wallpaper & style".to_string(), "Theme and background".to_string()),
            ("Home settings".to_string(), "Grid size".to_string()),
        ],
        WidgetPickerPage::Widgets => {
            let mut rows = vec![("< Back".to_string(), String::new())];
            rows.extend(
                WidgetKind::ALL
                    .iter()
                    .map(|kind| (kind.label().to_string(), kind.picker_subtitle().to_string())),
            );
            rows
        }
        WidgetPickerPage::HomeSettings => {
            let rows_per_page = home_grid::rows_per_page(height);
            vec![
                ("< Back".to_string(), String::new()),
                (
                    "Grid".to_string(),
                    format!("{} columns x {rows_per_page} rows per page (read-only)", home.layout.columns),
                ),
            ]
        }
    };
    for (index, (title, subtitle)) in rows.into_iter().enumerate() {
        let (x, y, w, h) = home_grid::picker_row_rect(width, height, index);
        service_card(cr, theme, "controls", x, y, w, h, false);
        // Row 0 ("< Back") never has a preview; every row after it lines up
        // with `previews[index - 1]` since both walk `WidgetKind::ALL` in
        // the same order.
        let preview = index.checked_sub(1).and_then(|preview_index| previews.get(preview_index));
        let (label_x, label_w) = if let Some(kind) = preview {
            let side = (h - 20.0).min(72.0);
            let preview_x = x + 12.0;
            let preview_y = y + (h - side) / 2.0;
            let _ = cr.save();
            rounded(cr, preview_x, preview_y, side, side, 10.0);
            cr.clip();
            paint_widget_card(cr, &style, *kind, (preview_x, preview_y, side, side), home);
            let _ = cr.restore();
            (x + side + 24.0, w - side - 36.0)
        } else {
            (x, w)
        };
        let label_color = if title.starts_with('<') { style.muted } else { style.accent };
        centered_label(cr, &title, label_x, y + 12.0, label_w, 22.0, label_color);
        if !subtitle.is_empty() {
            shadowed_label(cr, &subtitle, label_x, y + h - 30.0, label_w, 14.0, brush_rgb(theme, "launcher", "text", style.text));
        }
    }
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
/// A visible edge highlight and arrow while a live drag dwells in the
/// left/right edge zone, growing in with `HomeScreen::drag_edge_indicator`'s
/// own dwell progress (task 1: "a visible edge highlight or arrow showing
/// it's about to switch"). Painted last, over every page/dock/overlay
/// content, so it always reads clearly regardless of what is underneath.
fn paint_edge_page_indicator(cr: &Context, width: u32, height: u32, theme: Option<&AppearanceSnapshot>, home: &HomeScreen) {
    let Some((side, progress)) = home.drag_edge_indicator() else { return };
    let style = visual_style(theme, "launcher");
    let w = f64::from(width);
    let h = f64::from(height);
    let band_w = 56.0;
    let x0 = if side < 0 { 0.0 } else { w };
    let x1 = if side < 0 { band_w } else { w - band_w };
    let cy = h / 2.0;
    let alpha = 0.12 + 0.40 * progress;
    let (r, g, b) = rgb_floats(style.accent);
    let gradient = LinearGradient::new(x0, 0.0, x1, 0.0);
    gradient.add_color_stop_rgba(0.0, r, g, b, alpha);
    gradient.add_color_stop_rgba(1.0, r, g, b, 0.0);
    if cr.set_source(&gradient).is_ok() {
        cr.rectangle(if side < 0 { 0.0 } else { w - band_w }, 0.0, band_w, h);
        let _ = cr.fill();
    }
    let arrow_size = 13.0 + 9.0 * progress;
    let ax = if side < 0 { 18.0 } else { w - 18.0 };
    let dir = f64::from(side);
    cr.new_path();
    cr.move_to(ax - dir * arrow_size * 0.5, cy - arrow_size);
    cr.line_to(ax + dir * arrow_size * 0.5, cy);
    cr.line_to(ax - dir * arrow_size * 0.5, cy + arrow_size);
    color(cr, style.accent, (0.45 + 0.55 * progress).min(1.0));
    cr.set_line_width(4.0);
    cr.set_line_join(cairo::LineJoin::Round);
    cr.set_line_cap(cairo::LineCap::Round);
    let _ = cr.stroke();
}

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
    // The stored layout's own live column count -- kept equal to
    // `home_grid::columns_for_width(width)` by `HomeScreen::sync_columns`,
    // called before every `draw_home`. Painting reads it directly here
    // rather than recomputing `columns_for_width` independently, so it can
    // never disagree with what a slot index actually means in `home.layout
    // .pages` (see `home_grid::tile_rect`'s own doc).
    let columns = home.layout.columns;
    let pressed = home.pressed(width, height);
    let dragged_slot = home.drag.as_ref().and_then(|(source, _)| match source {
        DragSource::Existing(slot) => Some(*slot),
        DragSource::FromDrawer(_) | DragSource::Widget(_) | DragSource::FromFolder { .. } => None,
    });
    let drop_target = home.drop_target(width, height);
    let show_drop_target = home.drag.is_some() && drop_target.is_some() && drop_target != dragged_slot;
    let drop_target_fits = home.drop_target_fits(width, height);
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
                    paint_drop_target(cr, theme, home_grid::tile_rect(width, height, slot, columns), drop_target_fits);
                }
            }
        }
        if let Some(row) = home.layout.pages.get(page) {
            for (slot, entry) in row.iter().enumerate() {
                let Some(item) = entry else { continue };
                let this_slot = HomeSlot::Grid { page, slot };
                if dragged_slot == Some(this_slot) {
                    continue; // painted last, floating at the finger instead
                }
                if let HomeItem::Widget { widget } = item {
                    let rect = home_grid::spanned_tile_rect(width, height, slot, widget.span(), columns);
                    paint_widget_card(cr, &style, *widget, rect, home);
                    continue;
                }
                let content = home_grid::tile_content(width, height, slot, columns);
                let label = match item {
                    HomeItem::App { id } => app_by_id(apps, id).map(|app| app.name.clone()),
                    HomeItem::Folder(folder) => Some(folder.name.clone()),
                    HomeItem::Widget { .. } => None,
                };
                paint_item_plate(
                    cr,
                    theme,
                    icons,
                    apps,
                    item,
                    content.plate_x,
                    content.plate_y,
                    content.plate_size,
                    home_grid::ICON_SIZE,
                    pressed == Some(this_slot),
                );
                if let Some(label) = label {
                    shadowed_label(
                        cr,
                        &label,
                        content.plate_x,
                        content.label_y,
                        content.plate_size,
                        15.0,
                        brush_rgb(theme, "launcher", "text", style.text),
                    );
                }
                if home.rearranging {
                    paint_remove_badge(cr, theme, (content.plate_x, content.plate_y));
                }
            }
        }
        let _ = cr.restore();
    }

    if page_count > 1 {
        // Page dots enlarge during a drag (task 1: "Show page dots enlarged
        // during drag") -- a bigger target reads as "cross-page navigation
        // matters right now" exactly when a person is holding an item that
        // might need to cross one.
        let enlarged = home.drag.is_some();
        let scale = if enlarged { 1.4 } else { 1.0 };
        let dot_y = home_grid::dots_center_y(height);
        let spacing = 22.0 * scale;
        let start_x = f64::from(width) / 2.0 - spacing * (page_count as f64 - 1.0) / 2.0;
        for page in 0..page_count {
            let cx = start_x + spacing * page as f64;
            let active = (position - page as f64).abs() < 0.5;
            if active {
                // The active page reads as a short pill, not just a bigger
                // dot -- a subtle, common refinement over a plain dot row
                // that still costs nothing extra to hit-test (dots are
                // purely decorative; nothing here is tappable).
                let pill_w = 18.0 * scale;
                let pill_h = 7.0 * scale;
                rounded(cr, cx - pill_w / 2.0, dot_y - pill_h / 2.0, pill_w, pill_h, pill_h / 2.0);
                color(cr, style.accent, 0.95);
                let _ = cr.fill();
            } else {
                cr.arc(cx, dot_y, 3.5 * scale, 0.0, std::f64::consts::TAU);
                color(cr, style.text, 0.38);
                let _ = cr.fill();
            }
        }
    }

    paint_edge_page_indicator(cr, width, height, theme, home);

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
        let Some(item) = home.layout.dock.get(slot).and_then(Option::as_ref) else {
            continue;
        };
        let this_slot = HomeSlot::Dock { slot };
        if dragged_slot == Some(this_slot) {
            continue;
        }
        let content = home_grid::dock_content(width, height, slot);
        if show_drop_target && drop_target == Some(this_slot) {
            paint_drop_target(cr, theme, home_grid::dock_rect(width, height, slot), drop_target_fits);
        }
        paint_item_plate(
            cr,
            theme,
            icons,
            apps,
            item,
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
            .as_ref()
            .is_some_and(|(_, point)| home_grid::hits(*point, remove));
        service_card(cr, theme, "controls", remove.0, remove.1, remove.2, remove.3, over_remove);
        centered_label(cr, "Remove", remove.0, remove.1 + remove.3 / 2.0 - 12.0, remove.2, 24.0, style.error);
    }

    paint_open_folder(cr, width, height, theme, icons, apps, home);
    paint_widget_picker(cr, width, height, theme, home);

    if let Some(&(_, point)) = home.drag.as_ref() {
        if let Some(item) = home.dragged_item() {
            // A dragged icon lifts slightly larger than its resting plate
            // (matching iOS/webOS's jiggle-mode "pick up" scale) and always
            // shows its label, regardless of whether it started in the
            // grid, the dock, or the drawer, so what is being moved stays
            // legible under the finger. Widgets lift at their own (larger,
            // spanned) size instead of the single-cell icon plate size.
            let (plate_size, icon_size, label) = match &item {
                HomeItem::Widget { widget } => {
                    let (cols, rows) = widget.span();
                    let (_, _, w, h) = home_grid::spanned_tile_rect(width, height, 0, (cols, rows), columns);
                    (w.max(h), 0.0, None)
                }
                HomeItem::Folder(folder) => (home_grid::ICON_PLATE_SIZE * 1.08, home_grid::ICON_SIZE * 1.08, Some(folder.name.clone())),
                HomeItem::App { id } => (
                    home_grid::ICON_PLATE_SIZE * 1.08,
                    home_grid::ICON_SIZE * 1.08,
                    app_by_id(apps, id).map(|app| app.name.clone()),
                ),
            };
            let plate_x = point.0 - plate_size / 2.0;
            let plate_y = point.1 - plate_size / 2.0;
            if let HomeItem::Widget { widget } = &item {
                paint_widget_card(cr, &style, *widget, (plate_x, plate_y, plate_size, plate_size), home);
            } else {
                paint_item_plate(cr, theme, icons, apps, &item, plate_x, plate_y, plate_size, icon_size, true);
            }
            if let Some(label) = label {
                shadowed_label(
                    cr,
                    &label,
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
        &DrawerSearch::default(),
        &mut DrawerGridCache::default(),
    )
}

#[allow(clippy::too_many_arguments)]
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
    search: &DrawerSearch,
    grid_cache: &mut DrawerGridCache,
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
        search,
        grid_cache,
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
        &DrawerSearch::default(),
        &mut DrawerGridCache::default(),
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
    /// The launch splash's cached backdrop -- see `ensure_splash_bake`'s own
    /// doc. Lives here rather than on `ShellClient` because every other
    /// per-route cached bitmap this renderer owns (`static_pixels`,
    /// `preview_surface`, `thumbnails`) already lives on this cache, and the
    /// splash bake is architecturally the same kind of thing: a bitmap this
    /// renderer keeps so `ShellClient` never has to rebuild one itself.
    splash_bake: Option<SplashBake>,
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
    /// The Drawer's own live search field state -- set by `ShellClient`
    /// through `set_drawer_search`, read by `paint_drawer` every frame.
    drawer_search: DrawerSearch,
    /// The Drawer grid's pre-rendered bitmap -- see `DrawerGridCache`'s
    /// own doc. Persists across frames on purpose (that is the whole
    /// point); rebuilds only when its own key actually changes.
    drawer_grid: DrawerGridCache,
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

/// Layout still includes distant slices for painting/hit-testing. Decoding only
/// needs slices whose bounds reach the viewport, across BOTH carousel rows.
/// Rank them together so the two centers reach the bounded worker queue first.
fn theme_picker_working_set(chooser: Option<&ThemeView>, viewport_width: u32) -> Vec<ThumbnailKey> {
    let Some(chooser) = chooser.filter(|view| view.page == ThemePage::List) else {
        return Vec::new();
    };
    if viewport_width == 0 {
        return Vec::new();
    }
    let width = f64::from(viewport_width);
    let mut requested = Vec::new();
    fn add<'a>(
        requested: &mut Vec<(f64, ThumbnailKey)>,
        geometry: &theme_carousel::CarouselGeometry,
        position: f64,
        count: usize,
        width: f64,
        row: impl Fn(usize) -> Option<(&'a str, &'a std::path::Path)>,
    ) {
        for slice in theme_carousel::visible_slices(geometry, position, count, width / 2.0, 0.0) {
            if slice.x >= width || slice.x + slice.width <= 0.0 {
                continue;
            }
            let Some((id, path)) = row(slice.index) else {
                continue;
            };
            for variant in [Variant::Expanded, Variant::Slice] {
                let (width, height) = variant_size(geometry, variant);
                requested.push((
                    (slice.index as f64 - position).abs(),
                    ThumbnailKey {
                        id: id.to_owned(),
                        path: path.to_owned(),
                        variant,
                        width,
                        height,
                    },
                ));
            }
        }
    }
    if let Some(list) = chooser.list.as_ref() {
        add(
            &mut requested,
            &theme_carousel::THEME_GEOMETRY,
            chooser.theme_position,
            list.themes.len(),
            width,
            |index| {
                let entry = list.themes.get(index)?;
                Some((&entry.id, entry.preview_path.as_deref()?))
            },
        );
    }
    if let Some(preview) = chooser.preview.as_ref() {
        add(
            &mut requested,
            &theme_carousel::BACKGROUND_GEOMETRY,
            chooser.background_position,
            preview.backgrounds.len(),
            width,
            |index| {
                let entry = preview.backgrounds.get(index)?;
                (entry.kind == BackgroundKind::Image)
                    .then_some((entry.id.as_str(), entry.path.as_path()))
            },
        );
    }
    requested.sort_by(|a, b| a.0.total_cmp(&b.0));
    bounded_working_set(requested.into_iter().map(|(_, key)| key).collect())
}

impl RendererCache {
    pub fn content_generation(&self) -> u64 {
        self.content_generation
    }

    /// Paints the launch splash into `canvas`: the cached, name/geometry/
    /// status-keyed backdrop (rebuilt only when one of those actually
    /// changed -- see `ensure_splash_bake`'s own doc) plus the app's icon,
    /// composited fresh every call at `params.icon_alpha` so its fade-in
    /// can advance without rebuilding the backdrop text each frame.
    pub fn draw_splash(&mut self, canvas: &mut [u8], params: SplashParams) -> Result<(), String> {
        let SplashParams {
            width,
            height,
            name,
            icon,
            status,
            icon_alpha,
        } = params;
        ensure_splash_bake(&mut self.splash_bake, self.theme.as_ref(), name, width, height, status)?;
        let bake = self
            .splash_bake
            .as_ref()
            .ok_or("splash bake missing after ensure_splash_bake")?;
        draw_splash(canvas, bake, icon, &mut self.icons, icon_alpha)
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
    /// Request exactly the admitted visible working set shared by both rows.
    pub fn poll_theme_thumbnails(&mut self, viewport_width: u32) -> bool {
        let _profile = crate::runtime_trace::Span::new("thumbnail_poll");
        let requested = theme_picker_working_set(self.chooser.as_ref(), viewport_width);
        self.thumbnails.set_working_set(&requested);
        let changed = self.thumbnails.poll();
        if changed {
            self.content_generation = self.content_generation.wrapping_add(1);
            self.invalidate();
        }
        for key in requested {
            self.thumbnails.request(key);
        }
        changed
    }

    /// Offscreen/deferred entries must not keep polling and repainting spinners
    /// forever. Use the identical admitted set as the request path.
    pub fn theme_thumbnails_pending(&self, viewport_width: u32) -> bool {
        theme_picker_working_set(self.chooser.as_ref(), viewport_width)
            .iter().any(|key| !self.thumbnails.is_resolved(&key.id, key.variant))
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
    /// Sets the Drawer's live search field state -- a changed query or
    /// focus state changes what `paint_drawer` shows (a different filtered
    /// set, or the keyboard), so this forces the same kind of rebuild
    /// `set_drawer_pressed` does. Returns whether it actually changed.
    pub fn set_drawer_search(&mut self, search: DrawerSearch) -> bool {
        if self.drawer_search != search {
            self.drawer_search = search;
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

    /// Warms the Drawer's own pre-rendered grid bitmap (`DrawerGridCache`)
    /// for the unfiltered (no search query) catalog, at the current theme
    /// and panel width -- the coordinator's own board measurement,
    /// `K230_DRAWER_FRAME ms=549.89` on the drawer's first-ever open versus
    /// `1.04` on every one after, is entirely this bitmap's one-time build
    /// cost. Calling this proactively (`main.rs`, once at startup after the
    /// initial catalog scan, and again after a catalog rescan or a
    /// committed theme change) means that cost is paid before a person taps
    /// Apps at all, not the instant they do. A no-op if the cache is
    /// already fresh for this exact `(apps, theme, width)` -- rebuilding is
    /// `DrawerGridCache::ensure`'s own job, this only ever calls it with
    /// the drawer's steady, no-search-query state.
    pub fn prebuild_drawer_grid(&mut self, apps: &[AppEntry], width: u32, height: u32) {
        let content = DrawerContent {
            apps: apps.iter().collect(),
            search: &self.drawer_search,
        };
        let _ = self.drawer_grid.ensure(&content, self.theme.as_ref(), width, height, &mut self.icons);
    }

    #[cfg(test)]
    pub(crate) fn drawer_grid_rebuilds(&self) -> u64 {
        self.drawer_grid.rebuilds()
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
        let _profile = crate::runtime_trace::Span::new("overlay_prerender");
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
            &self.drawer_search,
            // A fresh, local cache: this method takes `&self`, and (per
            // its own doc) never actually renders `Route::Drawer` in
            // practice -- Optimistic Apply only pre-renders Settings.
            &mut DrawerGridCache::default(),
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

    /// Paints only the volume HUD onto an otherwise fully transparent
    /// canvas -- used instead of the ordinary route-based `draw` whenever
    /// nothing else (no open Drawer/Shade/Settings sheet) needs this
    /// shared overlay surface mapped at all, except to show the HUD (task:
    /// "render the HUD only while visible"). No scene cache, unlike
    /// `draw`'s own `static_pixels`: the HUD is small and shown rarely
    /// enough that a fresh paint on every call is cheap. Paints nothing
    /// (a fully transparent canvas, so whatever is behind this surface --
    /// Home, or a focused app -- shows through untouched) whenever the HUD
    /// isn't visible or no default sink has been reported yet.
    /// Paints only the HUD onto an otherwise fully transparent canvas of
    /// its own -- used by anything that wants the HUD isolated on a
    /// dedicated surface. `draw()`'s own live path instead calls
    /// `paint_hud_overlay` directly on its existing overlay context (see
    /// that function's own doc for why: a second full-screen surface's
    /// buffer pool/frame-callback lifecycle was judged not worth
    /// duplicating when the existing overlay layer can host the same
    /// pixels).
    pub fn draw_hud(
        &mut self,
        canvas: &mut [u8],
        width: u32,
        height: u32,
        hud: &Hud,
        now_ms: u64,
    ) -> Result<(), String> {
        let size = usize::try_from(width)
            .ok()
            .and_then(|w| w.checked_mul(height as usize))
            .and_then(|pixels| pixels.checked_mul(4))
            .ok_or("invalid HUD canvas geometry")?;
        if canvas.len() != size {
            return Err("invalid HUD canvas length".into());
        }
        canvas.fill(0);
        if !hud.is_visible(now_ms) {
            return Ok(());
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
        let audio = self.services.as_ref().and_then(|view| view.audio.as_ref());
        Self::paint_hud_overlay(
            &cr,
            self.theme.as_ref(),
            &mut self.icons,
            audio,
            hud,
            now_ms,
            f64::from(width),
            f64::from(height),
        );
        drop(cr);
        surface.flush();
        Ok(())
    }

    /// The HUD's own pixels (backdrop pill, speaker glyph, fill bar,
    /// expand affordance, and -- expanded -- one row per stream/sink),
    /// painted directly onto `cr`. Takes every input explicitly (no
    /// `&mut self`) for the same reason `paint_hud_row` does: `draw()`'s
    /// own live call site already holds other borrows of `self`
    /// (`self.service_view`/`self.hud`) it cannot also lend as `&mut
    /// self` through a method call. Does nothing (leaves whatever `cr`
    /// already had untouched) when `hud` is not currently visible or no
    /// default sink has been reported yet -- the "render the HUD only
    /// while visible" cost rule, enforced here rather than by the
    /// caller, so every call site gets it for free.
    #[allow(clippy::too_many_arguments)]
    fn paint_hud_overlay(
        cr: &Context,
        theme: Option<&AppearanceSnapshot>,
        icons: &mut IconCache,
        audio: Option<&GraphSnapshot>,
        hud: &Hud,
        now_ms: u64,
        width: f64,
        height: f64,
    ) {
        if !hud.is_visible(now_ms) {
            return;
        }
        let Some(sink) = default_sink(audio) else {
            return;
        };
        let percent = volume::linear_to_percent(sink.linear_volume);
        let muted = sink.muted;
        let expanded_rows = if hud.is_expanded() {
            audio.map_or(0, GraphSnapshot::expanded_row_count)
        } else {
            0
        };
        let geometry = volume::hud_geometry(width, height, hud.position_fraction(), expanded_rows);
        let style = visual_style(theme, "controls");
        // Backdrop: a rounded pill/card, never fully opaque so it still
        // reads as an overlay rather than a full sheet.
        rounded(
            cr,
            geometry.left,
            geometry.top,
            geometry.width,
            geometry.height,
            (geometry.width / 2.0).min(28.0),
        );
        color(cr, palette_rgb_or(theme, "background", 0x1e1e2e), 0.92);
        let _ = cr.fill();
        let center_x = geometry.left + geometry.width / 2.0;
        let icon_rgb = if muted { style.muted } else { style.accent };
        paint_speaker(cr, center_x, geometry.top + 30.0, 16.0, icon_rgb, 1.0, muted);
        // The vertical fill bar: the same inactive/active-track idea
        // `paint_slider_track` uses, rotated, at a scale that fits the
        // pill rather than the full panel width.
        let bar_top = geometry.top + 60.0;
        let bar_bottom = geometry.top + geometry.collapsed_h - 26.0;
        let bar_h = (bar_bottom - bar_top).max(1.0);
        rounded(cr, center_x - 6.0, bar_top, 12.0, bar_h, 6.0);
        color(cr, style.muted, 0.35);
        let _ = cr.fill();
        let fill_h = bar_h * f64::from(percent) / 100.0;
        rounded(cr, center_x - 6.0, bar_bottom - fill_h, 12.0, fill_h, 6.0);
        color(cr, style.accent, 1.0);
        let _ = cr.fill();
        // The "..." expand affordance, always at the same offset from the
        // pill's own top whether or not it is currently expanded.
        text(
            cr,
            "\u{2026}",
            geometry.left,
            geometry.top + geometry.collapsed_h - 22.0,
            geometry.width,
            16.0,
            style.muted,
        );
        if expanded_rows > 0 {
            if let Some(audio) = audio {
                for index in 0..expanded_rows {
                    let Some(row) = audio.expanded_row(index) else {
                        continue;
                    };
                    let row_top = geometry.top + geometry.collapsed_h + index as f64 * volume::HUD_ROW_H;
                    Self::paint_hud_row(icons, cr, style, &geometry, row_top, row);
                }
            }
        }
    }

    /// One row of the HUD's expanded panel: a stream gets its own name/
    /// icon and a mini horizontal volume slider; a sink gets its
    /// description and a filled/hollow dot marking whether it is the
    /// current default (the output device picker, task: "in the expanded
    /// panel"). A free function, not a method, so its `&mut IconCache`
    /// borrow stays disjoint from the `self.services`-derived `audio`
    /// borrow its caller (`draw_hud`) is still holding across the loop.
    fn paint_hud_row(
        icons: &mut IconCache,
        cr: &Context,
        style: VisualStyle,
        geometry: &volume::HudGeometry,
        row_top: f64,
        row: crate::pipewire_ipc::ExpandedRow,
    ) {
        let left = geometry.left + 12.0;
        let width = geometry.width - 24.0;
        match row {
            crate::pipewire_ipc::ExpandedRow::Stream(stream) => {
                let painted = stream
                    .app_icon
                    .as_deref()
                    .is_some_and(|icon| icons.paint(cr, icon, 28, left, row_top + 6.0));
                if !painted {
                    rounded(cr, left, row_top + 6.0, 28.0, 28.0, 14.0);
                    color(cr, style.muted, 0.4);
                    let _ = cr.fill();
                    text(
                        cr,
                        &stream
                            .app_name
                            .chars()
                            .next()
                            .unwrap_or('?')
                            .to_uppercase()
                            .to_string(),
                        left + 7.0,
                        row_top + 10.0,
                        18.0,
                        16.0,
                        style.text,
                    );
                }
                text(cr, &stream.app_name, left + 36.0, row_top + 8.0, width - 36.0, 15.0, style.text);
                let percent = volume::linear_to_percent(stream.linear_volume);
                let track_left = left + 36.0;
                let track_right = geometry.left + geometry.width - 12.0;
                let track_w = (track_right - track_left).max(1.0);
                let track_y = row_top + 38.0;
                rounded(cr, track_left, track_y, track_w, 8.0, 4.0);
                color(cr, style.muted, 0.35);
                let _ = cr.fill();
                let fill_w = track_w * f64::from(percent) / 100.0;
                rounded(cr, track_left, track_y, fill_w.max(8.0), 8.0, 4.0);
                color(cr, if stream.muted { style.muted } else { style.accent }, 1.0);
                let _ = cr.fill();
            }
            crate::pipewire_ipc::ExpandedRow::Sink(sink) => {
                text(cr, &sink.description, left, row_top + 8.0, width - 28.0, 15.0, style.text);
                let dot_x = geometry.left + geometry.width - 22.0;
                let dot_y = row_top + 16.0;
                cr.new_sub_path();
                cr.arc(dot_x, dot_y, 7.0, 0.0, std::f64::consts::TAU);
                color(cr, style.accent, if sink.is_default { 1.0 } else { 0.25 });
                let _ = cr.fill();
            }
        }
    }

    /// Convenience wrapper over [`Self::draw_with_hud`] for every call
    /// site (most of this module's own pixel-sampled tests) that has no
    /// opinion about the volume HUD at all: a freshly-constructed `Hud`
    /// is never visible (`Hud::is_visible` needs a prior `show()`), so
    /// this paints exactly what `draw_with_hud` would with the HUD
    /// simply not shown -- zero behavior difference for any caller that
    /// never had a HUD concept to begin with.
    pub fn draw(
        &mut self,
        canvas: &mut [u8],
        params: RenderParams,
        apps: &[AppEntry],
    ) -> Result<(), String> {
        self.draw_with_hud(canvas, params, apps, &Hud::default(), 0)
    }

    #[allow(clippy::too_many_arguments)]
    pub fn draw_with_hud(
        &mut self,
        canvas: &mut [u8],
        params: RenderParams,
        apps: &[AppEntry],
        hud: &Hud,
        hud_now_ms: u64,
    ) -> Result<(), String> {
        let _profile = crate::runtime_trace::Span::new("render_total");
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
        self.poll_theme_thumbnails(width);
        if self.route != Some(route)
            || self.width != width
            || self.height != height
            || (self.scroll - scroll).abs() >= 0.25
        {
            let _profile = crate::runtime_trace::Span::new("scene_rebuild");
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
                &self.drawer_search,
                &mut self.drawer_grid,
            )?;
            self.static_pixels = painted;
            self.width = width;
            self.height = height;
            self.route = Some(route);
            self.scroll = scroll;
            self.rebuilds += 1;
        }
        let _profile_copy = crate::runtime_trace::Span::new("canvas_copy");
        canvas.fill(0);
        let panel_height =
            panel_travel_height(route, width, height, self.chooser.as_ref(), self.services.as_ref());
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
        //
        // The volume HUD paints last, directly onto this same canvas/
        // context, on top of whatever route this call just composited --
        // it is not cached into `static_pixels` (unlike the rest of this
        // method's own content) because it is small, shown rarely, and
        // its own visibility/position/expand state changes far more
        // often than a full scene rebuild should be triggered for.
        // `paint_hud_overlay` itself is a no-op (zero Cairo calls) the
        // instant `hud.is_visible` reads false, so an idle HUD costs
        // nothing here beyond that one check.
        //
        // Known gap, not yet closed: this only runs while this overlay
        // layer surface is already mapped (a Drawer/Shade/Settings sheet
        // is open) -- `main.rs`'s own touch dispatch already treats the
        // HUD as route-independent (`hud_touch_down` is checked before
        // any route-specific branch), but nothing yet forces this layer
        // surface to exist purely because the HUD wants to show while
        // the Home screen alone is visible with nothing else open. See
        // `openspec/changes/the-handheld-controls-volume/tasks.md`.
        if hud.is_visible(hud_now_ms) {
            let surface = unsafe {
                ImageSurface::create_for_data_unsafe(
                    canvas.as_mut_ptr(),
                    Format::ARgb32,
                    width as i32,
                    height as i32,
                    row_bytes as i32,
                )
            }
            .map_err(|e| e.to_string())?;
            let cr = Context::new(&surface).map_err(|e| e.to_string())?;
            let audio = self.services.as_ref().and_then(|view| view.audio.as_ref());
            Self::paint_hud_overlay(
                &cr,
                self.theme.as_ref(),
                &mut self.icons,
                audio,
                hud,
                hud_now_ms,
                f64::from(width),
                f64::from(height),
            );
            drop(cr);
            surface.flush();
        }
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

    /// Renders the Drawer's own overlay surface while task 1's long-press-
    /// drag is live and no reveal animation is (or is no longer) playing
    /// (`main.rs`'s `drawer_home_drag`): transparent everywhere except a
    /// translucent Cancel band across the drawer's own former top-chrome
    /// zone (`navigation::drag_cancel_zone_hit`'s exact zone). Home's
    /// `Layer::Bottom` surface underneath already paints the lifted icon
    /// and drop-target highlight itself (`paint_home`), so this
    /// deliberately draws nothing else, letting that show through
    /// untouched. See [`Self::draw_drawer_reveal`] for the brief animated
    /// transition into this steady state.
    pub fn draw_drawer_drag(&mut self, canvas: &mut [u8], width: u32, height: u32) -> Result<(), String> {
        draw_drawer_drag_shm(canvas, width, height, self.theme.as_ref())
    }

    /// Renders the drawer's long-press-drag reveal *animation* (coordinator
    /// follow-up: "the drawer should visibly slide down or fade out over
    /// about 180-220 ms with ease-out, not vanish"): `snapshot` is a plain
    /// pixel copy of the drawer's own last rendered frame, taken once at
    /// the instant the drag armed (`main.rs::begin_drawer_home_drag`), and
    /// this composites it translated down and faded by `progress` (0.0 at
    /// the start of the animation, 1.0 once it's fully played out) -- cheap
    /// because it is exactly one more `cairo_paint_with_alpha` of an
    /// already-rendered image, not a second scene re-render every frame.
    /// The Cancel band paints on top throughout, so it is reachable from
    /// the very first frame of the drag, before the animation even starts.
    pub fn draw_drawer_reveal(
        &self,
        canvas: &mut [u8],
        width: u32,
        height: u32,
        snapshot: &[u8],
        progress: f64,
    ) -> Result<(), String> {
        draw_drawer_reveal_shm(canvas, width, height, snapshot, progress, self.theme.as_ref())
    }
}

fn draw_drawer_drag_shm(canvas: &mut [u8], width: u32, height: u32, theme: Option<&AppearanceSnapshot>) -> Result<(), String> {
    let stride = width.checked_mul(4).ok_or("invalid stride")?;
    if canvas.len() != usize::try_from(stride).unwrap_or(usize::MAX) * height as usize {
        return Err("invalid canvas length".into());
    }
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(canvas.as_mut_ptr(), Format::ARgb32, width as i32, height as i32, stride as i32)
    }
    .map_err(|error| error.to_string())?;
    let cr = Context::new(&surface).map_err(|error| error.to_string())?;
    cr.set_operator(Operator::Source);
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.0);
    let _ = cr.paint();
    cr.set_operator(Operator::Over);
    draw_drawer_cancel_band(&cr, width, theme);
    drop(cr);
    surface.flush();
    Ok(())
}

/// The Cancel band alone (task 1's Cancel target), shared by
/// [`draw_drawer_drag_shm`]'s steady state and [`draw_drawer_reveal_shm`]'s
/// animated one so the two never drift apart pixel-for-pixel.
fn draw_drawer_cancel_band(cr: &Context, width: u32, theme: Option<&AppearanceSnapshot>) {
    let style = visual_style(theme, "launcher");
    let band_h = 56.0_f64.max(navigation::list_top(1232) - 24.0);
    service_card(cr, theme, "controls", 12.0, 12.0, f64::from(width) - 24.0, band_h, false);
    centered_label(cr, "Cancel", 12.0, 12.0 + band_h / 2.0 - 14.0, f64::from(width) - 24.0, 26.0, style.error);
}

/// Ease-out-cubic progress, matching every other settle animation in this
/// shell (`home_pager::HomePager`'s own tick, `theme_carousel::Carousel`'s
/// settle) rather than inventing a fourth easing curve.
fn ease_out_cubic(t: f64) -> f64 {
    let t = t.clamp(0.0, 1.0);
    1.0 - (1.0 - t).powi(3)
}

fn draw_drawer_reveal_shm(
    canvas: &mut [u8],
    width: u32,
    height: u32,
    snapshot: &[u8],
    progress: f64,
    theme: Option<&AppearanceSnapshot>,
) -> Result<(), String> {
    let stride = width.checked_mul(4).ok_or("invalid stride")?;
    let expected = usize::try_from(stride).unwrap_or(usize::MAX) * height as usize;
    if canvas.len() != expected {
        return Err("invalid canvas length".into());
    }
    if snapshot.len() != expected {
        return Err("snapshot size mismatch".into());
    }
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(canvas.as_mut_ptr(), Format::ARgb32, width as i32, height as i32, stride as i32)
    }
    .map_err(|error| error.to_string())?;
    let cr = Context::new(&surface).map_err(|error| error.to_string())?;
    cr.set_operator(Operator::Source);
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.0);
    let _ = cr.paint();
    cr.set_operator(Operator::Over);
    let eased = ease_out_cubic(progress);
    // A plain pixel copy handed to Cairo's owned-data constructor -- one
    // `memcpy` of an already-rendered frame, not a re-render of the scene.
    let owned_snapshot = snapshot.to_vec();
    if let Ok(snap_surface) = ImageSurface::create_for_data(owned_snapshot, Format::ARgb32, width as i32, height as i32, stride as i32) {
        let alpha = (1.0 - eased).clamp(0.0, 1.0);
        if alpha > 0.001 {
            let travel = eased * 48.0; // a modest downward slide alongside the fade
            let _ = cr.save();
            cr.translate(0.0, travel);
            if cr.set_source_surface(&snap_surface, 0.0, 0.0).is_ok() {
                let _ = cr.paint_with_alpha(alpha);
            }
            let _ = cr.restore();
        }
    }
    draw_drawer_cancel_band(&cr, width, theme);
    drop(cr);
    surface.flush();
    Ok(())
}

/// The launch splash's icon size: large and centered, per the launch-splash
/// design's Android-12 reference. This is above `icon::IconCache`'s old
/// 128px decode cap (raised alongside this feature -- see that module's own
/// `decode` doc), since every existing caller before this feature asked for
/// 108px at most (`home_grid`'s icon plate).
pub const SPLASH_ICON_SIZE: i32 = 176;

fn splash_status_code(status: SplashStatus) -> u8 {
    match status {
        SplashStatus::Pending => 0,
        SplashStatus::TimedOut => 1,
        SplashStatus::Failed => 2,
    }
}

fn draw_centered(cr: &Context, value: &str, y: f64, width: f64, size: f64, rgb: u32) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(size * f64::from(pango::SCALE));
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
    layout.set_alignment(Alignment::Center);
    layout.set_ellipsize(EllipsizeMode::End);
    color(cr, rgb, 1.0);
    cr.move_to(0.0, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// The launch splash's cached, name/geometry/status-keyed backdrop: the
/// theme's opaque background colour plus every line of text, baked exactly
/// once per distinct `(name, width, height, status)` -- see
/// `ensure_splash_bake`'s own doc for why text is what gets cached here
/// (Pango font shaping, not the icon, is the one part of this scene that
/// is not already cheap to repeat every frame). The icon itself is
/// composited fresh each frame by `draw_splash` so its fade-in alpha can
/// change without rebuilding this bake.
pub struct SplashBake {
    key: (String, u32, u32, u8),
    width: u32,
    height: u32,
    pixels: Vec<u8>,
    icon_x: f64,
    icon_y: f64,
}

fn build_splash_bake(
    theme: Option<&AppearanceSnapshot>,
    name: &str,
    width: u32,
    height: u32,
    status: SplashStatus,
) -> Result<SplashBake, String> {
    let size = usize::try_from(width)
        .ok()
        .and_then(|w| w.checked_mul(height as usize))
        .and_then(|pixels| pixels.checked_mul(4))
        .ok_or("invalid splash geometry")?;
    let mut pixels = vec![0u8; size];
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(
            pixels.as_mut_ptr(),
            Format::ARgb32,
            width as i32,
            height as i32,
            (width * 4) as i32,
        )
    }
    .map_err(|e| e.to_string())?;
    let cr = Context::new(&surface).map_err(|e| e.to_string())?;
    // Opaque on this very first paint -- the previously active app must
    // never show through, even for one frame, so unlike the icon/name
    // below this backdrop fill carries no fade of its own.
    cr.set_operator(Operator::Source);
    color(&cr, palette_rgb_or(theme, "background", 0x1e1e2e), 1.0);
    cr.paint().map_err(|e| e.to_string())?;
    cr.set_operator(Operator::Over);
    if let Some(brush) = theme_brush(theme, "splash", "background") {
        let _ = fill_brush(&cr, brush, 0.0, 0.0, width as f64, height as f64);
    }
    let style = visual_style(theme, "splash");
    let icon_x = (f64::from(width) - f64::from(SPLASH_ICON_SIZE)) / 2.0;
    let icon_y = f64::from(height) * 0.36 - f64::from(SPLASH_ICON_SIZE) / 2.0;
    let label_y = icon_y + f64::from(SPLASH_ICON_SIZE) + 28.0;
    let (primary, primary_color) = match status {
        SplashStatus::Pending | SplashStatus::TimedOut => (name.to_string(), style.text),
        SplashStatus::Failed => (format!("Couldn't open {name}"), style.error),
    };
    draw_centered(&cr, &primary, label_y, width as f64, 30.0, primary_color);
    if status == SplashStatus::TimedOut {
        draw_centered(
            &cr,
            "Taking longer than usual…",
            label_y + 40.0,
            width as f64,
            20.0,
            style.muted,
        );
        draw_centered(
            &cr,
            "Tap to go Home",
            label_y + 70.0,
            width as f64,
            18.0,
            style.accent,
        );
    }
    drop(cr);
    surface.flush();
    Ok(SplashBake {
        key: (name.to_string(), width, height, splash_status_code(status)),
        width,
        height,
        pixels,
        icon_x,
        icon_y,
    })
}

/// Rebuilds `*bake` only when `(name, width, height, status)` actually
/// changed from whatever it already holds -- an ordinary `Pending` splash
/// showing the same app never rebuilds a second time, matching this
/// hardware's "render the splash bitmap once, then only fade" budget.
fn ensure_splash_bake(
    bake: &mut Option<SplashBake>,
    theme: Option<&AppearanceSnapshot>,
    name: &str,
    width: u32,
    height: u32,
    status: SplashStatus,
) -> Result<(), String> {
    let key = (name.to_string(), width, height, splash_status_code(status));
    if bake.as_ref().is_some_and(|existing| existing.key == key) {
        return Ok(());
    }
    *bake = Some(build_splash_bake(theme, name, width, height, status)?);
    Ok(())
}

/// Paints `bake`'s cached backdrop into `canvas`, then composites the
/// app's icon on top at `icon_alpha` (the only thing that changes from one
/// frame to the next while a splash is fading in). `icons` is the same
/// `IconCache` every other surface shares, so this icon is itself already
/// decoded at most once regardless of how many frames the fade takes.
fn draw_splash(
    canvas: &mut [u8],
    bake: &SplashBake,
    icon: Option<&str>,
    icons: &mut IconCache,
    icon_alpha: f64,
) -> Result<(), String> {
    if canvas.len() != bake.pixels.len() {
        return Err("invalid splash canvas".into());
    }
    canvas.copy_from_slice(&bake.pixels);
    let Some(icon) = icon else {
        return Ok(());
    };
    let alpha = icon_alpha.clamp(0.0, 1.0);
    if alpha <= 0.0 {
        return Ok(());
    }
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(
            canvas.as_mut_ptr(),
            Format::ARgb32,
            bake.width as i32,
            bake.height as i32,
            (bake.width * 4) as i32,
        )
    }
    .map_err(|e| e.to_string())?;
    let cr = Context::new(&surface).map_err(|e| e.to_string())?;
    cr.push_group();
    icons.paint(&cr, icon, SPLASH_ICON_SIZE, bake.icon_x, bake.icon_y);
    if cr.pop_group_to_source().is_ok() {
        let _ = cr.paint_with_alpha(alpha);
    }
    drop(cr);
    surface.flush();
    Ok(())
}

#[cfg(test)]
mod splash_render_tests {
    use super::*;

    #[test]
    fn ensure_splash_bake_only_rebuilds_on_a_key_change() {
        let mut bake: Option<SplashBake> = None;
        ensure_splash_bake(&mut bake, None, "Foot", 568, 1232, SplashStatus::Pending).unwrap();
        let first_pixels = bake.as_ref().unwrap().pixels.clone();
        // Same key: must not reallocate/rebuild (same bytes, and cheap to
        // call repeatedly every frame while pending).
        ensure_splash_bake(&mut bake, None, "Foot", 568, 1232, SplashStatus::Pending).unwrap();
        assert_eq!(bake.as_ref().unwrap().pixels, first_pixels);
        // A status change (Pending -> TimedOut) must rebuild: the baked
        // text differs.
        ensure_splash_bake(&mut bake, None, "Foot", 568, 1232, SplashStatus::TimedOut).unwrap();
        assert_ne!(bake.as_ref().unwrap().pixels, first_pixels);
    }

    #[test]
    fn draw_splash_backdrop_is_fully_opaque_even_before_the_icon_fades_in() {
        let mut bake: Option<SplashBake> = None;
        ensure_splash_bake(&mut bake, None, "Foot", 40, 40, SplashStatus::Pending).unwrap();
        let bake = bake.unwrap();
        let mut icons = IconCache::new();
        let mut canvas = vec![0u8; 40 * 40 * 4];
        // icon_alpha 0.0: the very first frame, before any fade progress.
        draw_splash(&mut canvas, &bake, Some("foot"), &mut icons, 0.0).unwrap();
        assert!(
            canvas.chunks_exact(4).all(|pixel| pixel[3] == 255),
            "every backdrop pixel must be fully opaque on the first splash frame"
        );
    }

    #[test]
    fn draw_splash_rejects_a_mismatched_canvas_size() {
        let mut bake: Option<SplashBake> = None;
        ensure_splash_bake(&mut bake, None, "Foot", 40, 40, SplashStatus::Pending).unwrap();
        let bake = bake.unwrap();
        let mut icons = IconCache::new();
        let mut wrong = vec![0u8; 10];
        assert!(draw_splash(&mut wrong, &bake, None, &mut icons, 1.0).is_err());
    }

    #[test]
    fn a_failed_launch_bakes_the_couldnt_open_message_distinctly() {
        let mut pending: Option<SplashBake> = None;
        ensure_splash_bake(&mut pending, None, "Foot", 200, 200, SplashStatus::Pending).unwrap();
        let mut failed: Option<SplashBake> = None;
        ensure_splash_bake(&mut failed, None, "Foot", 200, 200, SplashStatus::Failed).unwrap();
        assert_ne!(pending.unwrap().pixels, failed.unwrap().pixels);
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
        // +126 (SETTINGS_ROW_H + SETTINGS_ROW_GAP) from the pre-volume-row
        // values: the Volume row (task: "in Settings") added a fifth
        // settings row, cascading every value below it down by one row's
        // rhythm, same as `NOTIFICATION_TOP`'s own shift for the shade.
        let layout = settings_layout();
        assert_eq!(layout.power_heading_y, 798.0);
        assert_eq!(layout.reboot_y, 826.0);
        assert_eq!(layout.poweroff_y, 912.0);
        assert_eq!(layout.poweroff_bottom, 982.0);
    }

    #[test]
    fn settings_confirm_layout_follows_whatever_precedes_it() {
        let confirm = settings_confirm_layout(982.0);
        assert_eq!(confirm.label_y, 996.0);
        assert_eq!(confirm.card_y, 1024.0);
        assert_eq!(confirm.bottom, 1134.0);
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
    use crate::pipewire_ipc::{Sink, Stream};
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
                path: PathBuf::new(),
            },
            AppEntry {
                id: "monitor.desktop".into(),
                name: "Monitor".into(),
                icon: Some("system-monitor-app".into()),
                path: PathBuf::new(),
            },
            AppEntry {
                id: "video.desktop".into(),
                name: "Video".into(),
                icon: None,
                path: PathBuf::new(),
            },
            AppEntry {
                id: "files.desktop".into(),
                name: "Files".into(),
                icon: None,
                path: PathBuf::new(),
            },
            AppEntry {
                id: "editor.desktop".into(),
                name: "Editor".into(),
                icon: None,
                path: PathBuf::new(),
            },
            AppEntry {
                id: "help.desktop".into(),
                name: "Help".into(),
                icon: None,
                path: PathBuf::new(),
            },
            AppEntry {
                id: "foot-server.desktop".into(),
                name: "Foot Server".into(),
                icon: None,
                path: PathBuf::new(),
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
                motion: unavailable.clone(),
                volume: unavailable,
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
            ("power", Route::Power, None),
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

    fn theme_picker_two_row_fixture() -> ThemeView {
        let themes: Vec<_> = (0..40)
            .map(|i| ThemeEntry {
                id: format!("theme-{i}"),
                name: format!("Theme {i}"),
                label: format!("Theme {i}"),
                origin: ThemeOrigin::Builtin,
                preview_path: Some(format!("/unused/theme-{i}.png").into()),
            })
            .collect();
        ThemeView {
            page: ThemePage::List,
            theme_position: 20.0,
            background_position: 20.0,
            preview: Some(ThemePreview {
                theme: themes[20].clone(),
                generation: "fixture-generation".into(),
                appearance_path: "/unused/appearance.json".into(),
                palette: BTreeMap::new(),
                icon_theme: None,
                backgrounds: (0..40)
                    .map(|i| BackgroundChoice {
                        id: format!("background-{i}"),
                        label: format!("Background {i}"),
                        path: format!("/unused/background-{i}.png").into(),
                        kind: BackgroundKind::Image,
                        selected: i == 20,
                        decode_status: "unverified".into(),
                    })
                    .collect(),
                compatibility: Compatibility {
                    applied: vec![],
                    unavailable: vec![],
                    unknown: vec![],
                },
                activated: false,
                app_appearance: None,
            }),
            list: Some(ThemeList {
                themes,
                active: ActiveTheme {
                    id: None,
                    generation: None,
                },
            }),
            ..ThemeView::default()
        }
    }

    #[test]
    fn theme_picker_two_carousels_warm_without_continual_requeues() {
        use crate::theme_thumbnails::{CACHE_CAP, CACHE_MAX_BYTES};
        let view = theme_picker_two_row_fixture();
        let old_demand = 2
            * (theme_carousel::visible_slices(
                &theme_carousel::THEME_GEOMETRY,
                20.0,
                40,
                284.0,
                0.0,
            )
            .len()
                + theme_carousel::visible_slices(
                    &theme_carousel::BACKGROUND_GEOMETRY,
                    20.0,
                    40,
                    284.0,
                    0.0,
                )
                .len());
        assert_eq!(old_demand, 68);
        assert!(old_demand > CACHE_CAP);
        let (thumbnails, incoming, complete) = ThemeThumbnailCache::fixture();
        let mut renderer = RendererCache {
            thumbnails,
            ..RendererCache::default()
        };
        renderer.set_theme_view(view.clone());
        let expected = theme_picker_working_set(Some(&view), 568);
        assert_eq!(expected.len(), 24); // five hero slices + seven background slices
        assert_eq!(expected[0].id, "theme-20");
        assert_eq!(expected[2].id, "background-20"); // both centers claim first queue slots
        let mut admitted = Vec::new();
        for _ in 0..100 {
            renderer.poll_theme_thumbnails(568);
            for key in incoming.try_iter() {
                admitted.push((key.id.clone(), key.variant));
                complete(key);
            }
            if !renderer.theme_thumbnails_pending(568) {
                break;
            }
        }
        assert!(!renderer.theme_thumbnails_pending(568));
        assert_eq!(renderer.thumbnails.submitted_count(), expected.len());
        assert_eq!(
            admitted,
            expected
                .iter()
                .map(|key| (key.id.clone(), key.variant))
                .collect::<Vec<_>>()
        );
        for _ in 0..200 {
            assert!(!renderer.poll_theme_thumbnails(568));
            assert!(!renderer.theme_thumbnails_pending(568));
            assert!(incoming.try_recv().is_err());
        }
        assert_eq!(renderer.thumbnails.submitted_count(), expected.len());
        assert!(renderer.thumbnails.known_len() <= CACHE_CAP);
        assert!(renderer.thumbnails.resident_bytes() <= CACHE_MAX_BYTES);

        // Move both rows, including half-way positions and a wider viewport.
        // Each new settled set must converge without increasing either bound.
        for (theme, background, width) in [(21.4, 18.6, 568), (5.0, 5.0, 568), (25.0, 25.0, 1800)] {
            let mut moved = view.clone();
            moved.theme_position = theme;
            moved.background_position = background;
            renderer.set_theme_view(moved);
            for _ in 0..100 {
                renderer.poll_theme_thumbnails(width);
                for key in incoming.try_iter() {
                    complete(key);
                }
                if !renderer.theme_thumbnails_pending(width) {
                    break;
                }
            }
            assert!(!renderer.theme_thumbnails_pending(width));
            let submissions = renderer.thumbnails.submitted_count();
            for _ in 0..50 {
                assert!(!renderer.poll_theme_thumbnails(width));
            }
            assert_eq!(renderer.thumbnails.submitted_count(), submissions);
            assert!(renderer.thumbnails.known_len() <= CACHE_CAP);
            assert!(renderer.thumbnails.resident_bytes() <= CACHE_MAX_BYTES);
        }
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
        assert!(renderer.theme_thumbnails_pending(568));
        assert!(
            !renderer.poll_theme_thumbnails(568),
            "issuing a decode request must not itself report a change"
        );
        // And immediately calling it again, before the worker thread has
        // plausibly finished a real decode, must still report no change --
        // repeated polling alone is never a reason to redraw.
        assert!(
            !renderer.poll_theme_thumbnails(568),
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
            renderer.poll_theme_thumbnails(568);
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
            renderer.poll_theme_thumbnails(568);
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
                motion: unavailable.clone(),
                volume: unavailable,
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
        // Rows shifted +76 again along with `NOTIFICATION_TOP` itself
        // (task: "volume slider in the shade under the brightness
        // slider" -- room for the second header slider pushed the whole
        // list down once more, from 342 to 418) -- 431+76=507.
        let region = (507 * 568 * 4)..(527 * 568 * 4);
        assert!(normal[region.clone()] != failed[region]);
    }

    fn audio_view_with_one_sink(percent: u8, muted: bool) -> ServiceView {
        ServiceView {
            audio: Some(GraphSnapshot {
                sinks: vec![Sink {
                    id: 50,
                    name: "alsa_output.inno".into(),
                    description: "K230 Inno codec line-out".into(),
                    linear_volume: volume::percent_to_linear(percent),
                    muted,
                    is_default: true,
                }],
                streams: vec![Stream {
                    id: 78,
                    app_name: "k230 video".into(),
                    app_icon: Some("multimedia-player".into()),
                    linear_volume: 1.0,
                    muted: false,
                }],
            }),
            ..ServiceView::default()
        }
    }

    #[test]
    fn draw_with_hud_composites_the_pill_on_top_of_the_live_settings_scene() {
        // `draw_with_hud` (the real live-canvas path `main.rs` calls,
        // unlike `draw_hud`'s own separate/isolated canvas above) must
        // still show the pill on top of whatever route is already
        // painted there -- proving the HUD reaches the one canvas that
        // is actually ever attached to a Wayland surface, not just its
        // own standalone test surface.
        let mut renderer = RendererCache::default();
        renderer.set_services(audio_view_with_one_sink(60, false));
        let mut without_hud = vec![0u8; 568 * 1232 * 4];
        renderer
            .draw(&mut without_hud, SETTINGS_PARAMS, &[])
            .unwrap();
        let mut hud = volume::Hud::new();
        hud.show(0);
        let mut with_hud = vec![0u8; 568 * 1232 * 4];
        renderer
            .draw_with_hud(&mut with_hud, SETTINGS_PARAMS, &[], &hud, 0)
            .unwrap();
        assert_ne!(without_hud, with_hud, "the HUD did not reach the live canvas");
        // A pixel squarely inside the collapsed pill's own backdrop
        // (`volume::hud_geometry(568.0, 1232.0, 0.5, 0)`'s own left/top)
        // must actually have changed, not just some unrelated pixel
        // elsewhere on the frame.
        let geometry = volume::hud_geometry(568.0, 1232.0, hud.position_fraction(), 0);
        let x = (geometry.left + 10.0) as usize;
        let y = (geometry.top + 10.0) as usize;
        let index = (y * 568 + x) * 4;
        assert_ne!(&without_hud[index..index + 4], &with_hud[index..index + 4]);
    }

    #[test]
    fn draw_hud_paints_nothing_while_hidden_and_the_pill_once_shown() {
        let mut renderer = RendererCache::default();
        renderer.set_services(audio_view_with_one_sink(60, false));
        let mut hidden = vec![0u8; 568 * 1232 * 4];
        renderer
            .draw_hud(&mut hidden, 568, 1232, &volume::Hud::new(), 0)
            .unwrap();
        assert!(hidden.iter().all(|&byte| byte == 0));
        let mut hud = volume::Hud::new();
        hud.show(0);
        let mut shown = vec![0u8; 568 * 1232 * 4];
        renderer.draw_hud(&mut shown, 568, 1232, &hud, 0).unwrap();
        assert!(shown.iter().any(|&byte| byte != 0));
    }

    #[test]
    fn draw_hud_expanded_panel_is_taller_and_wider_than_the_collapsed_pill() {
        let mut renderer = RendererCache::default();
        renderer.set_services(audio_view_with_one_sink(60, false));
        let mut collapsed_hud = volume::Hud::new();
        collapsed_hud.show(0);
        let mut collapsed = vec![0u8; 568 * 1232 * 4];
        renderer
            .draw_hud(&mut collapsed, 568, 1232, &collapsed_hud, 0)
            .unwrap();
        let mut expanded_hud = volume::Hud::new();
        expanded_hud.toggle_expand(0);
        let mut expanded = vec![0u8; 568 * 1232 * 4];
        renderer
            .draw_hud(&mut expanded, 568, 1232, &expanded_hud, 0)
            .unwrap();
        // Derived from the same geometry function `draw_hud` itself calls
        // (one sink, zero streams -- exactly one expanded row), not a
        // magic screen coordinate: `position_fraction`'s default centers
        // the pill vertically, so a fixed probe point picked without this
        // would land outside both panels' bounds instead of inside them.
        let collapsed_geometry =
            volume::hud_geometry(568.0, 1232.0, collapsed_hud.position_fraction(), 0);
        let expanded_geometry =
            volume::hud_geometry(568.0, 1232.0, expanded_hud.position_fraction(), 1);
        assert!(expanded_geometry.width > collapsed_geometry.width);
        assert!(expanded_geometry.height > collapsed_geometry.height);
        // A column just inside the expanded panel's own left edge, at a
        // row inside its expanded-only body (below the collapsed pill's
        // own height): the collapsed pill never reaches this far left, so
        // this point is untouched when collapsed but painted once
        // expanded.
        let probe_x = (expanded_geometry.left + 10.0) as usize;
        let probe_y = (expanded_geometry.top + expanded_geometry.collapsed_h + 10.0) as usize;
        let index = (probe_y * 568 + probe_x) * 4;
        assert_eq!(&collapsed[index..index + 4], &[0, 0, 0, 0]);
        assert_ne!(&expanded[index..index + 4], &[0, 0, 0, 0]);
    }

    #[test]
    fn draw_hud_reflects_mute_state_in_different_pixels_than_unmuted() {
        let mut muted_renderer = RendererCache::default();
        muted_renderer.set_services(audio_view_with_one_sink(60, true));
        let mut unmuted_renderer = RendererCache::default();
        unmuted_renderer.set_services(audio_view_with_one_sink(60, false));
        let mut hud = volume::Hud::new();
        hud.show(0);
        let mut muted_pixels = vec![0u8; 568 * 1232 * 4];
        muted_renderer
            .draw_hud(&mut muted_pixels, 568, 1232, &hud, 0)
            .unwrap();
        let mut unmuted_pixels = vec![0u8; 568 * 1232 * 4];
        unmuted_renderer
            .draw_hud(&mut unmuted_pixels, 568, 1232, &hud, 0)
            .unwrap();
        assert_ne!(muted_pixels, unmuted_pixels);
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
    fn close_drag_progress_shifts_the_panel_and_dims_the_backdrop_together() {
        // Models a live close drag: the same `RendererCache::draw` a
        // pull-down open uses, fed a progress descending from 1.0 as the
        // finger pulls the shade back up -- there is no separate "closing"
        // code path (the whole point of reusing the row-shift renderer).
        // At progress = 0.4, y = 750 sits inside the fully-open panel's own
        // background (opaque there at progress 1.0), but the panel has
        // shifted up out of that row by then, so it must read as backdrop
        // (present, and dimmed to exactly this progress's eased value) --
        // not still-opaque panel and not the old bug's blank gap either.
        let mut renderer = RendererCache::default();
        let alpha_at = |frame: &[u8], y: usize| -> u8 { frame[(y * 568 + 280) * 4 + 3] };

        let mut open = vec![0; 568 * 1232 * 4];
        renderer
            .draw(
                &mut open,
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
        assert_eq!(
            alpha_at(&open, 750),
            255,
            "fully open: panel covers row 750"
        );

        let mut closing = vec![0; 568 * 1232 * 4];
        renderer
            .draw(
                &mut closing,
                RenderParams {
                    width: 568,
                    height: 1232,
                    route: Route::Shade,
                    progress: 0.4,
                    scroll: 0.0,
                },
                &[],
            )
            .unwrap();
        // The rebuild-vs-reuse cache only bakes on route/geometry/scroll
        // change, never on progress alone (`RendererCache::draw`'s own
        // rebuild guard) -- this is the "no per-frame re-render of the
        // panel" cost requirement, exercised for real here rather than
        // just asserted: two draws, one shared bake.
        assert_eq!(
            renderer.rebuild_count(),
            1,
            "progress alone must not rebuild the bake"
        );
        assert_eq!(
            alpha_at(&closing, 100),
            255,
            "40% open: panel content has shifted up into row 100"
        );
        let expected_backdrop_byte = (tray_backdrop_alpha(0.4, 0.35) * 255.0).round() as u8;
        assert_eq!(
            alpha_at(&closing, 750),
            expected_backdrop_byte,
            "40% open: row 750 is now backdrop, dimmed to this exact progress's eased value"
        );
        assert_ne!(
            alpha_at(&closing, 750),
            255,
            "row 750 must not still read as opaque panel once the drag has shifted it away"
        );
    }

    #[test]
    fn drawer_close_drag_progress_shifts_the_panel_downward() {
        // The Drawer's own mirror of the Shade test above: it opens from
        // the bottom, so a close drag shifts it *down*, off the bottom of
        // the screen, rather than up. `RendererCache::draw`'s shift sign
        // for `Route::Drawer` is already `+1` (see its own `panel_height`/
        // `shift` computation) -- this proves that existing sign actually
        // produces the right pixels for a live, partially-closed drag, not
        // just for the compositor's own opening reveal it was written for.
        // Unlike Shade/Settings, the Drawer has no backdrop at all today
        // (`apply_tray_backdrop` only covers those two routes), so the
        // area the panel has shifted away from should read as fully
        // transparent, not dimmed.
        let mut renderer = RendererCache::default();
        let alpha_at = |frame: &[u8], y: usize| -> u8 { frame[(y * 568 + 280) * 4 + 3] };
        let apps = vec![AppEntry {
            id: "foot.desktop".into(),
            name: "Terminal".into(),
            icon: Some("foot".into()),
            path: PathBuf::new(),
        }];

        let mut open = vec![0; 568 * 1232 * 4];
        renderer
            .draw(
                &mut open,
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
        assert_eq!(
            alpha_at(&open, 500),
            255,
            "fully open: the panel already covers row 500"
        );

        let mut closing = vec![0; 568 * 1232 * 4];
        renderer
            .draw(
                &mut closing,
                RenderParams {
                    width: 568,
                    height: 1232,
                    route: Route::Drawer,
                    progress: 0.4,
                    scroll: 0.0,
                },
                &apps,
            )
            .unwrap();
        assert_eq!(
            renderer.rebuild_count(),
            1,
            "progress alone must not rebuild the bake"
        );
        // 40% open: only the bottom ~40% of the panel's own travel is
        // still on screen, so a row near the bottom is still opaque
        // panel...
        assert_eq!(
            alpha_at(&closing, 1000),
            255,
            "40% open: the panel still reaches row 1000, near the bottom"
        );
        // ...while row 500, covered when fully open, has been shifted
        // away entirely -- and reads as plain transparency (no backdrop
        // to fade in), not still-opaque panel.
        assert_eq!(
            alpha_at(&closing, 500),
            0,
            "40% open: row 500 has shifted off screen; the Drawer has no backdrop to show there"
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
        // Row shifted +76 along with the preview card itself -- room for
        // the brightness slider now sits above it (task: "brightness
        // should be a slider").
        let pixel = (296 * 568 + 59) * 4;
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
            path: PathBuf::new(),
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
            path: PathBuf::new(),
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
            path: PathBuf::new(),
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
            path: PathBuf::new(),
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
    fn scrolling_repaints_clipped_rows_but_keeps_chrome() {
        // 60 apps (15 rows at the redesign's 110px row pitch) actually
        // overflows this panel's viewport -- 30 no longer does.
        let apps = (0..60)
            .map(|index| AppEntry {
                id: format!("app{index}.desktop"),
                name: format!("App {index}"),
                icon: None,
                path: PathBuf::new(),
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
        // Row 60 sits inside the fixed top chrome (handle + search field,
        // `navigation::panel_top`..`navigation::list_top`) -- unaffected
        // by the grid's own scroll.
        assert_eq!(
            &frame[60 * 568 * 4..61 * 568 * 4],
            &before[60 * 568 * 4..61 * 568 * 4]
        );
        // Row 300 sits inside the scrollable grid and must repaint.
        assert_ne!(
            &frame[300 * 568 * 4..360 * 568 * 4],
            &before[300 * 568 * 4..360 * 568 * 4]
        );
        assert_eq!(cache.rebuild_count(), 2);
    }

    #[test]
    fn pressed_grid_tile_has_a_visible_highlight_without_affecting_its_neighbor() {
        let apps = (0..3)
            .map(|index| AppEntry {
                id: format!("fixture-{index}.desktop"),
                name: format!("Fixture {index}"),
                icon: None,
                path: PathBuf::new(),
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

    /// The whole point of `DrawerGridCache` (`docs/design/
    /// app-drawer-review.md`'s performance section): a scroll-only redraw
    /// must reuse the already-painted grid bitmap rather than repainting
    /// every tile, while a catalog, theme, width or search-query change
    /// must still rebuild it.
    #[test]
    fn drawer_grid_cache_rebuilds_only_when_its_own_key_changes() {
        let apps = vec![
            AppEntry {
                id: "a.desktop".into(),
                name: "Alpha".into(),
                icon: None,
                path: PathBuf::new(),
            },
            AppEntry {
                id: "b.desktop".into(),
                name: "Beta".into(),
                icon: None,
                path: PathBuf::new(),
            },
        ];
        let search = DrawerSearch::default();
        let content = DrawerContent {
            apps: apps.iter().collect(),
            search: &search,
        };
        let mut cache = DrawerGridCache::default();
        let mut icons = IconCache::new();
        cache.ensure(&content, None, 568, 1232, &mut icons);
        assert_eq!(cache.rebuilds(), 1);

        // Same everything: a cache hit, not a rebuild.
        cache.ensure(&content, None, 568, 1232, &mut icons);
        assert_eq!(cache.rebuilds(), 1);

        // A different width changes the key.
        cache.ensure(&content, None, 600, 1232, &mut icons);
        assert_eq!(cache.rebuilds(), 2);

        // A different query changes the key, even over the same apps.
        let filtered_search = DrawerSearch {
            query: "alpha".into(),
            focused: false,
        };
        let filtered_content = DrawerContent {
            apps: vec![&apps[0]],
            search: &filtered_search,
        };
        cache.ensure(&filtered_content, None, 600, 1232, &mut icons);
        assert_eq!(cache.rebuilds(), 3);
    }

    #[test]
    fn prebuild_drawer_grid_warms_the_cache_and_is_a_no_op_once_fresh() {
        let apps = vec![AppEntry { id: "a.desktop".into(), name: "Alpha".into(), icon: None, path: PathBuf::new() }];
        let mut renderer = RendererCache::default();
        assert_eq!(renderer.drawer_grid_rebuilds(), 0);
        renderer.prebuild_drawer_grid(&apps, 568, 1232);
        assert_eq!(renderer.drawer_grid_rebuilds(), 1, "the first prebuild actually builds the bitmap");
        renderer.prebuild_drawer_grid(&apps, 568, 1232);
        assert_eq!(renderer.drawer_grid_rebuilds(), 1, "an unchanged catalog/theme/width prebuild is a no-op");
        // A real catalog/theme change still invalidates it, exactly like an
        // ordinary `ensure` call would.
        let more_apps = vec![
            AppEntry { id: "a.desktop".into(), name: "Alpha".into(), icon: None, path: PathBuf::new() },
            AppEntry { id: "b.desktop".into(), name: "Beta".into(), icon: None, path: PathBuf::new() },
        ];
        renderer.prebuild_drawer_grid(&more_apps, 568, 1232);
        assert_eq!(renderer.drawer_grid_rebuilds(), 2);
    }

    #[test]
    fn ease_out_cubic_starts_at_zero_ends_at_one_and_is_monotonic() {
        assert_eq!(ease_out_cubic(0.0), 0.0);
        assert!((ease_out_cubic(1.0) - 1.0).abs() < 1e-9);
        let mid = ease_out_cubic(0.5);
        assert!(mid > 0.5, "ease-out front-loads progress");
        assert!(ease_out_cubic(0.25) < mid);
        assert!(ease_out_cubic(-1.0) >= 0.0 && ease_out_cubic(2.0) <= 1.0, "clamped");
    }

    #[test]
    fn draw_drawer_reveal_shm_composites_a_faded_snapshot_and_the_cancel_band() {
        let width = 568u32;
        let height = 1232u32;
        let size = (width as usize) * (height as usize) * 4;
        // A fully opaque red snapshot stands in for "the drawer's last
        // rendered frame".
        let mut snapshot = vec![0u8; size];
        for pixel in snapshot.chunks_exact_mut(4) {
            pixel.copy_from_slice(&[0, 0, 255, 255]); // BGRA on this platform: opaque red
        }
        let mut canvas = vec![0u8; size];
        draw_drawer_reveal_shm(&mut canvas, width, height, &snapshot, 0.0, None).unwrap();
        // At progress 0.0 the snapshot is still fully opaque somewhere well
        // below the Cancel band, so that pixel must be the snapshot's own
        // opaque red, not transparent.
        let probe = ((600 * width as usize) + 50) * 4;
        assert_eq!(&canvas[probe..probe + 4], &[0, 0, 255, 255]);
        let mut canvas_done = vec![0u8; size];
        draw_drawer_reveal_shm(&mut canvas_done, width, height, &snapshot, 1.0, None).unwrap();
        // At progress 1.0 the snapshot has fully faded out; that same pixel
        // is back to transparent (nothing painted there).
        assert_eq!(&canvas_done[probe..probe + 4], &[0, 0, 0, 0]);
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

    /// Host-only, opt-in timing (`cargo test --lib --release -- --ignored
    /// --nocapture drawer_grid_cache_host_timing`): the honest, host-side
    /// half of `docs/design/app-drawer-review.md`'s performance section.
    /// Never run by default -- wall-clock numbers are noisy on a shared or
    /// loaded machine and must not make an unrelated CI run flaky -- but
    /// committed so the exact comparison this review's numbers came from
    /// can be re-run rather than taken on faith.
    ///
    /// Drives the real `RendererCache::draw` path (not a lower-level
    /// helper) over a simulated scroll/fling of a 64-app catalog (half
    /// with real icon paths, half without, so both `IconCache::paint` and
    /// the round-circle fallback are exercised). Compares a fresh
    /// `RendererCache` per simulated frame -- forcing a full grid-bitmap
    /// rebuild every time, i.e. this change's "before": every visible
    /// tile repainted from scratch every frame -- against one persistent
    /// cache reused across frames while only `scroll` changes -- this
    /// change's "after", and what scrolling the real Drawer actually does
    /// once the grid bitmap is already built.
    #[test]
    #[ignore]
    fn drawer_grid_cache_host_timing() {
        let apps: Vec<AppEntry> = (0..64)
            .map(|index| AppEntry {
                id: format!("fixture-{index}.desktop"),
                name: format!("Fixture App {index}"),
                icon: (index % 2 == 0).then(|| "utilities-terminal".into()),
                path: PathBuf::new(),
            })
            .collect();
        let frames: u32 = 200;
        let params = |scroll: f64| RenderParams {
            width: 568,
            height: 1232,
            route: Route::Drawer,
            progress: 1.0,
            scroll,
        };
        // A real scroll/fling changes `scroll` every frame; the catalog
        // does not. `% 1500.0` keeps this inside the grid's real scroll
        // range (64 apps / 4 columns = 16 rows, well past one viewport)
        // instead of pinning at one clamped value.
        let scroll_for = |frame: u32| (f64::from(frame) * 7.0) % 1500.0;
        let mut frame_buf = vec![0u8; 568 * 1232 * 4];

        // Cold: a brand-new `RendererCache` every frame, so the grid
        // bitmap always misses and rebuilds -- this change's "before" (no
        // caching at all).
        let cold_started = std::time::Instant::now();
        for frame in 0..frames {
            let mut renderer = RendererCache::default();
            renderer
                .draw(&mut frame_buf, params(scroll_for(frame)), &apps)
                .unwrap();
        }
        let cold = cold_started.elapsed() / frames;

        // Warm: one persistent cache reused across frames while only
        // `scroll` changes -- this change's "after".
        let mut warm_renderer = RendererCache::default();
        warm_renderer.draw(&mut frame_buf, params(0.0), &apps).unwrap(); // prime: first frame still builds the grid bitmap
        let warm_started = std::time::Instant::now();
        for frame in 0..frames {
            warm_renderer
                .draw(&mut frame_buf, params(scroll_for(frame)), &apps)
                .unwrap();
        }
        let warm = warm_started.elapsed() / frames;

        eprintln!(
            "drawer_grid_cache_host_timing: cold(fresh cache/frame) mean-per-frame={cold:?} \
             warm(persistent cache) mean-per-frame={warm:?} over {frames} frames, {} apps, host x86_64",
            apps.len()
        );
    }
}

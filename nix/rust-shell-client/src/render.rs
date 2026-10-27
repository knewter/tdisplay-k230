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
        self, list_top, panel_top, search_field_rect, tile_rect,
        GRID_BOTTOM_INSET,
    },
    pipewire_ipc::GraphSnapshot,
    service_data::{Control, ControlState, ControlValue, Priority},
    service_ui::{
        filter_app_indices, DrawerSearch, ServiceView,
        SETTINGS_VOLUME_ROW, SHADE_SLIDER_H, SHADE_SLIDER_TOP,
        shade_toggle_h, SHADE_TOGGLE_TOP, SHADE_VOLUME_H, SHADE_VOLUME_TOP,
    },
    slider,
    volume::{self, Hud},
    recovery::RecoveryState,
    splash::SplashStatus,
    theme_carousel,
    theme_catalog::{BackgroundKind, TEXT_SCALE_VALUES},
    theme_thumbnails::{bounded_working_set, ThemeThumbnailCache, ThumbnailKey, Variant},
    theme_ui::{
        background_display_label, vision_layout, ThemeImageKey, ThemeImageWorker, ThemePage,
        ThemeView,
    },
    wifi_settings::{Secret, Security},
    wifi_ui::{all_networks, Page as WifiPage, WifiPublic},
    Route,
};
use crate::glyph::{self, Glyph};
use cairo::{Context, Filter, Format, ImageSurface, LinearGradient, Matrix, Operator, SurfacePattern};
use pango::{Alignment, EllipsizeMode, FontDescription};
use std::{fs::File, path::Path, rc::Rc};

// Per-surface metrics keep independent renderers/candidate previews isolated.
// Geometry and input coordinates stay fixed; only glyphs and visual insets scale.
/// The five type roles (`the-shell-has-one-visual-language` design.md §7),
/// in design pixels at 100% before the vision step. Nothing is set below
/// `TYPE_CAPTION`; Display sizes come from the widget cell.
pub const TYPE_TITLE: f64 = 40.0;
pub const TYPE_BODY: f64 = 30.0;
pub const TYPE_LABEL: f64 = 26.0;
pub const TYPE_CAPTION: f64 = 26.0;
/// The 8 px spacing rhythm (§8): inside a row, between rows, around a
/// card's content, and between groups.
pub const SPACE_IN_ROW: f64 = 8.0;
pub const SPACE_BETWEEN_ROWS: f64 = 16.0;
pub const SPACE_CARD: f64 = 24.0;
pub const SPACE_GROUP: f64 = 32.0;

#[derive(Clone, Copy)]
struct ThemeMetrics { font: f64, spacing: f64 }
static THEME_METRICS: cairo::UserDataKey<ThemeMetrics> = cairo::UserDataKey::new();
static HOVER_POINT: cairo::UserDataKey<(f64, f64)> = cairo::UserDataKey::new();

fn theme_number(theme: Option<&AppearanceSnapshot>, section: &str, key: &str) -> Option<f64> {
    match theme?.token(section, key)? {
        AppearanceToken::Number(value) if value.is_finite() => Some(*value),
        _ => None,
    }
}

fn theme_spacing_scale(theme: Option<&AppearanceSnapshot>) -> f64 {
    let with_font = !matches!(theme.and_then(|t| t.token("spacing", "scale-with-font")),
                             Some(AppearanceToken::Boolean(false)));
    let font = if with_font { theme_number(theme, "font", "base-size").unwrap_or(12.0) / 12.0 } else { 1.0 };
    (theme_number(theme, "spacing", "scale").unwrap_or(1.0) * font).clamp(0.8, 1.25)
}

fn attach_theme_metrics(cr: &Context, theme: Option<&AppearanceSnapshot>) {
    let _ = cr.target().set_user_data(&THEME_METRICS, Rc::new(ThemeMetrics {
        // `accessibility.text-scale` is the person's vision choice
        // (`tools/theme_vision.py`), on top of the theme's own size; the card
        // shell's `appearance.c` `metrics()` applies the same product.
        font: theme_base_font(theme) * vision_text_scale(theme),
        spacing: theme_spacing_scale(theme),
    }));
}

/// The theme's own text size factor, before the vision step.
fn theme_base_font(theme: Option<&AppearanceSnapshot>) -> f64 {
    (theme_number(theme, "font", "base-size").unwrap_or(12.0) / 12.0).clamp(0.8, 1.25)
}

/// The person's vision text step (`accessibility.text-scale`, written by
/// `tools/theme_vision.py`): 1.0 to 2.0, applied after the theme's own
/// sizing so a theme cannot clamp it away.
fn vision_text_scale(theme: Option<&AppearanceSnapshot>) -> f64 {
    theme_number(theme, "accessibility", "text-scale").unwrap_or(1.0).clamp(1.0, 2.0)
}

/// True when the person has chosen a larger text step or high contrast,
/// which makes the drawer and Shade sheets opaque.
fn vision_adjusted(theme: Option<&AppearanceSnapshot>) -> bool {
    vision_text_scale(theme) > 1.0
        || matches!(theme.and_then(|t| t.token("accessibility", "high-contrast")),
                    Some(AppearanceToken::Boolean(true)))
}

fn context_font_size(cr: &Context, design: f64) -> f64 {
    (design * cr.target().user_data(&THEME_METRICS).map_or(1.0, |m| m.font)).max(design.min(11.0))
}

fn visual_inset(cr: &Context, design: f64) -> f64 {
    design * cr.target().user_data(&THEME_METRICS).map_or(1.0, |m| m.spacing)
}

fn hovered(cr: &Context, x: f64, y: f64, w: f64, h: f64) -> bool {
    cr.target().user_data(&HOVER_POINT).and_then(|point| cr.device_to_user(point.0, point.1).ok())
        .is_some_and(|(px, py)| px >= x && px < x + w && py >= y && py < y + h)
}

fn paint_scrim(cr: &Context, theme: Option<&AppearanceSnapshot>, section: &str,
               width: f64, height: f64, fallback: u32, alpha: f64) {
    if !theme_brush(theme, section, "scrim").is_some_and(|b| fill_brush(cr, b, 0.0, 0.0, width, height)) {
        color(cr, fallback, alpha);
        let _ = cr.paint();
    }
}

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
/// a 64px icon (no plate/box around it -- see `paint_drawer`), with a
/// two-line Caption-role label below.
pub const DRAWER_ICON_SIZE: i32 = 64;
/// The icon's own width in the grid math (a plain `f64` copy of
/// `DRAWER_ICON_SIZE`, since `IconCache::paint`/`paint_label` want
/// different numeric types for size).
pub const DRAWER_ICON_CARD: f64 = DRAWER_ICON_SIZE as f64;
/// The app-name label's design size: the Caption role.
pub const DRAWER_LABEL_SIZE: f64 = TYPE_CAPTION;

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
    if !matches!(route, Route::Settings | Route::Shade | Route::Power | Route::Help) {
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

/// Resolve handheld text size from Omarchy's `[font]` section. Role overrides
/// win; otherwise base-size scales the design size relative to its 12px
/// default. Bounds keep theme typography readable within the portrait layout.
fn theme_font_size(theme: Option<&AppearanceSnapshot>, role: &str, design: f64, min: f64, max: f64) -> f64 {
    let number = |key| match theme?.token("font", key)? {
        AppearanceToken::Number(value) if value.is_finite() => Some(*value),
        _ => None,
    };
    number(role)
        .or_else(|| number("base-size").map(|base| design * base / 12.0))
        .unwrap_or(design)
        .clamp(min, max)
        * vision_text_scale(theme)
}

/// Theme spacing changes visual Settings row inset only, never the row's
/// touch bounds. Keep the requested adaptation within handheld limits.
fn theme_settings_row_padding(theme: Option<&AppearanceSnapshot>) -> f64 {
    theme_number(theme, "spacing", "row-padding-x")
        .unwrap_or(18.0 * theme_spacing_scale(theme)).clamp(12.0, 36.0)
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
        if section == "controls" { "normal-color" } else { "text" },
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
    text_weight_resolved(cr, value, x, y, width, context_font_size(cr, size), rgb, weight);
}

#[allow(clippy::too_many_arguments)]
fn text_weight_resolved(cr: &Context, value: &str, x: f64, y: f64, width: f64,
                        size: f64, rgb: u32, weight: pango::Weight) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(size * f64::from(pango::SCALE));
    font.set_weight(weight);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    let inset = visual_inset(cr, 4.0) - 4.0;
    layout.set_width(((width - 2.0 * inset).max(1.0) * f64::from(pango::SCALE)) as i32);
    layout.set_ellipsize(EllipsizeMode::End);
    color(cr, rgb, 1.0);
    cr.move_to(x + inset, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// How many lines `value` takes when wrapped (between words, then inside a
/// word) to `width` at `px` -- for layouts that must place wrapped text
/// before there is a cairo context, such as `help::layout`.
pub fn wrapped_line_count(value: &str, px: f64, width: f64, weight: pango::Weight) -> u32 {
    let key = (value.to_owned(), px.to_bits(), width.to_bits(), pango::glib::translate::IntoGlib::into_glib(weight));
    if let Some(count) = TEXT_MEASURES.with(|m| m.borrow().lines.get(&key).copied()) {
        return count;
    }
    let context = pango::prelude::FontMapExt::create_context(&pangocairo::FontMap::default());
    let layout = pango::Layout::new(&context);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(px * f64::from(pango::SCALE));
    font.set_weight(weight);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width.max(1.0) * f64::from(pango::SCALE)) as i32);
    layout.set_wrap(pango::WrapMode::WordChar);
    let count = u32::try_from(layout.line_count()).unwrap_or(1).max(1);
    TEXT_MEASURES.with(|m| m.borrow_mut().remember_lines(key, count));
    count
}

/// Layout code such as `theme_ui::chooser_layout` runs on every draw and
/// measures the same strings each time; shaping them again cost about a
/// third of the client's CPU during drawer scroll. The results depend only
/// on the key and the installed fonts, so they are kept, up to a bound.
#[derive(Default)]
struct TextMeasures {
    lines: std::collections::HashMap<(String, u64, u64, i32), u32>,
    widths: std::collections::HashMap<(String, u64, i32), f64>,
}

const TEXT_MEASURES_MAX: usize = 1024;

impl TextMeasures {
    fn remember_lines(&mut self, key: (String, u64, u64, i32), count: u32) {
        if self.lines.len() >= TEXT_MEASURES_MAX {
            self.lines.clear();
        }
        self.lines.insert(key, count);
    }

    fn remember_width(&mut self, key: (String, u64, i32), width: f64) {
        if self.widths.len() >= TEXT_MEASURES_MAX {
            self.widths.clear();
        }
        self.widths.insert(key, width);
    }
}

thread_local! {
    static TEXT_MEASURES: std::cell::RefCell<TextMeasures> = std::cell::RefCell::new(TextMeasures::default());
}

/// The width `value` takes on one line at `px`, measured like
/// `wrapped_line_count`, for layouts that place text beside other text.
pub fn measured_text_width(value: &str, px: f64, weight: pango::Weight) -> f64 {
    let key = (value.to_owned(), px.to_bits(), pango::glib::translate::IntoGlib::into_glib(weight));
    if let Some(width) = TEXT_MEASURES.with(|m| m.borrow().widths.get(&key).copied()) {
        return width;
    }
    let context = pango::prelude::FontMapExt::create_context(&pangocairo::FontMap::default());
    let layout = pango::Layout::new(&context);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(px * f64::from(pango::SCALE));
    font.set_weight(weight);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    let width = f64::from(layout.pixel_size().0);
    TEXT_MEASURES.with(|m| m.borrow_mut().remember_width(key, width));
    width
}

/// `text` that wraps onto as many lines as `width` needs instead of
/// ending in "…", at the same theme- and step-scaled size.
fn text_wrapped(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    wrapped_text(cr, value, x, y, width, context_font_size(cr, size), rgb, pango::Weight::Normal);
}

/// `value` wrapped onto at most `lines` lines at `px`, the last ending in
/// "…" if it still does not fit.
#[allow(clippy::too_many_arguments)]
fn wrapped_text_lines(cr: &Context, value: &str, x: f64, y: f64, width: f64, px: f64, rgb: u32, lines: i32) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(px * f64::from(pango::SCALE));
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width.max(1.0) * f64::from(pango::SCALE)) as i32);
    layout.set_wrap(pango::WrapMode::WordChar);
    layout.set_height(-lines.max(1));
    layout.set_ellipsize(EllipsizeMode::End);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// `value` wrapped onto as many lines as it needs at `px` (no ellipsis).
#[allow(clippy::too_many_arguments)]
fn wrapped_text(cr: &Context, value: &str, x: f64, y: f64, width: f64, px: f64, rgb: u32, weight: pango::Weight) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(px * f64::from(pango::SCALE));
    font.set_weight(weight);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width.max(1.0) * f64::from(pango::SCALE)) as i32);
    layout.set_wrap(pango::WrapMode::WordChar);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// The drawn width of `value` as `text_weight` would lay it out unclipped,
/// at the same theme-scaled size, so a label can be placed after it.
fn text_advance(cr: &Context, value: &str, size: f64, weight: pango::Weight) -> f64 {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(context_font_size(cr, size) * f64::from(pango::SCALE));
    font.set_weight(weight);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    f64::from(layout.pixel_size().0)
}

/// `text_advance` for a size already resolved through the theme and step.
fn text_advance_resolved(cr: &Context, value: &str, size: f64, weight: pango::Weight) -> f64 {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(size * f64::from(pango::SCALE));
    font.set_weight(weight);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    f64::from(layout.pixel_size().0)
}

fn text(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    text_weight(cr, value, x, y, width, size, rgb, pango::Weight::Normal);
}

/// Text in a type role: the theme may enlarge the role (`font.<key>`), but
/// never below the role's own size; the vision step applies on top.
#[allow(clippy::too_many_arguments)]
fn themed_role(cr: &Context, theme: Option<&AppearanceSnapshot>, key: &str,
               value: &str, x: f64, y: f64, width: f64, role: f64, rgb: u32,
               weight: pango::Weight) {
    text_weight_resolved(cr, value, x, y, width, theme_font_size(theme, key, role, role, role * 1.25), rgb, weight);
}

/// `themed_role` that, at a larger vision step, shrinks a line that would
/// ellipsize in its column until it fits -- never below the role's 100%
/// size, so nothing is set under `TYPE_CAPTION`.
#[allow(clippy::too_many_arguments)]
fn themed_role_fit(cr: &Context, theme: Option<&AppearanceSnapshot>, key: &str,
                   value: &str, x: f64, y: f64, width: f64, role: f64, rgb: u32,
                   weight: pango::Weight) {
    let resolved = theme_font_size(theme, key, role, role, role * 1.25);
    let advance = text_advance_resolved(cr, value, resolved, weight);
    let room = (width - 8.0) * 0.96;
    let size = if advance > room { (resolved * room / advance).max(role) } else { resolved };
    text_weight_resolved(cr, value, x, y, width, size, rgb, weight);
}

fn heading(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    text_weight(cr, value, x, y, width, size, rgb, pango::Weight::Bold);
}

/// Vertical rhythm for the Settings screen's capability rows (finding P0-4
/// of `docs/design/webos-polish-review.md`): each row's height plus one gap,
/// from the header's `first_y`. `service_ui`'s hit-tests read the same
/// functions, so a tap and its paint cannot drift apart.
/// `SETTINGS_ROW_H` is the floor under a row's own height.
pub const SETTINGS_ROW_H: f64 = 110.0;
pub const SETTINGS_ROW_GAP: f64 = 16.0;
/// Wi-Fi, Brightness, Volume, Keyboard, Motion -- Volume (row 2, task:
/// "in Settings") sits directly after Brightness; Keyboard/Motion shifted
/// down one row each to make room, same rhythm cascade `settings_layout`'s
/// own doc already describes.
pub const SETTINGS_ROW_COUNT: u32 = 5;
pub const SETTINGS_POWER_CARD_H: f64 = 70.0;
/// The keyboard base's Key backlight row, after Motion; present only while
/// the base's LED exists (`ServiceView::key_backlight`), so the Power section
/// below it moves down one row only then.
pub const SETTINGS_KEY_BACKLIGHT_ROW: u32 = 5;

/// The Cellular and Location rows, after the last base row (Motion, or Key
/// backlight when the base's LED exists); present only once the modem has
/// answered (`ServiceView::modem`). They are plain label-and-value rows, so
/// they are placed from the base rows' bottom rather than by row index.
pub const SETTINGS_MODEM_ROWS: u32 = 2;
/// Date & time and About, the last plain rows before Power; always present.
/// They follow the modem rows when those exist, so About is the last row.
pub const SETTINGS_INFO_ROWS: u32 = 2;

/// How many plain label-and-value rows lead the Power column.
pub fn settings_plain_row_count(modem: bool) -> u32 {
    SETTINGS_INFO_ROWS + if modem { SETTINGS_MODEM_ROWS } else { 0 }
}

/// Index among the plain rows of Date & time (`0`) or About (`1`).
pub fn settings_info_row_index(modem: bool, info: u32) -> u32 {
    if modem { SETTINGS_MODEM_ROWS + info } else { info }
}

pub fn settings_modem_row_h() -> f64 {
    (SETTINGS_ROW_INSET + vision_line(TYPE_LABEL) + 2.0 + vision_line(TYPE_BODY) + SETTINGS_ROW_INSET)
        .ceil()
        .max(crate::service_ui::SHADE_TAP_MIN)
}

/// Top of modem row `index` (0 Cellular, 1 Location).
pub fn settings_modem_row_y(key_backlight: bool, index: u32) -> f64 {
    settings_rows_bottom(SETTINGS_ROW_COUNT + u32::from(key_backlight))
        + SETTINGS_ROW_GAP
        + f64::from(index) * (settings_modem_row_h() + SETTINGS_ROW_GAP)
}

pub fn settings_row_y(index: u32) -> f64 {
    (0..index).fold(settings_first_y(), |y, row| y + settings_row_h(row) + SETTINGS_ROW_GAP)
}

/// Line height of `design`-sized text at the current vision step.
fn vision_line(design: f64) -> f64 {
    design * crate::layout_text_scale() * 1.25
}

/// Capability row `row`'s height: room for its own lines (Label name, Body
/// value, one Caption or two for Keyboard's gesture hint) at the current
/// vision step and, for the slider rows, a full slider band beneath them.
pub fn settings_row_h(row: u32) -> f64 {
    let body = SETTINGS_ROW_INSET + vision_line(TYPE_LABEL) + 2.0 + vision_line(TYPE_BODY);
    let slider = SPACE_IN_ROW + 56.0 + 6.0;
    let h = match row {
        1 | SETTINGS_KEY_BACKLIGHT_ROW => body + slider,
        crate::service_ui::SETTINGS_VOLUME_ROW => {
            SETTINGS_ROW_INSET + vision_line(TYPE_BODY) + 2.0 + vision_line(TYPE_CAPTION) + slider
        }
        3 => body + 4.0 + 2.0 * vision_line(TYPE_CAPTION) + SETTINGS_ROW_INSET,
        _ => body + 4.0 + vision_line(TYPE_CAPTION) + SETTINGS_ROW_INSET,
    };
    h.ceil().max(SETTINGS_ROW_H)
}

/// The space above a row's first line and below its last.
const SETTINGS_ROW_INSET: f64 = SPACE_BETWEEN_ROWS;

/// Inside a row: where the label, value and caption lines start and where
/// the slider's centre sits, measured from the row's top.
pub fn settings_row_lines(row: u32) -> (f64, f64, f64, f64) {
    let value = SETTINGS_ROW_INSET + vision_line(TYPE_LABEL) + 2.0;
    let caption = value + vision_line(TYPE_BODY) + 4.0;
    let slider = settings_row_h(row) - 6.0 - 28.0;
    (SETTINGS_ROW_INSET, value, caption, slider)
}

/// The Settings header's tap bands and text rows: the Title beside Done,
/// the Vision and Themes links on their own Label row with bands sized for
/// the text at the current step, "Device controls" under them, and the rows
/// below that. Paint and every hit-test read this one struct.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SettingsHeader {
    /// Done's band: x from `done_x` to the right edge, y above `done_bottom`.
    pub done_x: f64,
    pub done_bottom: f64,
    /// The links' shared y band and each link's x range.
    pub links_y: (f64, f64),
    pub vision_x: (f64, f64),
    pub themes_x: (f64, f64),
    /// Where the "Device controls" eyebrow line starts.
    pub eyebrow_y: f64,
    /// The first capability row's top.
    pub first_y: f64,
}

/// A conservative width for `chars` characters of `design`-sized text at
/// the current step, for hit bands that are computed without a context.
fn estimated_text_w(chars: usize, design: f64) -> f64 {
    chars as f64 * design * crate::layout_text_scale() * 0.62
}

pub fn settings_header(width: f64) -> SettingsHeader {
    let done_w = (estimated_text_w(4, TYPE_LABEL) + 48.0).max(150.0);
    let done_bottom = (16.0 + vision_line(TYPE_TITLE) + SPACE_IN_ROW).max(80.0);
    let links_h = (vision_line(TYPE_LABEL) + SPACE_BETWEEN_ROWS).max(58.0);
    // The two links share the width; each fits its text to its band.
    let links_fit = ((width - 28.0) / (estimated_text_w(16, TYPE_LABEL) + 72.0)).min(1.0);
    let themes_w = (estimated_text_w(8, TYPE_LABEL) + 48.0) * links_fit;
    let vision_w = (estimated_text_w(8, TYPE_LABEL) + 24.0) * links_fit;
    // A wide panel has room for the links beside Done on the Title's row,
    // which gives that row back to the controls; a narrow one stacks them.
    let title_w = estimated_text_w(8, TYPE_TITLE) + 28.0 + 24.0;
    let one_row = title_w + vision_w + themes_w + done_w <= width;
    let (links_y, links_right) = if one_row {
        ((0.0, done_bottom), width - done_w)
    } else {
        ((done_bottom, done_bottom + links_h), width)
    };
    let eyebrow_y = links_y.1 + 4.0;
    SettingsHeader {
        done_x: width - done_w,
        done_bottom,
        links_y,
        vision_x: (links_right - themes_w - vision_w, links_right - themes_w),
        themes_x: (links_right - themes_w, links_right),
        eyebrow_y,
        first_y: (eyebrow_y + vision_line(TYPE_LABEL) + 12.0).ceil(),
    }
}

/// The first row's top in the content column's design space.
pub fn settings_first_y() -> f64 {
    settings_header(crate::DESIGN_WIDTH).first_y
}

/// The first row's top in the wide (landscape) layout, whose header is laid
/// out across the three columns' full width -- one row when the links fit
/// beside Done.
pub fn settings_wide_first_y() -> f64 {
    let width = crate::SETTINGS_WIDE_ORIGIN_X * 2.0 + crate::SETTINGS_WIDE_COL_PITCH * 2.0 + crate::SETTINGS_WIDE_COL_W;
    settings_header(width).first_y
}

/// The Volume row's output line, from the row's top: between the heading
/// and the slider.
pub fn settings_output_detail_y() -> f64 {
    SETTINGS_ROW_INSET + vision_line(TYPE_BODY) + 2.0
}

/// The Power section's card height: 70 px, or room for its larger label.
pub fn settings_power_card_h() -> f64 {
    (vision_line(TYPE_BODY) + SPACE_CARD).ceil().max(SETTINGS_POWER_CARD_H)
}

/// The bottom edge of `count` stacked settings rows, i.e. where any content
/// that follows the row list (the Power section) should begin.
pub fn settings_rows_bottom(count: u32) -> f64 {
    if count == 0 {
        return settings_first_y();
    }
    settings_row_y(count - 1) + settings_row_h(count - 1)
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

pub fn settings_layout(key_backlight: bool) -> SettingsLayout {
    settings_layout_for(key_backlight, false)
}

/// `settings_layout` with the Cellular and Location rows ahead of Power.
pub fn settings_layout_for(key_backlight: bool, modem: bool) -> SettingsLayout {
    let rows_bottom =
        settings_modem_row_y(key_backlight, settings_plain_row_count(modem) - 1) + settings_modem_row_h();
    let power_heading_y = rows_bottom + 22.0;
    let reboot_y = power_heading_y + (vision_line(TYPE_LABEL) + SPACE_IN_ROW).max(28.0);
    let poweroff_y = reboot_y + settings_power_card_h() + SETTINGS_ROW_GAP;
    SettingsLayout {
        power_heading_y,
        reboot_y,
        poweroff_y,
        poweroff_bottom: poweroff_y + settings_power_card_h(),
    }
}

/// Which wide-layout column a capability row belongs to: Wi-Fi, Brightness
/// and Volume on the left (column 0), Keyboard, Motion and Key backlight in
/// the middle (column 1). The Power section is column 2.
pub fn settings_row_column(row: u32) -> usize {
    usize::from(row >= 3)
}

/// Where the wide (landscape) layout moves `column`'s items relative to
/// their single-column design position: `(dx, dy)` added to the design x/y.
/// Column 1's rows slide up to the top of the row area and column 2's Power
/// heading takes the first row's y, so each column reads as its own stack
/// starting at the wide header's `first_y`. `render` paints through this offset
/// and `service_ui::panel_intent` subtracts the same one, so a tap and its
/// paint cannot drift apart.
pub fn settings_wide_offset(column: usize, key_backlight: bool) -> (f64, f64) {
    settings_wide_offset_for(column, key_backlight, false)
}

/// `settings_wide_offset` when the Cellular and Location rows lead column 2
/// (the Power column), ahead of the Power heading.
pub fn settings_wide_offset_for(column: usize, key_backlight: bool, modem: bool) -> (f64, f64) {
    let dx = crate::SETTINGS_WIDE_ORIGIN_X + column as f64 * crate::SETTINGS_WIDE_COL_PITCH;
    // Every column also rises by whatever the wide header saves over the
    // single column's stacked one.
    let dy = settings_wide_first_y() - settings_first_y() + match column {
        0 => 0.0,
        1 => settings_first_y() - settings_row_y(3),
        _ => settings_first_y() - settings_modem_row_y(key_backlight, 0),
    };
    let _ = modem;
    (dx, dy)
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
    let card_y = label_y + (vision_line(TYPE_BODY) + SPACE_IN_ROW).max(28.0);
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
    font.set_absolute_size(context_font_size(cr, size) * f64::from(pango::SCALE));
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
    service_card_state(cr, theme, section, x, y, w, h, selected, false);
}

fn service_card_state(
    cr: &Context,
    theme: Option<&AppearanceSnapshot>,
    section: &str,
    x: f64,
    y: f64,
    w: f64,
    h: f64,
    selected: bool,
    pressed: bool,
) {
    service_card_interaction(cr, theme, section, x, y, w, h, selected, pressed, false);
}

#[allow(clippy::too_many_arguments)]
fn service_card_interaction(cr: &Context, theme: Option<&AppearanceSnapshot>, section: &str,
                            x: f64, y: f64, w: f64, h: f64,
                            selected: bool, pressed: bool, focused: bool) {
    service_card_shaped(cr, theme, section, (x, y, w, h), CARD_RADIUS_CONTROL, selected, pressed, focused);
}

#[allow(clippy::too_many_arguments)]
fn service_card_shaped(cr: &Context, theme: Option<&AppearanceSnapshot>, section: &str,
                       (x, y, w, h): (f64, f64, f64, f64), radius: f64,
                       selected: bool, pressed: bool, focused: bool) {
    let _ = cr.save();
    rounded(cr, x, y, w, h, radius);
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
        color(cr, palette_rgb_or(theme, "background", 0x263946), 1.0);
        cr.paint().ok();
    }
    let state = if focused { "focus" } else if hovered(cr, x, y, w, h) { "hover-cursor" }
                else if selected { "selected" } else { "normal" };
    let tint = if pressed {
        "pressed-fill-alpha"
    } else {
        // These names are bounded renderer roles, never source-provided paths.
        match state { "focus" => "focus-fill-alpha", "hover-cursor" => "hover-cursor-fill-alpha",
                      "selected" => "selected-fill-alpha", _ => "normal-fill-alpha" }
    };
    let alpha = match theme.and_then(|snapshot| snapshot.token("controls", tint)) {
        Some(AppearanceToken::Number(value)) => value.clamp(0.0, 1.0),
        _ => {
            if pressed {
                0.22
            } else if selected {
                0.18
            } else {
                0.08
            }
        }
    };
    overlay_brush(
        cr,
        theme_brush(theme, "controls", &format!("{state}-color"))
            .or_else(|| theme_brush(theme, "controls", "normal-color")),
        x,
        y,
        w,
        h,
        alpha,
        0x78929d,
    );
    let _ = cr.restore();

    // Idle rims remain omitted; focus/hover/selection are transient or explicit.
    paint_control_border(cr, theme, section, state, (x, y, w, h), radius);
}

/// Card radii by job (`the-shell-has-one-visual-language` design.md §9).
const CARD_RADIUS_GROUP: f64 = 24.0;
const CARD_RADIUS_CONTROL: f64 = 16.0;

/// The three card treatments, by job (design.md §9).
#[derive(Clone, Copy, Debug, PartialEq)]
enum CardJob {
    /// A container of rows: the flat theme tint.
    Group,
    /// A row that acts: a slightly stronger tint and a 1 px top-edge
    /// highlight in the text colour at 10%.
    Control,
    /// The current choice: the accent at 18% and a 2 px accent rim. `pill`
    /// rounds it fully, for segments and chips.
    Chosen { pill: bool },
}

/// The Control tint's extra over the theme's flat card, and its highlight.
const CONTROL_TINT_ALPHA: f64 = 0.05;
/// Grab handles are not choices: the text colour, half strength.
const HANDLE_ALPHA: f64 = 0.5;
const CONTROL_EDGE_ALPHA: f64 = 0.10;
const CHOSEN_FILL_ALPHA: f64 = 0.18;
const CHOSEN_RIM: f64 = 2.0;

#[allow(clippy::too_many_arguments)]
/// The Control treatment over whatever the clip already shapes: the extra
/// tint and the 1 px top-edge highlight.
fn control_overlay(cr: &Context, ink: u32, x: f64, y: f64, w: f64) {
    color(cr, ink, CONTROL_TINT_ALPHA);
    let _ = cr.paint();
    color(cr, ink, CONTROL_EDGE_ALPHA);
    cr.rectangle(x, y, w, 1.0);
    let _ = cr.fill();
}

#[allow(clippy::too_many_arguments)]
fn paint_card(cr: &Context, theme: Option<&AppearanceSnapshot>, section: &str, job: CardJob,
              x: f64, y: f64, w: f64, h: f64) {
    let style = visual_style(theme, section);
    let radius = match job {
        CardJob::Group => CARD_RADIUS_GROUP,
        CardJob::Control => CARD_RADIUS_CONTROL,
        CardJob::Chosen { pill: true } => (h.min(w) / 2.0).max(0.0),
        CardJob::Chosen { pill: false } => CARD_RADIUS_CONTROL,
    };
    service_card_shaped(cr, theme, section, (x, y, w, h), radius, false, false, false);
    let _ = cr.save();
    rounded(cr, x, y, w, h, radius);
    cr.clip();
    match job {
        CardJob::Group => {}
        CardJob::Control => control_overlay(cr, style.text, x, y, w),
        CardJob::Chosen { .. } => {
            color(cr, style.accent, CHOSEN_FILL_ALPHA);
            let _ = cr.paint();
            let inset = CHOSEN_RIM / 2.0;
            rounded(cr, x + inset, y + inset, w - CHOSEN_RIM, h - CHOSEN_RIM, (radius - inset).max(0.0));
            cr.set_line_width(CHOSEN_RIM);
            color(cr, style.accent, 1.0);
            let _ = cr.stroke();
        }
    }
    let _ = cr.restore();
}

#[allow(clippy::too_many_arguments)]
fn paint_control_border(cr: &Context, theme: Option<&AppearanceSnapshot>, section: &str,
                        state: &str, (x, y, w, h): (f64, f64, f64, f64), radius: f64) {
    if state != "normal" {
        let border_section = if state == "selected" { section } else { "controls" };
        let widths = match theme.and_then(|s| s.token(border_section, &format!("{state}-border-width"))) {
            Some(AppearanceToken::Width(widths)) => *widths,
            _ => [1.5; 4],
        };
        if let Some(border) = theme_brush(theme, border_section, &format!("{state}-border")) {
            if let Some(gradient) = brush_gradient(border, x, y, w, h) {
                let _ = cr.save();
                rounded(cr, x, y, w, h, radius);
                cr.clip();
                if cr.set_source(&gradient).is_ok() {
                    // Stroke each edge within its own strip, retaining rounded
                    // corners and independently authored per-side widths.
                    for (width, strip) in widths.into_iter().zip([
                        (x, y, w, h / 2.0), (x + w / 2.0, y, w / 2.0, h),
                        (x, y + h / 2.0, w, h / 2.0), (x, y, w / 2.0, h),
                    ]) {
                        if width <= 0.0 { continue; }
                        let _ = cr.save();
                        cr.rectangle(strip.0, strip.1, strip.2, strip.3);
                        cr.clip();
                        rounded(cr, x, y, w, h, radius);
                        cr.set_line_width(width * 2.0);
                        let _ = cr.stroke();
                        let _ = cr.restore();
                    }
                }
                let _ = cr.restore();
            }
        }
    }
}

fn control_text(control: &Control) -> String {
    match &control.value {
        Some(ControlValue::Percent(value)) => format!("{value}%"),
        // The helper's network states are protocol words; show the ones a
        // person would use.
        Some(ControlValue::Text(value)) if value == "link-up" => "Connected".into(),
        Some(ControlValue::Text(value)) if value == "disconnected" => "Not connected".into(),
        Some(ControlValue::Text(value)) => value.clone(),
        Some(ControlValue::Boolean(value)) => {
            if *value { "On".into() } else { "Off".into() }
        }
        None => control.label.clone(),
    }
}

/// The narrowest fade at each outer edge of a wide carousel column.
const CAROUSEL_EDGE_FADE: f64 = 56.0;

/// How far below the Settings header a scrolled body fades out.
const SETTINGS_SCROLL_FADE: f64 = 20.0;

/// The box a slider-end glyph (sun, speaker) is drawn in, centred on the
/// point the touch geometry already uses (`volume_icon_tap_zone`).
const SLIDER_END_GLYPH: f64 = 36.0;

/// A card's leading glyph, sized to the first line of text (a `role` line
/// at the current vision step) and centred on it, so it grows with the
/// text and only that line is indented; the lines under it keep the full
/// width. Returns the x where that first line's text starts.
fn paint_line_glyph(cr: &Context, icon: Glyph, x: f64, line_y: f64, role: f64, rgb: u32) -> f64 {
    let drawn = role * crate::layout_text_scale();
    let size = (drawn * 1.3).round();
    glyph::paint(cr, icon, x, line_y + drawn * 0.6 - size / 2.0, size, rgb, 1.0);
    x + size + SPACE_IN_ROW
}

fn paint_slider_end(cr: &Context, glyph: Glyph, cx: f64, cy: f64, rgb: u32, alpha: f64) {
    let half = SLIDER_END_GLYPH / 2.0;
    glyph::paint(cr, glyph, cx - half, cy - half, SLIDER_END_GLYPH, rgb, alpha);
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
    paint_slider_end(cr, Glyph::SunSmall, left - 30.0, center_y, style.muted, 0.8);
    paint_slider_end(cr, Glyph::Sun, right + 30.0, center_y, style.text, 1.0);
    paint_slider_track(cr, style, w, center_y, percent);
}

/// A slider with `steps + 1` detents (the Key backlight's Off, Low, Medium
/// and High): the shared track and thumb at detent `index`, a dot on every
/// other detent, and the brightness slider's sun glyphs at the ends. Touch
/// maps through the same `slider::track_bounds`
/// (`service_ui::key_backlight_level_at`).
fn paint_level_slider(cr: &Context, style: VisualStyle, w: f64, center_y: f64, index: u8, steps: u8) {
    let (left, right) = slider::track_bounds(w);
    paint_slider_end(cr, Glyph::SunSmall, left - 30.0, center_y, style.muted, 0.8);
    paint_slider_end(cr, Glyph::Sun, right + 30.0, center_y, style.text, 1.0);
    let percent = (f64::from(index.min(steps)) * 100.0 / f64::from(steps)).round() as u8;
    paint_slider_track(cr, style, w, center_y, percent);
    for detent in (0..=steps).filter(|&d| d != index) {
        let x = left + f64::from(detent) / f64::from(steps) * (right - left);
        cr.new_sub_path();
        cr.arc(x, center_y, 3.5, 0.0, std::f64::consts::TAU);
        color(cr, style.text, 0.6);
        let _ = cr.fill();
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
    let icon_rgb = if muted { style.muted } else { style.text };
    // Six px further out than the suns: the muted cross reaches the glyph's
    // right edge, and at 0% the thumb sits on the track's left end. Still
    // inside `volume_icon_tap_zone` (56 px left of the track).
    paint_slider_end(cr, if muted { Glyph::SpeakerMuted } else { Glyph::Speaker }, left - 36.0, center_y, icon_rgb, 1.0);
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
/// Round the existing skewed preview silhouette without changing its layout.
fn rounded_skewed(cr: &Context, x: f64, y: f64, tl: f64, tr: f64, bl: f64, br: f64, h: f64, radius: f64) {
    let r = radius.min((tr - tl) / 3.0).min(h / 3.0).max(0.0);
    let lean = (tl - bl) / h.max(1.0);
    cr.new_path();
    cr.move_to(x + tl + r, y);
    cr.line_to(x + tr - r, y);
    cr.curve_to(x + tr, y, x + tr - lean * r, y, x + tr - lean * r, y + r);
    cr.line_to(x + br + lean * r, y + h - r);
    cr.curve_to(x + br, y + h, x + br, y + h, x + br - r, y + h);
    cr.line_to(x + bl + r, y + h);
    cr.curve_to(x + bl, y + h, x + bl + lean * r, y + h, x + bl + lean * r, y + h - r);
    cr.line_to(x + tl - lean * r, y + r);
    cr.curve_to(x + tl, y, x + tl, y, x + tl + r, y);
    cr.close_path();
}

/// Identity of one rendered carousel card: its thumbnail, whole-pixel size,
/// outline, scrim level and theme colours.
#[derive(Clone, Debug, Eq, Hash, PartialEq)]
struct CardKey {
    id: String,
    variant: &'static str,
    image: usize,
    width: i32,
    height: i32,
    skew: i32,
    blend: u8,
    look: String,
}

/// Bounded cache of rendered carousel cards and their outline masks. Only
/// cards at a row's two rest sizes are kept, least recently drawn first out:
/// a card growing or shrinking through a swipe has a new size on almost
/// every frame, so it is drawn through two reused scratch surfaces instead
/// of allocating its own. Everything is released, and freed heap returned to
/// the system, once a scene is built without the picker.
#[derive(Default)]
struct CardSprites {
    cards: std::collections::HashMap<CardKey, (ImageSurface, u64)>,
    masks: std::collections::HashMap<(i32, i32, i32), ImageSurface>,
    scratch: Option<(ImageSurface, ImageSurface)>,
    bytes: usize,
    clock: u64,
    painted: bool,
}

/// About two rows' worth of visible collapsed slices.
const CARD_SPRITE_MAX_BYTES: usize = 2 << 20;

thread_local! {
    static CARD_SPRITES: std::cell::RefCell<CardSprites> = std::cell::RefCell::new(CardSprites::default());
}

/// Called before a scene is built; releases the cards if that scene drew no
/// carousel (see `CardSprites`).
fn card_sprites_scene<T>(build: impl FnOnce() -> T) -> T {
    CARD_SPRITES.with(|sprites| sprites.borrow_mut().painted = false);
    let result = build();
    CARD_SPRITES.with(|sprites| {
        let mut sprites = sprites.borrow_mut();
        if !sprites.painted && (sprites.bytes != 0 || sprites.scratch.is_some() || !sprites.masks.is_empty()) {
            *sprites = CardSprites::default();
            // SAFETY: glibc's malloc_trim only releases free heap pages.
            unsafe { libc::malloc_trim(0) };
        }
    });
    result
}

/// Returns freed heap to the system and reports, for the `picker-memory`
/// log line, what the picker's caches hold and what the allocator keeps.
pub fn trim_and_report_picker_memory(thumbnail_bytes: usize) -> String {
    let (cards, masks, scratch) = CARD_SPRITES.with(|sprites| {
        let sprites = sprites.borrow();
        let area = |s: &ImageSurface| (s.stride() as usize) * (s.height() as usize);
        (
            sprites.bytes,
            sprites.masks.values().map(area).sum::<usize>(),
            sprites.scratch.as_ref().map_or(0, |(c, m)| area(c) + area(m)),
        )
    });
    // SAFETY: plain glibc calls with no pointers.
    let before = unsafe { libc::mallinfo2() };
    unsafe { libc::malloc_trim(0) };
    let after = unsafe { libc::mallinfo2() };
    let kib = |bytes: usize| bytes / 1024;
    format!(
        "cards_kib={} masks_kib={} scratch_kib={} thumbnails_kib={} heap_in_use_kib={} heap_free_kib={} \
         heap_free_after_trim_kib={} mmap_kib={}",
        kib(cards), kib(masks), kib(scratch), kib(thumbnail_bytes), kib(after.uordblks),
        kib(before.fordblks), kib(after.fordblks), kib(after.hblkhd)
    )
}

impl CardSprites {
    /// Paints one card's content (its image scaled into a plain rectangle,
    /// then the scrim) into `target` at its origin.
    #[allow(clippy::too_many_arguments)]
    fn paint_content(
        target: &ImageSurface,
        key: &CardKey,
        image: Option<&ImageSurface>,
        scrim: Option<&Brush>,
        dim_color: u32,
        fallback: u32,
    ) -> Option<()> {
        let (w, h) = (key.width, key.height);
        let cr = Context::new(target).ok()?;
        cr.rectangle(0.0, 0.0, f64::from(w), f64::from(h));
        cr.clip();
        match image {
            Some(image) => {
                let pattern = SurfacePattern::create(image);
                pattern.set_matrix(Matrix::new(
                    f64::from(image.width()) / f64::from(w), 0.0, 0.0,
                    f64::from(image.height()) / f64::from(h), 0.0, 0.0,
                ));
                pattern.set_filter(Filter::Bilinear);
                pattern.set_extend(cairo::Extend::Pad);
                cr.set_source(&pattern).ok()?;
            }
            None => color(&cr, fallback, 1.0),
        }
        cr.set_operator(Operator::Source);
        cr.paint().ok()?;
        cr.set_operator(Operator::Over);
        // Dims a non-centered slice, fading out as it nears the centered
        // position -- upstream's `Util.alpha(root.dimColor, item.selected ?
        // 0 : 0.42)`, continuous here instead of a hard boolean.
        let blend = f64::from(key.blend) / 32.0;
        if blend > 0.0 {
            if let Some(brush) = scrim {
                let _ = cr.push_group();
                fill_brush(&cr, brush, 0.0, 0.0, f64::from(w), f64::from(h));
                let _ = cr.pop_group_to_source();
                let _ = cr.paint_with_alpha(blend);
            } else {
                color(&cr, dim_color, 0.42 * blend);
                let _ = cr.paint();
            }
        }
        // A thin frame just inside the outline, in ink that contrasts with
        // the page, so a narrow side slice of a pale image still reads as
        // the edge of a card rather than a loose fragment.
        let (fw, fh) = (f64::from(w), f64::from(h));
        let skew = f64::from(key.skew) / 16.0;
        rounded_skewed(&cr, 0.0, 0.0, skew, fw, 0.0, fw - skew, fh, 14.0);
        let ink = if relative_luminance(dim_color) > 0.4 { 0x000000 } else { 0xffffff };
        color(&cr, ink, 0.22);
        cr.set_line_width(3.0);
        let _ = cr.stroke();
        Some(())
    }

    /// Fills the skewed rounded outline into `target` (A8) at its origin,
    /// clearing the rest of the `w` x `h` box.
    fn paint_mask(target: &ImageSurface, w: i32, h: i32, skew16: i32) -> Option<()> {
        let cr = Context::new(target).ok()?;
        let skew = f64::from(skew16) / 16.0;
        let (w, h) = (f64::from(w), f64::from(h));
        cr.rectangle(0.0, 0.0, w, h);
        cr.clip();
        cr.set_operator(Operator::Clear);
        cr.paint().ok()?;
        cr.set_operator(Operator::Over);
        rounded_skewed(&cr, 0.0, 0.0, skew, w, 0.0, w - skew, h, 14.0);
        cr.set_source_rgba(0.0, 0.0, 0.0, 1.0);
        cr.fill().ok()?;
        Some(())
    }

    /// Draws one card onto `cr` with its top-left corner at the whole-pixel
    /// point (`x`, `y`).
    #[allow(clippy::too_many_arguments)]
    fn draw(
        &mut self,
        cr: &Context,
        key: CardKey,
        keep: bool,
        image: Option<&ImageSurface>,
        scrim: Option<&Brush>,
        dim_color: u32,
        fallback: u32,
        (x, y): (f64, f64),
    ) -> Option<()> {
        self.painted = true;
        self.clock += 1;
        let clock = self.clock;
        let (w, h) = (key.width, key.height);
        if let Some((sprite, used)) = self.cards.get_mut(&key) {
            *used = clock;
            cr.set_source_surface(&*sprite, x, y).ok()?;
            return cr.paint().ok();
        }
        if !keep {
            let fits = |s: &ImageSurface| s.width() >= w && s.height() >= h;
            if !self.scratch.as_ref().is_some_and(|(c, m)| fits(c) && fits(m)) {
                let (sw, sh) = self.scratch.as_ref().map_or((0, 0), |(c, _)| (c.width(), c.height()));
                let (sw, sh) = (sw.max(w), sh.max(h));
                self.scratch = Some((
                    ImageSurface::create(Format::ARgb32, sw, sh).ok()?,
                    ImageSurface::create(Format::A8, sw, sh).ok()?,
                ));
            }
            let (content, mask) = self.scratch.as_ref()?;
            Self::paint_content(content, &key, image, scrim, dim_color, fallback)?;
            Self::paint_mask(mask, w, h, key.skew)?;
            content.flush();
            mask.flush();
            let _ = cr.save();
            cr.rectangle(x, y, f64::from(w), f64::from(h));
            cr.clip();
            cr.set_source_surface(content, x, y).ok()?;
            let result = cr.mask_surface(mask, x, y).ok();
            let _ = cr.restore();
            return result;
        }
        let content = ImageSurface::create(Format::ARgb32, w, h).ok()?;
        Self::paint_content(&content, &key, image, scrim, dim_color, fallback)?;
        let mask = match self.masks.get(&(w, h, key.skew)) {
            Some(mask) => mask.clone(),
            None => {
                let mask = ImageSurface::create(Format::A8, w, h).ok()?;
                Self::paint_mask(&mask, w, h, key.skew)?;
                mask.flush();
                if self.masks.len() >= 8 {
                    self.masks.clear();
                }
                self.masks.insert((w, h, key.skew), mask.clone());
                mask
            }
        };
        let sprite = ImageSurface::create(Format::ARgb32, w, h).ok()?;
        {
            let sprite_cr = Context::new(&sprite).ok()?;
            sprite_cr.set_source_surface(&content, 0.0, 0.0).ok()?;
            sprite_cr.mask_surface(&mask, 0.0, 0.0).ok()?;
        }
        sprite.flush();
        let size = (w as usize) * (h as usize) * 4;
        while self.bytes + size > CARD_SPRITE_MAX_BYTES && !self.cards.is_empty() {
            let oldest = self.cards.iter().min_by_key(|(_, (_, used))| *used).map(|(k, _)| k.clone())?;
            if let Some((old, _)) = self.cards.remove(&oldest) {
                self.bytes -= (old.width() as usize) * (old.height() as usize) * 4;
            }
        }
        self.bytes += size;
        self.cards.insert(key, (sprite.clone(), clock));
        cr.set_source_surface(&sprite, x, y).ok()?;
        cr.paint().ok()
    }
}

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
            rounded_skewed(cr, slice.x, slice.y, top_left, top_right,
                bottom_left, bottom_right, slice.height, 14.0);

        };
        // A slice is drawn as a cached sprite: its image scaled into a plain
        // rectangle, scrimmed, then cut to the skewed outline by an alpha
        // mask, and blitted at a whole-pixel offset. Each step stays on a
        // pixman fast path. Filling the anti-aliased outline with a scaled
        // image directly falls back to the general per-span compositor,
        // which spent most of a moving row's frame in memset on the board.
        // A slice at rest size is a cache hit and costs one copy.
        let variant = if slice.blend < 0.5 {
            Variant::Expanded
        } else {
            Variant::Slice
        };
        let image = thumbnails
            .and_then(|cache| cache.get(id, variant))
            .filter(|image| image.width() > 0 && image.height() > 0);
        let (sx, sy) = (slice.x.round(), slice.y.round());
        let (sw, sh) = (slice.width.round().max(1.0) as i32, slice.height.round().max(1.0) as i32);
        let scrim = theme_brush(theme, "image-picker", "scrim");
        let fallback = palette_rgb_or(theme, "background", 0x1b2830);
        let key = CardKey {
            id: (*id).to_owned(),
            variant: variant.tag(),
            image: image.map_or(0, |image| image.to_raw_none() as usize),
            width: sw,
            height: sh,
            skew: (skew * 16.0).round() as i32,
            blend: (slice.blend.clamp(0.0, 1.0) * 32.0).round() as u8,
            look: format!("{scrim:?}/{dim_color}/{fallback}"),
        };
        // Only collapsed side slices are kept: they are most of a row and
        // small. The centred card is the one that changes size as soon as a
        // swipe starts, so a kept copy of it would rarely be drawn again.
        let keep = (sw, sh) == (geometry.slice_w.round() as i32, geometry.slice_h.round() as i32);
        CARD_SPRITES.with(|sprites| {
            sprites.borrow_mut().draw(cr, key, keep, image, scrim, dim_color, fallback, (sx, sy));
        });
        // A slice with no decoded thumbnail yet gets a spinner instead of a
        // silent flat fill, so a slow decode (goal: never a frozen-looking
        // UI) reads as "loading", not "missing" or "broken".
        if image.is_none() {
            let _ = cr.save();
            parallelogram(cr);
            cr.clip();
            spinner(
                cr,
                slice.x + slice.width / 2.0,
                slice.y + slice.height / 2.0,
                (slice.width.min(slice.height) * 0.16).max(6.0),
                pulse_phase,
                style.accent,
            );
            let _ = cr.restore();
        }

        if slice.index == centered {
            rounded(cr, slice.x + slice.width / 2.0 - 18.0,
                slice.y + slice.height + 4.0, 36.0, 3.0, 1.5);
            color(cr, style.accent, 1.0);
            let _ = cr.fill();
        }

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
/// Settings' Vision page: two toggle cards, larger text and high contrast,
/// each a full 99 px tap target (`theme_ui::ThemeView::hit`). A tap saves the
/// choice and re-applies the active theme with it, so the page itself redraws
/// in the new size and palette once that settles.
fn paint_vision(cr: &Context, w: f64, h: f64, view: &ThemeView, theme: Option<&AppearanceSnapshot>) {
    let style = visual_style(theme, "controls");
    // The same header row as the theme chooser, which is also where
    // `ThemeView::hit` looks for Back and Close.
    paint_chooser_header(cr, style, w, h);
    let pending = view.vision_pending();
    let shown = pending.unwrap_or(&view.vision);
    // Laid out for the size the screen is drawn at now (the saved step),
    // the same call `ThemeView::hit` makes.
    let lay = vision_layout(w, view.vision.text_scale_value());
    let title_w = text_advance(cr, "Vision", TYPE_TITLE, pango::Weight::Bold);
    heading(cr, "Vision", 28.0, lay.title_y, w - 56.0, TYPE_TITLE, style.text);
    let note = "Applies to every theme";
    if lay.note_beside {
        let x = 28.0 + title_w + SPACE_CARD;
        let y = lay.title_y + vision_line(TYPE_TITLE) - vision_line(TYPE_CAPTION) - 4.0;
        themed_role_fit(cr, theme, "caption", note, x, y, w - x - 28.0, TYPE_CAPTION, style.muted, pango::Weight::Normal);
    } else {
        let y = lay.title_y + vision_line(TYPE_TITLE) + 2.0;
        themed_role_fit(cr, theme, "caption", note, 28.0, y, w - 56.0, TYPE_CAPTION, style.muted, pango::Weight::Normal);
    }
    let ink = if view.vision_loaded { style.text } else { style.muted };
    let state = |applying: bool, value: &str| -> String {
        if !view.vision_loaded {
            "Loading…".into()
        } else if applying {
            "Applying…".into()
        } else {
            value.into()
        }
    };

    // Text size: one card with the four steps as segments.
    let (x, y, cw, ch) = lay.text_card;
    paint_card(cr, theme, "controls", CardJob::Group, x, y, cw, ch);
    let text_applying = pending.is_some_and(|p| p.text_scale != view.vision.text_scale);
    let step = shown.text_step();
    let heading_value = state(text_applying, &format!("{}%", (TEXT_SCALE_VALUES[step] * 100.0).round()));
    let value_w = text_advance(cr, &heading_value, TYPE_LABEL, pango::Weight::Medium);
    text_weight(cr, &heading_value, x + cw - 20.0 - value_w, y + 18.0, value_w + 2.0, TYPE_LABEL,
                ink, pango::Weight::Medium);
    themed_role_fit(cr, theme, "body", "Text size", x + 20.0, y + 18.0, cw - 60.0 - value_w, TYPE_LABEL, ink, pango::Weight::Medium);
    for (index, (sx, sy, sw, sh)) in lay.segments.into_iter().enumerate() {
        let label = format!("{}%", (TEXT_SCALE_VALUES[index] * 100.0).round());
        // Shrinks toward the Body role to fit its segment at a larger step.
        let full = context_font_size(cr, TYPE_BODY);
        let advance = text_advance_resolved(cr, &label, full, pango::Weight::Bold);
        let room = sw - 12.0;
        let drawn = if advance > room { (full * room / advance).max(TYPE_BODY) } else { full };
        // The chosen step is the page's one accent: a pill around its
        // label (the whole segment stays the tap target). The others are
        // bare labels inside the group.
        let selected = index == step && view.vision_loaded;
        if selected {
            let pill_h = (drawn * 1.2 + 2.0 * SPACE_IN_ROW).min(sh);
            paint_card(cr, theme, "controls", CardJob::Chosen { pill: true },
                       sx + 2.0, sy + (sh - pill_h) / 2.0, sw - 4.0, pill_h);
        }
        let lw = text_advance_resolved(cr, &label, drawn, pango::Weight::Bold);
        text_weight_resolved(cr, &label, sx + (sw - lw) / 2.0, sy + (sh - drawn * 1.2) / 2.0, lw + 2.0, drawn,
                             ink, pango::Weight::Bold);
    }

    // High contrast: one on/off card.
    let (x, y, cw, ch) = lay.contrast_card;
    let on = shown.high_contrast();
    let job = if on { CardJob::Chosen { pill: false } } else { CardJob::Control };
    paint_card(cr, theme, "controls", job, x, y, cw, ch);
    themed_role_fit(cr, theme, "body", "High contrast", x + 20.0, y + 18.0, cw - 40.0, TYPE_LABEL, ink, pango::Weight::Medium);
    let contrast_applying = pending.is_some_and(|p| p.contrast != view.vision.contrast);
    let value = state(contrast_applying, if on { "On" } else { "Off" });
    let label_h = (TYPE_LABEL * lay.scale * 1.35).ceil();
    themed_role_fit(cr, theme, "body", &value, x + 20.0, y + 18.0 + label_h + 6.0, cw - 40.0, TYPE_BODY,
                    ink, pango::Weight::Normal);

    let (sx, sw) = (lay.text_card.0, lay.contrast_card.0 + lay.contrast_card.2 - lay.text_card.0);
    if let Some(error) = view.error.as_deref() {
        themed_role_fit(cr, theme, "caption", error, sx, lay.status_y, sw, TYPE_CAPTION, style.error, pango::Weight::Normal);
    } else if let Some(message) = view.message.as_deref() {
        themed_role_fit(cr, theme, "caption", message, sx, lay.status_y, sw, TYPE_CAPTION, style.muted, pango::Weight::Normal);
    }
}

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
    // Stacked on the portrait panel, side by side on the landscape one;
    // `theme_ui::chooser_layout` is what `main.rs` hit-tests with too.
    let lay = view.layout(w as u32, h as u32);
    // The wide layout keeps each carousel's slices inside its own half.
    // Slices are drawn into a group and painted back through a mask that
    // fades the column's outer edges, so a neighbour's thumbnail thins out
    // instead of ending in a hard cut at the column or output edge.
    let column_clip = |cr: &Context, cols: (f64, f64)| {
        let _ = cr.save();
        if lay.wide {
            cr.rectangle(cols.0, 0.0, cols.1 - cols.0, h);
            cr.clip();
            cr.push_group();
        }
    };
    // The fade spans from the centred card's edge to the column's edge (at
    // least CAROUSEL_EDGE_FADE), so the stacked neighbours thin out across
    // the whole gap and the centred card itself is never dimmed.
    let column_end = |cr: &Context, cols: (f64, f64), center_x: f64, card_w: f64| {
        if lay.wide {
            if let Ok(group) = cr.pop_group() {
                let span = cols.1 - cols.0;
                let left = (center_x - card_w / 2.0 - cols.0).max(CAROUSEL_EDGE_FADE) / span;
                let right = (cols.1 - center_x - card_w / 2.0).max(CAROUSEL_EDGE_FADE) / span;
                let (left, right) = (left.min(0.5), right.min(0.5));
                let mask = cairo::LinearGradient::new(cols.0, 0.0, cols.1, 0.0);
                mask.add_color_stop_rgba(0.0, 0.0, 0.0, 0.0, 0.0);
                mask.add_color_stop_rgba(left, 0.0, 0.0, 0.0, 1.0);
                mask.add_color_stop_rgba(1.0 - right, 0.0, 0.0, 0.0, 1.0);
                mask.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 0.0);
                if cr.set_source(&group).is_ok() {
                    let _ = cr.mask(&mask);
                }
            }
        }
        let _ = cr.restore();
    };
    if let Some(brush) = theme_brush(theme, "image-picker", "background") {
        let _ = fill_brush(cr, brush, 0.0, 0.0, w, h);
    }
    // Upstream's `dimColor: Color.background` -- tints unselected carousel
    // slices, not the panel's own background wash above.
    let dim_color = palette_rgb_or(theme, "background", 0x0b1216);
    if view.page != ThemePage::List {
        paint_chooser_header(cr, style, w, h);
        return;
    }
    // The header scrolls away with the page (`ThemeView::layout`).
    let _ = cr.save();
    cr.translate(0.0, -view.page_scroll(w as u32, h as u32));
    paint_chooser_header(cr, style, w, h);
    let _ = cr.restore();
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
    heading(cr, "Themes", lay.themes_heading.0, lay.themes_heading.1, lay.theme_text.1, TYPE_LABEL, style.text);
    text_wrapped(
        cr,
        crate::theme_ui::CHOOSER_HINT,
        lay.themes_hint.0,
        lay.themes_hint.1,
        lay.theme_text.1,
        TYPE_CAPTION,
        style.muted,
    );
    match &view.list {
        Some(list) if !list.themes.is_empty() => {
            let center_x = lay.theme_cx;
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
            column_clip(cr, lay.theme_cols);
            paint_carousel(
                cr,
                theme,
                dim_color,
                style,
                thumbnails,
                &lay.theme_geometry,
                view.theme_position,
                &ids,
                center_x,
                lay.theme_top,
                view.theme_pressed,
                view.applying_theme_index(),
                pulse_phase,
            );
            column_end(cr, lay.theme_cols, center_x, lay.theme_geometry.expanded_w);
            let entry = &list.themes[centered];
            let is_current = list.active.id.as_deref() == Some(entry.id.as_str());
            let label_y = lay.theme_top + lay.theme_geometry.expanded_h + 12.0;
            heading(cr, &entry.label, lay.theme_text.0, label_y, lay.theme_text.1, TYPE_LABEL, style.text);
            let status = if is_current {
                "Current theme"
            } else {
                match entry.origin {
                    crate::theme_catalog::ThemeOrigin::Builtin => "Built in",
                    crate::theme_catalog::ThemeOrigin::User => "User theme",
                }
            };
            text_wrapped(cr, status, lay.theme_text.0, label_y + chooser_label_line(cr), lay.theme_text.1, TYPE_CAPTION, style.muted);
        }
        Some(_) => {
            text(
                cr,
                "No themes available",
                lay.theme_text.0,
                lay.theme_top + 22.0,
                lay.theme_text.1,
                TYPE_CAPTION,
                style.muted,
            );
        }
        None => {
            text(
                cr,
                "Loading themes",
                lay.theme_text.0,
                lay.theme_top + 22.0,
                lay.theme_text.1,
                TYPE_CAPTION,
                style.muted,
            );
        }
    }
    // `view.preview` is the *active* theme's own detail (see `ThemeView`'s
    // own doc) -- this background carousel always reflects whichever
    // theme is currently, durably active, not whatever the theme carousel
    // above happens to be centred on mid-browse; it updates only once a
    // tapped theme's own activation actually settles.
    // Tapping this heading cycles the background's fit mode
    // (`ThemeIntent::Fit`); the current mode is named after the title.
    let backgrounds_title = format!("Backgrounds · {}", view.fit);
    wrapped_text(
        cr,
        &backgrounds_title,
        lay.backgrounds_heading.0,
        lay.backgrounds_heading.1,
        lay.background_text.1,
        context_font_size(cr, TYPE_LABEL),
        style.text,
        pango::Weight::Bold,
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
        // On the wide layout the acknowledgement shares the heading's line;
        // the heading now names the fit mode and grows with the theme's (and
        // the vision option's) text size, so start after what was drawn.
        // Only when the whole message fits after a one-line heading: the
        // card's status and the message line below say the same thing.
        let (x, y, width) = lay.feedback;
        let (hx, _) = lay.backgrounds_heading;
        let title_w = text_advance(cr, &backgrounds_title, TYPE_LABEL, pango::Weight::Bold);
        let start = x.max(hx + title_w + 16.0);
        if title_w <= lay.background_text.1
            && text_advance(cr, message, TYPE_CAPTION, pango::Weight::Normal) <= x + width - start
        {
            text(cr, message, start, y, x + width - start, TYPE_CAPTION, color);
        }
    }
    match view.preview.as_ref() {
        Some(preview) if !preview.backgrounds.is_empty() => {
            let center_x = lay.background_cx;
            let ids: Vec<&str> = preview.backgrounds.iter().map(|b| b.id.as_str()).collect();
            let centered = view
                .background_position
                .round()
                .clamp(0.0, (preview.backgrounds.len() - 1) as f64) as usize;
            column_clip(cr, lay.background_cols);
            paint_carousel(
                cr,
                theme,
                dim_color,
                style,
                thumbnails,
                &lay.background_geometry,
                view.background_position,
                &ids,
                center_x,
                lay.background_top,
                view.background_pressed,
                view.applying_background_index(),
                pulse_phase,
            );
            column_end(cr, lay.background_cols, center_x, lay.background_geometry.expanded_w);
            let background = &preview.backgrounds[centered];
            let label_y = lay.background_top + lay.background_geometry.expanded_h + 12.0;
            heading(
                cr,
                &background_display_label(&background.label),
                lay.background_text.0,
                label_y,
                lay.background_text.1,
                TYPE_LABEL,
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
            text_wrapped(
                cr,
                status,
                lay.background_text.0,
                label_y + chooser_label_line(cr),
                lay.background_text.1,
                TYPE_CAPTION,
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
                lay.background_text.0,
                lay.background_top + 22.0,
                lay.background_text.1,
                TYPE_CAPTION,
                style.muted,
            );
        }
        None => {
            text(
                cr,
                "Loading backgrounds",
                lay.background_text.0,
                lay.background_top + 22.0,
                lay.background_text.1,
                TYPE_CAPTION,
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
    let message_y = lay.message_y;
    let (mx, mw) = lay.background_text;
    if let Some(error) = &view.error {
        text(cr, error, mx, message_y, mw, TYPE_CAPTION, style.error);
    } else if view.pending.is_some() {
        text(cr, "Preparing…", mx, message_y, mw, TYPE_CAPTION, style.muted);
    } else if let Some(message) = &view.message {
        text(cr, message, mx, message_y, mw, TYPE_CAPTION, style.muted);
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

/// The Settings About and Date & time pages (`device_info`): a Back link, the
/// title, and one label-and-value card per row. Portrait paints the 568x1232
/// artwork scaled to the surface; landscape paints three columns in real
/// pixels. Every rect comes from `device_info::layout_for`, which the Back tap
/// reads too. Read-only: nothing here but Back is a target.
fn paint_info(
    cr: &Context,
    view: &crate::device_info::InfoPublic,
    theme: Option<&AppearanceSnapshot>,
    width: f64,
    height: f64,
) {
    let lay = crate::device_info::layout_for(width as u32, height as u32, view.rows.len());
    let _ = cr.save();
    if !lay.wide {
        cr.scale(width / 568.0, height / 1232.0);
    }
    let style = visual_style(theme, "controls");
    let (bx, by, bw, bs) = lay.back_text;
    text(cr, "\u{2039} Settings", bx, by, bw, bs, style.accent);
    let (tx, ty, tw, ts) = lay.title;
    heading(cr, view.page.title(), tx, ty, tw, ts, style.text);
    for ((label, value), (x, y, w, h)) in view.rows.iter().zip(&lay.cards) {
        service_card(cr, theme, "controls", *x, *y, *w, *h, false);
        themed_role_fit(cr, theme, "caption", label, x + 18.0, y + lay.label_dy, w - 36.0, TYPE_CAPTION, style.muted, pango::Weight::Normal);
        themed_role_fit(cr, theme, "body", value, x + 18.0, y + lay.value_dy, w - 36.0, TYPE_BODY, style.text, pango::Weight::Normal);
    }
    let _ = cr.restore();
}

/// The Settings Cellular and Location pages (`modem_ui`): the on/off switch,
/// the service's reported state, the SIM PIN keypad while the SIM asks for
/// one, and the stored-message clear control. Portrait paints the 568x1232
/// artwork scaled to the surface; landscape paints two columns in real
/// pixels. Every rect comes from `modem_ui::layout_for`, which the taps read
/// too. The PIN shows as dots only: the view holds a length, not the digits.
fn paint_modem(
    cr: &Context,
    view: &crate::modem_ui::ModemPublic,
    theme: Option<&AppearanceSnapshot>,
    width: f64,
    height: f64,
) {
    use crate::modem_ui::Page as ModemPage;
    let lay = crate::modem_ui::layout_for(width as u32, height as u32, view);
    let _ = cr.save();
    if !lay.wide {
        cr.scale(width / 568.0, height / 1232.0);
    }
    let style = visual_style(theme, "controls");
    let status = &view.status;
    let cellular = view.page == ModemPage::Cellular;
    let (bx, by, bw, bs) = lay.back_text;
    text(cr, "\u{2039} Settings", bx, by, bw, bs, style.accent);
    let (tx, ty, tw, ts) = lay.title;
    heading(cr, if cellular { "Cellular" } else { "Location" }, tx, ty, tw, ts, style.text);

    // The switch.
    let (cx, cy, cw, ch) = lay.switch_card;
    service_card(cr, theme, "controls", cx, cy, cw, ch, false);
    let on = if cellular { status.cellular } else { status.location };
    let working = matches!(view.pending, Some(crate::modem::Kind::Cellular | crate::modem::Kind::Location));
    let pill = lay.switch_pill;
    themed_role_fit(cr, theme, "body", if cellular { "Cellular" } else { "Location" }, cx + 18.0, cy + lay.switch_dy.0, pill.0 - cx - 30.0, TYPE_LABEL, style.text, pango::Weight::Medium);
    let value = if working { "Working…" } else if on { "On" } else { "Off" };
    themed_role_fit(cr, theme, "caption", value, cx + 18.0, cy + lay.switch_dy.1, pill.0 - cx - 30.0, TYPE_CAPTION, style.muted, pango::Weight::Normal);
    let (px, py, pw, ph) = pill;
    rounded(cr, px, py, pw, ph, ph / 2.0);
    if on {
        color(cr, style.accent, if working { 0.5 } else { 1.0 });
    } else {
        color(cr, style.muted, 0.35);
    }
    let _ = cr.fill();
    let knob = ph - 8.0;
    let knob_x = if on { px + pw - 4.0 - knob / 2.0 } else { px + 4.0 + knob / 2.0 };
    cr.arc(knob_x, py + ph / 2.0, knob / 2.0, 0.0, std::f64::consts::TAU);
    color(cr, if on { palette_rgb_or(theme, "background", 0x1e1e2e) } else { style.text }, 1.0);
    let _ = cr.fill();

    // The reported state.
    let (sx, sy, sw, sh) = lay.status_card;
    service_card(cr, theme, "controls", sx, sy, sw, sh, false);
    let signal_text = status.signal_label();
    let operator = status.operator.clone().unwrap_or_else(|| "\u{2014}".into());
    let access = status.rat.clone().unwrap_or_else(|| "\u{2014}".into());
    let rows: Vec<(&str, String)> = if cellular {
        vec![
            ("SIM", status.sim_label().into()),
            ("Network", status.registration_label().into()),
            ("Operator", operator),
            ("Access", access),
            ("Signal", signal_text.into()),
        ]
    } else {
        vec![("Status", status.location_label().into())]
    };
    let label_w = (sw - 36.0) * 0.34;
    for (index, (label, value)) in rows.iter().enumerate() {
        let y = sy + lay.status_row0 + index as f64 * lay.status_pitch;
        themed_role_fit(cr, theme, "caption", label, sx + 18.0, y, label_w - 8.0, TYPE_CAPTION, style.muted, pango::Weight::Normal);
        let mut value_x = sx + 18.0 + label_w;
        let mut value_w = sw - 36.0 - label_w;
        if cellular && *label == "Signal" {
            let size = vision_line(TYPE_CAPTION).ceil();
            let (lit, none) = match status.cellular_indicator() {
                Some(crate::modem::CellularIndicator::Bars(n)) => (n, false),
                _ => (0, true),
            };
            glyph::paint_signal(cr, lit, none, value_x, y + (vision_line(TYPE_BODY) - size) / 2.0, size, style.text);
            value_x += size + 10.0;
            value_w -= size + 10.0;
        }
        if !cellular {
            let size = vision_line(TYPE_CAPTION).ceil();
            if let Some(indicator) = status.location_indicator() {
                glyph::paint_location(cr, indicator == crate::modem::LocationIndicator::Fix, value_x, y + (vision_line(TYPE_BODY) - size) / 2.0, size, style.text);
                value_x += size + 10.0;
                value_w -= size + 10.0;
            }
        }
        themed_role_fit(cr, theme, "body", value, value_x, y, value_w, TYPE_BODY, style.text, pango::Weight::Normal);
    }

    // One line for a pending request, its failure, or the modem's own error.
    let (mx, my, mw) = lay.message;
    if working || view.pending.is_some() {
        themed_role_fit(cr, theme, "caption", "Working\u{2026}", mx, my, mw, TYPE_CAPTION, style.muted, pango::Weight::Normal);
    } else if let Some(message) = &view.message {
        themed_role_fit(cr, theme, "caption", message, mx, my, mw, TYPE_CAPTION, style.error, pango::Weight::Normal);
    } else if status.power == crate::modem::Power::Error {
        let reason = status.last_error.as_deref().unwrap_or("not responding");
        themed_role_fit(cr, theme, "caption", &format!("Modem error: {reason}"), mx, my, mw, TYPE_CAPTION, style.error, pango::Weight::Normal);
    }

    if let Some(pin) = &lay.pin {
        let (kx, ky, kw, kh) = pin.card;
        service_card(cr, theme, "controls", kx, ky, kw, kh, false);
        let prompt = match status.pin_attempts {
            Some(1) => "Enter SIM PIN \u{b7} 1 try left".to_string(),
            Some(n) => format!("Enter SIM PIN \u{b7} {n} tries left"),
            None => "Enter SIM PIN".to_string(),
        };
        themed_role_fit(cr, theme, "caption", &prompt, pin.prompt.0, pin.prompt.1, pin.prompt.2, TYPE_CAPTION, style.text, pango::Weight::Normal);
        let (fx, fy, fw, fh) = pin.field;
        let well = palette_rgb_or(theme, "background", 0x1e1e2e);
        rounded(cr, fx, fy, fw, fh, 12.0);
        color(cr, well, 0.55);
        let _ = cr.fill();
        let dots = "\u{2022}".repeat(view.pin_len);
        if dots.is_empty() {
            themed_role_fit(cr, theme, "caption", "4 to 8 digits", fx + 18.0, fy + pin.field_text_dy, fw - 36.0, TYPE_CAPTION, style.muted, pango::Weight::Normal);
        } else {
            text(cr, &dots, fx + 18.0, fy + pin.field_text_dy, fw - 36.0, TYPE_BODY, style.text);
        }
        let ready = view.pin_len >= 4 && view.pending.is_none();
        for (index, key) in pin.keys.iter().enumerate() {
            let (x, y, w, h) = *key;
            // A key is a darker well in the card, so each one reads as a button.
            rounded(cr, x, y, w, h, 12.0);
            color(cr, well, 0.55);
            let _ = cr.fill();
            let (label, rgb) = match index {
                9 => ("\u{232b}", style.text),
                11 => ("OK", if ready { style.accent } else { style.muted }),
                10 => ("0", style.text),
                n => (["1", "2", "3", "4", "5", "6", "7", "8", "9"][n], style.text),
            };
            centered_label(cr, label, x, y + pin.key_text_dy, w, TYPE_BODY, rgb);
        }
    }

    if let Some((x, y, w, h)) = lay.clear {
        let any = status.sms_count > 0;
        service_card(cr, theme, "controls", x, y, w, h, view.clear_armed);
        themed_role_fit(cr, theme, "body", "Clear stored messages", x + 18.0, y + lay.clear_dy.0, w - 36.0, TYPE_LABEL, if any { style.text } else { style.muted }, pango::Weight::Medium);
        let (detail, rgb) = if view.clear_armed {
            (format!("Tap again to delete {}", status.sms_count), style.error)
        } else if any {
            (format!("{} stored", status.sms_count), style.muted)
        } else {
            ("No stored messages".to_string(), style.muted)
        };
        themed_role_fit(cr, theme, "caption", &detail, x + 18.0, y + lay.clear_dy.1, w - 36.0, TYPE_CAPTION, rgb, pango::Weight::Normal);
    }
    let _ = cr.restore();
}

fn paint_wifi(
    cr: &Context,
    view: &WifiPublic,
    theme: Option<&AppearanceSnapshot>,
    width: f64,
    height: f64,
) {
    // Portrait: touch coordinates and artwork share a 568x1232 reference
    // layout scaled to the surface. The landscape panel paints its own
    // two-column layout in real pixels. `wifi_ui::layout` holds every rect
    // both this paint and `wifi_ui::hit` read.
    let lay = wifi_layout(view, width, height);
    let _ = cr.save();
    if !lay.wide {
        cr.scale(width / 568.0, height / 1232.0);
    }
    let style = visual_style(theme, "controls");
    // The Entry page pans its header up with it.
    let header_pan = if view.page == WifiPage::Entry { lay.entry_pan } else { 0.0 };
    let (bx, by, bw, bs) = lay.back_text;
    let by = by - header_pan;
    text(
        cr,
        if view.page == WifiPage::List {
            "‹ Settings"
        } else {
            "‹ Networks"
        },
        bx,
        by,
        bw,
        bs,
        style.accent,
    );
    let (tx, ty, tw, ts) = lay.title;
    heading(cr, "Wi-Fi", tx, ty - header_pan, tw, ts, style.text);
    match view.page {
        WifiPage::Closed => {}
        WifiPage::List => {
            let (rx, ry, rw, rs) = lay.refresh_text;
            text(cr, "Refresh", rx, ry, rw, rs, style.accent);
            let (cx, cy, cw, ch) = lay.current_card;
            service_card(cr, theme, "controls", cx, cy, cw, ch, false);
            let (label_dy, name_dy, saved_dy) = lay.current_dy;
            text_wrapped(cr, crate::wifi_ui::CURRENT_LABEL, cx + 18.0, cy + label_dy, cw - 36.0, TYPE_CAPTION, style.muted);
            text(
                cr,
                view.snapshot
                    .as_ref()
                    .and_then(|s| s.current.as_deref())
                    .unwrap_or("Not connected"),
                cx + 18.0,
                cy + name_dy,
                cw - 36.0,
                TYPE_BODY,
                style.text,
            );
            let saved = view.snapshot.as_ref().map_or(0, |s| s.saved.len());
            text_wrapped(
                cr,
                &format!("{saved} saved  ·  tap to connect"),
                cx + 18.0,
                cy + saved_dy,
                cw - 36.0,
                TYPE_CAPTION,
                style.muted,
            );
            let (lx, ly, lw, ls) = lay.list_label;
            text_wrapped(cr, crate::wifi_ui::LIST_LABEL, lx, ly, lw, ls, style.muted);
            let _ = cr.save();
            let (kx, ky, kw, kh) = lay.list_clip;
            cr.rectangle(kx, ky, kw, kh);
            cr.clip();
            let top = lay.list_view.1;
            let (name_dy, status_dy, chevron_dy) = lay.row_dy;
            if let Some(snapshot) = &view.snapshot {
                let rows = all_networks(snapshot);
                for (index, item) in rows.iter().enumerate() {
                    let y = top + index as f64 * lay.row_pitch - view.scroll;
                    if !(lay.row_cull.0..lay.row_cull.1).contains(&y) {
                        continue;
                    }
                    service_card(cr, theme, "controls", lay.row_x, y, lay.row_w, lay.row_h, false);
                    text(cr, &item.ssid, lay.row_x + 18.0, y + name_dy, lay.row_w - 80.0, TYPE_LABEL, style.text);
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
                    text(cr, status, lay.row_x + 18.0, y + status_dy, lay.row_w - 80.0, TYPE_CAPTION, style.muted);
                    text(cr, "›", lay.row_x + lay.row_w - 52.0, y + chevron_dy, 40.0, TYPE_LABEL, style.accent);
                }
                if rows.is_empty() && !view.pending {
                    let (ex, ey, ew) = lay.list_empty;
                    text_wrapped(cr, "No networks found. Tap Refresh.", ex, ey, ew, TYPE_CAPTION, style.muted);
                }
            } else {
                let (ex, ey, ew) = lay.list_empty;
                text_wrapped(cr, "Scanning nearby networks…", ex, ey, ew, TYPE_CAPTION, style.muted);
            }
            let _ = cr.restore();
        }
        WifiPage::Entry => {
            if let Some(selected) = &view.selected {
                let (nx, ny, nw, nh) = lay.net_card;
                service_card(cr, theme, "controls", nx, ny, nw, nh, true);
                text(cr, &selected.ssid, nx + 18.0, ny + lay.net_name_dy, nw - 50.0, TYPE_BODY, style.text);
                text_wrapped(
                    cr,
                    match selected.security {
                        Security::Open => "Open network · no password needed",
                        Security::Wpa2Psk if view.use_saved => "WPA2-Personal · saved credential",
                        Security::Wpa2Psk => crate::wifi_ui::LONGEST_SECURITY,
                        Security::Unsupported => "Unsupported",
                    },
                    nx + 18.0,
                    ny + lay.net_sub_dy,
                    nw - 50.0,
                    TYPE_CAPTION,
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
                        lay.pw_label.0,
                        lay.pw_label.1,
                        nw - 8.0,
                        TYPE_CAPTION,
                        style.muted,
                    );
                    let (fx, fy, fw, fh) = lay.field;
                    service_card_interaction(cr, theme, "controls", fx, fy, fw, fh, false, false, !view.use_saved);
                    // As many dots as fit beside the counter, never an ellipsis.
                    let fit = (lay.field_text_w / (context_font_size(cr, TYPE_BODY) * 0.62)).floor() as usize;
                    let mask = "•".repeat(view.password_len.min(22).min(fit));
                    text(
                        cr,
                        if view.use_saved {
                            "Stored securely"
                        } else if view.password_visible {
                            "" // Revealed input is painted transiently, outside scene caches.
                        } else if mask.is_empty() {
                            "Type the password"
                        } else {
                            &mask
                        },
                        fx + 18.0,
                        fy + lay.field_text_dy,
                        if view.use_saved { fw - 36.0 } else { lay.field_text_w },
                        TYPE_BODY,
                        style.text,
                    );
                    if !view.use_saved {
                        // Eye target is 72 units wide and the field's height, above the keyboard.
                        let (ex, ey) = lay.eye_center;
                        color(cr, style.accent, 1.0);
                        cr.set_line_width(2.5);
                        cr.move_to(ex - 18.0, ey);
                        cr.curve_to(ex - 10.0, ey - 13.0, ex + 10.0, ey - 13.0, ex + 18.0, ey);
                        cr.curve_to(ex + 10.0, ey + 13.0, ex - 10.0, ey + 13.0, ex - 18.0, ey);
                        let _ = cr.stroke();
                        cr.arc(ex, ey, 5.0, 0.0, std::f64::consts::TAU);
                        let _ = cr.stroke();
                        if !view.password_visible {
                            cr.move_to(ex - 18.0, ey + 18.0); cr.line_to(ex + 18.0, ey - 18.0);
                            let _ = cr.stroke();
                        }
                        let (kx, ky, kw) = lay.counter;
                        text(cr, &format!("{} / 63", view.password_len), kx, ky, kw, TYPE_CAPTION, style.muted);
                    }
                }
                let show_saved_buttons = view
                    .snapshot
                    .as_ref()
                    .is_some_and(|s| s.saved.iter().any(|n| n.ssid == selected.ssid));
                if show_saved_buttons {
                    if view.use_saved && selected.security == Security::Wpa2Psk {
                        let (x, y, w, h) = lay.saved_change;
                        service_card(cr, theme, "controls", x, y, w, h, false);
                        text_wrapped(cr, crate::wifi_ui::CHANGE_PASSWORD, x + crate::wifi_ui::SAVED_INSET, y + lay.saved_text_dy, w - 2.0 * crate::wifi_ui::SAVED_INSET, TYPE_LABEL, style.accent);
                    }
                    let (x, y, w, h) = lay.saved_forget;
                    service_card(cr, theme, "controls", x, y, w, h, false);
                    text_wrapped(cr, crate::wifi_ui::FORGET_NETWORK, x + crate::wifi_ui::SAVED_INSET, y + lay.saved_text_dy, w - 2.0 * crate::wifi_ui::SAVED_INSET, TYPE_LABEL, style.error);
                }
                // A rejected password used to sit as a single line of colored
                // text between the numeric row and the Cancel/Connect
                // buttons -- easy to miss in what otherwise reads as dead
                // space (finding P0-3). Give it its own elevated,
                // border-accented banner directly under the field it
                // refers to instead.
                if selected.security == Security::Wpa2Psk && !view.use_saved {
                    if let Some(message) = entry_error_message(view) {
                        let banner_y = if show_saved_buttons { lay.banner_saved_y } else { lay.banner_unsaved_y };
                        let (bw, bh, mw) = lay.banner;
                        let bx = lay.buttons.0 .0;
                        service_card(cr, theme, "controls", bx, banner_y, bw, bh, false);
                        rounded(cr, bx + 0.75, banner_y + 0.75, bw - 1.5, bh - 1.5, 15.25);
                        cr.set_line_width(1.5);
                        color(cr, style.error, 0.85);
                        let _ = cr.stroke();
                        let label_y = banner_y + (bh - context_font_size(cr, TYPE_LABEL) * 1.25) / 2.0;
                        let caption_px = context_font_size(cr, TYPE_CAPTION);
                        let line_h = (caption_px * 1.25).ceil();
                        // Two lines where the banner has room for them.
                        let room = ((bh - 12.0) / line_h).floor().max(1.0);
                        let lines = f64::from(wrapped_line_count(message, caption_px, mw, pango::Weight::Normal)).min(room);
                        let caption_y = banner_y + (bh - lines * line_h) / 2.0;
                        text(cr, "!", bx + 16.0, label_y, 30.0, TYPE_LABEL, style.error);
                        wrapped_text_lines(cr, message, bx + 54.0, caption_y, mw, caption_px, style.error, lines as i32);
                    }
                }
            }
            // The password field takes real keyboard focus and types through
            // the system keyboard (wvkbd) like every other text field in the
            // shell, instead of drawing its own keys here -- see
            // openspec/changes/the-handheld-configures-wifi-from-settings.
            // `lay.buttons` keeps Cancel/Connect above whatever height of
            // the screen the raised keyboard currently reserves
            // (`view.keyboard_inset`), matching `wifi_ui::target`'s own hit
            // region exactly.
            let (cancel, connect) = lay.buttons;
            service_card(cr, theme, "controls", cancel.0, cancel.1, cancel.2, cancel.3, false);
            service_card(cr, theme, "controls", connect.0, connect.1, connect.2, connect.3, true);
            let (cancel_dx, connect_dx) = lay.button_text_dx;
            text(cr, "Cancel", cancel.0 + cancel_dx, cancel.1 + lay.button_text_dy, cancel.2 - cancel_dx, TYPE_LABEL, style.muted);
            text(cr, "Connect", connect.0 + connect_dx, connect.1 + lay.button_text_dy, connect.2 - connect_dx, TYPE_LABEL, style.accent);
        }
        WifiPage::Connecting => {
            let (x, y, w, h) = lay.connecting_card;
            service_card(cr, theme, "controls", x, y, w, h, true);
            text(cr, "Connecting…", x + 18.0, y + lay.connecting_title_dy, w - 36.0, TYPE_BODY, style.text);
            text_wrapped(
                cr,
                crate::wifi_ui::CONNECTING_SUB,
                x + 18.0,
                y + lay.connecting_sub_dy,
                w - 36.0,
                TYPE_CAPTION,
                style.muted,
            );
            let (cx, cy, cw, ch) = lay.connecting_cancel;
            service_card(cr, theme, "controls", cx, cy, cw, ch, false);
            let (dx, dy) = lay.connecting_cancel_text;
            text(cr, "Cancel connection", cx + dx, cy + dy, cw - dx, TYPE_LABEL, style.accent);
        }
        WifiPage::ForgetConfirm => {
            let (x, y, w, h) = lay.forget_card;
            service_card(cr, theme, "controls", x, y, w, h, true);
            text_wrapped(cr, crate::wifi_ui::FORGET_TITLE, x + 18.0, y + lay.forget_title_dy, w - 36.0, TYPE_BODY, style.text);
            text_wrapped(cr, crate::wifi_ui::FORGET_SUB, x + 18.0, y + lay.forget_sub_dy, w - 36.0, TYPE_CAPTION, style.muted);
            let (kx, ky, kw, kh) = lay.forget_keep;
            let (fx, fy, fw, fh) = lay.forget_confirm;
            service_card(cr, theme, "controls", kx, ky, kw, kh, false);
            service_card(cr, theme, "controls", fx, fy, fw, fh, true);
            let (keep_dx, forget_dx) = lay.forget_text_dx;
            text(cr, "Keep", kx + keep_dx, ky + lay.forget_text_dy, kw - keep_dx, TYPE_LABEL, style.muted);
            text(cr, "Forget", fx + forget_dx, fy + lay.forget_text_dy, fw - forget_dx, TYPE_LABEL, style.error);
        }
    }
    // The Entry page's rejected-password case already got its own elevated
    // banner above (finding P0-3); do not also repeat it as a second,
    // lower-emphasis line down here.
    let already_shown = view.page == WifiPage::Entry && entry_error_message(view).is_some();
    if !already_shown {
        if let Some(message) = &view.message {
            // Anchored to the (possibly keyboard-raised) button row on the
            // Entry page, rather than a fixed offset, so this never ends up
            // beneath the system keyboard.
            let at = match view.page {
                WifiPage::List => Some(lay.list_message),
                WifiPage::Entry => Some(lay.entry_message),
                WifiPage::Connecting | WifiPage::ForgetConfirm => Some(lay.status_message),
                WifiPage::Closed => None,
            };
            let color = if view.pending
                || message.starts_with("Saved")
                || message.starts_with("Network forgotten")
            {
                style.muted
            } else {
                style.error
            };
            if let Some((mx, my)) = at {
                text(cr, message, mx, my, lay.message_w, TYPE_CAPTION, color);
            }
        }
    }
    let _ = cr.restore();
}

/// The Wi-Fi layout for a `width`x`height` surface and the view's keyboard
/// inset.
fn wifi_layout(view: &WifiPublic, width: f64, height: f64) -> crate::wifi_ui::Layout {
    crate::wifi_ui::layout_for(width as u32, height as u32, view.keyboard_inset)
}

/// Where the Settings screen's own content (rows, Power section, and any
/// confirm dialog or message) naturally ends, feeding `content_sized_panel_h`
/// (finding P0-2) instead of always filling the screen.
pub fn settings_content_bottom(services: Option<&ServiceView>) -> f64 {
    // "Loading settings" or the error, on one Body line under the header.
    let empty_bottom = settings_first_y() + vision_line(TYPE_BODY) + SPACE_CARD;
    let Some(view) = services else {
        return empty_bottom;
    };
    if view.settings.is_none() {
        return empty_bottom;
    }
    let mut bottom = settings_layout_for(view.key_backlight.is_some(), view.modem.is_some()).poweroff_bottom;
    if view.confirmation.is_some() {
        bottom = settings_confirm_layout(bottom).bottom;
    }
    if view.message.is_some() {
        bottom += 14.0 + vision_line(TYPE_CAPTION) + SPACE_IN_ROW;
    }
    bottom + SPACE_GROUP
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
            let lay = crate::wifi_ui::layout(false, 0.0);
            lay.list_view.1 + rows as f64 * lay.row_pitch + 24.0
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
            let lay = crate::theme_ui::chooser_layout(568, 1232);
            lay.message_y + (TYPE_CAPTION * crate::layout_text_scale() * crate::layout_theme_font() * 1.25).ceil() + 16.0
        }
        // Only the portrait sheet is content-sized (`settings_panel_h`), and
        // there the Vision cards stack whatever the exact width.
        ThemePage::Vision => vision_layout(0.0, view.vision.text_scale_value()).bottom,
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
    wide: bool,
) -> f64 {
    let min_panel_h = 420.0 * content_scale;
    if wide {
        // The landscape panel's Settings controls, Wi-Fi pages and theme
        // chooser all lay out against the whole short panel.
        return available_h;
    }
    // The Cellular and Location pages are fixed layouts over the whole panel.
    if services.is_some_and(|s| s.modem_page.is_some() || s.info_page.is_some()) {
        return available_h;
    }
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
        Route::Shade => crate::service_ui::shade_panel_height(height),
        // Fills nearly the whole screen from its own small top inset
        // (`navigation::panel_top`), not the old ~19%-of-height band --
        // `docs/design/app-drawer-review.md` §2: "filling the screen from
        // the top inset, with no black band above it."
        Route::Drawer => h - navigation::panel_top(height),
        Route::Settings => settings_panel_h(h, chooser, services, crate::density_scale(width, height), crate::settings_wide(width, height)),
        Route::Power => power_panel_h(h, services),
        Route::Help | Route::Hide => h,
    }
}

pub const POWER_REBOOT_Y: f64 = 132.0;
pub const POWER_OFF_Y: f64 = 218.0;
pub const POWER_CANCEL_Y: f64 = 304.0;
pub const POWER_CONFIRM_Y: f64 = 432.0;
pub const POWER_BUTTON_H: f64 = 68.0;
/// The gap between the confirmation's Cancel and action buttons.
pub const POWER_CONFIRM_GAP: f64 = 16.0;
/// The confirmation's buttons take taps this far beyond their painted
/// edges: on the board, real Confirm taps landed a few pixels below the
/// bar (2026-10-14), and nothing else sits below it on the sheet.
pub const POWER_CONFIRM_SLOP: f64 = 30.0;

/// The confirmation's action button names what it does.
pub fn power_confirm_label(action: crate::service_data::PowerAction) -> &'static str {
    match action {
        crate::service_data::PowerAction::Reboot => "Restart",
        crate::service_data::PowerAction::Poweroff => "Power off",
    }
}

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
    /// The drawer sheet (vision backdrop and themed background brush) from
    /// `panel_top` down, painted once per theme and size. A gradient brush
    /// takes pixman's generic path, which cost about 30% of the client's CPU
    /// when it was refilled under every scroll frame.
    sheet: Option<(DrawerSheetKey, ImageSurface)>,
    /// Bumped on every real rebuild -- test-only observability, the same
    /// role `IconCache::decode_count`/`RendererCache::rebuild_count`
    /// already play for their own caches.
    rebuilds: u64,
}

#[derive(Clone, PartialEq)]
struct DrawerSheetKey {
    theme_generation: Option<String>,
    vision: bool,
    width: u32,
    height: u32,
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
            let columns = navigation::columns_for_width(width).max(1);
            let rows = content.apps.len().div_ceil(columns).max(1);
            let content_height = (rows as f64 * navigation::drawer_metrics().row_height).max(1.0);
            let surface = ImageSurface::create(
                Format::ARgb32,
                (width.max(1)) as i32,
                content_height.ceil() as i32,
            )
            .unwrap_or_else(|_| {
                ImageSurface::create(Format::ARgb32, 1, 1).expect("1x1 fallback surface")
            });
            if let Ok(cr) = Context::new(&surface) {
                attach_theme_metrics(&cr, theme);
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

    /// The cached sheet for `theme` at this size, and the whole-pixel row it
    /// starts on; `None` if the surface cannot be allocated.
    fn ensure_sheet(&mut self, theme: Option<&AppearanceSnapshot>, width: u32, height: u32) -> Option<(&ImageSurface, f64)> {
        let key = DrawerSheetKey {
            theme_generation: theme.map(|snapshot| snapshot.generation.clone()),
            vision: vision_adjusted(theme),
            width,
            height,
        };
        let top = panel_top(height).floor();
        if self.sheet.as_ref().is_none_or(|(cached, _)| *cached != key) {
            self.sheet = None;
            let rows = (f64::from(height) - top).max(1.0).ceil() as i32;
            let surface = ImageSurface::create(Format::ARgb32, width.max(1) as i32, rows).ok()?;
            {
                let cr = Context::new(&surface).ok()?;
                cr.translate(0.0, -top);
                paint_drawer_sheet(&cr, theme, width, height);
            }
            surface.flush();
            self.sheet = Some((key, surface));
        }
        self.sheet.as_ref().map(|(_, surface)| (surface, top))
    }

    /// Drops the cached sheet, for an appearance change that keeps its
    /// generation name.
    fn forget_sheet(&mut self) {
        self.sheet = None;
    }
}

/// Copies a cached sheet onto its rows of a cleared canvas.
fn copy_drawer_sheet(cr: &Context, sheet: &ImageSurface, top: f64) {
    let _ = cr.save();
    cr.set_operator(Operator::Source);
    cr.rectangle(0.0, top, f64::from(sheet.width()), f64::from(sheet.height()));
    if cr.set_source_surface(sheet, 0.0, top).is_ok() {
        let _ = cr.fill();
    }
    let _ = cr.restore();
}

/// The drawer's rounded sheet below `panel_top`: an opaque palette backdrop
/// when a vision choice is active, then the themed background brush (or the
/// palette background when the theme has none).
fn paint_drawer_sheet(cr: &Context, theme: Option<&AppearanceSnapshot>, width: u32, height: u32) {
    let w = f64::from(width);
    let h = f64::from(height);
    let panel_y = panel_top(height);
    let _ = cr.save();
    // Rounded only when the sheet stops short of the top edge; at the edge
    // its corners would show the app underneath.
    rounded_top(cr, 0.0, panel_y, w, h - panel_y, if panel_y > 0.0 { 28.0 } else { 0.0 });
    cr.clip();
    if vision_adjusted(theme) {
        // A translucent sheet lets the wallpaper fight larger text; a vision
        // choice puts the drawer on a solid palette background first.
        color(cr, palette_rgb_or(theme, "background", 0x1e1e2e), 1.0);
        let _ = cr.paint();
    }
    if !theme_brush(theme, "launcher", "background")
        .is_some_and(|brush| fill_brush(cr, brush, 0.0, panel_y, w, h - panel_y))
    {
        color(cr, palette_rgb_or(theme, "background", 0x1e1e2e), 1.0);
        let _ = cr.paint();
    }
    let _ = cr.restore();
}

/// One tile's worth of content: an icon (no plate/box around it -- the
/// redesign's own "just the icon, with its label below, on the sheet
/// surface") and a label of up to two lines. Icon fallback (no
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
    let metrics = navigation::drawer_metrics();
    let icon_size = metrics.icon;
    let icon_card = f64::from(icon_size);
    let icon_x = x + (cell_w - icon_card) / 2.0;
    let icon_y = y + 8.0;
    let mut painted = app
        .icon
        .as_deref()
        .is_some_and(|icon| icons.paint(cr, icon, icon_size, icon_x, icon_y));
    // Board finding (2026-09-27): `Icon=mpv` (Video) and `Icon=foot`
    // (Terminal) name real applications the bundled Yaru-based theme does
    // not cover at all -- not a harness gap, a genuine resolution miss.
    // Before falling all the way back to a plain letter circle, a
    // terminal emulator or an app that runs inside one
    // (`catalog::terminal_like`) gets one more try against a generic
    // icon name real desktop themes do cover.
    if !painted && terminal_like(&app.path) {
        painted = icons.paint(cr, "utilities-terminal", icon_size, icon_x, icon_y);
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
        let radius = icon_card / 2.0;
        let initial_size = (24.0 * icon_card / 64.0).round();
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
            (icon_x, icon_y + (icon_card - initial_size) / 2.0),
            icon_card,
            initial_size,
            style.text,
        );
    }
    let label_y = icon_y + icon_card + visual_inset(cr, 6.0);
    // A name wraps onto a second line rather than ellipsizing.
    icons.paint_label_lines(
        cr,
        &app.name,
        (x + 2.0, label_y),
        (cell_w - 4.0).max(1.0),
        theme_font_size(theme, "caption", DRAWER_LABEL_SIZE, DRAWER_LABEL_SIZE, DRAWER_LABEL_SIZE * 1.25),
        brush_rgb(theme, "menu", "text", style.text),
        2,
    );
}

fn paint_help(
    cr: &Context,
    theme: Option<&AppearanceSnapshot>,
    width: u32,
    height: u32,
    services: Option<&ServiceView>,
) {
    let aid = services.is_some_and(|s| s.navigation_aid);
    let style = visual_style(theme, "controls");
    let scroll = services.map_or(0.0, |s| s.help_scroll);
    let lay = crate::help::layout(width, height, aid);
    let w = lay.column_w;
    let _ = cr.save();
    cr.translate(lay.x, -scroll);
    cr.scale(lay.scale, lay.scale);
    // Text is drawn at the layout's own sizes (the roles at the current
    // step), so every wrapped line lands where `help::layout` measured it.
    wrapped_text(
        cr,
        if aid { "Navigation buttons" } else { "Help" },
        lay.intro.0,
        lay.heading_y,
        w,
        lay.title_px,
        style.text,
        pango::Weight::Bold,
    );
    let (ix, iy) = lay.intro;
    wrapped_text(cr, crate::help::INTRO, ix, iy, w, lay.caption_px, style.muted, pango::Weight::Normal);
    for (name, &(gx, gy)) in crate::help::GROUPS.iter().zip(&lay.group_headings) {
        wrapped_text(cr, name, gx, gy, w, lay.label_px, style.accent, pango::Weight::Bold);
    }
    for ((title, detail), ((tx, ty), (dx, dy))) in crate::help::GUIDE.iter().zip(&lay.guide) {
        wrapped_text(cr, title, *tx, *ty, w, lay.label_px, style.text, pango::Weight::Medium);
        wrapped_text(cr, detail, *dx, *dy, w, lay.caption_px, style.muted, pango::Weight::Normal);
    }
    let buttons = crate::help::buttons(aid).iter().zip(&lay.buttons).zip(&lay.button_text);
    for (((action, label, detail), &(x, y, bw, bh)), &(label_y, detail_y)) in buttons {
        service_card(cr, theme, "controls", x, y, bw, bh, false);
        let pending =
            *action == crate::help::Action::Home && services.is_some_and(|s| s.help_home_pending);
        let inner = bw - 48.0;
        let label = if pending { "Opening Home…" } else { label };
        wrapped_text(cr, label, x + 24.0, label_y, inner, lay.label_px, style.accent, pango::Weight::Normal);
        wrapped_text(cr, detail, x + 24.0, detail_y, inner, lay.caption_px, style.muted, pango::Weight::Normal);
    }
    if let Some(message) = services.and_then(|s| s.message.as_deref()) {
        let (mx, my) = lay.message;
        wrapped_text(cr, message, mx, my, w, lay.caption_px, style.error, pango::Weight::Normal);
    }
    let _ = cr.restore();
}

/// Renders the drawer's slim top handle, its pill-shaped search field, and
/// a focused field caret. The normal keyboard is a separate wvkbd surface. Drawn
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
    color(cr, style.text, HANDLE_ALPHA);
    let _ = cr.fill();

    // Help is the same themed control card as the search field, at its
    // height, so the two read as one row of controls.
    let (hx, hy, hw, hh) = navigation::help_rect(width, height);
    service_card_interaction(cr, theme, "launcher", hx, hy, hw, hh, false, false, false);
    let help_y = hy + (hh - context_font_size(cr, TYPE_LABEL) * 1.2) / 2.0;
    let help_w = text_advance(cr, "Help", TYPE_LABEL, pango::Weight::Normal).min(hw);
    text(cr, "Help", hx + (hw - help_w) / 2.0, help_y, hw, TYPE_LABEL, style.text);
    let (sx, sy, sw, sh) = search_field_rect(width, height);
    rounded(cr, sx, sy, sw, sh, sh / 2.0);
    let _ = cr.save();
    cr.clip();
    if !theme_brush(theme, "launcher", "search")
        .is_some_and(|brush| fill_brush(cr, brush, sx, sy, sw, sh))
    {
        color(cr, palette_rgb_or(theme, "surface2", 0x2a2f3a), 1.0);
        let _ = cr.paint();
    }
    control_overlay(cr, style.text, sx, sy, sw);
    let _ = cr.restore();

    service_card_interaction(cr, theme, "launcher", sx, sy, sw, sh, false, false, search.focused);

    let label = if search.query.is_empty() {
        "Search apps"
    } else {
        search.query.as_str()
    };
    let label_color = if search.focused {
        brush_rgb(theme, "controls", "focus-color", style.text)
    } else if search.query.is_empty() {
        style.muted
    } else {
        style.text
    };
    // The glyph grows with the text step, inside the pill's height.
    let glyph_size = (24.0 * crate::layout_text_scale().max(1.0)).round().min(sh - 16.0);
    glyph::paint(cr, Glyph::Search, sx + 15.0, sy + (sh - glyph_size) / 2.0, glyph_size, label_color, 0.8);
    let tx = sx + 30.0 + glyph_size;
    let available = sw - (tx - sx) - 22.0;
    // A narrow pill at a large step shrinks the line until the placeholder
    // fits rather than ellipsizing it, never below the Label role's 100%
    // size. A query keeps that size and scrolls under the caret.
    let full = context_font_size(cr, TYPE_LABEL);
    let advance = text_advance_resolved(cr, "Search apps", full, pango::Weight::Normal);
    let room = available * 0.96;
    let label_size = if advance > room { (full * room / advance).max(TYPE_LABEL) } else { full };
    let ty = sy + (sh - label_size * 1.2) / 2.0;
    if !search.focused {
        text_weight_resolved(cr, label, tx, ty, available, label_size, label_color, pango::Weight::Normal);
        return;
    }
    // The focus brush/outline above belongs to the theme; keep the caret steady.
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(label_size * f64::from(pango::SCALE));
    layout.set_font_description(Some(&font));
    layout.set_single_paragraph_mode(true);
    layout.set_text(&search.query);
    let (caret, _) = layout.cursor_pos(search.query.len() as i32);
    let caret_x = f64::from(caret.x()) / f64::from(pango::SCALE);
    let shift = (caret_x - available + 4.0).max(0.0);
    let _ = cr.save();
    cr.rectangle(tx - 2.0, sy + 8.0, available + 2.0, sh - 16.0);
    cr.clip();
    if search.query.is_empty() {
        text_weight_resolved(cr, label, tx, ty, available, label_size, label_color, pango::Weight::Normal);
    } else {
        color(cr, style.text, 1.0);
        cr.move_to(tx - shift, ty);
        pangocairo::functions::show_layout(cr, &layout);
    }
    color(cr, style.accent, 1.0);
    cr.rectangle(tx + caret_x - shift - 1.0, sy + 12.0, 2.0, sh - 24.0);
    let _ = cr.fill();
    let _ = cr.restore();
}

/// The Drawer's whole paint: opaque themed sheet with rounded top corners,
/// the handle/search chrome, and the (cached) grid, scrolled into view by
/// blitting one slice of `DrawerGridCache` rather than repainting every
/// tile -- see that struct's own doc.
#[allow(clippy::too_many_arguments)]
/// The Shade header on the type roles: the Title shrinks only as far as it
/// must to sit beside the Settings link, and the hint, count and "Dismiss
/// all" lines stack by their drawn height, so nothing overlaps or
/// ellipsizes. Each link stays inside its `service_ui::shade_link_w` band.
/// The Shade's empty-state tile: one Caption line, or the preview's source
/// (Label) and summary (Body), inside `SHADE_TILE_INSET` above and below.
const SHADE_TILE_INSET: f64 = 11.0;

fn shade_preview_tile_h(preview: bool) -> f64 {
    let lines = if preview { vision_line(TYPE_LABEL) + vision_line(TYPE_BODY) } else { vision_line(TYPE_CAPTION) };
    (lines + 2.0 * SHADE_TILE_INSET).ceil().max(72.0)
}

/// A design size for `value` that fits `room` at `weight`: `design` itself
/// when it fits, otherwise shrunk in proportion rather than cut off.
fn fitted_size(cr: &Context, value: &str, design: f64, room: f64, weight: pango::Weight) -> f64 {
    let advance = text_advance(cr, value, design, weight);
    if advance > room * 0.96 { design * room * 0.96 / advance } else { design }
}

/// The wide Shade's left column above its sliders: the time with the date
/// under it and "Settings ›" beside it, the status line, and the quick tiles
/// (`service_ui::shade_tiles`, which the hit-tests read too).
fn paint_shade_wide_controls(
    cr: &Context,
    theme: Option<&AppearanceSnapshot>,
    style: VisualStyle,
    services: Option<&ServiceView>,
    panel_y: f64,
    hw: f64,
) {
    use crate::home_widgets::clock;
    use crate::service_ui::{
        shade_link_w, shade_tile_rect, shade_tiles, ShadeTile, SHADE_SETTINGS_BOTTOM, SHADE_WIDE_STATUS_TOP,
        SHADE_WIDE_TILE_TOP,
    };
    let line = |size: f64| context_font_size(cr, size) * 1.25;
    let link_w = shade_link_w(hw);
    let settings_size = fitted_size(cr, "Settings ›", TYPE_LABEL, link_w - 24.0, pango::Weight::Normal);
    let settings_w = text_advance(cr, "Settings ›", settings_size, pango::Weight::Normal) + 2.0;
    text(cr, "Settings ›", hw - 24.0 - settings_w, panel_y + 20.0, settings_w, settings_size, style.text);

    // The time, with the date under it while both fit the header band at
    // full size; at a larger text step the date joins the status line.
    let now = clock::now_local();
    let date = now.map(clock::format_date);
    let date_h = line(TYPE_CAPTION);
    let time_full = context_font_size(cr, 52.0);
    let stacked = 6.0 + time_full * 1.25 + date_h <= SHADE_SETTINGS_BOTTOM - 4.0;
    if let Some(now) = now {
        let room = hw - 28.0 - link_w;
        let time = clock::format_time(now);
        let mut time_px = if stacked { time_full } else { time_full.min((SHADE_SETTINGS_BOTTOM - 16.0) / 1.25) };
        let advance = text_advance_resolved(cr, &time, time_px, pango::Weight::Bold);
        if advance > room * 0.96 {
            time_px *= room * 0.96 / advance;
        }
        let time_y = panel_y + 6.0;
        text_weight_resolved(cr, &time, 28.0, time_y, room, time_px, style.text, pango::Weight::Bold);
        if stacked {
            text(cr, date.as_deref().unwrap_or(""), 28.0, time_y + time_px * 1.25, hw - 56.0, TYPE_CAPTION, style.muted);
        }
    }

    // The status line: the date when it did not fit above, then the
    // battery, then the modem glyphs while they are on. Wi-Fi's state is
    // its tile's, so it is not repeated here.
    let mut status = Vec::new();
    if !stacked {
        status.extend(date);
    }
    if let Some(battery) = services
        .filter(|v| v.battery != crate::home_widgets::battery::BatteryState::Absent)
        .map(|v| crate::home_widgets::battery::format(&v.battery))
    {
        status.push(battery);
    }
    let modem = services.and_then(|v| v.modem.as_ref());
    let signal = modem.and_then(|m| m.cellular_indicator());
    let location = modem.and_then(|m| m.location_indicator());
    // The line keeps to its band (`SHADE_WIDE_STATUS_TOP..SHADE_WIDE_TILE_TOP`).
    let band = SHADE_WIDE_TILE_TOP - SHADE_WIDE_STATUS_TOP - 4.0;
    let status_design = TYPE_CAPTION.min(TYPE_CAPTION * band / line(TYPE_CAPTION));
    let icon_size = line(status_design).ceil();
    let icons_w = f64::from(u8::from(signal.is_some()) + u8::from(location.is_some())) * (icon_size + 8.0);
    let status_y = panel_y + SHADE_WIDE_STATUS_TOP;
    let status_text = status.join(" · ");
    let status_room = hw - 56.0 - icons_w;
    let status_size = fitted_size(cr, &status_text, status_design, status_room, pango::Weight::Normal);
    text(cr, &status_text, 28.0, status_y + (icon_size - line(status_size)) / 2.0, status_room, status_size, style.muted);
    let mut icon_x = hw - 28.0;
    if let Some(indicator) = location {
        icon_x -= icon_size;
        glyph::paint_location(cr, indicator == crate::modem::LocationIndicator::Fix, icon_x, status_y, icon_size, style.text);
        icon_x -= 8.0;
    }
    if let Some(indicator) = signal {
        icon_x -= icon_size;
        let (lit, none) = match indicator {
            crate::modem::CellularIndicator::Bars(n) => (n, false),
            crate::modem::CellularIndicator::NoService => (0, true),
        };
        glyph::paint_signal(cr, lit, none, icon_x, status_y, icon_size, style.text);
    }

    // The tiles: an icon and label over a state line. A tile that is on
    // takes the accent for its state; an unavailable one is muted.
    let Some(view) = services else { return };
    let settings = view.settings.as_ref();
    for (index, tile) in shade_tiles(view).into_iter().enumerate() {
        let (x, y, w, h) = shade_tile_rect(index, hw);
        let y = panel_y + y;
        let (icon, label, state, on, available) = match tile {
            ShadeTile::Wifi => {
                let network = settings.map(|s| &s.network);
                // "Connected" or "Not connected"; with no link state, where
                // the tile leads.
                let state = match network {
                    None => "Loading".into(),
                    Some(n) if n.value.is_none() => "Choose network".into(),
                    Some(n) => control_text(n),
                };
                let on = network.is_some_and(|n| matches!(&n.value, Some(ControlValue::Text(v)) if v == "link-up"));
                (Glyph::Wifi, "Wi-Fi", state, on, true)
            }
            ShadeTile::Keyboard => {
                let available = settings.is_some_and(|s| s.keyboard.state == ControlState::Action);
                (Glyph::Keyboard, "Keyboard", if available { "Show or hide" } else { "Unavailable" }.to_string(), false, available)
            }
            ShadeTile::Location => {
                let state = match view.modem.as_ref().and_then(|m| m.location_indicator()) {
                    Some(crate::modem::LocationIndicator::Fix) => "Fix",
                    Some(crate::modem::LocationIndicator::Searching) => "Searching",
                    None => "Off",
                };
                (Glyph::Location, "Location", state.to_string(), state != "Off", true)
            }
            ShadeTile::Cellular => {
                let on = view.modem.as_ref().is_some_and(|m| m.cellular);
                (Glyph::Signal, "Cellular", if on { "On" } else { "Off" }.to_string(), on, true)
            }
        };
        paint_card(cr, theme, "controls", CardJob::Control, x, y, w, h);
        let ink = if available { style.text } else { style.muted };
        // Both lines shrink together when the capped tile cannot hold them.
        let label_h = vision_line(TYPE_LABEL) / 1.25 * 1.2;
        let state_h = vision_line(TYPE_CAPTION) / 1.25 * 1.2;
        let k = ((h - 16.0) / (label_h + state_h)).min(1.0);
        let label_y = y + (h - (label_h + state_h) * k) / 2.0;
        let text_x = paint_line_glyph(cr, icon, x + 18.0, label_y, TYPE_LABEL * k, ink);
        themed_role_fit(cr, theme, "body", label, text_x, label_y, x + w - 14.0 - text_x, TYPE_LABEL * k, ink, pango::Weight::Medium);
        let state_ink = if on { style.accent } else if available { style.muted } else { ink };
        themed_role_fit(cr, theme, "caption", &state, x + 18.0, label_y + label_h * k, w - 32.0, TYPE_CAPTION * k, state_ink, pango::Weight::Normal);
    }
}

/// The wide Shade's list column heading: "Notifications" and its count, with
/// "Dismiss all" at the right in the same `0..SHADE_SETTINGS_BOTTOM` band
/// `panel_intent` tests.
fn paint_shade_list_heading(
    cr: &Context,
    style: VisualStyle,
    panel_y: f64,
    shade: &crate::service_ui::ShadeLayout,
    count: usize,
) {
    use crate::service_ui::{shade_link_w, SHADE_SETTINGS_BOTTOM};
    let x = shade.list_x;
    let w = shade.list_w;
    let link_w = shade_link_w(w);
    let room = w - 28.0 - link_w;
    let title_y = panel_y + 12.0;
    let label = if count == 1 { "1 notification".to_string() } else { format!("{count} notifications") };
    // The Title and the count line shrink together to keep to the band.
    let line = |size: f64| context_font_size(cr, size) * 1.25;
    let lines_h = line(TYPE_TITLE) + if count > 0 { line(TYPE_CAPTION) } else { 0.0 };
    let k = ((SHADE_SETTINGS_BOTTOM - 16.0) / lines_h).min(1.0);
    let title = fitted_size(cr, "Notifications", TYPE_TITLE * k, room, pango::Weight::Bold);
    heading(cr, "Notifications", x + 28.0, title_y, room, title, style.text);
    if count > 0 {
        let title_h = line(TYPE_TITLE * k);
        let size = fitted_size(cr, &label, TYPE_CAPTION * k, room, pango::Weight::Normal);
        text(cr, &label, x + 28.0, title_y + title_h, room, size, style.muted);
        let dismiss = fitted_size(cr, "Dismiss all", TYPE_LABEL, link_w - 24.0, pango::Weight::Normal);
        // The Shade's one primary action takes the accent (design.md §10).
        let dismiss_w = text_advance(cr, "Dismiss all", dismiss, pango::Weight::Normal) + 2.0;
        text(cr, "Dismiss all", x + w - 24.0 - dismiss_w, title_y + 8.0, dismiss_w, dismiss, style.accent);
    }
}

fn paint_shade_header(
    cr: &Context,
    style: VisualStyle,
    services: Option<&ServiceView>,
    panel_y: f64,
    hw: f64,
    count: usize,
) {
    use crate::service_ui::{shade_link_w, SHADE_DISMISS_BOTTOM, SHADE_SETTINGS_BOTTOM};
    let scale = crate::layout_text_scale();
    let line = |size: f64| context_font_size(cr, size) * 1.25;
    // Two lines that share a row shrink together, keeping their ratio, until
    // both fit; neither goes below the Label floor.
    let share = |left: (&str, f64, pango::Weight), right: (&str, f64), room: f64, right_room: f64| {
        let floor = TYPE_LABEL / scale;
        let left_adv = text_advance(cr, left.0, left.1, left.2);
        let right_adv = text_advance(cr, right.0, right.1, pango::Weight::Normal);
        let k = (room * 0.96 / (left_adv + right_adv)).min(right_room * 0.96 / right_adv).min(1.0);
        let right_size = (right.1 * k).max(floor);
        let right_w = text_advance(cr, right.0, right_size, pango::Weight::Normal) + 2.0;
        let left_room = room - right_w;
        let left_size = if left_adv * (left.1 * k) / left.1 > left_room * 0.96 {
            left.1 * left_room * 0.96 / left_adv
        } else {
            left.1 * k
        };
        (left_size.max(floor), right_size, right_w)
    };
    let link_room = shade_link_w(hw) - 24.0;
    let row_room = hw - 28.0 - 24.0 - 16.0;
    let (title_size, settings_size, settings_w) = share(
        ("Notifications", TYPE_TITLE, pango::Weight::Bold), ("Settings ›", TYPE_LABEL), row_room, link_room,
    );
    let title_y = panel_y + 16.0;
    let title_h = line(title_size);
    heading(cr, "Notifications", 28.0, title_y, row_room - settings_w, title_size, style.text);
    let settings_y = title_y + (title_h - line(settings_size)) / 2.0;
    text(cr, "Settings ›", hw - 24.0 - settings_w, settings_y, settings_w, settings_size, style.text);

    // The rows under the Title keep their ratio to it: when a narrow
    // column shrinks the Title, they shrink with it (to the Label floor).
    let header_k = title_size / TYPE_TITLE;
    let label = (TYPE_LABEL * header_k).max(TYPE_LABEL / scale).min(TYPE_LABEL);
    let caption = (TYPE_CAPTION * header_k).max(TYPE_CAPTION / scale).min(TYPE_CAPTION);
    let count_label = if count == 1 { "1 notification".to_string() } else { format!("{count} notifications") };
    let (count_size, dismiss_size, dismiss_w) = if count > 0 {
        share((&count_label, label, pango::Weight::Normal), ("Dismiss all", label), row_room, link_room)
    } else {
        let (size, _, _) = share((&count_label, label, pango::Weight::Normal), ("", label), hw - 56.0, link_room);
        (size, label, 0.0)
    };
    let count_h = line(count_size).max(line(dismiss_size));

    // The hint and battery line, while it fits between the Title and the
    // count row inside the "Dismiss all" band; otherwise it is left out.
    let hint_y = title_y + title_h + 2.0;
    let battery = services
        .filter(|view| view.battery != crate::home_widgets::battery::BatteryState::Absent)
        .map(|view| crate::home_widgets::battery::format(&view.battery));
    let hint = "Swipe up above the list to close";
    let fit = |value: &str, size: f64, room: f64| {
        let advance = text_advance(cr, value, size, pango::Weight::Normal);
        let fitted = if advance > room * 0.96 { size * room * 0.96 / advance } else { size };
        fitted.max(TYPE_CAPTION / scale)
    };
    let battery_size = battery.as_deref().map_or(caption, |label| fit(label, caption, (hw - 56.0) * 0.5));
    let battery_w = battery.as_deref().map_or(0.0, |label| text_advance(cr, label, battery_size, pango::Weight::Normal) + 2.0);
    // The modem's signal and location glyphs sit left of the battery text,
    // only while Cellular or Location is on (`ServiceView::modem`).
    let modem = services.and_then(|view| view.modem.as_ref());
    let signal = modem.and_then(|m| m.cellular_indicator());
    let location = modem.and_then(|m| m.location_indicator());
    let icon_size = line(caption).ceil();
    let icons_w = f64::from(u8::from(signal.is_some()) + u8::from(location.is_some())) * (icon_size + 8.0);
    let right_w = (if battery.is_some() { battery_w + 12.0 } else { 0.0 }) + if icons_w > 0.0 { icons_w + 4.0 } else { 0.0 };
    let hint_room = hw - 56.0 - right_w;
    let hint_size = fit(hint, caption, hint_room);
    // The hint is left out rather than cut off; the battery stays.
    let hint_whole = text_advance(cr, hint, hint_size, pango::Weight::Normal) <= hint_room;
    let hint_h = line(hint_size).max(line(battery_size));
    let band_bottom = SHADE_DISMISS_BOTTOM - 4.0;
    let count_top = SHADE_SETTINGS_BOTTOM + 4.0;
    let count_y = if (hint_y + hint_h + 2.0).max(count_top) + count_h <= band_bottom {
        if let Some(label) = &battery {
            text(cr, label, hw - 24.0 - battery_w, hint_y, battery_w, battery_size, style.text);
        }
        let mut icon_x = hw - 24.0 - if battery.is_some() { battery_w + 12.0 } else { 0.0 };
        let icon_y = hint_y + (hint_h - icon_size) / 2.0;
        if let Some(indicator) = location {
            icon_x -= icon_size;
            glyph::paint_location(cr, indicator == crate::modem::LocationIndicator::Fix, icon_x, icon_y, icon_size, style.text);
            icon_x -= 8.0;
        }
        if let Some(indicator) = signal {
            icon_x -= icon_size;
            let (lit, none) = match indicator {
                crate::modem::CellularIndicator::Bars(n) => (n, false),
                crate::modem::CellularIndicator::NoService => (0, true),
            };
            glyph::paint_signal(cr, lit, none, icon_x, icon_y, icon_size, style.text);
        }
        if hint_whole {
            text(cr, hint, 28.0, hint_y, hint_room, hint_size, style.muted);
        }
        (hint_y + hint_h + 2.0).max(count_top)
    } else {
        (title_y + title_h + 2.0).max(count_top)
    };
    if count > 0 {
        let dismiss_y = count_y + (count_h - line(dismiss_size)) / 2.0;
        // The Shade's one primary action takes the accent (design.md §10).
        text(cr, "Dismiss all", hw - 24.0 - dismiss_w, dismiss_y, dismiss_w, dismiss_size, style.accent);
    }
    // The empty state says "No new notifications" already; a "0
    // notifications" line beside it would repeat it.
    if count > 0 {
        let count_room = hw - 56.0 - dismiss_w - 16.0;
        text(cr, &count_label, 28.0, count_y + (count_h - line(count_size)) / 2.0, count_room, count_size, style.muted);
    }
}

/// The Settings header (`settings_header`): the Title fits beside Done, the
/// Vision and Themes links get their own row, and "Device controls" sits
/// beneath them.
fn paint_settings_header(cr: &Context, theme: Option<&AppearanceSnapshot>, style: VisualStyle, w: f64) {
    let head = settings_header(w);
    let fit = |value: &str, size: f64, room: f64, weight| {
        let advance = text_advance(cr, value, size, weight);
        if advance > room * 0.96 { size * room * 0.96 / advance } else { size }
    };
    let title_room = head.done_x - 28.0 - 8.0;
    let title_size = fit("Settings", TYPE_TITLE, title_room, pango::Weight::Bold);
    heading(cr, "Settings", 28.0, 16.0, title_room, title_size, style.text);
    let line_mid = 16.0 + vision_line(TYPE_TITLE) / 2.0;
    let link = |label: &str, (x0, x1): (f64, f64), y_mid: f64| {
        let room = x1 - x0 - 24.0;
        let size = fit(label, TYPE_LABEL, room, pango::Weight::Normal);
        let advance = text_advance(cr, label, size, pango::Weight::Normal) + 2.0;
        text(cr, label, x1 - 24.0 - advance, y_mid - vision_line(size) / 2.0, advance, size, style.text);
    };
    link("Done", (head.done_x, w), line_mid);
    let links_mid = (head.links_y.0 + head.links_y.1) / 2.0;
    link("Vision ›", head.vision_x, links_mid);
    link("Themes ›", head.themes_x, links_mid);
    themed_role(cr, theme, "heading", "Device controls", 28.0, head.eyebrow_y, w - 56.0, TYPE_LABEL, style.muted, pango::Weight::Bold);
}

/// The theme chooser's and Vision page's Back and Close links, inside
/// `theme_ui::chooser_header_bands`; returns the header line's bottom.
/// The distance from a carousel card's name line to its status line,
/// matching `theme_ui::carousel_label_h`.
fn chooser_label_line(cr: &Context) -> f64 {
    (context_font_size(cr, TYPE_LABEL) * 1.25).ceil() + 2.0
}

fn paint_chooser_header(cr: &Context, style: VisualStyle, w: f64, h: f64) -> f64 {
    let lay = crate::theme_ui::chooser_layout(w as u32, h as u32);
    let (_, back_right, close_left) = crate::theme_ui::chooser_header_bands(w as u32, h as u32);
    let fit = |value: &str, size: f64, room: f64| {
        let advance = text_advance(cr, value, size, pango::Weight::Normal);
        if advance > room * 0.96 { size * room * 0.96 / advance } else { size }
    };
    let back_size = fit("‹ Settings", TYPE_LABEL, back_right - 28.0 - 8.0);
    text(cr, "‹ Settings", 28.0, lay.header_y, back_right - 28.0, back_size, style.text);
    let close_room = w - 24.0 - close_left - 8.0;
    let close_size = fit("Close", TYPE_LABEL, close_room);
    let close_w = text_advance(cr, "Close", close_size, pango::Weight::Normal) + 2.0;
    text(cr, "Close", w - 24.0 - close_w, lay.header_y, close_w, close_size, style.text);
    lay.header_y + vision_line(back_size.max(close_size))
}

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
    // `RendererCache::draw` always calls this at a fixed `progress: 1.0`
    // and does its own cheap post-bake row-shift for the live drag/settle
    // progress instead (see `scene`'s own doc); this translate only
    // matters for a direct caller (`draw_shm`/`export_png`, or a test)
    // that passes some other `progress` straight through.
    let hidden = 1.0 - progress.clamp(0.0, 1.0);
    cr.translate(0.0, hidden * (h - panel_y));

    let style = visual_style(theme, "launcher");
    // The scene cleared this area, so copying the cached sheet over it gives
    // the same pixels as painting it, provided the copy lands on whole pixels.
    let m = cr.matrix();
    let whole_pixels = m.xx() == 1.0 && m.yy() == 1.0 && m.xy() == 0.0 && m.yx() == 0.0
        && m.x0().fract() == 0.0 && m.y0().fract() == 0.0;
    match grid_cache.ensure_sheet(theme, width, height).filter(|_| whole_pixels) {
        Some((sheet, top)) => copy_drawer_sheet(cr, sheet, top),
        None => paint_drawer_sheet(cr, theme, width, height),
    }

    paint_drawer_chrome(cr, theme, width, height, search);

    let matched: Vec<usize> = filter_app_indices(apps, &search.query);
    let content = DrawerContent {
        apps: matched.iter().filter_map(|&i| apps.get(i)).collect(),
        search,
    };
    let row_start = list_top(height);
    let bottom = f64::from(search.viewport_height(height)) - GRID_BOTTOM_INSET;
    let (grid_surface, content_height) = grid_cache.ensure(&content, theme, width, height, icons);
    let _ = cr.save();
    cr.rectangle(0.0, row_start, w, (bottom - row_start).max(0.0));
    cr.clip();
    let max_scroll = (content_height - (bottom - row_start)).max(0.0);
    let clamped_scroll = scroll.clamp(0.0, max_scroll);
    // A whole-pixel offset with a nearest filter lets pixman copy rows; a
    // fractional scroll resampled the whole grid bilinearly every frame
    // (about 37% of the client's CPU during a drawer scroll).
    if cr
        .set_source_surface(grid_surface, 0.0, (row_start - clamped_scroll).round())
        .is_ok()
    {
        cr.source().set_filter(Filter::Fast);
        let _ = cr.paint();
    }
    let _ = cr.restore();

    if let Some(point) = cr.target().user_data(&HOVER_POINT).and_then(|p| cr.device_to_user(p.0, p.1).ok()) {
        if let Some(index) = navigation::tile_at(point, width, search.viewport_height(height), matched.len(), scroll) {
            let (x, y, tw, th) = tile_rect(width, height, index, scroll);
            let _ = cr.save();
            cr.rectangle(0.0, row_start, w, (bottom - row_start).max(0.0));
            cr.clip();
            let _ = cr.save();
            rounded(cr, x, y, tw, th, 16.0);
            cr.clip();
            overlay_brush(cr, theme_brush(theme, "controls", "hover-cursor-color"), x, y, tw, th,
                theme_number(theme, "controls", "hover-cursor-fill-alpha").unwrap_or(0.08).clamp(0.0, 1.0), style.accent);
            let _ = cr.restore();
            paint_control_border(cr, theme, "controls", "hover-cursor", (x, y, tw, th), CARD_RADIUS_CONTROL);
            let _ = cr.restore();
        }
    }
    // Typing from the base's keys: Enter launches the first match, so it
    // carries the hover cursor's outline.
    if search.from_keys && !search.query.is_empty() && !matched.is_empty() {
        let (x, y, tw, th) = tile_rect(width, height, 0, clamped_scroll);
        if y + th > row_start && y < bottom {
            let _ = cr.save();
            cr.rectangle(0.0, row_start, w, (bottom - row_start).max(0.0));
            cr.clip();
            paint_control_border(cr, theme, "controls", "hover-cursor", (x, y, tw, th), CARD_RADIUS_CONTROL);
            let _ = cr.restore();
        }
    }
    if let Some(display_index) = pressed {
        // `pressed` is already a *display* (filtered) index -- the same
        // one `tile_rect`/`tile_at` use everywhere else -- so its position
        // is just this call, no re-mapping through `matched` needed.
        let (x, y, tile_w, _) = tile_rect(width, height, display_index, clamped_scroll);
        let metrics = navigation::drawer_metrics();
        let card = f64::from(metrics.icon);
        if y + metrics.row_height > row_start && y < bottom {
            let cx = x + tile_w / 2.0;
            let cy = y + 8.0 + card / 2.0;
            cr.new_sub_path();
            cr.arc(cx, cy, card / 2.0 + 8.0, 0.0, 2.0 * std::f64::consts::PI);
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
        text(cr, message, 28.0, row_start + 18.0, w - 56.0, TYPE_BODY, style.muted);
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
    attach_theme_metrics(cr, theme);
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
        Route::Shade => crate::service_ui::shade_panel_height(height),
        Route::Settings => settings_panel_h(h - panel_y, chooser, services, crate::density_scale(width, height), crate::settings_wide(width, height)),
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
        Route::Power | Route::Help => "controls",
        Route::Hide => "launcher",
    };
    let style = visual_style(theme, section);
    let panel_brush = theme_brush(theme, section, "background").or_else(|| {
        matches!(route, Route::Settings | Route::Power | Route::Help)
            .then(|| theme_brush(theme, "menu", "background"))
            .flatten()
    });
    if vision_adjusted(theme) {
        // As on the drawer: an opaque sheet under a vision choice.
        color(cr, palette_rgb_or(theme, "background", 0x1e1e2e), 1.0);
        cr.rectangle(0.0, panel_y, w, panel_h);
        let _ = cr.fill();
    }
    if !panel_brush.is_some_and(|brush| fill_brush(cr, brush, 0.0, panel_y, w, panel_h)) {
        color(cr, palette_rgb_or(theme, "background", 0x1e1e2e), 1.0);
        cr.rectangle(0.0, panel_y, w, panel_h);
        let _ = cr.fill();
    }
    // Whatever content-sizing (Settings) or the fixed Shade cap leaves
    // beneath the panel is the live deck, not empty air; `RendererCache::
    // draw` dims it with a stationary, live-eased backdrop rather than
    // either an opaque void or an undimmed, jarring reveal (finding P0-2).
    // Nothing is painted here -- see this function's own doc above.
    if route == Route::Shade {
        rounded(cr, w / 2.0 - 36.0, panel_y + 11.0, 72.0, 6.0, 3.0);
        color(cr, style.text, HANDLE_ALPHA);
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
        Route::Help => "Help",
        Route::Hide => return,
    };
    // The Shade, Settings, its Wi-Fi pages and the theme chooser draw their
    // own titles.
    if !matches!(route, Route::Help | Route::Settings | Route::Shade) {
        heading(cr, title, 28.0, panel_y + 32.0, w - 180.0, 32.0, style.text);
    }
    match route {
        Route::Drawer => {}
        Route::Shade => {
            // The wide (landscape) Shade keeps its header and sliders in a
            // left column and gives the notification list the rest at its
            // full height (`service_ui::shade_layout`, which the hit-tests
            // read too). Portrait: `hw == w` and the list sits at
            // `notification_top()`, exactly as before.
            let shade = crate::service_ui::shade_layout(width, height);
            let hw = shade.controls_w;
            let items = services.and_then(|view| view.notifications.as_ref());
            let count = items.map_or(0, |snapshot| snapshot.count);
            if shade.wide {
                paint_shade_wide_controls(cr, theme, style, services, panel_y, hw);
                paint_shade_list_heading(cr, style, panel_y, &shade, count);
            } else {
                paint_shade_header(cr, style, services, panel_y, hw, count);
            }
            // The wide Shade's sliders sit under its tiles.
            let shift = crate::service_ui::shade_slider_shift(shade.wide);

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
                        hw,
                        shift + SHADE_SLIDER_TOP + SHADE_SLIDER_H / 2.0,
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
                    hw,
                    shift + SHADE_VOLUME_TOP + SHADE_VOLUME_H / 2.0,
                    volume::linear_to_percent(sink.linear_volume),
                    sink.muted,
                );
            }
            // The keyboard quick toggle: Settings' Keyboard row, in the
            // shade. Same `control_text` and the same muted treatment when
            // the capability is not an action (`panel_intent` gates the tap
            // on the same `ControlState`). The wide Shade shows it as a tile.
            if let Some(settings) = services.and_then(|view| view.settings.as_ref()).filter(|_| !shade.wide) {
                let keyboard = &settings.keyboard;
                let y = SHADE_TOGGLE_TOP + 4.0;
                paint_card(cr, theme, "controls", CardJob::Control, 24.0, y, hw - 48.0, shade_toggle_h() - 8.0);
                let available = keyboard.state == ControlState::Action;
                let ink = if available { style.text } else { style.muted };
                // The helper keeps the label "Show or hide" in both states,
                // so the unavailable card says so instead of echoing it.
                let detail = if available { control_text(keyboard) } else { "Unavailable".into() };
                // The two lines centred by their drawn height
                // (`service_ui::shade_toggle_h` grows the card to hold them).
                let label_h = vision_line(TYPE_LABEL) / 1.25 * 1.2;
                let detail_h = vision_line(TYPE_BODY) / 1.25 * 1.2;
                let label_y = y + ((shade_toggle_h() - 8.0) - label_h - detail_h) / 2.0;
                let text_x = paint_line_glyph(cr, Glyph::Keyboard, 44.0, label_y, TYPE_LABEL, ink);
                themed_role_fit(cr, theme, "body", "Keyboard", text_x, label_y, hw - 44.0 - text_x, TYPE_LABEL, ink, pango::Weight::Medium);
                themed_role_fit(cr, theme, "body", &detail, 44.0, label_y + label_h, hw - 88.0, TYPE_BODY, ink, pango::Weight::Normal);
            }
            // The preview tile repeated whatever the top history row already
            // shows -- identical text for one notification, or a
            // contentless "No active preview" sitting directly above a full
            // history list (finding P1-4). webOS kept banners (ephemeral)
            // and the dashboard (persistent history) as two different
            // objects; here, show the tile only when there is no history to
            // display it alongside.
            let show_preview = items.is_none() || count == 0;
            // Wide: the empty-state tile sits at the top of the list column
            // (the left column's volume slider occupies y 266..322).
            let (px, pw, py) = if shade.wide {
                (shade.list_x, shade.list_w, shade.list_top)
            } else {
                (0.0, w, shade.list_top)
            };
            let preview = items.and_then(|snapshot| snapshot.preview.as_ref());
            let tile_h = shade_preview_tile_h(preview.is_some());
            // Wide and empty: the message alone, centred in the list column,
            // not a lone card pinned to its top.
            let centred_empty = shade.wide && show_preview && preview.is_none() && items.is_some();
            if centred_empty {
                let size = context_font_size(cr, TYPE_BODY);
                let msg = "No new notifications";
                let msg_w = text_advance(cr, msg, TYPE_BODY, pango::Weight::Normal).min(pw);
                let y = shade.list_top + (shade.list_bottom - shade.list_top - size * 1.25) / 2.0;
                text(cr, msg, px + (pw - msg_w) / 2.0, y, pw, TYPE_BODY, style.muted);
            }
            let _ = cr.save();
            cr.translate(px, py - 262.0);
            let w = pw;
            if show_preview && !centred_empty {
                service_card(
                    cr,
                    theme,
                    "notifications",
                    24.0,
                    262.0,
                    w - 48.0,
                    tile_h,
                    false,
                );
                if let Some(preview) = preview {
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
                    let source_y = 262.0 + SHADE_TILE_INSET;
                    themed_role_fit(cr, theme, "body", &preview.source, 94.0, source_y, w - 132.0, TYPE_LABEL, style.text, pango::Weight::Medium);
                    let summary_y = source_y + vision_line(TYPE_LABEL);
                    themed_role_fit(cr, theme, "body", &preview.summary, 94.0, summary_y, w - 132.0, TYPE_BODY, style.text, pango::Weight::Normal);
                } else {
                    let empty = if items.is_none() {
                        "Loading preview"
                    } else {
                        "No new notifications"
                    };
                    let y = 262.0 + (tile_h - vision_line(TYPE_CAPTION)) / 2.0;
                    themed_role_fit(cr, theme, "caption", empty, 42.0, y, w - 84.0, TYPE_CAPTION, style.muted, pango::Weight::Normal);
                }
            }
            let _ = cr.restore();
            let w = shade.list_w;
            let list_top = shade.list_top;
            let list_bottom = shade.list_bottom;
            // The wide list column starts with the empty-state tile, so its
            // loading/error line goes beneath that instead of on top of it.
            let status_y = list_top + 14.0 + if shade.wide && show_preview { tile_h + 14.0 } else { 0.0 };
            let _ = cr.save();
            cr.translate(shade.list_x, 0.0);
            if let Some(error) = services.and_then(|view| view.notification_error.as_deref()) {
                themed_role_fit(cr, theme, "caption", error, 28.0, status_y, w - 56.0, TYPE_CAPTION, style.error, pango::Weight::Normal);
            } else if let Some(items) = items {
                let _ = cr.save();
                cr.rectangle(0.0, list_top, w, (list_bottom - list_top).max(0.0));
                cr.clip();
                let offset = services.map_or(0.0, |view| view.notification_scroll);
                let row = crate::service_ui::notification_row();
                for (index, event) in items.events.iter().enumerate() {
                    let y = list_top + index as f64 * row - offset;
                    if y + row < list_top || y >= list_bottom {
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
                        let label_w = text_advance(cr, "Dismiss", TYPE_LABEL, pango::Weight::Normal) + 2.0;
                        let x = if drag > 0.0 { 36.0 } else { w - 32.0 - label_w };
                        let label_y = y + (row - 8.0 - vision_line(TYPE_LABEL)) / 2.0;
                        text(cr, "Dismiss", x, label_y, label_w, TYPE_LABEL, style.error);
                    }
                    // The source (Label), summary (Body) and body (Caption)
                    // stack by their drawn height beside the icon column,
                    // which widens with the step.
                    let lift = crate::layout_text_scale();
                    let text_x = 56.0 + 36.0 * lift;
                    let source_y = y + 13.0;
                    let summary_y = source_y + vision_line(TYPE_LABEL) + 4.0;
                    let body_y = summary_y + vision_line(TYPE_BODY) + 4.0;
                    let _ = cr.save();
                    cr.translate(drag, 0.0);
                    service_card(
                        cr,
                        theme,
                        "notifications",
                        24.0,
                        y,
                        w - 48.0,
                        row - 8.0,
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
                            36.0 * lift,
                            22.0,
                            style.text,
                        );
                    }
                    let text_w = w - text_x - 40.0;
                    themed_role_fit(cr, theme, "body", &event.source, text_x, source_y, text_w, TYPE_LABEL, style.text, pango::Weight::Medium);
                    themed_role_fit(cr, theme, "body", &event.summary, text_x, summary_y, text_w, TYPE_BODY, style.text, pango::Weight::Normal);
                    // A failed action's reason takes the body's line.
                    match &event.error {
                        Some(error) => themed_role_fit(cr, theme, "caption", error, text_x, body_y, text_w, TYPE_CAPTION, style.error, pango::Weight::Normal),
                        None => themed_role_fit(cr, theme, "caption", &event.body, text_x, body_y, text_w, TYPE_CAPTION, style.muted, pango::Weight::Normal),
                    }
                    let _ = cr.restore();
                }
                let _ = cr.restore();
            } else {
                themed_role_fit(cr, theme, "caption", "Loading notifications", 28.0, status_y, w - 56.0, TYPE_CAPTION, style.muted, pango::Weight::Normal);
            }
            let _ = cr.restore();
            let w = hw;
            if let Some(message) = services.and_then(|view| view.message.as_deref()) {
                let card_h = (vision_line(TYPE_CAPTION) + 2.0 * SPACE_IN_ROW).max(49.0);
                let card_y = panel_h - 24.0 - card_h;
                service_card(cr, theme, "notifications", 24.0, card_y, w - 48.0, card_h, false);
                let y = card_y + (card_h - vision_line(TYPE_CAPTION)) / 2.0;
                themed_role_fit(cr, theme, "caption", message, 42.0, y, w - 84.0, TYPE_CAPTION, style.error, pango::Weight::Normal);
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
            if let Some(view) = services.and_then(|s| s.modem_page.as_ref()) {
                paint_modem(cr, view, theme, w, h);
                return;
            }
            if let Some(view) = services.and_then(|s| s.info_page.as_ref()) {
                paint_info(cr, view, theme, w, h);
                return;
            }
            if let Some(view) = chooser.filter(|view| view.page == ThemePage::Vision) {
                paint_vision(cr, w, h, view, theme);
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
            paint_settings_header(cr, theme, style, w);
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
            // At a larger vision step the body scrolls under the fixed
            // header (`service_ui::settings_max_scroll`).
            let body_top = crate::service_ui::settings_body_top(width, height);
            if body_top > 0.0 {
                cr.rectangle(0.0, body_top, w, f64::from(height));
                cr.clip();
            }
            cr.translate(content_x, -services.map_or(0.0, |view| view.settings_scroll));
            cr.scale(content_scale, content_scale);
            let wide = crate::settings_wide(width, height);
            let key_backlight_row = services.is_some_and(|view| view.key_backlight.is_some());
            let modem_rows = services.is_some_and(|view| view.modem.is_some());
            // The wide layout paints each item through its column's offset.
            let place = |column: usize| {
                let _ = cr.save();
                if wide {
                    let (dx, dy) = settings_wide_offset_for(column, key_backlight_row, modem_rows);
                    cr.translate(dx, dy);
                }
            };
            let w = if wide { crate::SETTINGS_WIDE_COL_W } else { crate::DESIGN_WIDTH };
            let row_padding = theme_settings_row_padding(theme);
            let row_text_x = 24.0 + row_padding;
            let row_text_width = w - 48.0 - row_padding * 2.0;
            if let Some(settings) = services.and_then(|view| view.settings.as_ref()) {
                // Row numbers are explicit, not a plain `enumerate()`,
                // because row 2 (Volume) is painted separately below --
                // its data comes from the PipeWire monitor
                // (`GraphSnapshot`), not `k230-settings`, so there is no
                // `Control` to hand this generic loop.
                for (row, name, control, icon) in [
                    (0u32, "Wi-Fi ›", &settings.network, Glyph::Wifi),
                    (1, "Brightness", &settings.brightness, Glyph::Sun),
                    (3, "Keyboard", &settings.keyboard, Glyph::Keyboard),
                    (4, "Reduce motion", &settings.motion, Glyph::Motion),
                ] {
                    place(settings_row_column(row));
                    let y = settings_row_y(row);
                    let (label_dy, value_dy, caption_dy, _) = settings_row_lines(row);
                    paint_card(cr, theme, "controls", CardJob::Control, 24.0, y, w - 48.0, settings_row_h(row));
                    let label_x = paint_line_glyph(cr, icon, row_text_x, y + label_dy, TYPE_LABEL, style.text);
                    themed_role_fit(cr, theme, "body", name, label_x, y + label_dy, row_text_x + row_text_width - label_x, TYPE_LABEL, style.text, pango::Weight::Medium);
                    themed_role_fit(cr, theme, "body", &control_text(control), row_text_x, y + value_dy, row_text_width, TYPE_BODY, style.text, pango::Weight::Normal);
                    if name == "Keyboard" && services.is_some_and(|view| view.keyboard_gesture_hint)
                    {
                        themed_role_fit(cr, theme, "caption", "Two fingers up: show", row_text_x, y + caption_dy, row_text_width, TYPE_CAPTION, style.muted, pango::Weight::Normal);
                        themed_role_fit(cr, theme, "caption", "Drag handle down: hide", row_text_x, y + caption_dy + vision_line(TYPE_CAPTION), row_text_width, TYPE_CAPTION, style.muted, pango::Weight::Normal);
                    } else if let Some(detail) = &control.detail {
                        themed_role_fit(cr, theme, "caption", detail, row_text_x, y + caption_dy, row_text_width, TYPE_CAPTION, style.muted, pango::Weight::Normal);
                    }
                    let _ = cr.restore();
                }
                if settings.brightness.state == ControlState::Writable {
                    // Material-3-style slider (task: "brightness should
                    // be a slider"), replacing the old stepper -- the
                    // touch target is the whole row (`slider_band` in
                    // `service_ui.rs` mirrors this same row rhythm), well
                    // past the "at least about 56 px tall" ask.
                    place(0);
                    paint_slider(cr, style, w, settings_row_y(1) + settings_row_lines(1).3, &settings.brightness);
                    let _ = cr.restore();
                }
                // Volume row (task: "in Settings"): row 2, directly after
                // Brightness. The device name doubles as the entry point
                // into the device picker -- one picker UI (the HUD's own
                // expanded panel), not two (design.md's "one picker, two
                // entry points").
                place(settings_row_column(SETTINGS_VOLUME_ROW));
                let volume_y = settings_row_y(SETTINGS_VOLUME_ROW);
                let volume_lines = settings_row_lines(SETTINGS_VOLUME_ROW);
                paint_card(cr, theme, "controls", CardJob::Control, 24.0, volume_y, w - 48.0, settings_row_h(SETTINGS_VOLUME_ROW));
                let label_x = paint_line_glyph(cr, Glyph::Speaker, row_text_x, volume_y + volume_lines.0, TYPE_LABEL, style.text);
                let sink = default_sink(services.and_then(|view| view.audio.as_ref()));
                // The level sits at the right of the heading line; the
                // "Volume" label fits the room left of it.
                let value = sink.map(|sink| {
                    let percent = volume::linear_to_percent(sink.linear_volume);
                    let label = if sink.muted { "Muted".to_string() } else { format!("{percent}%") };
                    let value_w = text_advance_resolved(cr, &label, theme_font_size(theme, "body", TYPE_BODY, TYPE_BODY, TYPE_BODY * 1.25), pango::Weight::Normal) + 2.0;
                    (label, 24.0 + w - 48.0 - row_padding - value_w, value_w)
                });
                let label_end = value.as_ref().map_or(row_text_x + row_text_width, |(_, value_x, _)| value_x - 8.0);
                themed_role_fit(cr, theme, "body", "Volume", label_x, volume_y + volume_lines.0, label_end - label_x, TYPE_LABEL, style.text, pango::Weight::Medium);
                if let (Some(sink), Some((label, value_x, value_w))) = (sink, value) {
                    let percent = volume::linear_to_percent(sink.linear_volume);
                    themed_role(cr, theme, "body", &label, value_x, volume_y + volume_lines.0, value_w, TYPE_BODY, style.text, pango::Weight::Normal);
                    themed_role_fit(
                        cr, theme, "caption",
                        &format!("{} ›", sink.description),
                        row_text_x,
                        volume_y + settings_output_detail_y(),
                        row_text_width,
                        TYPE_CAPTION,
                        style.muted,
                        pango::Weight::Normal,
                    );
                    paint_volume_slider(cr, style, w, volume_y + volume_lines.3, percent, sink.muted);
                } else {
                    themed_role_fit(
                        cr,
                        theme,
                        "body",
                        services
                            .and_then(|view| view.audio_error.as_deref())
                            .unwrap_or("No audio device found"),
                        row_text_x,
                        volume_y + volume_lines.1,
                        row_text_width,
                        TYPE_BODY,
                        style.muted,
                        pango::Weight::Normal,
                    );
                }
                let _ = cr.restore();
                // Key backlight row (keyboard base): only while its LED exists.
                if let Some(level) = services.and_then(|view| view.key_backlight) {
                    place(settings_row_column(SETTINGS_KEY_BACKLIGHT_ROW));
                    let y = settings_row_y(SETTINGS_KEY_BACKLIGHT_ROW);
                    let lines = settings_row_lines(SETTINGS_KEY_BACKLIGHT_ROW);
                    paint_card(cr, theme, "controls", CardJob::Control, 24.0, y, w - 48.0, settings_row_h(SETTINGS_KEY_BACKLIGHT_ROW));
                    let label_x = paint_line_glyph(cr, Glyph::KeyBacklight, row_text_x, y + lines.0, TYPE_LABEL, style.text);
                    themed_role_fit(cr, theme, "body", "Key backlight", label_x, y + lines.0, row_text_x + row_text_width - label_x, TYPE_LABEL, style.text, pango::Weight::Medium);
                    themed_role_fit(cr, theme, "body", level.label(), row_text_x, y + lines.1, row_text_width, TYPE_BODY, style.text, pango::Weight::Normal);
                    paint_level_slider(cr, style, w, y + lines.3, level.index(), 3);
                    let _ = cr.restore();
                }
            } else {
                text(
                    cr,
                    services
                        .and_then(|view| view.settings_error.as_deref())
                        .unwrap_or("Loading settings"),
                    28.0,
                    settings_first_y(),
                    w - 56.0,
                    TYPE_BODY,
                    style.muted,
                );
            }
            // Cellular and Location (only once the modem has answered), then
            // Date & time and About: plain label-and-value rows.
            {
                let mut rows: Vec<(&str, Glyph, String)> = Vec::new();
                if let Some(modem) = services.and_then(|view| view.modem.as_ref()) {
                    rows.push(("Cellular \u{203a}", Glyph::Signal, modem.cellular_summary()));
                    rows.push(("Location \u{203a}", Glyph::Location, modem.location_label().to_string()));
                }
                rows.push(("Date & time \u{203a}", Glyph::Clock, "Clock and time zone".to_string()));
                rows.push(("About \u{203a}", Glyph::Info, "Device and build".to_string()));
                for (index, (name, icon, value)) in rows.iter().enumerate() {
                    place(2);
                    let y = settings_modem_row_y(key_backlight_row, index as u32);
                    paint_card(cr, theme, "controls", CardJob::Control, 24.0, y, w - 48.0, settings_modem_row_h());
                    let label_x = paint_line_glyph(cr, *icon, row_text_x, y + SETTINGS_ROW_INSET, TYPE_LABEL, style.text);
                    themed_role_fit(cr, theme, "body", name, label_x, y + SETTINGS_ROW_INSET, row_text_x + row_text_width - label_x, TYPE_LABEL, style.text, pango::Weight::Medium);
                    let value_y = y + SETTINGS_ROW_INSET + vision_line(TYPE_LABEL) + 2.0;
                    themed_role_fit(cr, theme, "body", value, row_text_x, value_y, row_text_width, TYPE_BODY, style.text, pango::Weight::Normal);
                    let _ = cr.restore();
                }
            }
            // Power heading/actions and the confirm dialog are positioned
            // relative to the row rhythm above (finding P0-4), not as
            // independent literals that stay correct only by coincidence.
            let layout = settings_layout_for(key_backlight_row, modem_rows);
            let power_label_dy = (settings_power_card_h() - vision_line(TYPE_BODY)) / 2.0;
            place(2);
            if services.and_then(|view| view.settings.as_ref()).is_some() {
                themed_role(cr, theme, "heading", "Power", 28.0, layout.power_heading_y, w - 56.0, TYPE_LABEL, style.muted, pango::Weight::Bold);
                for (label, icon, card_y) in [("Reboot…", Glyph::Reboot, layout.reboot_y), ("Power off…", Glyph::Power, layout.poweroff_y)] {
                    paint_card(cr, theme, "controls", CardJob::Control, 24.0, card_y, w - 48.0, settings_power_card_h());
                    let text_x = paint_line_glyph(cr, icon, 42.0, card_y + power_label_dy, TYPE_BODY, style.text);
                    themed_role_fit(cr, theme, "body", label, text_x, card_y + power_label_dy, w - 42.0 - text_x, TYPE_BODY, style.text, pango::Weight::Normal);
                }
            }
            if let Some(confirm) = services.and_then(|view| view.confirmation.as_ref()) {
                let confirm_layout = settings_confirm_layout(layout.poweroff_bottom);
                themed_role_fit(cr, theme, "body", &confirm.label, 28.0, confirm_layout.label_y, w - 56.0, TYPE_BODY, style.text, pango::Weight::Normal);
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
                let button_y = confirm_layout.card_y + (110.0 - vision_line(TYPE_BODY)) / 2.0;
                themed_role_fit(cr, theme, "body", "Cancel", 45.0, button_y, w / 2.0 - 45.0, TYPE_BODY, style.muted, pango::Weight::Normal);
                themed_role_fit(cr, theme, "body", "Confirm", w / 2.0 + 20.0, button_y, w / 2.0 - 45.0, TYPE_BODY, style.error, pango::Weight::Normal);
            }
            if let Some(message) = services.and_then(|view| view.message.as_deref()) {
                let after = services
                    .and_then(|view| view.confirmation.as_ref())
                    .map_or(layout.poweroff_bottom, |_| {
                        settings_confirm_layout(layout.poweroff_bottom).bottom
                    });
                themed_role_fit(cr, theme, "caption", message, 28.0, after + 14.0, w - 56.0, TYPE_CAPTION, style.muted, pango::Weight::Normal);
            }
            let _ = cr.restore();
            let _ = cr.restore();
            // A scrolled body meets a hairline and fades into the page
            // under it, so no line of text ends in a bare cut.
            let scrolled = services.is_some_and(|view| view.settings_scroll > 0.0);
            if scrolled && body_top > 0.0 {
                let full_w = f64::from(width);
                let bg = palette_rgb_or(theme, "background", 0x1e1e2e);
                let (r, g, b) = (
                    f64::from((bg >> 16) & 0xff) / 255.0,
                    f64::from((bg >> 8) & 0xff) / 255.0,
                    f64::from(bg & 0xff) / 255.0,
                );
                let fade = cairo::LinearGradient::new(0.0, body_top, 0.0, body_top + SETTINGS_SCROLL_FADE);
                fade.add_color_stop_rgba(0.0, r, g, b, 0.95);
                fade.add_color_stop_rgba(1.0, r, g, b, 0.0);
                cr.rectangle(0.0, body_top, full_w, SETTINGS_SCROLL_FADE);
                if cr.set_source(&fade).is_ok() {
                    let _ = cr.fill();
                }
                cr.rectangle(24.0, body_top, full_w - 48.0, 1.0);
                color(cr, style.muted, 0.35);
                let _ = cr.fill();
            }
        }
        Route::Help => paint_help(cr, theme, width, height, services),
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
                // Two separate buttons, split at the middle the way
                // `service_ui::panel_intent` hit-tests them: Cancel on the
                // left, the named action on the right.
                let button_w = (w - 48.0 - POWER_CONFIRM_GAP) / 2.0;
                let action_x = 24.0 + button_w + POWER_CONFIRM_GAP;
                service_card(cr, theme, "controls", 24.0, POWER_CONFIRM_Y, button_w, POWER_BUTTON_H, false);
                service_card(cr, theme, "controls", action_x, POWER_CONFIRM_Y, button_w, POWER_BUTTON_H, true);
                text(cr, "Cancel", 44.0, POWER_CONFIRM_Y + 19.0, button_w - 40.0, 24.0, style.text);
                text(
                    cr, power_confirm_label(confirm.action), action_x + 20.0, POWER_CONFIRM_Y + 19.0,
                    button_w - 40.0, 24.0, style.error,
                );
            }
            // The confirmation's own question is already painted above its
            // buttons; the service reply repeats it as the message.
            let confirm_label = services.and_then(|view| view.confirmation.as_ref()).map(|c| c.label.as_str());
            if let Some(message) = services
                .and_then(|view| view.message.as_deref())
                .filter(|message| Some(*message) != confirm_label)
            {
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
    shadowed_label_px(cr, value, x, y, width, context_font_size(cr, size), rgb);
}

/// An app or folder name under its icon: the Caption role at the current
/// step, never taller than the cell leaves room for, and shrunk toward the
/// role's 100% size before a long name is shortened.
fn icon_label(cr: &Context, value: &str, content: &home_grid::TileContent, rgb: u32) {
    let px = context_font_size(cr, TYPE_CAPTION).min(content.label_room / 1.3).max(TYPE_CAPTION);
    let advance = text_advance_resolved(cr, value, px, pango::Weight::Medium);
    let room = content.label_w * 0.96;
    let px = if advance > room { (px * room / advance).max(TYPE_CAPTION) } else { px };
    shadowed_label_px(cr, value, content.label_x, content.label_y, content.label_w, px, rgb);
}

fn shadowed_label_px(cr: &Context, value: &str, x: f64, y: f64, width: f64, px: f64, rgb: u32) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(px * f64::from(pango::SCALE));
    font.set_weight(pango::Weight::Medium);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
    layout.set_alignment(pango::Alignment::Center);
    layout.set_ellipsize(EllipsizeMode::End);
    color(cr, glow_for(rgb), 0.55);
    cr.move_to(x, y + 1.4);
    pangocairo::functions::show_layout(cr, &layout);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// Exposes the icon theme's own artwork. The established plate rectangle
/// remains the touch target and provides a transient pressed cue only.
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
    cr.new_path();
    if pressed || hovered(cr, plate_x, plate_y, plate_size, plate_size) {
        service_card_state(cr, theme, "launcher", plate_x, plate_y, plate_size, plate_size, false, pressed);
    }
    let icon_x = plate_x + (plate_size - icon_size) / 2.0;
    let icon_y = plate_y + (plate_size - icon_size) / 2.0;
    let painted = app
        .icon
        .as_deref()
        .is_some_and(|icon| icons.paint(cr, icon, icon_size as i32, icon_x, icon_y))
        || (terminal_like(&app.path)
            && icons.paint(cr, "utilities-terminal", icon_size as i32, icon_x, icon_y));
    if !painted {
        service_card(cr, theme, "launcher", icon_x, icon_y, icon_size, icon_size, false);
        let initial = app.name.chars().next().unwrap_or('?').to_uppercase().to_string();
        centered_label(
            cr,
            &initial,
            plate_x,
            plate_y + plate_size / 2.0 - icon_size * 0.27,
            plate_size,
            // Sized to the icon, not the text step: undo the step that
            // `centered_label` applies.
            icon_size * 0.55 * 100.0 / context_font_size(cr, 100.0),
            style.accent,
        );
    }
}

/// A stream or output name in the volume HUD's expanded row: the Caption
/// role, growing with the step only as far as the row leaves above its
/// slider, and shrunk toward 26 px before a long name is shortened.
fn hud_row_name(cr: &Context, value: &str, x: f64, y: f64, width: f64, rgb: u32) {
    let room = volume::HUD_ROW_H - 18.0 - 6.0;
    let px = context_font_size(cr, TYPE_CAPTION).min(room / 1.25).max(TYPE_CAPTION);
    let advance = text_advance_resolved(cr, value, px, pango::Weight::Normal);
    let px = if advance > width * 0.96 { (px * width * 0.96 / advance).max(TYPE_CAPTION) } else { px };
    text_weight_resolved(cr, value, x, y, width, px, rgb, pango::Weight::Normal);
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
            service_card_state(cr, theme, "launcher", plate_x, plate_y, plate_size, plate_size, false, pressed);
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
    font.set_absolute_size(context_font_size(cr, size) * f64::from(pango::SCALE));
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

/// A small centered number/label (the battery ring's percentage, a
/// forecast column's temperature), haloed the same way -- distinct from
/// the top-level `centered_label` (used by panels that still have their
/// own opaque backing, e.g. the folder overlay/picker sheet, where a halo
/// would be redundant).
fn centered_glow(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(context_font_size(cr, size) * f64::from(pango::SCALE));
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
            if col_index >= cols {
                continue;
            }
            let cx = x0 + (col_index as f64 + 0.5) * pitch;
            let cy = y0 + (row_index as f64 + 0.5) * pitch;
            if ch != '1' {
                // The unlit dots of a digit stay faintly visible, so the
                // block reads as a lamp grid rather than floating dots.
                if cols == 5 {
                    cr.new_path();
                    cr.arc(cx, cy, radius * 0.5, 0.0, std::f64::consts::TAU);
                    color(cr, rgb, 0.16);
                    let _ = cr.fill();
                }
                continue;
            }
            draw_soft_backdrop(cr, cx, cy, radius * 1.9, glow, 0.16);
            // A crisp ring in the halo colour keeps a lit dot apart from a
            // wallpaper of its own hue (the accent minute over an orange
            // label), the way the Bubble digits keep their outline.
            cr.new_path();
            cr.arc(cx, cy, radius + (pitch * 0.1).max(1.5), 0.0, std::f64::consts::TAU);
            color(cr, glow, 0.8);
            let _ = cr.fill();
            cr.new_path();
            cr.arc(cx, cy, radius, 0.0, std::f64::consts::TAU);
            color(cr, rgb, 0.95);
            let _ = cr.fill();
        }
    }
}

/// Draws `"HH"`/`"MM"` as a Nothing-OS-style dot-matrix readout, centered
/// within `(x, y, w, h)`: the hour and colon in `digit_rgb`, the minute in
/// `accent_rgb` (task: "Use theme colours tastefully: an accent for one
/// element and the foreground for the rest").
#[allow(clippy::too_many_arguments)]
fn draw_dot_matrix_time(cr: &Context, hour_text: &str, minute_text: &str, x: f64, y: f64, w: f64, h: f64, digit_rgb: u32, accent_rgb: u32) {
    let chars: Vec<(char, usize, u32)> = hour_text
        .chars()
        .map(|ch| (ch, 5, digit_rgb))
        .chain(std::iter::once((':', 2, digit_rgb)))
        .chain(minute_text.chars().map(|ch| (ch, 5, accent_rgb)))
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
    // Larger text (the vision step) or a large theme font must still fit
    // inside the ring: shrink this one label rather than cross the stroke.
    let size = ring_label_size(cr, value, size, radius);
    let drawn = context_font_size(cr, size);
    centered_glow(cr, value, cx - width / 2.0, cy - drawn * 0.42, width, size, rgb);
}

/// The Clock widget's date line at 100% text: about 15.5 dp on the panel.
/// Sentence case in Inter Semibold has a smaller footprint than the old
/// tracked capitals (the operator said the clock text was too small), so the
/// floor rises from 26 to 32 px.
const CLOCK_DATE_MIN: f64 = 32.0;

/// Where a Clock widget's date line goes in a card `w` x `h`.
struct ClockDate {
    /// Design size of the date text.
    size: f64,
    /// Top of the date, relative to the card.
    top: f64,
    /// How much the time above shrinks to clear it (1.0 = untouched).
    time_scale: f64,
}

/// The date as one neutral Inter line: "Fri, Oct 16", not capitals with
/// thin-space tracking. The accent belongs to the minute.
fn clock_date_layout(cr: &Context, value: &str, size: f64) -> pango::Layout {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(CLOCK_FONT_FAMILY);
    font.set_absolute_size(context_font_size(cr, size) * f64::from(pango::SCALE));
    font.set_weight(pango::Weight::Semibold);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout
}

/// Centered, haloed like every other glyph drawn on the wallpaper.
fn clock_date_glow(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    let layout = clock_date_layout(cr, value, size);
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
    layout.set_alignment(pango::Alignment::Center);
    draw_layout_halo(cr, &layout, x, y, glow_for(rgb), 2.0, 8, 0.35);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// `default_top` is the style's original date position as a fraction of
/// `h`. The date grows with the Vision text step, which the rest of the
/// widget ignores, and fits the card's width with the shell's 4% margin.
fn clock_date_metrics(cr: &Context, date: &str, w: f64, h: f64, default_top: f64) -> ClockDate {
    let room = (w - 2.0 * visual_inset(cr, 22.0)).max(1.0) * 0.96;
    let wanted = CLOCK_DATE_MIN * crate::layout_text_scale();
    let (_, logical) = clock_date_layout(cr, date, wanted).pixel_extents();
    let (advance, height) = (f64::from(logical.width()), f64::from(logical.height()));
    let fit = if advance > room { room / advance } else { 1.0 };
    let top = (h * default_top).min(h - height * fit - h * 0.04);
    ClockDate { size: wanted * fit, top, time_scale: (top / (h * default_top)).min(1.0) }
}

/// The Bubble clock's two stacked lines in a card `w` x `h`, scaled by `k`
/// (see [`ClockDate::time_scale`]): font size, the two line tops relative to
/// the card, and the baseline of the second line (about 1 em below its top).
/// The lines sit closer than their boxes (pitch 0.92 em) so both numerals
/// read as one mass.
fn bubble_lines(w: f64, h: f64, k: f64) -> (f64, f64, f64, f64) {
    let size = (h * 0.38 * k).min(w * 0.46);
    let first = h * 0.05 * k;
    let second = first + size * 0.92;
    (size, first, second, second + size)
}

/// A run of differently coloured pieces of one line (`HH`, `:`, `MM`),
/// centered as a whole in `[x, x+width]`, each piece haloed like
/// [`hero_glow`].
#[allow(clippy::too_many_arguments)]
fn hero_glow_run(cr: &Context, parts: &[(&str, u32, f64)], x: f64, y: f64, width: f64, size: f64, weight: pango::Weight, font_family: &str) {
    let layouts: Vec<pango::Layout> = parts
        .iter()
        .map(|(text, _, _)| {
            let layout = pangocairo::functions::create_layout(cr);
            let mut font = FontDescription::new();
            font.set_family(font_family);
            font.set_absolute_size(context_font_size(cr, size) * f64::from(pango::SCALE));
            font.set_weight(weight);
            layout.set_font_description(Some(&font));
            layout.set_text(text);
            layout
        })
        .collect();
    let total: f64 = layouts.iter().map(|l| f64::from(l.pixel_size().0)).sum();
    let mut cursor = x + (width - total) / 2.0;
    for (layout, (_, rgb, alpha)) in layouts.iter().zip(parts) {
        draw_layout_halo(cr, layout, cursor, y, glow_for(*rgb), (size * 0.05).max(2.0), 8, 0.30 * alpha);
        color(cr, *rgb, *alpha);
        cr.move_to(cursor, y);
        pangocairo::functions::show_layout(cr, layout);
        cursor += f64::from(layout.pixel_size().0);
    }
}

fn ring_label_size(cr: &Context, value: &str, size: f64, radius: f64) -> f64 {
    let inside = radius * 1.5;
    let advance = text_advance(cr, value, size, pango::Weight::Bold);
    if advance > inside { size * inside / advance } else { size }
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

/// One haloed text run with explicit alignment and end-ellipsis, for the
/// Battery - Details widget.
#[allow(clippy::too_many_arguments)]
/// A small widget's line at an already-resolved `px`, shrunk toward (never
/// below) `floor` until it fits `width`, haloed like [`detail_glow`].
#[allow(clippy::too_many_arguments)]
fn widget_line(cr: &Context, value: &str, x: f64, y: f64, width: f64, px: f64, floor: f64, rgb: u32,
               weight: pango::Weight, align: pango::Alignment) {
    let advance = text_advance_resolved(cr, value, px, weight);
    let room = width * 0.96;
    let px = if advance > room { (px * room / advance).max(floor.min(px)) } else { px };
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(px * f64::from(pango::SCALE));
    font.set_weight(weight);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
    layout.set_ellipsize(EllipsizeMode::End);
    layout.set_alignment(align);
    draw_layout_halo(cr, &layout, x, y, glow_for(rgb), 2.0, 8, 0.35);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// The Caption-role size for a 2x2 widget's lines: 26 px at a Home-sized
/// card (narrower picker previews scale down in proportion), growing with
/// the text step only as far as `lines` such lines plus `fixed` px of
/// other content fit the card's height.
fn widget_caption_px(w: f64, h: f64, lines: f64, fixed: f64) -> (f64, f64) {
    let floor = TYPE_CAPTION * (w / 240.0).min(1.0);
    let step = crate::layout_text_scale().max(1.0);
    let fit = ((h - fixed) / (lines * floor * 1.25)).max(1.0);
    (floor * step.min(fit), floor)
}

fn detail_glow(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32, weight: pango::Weight, align: pango::Alignment) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(context_font_size(cr, size) * f64::from(pango::SCALE));
    font.set_weight(weight);
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
    layout.set_ellipsize(EllipsizeMode::End);
    layout.set_alignment(align);
    draw_layout_halo(cr, &layout, x, y, glow_for(rgb), 2.0, 8, 0.35);
    color(cr, rgb, 1.0);
    cr.move_to(x, y);
    pangocairo::functions::show_layout(cr, &layout);
}

/// The Battery - Details charge graph: the last 12 hours of recorded
/// percentage from 0 to 100, filled under the line, charging stretches in
/// the accent colour, and a break wherever the shell recorded nothing for
/// more than five minutes.
fn paint_charge_graph(cr: &Context, style: &VisualStyle, view: &crate::home_widgets::battery::history::View, rect: (f64, f64, f64, f64), caption_size: f64) {
    let (gx, gy, gw, gh) = rect;
    let plot_h = gh - caption_size * 1.5;
    let bottom = gy + plot_h;
    let span = view.span_s();
    let start = view.now - span;
    let px = |at: i64| gx + (at - start) as f64 / span as f64 * gw;
    let py = |percent: u8| bottom - f64::from(percent) / 100.0 * plot_h;

    cr.save().ok();
    cr.set_line_width(1.0);
    // A soft panel behind the plot keeps it legible on a busy wallpaper.
    cr.new_path();
    cr.rectangle(gx, gy, gw, plot_h);
    color(cr, glow_for(style.text), 0.35);
    let _ = cr.fill();
    for level in [0u8, 50, 100] {
        cr.new_path();
        cr.move_to(gx, py(level).round() + 0.5);
        cr.line_to(gx + gw, py(level).round() + 0.5);
        color(cr, style.muted, if level == 0 { 0.7 } else { 0.4 });
        let _ = cr.stroke();
    }
    cr.set_line_join(cairo::LineJoin::Round);
    cr.set_line_cap(cairo::LineCap::Round);
    for run in view.runs() {
        if run.len() == 1 {
            let only = run[0];
            cr.new_path();
            cr.arc(px(only.at), py(only.percent), 2.5, 0.0, std::f64::consts::TAU);
            color(cr, if only.charging { style.accent } else { style.text }, 1.0);
            let _ = cr.fill();
            continue;
        }
        // Stretches of one style: a segment takes the style of its later
        // sample, so a charge starts where the plug went in.
        let mut stretches: Vec<(bool, &[crate::home_widgets::battery::history::Sample])> = Vec::new();
        let mut from = 0;
        for i in 1..run.len() {
            if i + 1 == run.len() || run[i + 1].charging != run[i].charging {
                stretches.push((run[i].charging, &run[from..=i]));
                from = i;
            }
        }
        for (charging, stretch) in &stretches {
            cr.new_path();
            cr.move_to(px(stretch[0].at), bottom);
            for sample in stretch.iter() {
                cr.line_to(px(sample.at), py(sample.percent));
            }
            cr.line_to(px(stretch[stretch.len() - 1].at), bottom);
            cr.close_path();
            color(cr, if *charging { style.accent } else { style.text }, 0.16);
            let _ = cr.fill();
        }
        cr.new_path();
        cr.move_to(px(run[0].at), py(run[0].percent));
        for sample in &run[1..] {
            cr.line_to(px(sample.at), py(sample.percent));
        }
        color(cr, glow_for(style.text), 0.5);
        cr.set_line_width(5.0);
        let _ = cr.stroke();
        cr.set_line_width(2.5);
        for (charging, stretch) in &stretches {
            cr.new_path();
            cr.move_to(px(stretch[0].at), py(stretch[0].percent));
            for sample in &stretch[1..] {
                cr.line_to(px(sample.at), py(sample.percent));
            }
            color(cr, if *charging { style.accent } else { style.text }, 1.0);
            let _ = cr.stroke();
        }
    }
    cr.restore().ok();
    let caption_y = bottom + caption_size * 0.35;
    detail_glow(cr, &format!("{} h ago", span / 3600), gx, caption_y, gw / 2.0, caption_size, style.muted, pango::Weight::Normal, pango::Alignment::Left);
    detail_glow(cr, "now", gx + gw / 2.0, caption_y, gw / 2.0, caption_size, style.muted, pango::Weight::Normal, pango::Alignment::Right);
    if view.samples.len() < 2 {
        detail_glow(cr, "Recording charge", gx, gy + plot_h * 0.38, gw, caption_size, style.muted, pango::Weight::Normal, pango::Alignment::Center);
    }
}

/// The Battery - Details widget (4x2): a ring with the percentage and the
/// state/time beside it, a two-row grid of the gauge's metrics (absent ones
/// are skipped and the rest reflow), and the charger/input line beneath.
/// Sizes derive from both the rect's height and width so the same code reads
/// on the portrait panel, wide surfaces and the square picker preview.
/// The Label/Caption role's floor for Battery - Details text, in design px.
const BATTERY_TEXT_FLOOR: f64 = 26.0;
/// The widget width at which that floor applies in full (a Home-sized 4x2
/// cell is wider); narrower previews scale it down in proportion.
const BATTERY_FLOOR_WIDTH: f64 = 400.0;

fn paint_battery_details(cr: &Context, style: &VisualStyle, rect: (f64, f64, f64, f64), home: &HomeScreen, pad: f64) {
    use crate::home_widgets::battery::DetailsState;
    let (x, y, w, h) = rect;
    let DetailsState::Present(details) = &home.battery_details else {
        let (px, floor) = widget_caption_px(w, h, 2.0, h * 0.62);
        widget_line(cr, "Battery", x + pad, y + pad * 0.7, w - pad * 2.0, px, floor, style.text,
            pango::Weight::Medium, pango::Alignment::Left);
        let glyph_w = (w * 0.16).min(h * 0.4);
        let glyph_h = glyph_w * 0.52;
        draw_battery_outline(cr, x + (w - glyph_w) / 2.0, y + h * 0.32, glyph_w, glyph_h, style.text);
        widget_line(cr, "No battery info", x + pad, y + h * 0.62, w - pad * 2.0, px, floor, style.text,
            pango::Weight::Normal, pango::Alignment::Center);
        return;
    };
    // The Label/Caption floor (the-shell-has-one-visual-language, type
    // scale): 26 px on a Home-sized widget. The picker's small preview
    // scales it down with the widget instead of overflowing.
    let floor = BATTERY_TEXT_FLOOR * (w / BATTERY_FLOOR_WIDTH).min(1.0);
    // The bottom of the widget is the charge graph; everything else lays
    // out in the rest. The graph keeps a readable plot under its captions.
    let graph_h = (h * 0.27).max(floor * 1.5 + 48.0 * (w / BATTERY_FLOOR_WIDTH).min(1.0));
    let h = h - graph_h;
    let size = |h_frac: f64, w_frac: f64, floor: f64| (h * h_frac).min(w * w_frac).max(floor);
    let left = x + pad;
    let inner_w = w - pad * 2.0;
    paint_charge_graph(
        cr,
        style,
        &home.battery_history,
        (left, y + h, inner_w, graph_h - pad * 0.4),
        floor,
    );

    // Hero: ring + percentage, then state and time to its right.
    let radius = (h * 0.17).min(w * 0.105);
    let state_size = size(0.10, 0.06, floor);
    let time_size = size(0.08, 0.048, floor);
    let line_size = size(0.06, 0.034, floor);
    // Metrics: one line per cell, the label on the left and the value
    // after it, two cells to a row. A larger vision step enlarges them as
    // far as two rows still fit; the hero and graph keep their
    // cell-proportional sizes.
    let base_label = floor;
    let base_value = floor * 1.15;
    let mut cells: Vec<(&str, String)> = Vec::new();
    let mut push = |label: &'static str, value: Option<String>| {
        if let Some(value) = value {
            cells.push((label, value));
        }
    };
    push("Current", details.current_label());
    push("Power", details.power_label());
    push("Voltage", details.voltage_label());
    push("Temp", details.temperature_label());
    push("Health", details.health_label());
    push("Cycles", details.cycles_label());
    let cell_w = inner_w / 2.0 - pad * 0.5;
    // The widest label-and-value pair (in the first two rows) at 100%,
    // which bounds how far the step can enlarge them without cutting a
    // value off.
    let widest = cells
        .iter()
        .take(4)
        .map(|(label, value)| {
            text_advance(cr, label, base_label, pango::Weight::Normal)
                + base_label * 0.4
                + text_advance(cr, value, base_value, pango::Weight::Bold)
        })
        .fold(0.0, f64::max);
    let width_room = if widest > 0.0 { cell_w * 0.96 / widest } else { 1.0 };
    let grid_room = (h - radius * 2.2 - line_size * 1.3) / (base_value * 1.3 * 2.0);
    // A pair that would not fit even at 100% shrinks a little rather than
    // losing its unit to an ellipsis.
    let grid_scale = crate::layout_text_scale().min(grid_room).max(1.0).min(width_room.max(0.85));
    let label_size = base_label * grid_scale;
    let value_size = base_value * grid_scale;
    let row_h = value_size * 1.3;
    // As many rows as the space holds (at least one, at most three), and
    // the input line only when it still fits under them.
    let free = h - radius * 2.2;
    let rows = ((free / row_h).floor() as usize).clamp(1, 3).min(cells.len().div_ceil(2));
    // The most detailed input line that fits the width uncut; failing
    // that, the shortest, which the ellipsis may still trim.
    let input = {
        let choices = details.input_label_choices();
        let fits = |line: &String| text_advance(cr, line, line_size, pango::Weight::Normal) <= inner_w * 0.98;
        choices.iter().find(|line| fits(line)).or(choices.last()).cloned()
    }
    .filter(|_| free - rows as f64 * row_h >= line_size * 1.3);
    let blocks_h = radius * 2.2 + row_h * rows as f64 + if input.is_some() { line_size * 1.3 } else { 0.0 };
    let gap = ((h - blocks_h) / 4.0).max(0.0);
    let ring_cx = left + radius + radius * 0.2;
    let ring_cy = y + gap + radius * 1.1;
    draw_battery_ring(cr, ring_cx, ring_cy, radius, details.percent, style);
    ring_percent_label(cr, &format!("{}%", details.percent), ring_cx, ring_cy, radius, style.text);
    if details.is_charging() {
        let badge_r = radius * 0.34;
        let (bx, by) = (ring_cx + radius * 0.74, ring_cy - radius * 0.74);
        draw_soft_backdrop(cr, bx, by, badge_r * 1.5, glow_for(style.accent), 0.20);
        cr.new_path();
        cr.arc(bx, by, badge_r, 0.0, std::f64::consts::TAU);
        color(cr, style.accent, 0.95);
        let _ = cr.fill();
        draw_bolt(cr, bx, by, badge_r * 1.25, glow_for(style.accent));
    }
    let text_x = ring_cx + radius * 1.45;
    let text_w = (x + w - pad - text_x).max(10.0);
    let hero_h = state_size * 1.25 + time_size * 1.3;
    let mut ty = ring_cy - hero_h / 2.0;
    detail_glow(cr, &details.state_label(), text_x, ty, text_w, state_size, style.text, pango::Weight::Bold, pango::Alignment::Left);
    ty += state_size * 1.25;
    if let Some(time) = details.time_label() {
        detail_glow(cr, &time, text_x, ty, text_w, time_size, style.accent, pango::Weight::Bold, pango::Alignment::Left);
    }

    let col_w = inner_w / 2.0;
    let grid_y = ring_cy + radius * 1.1 + gap;
    // The label sits on the value's baseline, roughly.
    let label_drop = (value_size - label_size) * 0.8;
    for (i, (label, value)) in cells.into_iter().take(rows * 2).enumerate() {
        let cx = left + (i % 2) as f64 * col_w;
        let cy = grid_y + (i / 2) as f64 * row_h;
        let label_w = text_advance(cr, label, label_size, pango::Weight::Normal);
        detail_glow(cr, label, cx, cy + label_drop, cell_w, label_size, style.muted, pango::Weight::Normal, pango::Alignment::Left);
        let value_x = cx + label_w + label_size * 0.4;
        // The value may use its column up to the next one (the right
        // column up to the widget's inset), and shrinks toward the label
        // size, never below it, before it would be cut off.
        let room = cx + col_w - pad * 0.25 - value_x;
        let advance = text_advance(cr, &value, value_size, pango::Weight::Bold);
        let fitted = if advance > room * 0.96 { (value_size * room * 0.96 / advance).max(label_size) } else { value_size };
        detail_glow(cr, &value, value_x, cy + (value_size - fitted) * 0.8, room.max(10.0), fitted, style.text, pango::Weight::Bold, pango::Alignment::Left);
    }

    // Input line.
    if let Some(line) = input {
        detail_glow(cr, &line, left, grid_y + row_h * rows as f64 + gap, inner_w, line_size, style.accent, pango::Weight::Normal, pango::Alignment::Left);
    }
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
    // A widget sizes its text to its own cell (the clock's digits are 30% of
    // its height), so the vision step must not multiply that again: at 200%
    // the digits overlapped and the battery grid truncated (board, panel
    // 1232x568, 2026-10-16). Widgets reflow for the step themselves instead
    // (`paint_battery_details`' grid).
    let target = cr.target();
    let saved = target.user_data(&THEME_METRICS);
    let vision = crate::layout_text_scale();
    if let Some(metrics) = saved.as_ref().filter(|_| vision > 1.0) {
        let _ = target.set_user_data(&THEME_METRICS, Rc::new(ThemeMetrics {
            font: metrics.font / vision,
            spacing: metrics.spacing,
        }));
    }
    paint_widget_card_content(cr, style, kind, rect, home);
    if let Some(metrics) = saved {
        let _ = target.set_user_data(&THEME_METRICS, metrics);
    }
}

fn paint_widget_card_content(cr: &Context, style: &VisualStyle, kind: WidgetKind, rect: (f64, f64, f64, f64), home: &HomeScreen) {
    let (x, y, w, h) = rect;
    cr.new_path();
    let pad = visual_inset(cr, 22.0);
    match kind {
        WidgetKind::Clock | WidgetKind::ClockMinimal | WidgetKind::ClockDotMatrix => {
            let (hour_text, minute_text, date_text) = match crate::home_widgets::clock::now_local() {
                Some(now) => (format!("{:02}", now.hour), format!("{:02}", now.minute), crate::home_widgets::clock::format_date(now)),
                None => ("--".to_string(), "--".to_string(), String::new()),
            };
            // The date is sized first; the time takes what is left above it.
            let date = clock_date_metrics(cr, &date_text, w, h, 0.84);
            let k = date.time_scale;
            // One rule for every style: the hour is the foreground colour
            // and the minute, the part that changes, carries the accent.
            match kind {
                WidgetKind::Clock => {
                    // "Bubble": Pixel's heavy two-line lock clock, tightened
                    // into one mass (`docs/design/clock-widget-research.md`
                    // #1/#7), the hour in the text colour over the minute in
                    // the accent.
                    let (line_size, first, second, _) = bubble_lines(w, h, k);
                    hero_glow(cr, &hour_text, x, y + first, w, line_size, style.text, pango::Weight::Heavy, true, CLOCK_FONT_FAMILY);
                    hero_glow(cr, &minute_text, x, y + second, w, line_size, style.accent, pango::Weight::Heavy, true, CLOCK_FONT_FAMILY);
                }
                WidgetKind::ClockMinimal => {
                    // "Thin": a real light weight, not a shrunk bold
                    // (research #2/#9/#12); the colon is a quiet separator.
                    let line_size = (h * 0.32 * k).min(w * 0.30);
                    hero_glow_run(
                        cr,
                        &[(hour_text.as_str(), style.text, 1.0), (":", style.text, 0.6), (minute_text.as_str(), style.accent, 1.0)],
                        x, y + h * 0.34 * k, w, line_size, pango::Weight::Light, CLOCK_FONT_FAMILY,
                    );
                }
                WidgetKind::ClockDotMatrix => {
                    // "Dot matrix": Nothing OS's Ndot (research #4), drawn
                    // procedurally -- no font at all.
                    draw_dot_matrix_time(cr, &hour_text, &minute_text, x + pad * 0.5, y, w - pad, h * 0.72 * k, style.text, style.accent);
                }
                _ => unreachable!("matched above"),
            }
            clock_date_glow(cr, &date_text, x + pad, y + date.top, w - pad * 2.0, date.size, style.text);
        }
        WidgetKind::ClockAnalog => {
            let (hour, minute, date_text) = match crate::home_widgets::clock::now_local() {
                Some(now) => (now.hour, now.minute, crate::home_widgets::clock::format_date(now)),
                None => (0, 0, String::new()),
            };
            let date = clock_date_metrics(cr, &date_text, w, h, 0.86);
            let k = date.time_scale;
            let cx = x + w / 2.0;
            let cy = y + h * 0.42 * k;
            let radius = (w / 2.0 - pad).min(h * 0.34 * k);
            draw_analog_clock(cr, cx, cy, radius, hour, minute, style);
            clock_date_glow(cr, &date_text, x + pad, y + date.top, w - pad * 2.0, date.size, style.text);
        }
        WidgetKind::Battery => {
            let (px, floor) = widget_caption_px(w, h, 2.0, h * 0.62);
            widget_line(cr, "Battery", x + pad, y + pad * 0.7, w - pad * 2.0, px, floor, style.text,
                pango::Weight::Medium, pango::Alignment::Left);
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
                    widget_line(cr, "No battery info", x + pad, y + h * 0.68, w - pad * 2.0, px, floor, style.text,
                        pango::Weight::Normal, pango::Alignment::Center);
                }
            }
        }
        WidgetKind::BatteryDetails => paint_battery_details(cr, style, rect, home, pad),
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
            // Top to bottom: location (beside the condition glyph), the
            // temperature, the high/low line and a three-column forecast
            // strip, each caption on the Caption role; the temperature takes
            // whatever height is left.
            let shown: Vec<_> = forecast.iter().take(3).collect();
            let k = (w / 240.0).min(1.0);
            let strip_glyph = 32.0 * k;
            let lines = if shown.is_empty() { 2.0 } else { 4.0 };
            let (px, floor) = widget_caption_px(w, h, lines, pad * 1.6 + 56.0 * k + strip_glyph + 20.0);
            let line_h = px * 1.25;
            let glyph_size = 56.0 * k;
            draw_weather_glyph(cr, &glyph, x + w - pad - glyph_size * 0.46, y + pad + glyph_size * 0.4, glyph_size, style);
            let loc_y = y + pad * 0.6;
            if !location.is_empty() {
                widget_line(cr, &location, x + pad, loc_y, w - pad * 2.0 - glyph_size, px, floor, style.text,
                    pango::Weight::Medium, pango::Alignment::Left);
            }
            let strip_h = if shown.is_empty() { 0.0 } else { line_h + 4.0 + strip_glyph + 4.0 + line_h };
            let strip_y = y + h - pad * 0.6 - strip_h;
            let hl_y = strip_y - line_h - 4.0;
            let hero_top = loc_y + line_h;
            let mut hero_size = (h * 0.24).min(((hl_y - hero_top) / 1.2).max(0.0) / context_font_size(cr, 1.0));
            let hero = temp_c.map_or_else(|| "--".to_string(), crate::home_widgets::weather::fahrenheit_label);
            // Where the temperature's line shares rows with the glyph, it
            // keeps to the width left of the glyph's backdrop.
            let glyph_bottom = y + pad + glyph_size * 0.4 + glyph_size * 0.62;
            if hero_top < glyph_bottom {
                let room = w - pad * 2.0 - glyph_size * 1.08 - 4.0;
                let advance = text_advance(cr, &hero, hero_size, pango::Weight::Bold);
                if advance > room && advance > 0.0 {
                    hero_size *= (room / advance).max(0.0);
                }
            }
            hero_glow(cr, &hero, x + pad, hero_top, w, hero_size, style.text, pango::Weight::Bold, false, FONT_FAMILY);
            let high_low = match (high_c, low_c) {
                (Some(high), Some(low)) => format!("H {}  L {}", crate::home_widgets::weather::fahrenheit_label(high),
                    crate::home_widgets::weather::fahrenheit_label(low)),
                _ => "No data".to_string(),
            };
            widget_line(cr, &high_low, x + pad, hl_y, w - pad * 2.0, px, floor, style.text,
                pango::Weight::Normal, pango::Alignment::Left);
            if !shown.is_empty() {
                // The strip spans the whole card: with the side padding a
                // column is too narrow for "12am" at the Caption role.
                let col_w = w / shown.len() as f64;
                for (index, entry) in shown.iter().enumerate() {
                    let col_x = x + col_w * index as f64;
                    widget_line(cr, &entry.label, col_x, strip_y, col_w, px, floor, style.text,
                        pango::Weight::Normal, pango::Alignment::Center);
                    let entry_glyph = crate::home_widgets::weather::condition_glyph(&entry.condition);
                    draw_weather_glyph(cr, entry_glyph, col_x + col_w / 2.0, strip_y + line_h + 4.0 + strip_glyph / 2.0,
                        strip_glyph, style);
                    // Degrees alone: three "°F" columns run together in a 2x2 card.
                    let temp = crate::home_widgets::weather::fahrenheit_label(entry.temp_c);
                    widget_line(cr, temp.trim_end_matches('F'), col_x,
                        strip_y + line_h + 8.0 + strip_glyph, col_w, px, floor, style.text, pango::Weight::Bold,
                        pango::Alignment::Center);
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
    paint_scrim(cr, theme, "launcher", f64::from(width), f64::from(height), 0, 0.5);
    let (cx, cy, cw, ch) = home_grid::folder_overlay_rect_inset(width, height, home.keyboard_inset);
    service_card(cr, theme, "launcher", cx, cy, cw, ch, false);
    let name_rect = home_grid::folder_name_rect_inset(width, height, home.keyboard_inset);
    if open.editing_name {
        service_card_interaction(cr, theme, "launcher", name_rect.0, name_rect.1, name_rect.2, name_rect.3, false, false, true);
    }
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
        let content = home_grid::content_in(home_grid::folder_app_rect_inset(width, height, index, home.keyboard_inset));
        if let Some(app) = app_by_id(apps, id) {
            paint_icon_plate(cr, theme, icons, app, content.plate_x, content.plate_y, content.plate_size,
                content.icon_size, false);
            icon_label(cr, &app.name, &content, brush_rgb(theme, "launcher", "text", style.text));
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
    paint_scrim(cr, theme, "launcher", f64::from(width), f64::from(height), 0, 0.5);
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
        // Rows shrink to fit the card (`home_grid::picker_row_rect`); the
        // labels scale with them from the full 92 px row.
        let k = (h / 92.0).clamp(0.6, 1.0);
        centered_label(cr, &title, label_x, y + 12.0 * k, label_w, 22.0 * k, label_color);
        if !subtitle.is_empty() {
            shadowed_label(cr, &subtitle, label_x, y + h - 30.0 * k, label_w, (14.0 * k).max(11.0), brush_rgb(theme, "launcher", "text", style.text));
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

/// Home's pending-notification count: an accent pill with the number, in the
/// top-right corner of Home's own buffer. Painted text only -- no surface, no
/// opaque region, not a touch target -- and it reads nothing but the integer.
/// Hidden at zero and while rearranging (the Done pill uses that corner).
fn paint_pending_count(
    cr: &Context,
    width: u32,
    height: u32,
    _theme: Option<&AppearanceSnapshot>,
    home: &HomeScreen,
    style: &VisualStyle,
) {
    let Some(label) = crate::home_screen::count_label(home.pending_count) else { return };
    if home.rearranging {
        return;
    }
    let px = context_font_size(cr, TYPE_CAPTION);
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(px * f64::from(pango::SCALE));
    font.set_weight(pango::Weight::Bold);
    layout.set_font_description(Some(&font));
    layout.set_text(&label);
    let (text_w, text_h) = layout.pixel_size();
    let pad_x = visual_inset(cr, 14.0);
    let pad_y = visual_inset(cr, 5.0);
    let (pill_w, pill_h) = ((f64::from(text_w) + 2.0 * pad_x).max(f64::from(text_h) + 2.0 * pad_y), f64::from(text_h) + 2.0 * pad_y);
    let columns = home.layout.columns;
    let occupied: Vec<_> = (0..home_grid::apps_per_page(width, height))
        .map(|slot| home_grid::tile_rect(width, height, slot, columns))
        .collect();
    let (x, y, w, h) = crate::home_screen::count_pill_rect(width, pill_w, pill_h, &occupied);
    rounded(cr, x, y, w, h, h / 2.0);
    color(cr, style.accent, 1.0);
    let _ = cr.fill();
    // Dark or light text, whichever contrasts with the accent fill.
    let (r, g, b) = (f64::from((style.accent >> 16) & 255), f64::from((style.accent >> 8) & 255), f64::from(style.accent & 255));
    let on_accent = if 0.299 * r + 0.587 * g + 0.114 * b > 150.0 { 0x11141a } else { 0xffffff };
    color(cr, on_accent, 1.0);
    cr.move_to(x + (w - f64::from(text_w)) / 2.0, y + (h - f64::from(text_h)) / 2.0);
    pangocairo::functions::show_layout(cr, &layout);
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
    attach_theme_metrics(cr, theme);
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
                    if home.rearranging {
                        paint_remove_badge(cr, theme, home.badge_corner(this_slot, width, height, columns));
                    }
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
                    content.icon_size,
                    pressed == Some(this_slot),
                );
                if let Some(label) = label {
                    icon_label(cr, &label, &content, brush_rgb(theme, "launcher", "text", style.text));
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
    paint_pending_count(cr, width, height, theme, home, &style);

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
    paint_card(cr, theme, "launcher", CardJob::Control, dock_band.0, dock_band.1, dock_band.2, dock_band.3);
    for slot in 0..home_grid::dock_slots(width, height) {
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
                    plate_y + plate_size + visual_inset(cr, 8.0),
                    plate_size,
                    TYPE_CAPTION,
                    brush_rgb(theme, "launcher", "text", style.text),
                );
            }
        }
    }
    // A stationary tap on this bottom handle returns to the retained cards.
    // Dragging up from the same edge continues to open the app drawer.
    color(cr, style.text, 0.65);
    rounded(cr, f64::from(width) / 2.0 - 48.0, f64::from(height) - 14.0, 96.0, 6.0, 3.0);
    cr.fill().ok();
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
        None,
        None,
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
    pointer: Option<(f64, f64)>,
    row_clip: Option<(f64, f64)>,
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
    if let Some(point) = pointer { let _ = cr.target().set_user_data(&HOVER_POINT, Rc::new(point)); }
    if let Some((top, bottom)) = row_clip {
        cr.rectangle(0.0, top, f64::from(width), bottom - top);
        cr.clip();
    }
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
    pointer: Option<(f64, f64)>,
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
    if let Some(point) = pointer { let _ = cr.target().set_user_data(&HOVER_POINT, Rc::new(point)); }
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
    /// Position/pressed-only picker changes since the last paint.
    picker_dirty_rows: u8,
    /// Rows `[top, bottom)` that the last `draw_with_hud` changed, when it
    /// was a drawer scroll band repaint at rest; `None` means the whole
    /// frame may differ. The caller reports this as the surface damage.
    band_damage: Option<(i32, i32)>,
    /// The row shift the last frame was copied with.
    last_shift: i32,
    rebuilds: u64,
    icons: IconCache,
    scroll: f64,
    pressed: Option<usize>,
    pointer: Option<(f64, f64)>,
    home_pointer: Option<(f64, f64)>,
    theme: Option<AppearanceSnapshot>,
    services: Option<ServiceView>,
    wifi_password_preview: Option<Secret>,
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
    /// Which input last bumped `content_generation`, for the
    /// `optimistic-apply shown ... reason=content-changed` log line.
    content_source: &'static str,
    /// Value-based fingerprint of the chooser inputs `theme_view_cache_key_
    /// differs` tracks (page, list, preview, quantised positions, pressed
    /// rows), folded into `content_generation()`. A counter cannot tell a
    /// pressed wash that came and went from a real change: the tap's own
    /// down/up pair bumped it twice and made the browse-time pre-render read
    /// `content-changed` although the view had returned to the identical
    /// state (board 2026-10-12, task 6.6). A fingerprint returns to its old
    /// value when the view does.
    chooser_key: u64,
    /// The list/preview/page part of `chooser_key`, recomputed only when
    /// those fields change so per-frame position updates stay cheap.
    chooser_static_key: u64,
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

fn stable_hash(text: &str) -> u64 {
    use std::hash::Hasher;
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    hasher.write(text.as_bytes());
    hasher.finish()
}

/// Fingerprint of exactly the fields `theme_view_cache_key_differs` compares;
/// positions are quantised to the same quarter-step tolerance. Equal views
/// (by that function's standard) give equal fingerprints.
fn chooser_fingerprint(static_key: u64, view: &ThemeView) -> u64 {
    let quantise = |position: f64| (position * 4.0).round() as i64;
    stable_hash(&format!(
        "{static_key}|{}|{}|{:?}|{:?}|{}",
        quantise(view.theme_position),
        quantise(view.background_position),
        view.theme_pressed,
        view.background_pressed,
        view.scroll.round() as i64
    ))
}

/// Some(mask) only when every rendered input other than row geometry is equal.
/// This is deliberately stricter than optimistic pre-render freshness.
fn picker_row_changes(old: &ThemeView, new: &ThemeView) -> Option<u8> {
    if old.page != ThemePage::List || new.page != ThemePage::List
        || old.list != new.list || old.preview != new.preview
        || old.pending != new.pending || old.pending_id != new.pending_id
        || old.error != new.error || old.message != new.message
        || old.desired != new.desired || old.scroll != new.scroll
    {
        return None;
    }
    // The loading-spinner pulse is painted only inside the two rows.
    let pulse = old.pulse_phase != new.pulse_phase;
    let theme = pulse || old.theme_position != new.theme_position || old.theme_pressed != new.theme_pressed;
    let background = pulse
        || old.background_position != new.background_position
        || old.background_pressed != new.background_pressed;
    Some(u8::from(theme) | (u8::from(background) << 1))
}

/// Integer device-space bands enclose outlines and both row labels.
fn picker_row_clip(mask: u8, width: u32, height: u32, view: Option<&ThemeView>) -> (f64, f64) {
    let lay = view.map_or_else(|| crate::theme_ui::chooser_layout(width, height), |view| view.layout(width, height));
    let top = if mask & 1 != 0 { lay.theme_top - 4.0 } else { lay.background_top - 4.0 };
    let bottom = if mask & 2 != 0 {
        lay.background_top + lay.background_geometry.expanded_h + lay.background_label_h + 4.0
    } else {
        lay.theme_top + lay.theme_geometry.expanded_h + lay.theme_label_h + 4.0
    };
    (top.floor(), bottom.ceil())
}

/// Layout still includes distant slices for painting/hit-testing. Decoding only
/// needs slices whose bounds reach the viewport, across BOTH carousel rows.
/// Rank them together so the two centers reach the bounded worker queue first.
fn theme_picker_working_set(chooser: Option<&ThemeView>, viewport_width: u32, viewport_height: u32) -> Vec<ThumbnailKey> {
    let Some(chooser) = chooser.filter(|view| view.page == ThemePage::List) else {
        return Vec::new();
    };
    if viewport_width == 0 {
        return Vec::new();
    }
    let lay = chooser.layout(viewport_width, viewport_height);
    let mut requested = Vec::new();
    fn add<'a>(
        requested: &mut Vec<(f64, ThumbnailKey)>,
        geometry: &theme_carousel::CarouselGeometry,
        position: f64,
        count: usize,
        center_x: f64,
        cols: (f64, f64),
        row: impl Fn(usize) -> Option<(&'a str, &'a std::path::Path)>,
    ) {
        for slice in theme_carousel::visible_slices(geometry, position, count, center_x, 0.0) {
            if slice.x >= cols.1 || slice.x + slice.width <= cols.0 {
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
            &lay.theme_geometry,
            chooser.theme_position,
            list.themes.len(),
            lay.theme_cx,
            lay.theme_cols,
            |index| {
                let entry = list.themes.get(index)?;
                Some((&entry.id, entry.preview_path.as_deref()?))
            },
        );
    }
    if let Some(preview) = chooser.preview.as_ref() {
        add(
            &mut requested,
            &lay.background_geometry,
            chooser.background_position,
            preview.backgrounds.len(),
            lay.background_cx,
            lay.background_cols,
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
    pub fn set_pointer(&mut self, point: Option<(f64, f64)>, home: bool) -> bool {
        let point = point.filter(|(x, y)| x.is_finite() && y.is_finite());
        let slot = if home { &mut self.home_pointer } else { &mut self.pointer };
        if *slot == point { return false; }
        *slot = point;
        if !home {
            self.content_generation = self.content_generation.wrapping_add(1);
            self.content_source = "set_pointer";
            self.invalidate();
        }
        true
    }
    /// What `content_generation()` is made of, for the optimistic-apply
    /// mismatch log: the bump counter, the input that last bumped it, and
    /// the chooser inputs the fingerprint covers (quantised positions,
    /// pressed rows, a hash of the list/preview/page).
    pub fn content_parts(&self) -> String {
        let (theme, background, theme_pressed, background_pressed) = self.chooser.as_ref().map_or(
            (0, 0, None, None),
            |view| ((view.theme_position * 4.0).round() as i64, (view.background_position * 4.0).round() as i64,
                view.theme_pressed, view.background_pressed),
        );
        format!(
            "counter={}/{} chooser={:016x}/{theme}/{background}/{theme_pressed:?}/{background_pressed:?}",
            self.content_generation, self.content_source, self.chooser_static_key
        )
    }
    /// See `trim_and_report_picker_memory`.
    pub fn picker_memory_report(&self) -> String {
        trim_and_report_picker_memory(self.thumbnails.resident_bytes())
    }
    pub fn content_generation(&self) -> u64 {
        self.content_generation.wrapping_mul(0x9E37_79B9_7F4A_7C15) ^ self.chooser_key
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
        // Recomputed on every update, not only when
        // `theme_view_cache_key_differs` fires: that compares each update
        // with the previous one, so a settle moving in steps under its
        // quarter-item tolerance would leave the fingerprint on a mid-settle
        // position (board 2026-10-12: the browse-time pre-render then read
        // `content-changed` at every tap).
        let static_changed = self.chooser.as_ref().is_none_or(|old| {
            old.page != view.page || old.list != view.list || old.preview != view.preview
        });
        if static_changed {
            self.chooser_static_key =
                stable_hash(&format!("{:?}|{:?}|{:?}", view.page, view.list, view.preview));
        }
        self.chooser_key = chooser_fingerprint(self.chooser_static_key, &view);
        let rows = self.chooser.as_ref().and_then(|old| picker_row_changes(old, &view));
        self.chooser = Some(view);
        if self.route == Some(Route::Settings) && !self.static_pixels.is_empty() {
            if let Some(rows) = rows {
                self.picker_dirty_rows |= rows;
                return;
            }
        }
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
            self.content_source = "poll_theme_image";
        }
        changed
    }
    /// Request exactly the admitted visible working set shared by both rows.
    pub fn poll_theme_thumbnails(&mut self, viewport_width: u32) -> bool {
        let _profile = crate::runtime_trace::Span::new("thumbnail_poll");
        let requested = theme_picker_working_set(self.chooser.as_ref(), viewport_width, self.height);
        self.thumbnails.set_working_set(&requested);
        let changed = self.thumbnails.poll();
        if changed {
            self.content_generation = self.content_generation.wrapping_add(1);
            self.content_source = "poll_theme_thumbnails";
            // Thumbnails are painted only inside the chooser's two rows, so
            // a completion mid-swipe repaints those rows rather than paying
            // a full scene rebuild.
            if self.route == Some(Route::Settings)
                && !self.static_pixels.is_empty()
                && self.chooser.as_ref().is_some_and(|view| view.page == ThemePage::List)
            {
                self.picker_dirty_rows |= 3;
            } else {
                self.invalidate();
            }
        }
        for key in requested {
            self.thumbnails.request(key);
        }
        changed
    }

    /// Offscreen/deferred entries must not keep polling and repainting spinners
    /// forever. Use the identical admitted set as the request path.
    pub fn theme_thumbnails_pending(&self, viewport_width: u32) -> bool {
        theme_picker_working_set(self.chooser.as_ref(), viewport_width, self.height)
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

    pub fn set_wifi_password_preview(&mut self, preview: Option<&str>) {
        self.wifi_password_preview = preview.map(|s| Secret::new(s.to_owned()));
    }

    pub fn set_services(&mut self, services: ServiceView) {
        if !services.wifi.as_ref().is_some_and(|v| v.page == WifiPage::Entry && v.password_visible && !v.use_saved) {
            self.wifi_password_preview = None;
        }
        self.services = Some(services);
        self.content_generation = self.content_generation.wrapping_add(1);
        self.content_source = "set_services";
        self.invalidate();
    }
    pub fn set_drawer_pressed(&mut self, pressed: Option<usize>) -> bool {
        if self.pressed != pressed {
            self.pressed = pressed;
            self.content_generation = self.content_generation.wrapping_add(1);
            self.content_source = "set_drawer_pressed";
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
            self.content_source = "set_drawer_search";
            self.invalidate();
            return true;
        }
        false
    }
    pub fn set_appearance(&mut self, theme: Option<AppearanceSnapshot>) {
        let name = icon_theme_name_for(theme.as_ref());
        self.icons.set_theme(&name);
        crate::set_layout_text_scale(vision_text_scale(theme.as_ref()));
        crate::set_layout_theme_font(theme_base_font(theme.as_ref()));
        self.theme = theme;
        self.drawer_grid.forget_sheet();
        self.invalidate();
    }
    pub fn invalidate(&mut self) {
        self.route = None;
        self.static_pixels.clear();
        self.picker_dirty_rows = 0;
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

    /// See `band_damage`; cleared by the read.
    pub fn take_band_damage(&mut self) -> Option<(i32, i32)> {
        self.band_damage.take()
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
            self.pointer,
            None,
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
        self.picker_dirty_rows = 0;
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

    /// Paints the notification banner (`notification_banner`) onto a canvas
    /// that is exactly the banner's own surface. Text comes only from the
    /// broker's already-filtered preview.
    pub fn draw_notification_banner(
        &mut self,
        canvas: &mut [u8],
        width: u32,
        height: u32,
        preview: &crate::service_data::NotificationPreview,
    ) -> Result<(), String> {
        let size = usize::try_from(width)
            .ok()
            .and_then(|w| w.checked_mul(height as usize))
            .and_then(|pixels| pixels.checked_mul(4))
            .ok_or("invalid banner canvas geometry")?;
        if canvas.len() != size {
            return Err("invalid banner canvas length".into());
        }
        canvas.fill(0);
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
        let theme = self.theme.as_ref();
        attach_theme_metrics(&cr, theme);
        let style = visual_style(theme, "controls");
        let (w, h) = (f64::from(width), f64::from(height));
        let (source, summary) = crate::notification_banner::banner_text(preview);
        rounded(&cr, 0.0, 0.0, w, h, 18.0);
        color(&cr, palette_rgb_or(theme, "background", 0x1e1e2e), 0.96);
        let _ = cr.fill();
        rounded(&cr, 0.5, 0.5, w - 1.0, h - 1.0, 18.0);
        color(&cr, style.muted, 0.45);
        cr.set_line_width(1.0);
        let _ = cr.stroke();
        let painted = preview
            .icon
            .as_deref()
            .is_some_and(|icon| self.icons.paint(&cr, icon, 36, 14.0, (h - 36.0) / 2.0));
        if !painted {
            cr.new_sub_path();
            cr.arc(32.0, h / 2.0, 8.0, 0.0, std::f64::consts::TAU);
            color(&cr, style.accent, 1.0);
            let _ = cr.fill();
        }
        let left = 62.0;
        let pad = crate::notification_banner::PAD_Y;
        let source_h = context_font_size(&cr, TYPE_CAPTION) * 1.25;
        text(&cr, &source, left, pad, w - left - 14.0, TYPE_CAPTION, style.muted);
        text(&cr, &summary, left, pad + source_h + 4.0, w - left - 14.0, TYPE_BODY, style.text);
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
    attach_theme_metrics(cr, theme);
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
        let icon_rgb = if muted { style.muted } else { style.text };
        let speaker = if muted { Glyph::SpeakerMuted } else { Glyph::Speaker };
        glyph::paint(cr, speaker, center_x - 19.0, geometry.top + 11.0, 38.0, icon_rgb, 1.0);
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
        // pill's own top whether or not it is currently expanded. Three
        // dots rather than a glyph: it is a control mark, and a glyph would
        // grow with the text step into the first expanded row.
        color(cr, style.muted, 1.0);
        for dot in 0..3 {
            cr.arc(
                geometry.left + 5.0 + f64::from(dot) * 5.0,
                geometry.top + geometry.collapsed_h - 9.0,
                1.5,
                0.0,
                std::f64::consts::TAU,
            );
            let _ = cr.fill();
        }
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
                    centered_label(
                        cr,
                        &stream
                            .app_name
                            .chars()
                            .next()
                            .unwrap_or('?')
                            .to_uppercase()
                            .to_string(),
                        left,
                        row_top + 10.0,
                        28.0,
                        // Sized to the circle, not the text step: undo the
                        // step that `centered_label` applies.
                        16.0 * 100.0 / context_font_size(cr, 100.0),
                        style.text,
                    );
                }
                hud_row_name(cr, &stream.app_name, left + 36.0, row_top + 4.0, width - 36.0, style.text);
                let percent = volume::linear_to_percent(stream.linear_volume);
                let track_left = left + 36.0;
                let track_right = geometry.left + geometry.width - 12.0;
                let track_w = (track_right - track_left).max(1.0);
                let track_y = row_top + volume::HUD_ROW_H - 18.0;
                rounded(cr, track_left, track_y, track_w, 8.0, 4.0);
                color(cr, style.muted, 0.35);
                let _ = cr.fill();
                let fill_w = track_w * f64::from(percent) / 100.0;
                rounded(cr, track_left, track_y, fill_w.max(8.0), 8.0, 4.0);
                color(cr, if stream.muted { style.muted } else { style.accent }, 1.0);
                let _ = cr.fill();
            }
            crate::pipewire_ipc::ExpandedRow::Sink(sink) => {
                hud_row_name(cr, &sink.description, left, row_top + 4.0, width - 28.0, style.text);
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
        let same_scene = self.route == Some(route) && self.width == width && self.height == height;
        let scrolled = (self.scroll - scroll).abs() >= 0.25;
        self.band_damage = None;
        let mut band = None;
        if same_scene && scrolled && route == Route::Drawer && self.picker_dirty_rows == 0
            && self.pressed.is_none()
        {
            // Only the grid viewport depends on the drawer's scroll, so a
            // scroll frame repaints that band of the cached frame; the
            // chrome and sheet around it stay as last painted. A pressed
            // tile's ring can reach past that band, so it takes a rebuild.
            let _profile = crate::runtime_trace::Span::new("drawer_scroll_repaint");
            let top = navigation::list_top(height).floor();
            let bottom = (f64::from(self.drawer_search.viewport_height(height)) - GRID_BOTTOM_INSET).ceil();
            draw_shm_with_icons(
                &mut self.static_pixels,
                RenderParams { progress: 1.0, ..params },
                apps, &mut self.icons, self.theme.as_ref(), self.services.as_ref(),
                self.chooser.as_ref(), self.preview_surface.as_ref(), self.preview_error,
                Some(&self.thumbnails), self.pressed, &self.drawer_search,
                &mut self.drawer_grid, self.pointer, Some((top, bottom.max(top))),
            )?;
            self.scroll = scroll;
            band = Some((top as i32, bottom.max(top) as i32));
        } else if !same_scene || scrolled {
            let _profile = crate::runtime_trace::Span::new("scene_rebuild");
            let mut painted = vec![0; size];
            card_sprites_scene(|| draw_shm_with_icons(
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
                self.pointer,
                None,
            ))?;
            self.static_pixels = painted;
            self.width = width;
            self.height = height;
            self.route = Some(route);
            self.scroll = scroll;
            self.rebuilds += 1;
            self.picker_dirty_rows = 0;
        } else if self.picker_dirty_rows != 0 {
            let _profile = crate::runtime_trace::Span::new("picker_row_repaint");
            draw_shm_with_icons(
                &mut self.static_pixels,
                RenderParams { progress: 1.0, ..params },
                apps, &mut self.icons, self.theme.as_ref(), self.services.as_ref(),
                self.chooser.as_ref(), self.preview_surface.as_ref(), self.preview_error,
                Some(&self.thumbnails), self.pressed, &self.drawer_search,
                &mut self.drawer_grid, self.pointer, Some(picker_row_clip(self.picker_dirty_rows, width, height, self.chooser.as_ref())),
            )?;
            self.picker_dirty_rows = 0;
        }
        let _profile_copy = crate::runtime_trace::Span::new("canvas_copy");
        let panel_height =
            panel_travel_height(route, width, height, self.chooser.as_ref(), self.services.as_ref());
        let hidden = 1.0 - progress.clamp(0.0, 1.0);
        let shift =
            (hidden * panel_height).round() as i32 * if route == Route::Drawer { 1 } else { -1 };
        let row_bytes = width as usize * 4;
        // Only a sliding panel leaves rows the copy below does not cover.
        if shift != 0 {
            canvas.fill(0);
        }
        if shift == 0 && self.last_shift == 0 && !hud.is_visible(hud_now_ms) {
            self.band_damage = band;
        }
        self.last_shift = shift;
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
        // full rebuild above on semantic changes; row-only updates repaint
        // their geometry and labels under a clip. No separate live status
        // pass is necessary. See
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
        // The production shell now uses its dedicated k230-volume-hud
        // surface on every route. This optional composition path remains for
        // standalone renderer callers; main.rs never paints the HUD twice.
        if route == Route::Settings {
            if let Some(preview) = self.wifi_password_preview.as_ref().filter(|_| {
                self.services.as_ref().and_then(|s| s.wifi.as_ref())
                    .is_some_and(|v| v.page == WifiPage::Entry && v.password_visible && !v.use_saved)
            }) {
                let surface = unsafe { ImageSurface::create_for_data_unsafe(
                    canvas.as_mut_ptr(), Format::ARgb32, width as i32, height as i32, row_bytes as i32,
                ) }.map_err(|e| e.to_string())?;
                let cr = Context::new(&surface).map_err(|e| e.to_string())?;
                cr.translate(0.0, f64::from(shift));
                let lay = crate::wifi_ui::layout_for(width, height, 0.0);
                if !lay.wide {
                    cr.scale(f64::from(width) / 568.0, f64::from(height) / 1232.0);
                }
                attach_theme_metrics(&cr, self.theme.as_ref());
                let style = visual_style(self.theme.as_ref(), "controls");
                text(&cr, preview.as_str(), lay.field.0 + 18.0, lay.field.1 + lay.field_text_dy, lay.field_text_w, TYPE_BODY, style.text);
                drop(cr); surface.flush();
            }
        }
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

    /// Context app actions overlay. It leaves Home/All apps and their layout
    /// intact underneath; outside clicks/Escape dismiss instead of navigating.
    pub fn draw_app_menu(&mut self,canvas:&mut [u8],width:u32,height:u32,menu:&crate::app_actions::AppMenu) -> Result<(),String> {
        let surface=ImageSurface::create(Format::ARgb32,width as i32,height as i32).map_err(|e|e.to_string())?;
        let cr=Context::new(&surface).map_err(|e|e.to_string())?;
        let theme=self.theme.as_ref();
        attach_theme_metrics(&cr, theme);
        if let Some(point) = self.pointer { let _ = cr.target().set_user_data(&HOVER_POINT, Rc::new(point)); }
        paint_scrim(&cr,theme,"menu",f64::from(width),f64::from(height),0,0.32);
        let style=visual_style(theme,"menu");
        let m=crate::app_actions::AppMenu::metrics(width,height);
        let scale=m.scale;
        let (x,y,w,h,row)=menu.geometry(width,height);
        service_card(&cr,theme,"menu",x,y,w,h,false);
        if let Some(icon)=menu.entry.icon.as_deref() {
            self.icons.paint(&cr,icon,(44.0*scale) as i32,x+20.0*scale,y+16.0*scale);
        }
        heading(&cr,&menu.entry.name,x+80.0*scale,y+m.name_y,w-100.0*scale,TYPE_LABEL*scale,style.text);
        let subtitle=match menu.window_state() {
            Some(RecoveryState::WindowsEmpty)=>format!("App actions · {}",RecoveryState::WindowsEmpty.copy()),
            _=>"App actions".to_string(),
        };
        wrapped_text_lines(&cr,&subtitle,x+80.0*scale,y+m.subtitle_y,w-100.0*scale,context_font_size(&cr,TYPE_CAPTION*scale),style.muted,2);
        let top=y+m.header;
        cr.save().map_err(|e|e.to_string())?;
        cr.rectangle(x,top,w,(h-m.header-12.0*scale).max(0.0));cr.clip();
        if menu.rows.is_empty() {
            let copy=if menu.ready {"App actions unavailable"}else{RecoveryState::WindowsLoading.copy()};
            text(&cr,copy,x+24.0*scale,top+m.row_text_dy,w-48.0*scale,TYPE_CAPTION*scale,style.muted);
            text(&cr,crate::recovery::RecoveryAction::Back.label(),x+24.0*scale,top+m.row_text_dy+row,w-48.0*scale,TYPE_LABEL*scale,style.accent);
        }
        for (index,action) in menu.rows.iter().enumerate() {
            let at=top+index as f64*row-menu.scroll;
            if at+row<top || at>y+h {continue;}
            text(&cr,&action.label,x+24.0*scale,at+m.row_text_dy,w-48.0*scale,TYPE_LABEL*scale,
                if matches!(action.action,crate::app_actions::AppAction::NewWindow(_)) {style.accent}else{style.text});
        }
        cr.restore().map_err(|e|e.to_string())?;
        drop(cr);surface.flush();
        let mut surface=surface;
        let data=surface.data().map_err(|e|e.to_string())?;
        if canvas.len()!=data.len() {return Err("app menu canvas mismatch".into());}
        canvas.copy_from_slice(&data);Ok(())
    }

    /// Renders the always-mapped Home layer with its own pager/drag state.
    pub fn draw_home(
        &mut self,
        canvas: &mut [u8],
        width: u32,
        height: u32,
        apps: &[AppEntry],
        home: &HomeScreen,
    ) -> Result<(), String> {
        draw_home_shm(canvas, width, height, apps, &mut self.icons, self.theme.as_ref(), home, self.home_pointer)
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
        SplashStatus::Recovery(state) => {
            3 + crate::recovery::ALL.iter().position(|s| *s == state).unwrap_or(0) as u8
        }
    }
}

/// Centred text, wrapped inside a 24 px margin each side; returns the
/// height it took.
fn draw_centered(cr: &Context, value: &str, y: f64, width: f64, size: f64, rgb: u32) -> f64 {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family(FONT_FAMILY);
    font.set_absolute_size(context_font_size(cr, size) * f64::from(pango::SCALE));
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width(((width - 48.0).max(1.0) * f64::from(pango::SCALE)) as i32);
    layout.set_wrap(pango::WrapMode::WordChar);
    layout.set_alignment(Alignment::Center);
    color(cr, rgb, 1.0);
    cr.move_to(24.0, y);
    pangocairo::functions::show_layout(cr, &layout);
    f64::from(layout.pixel_size().1)
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
    attach_theme_metrics(&cr, theme);
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
        SplashStatus::Recovery(state) => (state.copy().to_string(), style.text),
    };
    // The name or recovery copy in Body, the hints under it in Caption,
    // each wrapping onto as many lines as it needs.
    let mut y = label_y;
    y += draw_centered(&cr, &primary, y, width as f64, TYPE_BODY, primary_color) + 10.0;
    if let SplashStatus::Recovery(state) = status {
        draw_centered(&cr, &state.tap_hint(), y, width as f64, TYPE_CAPTION, style.accent);
    }
    if status == SplashStatus::TimedOut {
        y += draw_centered(&cr, "Taking longer than usual…", y, width as f64, TYPE_CAPTION, style.muted) + 4.0;
        draw_centered(&cr, "Tap to go Home", y, width as f64, TYPE_CAPTION, style.accent);
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

    #[test]
    fn a_stale_window_bakes_its_own_message_not_the_launch_failure() {
        let mut failed: Option<SplashBake> = None;
        ensure_splash_bake(&mut failed, None, "Foot", 200, 200, SplashStatus::Failed).unwrap();
        let mut stale: Option<SplashBake> = None;
        ensure_splash_bake(
            &mut stale,
            None,
            "Foot",
            200,
            200,
            SplashStatus::Recovery(crate::recovery::RecoveryState::WindowStale),
        )
        .unwrap();
        let stale = stale.unwrap();
        assert_ne!(failed.unwrap().pixels, stale.pixels);
        let mut ended: Option<SplashBake> = None;
        ensure_splash_bake(
            &mut ended,
            None,
            "Video",
            200,
            200,
            SplashStatus::Recovery(crate::recovery::RecoveryState::VideoEnded),
        )
        .unwrap();
        assert_ne!(stale.pixels, ended.unwrap().pixels);
    }
}

#[cfg(test)]
mod layout_tests {
    use super::*;

    #[test]
    fn settings_row_y_uses_one_height_and_one_gap() {
        // The header holds a Title line, the Vision and Themes links on
        // their own Label line, and "Device controls" (visual language 2.1).
        assert_eq!(settings_row_y(0), 187.0);
        for row in 0..5 {
            assert_eq!(settings_row_y(row + 1), settings_row_y(row) + settings_row_h(row) + SETTINGS_ROW_GAP);
        }
    }

    #[test]
    fn every_settings_row_holds_its_role_lines() {
        for row in 0..6 {
            let (label, value, caption, slider) = settings_row_lines(row);
            assert_eq!(label, SPACE_BETWEEN_ROWS);
            assert!(value >= label + TYPE_LABEL * 1.25, "row {row}");
            assert!(caption >= value + TYPE_BODY * 1.25, "row {row}");
            assert!(settings_row_h(row) >= SETTINGS_ROW_H, "row {row}");
            if matches!(row, 1 | 2 | SETTINGS_KEY_BACKLIGHT_ROW) {
                assert!(slider - 28.0 >= caption.min(value + TYPE_BODY * 1.25) - 1.0, "row {row}");
            }
        }
    }

    #[test]
    fn settings_rows_bottom_is_the_last_row_end() {
        assert_eq!(settings_rows_bottom(0), settings_first_y());
        assert_eq!(settings_rows_bottom(1), settings_row_y(0) + settings_row_h(0));
        assert_eq!(settings_rows_bottom(4), settings_row_y(3) + settings_row_h(3));
    }

    #[test]
    fn settings_layout_cascades_from_the_row_rhythm() {
        // The Key backlight row, when present, moves the Power section down
        // by its own height and one gap.
        let with_keys = settings_layout(true);
        let layout = settings_layout(false);
        assert_eq!(
            with_keys.power_heading_y,
            layout.power_heading_y + settings_row_h(SETTINGS_KEY_BACKLIGHT_ROW) + SETTINGS_ROW_GAP
        );
        // Date & time and About are always the last rows before Power.
        assert_eq!(
            layout.power_heading_y,
            settings_modem_row_y(false, SETTINGS_INFO_ROWS - 1) + settings_modem_row_h() + 22.0
        );
        assert!(settings_modem_row_y(false, 0) > settings_rows_bottom(SETTINGS_ROW_COUNT));
        assert_eq!(layout.reboot_y, layout.power_heading_y + TYPE_LABEL * 1.25 + SPACE_IN_ROW);
        assert_eq!(layout.poweroff_y, layout.reboot_y + settings_power_card_h() + SETTINGS_ROW_GAP);
        assert_eq!(layout.poweroff_bottom, layout.poweroff_y + settings_power_card_h());
        assert!(settings_power_card_h() >= TYPE_BODY * 1.25 + SPACE_CARD);
    }

    #[test]
    fn settings_confirm_layout_follows_whatever_precedes_it() {
        let confirm = settings_confirm_layout(982.0);
        assert_eq!(confirm.label_y, 996.0);
        assert_eq!(confirm.card_y, 996.0 + TYPE_BODY * 1.25 + SPACE_IN_ROW);
        assert_eq!(confirm.bottom, confirm.card_y + 110.0);
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
    #[test]
    fn clock_date_is_readable_at_every_text_step() {
        let target = ImageSurface::create(Format::ARgb32, 8, 8).unwrap();
        let cr = Context::new(&target).unwrap();
        let date = "Wed, Sep 30";
        for &(w, h) in &[(280.0, 300.0), (250.0, 250.0), (560.0, 300.0), (200.0, 220.0)] {
            let mut last = 0.0;
            for &step in &[1.0, 1.3, 1.6, 2.0] {
                crate::set_layout_text_scale(step);
                let ClockDate { size, top, time_scale: k } = clock_date_metrics(&cr, date, w, h, 0.84);
                let layout = clock_date_layout(&cr, date, size);
                let (_, logical) = layout.pixel_extents();
                let room = w - 2.0 * visual_inset(&cr, 22.0);
                assert!(f64::from(logical.width()) <= room, "{w}x{h} at {step}: date {} wider than {room}", logical.width());
                assert!(top + f64::from(logical.height()) <= h, "{w}x{h} at {step}: date runs off the card");
                assert!(size >= last - 0.5, "{w}x{h} at {step}: date shrank from {last} to {size}");
                let (_, _, _, bubble_bottom) = bubble_lines(w, h, k);
                assert!(bubble_bottom <= top + 1.0, "{w}x{h} at {step}: time overlaps the date");
                if w >= 250.0 && step == 1.0 {
                    assert!(size >= CLOCK_DATE_MIN, "{w}x{h}: date {size} under the floor");
                }
                last = size;
            }
        }
        crate::set_layout_text_scale(1.0);
    }

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
    fn wifi_revealed_input_is_painted_outside_the_scene_cache_and_cleared_on_exit() {
        let mut view = crate::wifi_ui::WifiView::default();
        view.page = WifiPage::Entry;
        view.selected = Some(crate::wifi_settings::Network {
            ssid: "Example".into(), security: Security::Wpa2Psk,
        });
        for c in "sample-pass".chars() { view.key(crate::wifi_ui::Intent::Key(c)); }
        view.toggle_password();
        let services = ServiceView { wifi: Some(view.public()), ..ServiceView::default() };
        let mut renderer = RendererCache::default();
        renderer.set_services(services);
        renderer.set_wifi_password_preview(view.password_preview());
        let params = RenderParams { width: 568, height: 1232, route: Route::Settings, progress: 1.0, scroll: 0.0 };
        let mut first = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut first, params, &[]).unwrap();
        let cache = renderer.static_pixels.clone();
        renderer.set_wifi_password_preview(Some("another-sample"));
        let mut second = first.clone();
        renderer.draw(&mut second, params, &[]).unwrap();
        assert_ne!(first, second);
        assert_eq!(cache, renderer.static_pixels, "revealed input must not enter static scene cache");
        renderer.set_services(ServiceView::default());
        assert!(renderer.wifi_password_preview.is_none());
    }

    #[test]
    fn the_cached_drawer_sheet_copies_the_same_pixels_it_paints() {
        let stop = |offset, argb: &str| BrushStop { offset, argb: argb.into() };
        let snapshot = AppearanceSnapshot {
            generation: "0123456789abcdef0123cafe".into(),
            path: "/tmp/public-visual-fixture".into(),
            icon_theme: None,
            background: None,
            selected_background: None,
            backgrounds: vec![],
            palette: BTreeMap::new(),
            sections: BTreeMap::from([(
                "launcher".into(),
                BTreeMap::from([(
                    "background".into(),
                    AppearanceToken::Brush(Brush {
                        stops: vec![stop(0.0, "#cc172738"), stop(1.0, "#9927394e")],
                        angle_degrees: 35.0,
                        alpha: 0.9,
                    }),
                )]),
            )]),
            applied: vec![],
            unavailable: vec![],
            unknown: vec![],
        };
        for (width, height) in [(568, 1232), (1232, 568)] {
            for theme in [None, Some(&snapshot)] {
                let painted = ImageSurface::create(Format::ARgb32, width, height).unwrap();
                paint_drawer_sheet(&Context::new(&painted).unwrap(), theme, width as u32, height as u32);
                let copied = ImageSurface::create(Format::ARgb32, width, height).unwrap();
                let mut cache = DrawerGridCache::default();
                let (sheet, top) = cache.ensure_sheet(theme, width as u32, height as u32).unwrap();
                copy_drawer_sheet(&Context::new(&copied).unwrap(), sheet, top);
                painted.flush();
                copied.flush();
                let (mut painted, mut copied) = (painted, copied);
                assert!(painted.data().unwrap()[..] == copied.data().unwrap()[..], "{width}x{height}");
            }
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
        let expected_drawer_alpha = snapshot
            .sections
            .get("launcher")
            .and_then(|section| section.get("background"))
            .and_then(|token| match token {
                AppearanceToken::Brush(brush) => Some((255.0 * brush.alpha).round() as u8),
                _ => None,
            })
            .unwrap_or(255);
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
                vision: None,
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
                    adapted: vec![],
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
                assert!(
                    frame[(600 * 568 + 10) * 4 + 3].abs_diff(expected_drawer_alpha) <= 1,
                    "drawer panel alpha must follow the active generation's launcher background"
                );
                assert!(
                    frame[3].abs_diff(expected_drawer_alpha) <= 1,
                    "the drawer sheet reaches the top edge"
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
                vision: None,
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
                adapted: vec![],
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
                vision: None,
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
                adapted: vec![],
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
                    adapted: vec![],
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
                vision: None,
            }),
            ..ThemeView::default()
        }
    }

    fn picker_row_test_renderer(view: &ThemeView) -> RendererCache {
        let (thumbnails, incoming, complete) = ThemeThumbnailCache::fixture();
        let mut renderer = RendererCache { thumbnails, ..RendererCache::default() };
        renderer.set_theme_view(view.clone());
        for _ in 0..100 {
            renderer.poll_theme_thumbnails(568);
            for key in incoming.try_iter() { complete(key); }
            if !renderer.theme_thumbnails_pending(568) { break; }
        }
        assert!(!renderer.theme_thumbnails_pending(568));
        renderer
    }

    /// Host timing of a theme-row swipe (`cargo test ... -- --ignored --nocapture
    /// theme_row_swipe_cost`). Relative costs only; the board is far slower.
    #[test]
    #[ignore]
    fn theme_row_swipe_cost() {
        let mut view = theme_picker_two_row_fixture();
        view.theme_position = 20.0;
        view.background_position = 20.0;
        let mut renderer = picker_row_test_renderer(&view);
        let params = RenderParams { width: 568, height: 1232, route: Route::Settings,
            progress: 1.0, scroll: 0.0 };
        let mut pixels = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut pixels, params, &[]).unwrap();
        let cpu_ms = || {
            let mut now = libc::timespec { tv_sec: 0, tv_nsec: 0 };
            unsafe { libc::clock_gettime(libc::CLOCK_THREAD_CPUTIME_ID, &mut now) };
            now.tv_sec as f64 * 1000.0 + now.tv_nsec as f64 / 1e6
        };
        for (label, moving) in [("theme", true), ("rest", false)] {
            let frames = 60;
            let best = (0..7)
                .map(|_| {
                    let begin = cpu_ms();
                    for frame in 0..frames {
                        view.theme_position = if moving { 20.0 + frame as f64 / 20.0 } else { 23.0 };
                        renderer.set_theme_view(view.clone());
                        renderer.draw(&mut pixels, params, &[]).unwrap();
                    }
                    (cpu_ms() - begin) / frames as f64
                })
                .fold(f64::INFINITY, f64::min);
            eprintln!("{label}: {best:.2} ms/frame thread CPU, best of 7");
        }
    }

    #[test]
    fn card_sprites_keep_only_rest_sizes_through_a_swipe() {
        let mut view = theme_picker_two_row_fixture();
        view.theme_position = 20.0;
        view.background_position = 20.0;
        let mut renderer = picker_row_test_renderer(&view);
        let params = RenderParams { width: 568, height: 1232, route: Route::Settings,
            progress: 1.0, scroll: 0.0 };
        let mut pixels = vec![0; 568 * 1232 * 4];
        for frame in 0..120 {
            view.theme_position = 20.0 + f64::from(frame) / 17.0;
            view.background_position = 20.0 - f64::from(frame) / 13.0;
            renderer.set_theme_view(view.clone());
            renderer.draw(&mut pixels, params, &[]).unwrap();
        }
        let lay = crate::theme_ui::chooser_layout(568, 1232);
        let rest: Vec<(i32, i32)> = [lay.theme_geometry, lay.background_geometry]
            .iter()
            .flat_map(|g| [(g.expanded_w, g.expanded_h), (g.slice_w, g.slice_h)])
            .map(|(w, h)| (w.round() as i32, h.round() as i32))
            .collect();
        CARD_SPRITES.with(|sprites| {
            let sprites = sprites.borrow();
            assert!(!sprites.cards.is_empty());
            assert!(sprites.bytes <= CARD_SPRITE_MAX_BYTES);
            for key in sprites.cards.keys() {
                assert!(rest.contains(&(key.width, key.height)), "kept a transient card {key:?}");
            }
            for &(w, h, _) in sprites.masks.keys() {
                assert!(rest.contains(&(w, h)), "kept a transient mask {w}x{h}");
            }
        });
    }

    #[test]
    fn card_sprites_are_released_once_a_scene_is_built_without_the_picker() {
        let mut view = theme_picker_two_row_fixture();
        view.theme_position = 3.4;
        let mut renderer = picker_row_test_renderer(&view);
        let params = RenderParams { width: 568, height: 1232, route: Route::Settings,
            progress: 1.0, scroll: 0.0 };
        let mut pixels = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut pixels, params, &[]).unwrap();
        CARD_SPRITES.with(|sprites| {
            let sprites = sprites.borrow();
            assert!(sprites.bytes > 0 && sprites.scratch.is_some());
        });
        renderer.draw(&mut pixels, RenderParams { route: Route::Shade, ..params }, &[]).unwrap();
        CARD_SPRITES.with(|sprites| {
            let sprites = sprites.borrow();
            assert!(sprites.cards.is_empty() && sprites.masks.is_empty() && sprites.scratch.is_none());
            assert_eq!(sprites.bytes, 0);
        });
    }

    #[test]
    fn a_card_drawn_through_scratch_matches_its_cached_sprite() {
        let image = ImageSurface::create(Format::ARgb32, 96, 128).unwrap();
        {
            let cr = Context::new(&image).unwrap();
            let gradient = LinearGradient::new(0.0, 0.0, 96.0, 128.0);
            gradient.add_color_stop_rgb(0.0, 0.9, 0.2, 0.1);
            gradient.add_color_stop_rgb(1.0, 0.1, 0.3, 0.8);
            cr.set_source(&gradient).unwrap();
            cr.paint().unwrap();
        }
        let key = CardKey { id: "t".into(), variant: "slice", image: 1, width: 61, height: 233,
            skew: 18 * 16, blend: 20, look: String::new() };
        let draw = |keep: bool| {
            let target = ImageSurface::create(Format::ARgb32, 100, 260).unwrap();
            {
                let cr = Context::new(&target).unwrap();
                cr.set_source_rgb(0.1, 0.1, 0.1);
                cr.paint().unwrap();
                let mut sprites = CardSprites::default();
                sprites.draw(&cr, key.clone(), keep, Some(&image), None, 0x101010, 0, (7.0, 9.0)).unwrap();
                assert_eq!(sprites.cards.is_empty(), !keep);
            }
            target.flush();
            let mut target = target;
            let bytes = target.data().unwrap().to_vec();
            bytes
        };
        let (cached, scratch) = (draw(true), draw(false));
        let worst = cached.iter().zip(&scratch).map(|(a, b)| a.abs_diff(*b)).max().unwrap();
        assert!(worst <= 1, "scratch and cached cards differ by {worst}");
    }

    #[test]
    fn picker_row_repaint_matches_full_scene_for_motion_and_press() {
        let mut view = theme_picker_two_row_fixture();
        view.list.as_mut().unwrap().themes.truncate(4);
        view.preview.as_mut().unwrap().backgrounds.truncate(4);
        view.theme_position = 1.0;
        view.background_position = 1.0;
        let mut partial = picker_row_test_renderer(&view);
        let mut full = picker_row_test_renderer(&view);
        let params = RenderParams { width: 568, height: 1232, route: Route::Settings,
            progress: 1.0, scroll: 0.0 };
        let mut actual = vec![0; 568 * 1232 * 4];
        let mut expected = actual.clone();
        partial.draw(&mut actual, params, &[]).unwrap();
        let initial_rebuilds = partial.rebuild_count();
        for (theme, background, pressed) in [
            (1.0, 1.0, Some(1)), (1.125, 1.0, None), (1.51, 1.0, None),
            (1.25, 1.0, None), (0.0, 1.0, None), (3.0, 1.0, None),
            (3.0, 1.49, None), (3.0, 1.51, None), (3.0, 2.125, None),
            (1.25, 0.0, None), (1.25, 3.0, Some(3)), (1.0, 1.0, None),
        ] {
            view.theme_position = theme; view.background_position = background;
            view.theme_pressed = pressed; view.background_pressed = pressed;
            partial.set_theme_view(view.clone()); full.set_theme_view(view.clone());
            full.invalidate();
            partial.draw(&mut actual, params, &[]).unwrap();
            full.draw(&mut expected, params, &[]).unwrap();
            assert!(actual == expected, "clipped/full pixels differ at {theme}/{background}/{pressed:?}");
        }
        assert_eq!(partial.rebuild_count(), initial_rebuilds);
        // A semantic message invalidates even when both rows have queued damage.
        view.theme_position = 1.75;
        partial.set_theme_view(view.clone());
        view.error = Some("Could not apply".into());
        partial.set_theme_view(view.clone()); full.set_theme_view(view.clone());
        partial.draw(&mut actual, params, &[]).unwrap();
        full.draw(&mut expected, params, &[]).unwrap();
        assert!(actual == expected);
        assert_eq!(partial.rebuild_count(), initial_rebuilds + 1);
        // Route and geometry changes must take the ordinary full scene path.
        for params in [RenderParams { width: 640, height: 1280, ..params },
                       RenderParams { route: Route::Shade, ..params }, params] {
            actual.resize((params.width * params.height * 4) as usize, 0);
            expected.resize(actual.len(), 0);
            partial.draw(&mut actual, params, &[]).unwrap();
            full.invalidate(); full.draw(&mut expected, params, &[]).unwrap();
            assert!(actual == expected);
        }
    }

    #[test]
    fn thumbnail_arrival_and_spinner_pulse_repaint_rows_without_a_rebuild() {
        let mut view = theme_picker_two_row_fixture();
        view.list.as_mut().unwrap().themes.truncate(4);
        view.preview.as_mut().unwrap().backgrounds.truncate(4);
        view.theme_position = 1.25;
        view.background_position = 1.0;
        let params = RenderParams { width: 568, height: 1232, route: Route::Settings,
            progress: 1.0, scroll: 0.0 };
        let (thumbnails, incoming, complete) = ThemeThumbnailCache::fixture();
        let mut partial = RendererCache { thumbnails, ..RendererCache::default() };
        partial.set_theme_view(view.clone());
        let mut actual = vec![0; 568 * 1232 * 4];
        partial.draw(&mut actual, params, &[]).unwrap();
        let rebuilds = partial.rebuild_count();
        // Spinners show for the missing thumbnails; a pulse tick repaints rows only.
        view.pulse_phase = 0.5;
        partial.set_theme_view(view.clone());
        partial.draw(&mut actual, params, &[]).unwrap();
        // Thumbnails then arrive while the row is between slots.
        for _ in 0..100 {
            for key in incoming.try_iter() { complete(key); }
            partial.draw(&mut actual, params, &[]).unwrap();
            if !partial.theme_thumbnails_pending(568) { break; }
        }
        assert!(!partial.theme_thumbnails_pending(568));
        assert_eq!(partial.rebuild_count(), rebuilds, "neither change may rebuild the scene");
        let mut full = picker_row_test_renderer(&view);
        let mut expected = actual.clone();
        full.invalidate();
        full.draw(&mut expected, params, &[]).unwrap();
        assert!(actual == expected, "row repaint must match a full scene");
    }

    #[test]
    fn picker_row_semantic_updates_keep_full_invalidation() {
        let original = theme_picker_two_row_fixture();
        for change in 0..7 {
            let mut view = original.clone();
            match change {
                0 => view.page = ThemePage::Controls,
                1 => view.list.as_mut().unwrap().themes[20].label = "Changed".into(),
                2 => view.preview.as_mut().unwrap().backgrounds[20].selected = false,
                3 => view.message = Some("Background applied".into()),
                4 => view.error = Some("Failed".into()),
                5 => view.pending_id = Some(42),
                _ => view.pending = Some(crate::theme_catalog::ThemeRequest::List),
            }
            assert_eq!(picker_row_changes(&original, &view), None);
        }
        let mut unchanged = original.clone();
        unchanged.prepare_ahead_elapsed_ms += 1;
        assert_eq!(picker_row_changes(&original, &unchanged), Some(0));
        let mut pulsed = original.clone();
        pulsed.pulse_phase = 0.5;
        assert_eq!(picker_row_changes(&original, &pulsed), Some(3), "the spinner pulse repaints only the rows");
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
        let expected = theme_picker_working_set(Some(&view), 568, 1232);
        assert_eq!(expected.len(), 28); // seven hero slices + seven background slices
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
                vision: None,
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
                vision: None,
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
                vision: None,
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
                    adapted: vec![],
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
                    adapted: vec![],
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
        // Rows shifted +76 again along with `notification_top()` itself
        // (task: "volume slider in the shade under the brightness
        // slider" -- room for the second header slider pushed the whole
        // list down once more, from 342 to 418) -- 431+76=507; the keyboard
        // quick toggle moved it again, from 418 to 480 -- 507+62=569.
        let region = (569 * 568 * 4)..(589 * 568 * 4);
        assert!(normal[region.clone()] != failed[region]);
    }

    fn draw_view(route: Route, view: ServiceView) -> Vec<u8> {
        let mut renderer = RendererCache::default();
        renderer.set_services(view);
        let mut frame = vec![0u8; 568 * 1232 * 4];
        renderer
            .draw(
                &mut frame,
                RenderParams { width: 568, height: 1232, route, progress: 1.0, scroll: 0.0 },
                &[],
            )
            .unwrap();
        frame
    }

    fn rows(frame: &[u8], top: usize, bottom: usize) -> &[u8] {
        &frame[top * 568 * 4..bottom * 568 * 4]
    }

    #[test]
    fn the_shade_shows_a_battery_line_only_when_a_battery_exists() {
        use crate::home_widgets::battery::BatteryState;
        let none = draw_view(Route::Shade, ServiceView::default());
        let battery = |percent, status: &str| ServiceView {
            battery: BatteryState::Present { percent, status: status.into() },
            ..ServiceView::default()
        };
        let discharging = draw_view(Route::Shade, battery(64, "Discharging"));
        let charging = draw_view(Route::Shade, battery(64, "Charging"));
        // The battery text sits on the hint line under the Title (y 66..104,
        // a Caption line from 16 + 50 + 2); nothing else moves.
        assert_ne!(rows(&none, 66, 104), rows(&discharging, 66, 104));
        assert_ne!(rows(&discharging, 66, 104), rows(&charging, 66, 104), "charging mark");
        assert_eq!(rows(&none, 0, 66), rows(&discharging, 0, 66));
        assert_eq!(rows(&none, 104, 1232), rows(&discharging, 104, 1232));
        let absent = ServiceView { battery: BatteryState::Absent, ..ServiceView::default() };
        assert_eq!(none, draw_view(Route::Shade, absent), "Absent paints no battery element");
    }

    fn modem_state(edits: &[(&str, serde_json::Value)]) -> crate::modem::ModemStatus {
        let mut state = serde_json::json!({
            "schema": 1, "present": true, "power": "on", "cellular": true, "location": false,
            "sim": "ready", "registration": "registered_home", "operator": "Example Net",
            "rat": "LTE-M", "bars": 3, "gnss": "off", "sms_count": 2
        });
        for (key, value) in edits {
            state[*key] = value.clone();
        }
        crate::modem::parse_status(state.to_string().as_bytes()).unwrap()
    }

    #[test]
    fn the_shade_shows_modem_indicators_only_while_cellular_or_location_is_on() {
        use serde_json::json;
        let shade = |status: Option<crate::modem::ModemStatus>| draw_view(Route::Shade, ServiceView { modem: status, ..ServiceView::default() });
        let none = shade(None);
        let off = modem_state(&[("cellular", json!(false))]);
        assert_eq!(none, shade(Some(off)), "both off: no indicator, nothing else moves");
        let cellular = |bars: u64, reg: &str| shade(Some(modem_state(&[("bars", json!(bars)), ("registration", json!(reg))])));
        let (one, four) = (cellular(1, "registered_home"), cellular(4, "registered_home"));
        // The glyphs sit on the hint line under the Title, as the battery text does.
        assert_ne!(rows(&none, 66, 104), rows(&one, 66, 104));
        assert_ne!(rows(&one, 66, 104), rows(&four, 66, 104), "bars follow the service");
        assert_eq!(rows(&none, 0, 66), rows(&one, 0, 66));
        assert_eq!(rows(&none, 104, 1232), rows(&one, 104, 1232));
        assert_ne!(cellular(0, "registered_home"), cellular(0, "searching"), "no service is not zero bars");
        let location = |gnss: &str| shade(Some(modem_state(&[("cellular", json!(false)), ("location", json!(true)), ("gnss", json!(gnss))])));
        assert_ne!(none, location("searching"));
        assert_ne!(location("searching"), location("fix"), "searching differs from a fix");
        assert_eq!(location("searching"), location("off"), "location on without a fix reads as searching");
        let both = shade(Some(modem_state(&[("location", json!(true)), ("gnss", json!("fix"))])));
        assert_ne!(both, one);
        assert_ne!(both, location("fix"));
    }

    #[test]
    fn settings_shows_cellular_and_location_only_once_the_modem_has_answered() {
        use serde_json::json;
        let view = |modem: Option<crate::modem::ModemStatus>| ServiceView {
            settings: Some(crate::evidence_render::fixture_settings()),
            modem,
            ..ServiceView::default()
        };
        let absent = draw_view(Route::Settings, view(None));
        let on = draw_view(Route::Settings, view(Some(modem_state(&[]))));
        let off = draw_view(Route::Settings, view(Some(modem_state(&[("cellular", json!(false))]))));
        let top = settings_modem_row_y(false, 0) as usize;
        assert_eq!(rows(&absent, 0, top), rows(&on, 0, top), "rows above are untouched");
        assert_ne!(rows(&absent, top, 1232), rows(&on, top, 1232));
        assert_ne!(rows(&on, top, 1232), rows(&off, top, 1232), "the row says what Cellular is doing");
    }

    #[test]
    fn the_cellular_and_location_pages_replace_the_settings_rows() {
        use crate::modem_ui::{ModemView, Page};
        use serde_json::json;
        let page = |status: crate::modem::ModemStatus, which: Page| {
            let mut modem = ModemView::default();
            modem.set_status(Some(status.clone()));
            modem.open(which);
            draw_view(Route::Settings, ServiceView {
                settings: Some(crate::evidence_render::fixture_settings()),
                modem: Some(status),
                modem_page: modem.public(),
                ..ServiceView::default()
            })
        };
        let rows_view = draw_view(Route::Settings, ServiceView {
            settings: Some(crate::evidence_render::fixture_settings()),
            modem: Some(modem_state(&[])),
            ..ServiceView::default()
        });
        let cellular = page(modem_state(&[]), Page::Cellular);
        assert_ne!(rows_view, cellular);
        assert_ne!(cellular, page(modem_state(&[]), Page::Location));
        // No SIM, unknown registration: a plain page with no keypad.
        let no_sim = page(modem_state(&[("sim", json!("absent")), ("registration", json!("unknown")), ("bars", json!(0))]), Page::Cellular);
        let pin = page(modem_state(&[("sim", json!("pin_required")), ("pin_attempts", json!(3))]), Page::Cellular);
        assert_ne!(no_sim, pin, "the keypad appears only when the SIM asks for a PIN");
        let location = |gnss: &str| page(modem_state(&[("cellular", json!(false)), ("location", json!(true)), ("gnss", json!(gnss))]), Page::Location);
        assert_ne!(location("searching"), location("fix"));
    }

    #[test]
    fn settings_shows_the_key_backlight_row_only_when_the_led_exists() {
        let view = |key_backlight| ServiceView {
            settings: Some(crate::evidence_render::fixture_settings()),
            key_backlight,
            ..ServiceView::default()
        };
        let top = settings_row_y(SETTINGS_KEY_BACKLIGHT_ROW) as usize;
        let row = (top, top + SETTINGS_ROW_H as usize);
        let absent = draw_view(Route::Settings, view(None));
        use crate::keyboard_base::KeyBacklight;
        let on = draw_view(Route::Settings, view(Some(KeyBacklight::High)));
        let off = draw_view(Route::Settings, view(Some(KeyBacklight::Off)));
        let low = draw_view(Route::Settings, view(Some(KeyBacklight::Low)));
        assert_ne!(rows(&absent, row.0, row.1), rows(&on, row.0, row.1));
        assert_ne!(rows(&on, row.0, row.1), rows(&off, row.0, row.1), "High differs from Off");
        assert_ne!(rows(&on, row.0, row.1), rows(&low, row.0, row.1), "High differs from Low");
        assert_eq!(rows(&absent, 0, row.0), rows(&on, 0, row.0), "rows above are untouched");
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
                    route: None,
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
        // The empty-state tile now sits where the list starts
        // (`notification_top()`, 480) instead of at 262: 296-262+480 = 514.
        let pixel = (514 * 568 + 59) * 4;
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
        assert_eq!(&frame[0..4], &[0, 0, 255, 255], "the sheet reaches the top edge");
        renderer.draw_wallpaper(&mut frame, 568, 1232).unwrap();
        assert_eq!(&frame[0..4], &[0, 0, 255, 255]);
    }

    #[test]
    fn drawer_sheet_covers_the_output_from_its_top_edge() {
        let apps = vec![AppEntry {
            id: "foot.desktop".into(),
            name: "Terminal".into(),
            icon: Some("foot".into()),
            path: PathBuf::new(),
        }];
        let mut frame = vec![0; 568 * 1232 * 4];
        draw_shm(&mut frame, 568, 1232, Route::Drawer, &apps, 1.0).unwrap();
        assert_eq!(frame[3], 255, "no live scene shows above the sheet");
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
        // The scroll repainted only the grid band, not the whole scene.
        assert_eq!(cache.rebuild_count(), 1);
        // That band repaint matches a frame built from scratch at the same
        // scroll, fractional offsets included.
        for scroll in [188.0, 251.6] {
            cache.draw(&mut frame, RenderParams { scroll, ..params }, &apps).unwrap();
            let mut fresh = vec![0; frame.len()];
            RendererCache::default()
                .draw(&mut fresh, RenderParams { scroll, ..params }, &apps)
                .unwrap();
            assert!(frame == fresh, "band repaint differs from a rebuild at scroll {scroll}");
        }
        assert_eq!(cache.rebuild_count(), 1);
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
        let dark = fixture_theme("dark-generation", (28, 28, 46));
        let light = fixture_theme("light-generation", (239, 241, 245));
        cache.ensure(&content, Some(&dark), 568, 1232, &mut icons);
        assert_eq!(cache.rebuilds(), 1);

        // Same generation and content: a cache hit, not a rebuild.
        cache.ensure(&content, Some(&dark), 568, 1232, &mut icons);
        assert_eq!(cache.rebuilds(), 1);

        // A committed appearance generation repaints drawer chrome even
        // when the catalog, width and query are unchanged.
        cache.ensure(&content, Some(&light), 568, 1232, &mut icons);
        assert_eq!(cache.rebuilds(), 2);

        // A different width changes the key.
        cache.ensure(&content, Some(&light), 600, 1232, &mut icons);
        assert_eq!(cache.rebuilds(), 3);

        // A different query changes the key, even over the same apps.
        let filtered_search = DrawerSearch {
            query: "alpha".into(),
            focused: false,
            ..DrawerSearch::default()
        };
        let filtered_content = DrawerContent {
            apps: vec![&apps[0]],
            search: &filtered_search,
        };
        cache.ensure(&filtered_content, Some(&light), 600, 1232, &mut icons);
        assert_eq!(cache.rebuilds(), 4);
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
                adapted: vec![],
                applied: vec![],
                unavailable: vec![],
                unknown: vec![],
            },
            activated: false,
            app_appearance: None,
        }
    }

    #[test]
    fn content_generation_follows_a_settle_made_of_small_steps() {
        let mut renderer = RendererCache::default();
        let mut view = ThemeView {
            page: ThemePage::List,
            preview: Some(fixture_preview("aaaaaaaaaaaaaaaaaaaaaaaa")),
            theme_position: 2.0,
            ..ThemeView::default()
        };
        renderer.set_theme_view(view.clone());
        let at_two = renderer.content_generation();
        // A settle from 0.6 to 1.0 in steps far under the quarter-item
        // tolerance, then the view at rest on item 1.
        view.theme_position = 0.6;
        renderer.set_theme_view(view.clone());
        for step in 1..=20 {
            view.theme_position = 0.6 + 0.02 * f64::from(step);
            renderer.set_theme_view(view.clone());
        }
        let settled = renderer.content_generation();
        assert_ne!(settled, at_two);
        let mut fresh = RendererCache::default();
        fresh.set_theme_view(view.clone());
        assert_eq!(settled, fresh.content_generation(), "a settled view must fingerprint as itself");
        // A tap's press and release then leave it unchanged.
        view.theme_pressed = Some(1);
        renderer.set_theme_view(view.clone());
        view.theme_pressed = None;
        renderer.set_theme_view(view);
        assert_eq!(renderer.content_generation(), settled);
    }

    #[test]
    fn a_pressed_wash_that_came_and_went_leaves_content_generation_unchanged() {
        // Board 2026-10-12 (task 6.6): the tap's own down/up pair toggled
        // `theme_pressed` Some then None. A bump-per-change counter read
        // that as `content-changed` and discarded the browse-time
        // pre-render even though the chooser had returned to the identical
        // view. The fingerprint must return to its old value, while a
        // real difference (pressed held, new preview, moved carousel) must not.
        let mut renderer = RendererCache::default();
        let view = ThemeView {
            page: ThemePage::List,
            preview: Some(fixture_preview("aaaaaaaaaaaaaaaaaaaaaaaa")),
            ..ThemeView::default()
        };
        renderer.set_theme_view(view.clone());
        let at_rest = renderer.content_generation();

        let mut pressed = view.clone();
        pressed.theme_pressed = Some(1);
        renderer.set_theme_view(pressed);
        assert_ne!(renderer.content_generation(), at_rest, "a held press is different content");

        let mut moved = view.clone();
        moved.theme_position = 2.0;
        renderer.set_theme_view(moved);
        assert_ne!(renderer.content_generation(), at_rest);

        renderer.set_theme_view(view.clone());
        assert_eq!(renderer.content_generation(), at_rest, "released press: identical view, identical content");

        let mut different = view.clone();
        different.preview = Some(fixture_preview("bbbbbbbbbbbbbbbbbbbbbbbb"));
        renderer.set_theme_view(different);
        assert_ne!(renderer.content_generation(), at_rest);
        renderer.set_theme_view(view);
        assert_eq!(renderer.content_generation(), at_rest);

        // Other inputs still bump irreversibly.
        renderer.set_services(ServiceView::default());
        assert_ne!(renderer.content_generation(), at_rest);
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
    #[test]
    fn drawer_preserves_authored_gradient_and_alpha_without_an_opaque_mask() {
        let mut theme = fixture_theme("quiet-drawer", (16, 24, 32));
        theme.sections.insert("launcher".into(), BTreeMap::from([(
            "background".into(), AppearanceToken::Brush(Brush {
                stops: vec![BrushStop {offset: 0.0, argb: "#ff204060".into()},
                            BrushStop {offset: 1.0, argb: "#ff80a0c0".into()}],
                angle_degrees: 0.0, alpha: 0.4,
            })
        )]));
        let mut renderer = RendererCache::default();
        renderer.set_appearance(Some(theme));
        let mut pixels = vec![0; 568 * 1232 * 4];
        renderer.draw(&mut pixels, RenderParams {width:568, height:1232,
            route:Route::Drawer, progress:1.0, scroll:0.0}, &[]).unwrap();
        let at = |x: usize| &pixels[(900 * 568 + x) * 4..(900 * 568 + x) * 4 + 4];
        assert_eq!(at(40)[3], 102, "authored alpha must reach the compositor");
        assert_eq!(at(520)[3], 102);
        assert!(at(520)[2] > at(40)[2] + 20, "all gradient stops must survive");
    }

    #[test]
    fn quiet_control_respects_a_theme_authored_zero_fill() {
        let mut theme = fixture_theme("no-tint", (32, 64, 96));
        theme.sections.get_mut("controls").unwrap().insert(
            "normal-fill-alpha".into(), AppearanceToken::Number(0.0));
        let surface = ImageSurface::create(Format::ARgb32, 120, 80).unwrap();
        let cr = Context::new(&surface).unwrap();
        service_card(&cr, Some(&theme), "controls", 0.0, 0.0, 120.0, 80.0, false);
        drop(cr);
        let mut surface = surface;
        let data = surface.data().unwrap();
        assert_eq!(&data[(40 * 120 + 60) * 4..(40 * 120 + 60) * 4 + 4], &[96, 64, 32, 255]);
    }

    #[test]
    fn theme_hover_focus_brushes_and_independent_border_widths_reach_pixels() {
        let mut theme = fixture_theme("interaction", (32, 64, 96));
        let brush = |rgb: &str, alpha| AppearanceToken::Brush(Brush {
            stops: vec![BrushStop { offset: 0.0, argb: rgb.into() },
                        BrushStop { offset: 1.0, argb: "#ffffffff".into() }],
            angle_degrees: 45.0, alpha,
        });
        theme.sections.get_mut("controls").unwrap().extend([
            ("hover-cursor-color".into(), brush("#ffff0000", 1.0)),
            ("hover-cursor-fill-alpha".into(), AppearanceToken::Number(0.3)),
            ("hover-cursor-border".into(), brush("#ff0000ff", 0.6)),
            ("hover-cursor-border-width".into(), AppearanceToken::Width([1.0, 2.0, 3.0, 4.0])),
            ("focus-color".into(), brush("#ff00ff00", 1.0)),
            ("focus-fill-alpha".into(), AppearanceToken::Number(0.3)),
            ("focus-border".into(), brush("#ff00ffff", 0.5)),
            ("focus-border-width".into(), AppearanceToken::Width([4.0, 3.0, 2.0, 1.0])),
        ]);
        let paint = |theme: &AppearanceSnapshot, point, focus| {
            let mut surface = ImageSurface::create(Format::ARgb32, 120, 80).unwrap();
            let cr = Context::new(&surface).unwrap();
            if let Some(point) = point { cr.target().set_user_data(&HOVER_POINT, Rc::new(point)).unwrap(); }
            // Real render roots transform their reference layout; the pointer
            // must be tested in that space rather than compared to raw pixels.
            cr.translate(8.0, 4.0);
            service_card_interaction(&cr, Some(theme), "controls", 0.0, 0.0, 104.0, 72.0, false, false, focus);
            drop(cr);
            let pixels = surface.data().unwrap().to_vec();
            pixels
        };
        let idle = paint(&theme, None, false);
        assert_eq!(idle, paint(&theme, Some((2.0, 2.0)), false), "outside hover must not change the card");
        let hover = paint(&theme, Some((40.0, 40.0)), false);
        let focus = paint(&theme, Some((40.0, 40.0)), true);
        assert_ne!(idle, hover);
        assert_ne!(hover, focus, "owned focus wins over hover");
        theme.sections.get_mut("controls").unwrap().insert("hover-cursor-border-width".into(), AppearanceToken::Width([0.0; 4]));
        assert_ne!(hover, paint(&theme, Some((40.0, 40.0)), false), "per-side state outlines must be painted");
    }

    #[test]
    fn theme_base_font_reaches_non_settings_scenes_and_remains_isolated() {
        let baseline = fixture_theme("metrics-baseline", (32, 64, 96));
        let mut adapted = baseline.clone();
        adapted.sections.insert("font".into(), BTreeMap::from([
            ("base-size".into(), AppearanceToken::Number(15.0)),
        ]));
        adapted.sections.insert("spacing".into(), BTreeMap::from([
            ("scale-with-font".into(), AppearanceToken::Boolean(false)),
        ]));
        let render = |theme: &AppearanceSnapshot, route| {
            let mut cache = RendererCache::default();
            cache.set_appearance(Some(theme.clone()));
            let mut pixels = vec![0; 568 * 1232 * 4];
            cache.draw(&mut pixels, RenderParams { width: 568, height: 1232, route, progress: 1.0, scroll: 0.0 }, &[]).unwrap();
            pixels
        };
        for route in [Route::Drawer, Route::Shade, Route::Help, Route::Power] {
            let old = render(&baseline, route);
            assert_ne!(old, render(&adapted, route), "font.base-size must reach {route:?}");
            assert_eq!(old, render(&baseline, route), "another renderer must not inherit an adapted surface's metrics");
        }
    }

    #[test]
    fn the_vision_text_step_enlarges_text_everywhere_including_themed_rows() {
        let baseline = fixture_theme("vision-baseline", (32, 64, 96));
        let mut large = baseline.clone();
        large.sections.insert("accessibility".into(), BTreeMap::from([
            ("text-scale".into(), AppearanceToken::Number(2.0)),
            ("high-contrast".into(), AppearanceToken::Boolean(false)),
        ]));
        let mut huge = baseline.clone();
        huge.sections.insert("accessibility".into(), BTreeMap::from([
            ("text-scale".into(), AppearanceToken::Number(9.0)),
        ]));
        let render = |theme: &AppearanceSnapshot, route| {
            let mut cache = RendererCache::default();
            cache.set_appearance(Some(theme.clone()));
            let mut pixels = vec![0; 568 * 1232 * 4];
            cache.draw(&mut pixels, RenderParams { width: 568, height: 1232, route, progress: 1.0, scroll: 0.0 }, &[]).unwrap();
            pixels
        };
        for route in [Route::Drawer, Route::Shade, Route::Settings, Route::Power] {
            let old = render(&baseline, route);
            let bigger = render(&large, route);
            assert_ne!(old, bigger, "accessibility.text-scale must reach {route:?}");
            assert_eq!(bigger, render(&huge, route), "the vision step is bounded at 2.0 on {route:?}");
        }
        // Themed labels (role-sized, then clamped) still get the step.
        assert_eq!(theme_font_size(Some(&baseline), "body", 18.0, 14.0, 18.0), 18.0);
        assert_eq!(theme_font_size(Some(&large), "body", 18.0, 14.0, 18.0), 36.0);
    }

    #[test]
    fn a_hud_stream_initial_stays_a_letter_at_the_largest_text_step() {
        let surface = ImageSurface::create(Format::ARgb32, 240, 60).unwrap();
        let _ = surface.set_user_data(&THEME_METRICS, std::rc::Rc::new(ThemeMetrics { font: 2.0, spacing: 1.0 }));
        {
            let cr = Context::new(&surface).unwrap();
            let style = visual_style(None, "controls");
            let geometry = volume::HudGeometry { left: 0.0, top: 0.0, width: 240.0, height: 60.0, collapsed_h: 0.0 };
            let stream = crate::pipewire_ipc::Stream {
                id: 1, app_name: "PipeWire ALSA".into(), app_icon: None, linear_volume: 0.5, muted: false,
            };
            RendererCache::paint_hud_row(&mut IconCache::new(), &cr, style, &geometry, 0.0,
                                    crate::pipewire_ipc::ExpandedRow::Stream(&stream));
        }
        surface.flush();
        let stride = surface.stride() as usize;
        let data = surface.take_data().unwrap();
        // Bright text pixels inside the 28 px icon circle at x 12..40.
        let rows: Vec<usize> = (6..34)
            .filter(|y| (12..40).any(|x| data[y * stride + x * 4 + 1] > 180))
            .collect();
        let span = rows.last().unwrap_or(&0) - rows.first().unwrap_or(&0);
        // An ellipsis is a 2 px row of dots; a capital letter is most of the circle.
        assert!(span >= 9, "the initial collapsed to an ellipsis: rows {rows:?}");
    }

    #[test]
    fn the_battery_ring_percentage_stays_inside_the_ring_at_the_larger_text_step() {
        let surface = ImageSurface::create(Format::ARgb32, 8, 8).unwrap();
        let _ = surface.set_user_data(&THEME_METRICS, std::rc::Rc::new(ThemeMetrics { font: 1.25, spacing: 1.0 }));
        let cr = Context::new(&surface).unwrap();
        for radius in [24.0, 40.0, 60.0] {
            let design = (radius * 0.68f64).max(13.0);
            assert!(text_advance(&cr, "100%", design, pango::Weight::Bold) > radius * 1.5,
                    "the unfitted label overflows at r={radius}");
            let size = ring_label_size(&cr, "100%", design, radius);
            assert!(text_advance(&cr, "100%", size, pango::Weight::Bold) <= radius * 1.5 + 1.0, "r={radius}");
        }
    }

    #[test]
    fn theme_hover_invalidates_candidate_cache_without_activating_or_changing_search() {
        let mut cache = RendererCache::default();
        let start = cache.content_generation();
        assert!(cache.set_pointer(Some((40.0, 40.0)), false));
        assert_ne!(start, cache.content_generation());
        let changed = cache.content_generation();
        assert!(!cache.set_pointer(Some((40.0, 40.0)), false));
        assert_eq!(changed, cache.content_generation());
        assert!(cache.set_pointer(Some((40.0, 40.0)), true));
        assert_eq!(changed, cache.content_generation(), "Home hover does not invalidate an unrelated overlay candidate");
        assert!(!cache.drawer_search.focused);
        assert!(cache.chooser.is_none());
        assert!(cache.set_pointer(Some((f64::NAN, 40.0)), false));
        assert!(cache.pointer.is_none(), "invalid or removed pointer must clear hover");
    }

    /// Groups of accent-coloured pixels in a frame: 8 px cells holding any
    /// pixel within a small distance of `accent`, joined when within two
    /// cells, so the words of one label are one group.
    fn accent_groups(frame: &[u8], width: usize, height: usize, accent: u32) -> usize {
        let (ar, ag, ab) = ((accent >> 16) as i32 & 0xff, (accent >> 8) as i32 & 0xff, accent as i32 & 0xff);
        let cell = 8;
        let (cw, ch) = (width.div_ceil(cell), height.div_ceil(cell));
        let mut on = vec![false; cw * ch];
        for y in 0..height {
            for x in 0..width {
                let i = (y * width + x) * 4;
                let (b, g, r) = (frame[i] as i32, frame[i + 1] as i32, frame[i + 2] as i32);
                if (r - ar).abs() + (g - ag).abs() + (b - ab).abs() <= 30 {
                    on[(y / cell) * cw + x / cell] = true;
                }
            }
        }
        let mut groups = 0;
        for start in 0..on.len() {
            if !on[start] {
                continue;
            }
            groups += 1;
            let mut stack = vec![start];
            on[start] = false;
            while let Some(index) = stack.pop() {
                let (cx, cy) = ((index % cw) as i64, (index / cw) as i64);
                for dy in -2..=2 {
                    for dx in -2..=2 {
                        let (nx, ny) = (cx + dx, cy + dy);
                        if nx >= 0 && ny >= 0 && (nx as usize) < cw && (ny as usize) < ch {
                            let next = ny as usize * cw + nx as usize;
                            if on[next] {
                                on[next] = false;
                                stack.push(next);
                            }
                        }
                    }
                }
            }
        }
        groups
    }

    #[test]
    fn the_accent_marks_only_the_current_choice_on_settings_vision_and_the_shade() {
        use crate::service_data::{ControlState, NotificationSnapshot};
        // No sliders: a slider's filled track is its own current value and
        // is counted apart from this rule. Brightness read only, no audio.
        let mut settings = crate::evidence_render::fixture_settings();
        settings.brightness.state = ControlState::ReadOnly;
        let services = ServiceView {
            settings: Some(settings),
            notifications: Some(NotificationSnapshot {
                count: 2,
                events: crate::evidence_render::fixture_notification_events(2),
                preview: None,
            }),
            ..ServiceView::default()
        };
        let accent = visual_style(None, "controls").accent;
        for (width, height) in [(568u32, 1232u32), (1232, 568)] {
            let draw = |route, vision: bool| {
                let mut renderer = RendererCache::default();
                renderer.set_services(services.clone());
                if vision {
                    renderer.set_theme_view(ThemeView {
                        page: ThemePage::Vision,
                        vision_loaded: true,
                        ..ThemeView::default()
                    });
                }
                let mut frame = vec![0; (width * height * 4) as usize];
                renderer
                    .draw(&mut frame, RenderParams { width, height, route, progress: 1.0, scroll: 0.0 }, &[])
                    .unwrap();
                accent_groups(&frame, width as usize, height as usize, accent)
            };
            // Links, Done, Close and a row's source are in the foreground
            // colour; Settings has no current choice, and the Shade's one
            // accent is its primary action, Dismiss all.
            assert_eq!(draw(Route::Settings, false), 0, "Settings at {width}x{height}");
            assert_eq!(draw(Route::Shade, false), 1, "Shade at {width}x{height}");
            // Vision: only the chosen text step.
            assert_eq!(draw(Route::Settings, true), 1, "Vision at {width}x{height}");
        }
    }

    #[test]
    fn theme_scrim_preserves_gradient_and_authored_opacity() {
        let mut theme = fixture_theme("scrim", (32, 64, 96));
        theme.sections.insert("menu".into(), BTreeMap::from([("scrim".into(), AppearanceToken::Brush(Brush {
            stops: vec![BrushStop { offset: 0.0, argb: "#ffff0000".into() },
                        BrushStop { offset: 1.0, argb: "#ff0000ff".into() }],
            angle_degrees: 0.0, alpha: 0.4,
        }))]));
        let mut surface = ImageSurface::create(Format::ARgb32, 100, 40).unwrap();
        let cr = Context::new(&surface).unwrap();
        paint_scrim(&cr, Some(&theme), "menu", 100.0, 40.0, 0, 0.32);
        drop(cr);
        let pixels = surface.data().unwrap();
        assert!((100..=103).contains(&pixels[3]), "theme alpha must replace fixed fallback alpha");
        assert_ne!(&pixels[0..3], &pixels[396..399], "gradient stops must survive scrim painting");
    }

    #[test]
    fn theme_font_and_spacing_adapt_with_touch_geometry_preserved() {
        let mut theme = fixture_theme("metrics", (32, 64, 96));
        theme.sections.insert("font".into(), BTreeMap::from([
            ("base-size".into(), AppearanceToken::Number(15.0)),
            ("body".into(), AppearanceToken::Number(20.0)),
            ("caption".into(), AppearanceToken::Number(12.0)),
        ]));
        theme.sections.insert("spacing".into(), BTreeMap::from([
            ("scale".into(), AppearanceToken::Number(1.1)),
        ]));
        assert_eq!(theme_font_size(Some(&theme), "body", 19.0, 14.0, 24.0), 20.0);
        assert_eq!(theme_font_size(Some(&theme), "heading", 19.0, 16.0, 24.0), 23.75);
        assert_eq!(theme_font_size(None, "body", 19.0, 14.0, 24.0), 19.0);
        assert_eq!(theme_settings_row_padding(Some(&theme)), 22.5);
        theme.sections.get_mut("spacing").unwrap().insert("scale-with-font".into(), AppearanceToken::Boolean(false));
        assert_eq!(theme_settings_row_padding(Some(&theme)), 19.8);
        assert_eq!(theme_settings_row_padding(None), 18.0);
        assert_eq!(settings_row_y(1), settings_row_y(0) + settings_row_h(0) + SETTINGS_ROW_GAP,
                   "theme spacing does not move touch rows");
        // A theme can enlarge a type role but never set it below the role.
        assert_eq!(theme_font_size(Some(&theme), "body", TYPE_BODY, TYPE_BODY, TYPE_BODY * 1.25), TYPE_BODY);
        assert_eq!(theme_font_size(Some(&theme), "caption", TYPE_CAPTION, TYPE_CAPTION, TYPE_CAPTION * 1.25), TYPE_CAPTION);

        fn label(theme: Option<&AppearanceSnapshot>) -> Vec<u8> {
            let mut surface = ImageSurface::create(Format::ARgb32, 240, 56).unwrap();
            let cr = Context::new(&surface).unwrap();
            // `font.base-size` 15 enlarges the role by 15/12.
            themed_role(&cr, theme, "heading", "Brightness", 12.0, 10.0, 216.0, TYPE_LABEL, 0xffffff, pango::Weight::Normal);
            drop(cr);
            let pixels = surface.data().unwrap().to_vec();
            pixels
        }
        assert_ne!(label(None), label(Some(&theme)), "the font token must affect rendered glyph pixels");
    }

    #[test]
    fn pressed_home_cards_consume_authored_pressed_fill_without_selection() {
        let mut theme = fixture_theme("pressed", (32, 64, 96));
        theme.sections.get_mut("controls").unwrap().extend([
            ("normal-color".into(), AppearanceToken::Brush(Brush { stops: vec![BrushStop { offset: 0.0, argb: "#ffff0000".into() }], angle_degrees: 0.0, alpha: 1.0 })),
            ("normal-fill-alpha".into(), AppearanceToken::Number(0.0)),
            ("pressed-fill-alpha".into(), AppearanceToken::Number(0.65)),
            ("selected-fill-alpha".into(), AppearanceToken::Number(0.0)),
            ("selected-border-width".into(), AppearanceToken::Width([0.0; 4])),
        ]);
        fn card(theme: &AppearanceSnapshot, pressed: bool) -> Vec<u8> {
            let mut surface = ImageSurface::create(Format::ARgb32, 120, 80).unwrap();
            let cr = Context::new(&surface).unwrap();
            service_card_state(&cr, Some(theme), "launcher", 0.0, 0.0, 120.0, 80.0, false, pressed);
            drop(cr);
            let pixels = surface.data().unwrap().to_vec();
            pixels
        }
        assert_ne!(card(&theme, false), card(&theme, true));
        assert_eq!(settings_row_y(1), settings_row_y(0) + settings_row_h(0) + SETTINGS_ROW_GAP);
    }

    #[test]
    fn system_theme_roles_reach_real_settings_and_shade_pixels() {
        fn token(rgb: &str, alpha: f64) -> AppearanceToken {
            AppearanceToken::Brush(Brush { stops: vec![BrushStop {
                offset: 0.0, argb: rgb.into(),
            }], angle_degrees: 0.0, alpha })
        }
        fn panel(theme: &AppearanceSnapshot, route: Route) -> Vec<u8> {
            let mut renderer = RendererCache::default();
            renderer.set_appearance(Some(theme.clone()));
            // One notification, so the Shade shows its accent action.
            renderer.set_services(ServiceView {
                notifications: Some(crate::service_data::NotificationSnapshot {
                    count: 1,
                    events: crate::evidence_render::fixture_notification_events(1),
                    preview: None,
                }),
                ..ServiceView::default()
            });
            let mut pixels = vec![0; 568 * 1232 * 4];
            renderer.draw(&mut pixels, RenderParams { route, ..SETTINGS_PARAMS }, &[]).unwrap();
            pixels
        }
        fn card(theme: &AppearanceSnapshot, selected: bool) -> Vec<u8> {
            let mut surface = ImageSurface::create(Format::ARgb32, 160, 100).unwrap();
            let cr = Context::new(&surface).unwrap();
            service_card(&cr, Some(theme), "controls", 0.0, 0.0, 160.0, 100.0, selected);
            drop(cr);
            let pixels = surface.data().unwrap().to_vec();
            pixels
        }
        let mut theme = fixture_theme("aaaaaaaaaaaaaaaaaaaaaaaa", (16, 24, 32));
        theme.sections.get_mut("controls").unwrap().extend([
            ("normal-color".into(), token("#ffdd8844", 1.0)),
            ("normal-fill-alpha".into(), AppearanceToken::Number(0.25)),
            ("selected-color".into(), token("#ff44aadd", 1.0)),
            ("selected-fill-alpha".into(), AppearanceToken::Number(0.35)),
            ("selected-border".into(), token("#ffcc55ee", 1.0)),
            ("selected-border-width".into(), AppearanceToken::Width([3.0; 4])),
        ]);
        theme.sections.insert("notifications".into(), BTreeMap::from([
            ("background".into(), token("#ff183044", 0.85)),
            ("text".into(), token("#ffeeccee", 1.0)),
            ("countdown".into(), token("#ff55ddaa", 1.0)),
        ]));
        for (section, key, replacement, selected) in [
            ("controls", "normal-color", token("#ff2266bb", 1.0), false),
            ("controls", "normal-fill-alpha", AppearanceToken::Number(0.0), false),
            ("controls", "selected-color", token("#ffcc7722", 1.0), true),
            ("controls", "selected-fill-alpha", AppearanceToken::Number(0.0), true),
            ("controls", "selected-border", token("#ff2255aa", 1.0), true),
            ("controls", "selected-border-width", AppearanceToken::Width([0.0; 4]), true),
        ] {
            let before = card(&theme, selected);
            let mut changed = theme.clone();
            changed.sections.get_mut(section).unwrap().insert(key.into(), replacement);
            assert_ne!(before, card(&changed, selected), "{section}.{key} must change painted pixels");
        }
        // The selected color must not alter an ordinary row's appearance.
        let mut selected_only = theme.clone();
        selected_only.sections.get_mut("controls").unwrap().insert("selected-color".into(), token("#ffff0000", 1.0));
        assert_eq!(card(&theme, false), card(&selected_only, false));
        for (section, key, replacement, route) in [
            ("controls", "background", token("#ff503020", 1.0), Route::Settings),
            ("controls", "normal-color", token("#ff2266bb", 1.0), Route::Settings),
            ("notifications", "background", token("#ff332255", 0.85), Route::Shade),
            ("notifications", "background", token("#ff183044", 0.25), Route::Shade),
            ("notifications", "text", token("#ff22bb66", 1.0), Route::Shade),
            ("notifications", "countdown", token("#ffcc5522", 1.0), Route::Shade),
        ] {
            let before = panel(&theme, route);
            let mut changed = theme.clone();
            changed.sections.get_mut(section).unwrap().insert(key.into(), replacement);
            assert_ne!(before, panel(&changed, route), "{section}.{key} must reach the actual route renderer");
        }
    }

    #[test]
    fn system_theme_swap_and_rollback_restore_settings_and_shade() {
        for route in [Route::Settings, Route::Shade] {
            let mut dark = fixture_theme("aaaaaaaaaaaaaaaaaaaaaaaa", (16, 24, 32));
            dark.sections.insert("notifications".into(), dark.sections["controls"].clone());
            let mut light = fixture_theme("bbbbbbbbbbbbbbbbbbbbbbbb", (220, 225, 230));
            light.sections.insert("notifications".into(), light.sections["controls"].clone());
            let mut renderer = RendererCache::default();
            let mut pixels = vec![0; 568 * 1232 * 4];
            let params = RenderParams {route, ..SETTINGS_PARAMS};
            renderer.set_appearance(Some(dark.clone()));
            renderer.draw(&mut pixels, params, &[]).unwrap();
            let previous = pixels.clone();
            renderer.set_appearance(Some(light));
            renderer.draw(&mut pixels, params, &[]).unwrap();
            assert_ne!(previous, pixels, "{route:?} must update on commit");
            renderer.set_appearance(Some(dark));
            renderer.draw(&mut pixels, params, &[]).unwrap();
            assert_eq!(previous, pixels, "{route:?} rollback must restore the same pixels");
        }
    }

}

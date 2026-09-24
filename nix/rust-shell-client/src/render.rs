//! Cairo/Pango software scene for the opt-in shell client.
//! This first view uses real desktop names and explicit fallback artwork.
use crate::{
    appearance::{AppearanceSnapshot, AppearanceToken, Brush},
    catalog::AppEntry,
    icon::IconCache,
    navigation::{list_top, tile_rect, COLUMNS, GRID_BOTTOM_INSET, ROW_HEIGHT},
    service_data::{Control, ControlValue},
    service_ui::{ServiceView, NOTIFICATION_ROW, NOTIFICATION_TOP},
    theme_catalog::BackgroundKind,
    theme_ui::{background_display_label, ThemeImageKey, ThemeImageWorker, ThemePage, ThemeView},
    wifi_settings::Security,
    wifi_ui::{all_networks, Page as WifiPage, WifiPublic},
    Route,
};
use cairo::{Context, Format, ImageSurface, LinearGradient, Operator};
use pango::{EllipsizeMode, FontDescription};
use std::{fs::File, path::Path};

fn color(cr: &Context, rgb: u32, alpha: f64) {
    cr.set_source_rgba(
        f64::from((rgb >> 16) & 255) / 255.0,
        f64::from((rgb >> 8) & 255) / 255.0,
        f64::from(rgb & 255) / 255.0,
        alpha,
    );
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
    font.set_family("DejaVu Sans");
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

fn heading(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    text_weight(cr, value, x, y, width, size, rgb, pango::Weight::Bold);
}

fn centered_label(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family("DejaVu Sans");
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

fn palette_rgb(value: &str) -> Option<u32> {
    let hex = value.strip_prefix('#')?;
    let rgb = match hex.len() {
        6 => hex,
        8 => &hex[2..],
        _ => return None,
    };
    u32::from_str_radix(rgb, 16).ok()
}

fn paint_theme_chooser(
    cr: &Context,
    w: f64,
    h: f64,
    view: &ThemeView,
    theme: Option<&AppearanceSnapshot>,
    preview_image: Option<&ImageSurface>,
    preview_error: bool,
) {
    let style = visual_style(theme, "image-picker");
    if let Some(brush) = theme_brush(theme, "image-picker", "background") {
        let _ = fill_brush(cr, brush, 0.0, 0.0, w, h);
    }
    text(cr, "‹ Settings", 28.0, 42.0, 185.0, 22.0, style.accent);
    text(cr, "Close", w - 115.0, 42.0, 90.0, 21.0, style.accent);
    match view.page {
        ThemePage::Controls => return,
        ThemePage::List => {
            heading(cr, "Themes", 28.0, 112.0, w - 56.0, 36.0, style.text);
            text(
                cr,
                "Tap to preview · swipe to browse",
                28.0,
                166.0,
                w - 56.0,
                18.0,
                style.muted,
            );
            if let Some(list) = &view.list {
                let _ = cr.save();
                cr.rectangle(0.0, 204.0, w, (h - 268.0).max(0.0));
                cr.clip();
                let first = (view.scroll / 92.0).floor().max(0.0) as usize;
                for (index, entry) in list.themes.iter().enumerate().skip(first).take(14) {
                    let y = 204.0 + index as f64 * 92.0 - view.scroll;
                    if y >= h - 64.0 {
                        break;
                    }
                    service_card(
                        cr,
                        theme,
                        "launcher",
                        24.0,
                        y,
                        w - 48.0,
                        82.0,
                        list.active.id.as_deref() == Some(entry.id.as_str()),
                    );
                    heading(cr, &entry.label, 42.0, y + 13.0, w - 86.0, 24.0, style.text);
                    let status = if list.active.id.as_deref() == Some(entry.id.as_str()) {
                        "Current theme"
                    } else {
                        match entry.origin {
                            crate::theme_catalog::ThemeOrigin::Builtin => "Built in",
                            crate::theme_catalog::ThemeOrigin::User => "User theme",
                        }
                    };
                    text(cr, status, 42.0, y + 47.0, w - 86.0, 16.0, style.muted);
                }
                let _ = cr.restore();
                if list.themes.is_empty() {
                    text(
                        cr,
                        "No themes available",
                        28.0,
                        226.0,
                        w - 56.0,
                        20.0,
                        style.muted,
                    );
                }
            } else {
                text(
                    cr,
                    "Loading themes",
                    28.0,
                    226.0,
                    w - 56.0,
                    20.0,
                    style.muted,
                );
            }
        }
        ThemePage::Preview => {
            let Some(preview) = view.preview.as_ref() else {
                return;
            };
            heading(
                cr,
                &preview.theme.label,
                28.0,
                112.0,
                w - 56.0,
                34.0,
                style.text,
            );
            text(
                cr,
                if preview.activated {
                    "Current theme"
                } else {
                    "Preview · no change applied"
                },
                28.0,
                160.0,
                w - 56.0,
                18.0,
                style.muted,
            );
            text(cr, "Palette", 28.0, 219.0, w - 56.0, 20.0, style.muted);
            for (index, (name, value)) in preview.palette.iter().take(5).enumerate() {
                let x = 28.0 + index as f64 * ((w - 56.0) / 5.0);
                rounded(cr, x, 257.0, 66.0, 66.0, 12.0);
                color(cr, palette_rgb(value).unwrap_or(0x425661), 1.0);
                let _ = cr.fill();
                rounded(cr, x + 0.75, 257.75, 64.5, 64.5, 11.25);
                cr.set_line_width(1.5);
                color(cr, style.muted, 0.65);
                let _ = cr.stroke();
                text(cr, name, x, 334.0, 86.0, 13.0, style.muted);
            }
            let selected = preview.backgrounds.iter().find(|row| row.selected);
            text(
                cr,
                "Selected background",
                28.0,
                373.0,
                w - 56.0,
                18.0,
                style.muted,
            );
            text(
                cr,
                &format!(
                    "{} supported · {} unavailable",
                    preview.compatibility.applied.len(),
                    preview.compatibility.unavailable.len()
                ),
                w - 274.0,
                373.0,
                246.0,
                14.0,
                style.muted,
            );
            let image_x = 28.0;
            let image_y = 399.0;
            let image_w = w - 56.0;
            let image_h = 176.0;
            rounded(cr, image_x, image_y, image_w, image_h, 15.0);
            color(cr, palette_rgb_or(theme, "background", 0x263946), 1.0);
            let _ = cr.fill();
            if let Some(image) = preview_image {
                let _ = cr.save();
                rounded(cr, image_x, image_y, image_w, image_h, 15.0);
                cr.clip();
                if cr.set_source_surface(image, image_x, image_y).is_ok() {
                    let _ = cr.paint();
                }
                let _ = cr.restore();
            } else {
                let message = if selected.is_some_and(|row| row.kind == BackgroundKind::Video) {
                    "Video preview unavailable"
                } else if preview_error {
                    "Still preview unavailable"
                } else if selected.is_some() {
                    "Preparing still preview"
                } else {
                    "Choose a background"
                };
                text(
                    cr,
                    message,
                    44.0,
                    image_y + 72.0,
                    image_w - 32.0,
                    20.0,
                    style.muted,
                );
            }
            if let Some(background) = selected {
                let detail = if background.kind == BackgroundKind::Video {
                    "video preview unavailable"
                } else {
                    "wallpaper sample, center crop"
                };
                text(
                    cr,
                    &format!("{} · {detail}", background_display_label(&background.label),),
                    28.0,
                    580.0,
                    w - 56.0,
                    16.0,
                    style.muted,
                );
            }
            text(cr, "Backgrounds", 28.0, 615.0, w - 56.0, 22.0, style.text);
            let _ = cr.save();
            cr.rectangle(0.0, 662.0, w, (h - 814.0).max(0.0));
            cr.clip();
            let first = (view.scroll / 78.0).floor().max(0.0) as usize;
            for (index, background) in preview.backgrounds.iter().enumerate().skip(first).take(10) {
                let y = 662.0 + index as f64 * 78.0 - view.scroll;
                if y >= h - 152.0 {
                    break;
                }
                service_card(
                    cr,
                    theme,
                    "image-picker",
                    24.0,
                    y,
                    w - 48.0,
                    70.0,
                    background.selected,
                );
                text(
                    cr,
                    &background_display_label(&background.label),
                    42.0,
                    y + 9.0,
                    w - 84.0,
                    21.0,
                    style.text,
                );
                let status = if background.kind == BackgroundKind::Video {
                    "Video unavailable"
                } else if background.selected {
                    "Selected still"
                } else {
                    "Tap to preview still"
                };
                text(
                    cr,
                    status,
                    42.0,
                    y + 39.0,
                    w - 84.0,
                    15.0,
                    if background.kind == BackgroundKind::Video {
                        style.error
                    } else {
                        style.muted
                    },
                );
            }
            let _ = cr.restore();
            service_card(cr, theme, "controls", 24.0, h - 126.0, w - 48.0, 86.0, true);
            if view.pending.is_some() {
                let alpha = match theme
                    .and_then(|snapshot| snapshot.token("controls", "pressed-fill-alpha"))
                {
                    Some(AppearanceToken::Number(value)) => value.clamp(0.0, 1.0),
                    _ => 0.22,
                };
                let _ = cr.save();
                rounded(cr, w / 2.0, h - 126.0, w / 2.0 - 24.0, 86.0, 16.0);
                cr.clip();
                overlay_brush(
                    cr,
                    theme_brush(theme, "controls", "normal-color"),
                    w / 2.0,
                    h - 126.0,
                    w / 2.0 - 24.0,
                    86.0,
                    alpha,
                    style.accent,
                );
                let _ = cr.restore();
            }
            text(
                cr,
                "Cancel",
                48.0,
                h - 101.0,
                w / 2.0 - 50.0,
                22.0,
                style.muted,
            );
            text(
                cr,
                if preview.activated {
                    "Apply again"
                } else {
                    "Apply"
                },
                w / 2.0 + 18.0,
                h - 101.0,
                w / 2.0 - 46.0,
                22.0,
                if view.selection_error || view.pending.is_some() {
                    style.muted
                } else {
                    style.accent
                },
            );
        }
    }
    if view.pending.is_some() {
        text(
            cr,
            "Preparing…",
            28.0,
            h - 167.0,
            w - 56.0,
            18.0,
            style.muted,
        );
    }
    if let Some(error) = &view.error {
        text(cr, error, 28.0, h - 167.0, w - 56.0, 17.0, style.error);
    }
    if let Some(message) = &view.message {
        text(cr, message, 28.0, h - 167.0, w - 56.0, 17.0, style.muted);
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
    let _ = cr.restore();
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
    let panel_h = if route == Route::Shade {
        h * 0.65
    } else {
        h - panel_y
    };
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
    if route == Route::Drawer {
        // Preserve the authored translucent launcher brush over an opaque
        // theme plate, rather than letting live card text ghost through apps.
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
        text(
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
            text(
                cr,
                "SWIPE DOWN TO RETURN TO CARDS",
                88.0,
                h - 43.0,
                w - 176.0,
                13.0,
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
                &format!("{count} notifications"),
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
                } else if count == 0 {
                    "No new notifications"
                } else {
                    "No active preview"
                };
                text(cr, empty, 42.0, 211.0, w - 84.0, 20.0, style.muted);
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
                paint_theme_chooser(cr, w, h, view, theme, preview_image, preview_error);
                return;
            }
            text(cr, "Done", w - 114.0, 46.0, 90.0, 20.0, style.accent);
            text(
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
                for (y, name, control) in [
                    (162.0, "Wi-Fi ›", &settings.network),
                    (326.0, "Brightness", &settings.brightness),
                    (452.0, "Keyboard", &settings.keyboard),
                    (590.0, "Motion", &settings.motion),
                ] {
                    service_card(cr, theme, "controls", 24.0, y, w - 48.0, 110.0, false);
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
                    text(cr, "−       +", w - 162.0, 366.0, 130.0, 25.0, style.accent);
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
            if services.and_then(|view| view.settings.as_ref()).is_some() {
                text(cr, "Power", 28.0, 722.0, w - 56.0, 19.0, style.muted);
                service_card(cr, theme, "controls", 24.0, 750.0, w - 48.0, 70.0, false);
                text(cr, "Reboot…", 42.0, 770.0, w - 84.0, 23.0, style.text);
                service_card(cr, theme, "controls", 24.0, 828.0, w - 48.0, 70.0, false);
                text(cr, "Power off…", 42.0, 848.0, w - 84.0, 23.0, style.text);
            }
            if let Some(confirm) = services.and_then(|view| view.confirmation.as_ref()) {
                text(cr, &confirm.label, 28.0, 912.0, w - 56.0, 19.0, style.text);
                service_card(cr, theme, "controls", 24.0, 940.0, w - 48.0, 110.0, true);
                text(cr, "Cancel", 45.0, 973.0, w / 2.0 - 45.0, 23.0, style.muted);
                text(
                    cr,
                    "Confirm",
                    w / 2.0 + 20.0,
                    973.0,
                    w / 2.0 - 45.0,
                    23.0,
                    style.error,
                );
            }
            if let Some(message) = services.and_then(|view| view.message.as_deref()) {
                text(cr, message, 28.0, 1080.0, w - 56.0, 17.0, style.muted);
            }
        }
        Route::Hide => {}
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
        pressed,
    );
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
}

impl RendererCache {
    pub fn set_theme_view(&mut self, view: ThemeView) {
        self.chooser = Some(view);
        self.invalidate();
    }
    /// Nonblocking dispatch hook. Only a selected staged still is decoded;
    /// the one-entry worker cache and result channel bound memory and work.
    pub fn poll_theme_image(&mut self, width: u32) -> bool {
        let desired = self.chooser.as_ref().and_then(|view| {
            let preview = (view.page == ThemePage::Preview)
                .then_some(view.preview.as_ref())
                .flatten()?;
            preview
                .backgrounds
                .iter()
                .find(|row| row.selected && row.kind == BackgroundKind::Image)
                .and_then(|row| {
                    let image_width = width.checked_sub(56)?;
                    (image_width > 0 && image_width <= 1024).then(|| ThemeImageKey {
                        generation: preview.generation.clone(),
                        path: row.path.clone(),
                        width: image_width,
                        height: 176,
                    })
                })
        });
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
        changed
    }
    pub fn set_services(&mut self, services: ServiceView) {
        self.services = Some(services);
        self.invalidate();
    }
    pub fn set_drawer_pressed(&mut self, pressed: Option<usize>) -> bool {
        if self.pressed != pressed {
            self.pressed = pressed;
            self.invalidate();
            return true;
        }
        false
    }
    pub fn set_appearance(&mut self, theme: Option<AppearanceSnapshot>) {
        let configured = std::env::var("K230_ICON_THEME").ok();
        let name = theme
            .as_ref()
            .and_then(|value| value.icon_theme.as_deref())
            .or(configured.as_deref())
            .unwrap_or("hicolor");
        self.icons.set_theme(name);
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
        self.poll_theme_image(width);
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
        Ok(())
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
    use crate::theme_catalog::{
        ActiveTheme, BackgroundChoice, Compatibility, ThemeEntry, ThemeList, ThemeOrigin,
        ThemePreview,
    };
    use std::collections::BTreeMap;

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
        let theme_entry = ThemeEntry {
            id: theme_id.into(),
            name: theme_label.into(),
            label: theme_label.into(),
            origin: ThemeOrigin::Builtin,
        };
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
                    },
                ],
                active: ActiveTheme {
                    id: Some(theme_entry.id.clone()),
                    generation: None,
                },
            }),
            ..ThemeView::default()
        };
        let preview = ThemeView {
            page: ThemePage::Preview,
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
            ("themes", Route::Settings, Some(chooser)),
            ("preview", Route::Settings, Some(preview)),
        ] {
            if let Some(view) = theme_view {
                renderer.set_theme_view(view);
            }
            if name == "preview" {
                let deadline = std::time::Instant::now() + std::time::Duration::from_secs(8);
                while std::time::Instant::now() < deadline {
                    renderer.poll_theme_image(568);
                    if renderer.preview_surface.is_some() || renderer.preview_error {
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(5));
                }
                if std::env::var_os("K230_VISUAL_REQUIRE_BACKGROUND").is_some() {
                    assert!(
                        renderer.preview_surface.is_some(),
                        "actual staged still must render: key={:?} requested={:?} error={}",
                        renderer.preview_key,
                        renderer.preview_requested,
                        renderer.preview_error
                    );
                }
            }
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
        view.scroll = 460.0;
        renderer.set_theme_view(view.clone());
        let mut scrolled = vec![0; controls.len()];
        renderer.draw(&mut scrolled, params, &[]).unwrap();
        assert_ne!(list, scrolled);
        // Scrolling leaves the header unchanged while replacing visible rows.
        assert_eq!(&list[..568 * 180 * 4], &scrolled[..568 * 180 * 4]);
        view.page = ThemePage::Preview;
        view.scroll = 0.0;
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
                    path: "/tmp/fixture.png".into(),
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
    }

    #[test]
    fn cancelled_still_result_never_reappears_in_chooser() {
        let path =
            std::env::temp_dir().join(format!("k230-cancelled-still-{}.png", std::process::id()));
        image::RgbaImage::from_pixel(4, 4, image::Rgba([90, 40, 150, 255]))
            .save(&path)
            .unwrap();
        let entry = ThemeEntry {
            id: "fixture".into(),
            name: "Fixture".into(),
            label: "Fixture".into(),
            origin: ThemeOrigin::Builtin,
        };
        let mut renderer = RendererCache::default();
        renderer.set_theme_view(ThemeView {
            page: ThemePage::Preview,
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
                    path: path.canonicalize().unwrap(),
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
        assert!(renderer.poll_theme_image(568));
        renderer.set_theme_view(ThemeView::default());
        assert!(renderer.poll_theme_image(568));
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while renderer.preview_requested.is_some() && std::time::Instant::now() < deadline {
            renderer.poll_theme_image(568);
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert!(renderer.preview_requested.is_none());
        assert!(renderer.preview_surface.is_none());
        assert!(renderer.preview_key.is_none());
        std::fs::remove_file(path).unwrap();
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
}

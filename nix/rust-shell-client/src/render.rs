//! Cairo/Pango software scene for the opt-in shell client.
//! This first view uses real desktop names and explicit fallback artwork.
use crate::{catalog::AppEntry, Route};
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

fn text(cr: &Context, value: &str, x: f64, y: f64, width: f64, size: f64, rgb: u32) {
    let layout = pangocairo::functions::create_layout(cr);
    let mut font = FontDescription::new();
    font.set_family("DejaVu Sans");
    font.set_absolute_size(size * f64::from(pango::SCALE));
    layout.set_font_description(Some(&font));
    layout.set_text(value);
    layout.set_width((width * f64::from(pango::SCALE)) as i32);
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

fn scene(cr: &Context, width: u32, height: u32, route: Route, apps: &[AppEntry]) {
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
    let gradient = LinearGradient::new(0.0, panel_y, w, panel_y + panel_h);
    gradient.add_color_stop_rgb(0.0, 0.075, 0.12, 0.17);
    gradient.add_color_stop_rgb(1.0, 0.12, 0.19, 0.24);
    cr.rectangle(0.0, panel_y, w, panel_h);
    let _ = cr.set_source(&gradient);
    let _ = cr.fill();
    color(cr, 0x78d7cb, 1.0);
    cr.rectangle(0.0, panel_y, w, 3.0);
    let _ = cr.fill();
    let title = match route {
        Route::Drawer => "Apps",
        Route::Shade => "Notifications",
        Route::Settings => "Settings",
        Route::Hide => return,
    };
    text(cr, title, 28.0, panel_y + 32.0, w - 56.0, 40.0, 0xf4f7f8);
    match route {
        Route::Drawer => {
            text(
                cr,
                "Installed on this device",
                28.0,
                panel_y + 92.0,
                w - 56.0,
                18.0,
                0xc8d7dd,
            );
            let row_start = panel_y + 144.0;
            for (index, app) in apps.iter().take(7).enumerate() {
                let y = row_start + index as f64 * 94.0;
                if y + 82.0 > h - 28.0 {
                    break;
                }
                rounded(cr, 24.0, y, w - 48.0, 82.0, 16.0);
                color(cr, 0x263946, 1.0);
                let _ = cr.fill();
                rounded(cr, 38.0, y + 15.0, 52.0, 52.0, 12.0);
                color(cr, 0x375466, 1.0);
                let _ = cr.fill();
                let initial = app
                    .name
                    .chars()
                    .next()
                    .unwrap_or('?')
                    .to_uppercase()
                    .to_string();
                text(cr, &initial, 53.0, y + 23.0, 34.0, 24.0, 0xf4f7f8);
                text(cr, &app.name, 108.0, y + 20.0, w - 156.0, 25.0, 0xf4f7f8);
                text(
                    cr,
                    "Installed app",
                    108.0,
                    y + 52.0,
                    w - 156.0,
                    16.0,
                    0xc8d7dd,
                );
            }
            if apps.is_empty() {
                text(
                    cr,
                    "No installed apps are available",
                    28.0,
                    row_start + 18.0,
                    w - 56.0,
                    21.0,
                    0xc8d7dd,
                );
            }
        }
        Route::Shade => {
            text(cr, "Current activity", 28.0, 98.0, w - 56.0, 19.0, 0xc8d7dd);
            rounded(cr, 24.0, 148.0, w - 48.0, 116.0, 16.0);
            color(cr, 0x263946, 1.0);
            let _ = cr.fill();
            text(
                cr,
                "No notifications loaded",
                44.0,
                174.0,
                w - 88.0,
                24.0,
                0xf4f7f8,
            );
            text(
                cr,
                "Open Settings from this shade",
                44.0,
                213.0,
                w - 88.0,
                18.0,
                0xc8d7dd,
            );
        }
        Route::Settings => {
            text(cr, "Device controls", 28.0, 98.0, w - 56.0, 19.0, 0xc8d7dd);
            rounded(cr, 24.0, 148.0, w - 48.0, 116.0, 16.0);
            color(cr, 0x263946, 1.0);
            let _ = cr.fill();
            text(
                cr,
                "Loading capability state",
                44.0,
                174.0,
                w - 88.0,
                24.0,
                0xf4f7f8,
            );
            text(
                cr,
                "Controls appear only when confirmed",
                44.0,
                213.0,
                w - 88.0,
                18.0,
                0xc8d7dd,
            );
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
) -> Result<(), String> {
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
    scene(&cr, width, height, route, apps);
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
    scene(&cr, width, height, route, apps);
    drop(cr);
    let mut file = File::create(path).map_err(|error| error.to_string())?;
    surface
        .write_to_png(&mut file)
        .map_err(|error| error.to_string())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn drawer_keeps_live_scene_above_opaque_panel() {
        let apps = vec![AppEntry {
            id: "foot.desktop".into(),
            name: "Terminal".into(),
            icon: Some("foot".into()),
        }];
        let mut frame = vec![0; 568 * 1232 * 4];
        draw_shm(&mut frame, 568, 1232, Route::Drawer, &apps).unwrap();
        assert_eq!(&frame[0..4], &[0, 0, 0, 0]);
        let panel_pixel = (900 * 568 + 280) * 4;
        assert_eq!(frame[panel_pixel + 3], 255);
        assert!(draw_shm(&mut frame[..100], 568, 1232, Route::Drawer, &apps).is_err());
    }
}

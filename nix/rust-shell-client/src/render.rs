//! Cairo/Pango software scene for the opt-in shell client.
//! This first view uses real desktop names and explicit fallback artwork.
use crate::{
    catalog::AppEntry,
    icon::IconCache,
    navigation::{list_top, ROW_HEIGHT, ROW_VISIBLE_HEIGHT},
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

#[derive(Clone, Copy)]
pub struct RenderParams {
    pub width: u32,
    pub height: u32,
    pub route: Route,
    pub progress: f64,
    pub scroll: f64,
}

fn scene(cr: &Context, params: RenderParams, apps: &[AppEntry], icons: &mut IconCache) {
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
            let row_start = list_top(height);
            let _ = cr.save();
            cr.rectangle(0.0, row_start, w, (h - 28.0 - row_start).max(0.0));
            cr.clip();
            let first = (scroll / ROW_HEIGHT).floor().max(0.0) as usize;
            for (index, app) in apps.iter().enumerate().skip(first).take(10) {
                let y = row_start + index as f64 * ROW_HEIGHT - scroll;
                if y >= h - 28.0 {
                    break;
                }
                rounded(cr, 24.0, y, w - 48.0, ROW_VISIBLE_HEIGHT, 16.0);
                color(cr, 0x263946, 1.0);
                let _ = cr.fill();
                rounded(cr, 38.0, y + 15.0, 52.0, 52.0, 12.0);
                color(cr, 0x375466, 1.0);
                let _ = cr.fill();
                let painted = app
                    .icon
                    .as_deref()
                    .is_some_and(|icon| icons.paint(cr, icon, 48, 40.0, y + 17.0));
                if !painted {
                    let initial = app
                        .name
                        .chars()
                        .next()
                        .unwrap_or('?')
                        .to_uppercase()
                        .to_string();
                    text(cr, &initial, 53.0, y + 23.0, 34.0, 24.0, 0xf4f7f8);
                }
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
            let _ = cr.restore();
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
    )
}

fn draw_shm_with_icons(
    canvas: &mut [u8],
    params: RenderParams,
    apps: &[AppEntry],
    icons: &mut IconCache,
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
    scene(&cr, params, apps, icons);
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
}

impl RendererCache {
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
        let pixel = (402 * 568 + 52) * 4;
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
        let pixel = (402 * 568 + 52) * 4;
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
}

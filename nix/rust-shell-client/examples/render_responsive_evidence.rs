//! Host render harness for `openspec/changes/the-shell-adapts-to-output-
//! resolution`'s evidence captures.
//!
//! Renders Home, the wallpaper background, the Drawer and Settings through
//! the exact same production paths (`render::paint_home`,
//! `render::RendererCache::draw_wallpaper`, `render::export_png`) the real
//! Wayland client calls, at each of four surface sizes this change targets:
//! the native panel (568x1232, must stay pixel-identical to before this
//! change) and three whole-output HDMI sizes that `feat/hdmi-pillarbox`
//! used to letterbox down to a centered 568-aspect column and that
//! `feat/shell-responsive` now fills instead (768x1024, 1080x1920 rotated
//! portrait, 1920x1080 landscape).
//!
//! This proves the render geometry reflows/fills correctly; it does not
//! open a Wayland connection, so it does not prove the compositor actually
//! hands this client a whole-output configure at these sizes (that is
//! `main.rs`'s `is_whole_output`/`configure_preserves_aspect`, covered by
//! `lib.rs`'s own unit tests) or anything about real touch/board behavior.
//!
//! `cargo run --example render_responsive_evidence -- <out-dir>` writes
//! every PNG into `<out-dir>`.
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    catalog::AppEntry,
    home_grid::{self, HomeSlot},
    home_screen::HomeScreen,
    home_state::{HomeItem, HomeLayout},
    icon::IconCache,
    render::{self, RendererCache},
    Route,
};
use std::{env, path::PathBuf};

/// Enough synthetic apps to overflow a single Home page and a single
/// Drawer viewport at every target resolution, so a render at each size
/// visibly exercises more than one row -- 30 apps is comfortably past this
/// panel's own 20-per-page grid capacity (`home_grid::apps_per_page(1232)`)
/// and the drawer's per-viewport row count.
fn synthetic_apps(count: usize) -> Vec<AppEntry> {
    (0..count)
        .map(|index| AppEntry {
            id: format!("evidence.app{index}.desktop"),
            name: format!("App {index}"),
            icon: None,
            path: PathBuf::from(format!("/nonexistent/app{index}.desktop")),
        })
        .collect()
}

/// Fills the dock with the first `home_grid::DOCK_SLOTS` apps and the grid
/// pages with the rest, via the same `HomeLayout::place`/`place_first_fit`
/// primitives a real drag uses -- unlike `home_state::seed_default`, which
/// only auto-pins a small curated list of well-known real desktop-entry
/// ids (`foot.desktop` and friends) and would seed nothing but the Clock
/// widget for this harness's synthetic `evidence.appN.desktop` ids.
fn seed_layout(apps: &[AppEntry], height: u32) -> HomeLayout {
    let apps_per_page = home_grid::apps_per_page(height);
    let mut layout = HomeLayout::default();
    layout.dock = vec![None; home_grid::DOCK_SLOTS];
    let mut iter = apps.iter();
    for slot in 0..home_grid::DOCK_SLOTS {
        let Some(app) = iter.next() else { break };
        layout.set(HomeSlot::Dock { slot }, Some(HomeItem::app(app.id.clone())), apps_per_page);
    }
    for app in iter {
        layout.place_first_fit(HomeItem::app(app.id.clone()), apps_per_page);
    }
    layout
}

/// `render::paint_home` clears to a fully transparent canvas before
/// painting (real production compositing shows it over the separate,
/// always-opaque wallpaper layer beneath). Composite it over the same flat
/// backdrop `render_wallpaper` below draws so light-on-transparent text
/// (e.g. the Clock widget) is legible in a standalone PNG instead of
/// disappearing into an image viewer's own white behind full alpha 0.
fn render_home(path: &std::path::Path, width: u32, height: u32, apps: &[AppEntry]) {
    let content = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&content).unwrap();
        let home_layout = seed_layout(apps, height);
        let home = HomeScreen::new(home_layout, f64::from(width));
        let mut icons = IconCache::new();
        render::paint_home(&cr, width, height, None, &home, apps, &mut icons);
    }
    let composited = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&composited).unwrap();
        cr.set_source_rgb(0x1e as f64 / 255.0, 0x1e as f64 / 255.0, 0x2e as f64 / 255.0);
        cr.paint().unwrap();
        cr.set_source_surface(&content, 0.0, 0.0).unwrap();
        cr.paint().unwrap();
    }
    let mut file = std::fs::File::create(path).unwrap();
    composited.write_to_png(&mut file).unwrap();
}

fn render_wallpaper(path: &std::path::Path, width: u32, height: u32) {
    let cache = RendererCache::default();
    let mut canvas = vec![0u8; (width as usize) * (height as usize) * 4];
    cache.draw_wallpaper(&mut canvas, width, height).unwrap();
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(
            canvas.as_mut_ptr(),
            Format::ARgb32,
            width as i32,
            height as i32,
            (width * 4) as i32,
        )
    }
    .unwrap();
    let mut file = std::fs::File::create(path).unwrap();
    surface.write_to_png(&mut file).unwrap();
}

fn render_route(path: &std::path::Path, width: u32, height: u32, route: Route, apps: &[AppEntry]) {
    render::export_png(path, width, height, route, apps).unwrap();
}

fn main() {
    let out_dir = PathBuf::from(env::args().nth(1).expect("usage: render_responsive_evidence <out-dir>"));
    std::fs::create_dir_all(&out_dir).unwrap();
    let apps = synthetic_apps(30);
    // (label, width, height) -- 568x1232 first, and its own render must
    // stay pixel-identical across a future re-run of this same harness:
    // that is what "pixel-identical to today" means for a headless,
    // no-Wayland capture like this one.
    let sizes: [(&str, u32, u32); 4] = [
        ("568x1232", 568, 1232),
        ("768x1024", 768, 1024),
        ("1080x1920", 1080, 1920),
        ("1920x1080", 1920, 1080),
    ];
    for (label, width, height) in sizes {
        render_home(&out_dir.join(format!("home-{label}.png")), width, height, &apps);
        render_wallpaper(&out_dir.join(format!("wallpaper-{label}.png")), width, height);
        render_route(&out_dir.join(format!("drawer-{label}.png")), width, height, Route::Drawer, &apps);
        render_route(&out_dir.join(format!("settings-{label}.png")), width, height, Route::Settings, &apps);
        eprintln!("rendered {label}");
    }
}

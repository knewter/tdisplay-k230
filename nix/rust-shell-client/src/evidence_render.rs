//! Host render helpers shared by `examples/render_responsive_evidence.rs`
//! (produces `docs/evidence/shell-responsive/*.png`) and
//! `tests/responsive_pixel_identity.rs` (proves the 568x1232 renders those
//! helpers produce stay byte-for-byte identical to the committed evidence,
//! i.e. `feat/shell-responsive` never changed the native panel's own
//! output). One shared implementation so the evidence PNGs and the test
//! that guards them can never quietly drift apart from each other.
//!
//! Renders Home, the wallpaper background, the Drawer and Settings through
//! the exact same production paths (`render::paint_home`,
//! `render::RendererCache::draw_wallpaper`, `render::export_png`) the real
//! Wayland client calls -- never opens a Wayland connection itself, so this
//! proves render geometry only, not that the compositor hands this client
//! a whole-output configure at any given size (see `lib.rs`'s own
//! `is_whole_output`/`configure_preserves_aspect` tests for that).
use crate::{
    catalog::AppEntry,
    home_grid::{self, HomeSlot},
    home_screen::HomeScreen,
    home_state::{HomeItem, HomeLayout},
    icon::IconCache,
    render::{self, RendererCache},
    Route,
};
use cairo::{Context, Format, ImageSurface};
use std::path::{Path, PathBuf};

/// Enough synthetic apps to overflow a single Home page and a single
/// Drawer viewport at every target resolution, so a render at each size
/// visibly exercises more than one row -- 30 apps is comfortably past this
/// panel's own 20-per-page grid capacity (`home_grid::apps_per_page`) and
/// the drawer's per-viewport row count.
pub fn synthetic_apps(count: usize) -> Vec<AppEntry> {
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
pub fn seed_layout(apps: &[AppEntry], width: u32, height: u32) -> HomeLayout {
    let apps_per_page = home_grid::apps_per_page(width, height);
    let mut layout = HomeLayout {
        columns: home_grid::columns_for_width(width),
        dock: vec![None; home_grid::DOCK_SLOTS],
        ..HomeLayout::default()
    };
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
/// backdrop [`render_wallpaper`] draws so light-on-transparent text (e.g.
/// the Clock widget) is legible in a standalone PNG instead of
/// disappearing into an image viewer's own white behind full alpha 0.
pub fn render_home(path: &Path, width: u32, height: u32, apps: &[AppEntry]) {
    let content = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&content).unwrap();
        let home_layout = seed_layout(apps, width, height);
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

pub fn render_wallpaper(path: &Path, width: u32, height: u32) {
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

pub fn render_route(path: &Path, width: u32, height: u32, route: Route, apps: &[AppEntry]) {
    render::export_png(path, width, height, route, apps).unwrap();
}

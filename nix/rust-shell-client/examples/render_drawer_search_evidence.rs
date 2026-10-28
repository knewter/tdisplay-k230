//! Host renders of the drawer search results (the-drawer-search-finds-
//! settings-and-app-actions task 2.1): a fixture catalog, no icon theme, no
//! theme generation, so these show geometry, ranking and the first-row
//! outline only -- not the board's colours or icons.
//!
//! usage: render_drawer_search_evidence [out-dir]
//!        (default docs/evidence/drawer-search/host)
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    catalog::AppEntry,
    render::{RenderParams, RendererCache},
    search::Hardware,
    service_ui::DrawerSearch,
    Route,
};
use std::{env, fs, path::PathBuf};

fn catalog() -> Vec<AppEntry> {
    let app = |name: &str, actions: &[(&str, &str)]| AppEntry {
        actions: actions.iter().map(|(id, label)| (id.to_string(), label.to_string())).collect(),
        id: format!("{}.desktop", name.to_lowercase().replace(' ', "-")),
        name: name.into(),
        icon: None,
        path: PathBuf::new(),
    };
    vec![
        app("Calculator", &[]),
        app("Files", &[("new-window", "New Window")]),
        app("Terminal", &[("new-window", "New Window"), ("prefs", "Preferences")]),
        app("Timer", &[]),
        app("Video", &[]),
    ]
}

fn render(path: PathBuf, width: u32, height: u32, step: f64, query: &str, hardware: Hardware) {
    k230_shell_rust::set_layout_text_scale(step);
    let apps = catalog();
    let mut renderer = RendererCache::default();
    renderer.set_drawer_search(DrawerSearch {
        query: query.into(),
        focused: true,
        from_keys: true,
        hardware,
        ..DrawerSearch::default()
    });
    let mut pixels = vec![0u8; (width * height * 4) as usize];
    renderer
        .draw(&mut pixels, RenderParams { width, height, route: Route::Drawer, progress: 1.0, scroll: 0.0 }, &apps)
        .expect("draw");
    let frame = ImageSurface::create_for_data(pixels, Format::ARgb32, width as i32, height as i32, (width * 4) as i32).unwrap();
    let target = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    let cr = Context::new(&target).unwrap();
    cr.set_source_rgb(0.5, 0.5, 0.5);
    cr.paint().unwrap();
    cr.set_source_surface(&frame, 0.0, 0.0).unwrap();
    cr.paint().unwrap();
    drop(cr);
    target.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

fn main() {
    let out = PathBuf::from(env::args().nth(1).unwrap_or_else(|| "docs/evidence/drawer-search/host".into()));
    fs::create_dir_all(&out).unwrap();
    let both = Hardware { modem: true, key_backlight: true };
    let none = Hardware::default();
    for (shape, width, height) in [("landscape", 1232u32, 568u32), ("portrait", 568, 1232)] {
        for (step, label) in [(1.0, "100"), (2.0, "200")] {
            for (name, query, hardware) in [
                ("grid", "", both),
                ("wifi", "wifi", both),
                ("ti", "ti", both),
                ("pref", "pref", both),
                ("location-without-modem", "location", none),
                ("location-with-modem", "location", both),
            ] {
                render(out.join(format!("{shape}-{label}-{name}.png")), width, height, step, query, hardware);
            }
        }
    }
    println!("wrote {}", out.display());
}

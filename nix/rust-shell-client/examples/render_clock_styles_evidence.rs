//! Host renders of the four Clock widget styles on two backdrops, from real
//! theme generations (`the-shell-has-one-visual-language`).
//!
//! usage: render_clock_styles_evidence <out-dir> <generations-root>
//!        <name>=<generation-id>...
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    appearance::{AppearanceReceiver, AppearanceSnapshot},
    render::{self, RendererCache},
    home_grid::{self, HomeSlot},
    home_screen::HomeScreen,
    home_state::{HomeItem, HomeLayout, WidgetKind},
    icon::IconCache,
};
use std::{env, fs, os::unix::fs::PermissionsExt, path::PathBuf};

fn snapshot(root: &PathBuf, sockets: &PathBuf, name: &str, id: &str) -> AppearanceSnapshot {
    let receiver = AppearanceReceiver::bind_with_roots(
        sockets.join(format!("{name}.sock")),
        Some(root.join(id)),
        root.clone(),
    )
    .expect("bind fixture receiver");
    receiver.active().cloned().expect("generation did not load")
}

/// One Home with a single Clock widget in slot 0 over a flat `backdrop`,
/// cropped to the left `crop` x `h` pixels.
fn render_clock(path: PathBuf, theme: &AppearanceSnapshot, kind: WidgetKind, backdrop: (f64, f64, f64), w: u32, h: u32, crop: i32) {
    // `RendererCache::set_appearance` sets the layout step; do the same.
    let mut cache = RendererCache::default();
    cache.set_appearance(Some(theme.clone()));
    let per_page = home_grid::apps_per_page(w, h);
    let mut layout = HomeLayout {
        columns: home_grid::columns_for_width(w),
        dock: vec![None; home_grid::DOCK_SLOTS],
        ..HomeLayout::default()
    };
    layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: kind }, per_page, false);
    let home = HomeScreen::new(layout, f64::from(w));
    let target = ImageSurface::create(Format::ARgb32, w as i32, h as i32).unwrap();
    {
        let cr = Context::new(&target).unwrap();
        cr.set_source_rgb(backdrop.0, backdrop.1, backdrop.2);
        cr.paint().unwrap();
        let content = ImageSurface::create(Format::ARgb32, w as i32, h as i32).unwrap();
        {
            let cc = Context::new(&content).unwrap();
            render::paint_home(&cc, w, h, Some(theme), &home, &[], &mut IconCache::new());
        }
        cr.set_source_surface(&content, 0.0, 0.0).unwrap();
        cr.paint().unwrap();
    }
    let cropped = ImageSurface::create(Format::ARgb32, crop, h as i32).unwrap();
    {
        let cr = Context::new(&cropped).unwrap();
        cr.set_source_surface(&target, 0.0, 0.0).unwrap();
        cr.paint().unwrap();
    }
    cropped.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

fn main() {
    let mut args = env::args().skip(1);
    let out = PathBuf::from(args.next().expect("out dir"));
    let root = PathBuf::from(args.next().expect("generations root"));
    fs::create_dir_all(&out).unwrap();
    let sockets = env::temp_dir().join(format!("k230-clock-evidence-{}", std::process::id()));
    fs::create_dir_all(&sockets).unwrap();
    fs::set_permissions(&sockets, fs::Permissions::from_mode(0o700)).unwrap();
    // A dark teal and a bright orange: the two halves of the vinyl
    // wallpaper the operator's panel shows.
    let backdrops = [("teal", (0.05, 0.55, 0.52)), ("orange", (0.93, 0.45, 0.25))];
    let styles = [
        ("bubble", WidgetKind::Clock),
        ("thin", WidgetKind::ClockMinimal),
        ("dots", WidgetKind::ClockDotMatrix),
        ("analog", WidgetKind::ClockAnalog),
    ];
    for pair in args {
        let (name, id) = pair.split_once('=').expect("name=generation");
        let theme = snapshot(&root, &sockets, name, id);
        for (style, kind) in styles {
            for (back, rgb) in backdrops {
                render_clock(out.join(format!("{name}-{style}-{back}.png")), &theme, kind, rgb, 1232, 568, 620);
            }
        }
        println!("rendered {name}");
    }
    let _ = fs::remove_dir_all(&sockets);
}

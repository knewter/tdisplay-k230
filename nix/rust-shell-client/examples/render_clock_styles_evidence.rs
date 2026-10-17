//! Host renders of the four Clock widget styles on two backdrops, from real
//! theme generations (`the-shell-has-one-visual-language`).
//!
//! usage: render_clock_styles_evidence <out-dir> <generations-root>
//!        <name>=<generation-id>...
//!
//! Optional environment: `CLOCK_SIZE=portrait` renders 568x1232 (cropped to
//! the top 620 px) instead of 1232x568; `CLOCK_WALLPAPER=<png>` replaces the
//! flat teal/orange backdrops with that image, scaled to cover the panel.
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

enum Backdrop {
    Flat(f64, f64, f64),
    Image(ImageSurface),
}

/// One Home with a single Clock widget in slot 0 over a `backdrop`,
/// cropped to the top-left `crop` pixels.
fn render_clock(path: PathBuf, theme: &AppearanceSnapshot, kind: WidgetKind, backdrop: &Backdrop, w: u32, h: u32, crop: (i32, i32)) {
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
        match backdrop {
            Backdrop::Flat(r, g, b) => {
                cr.set_source_rgb(*r, *g, *b);
                cr.paint().unwrap();
            }
            Backdrop::Image(img) => {
                let scale = (f64::from(w) / f64::from(img.width())).max(f64::from(h) / f64::from(img.height()));
                cr.scale(scale, scale);
                cr.set_source_surface(img, 0.0, 0.0).unwrap();
                cr.paint().unwrap();
                cr.identity_matrix();
            }
        }
        let content = ImageSurface::create(Format::ARgb32, w as i32, h as i32).unwrap();
        {
            let cc = Context::new(&content).unwrap();
            render::paint_home(&cc, w, h, Some(theme), &home, &[], &mut IconCache::new());
        }
        cr.set_source_surface(&content, 0.0, 0.0).unwrap();
        cr.paint().unwrap();
    }
    let cropped = ImageSurface::create(Format::ARgb32, crop.0, crop.1).unwrap();
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
    let backdrops: Vec<(&str, Backdrop)> = match env::var("CLOCK_WALLPAPER") {
        Ok(path) => {
            let img = ImageSurface::create_from_png(&mut fs::File::open(path).expect("wallpaper png")).expect("decode wallpaper png");
            vec![("wall", Backdrop::Image(img))]
        }
        Err(_) => vec![("teal", Backdrop::Flat(0.05, 0.55, 0.52)), ("orange", Backdrop::Flat(0.93, 0.45, 0.25))],
    };
    let portrait = env::var("CLOCK_SIZE").is_ok_and(|v| v == "portrait");
    let (w, h, crop, tag) = if portrait { (568, 1232, (568, 620), "portrait-") } else { (1232, 568, (620, 568), "") };
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
            for (back, backdrop) in &backdrops {
                render_clock(out.join(format!("{tag}{name}-{style}-{back}.png")), &theme, kind, backdrop, w, h, crop);
            }
        }
        println!("rendered {name}");
    }
    let _ = fs::remove_dir_all(&sockets);
}

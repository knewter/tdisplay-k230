//! Host renders for the vision option (task C.3): the same screens drawn
//! from real generations that `tools/theme_activate.py` prepared from one
//! theme at each text step, and with high contrast.
//!
//! usage: render_accessibility_scale_evidence <out-dir> <generations-root>
//!        <name>=<generation-id>...
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    appearance::{AppearanceReceiver, AppearanceSnapshot},
    catalog::AppEntry,
    evidence_render::{fixture_notification_events, fixture_settings},
    render::{RenderParams, RendererCache},
    service_data::NotificationSnapshot,
    service_ui::ServiceView,
    theme_catalog::VisionChoice,
    theme_ui::{ThemePage, ThemeView},
    Route,
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

fn render(path: PathBuf, theme: &AppearanceSnapshot, vision: &VisionChoice, w: u32, h: u32, page: &str) {
    let mut cache = RendererCache::default();
    cache.set_appearance(Some(theme.clone()));
    cache.set_services(ServiceView {
        settings: Some(fixture_settings()),
        notifications: Some(NotificationSnapshot {
            count: 2,
            events: fixture_notification_events(2),
            preview: None,
        }),
        ..ServiceView::default()
    });
    let route = match page {
        "settings" | "vision" => Route::Settings,
        "shade" => Route::Shade,
        _ => Route::Drawer,
    };
    if page == "vision" {
        cache.set_theme_view(ThemeView {
            page: ThemePage::Vision,
            vision: vision.clone(),
            vision_loaded: true,
            message: Some("Applied to every theme".into()),
            ..ThemeView::default()
        });
    }
    let apps: Vec<AppEntry> = ["Terminal", "Files", "Video Player", "Settings", "Text Editor", "System Monitor", "Calculator", "Image Viewer"]
        .into_iter()
        .map(|name| AppEntry { id: format!("{name}.desktop"), name: name.into(), icon: None, path: PathBuf::new() })
        .collect();
    let mut pixels = vec![0; (w * h * 4) as usize];
    cache
        .draw(&mut pixels, RenderParams { width: w, height: h, route, progress: 1.0, scroll: 0.0 }, &apps)
        .expect("draw");
    let frame = ImageSurface::create_for_data(pixels, Format::ARgb32, w as i32, h as i32, (w * 4) as i32).unwrap();
    let target = ImageSurface::create(Format::ARgb32, w as i32, h as i32).unwrap();
    let cr = Context::new(&target).unwrap();
    cr.set_source_rgb(0.5, 0.5, 0.5);
    cr.paint().unwrap();
    cr.set_source_surface(&frame, 0.0, 0.0).unwrap();
    cr.paint().unwrap();
    drop(cr);
    target.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

fn main() {
    let mut args = env::args().skip(1);
    let out = PathBuf::from(args.next().expect("out dir"));
    let root = PathBuf::from(args.next().expect("generations root"));
    fs::create_dir_all(&out).unwrap();
    let sockets = env::temp_dir().join(format!("k230-a11y-evidence-{}", std::process::id()));
    fs::create_dir_all(&sockets).unwrap();
    fs::set_permissions(&sockets, fs::Permissions::from_mode(0o700)).unwrap();
    for pair in args {
        let (name, id) = pair.split_once('=').expect("name=generation");
        let theme = snapshot(&root, &sockets, name, id);
        // `<step>` or `<step>-high`, where step is a TEXT_SCALE_NAMES entry.
        let step = name.split('-').next().unwrap_or("default");
        let vision = VisionChoice {
            text_scale: step.into(),
            contrast: if name.ends_with("high") { "high" } else { "standard" }.into(),
        };
        for (w, h) in [(568u32, 1232u32), (1232, 568)] {
            for page in ["settings", "vision", "shade", "drawer"] {
                render(out.join(format!("{name}-{page}-{w}x{h}.png")), &theme, &vision, w, h, page);
            }
        }
        println!("rendered {name}");
    }
    let _ = fs::remove_dir_all(&sockets);
}

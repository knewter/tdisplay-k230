//! Host renders for the notification banner: `cargo run --example
//! render_notification_banner_evidence -- <out-dir>` writes
//! `banner-{trusted,unknown}-{568x1232,1232x568}.png`, the banner composited
//! at its layer-surface position over a rendered Home screen. Host render
//! only: it proves paint and geometry, not the compositor or the glass.
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    evidence_render::{render_home, synthetic_apps},
    notification_banner::{banner_geometry, surface_size},
    render::RendererCache,
    service_data::{NotificationPreview, Priority},
};
use std::{env, fs, path::Path};

fn main() {
    let out = env::args().nth(1).expect("usage: render_notification_banner_evidence <out-dir>");
    let out = Path::new(&out);
    fs::create_dir_all(out).unwrap();
    let apps = synthetic_apps(30);
    // The broker's own output: a trusted sender keeps its text; an unknown or
    // private sender arrives already reduced to these generic fields.
    let trusted = NotificationPreview { id: 1, source: "Terminal".into(), icon: None, summary: "Build finished: 0 errors".into(), priority: Priority::Ordinary, ongoing: false, breakthrough: false };
    let unknown = NotificationPreview { id: 2, source: "Notification".into(), icon: None, summary: "New notification".into(), priority: Priority::Ordinary, ongoing: false, breakthrough: false };
    for (w, h) in [(568u32, 1232u32), (1232, 568)] {
        let base = out.join(format!("base-{w}x{h}.tmp.png"));
        render_home(&base, w, h, &apps);
        for (name, preview) in [("trusted", &trusted), ("unknown", &unknown)] {
            let mut file = fs::File::open(&base).unwrap();
            let screen = ImageSurface::create_from_png(&mut file).unwrap();
            let (bw, bh, _) = surface_size(f64::from(w), f64::from(h));
            let mut canvas = vec![0u8; (bw * bh * 4) as usize];
            RendererCache::default().draw_notification_banner(&mut canvas, bw, bh, preview).unwrap();
            let banner = unsafe {
                ImageSurface::create_for_data_unsafe(canvas.as_mut_ptr(), Format::ARgb32, bw as i32, bh as i32, (bw * 4) as i32)
            }
            .unwrap();
            let g = banner_geometry(f64::from(w), f64::from(h));
            let cr = Context::new(&screen).unwrap();
            cr.set_source_surface(&banner, g.left, g.top).unwrap();
            cr.paint().unwrap();
            drop(cr);
            let mut png = fs::File::create(out.join(format!("banner-{name}-{w}x{h}.png"))).unwrap();
            screen.write_to_png(&mut png).unwrap();
        }
        fs::remove_file(&base).unwrap();
    }
}

//! Host renders of Settings' About and Date & time pages
//! (settings-has-about-and-date-time-pages 3.2): the Settings top page with
//! its two new rows, and both pages, at the landscape panel (1232x568) and the
//! native portrait panel (568x1232), at the 100% and the 200% vision text step.
//!
//! `cargo run --example render_settings_about_evidence -- <out-dir>` writes
//! `<case>-<step>-<WxH>.png`. Host render only: it proves paint and layout,
//! not the board's glass. The rows are FIXTURE values (no real store path,
//! kernel or clock), so the images carry nothing about any installed build.
use k230_shell_rust::{
    appearance::{AppearanceSnapshot, AppearanceToken},
    device_info::{InfoPublic, Page},
    evidence_render::fixture_settings,
    render::{RenderParams, RendererCache},
    service_ui::ServiceView,
    Route,
};
use std::{collections::BTreeMap, env, fs, path::PathBuf};

fn theme(step: f64) -> AppearanceSnapshot {
    AppearanceSnapshot {
        generation: "fixture".into(),
        path: PathBuf::new(),
        icon_theme: None,
        background: None,
        selected_background: None,
        backgrounds: vec![],
        palette: BTreeMap::new(),
        sections: BTreeMap::from([(
            "accessibility".to_string(),
            BTreeMap::from([("text-scale".to_string(), AppearanceToken::Number(step))]),
        )]),
        applied: vec![],
        unavailable: vec![],
        unknown: vec![],
    }
}

fn about() -> InfoPublic {
    InfoPublic {
        page: Page::About,
        rows: vec![
            ("Device", "k230".into()),
            ("System", "ab12cd34 \u{b7} nixos-system-k230-26.05.20261026".into()),
            ("Kernel", "7.0.0-k230".into()),
            ("Uptime", "3 d 4 h".into()),
            ("Storage", "14.2 GB free of 29.8 GB".into()),
            ("Shell", "0.1.0 \u{b7} ef56gh78".into()),
        ],
    }
}

fn date_time() -> InfoPublic {
    InfoPublic {
        page: Page::DateTime,
        rows: vec![
            ("Date", "Monday, October 26 2026".into()),
            ("Time", "14:05:09".into()),
            ("Time zone", "America/Chicago (UTC-05:00)".into()),
            ("Network time", "Synchronized".into()),
            ("Clock format", "24-hour".into()),
        ],
    }
}

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_settings_about_evidence <out-dir>"));
    fs::create_dir_all(&out).unwrap();
    for (step_name, step) in [("100", 1.0), ("200", 2.0)] {
        for (w, h) in [(1232u32, 568u32), (568, 1232)] {
            let base = ServiceView { settings: Some(fixture_settings()), ..ServiceView::default() };
            let cases = [
                ("settings", base.clone()),
                ("about", ServiceView { info_page: Some(about()), ..base.clone() }),
                ("date-time", ServiceView { info_page: Some(date_time()), ..base }),
            ];
            for (name, view) in cases {
                let mut cache = RendererCache::default();
                cache.set_appearance(Some(theme(step)));
                cache.set_services(view);
                let mut canvas = vec![0u8; (w * h * 4) as usize];
                cache
                    .draw(
                        &mut canvas,
                        RenderParams { width: w, height: h, route: Route::Settings, progress: 1.0, scroll: 0.0 },
                        &[],
                    )
                    .unwrap();
                let path = out.join(format!("{name}-{step_name}-{w}x{h}.png"));
                write_png(&path, &mut canvas, w, h);
            }
        }
        eprintln!("rendered step {step_name}");
    }
}

fn write_png(path: &std::path::Path, canvas: &mut [u8], w: u32, h: u32) {
    use cairo::{Format, ImageSurface};
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(canvas.as_mut_ptr(), Format::ARgb32, w as i32, h as i32, (w * 4) as i32)
    }
    .unwrap();
    surface.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

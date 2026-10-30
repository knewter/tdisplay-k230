//! Host renders of the 12-hour clock (settings-chooses-a-12-or-24-hour-clock
//! 2.1): Date & time with the switch on, the shade's time, and Home's three
//! digit clock styles, at the landscape panel (1232x568) and the native
//! portrait panel (568x1232), at the 100% and the 200% vision text step.
//!
//! `cargo run --example render_clock_format_evidence -- <out-dir>` writes
//! `<case>-<step>-<WxH>.png`. Host render only: it proves paint and layout,
//! not the board's glass. Date & time's rows are FIXTURE values; the shade and
//! Home show the host's clock at render time, in 12-hour form.
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    appearance::{AppearanceSnapshot, AppearanceToken},
    device_info::{InfoPublic, Page, CLOCK_FORMAT_LABEL},
    evidence_render::fixture_settings,
    home_grid::{self, HomeSlot},
    home_screen::HomeScreen,
    home_state::{HomeItem, HomeLayout, WidgetKind},
    home_widgets::clock,
    icon::IconCache,
    render::{self, RenderParams, RendererCache},
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

fn date_time() -> InfoPublic {
    InfoPublic::new(
        Page::DateTime,
        vec![
            ("Date", "Thursday, October 29 2026".into()),
            ("Time", "9:05:09 PM".into()),
            ("Time zone", "America/Chicago (UTC-05:00)".into()),
            ("Network time", "Synchronized".into()),
            (CLOCK_FORMAT_LABEL, "12-hour".into()),
        ],
    )
}

fn home(path: PathBuf, theme: &AppearanceSnapshot, kind: WidgetKind, w: u32, h: u32) {
    let per_page = home_grid::apps_per_page(w, h);
    let mut layout = HomeLayout {
        columns: home_grid::columns_for_width(w),
        dock: vec![None; home_grid::DOCK_SLOTS],
        ..HomeLayout::default()
    };
    layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: kind }, per_page, false);
    let screen = HomeScreen::new(layout, f64::from(w));
    let target = ImageSurface::create(Format::ARgb32, w as i32, h as i32).unwrap();
    {
        let cr = Context::new(&target).unwrap();
        cr.set_source_rgb(0.05, 0.55, 0.52);
        cr.paint().unwrap();
        render::paint_home(&cr, w, h, Some(theme), &screen, &[], &mut IconCache::new());
    }
    target.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_clock_format_evidence <out-dir>"));
    fs::create_dir_all(&out).unwrap();
    clock::set_twelve_hour(true);
    for (step_name, step) in [("100", 1.0), ("200", 2.0)] {
        for (w, h) in [(1232u32, 568u32), (568, 1232)] {
            let mut cache = RendererCache::default();
            cache.set_appearance(Some(theme(step)));
            cache.set_services(ServiceView {
                settings: Some(fixture_settings()),
                info_page: Some(date_time()),
                ..ServiceView::default()
            });
            let mut canvas = vec![0u8; (w * h * 4) as usize];
            cache
                .draw(&mut canvas, RenderParams { width: w, height: h, route: Route::Settings, progress: 1.0, scroll: 0.0 }, &[])
                .unwrap();
            write_png(&out.join(format!("date-time-{step_name}-{w}x{h}.png")), &mut canvas, w, h);
            for (name, kind) in [("bubble", WidgetKind::Clock), ("thin", WidgetKind::ClockMinimal), ("dot-matrix", WidgetKind::ClockDotMatrix)] {
                home(out.join(format!("home-{name}-{step_name}-{w}x{h}.png")), &theme(step), kind, w, h);
            }
            let mut cache = RendererCache::default();
            cache.set_appearance(Some(theme(step)));
            cache.set_services(ServiceView { settings: Some(fixture_settings()), ..ServiceView::default() });
            let mut canvas = vec![0u8; (w * h * 4) as usize];
            cache
                .draw(&mut canvas, RenderParams { width: w, height: h, route: Route::Shade, progress: 1.0, scroll: 0.0 }, &[])
                .unwrap();
            write_png(&out.join(format!("shade-{step_name}-{w}x{h}.png")), &mut canvas, w, h);
        }
        eprintln!("rendered step {step_name}");
    }
}

fn write_png(path: &std::path::Path, canvas: &mut [u8], w: u32, h: u32) {
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(canvas.as_mut_ptr(), Format::ARgb32, w as i32, h as i32, (w * 4) as i32)
    }
    .unwrap();
    surface.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

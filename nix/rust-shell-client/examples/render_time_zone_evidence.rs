//! Host renders of Settings' time zone and network time controls
//! (settings-sets-the-time-zone-and-network-time 2.2): Date & time with its
//! zone link and two switches, the area page, and an area's paged zones, at
//! the landscape panel (1232x568) and the native portrait panel (568x1232),
//! at the 100% and the 200% vision text step.
//!
//! `cargo run --example render_time_zone_evidence -- <out-dir> [<zoneinfo>]`
//! writes `<case>-<step>-<WxH>.png`. The chooser reads the host's tzdata
//! (`/usr/share/zoneinfo` by default) through the same `InfoView` the shell
//! drives, so its pages are the real flow. Date & time's rows are FIXTURE
//! values. Host render only: it proves paint and layout, not the board.
use cairo::{Format, ImageSurface};
use k230_shell_rust::{
    appearance::{AppearanceSnapshot, AppearanceToken},
    device_info::{self, InfoPublic, InfoView, Page, Sources, CLOCK_FORMAT_LABEL, NETWORK_TIME_LABEL, TIME_ZONE_LABEL},
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

fn date_time(network_on: bool) -> InfoPublic {
    InfoPublic::new(
        Page::DateTime,
        vec![
            ("Date", "Thursday, October 29 2026".into()),
            ("Time", "21:00:09".into()),
            (TIME_ZONE_LABEL, "Europe/London (UTC+00:00)".into()),
            (NETWORK_TIME_LABEL, if network_on { "Synchronized" } else { device_info::NETWORK_TIME_OFF_VALUE }.into()),
            (CLOCK_FORMAT_LABEL, "24-hour".into()),
        ],
    )
}

fn draw(path: PathBuf, page: InfoPublic, step: f64, w: u32, h: u32) {
    let mut cache = RendererCache::default();
    cache.set_appearance(Some(theme(step)));
    cache.set_services(ServiceView { settings: Some(fixture_settings()), info_page: Some(page), ..ServiceView::default() });
    let mut canvas = vec![0u8; (w * h * 4) as usize];
    cache
        .draw(&mut canvas, RenderParams { width: w, height: h, route: Route::Settings, progress: 1.0, scroll: 0.0 }, &[])
        .unwrap();
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(canvas.as_mut_ptr(), Format::ARgb32, w as i32, h as i32, (w * 4) as i32)
    }
    .unwrap();
    surface.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

fn main() {
    let mut args = env::args().skip(1);
    let out = PathBuf::from(args.next().expect("usage: render_time_zone_evidence <out-dir> [<zoneinfo>]"));
    let zoneinfo = PathBuf::from(args.next().unwrap_or_else(|| "/usr/share/zoneinfo".into()));
    fs::create_dir_all(&out).unwrap();
    // A fixture root whose etc/zoneinfo is the host's tzdata.
    let root = env::temp_dir().join(format!("k230-time-zone-evidence-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("etc")).unwrap();
    std::os::unix::fs::symlink(&zoneinfo, root.join("etc/zoneinfo")).unwrap();
    let src = Sources { root: root.clone(), exe: None };
    let mut view = InfoView::default();
    view.open(Page::Regions, &src);
    let regions = view.public().unwrap();
    let europe = regions.rows.iter().position(|r| r.1 == "Europe").expect("Europe in tzdata");
    view.choose(europe, &src);
    let zones = view.public().unwrap();
    eprintln!("{} areas, Europe has {} zones", regions.rows.len(), zones.rows.len());
    for (step_name, step) in [("100", 1.0), ("200", 2.0)] {
        k230_shell_rust::set_layout_text_scale(step);
        for (w, h) in [(1232u32, 568u32), (568, 1232)] {
            draw(out.join(format!("date-time-{step_name}-{w}x{h}.png")), date_time(true), step, w, h);
            draw(out.join(format!("date-time-network-off-{step_name}-{w}x{h}.png")), date_time(false), step, w, h);
            draw(out.join(format!("areas-{step_name}-{w}x{h}.png")), regions.clone(), step, w, h);
            draw(out.join(format!("europe-page-1-{step_name}-{w}x{h}.png")), zones.clone(), step, w, h);
            let (_, pager) = device_info::window(&zones, w, h);
            let mut second = zones.clone();
            second.page_index = 1;
            if pager.is_some_and(|(_, pages)| pages > 1) {
                draw(out.join(format!("europe-page-2-{step_name}-{w}x{h}.png")), second, step, w, h);
            }
            eprintln!("{step_name} {w}x{h}: Europe {:?}", device_info::window(&zones, w, h));
        }
    }
    let _ = fs::remove_dir_all(root);
}

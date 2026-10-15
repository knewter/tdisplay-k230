//! Host renders of the Battery - Details charge graph
//! (`openspec/changes/battery-details-graphs-charge-over-time`, task 2.1).
//!
//! `cargo run --example render_battery_history_evidence -- <out-dir>` writes
//! `<state>-<W>x<H>.png` for a fixture history (a discharge, a gap where the
//! shell was off, a charge and a short discharge) and for a fresh history with
//! one sample. Host render only: the history and the gauge values are
//! invented fixtures, not board captures.
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    evidence_render::synthetic_apps,
    home_grid::{self, HomeSlot},
    home_screen::HomeScreen,
    home_state::{HomeItem, HomeLayout, WidgetKind},
    home_widgets::battery::{
        history::{History, View},
        read_details, DetailsState,
    },
    icon::IconCache,
    render,
};
use std::{env, fs, path::PathBuf};

/// A discharging fixture (not a board capture).
const GAUGE_DISCHARGING: &str = "POWER_SUPPLY_TYPE=Battery\nPOWER_SUPPLY_STATUS=Discharging\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_CYCLE_COUNT=0\nPOWER_SUPPLY_VOLTAGE_NOW=3890000\nPOWER_SUPPLY_CURRENT_NOW=-412000\nPOWER_SUPPLY_CAPACITY=71\nPOWER_SUPPLY_TIME_TO_EMPTY_NOW=18600\nPOWER_SUPPLY_CHARGE_FULL=3000000\nPOWER_SUPPLY_CHARGE_FULL_DESIGN=3000000\nPOWER_SUPPLY_CHARGE_NOW=2130000\nPOWER_SUPPLY_TEMP=342\n";
const CHARGER_OFFLINE: &str = "POWER_SUPPLY_TYPE=USB\nPOWER_SUPPLY_ONLINE=0\nPOWER_SUPPLY_HEALTH=Good\n";
const NOW: i64 = 1_792_100_000;

fn details() -> DetailsState {
    let dir = env::temp_dir().join(format!("k230-history-evidence-{}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    for (name, uevent) in [("bq25890-charger-0", CHARGER_OFFLINE), ("bq27220-0", GAUGE_DISCHARGING)] {
        fs::create_dir_all(dir.join(name)).unwrap();
        fs::write(dir.join(name).join("uevent"), uevent).unwrap();
    }
    let state = read_details(&dir).quantized();
    fs::remove_dir_all(&dir).unwrap();
    state
}

/// 11.5 h ago: 90 -> 40 % over 6 h; the shell off for 20 min; a 3 h charge
/// to 78 %; then a discharge to 71 % now.
fn day_history() -> View {
    let mut history = History::load(None, 0);
    let mut t = NOW - 11 * 3600 - 1800;
    let lerp = |from: f64, to: f64, i: i64, n: i64| (from + (to - from) * i as f64 / n as f64).round() as u8;
    let n = 6 * 60;
    for i in 0..=n {
        history.record(t, lerp(90.0, 40.0, i, n), false);
        t += 60;
    }
    t += 20 * 60;
    let n = 3 * 60;
    for i in 0..=n {
        history.record(t, lerp(40.0, 78.0, i, n), true);
        t += 60;
    }
    let n = (NOW - t) / 60;
    for i in 0..=n {
        history.record(t, lerp(78.0, 71.0, i, n), false);
        t += 60;
    }
    history.view(NOW)
}

fn fresh_history() -> View {
    let mut history = History::load(None, 0);
    history.record(NOW - 10, 71, false);
    history.view(NOW)
}

fn render(path: &std::path::Path, width: u32, height: u32, details: &DetailsState, view: &View) {
    let apps = synthetic_apps(8);
    let apps_per_page = home_grid::apps_per_page(width, height);
    let mut layout = HomeLayout {
        columns: home_grid::columns_for_width(width),
        dock: vec![None; home_grid::DOCK_SLOTS],
        ..HomeLayout::default()
    };
    layout.place(HomeSlot::Grid { page: 0, slot: 0 }, HomeItem::Widget { widget: WidgetKind::BatteryDetails }, apps_per_page, false);
    for app in apps.iter().take(4) {
        layout.place_first_fit(HomeItem::app(app.id.clone()), apps_per_page);
    }
    for (index, app) in apps.iter().take(home_grid::DOCK_SLOTS).enumerate() {
        layout.place(HomeSlot::Dock { slot: index }, HomeItem::app(app.id.clone()), 4, false);
    }
    let mut home = HomeScreen::new(layout, f64::from(width));
    home.battery_details = details.clone();
    home.battery_history = view.clone();
    let content = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&content).unwrap();
        let mut icons = IconCache::new();
        render::paint_home(&cr, width, height, None, &home, &apps, &mut icons);
    }
    let out = ImageSurface::create(Format::ARgb32, width as i32, height as i32).unwrap();
    {
        let cr = Context::new(&out).unwrap();
        cr.set_source_rgb(f64::from(0x1e) / 255.0, f64::from(0x1e) / 255.0, f64::from(0x2e) / 255.0);
        cr.paint().unwrap();
        cr.set_source_surface(&content, 0.0, 0.0).unwrap();
        cr.paint().unwrap();
    }
    out.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_battery_history_evidence <out-dir>"));
    fs::create_dir_all(&out).unwrap();
    let details = details();
    let states = [("day", day_history()), ("fresh", fresh_history())];
    for (w, h) in [(568u32, 1232u32), (1232, 568), (1280, 800), (1920, 1080)] {
        for (name, view) in &states {
            render(&out.join(format!("{name}-{w}x{h}.png")), w, h, &details, view);
        }
    }
    println!("wrote {}", out.display());
}

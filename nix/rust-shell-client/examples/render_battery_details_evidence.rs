//! Host renders of the Battery - Details Home widget
//! (`openspec/changes/home-offers-a-battery-details-widget`, task 2.1).
//!
//! `cargo run --example render_battery_details_evidence -- <out-dir>` writes
//! `<state>-<W>x<H>.png` for a charging, a discharging and a no-battery
//! state at the portrait panel, the landscape panel and a 1280x800 HDMI
//! surface, plus the widget picker. Host render only: it proves paint and
//! layout from fixture values, not the board's glass or its real sysfs.
use cairo::{Context, Format, ImageSurface};
use k230_shell_rust::{
    evidence_render::synthetic_apps,
    home_grid::{self, HomeSlot},
    home_screen::{HomeScreen, WidgetPicker, WidgetPickerPage},
    home_state::{HomeItem, HomeLayout, WidgetKind},
    home_widgets::battery::{read_details, DetailsState},
    icon::IconCache,
    render,
};
use std::{env, fs, path::PathBuf};

/// The board's real uevent text from 2026-10-15 (charging over USB-C).
const GAUGE_CHARGING: &str = "POWER_SUPPLY_TYPE=Battery\nPOWER_SUPPLY_STATUS=Charging\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\nPOWER_SUPPLY_TECHNOLOGY=Li-ion\nPOWER_SUPPLY_CYCLE_COUNT=0\nPOWER_SUPPLY_VOLTAGE_NOW=4202000\nPOWER_SUPPLY_CURRENT_NOW=600000\nPOWER_SUPPLY_POWER_AVG=2540000\nPOWER_SUPPLY_CHARGE_FULL_DESIGN=3000000\nPOWER_SUPPLY_CHARGE_FULL=3000000\nPOWER_SUPPLY_CHARGE_NOW=1627000\nPOWER_SUPPLY_CAPACITY=55\nPOWER_SUPPLY_CAPACITY_LEVEL=Normal\nPOWER_SUPPLY_TEMP=381\nPOWER_SUPPLY_TIME_TO_FULL_NOW=8160\n";
const CHARGER_ONLINE: &str = "POWER_SUPPLY_TYPE=USB\nPOWER_SUPPLY_STATUS=Charging\nPOWER_SUPPLY_CHARGE_TYPE=Fast\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_VOLTAGE_NOW=4204000\nPOWER_SUPPLY_CURRENT_NOW=-550000\nPOWER_SUPPLY_CONSTANT_CHARGE_CURRENT=2048000\nPOWER_SUPPLY_CONSTANT_CHARGE_VOLTAGE=4208000\nPOWER_SUPPLY_INPUT_CURRENT_LIMIT=3250000\nPOWER_SUPPLY_TEMP=380\n";
/// A discharging fixture (not a board capture): negative current, time to empty.
const GAUGE_DISCHARGING: &str = "POWER_SUPPLY_TYPE=Battery\nPOWER_SUPPLY_STATUS=Discharging\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_CYCLE_COUNT=37\nPOWER_SUPPLY_VOLTAGE_NOW=3890000\nPOWER_SUPPLY_CURRENT_NOW=-412000\nPOWER_SUPPLY_CAPACITY=71\nPOWER_SUPPLY_TIME_TO_EMPTY_NOW=2700\nPOWER_SUPPLY_CHARGE_FULL=2850000\nPOWER_SUPPLY_CHARGE_FULL_DESIGN=3000000\nPOWER_SUPPLY_CHARGE_NOW=2025000\nPOWER_SUPPLY_TEMP=342\n";
const CHARGER_OFFLINE: &str = "POWER_SUPPLY_TYPE=USB\nPOWER_SUPPLY_ONLINE=0\nPOWER_SUPPLY_HEALTH=Good\n";

fn fixture(tag: &str, supplies: &[(&str, &str)]) -> DetailsState {
    let dir = env::temp_dir().join(format!("k230-details-evidence-{tag}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    for (name, uevent) in supplies {
        fs::create_dir_all(dir.join(name)).unwrap();
        fs::write(dir.join(name).join("uevent"), uevent).unwrap();
    }
    fs::create_dir_all(&dir).unwrap();
    let state = read_details(&dir).quantized();
    fs::remove_dir_all(&dir).unwrap();
    state
}

fn render(path: &std::path::Path, width: u32, height: u32, details: &DetailsState, picker: bool) {
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
    if picker {
        home.widget_picker = Some(WidgetPicker { page: WidgetPickerPage::Widgets });
    }
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
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_battery_details_evidence <out-dir>"));
    fs::create_dir_all(&out).unwrap();
    let states = [
        ("charging", fixture("c", &[("bq25890-charger-0", CHARGER_ONLINE), ("bq27220-0", GAUGE_CHARGING)])),
        ("discharging", fixture("d", &[("bq25890-charger-0", CHARGER_OFFLINE), ("bq27220-0", GAUGE_DISCHARGING)])),
        ("no-battery", fixture("n", &[("bq25890-charger-0", CHARGER_ONLINE)])),
    ];
    for (w, h) in [(568u32, 1232u32), (1232, 568), (1280, 800), (1920, 1080)] {
        for (name, state) in &states {
            render(&out.join(format!("{name}-{w}x{h}.png")), w, h, state, false);
        }
    }
    render(&out.join("picker-568x1232.png"), 568, 1232, &states[0].1, true);
    println!("wrote {}", out.display());
}

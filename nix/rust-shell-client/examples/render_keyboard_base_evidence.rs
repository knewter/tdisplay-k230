//! Host renders for keyboard-base task 6.3: the shade's battery line and
//! Settings' Key backlight row, with and without a fake `power_supply` and
//! LED tree. The views come from `keyboard_base::read_view_state`, the same
//! reader the live client uses, pointed at temporary trees instead of sysfs.
//!
//! `cargo run --example render_keyboard_base_evidence -- <out-dir>` writes
//! `{shade,settings}-{with,without}-base-{568x1232,1232x568}.png`.
//! Host render only: it proves the paint and gating, not the board's glass.
use k230_shell_rust::{
    evidence_render::{fixture_settings, render_route_with_services},
    keyboard_base::{self, BACKLIGHT_LED},
    service_data::NotificationSnapshot,
    service_ui::ServiceView,
    Route,
};
use std::{env, fs, path::Path};

fn fake_base(root: &Path) {
    let gauge = root.join("power_supply/bq27220-0");
    fs::create_dir_all(&gauge).unwrap();
    fs::write(gauge.join("type"), "Battery\n").unwrap();
    fs::write(gauge.join("capacity"), "64\n").unwrap();
    fs::write(gauge.join("status"), "Charging\n").unwrap();
    let led = root.join("leds").join(BACKLIGHT_LED);
    fs::create_dir_all(&led).unwrap();
    fs::write(led.join("brightness"), "0\n").unwrap();
    fs::write(led.join("max_brightness"), "1\n").unwrap();
}

fn view(root: &Path) -> ServiceView {
    let (battery, key_backlight) = keyboard_base::read_view_state(
        &root.join("power_supply"),
        &root.join("leds"),
        &root.join("key-backlight"),
    );
    ServiceView {
        settings: Some(fixture_settings()),
        notifications: Some(NotificationSnapshot { count: 0, events: vec![], preview: None }),
        battery,
        key_backlight,
        ..ServiceView::default()
    }
}

fn main() {
    let out = env::args().nth(1).expect("usage: render_keyboard_base_evidence <out-dir>");
    let out = Path::new(&out);
    fs::create_dir_all(out).unwrap();
    let scratch = env::temp_dir().join(format!("k230-kbd-evidence-{}", std::process::id()));
    let (with, without) = (scratch.join("with"), scratch.join("without"));
    fs::create_dir_all(&with).unwrap();
    fs::create_dir_all(without.join("power_supply")).unwrap(); // an empty class: no gauge, no LED
    fake_base(&with);
    for (tag, root) in [("with", &with), ("without", &without)] {
        for (route, name) in [(Route::Shade, "shade"), (Route::Settings, "settings")] {
            for (w, h) in [(568, 1232), (1232, 568)] {
                let path = out.join(format!("{name}-{tag}-base-{w}x{h}.png"));
                render_route_with_services(&path, w, h, route, view(root));
                println!("{}", path.display());
            }
        }
    }
    fs::remove_dir_all(&scratch).unwrap();
}

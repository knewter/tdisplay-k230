//! Host renders of the modem UI (the-nrf9151-gives-the-handheld-cellular-sms-
//! and-location 6.1): the shade's signal and location indicators, Settings
//! with and without the Cellular and Location rows, and both pages, drawn
//! from fake `state.json` files at the landscape panel (1232x568) and the
//! native portrait panel (568x1232).
//!
//! `cargo run --example render_modem_evidence -- <out-dir>` writes the fake
//! state files and `<surface>-<WxH>.png`. Host render only: it proves paint
//! and layout, not the board's glass or a real modem.
use k230_shell_rust::{
    evidence_render::{fixture_notification_events, fixture_settings, render_route_with_views},
    home_widgets::battery::BatteryState,
    modem::{read_status, ModemStatus},
    modem_ui::{ModemView, Page},
    service_data::NotificationSnapshot,
    service_ui::ServiceView,
    Route,
};
use std::{env, fs, path::{Path, PathBuf}};

/// A `state.json` as the service writes it, with `edits` applied.
fn fake_state(dir: &Path, name: &str, edits: &[(&str, serde_json::Value)]) -> ModemStatus {
    let mut state = serde_json::json!({
        "schema": 1, "updated": 1_700_000_000u64, "power": "on", "present": true,
        "cellular": true, "location": false, "sim": "ready", "pin_attempts": null,
        "registration": "registered_home", "operator": "Example Net", "rat": "LTE-M",
        "rsrp": -95, "bars": 3, "gnss": "off", "modem_firmware": "mfw_nrf91x1_2.0.3",
        "slm_version": "2.9.0", "sms_count": 3, "last_error": null
    });
    for (key, value) in edits {
        state[*key] = value.clone();
    }
    let path = dir.join(format!("state-{name}.json"));
    fs::write(&path, state.to_string()).unwrap();
    read_status(&path).expect("a present fake state parses")
}

fn page(status: &ModemStatus, which: Page, digits: &[u8]) -> ServiceView {
    let mut view = ModemView::default();
    view.set_status(Some(status.clone()));
    view.open(which);
    for digit in digits {
        view.digit(*digit);
    }
    ServiceView {
        settings: Some(fixture_settings()),
        modem: Some(status.clone()),
        modem_page: view.public(),
        ..ServiceView::default()
    }
}

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_modem_evidence <out-dir>"));
    fs::create_dir_all(&out).unwrap();
    use serde_json::json;
    let on_net = fake_state(&out, "cellular-3-bars", &[]);
    let both_search = fake_state(&out, "both-searching", &[("location", json!(true)), ("gnss", json!("searching"))]);
    let fix_no_service = fake_state(
        &out,
        "fix-no-service",
        &[("location", json!(true)), ("gnss", json!("fix")), ("registration", json!("searching")), ("bars", json!(0))],
    );
    let both_off = fake_state(&out, "both-off", &[("cellular", json!(false)), ("power", json!("off")), ("sim", json!("unknown")), ("registration", json!("unknown")), ("operator", json!(null)), ("rat", json!(null)), ("bars", json!(0))]);
    let no_sim = fake_state(&out, "no-sim", &[("sim", json!("absent")), ("registration", json!("unknown")), ("operator", json!(null)), ("rat", json!(null)), ("bars", json!(0)), ("sms_count", json!(0))]);
    let pin = fake_state(&out, "pin-required", &[("sim", json!("pin_required")), ("pin_attempts", json!(3)), ("registration", json!("unknown")), ("operator", json!(null)), ("rat", json!(null)), ("bars", json!(0))]);
    let loc_fix = fake_state(&out, "location-fix", &[("cellular", json!(false)), ("location", json!(true)), ("gnss", json!("fix"))]);
    let loc_search = fake_state(&out, "location-searching", &[("cellular", json!(false)), ("location", json!(true)), ("gnss", json!("searching"))]);
    let loc_off = fake_state(&out, "location-off", &[("cellular", json!(false)), ("power", json!("off"))]);

    for (w, h) in [(1232u32, 568u32), (568, 1232)] {
        let shade = |status: Option<&ModemStatus>, battery: bool| ServiceView {
            settings: Some(fixture_settings()),
            notifications: Some(NotificationSnapshot { count: 2, events: fixture_notification_events(2), preview: None }),
            battery: if battery {
                BatteryState::Present { percent: 64, status: "Discharging".into() }
            } else {
                BatteryState::Absent
            },
            modem: status.cloned(),
            ..ServiceView::default()
        };
        let named = [
            ("shade-no-modem", shade(None, true)),
            ("shade-both-off", shade(Some(&both_off), true)),
            ("shade-cellular-3-bars", shade(Some(&on_net), true)),
            ("shade-both-searching", shade(Some(&both_search), true)),
            ("shade-fix-no-service", shade(Some(&fix_no_service), true)),
            ("shade-both-searching-no-battery", shade(Some(&both_search), false)),
            ("settings-no-modem", ServiceView { settings: Some(fixture_settings()), ..ServiceView::default() }),
            ("settings-with-modem", ServiceView { settings: Some(fixture_settings()), modem: Some(on_net.clone()), ..ServiceView::default() }),
            ("settings-with-modem-no-sim", ServiceView { settings: Some(fixture_settings()), modem: Some(no_sim.clone()), ..ServiceView::default() }),
            ("cellular-registered", page(&on_net, Page::Cellular, &[])),
            ("cellular-off", page(&both_off, Page::Cellular, &[])),
            ("cellular-no-sim", page(&no_sim, Page::Cellular, &[])),
            ("cellular-pin", page(&pin, Page::Cellular, &[4, 8, 2])),
            ("location-searching", page(&loc_search, Page::Location, &[])),
            ("location-fix", page(&loc_fix, Page::Location, &[])),
            ("location-off", page(&loc_off, Page::Location, &[])),
        ];
        for (name, view) in named {
            let route = if name.starts_with("shade") { Route::Shade } else { Route::Settings };
            render_route_with_views(&out.join(format!("{name}-{w}x{h}.png")), w, h, route, view, None);
        }
        eprintln!("rendered {w}x{h}");
    }
}

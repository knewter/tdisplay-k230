//! Host renders of the landscape shade (the-shade-leads-with-time-and-quick-
//! tiles 1.3): the time header, status line, quick tiles, sliders and the
//! list heading, with and without the modem and notifications, at the
//! landscape panel (1232x568), and the unchanged portrait panel (568x1232).
//!
//! `cargo run --example render_shade_pass_evidence -- <out-dir>` writes
//! `shade-<case>-<WxH>.png`. Host render only: it proves paint and layout,
//! not the board's glass. The time is the host's clock at render time.
use k230_shell_rust::{
    evidence_render::{fixture_notification_events, fixture_settings, render_route_with_views},
    home_widgets::battery::BatteryState,
    modem::parse_status,
    pipewire_ipc::{GraphSnapshot, Sink},
    service_data::{ControlValue, NotificationSnapshot},
    service_ui::ServiceView,
    Route,
};
use std::{env, path::PathBuf};

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_shade_pass_evidence <out-dir>"));
    std::fs::create_dir_all(&out).unwrap();
    let modem = |location: bool| {
        parse_status(
            serde_json::json!({
                "schema": 1, "updated": 1, "power": "on", "present": true, "cellular": true,
                "location": location, "sim": "ready", "registration": "registered_home",
                "operator": "Example Net", "rat": "LTE-M", "bars": 3,
                "gnss": if location { "searching" } else { "off" }, "sms_count": 0
            })
            .to_string()
            .as_bytes(),
        )
        .unwrap()
    };
    let view = |count: usize, with_modem: Option<bool>| {
        let mut settings = fixture_settings();
        settings.network.value = Some(ControlValue::Text("link-up".into()));
        ServiceView {
            settings: Some(settings),
            notifications: Some(NotificationSnapshot { count, events: fixture_notification_events(count), preview: None }),
            battery: BatteryState::Present { percent: 64, status: "Discharging".into() },
            modem: with_modem.map(modem),
            audio: Some(GraphSnapshot {
                sinks: vec![Sink {
                    id: 1,
                    name: "speaker".into(),
                    description: "Speaker".into(),
                    linear_volume: 0.4,
                    muted: false,
                    is_default: true,
                    route: None,
                }],
                streams: vec![],
            }),
            ..ServiceView::default()
        }
    };
    for (w, h) in [(1232u32, 568u32), (568, 1232)] {
        for (name, v) in [
            ("no-modem-2", view(2, None)),
            ("no-modem-empty", view(0, None)),
            ("modem-location-off-4", view(4, Some(false))),
            ("modem-location-on-4", view(4, Some(true))),
        ] {
            render_route_with_views(&out.join(format!("shade-{name}-{w}x{h}.png")), w, h, Route::Shade, v, None);
        }
        eprintln!("rendered {w}x{h}");
    }
}

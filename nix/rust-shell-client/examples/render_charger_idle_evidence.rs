//! Host renders of Settings with the "Idle on charger" row
//! (the-charging-display-shows-an-exhibition-clock 2.5): Clock and Sleep,
//! with and without the modem, at 100% and at the largest vision text step
//! (200%), on the 1232x568 panel, scrolled so the row's column is in view.
//!
//! `cargo run --offline --example render_charger_idle_evidence -- <out-dir>`
//! writes `settings-<modem>-charger-<clock|sleep>-<step>-1232x568.png`. Host
//! render only: it proves paint and layout, not the board's glass.
use k230_shell_rust::{
    appearance::{AppearanceSnapshot, AppearanceToken},
    evidence_render::{fixture_notification_events, fixture_settings},
    render::{
        settings_info_row_index, settings_modem_row_h, settings_modem_row_y, settings_wide_offset_for,
        RenderParams, RendererCache,
    },
    home_widgets::battery::BatteryState,
    modem::parse_status,
    pipewire_ipc::{GraphSnapshot, Sink},
    service_data::{ControlValue, NotificationSnapshot},
    service_ui::{settings_max_scroll, ServiceView},
    shell_prefs::ChargerIdle,
    Route,
};
use std::{collections::BTreeMap, env, fs, path::PathBuf};

/// A theme carrying only the person's vision text step, as the shell's
/// appearance service delivers it (`accessibility.text-scale`).
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

fn write_png(path: &std::path::Path, canvas: &mut [u8], w: u32, h: u32) {
    use cairo::{Format, ImageSurface};
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(canvas.as_mut_ptr(), Format::ARgb32, w as i32, h as i32, (w * 4) as i32)
    }
    .unwrap();
    surface.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_charger_idle_evidence <out-dir>"));
    fs::create_dir_all(&out).unwrap();
    let modem = || {
        parse_status(
            serde_json::json!({
                "schema": 1, "updated": 1, "power": "on", "present": true, "cellular": true,
                "location": true, "sim": "ready", "registration": "registered_home",
                "operator": "Example Net", "rat": "LTE-M", "bars": 3,
                "gnss": "searching", "sms_count": 0
            })
            .to_string()
            .as_bytes(),
        )
        .unwrap()
    };
    let view = |with_modem: bool, charger_idle: ChargerIdle| {
        let mut settings = fixture_settings();
        settings.network.value = Some(ControlValue::Text("link-up".into()));
        ServiceView {
            settings: Some(settings),
            notifications: Some(NotificationSnapshot { count: 2, events: fixture_notification_events(2), preview: None }),
            battery: BatteryState::Present { percent: 64, status: "Discharging".into() },
            modem: with_modem.then(modem),
            idle_on_charger: charger_idle,
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
    let (w, h) = (1232u32, 568u32);
    for (step_name, step) in [("100", 1.0), ("200", 2.0)] {
        for (modem_name, with_modem) in [("no-modem", false), ("modem", true)] {
            for (choice_name, choice) in [("clock", ChargerIdle::Clock), ("sleep", ChargerIdle::Sleep)] {
                let name = format!("settings-{modem_name}-charger-{choice_name}-{step_name}-{w}x{h}.png");
                let mut cache = RendererCache::default();
                cache.set_appearance(Some(theme(step)));
                // Scroll the third column so the row sits mid-panel, as the
                // Settings hit-region test does; the layout step is global.
                k230_shell_rust::set_layout_text_scale(step);
                let mut services = view(with_modem, choice);
                let index = settings_info_row_index(with_modem, 1);
                let (_, dy) = settings_wide_offset_for(2, false, with_modem);
                let row_y = settings_modem_row_y(false, index) + dy + settings_modem_row_h() / 2.0;
                services.settings_scroll = (row_y - h as f64 / 2.0).clamp(0.0, settings_max_scroll(w, h, &services));
                cache.set_services(services);
                let mut canvas = vec![0u8; (w * h * 4) as usize];
                cache
                    .draw(&mut canvas, RenderParams { width: w, height: h, route: Route::Settings, progress: 1.0, scroll: 0.0 }, &[])
                    .unwrap();
                write_png(&out.join(name), &mut canvas, w, h);
            }
        }
        eprintln!("rendered step {step_name}");
    }
}

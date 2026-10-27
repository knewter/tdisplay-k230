//! Host renders of the landscape shade with the Do Not Disturb tile
//! (do-not-disturb-quiets-banners-and-keeps-history 2.2 and 2.3): three tiles
//! across and two deep, quiet mode off and on, with and without the modem, at
//! 100% and at the largest vision text step (200%), plus Settings'
//! Do Not Disturb row.
//!
//! `cargo run --example render_do_not_disturb_evidence -- <out-dir>` writes
//! `shade-<modem>-dnd-<off|on>-<step>-1232x568.png` and
//! `settings-<modem>-dnd-<off|on>-<step>-1232x568.png`. Host render only: it
//! proves paint and layout, not the board's glass. The time is the host's
//! clock at render time.
use k230_shell_rust::{
    appearance::{AppearanceSnapshot, AppearanceToken},
    evidence_render::{fixture_notification_events, fixture_settings},
    render::{RenderParams, RendererCache},
    home_widgets::battery::BatteryState,
    modem::parse_status,
    pipewire_ipc::{GraphSnapshot, Sink},
    service_data::{ControlValue, NotificationSnapshot},
    service_ui::ServiceView,
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
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_do_not_disturb_evidence <out-dir>"));
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
    let view = |with_modem: bool, quiet: bool| {
        let mut settings = fixture_settings();
        settings.network.value = Some(ControlValue::Text("link-up".into()));
        ServiceView {
            settings: Some(settings),
            notifications: Some(NotificationSnapshot { count: 2, events: fixture_notification_events(2), preview: None }),
            battery: BatteryState::Present { percent: 64, status: "Discharging".into() },
            modem: with_modem.then(modem),
            do_not_disturb: quiet,
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
            for (dnd_name, quiet) in [("off", false), ("on", true)] {
                for (page, route) in [("shade", Route::Shade), ("settings", Route::Settings)] {
                    let name = format!("{page}-{modem_name}-dnd-{dnd_name}-{step_name}-{w}x{h}.png");
                    let mut cache = RendererCache::default();
                    cache.set_appearance(Some(theme(step)));
                    cache.set_services(view(with_modem, quiet));
                    let mut canvas = vec![0u8; (w * h * 4) as usize];
                    cache
                        .draw(&mut canvas, RenderParams { width: w, height: h, route, progress: 1.0, scroll: 0.0 }, &[])
                        .unwrap();
                    write_png(&out.join(name), &mut canvas, w, h);
                }
            }
        }
        eprintln!("rendered step {step_name}");
    }
}

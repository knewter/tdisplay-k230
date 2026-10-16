//! Host renders for the Shade's keyboard quick toggle and 99 px tap floor
//! (the-shell-offers-quick-toggles-and-vision-options B.3): the Shade with
//! no and four notifications, with the keyboard available and unavailable,
//! at the portrait panel, the landscape panel and a 1280x800 monitor.
//!
//! `cargo run --example render_shade_quick_toggles_evidence -- <out-dir>`
//! writes `shade-<notifications>-keyboard-<state>-<WxH>.png`. Host render
//! only: it proves paint and layout, not the board's glass.
use k230_shell_rust::{
    evidence_render::{fixture_notification_events, fixture_settings, render_route_with_views},
    pipewire_ipc::{GraphSnapshot, Sink},
    service_data::{ControlState, NotificationSnapshot},
    service_ui::ServiceView,
    Route,
};
use std::{env, path::PathBuf};

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_shade_quick_toggles_evidence <out-dir>"));
    std::fs::create_dir_all(&out).unwrap();
    for (w, h) in [(568u32, 1232u32), (1232, 568), (1280, 800)] {
        for count in [0usize, 4] {
            for (state, name) in [(ControlState::Action, "available"), (ControlState::Unavailable, "unavailable")] {
                let mut settings = fixture_settings();
                settings.keyboard.state = state;
                if state == ControlState::Unavailable {
                    settings.keyboard.label = "Unavailable".into();
                }
                let view = ServiceView {
                    settings: Some(settings),
                    notifications: Some(NotificationSnapshot { count, events: fixture_notification_events(count), preview: None }),
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
                };
                render_route_with_views(&out.join(format!("shade-{count}-keyboard-{name}-{w}x{h}.png")), w, h, Route::Shade, view, None);
            }
        }
        eprintln!("rendered {w}x{h}");
    }
}

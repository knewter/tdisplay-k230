//! Host renders of the surfaces the 2026-10-26 design review covered
//! (the-shell-and-its-apps-look-finished): the drawer, the empty shade,
//! Settings at rest and scrolled, and the theme chooser, in landscape
//! (1232x568) and portrait (568x1232).
//!
//! `cargo run --example render_design_review -- <out-dir>` writes
//! `<surface>-<WxH>.png`. Host render only: it proves paint and layout, not
//! the board's glass.

use k230_shell_rust::{
    evidence_render::{fixture_theme_view, render_route, render_route_with_views, synthetic_apps},
    home_widgets::battery::BatteryState,
    pipewire_ipc::{GraphSnapshot, Sink},
    service_data::{Control, ControlState, ControlValue, NotificationSnapshot, SettingsSnapshot},
    service_ui::ServiceView,
    Route,
};
use std::{env, path::PathBuf};

/// The values the board reported on 2026-10-26.
fn board_settings() -> SettingsSnapshot {
    let control = |state, value, label: &str, detail: Option<&str>| Control {
        state,
        value,
        label: label.into(),
        detail: detail.map(Into::into),
        action: None,
    };
    SettingsSnapshot {
        network: control(ControlState::ReadOnly, Some(ControlValue::Text("link-up".into())), "Network link available", None),
        brightness: control(ControlState::Writable, Some(ControlValue::Percent(58)), "Brightness", None),
        keyboard: control(ControlState::Action, None, "Toggle keyboard", None),
        motion: control(ControlState::Writable, Some(ControlValue::Boolean(false)), "Reduce motion", Some("Session preference")),
        volume: k230_shell_rust::service_data::unknown_volume_placeholder(),
    }
}

fn audio() -> GraphSnapshot {
    GraphSnapshot {
        sinks: vec![Sink {
            id: 1,
            name: "builtin".into(),
            description: "Built-in Audio Stereo".into(),
            linear_volume: 0.96,
            muted: false,
            is_default: true,
            route: None,
        }],
        streams: vec![],
    }
}

fn view(scroll: f64) -> ServiceView {
    ServiceView {
        settings: Some(board_settings()),
        notifications: Some(NotificationSnapshot { count: 0, events: vec![], preview: None }),
        audio: Some(audio()),
        battery: BatteryState::Present { percent: 100, status: "Full".into() },
        settings_scroll: scroll,
        keyboard_gesture_hint: true,
        ..ServiceView::default()
    }
}

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_design_review <out-dir>"));
    std::fs::create_dir_all(&out).unwrap();
    let apps = synthetic_apps(18);
    for (w, h) in [(1232u32, 568u32), (568, 1232)] {
        render_route(&out.join(format!("drawer-{w}x{h}.png")), w, h, Route::Drawer, &apps);
        render_route_with_views(&out.join(format!("shade-empty-{w}x{h}.png")), w, h, Route::Shade, view(0.0), None);
        render_route_with_views(&out.join(format!("settings-{w}x{h}.png")), w, h, Route::Settings, view(0.0), None);
        render_route_with_views(&out.join(format!("settings-scrolled-{w}x{h}.png")), w, h, Route::Settings, view(150.0), None);
        render_route_with_views(
            &out.join(format!("theme-chooser-{w}x{h}.png")),
            w,
            h,
            Route::Settings,
            view(0.0),
            Some(fixture_theme_view(7)),
        );
        eprintln!("rendered {w}x{h}");
    }
}

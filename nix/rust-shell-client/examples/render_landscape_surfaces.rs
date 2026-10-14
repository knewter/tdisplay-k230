//! Host renders of the remaining landscape (task 8.3) surfaces: the Wi-Fi
//! pages, the theme chooser, the open-folder overlay and the shade with real
//! notification rows, at the landscape panel (1232x568) and, for comparison,
//! the native portrait panel (568x1232).
//!
//! `cargo run --example render_landscape_surfaces -- <out-dir>` writes
//! `<surface>-<WxH>.png`. Host render only: it proves paint and layout, not
//! the board's glass.
use k230_shell_rust::{
    evidence_render::{
        fixture_notification_events, fixture_settings, fixture_theme_view, fixture_wifi,
        render_home_with_open_folder, render_route_with_views, synthetic_apps,
    },
    pipewire_ipc::{GraphSnapshot, Sink},
    service_data::NotificationSnapshot,
    service_ui::ServiceView,
    wifi_ui::Page,
    Route,
};
use std::{env, path::PathBuf};

const LONG: &str = "A Rather Long Network Name For The Neighbours Upstairs";
const HOME: &str = "Home Network";
const OPEN: &str = "Guest (open)";

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_landscape_surfaces <out-dir>"));
    std::fs::create_dir_all(&out).unwrap();
    let apps = synthetic_apps(30);
    for (w, h) in [(1232u32, 568u32), (568, 1232)] {
        // The on-screen keyboard's default height on each panel.
        let keyboard = if w > h { 240.0 } else { 440.0 };
        let wifi = |page, selected: Option<&str>, use_saved, inset, message: Option<&str>| ServiceView {
            settings: Some(fixture_settings()),
            wifi: Some(fixture_wifi(page, selected, use_saved, inset, message)),
            ..ServiceView::default()
        };
        let pages = [
            ("wifi-list", wifi(Page::List, None, false, 0.0, None)),
            ("wifi-entry-password", wifi(Page::Entry, Some(LONG), false, keyboard, None)),
            ("wifi-entry-error", wifi(Page::Entry, Some(LONG), false, keyboard, Some("Wrong password or the network refused it"))),
            ("wifi-entry-saved", wifi(Page::Entry, Some(HOME), true, 0.0, None)),
            ("wifi-entry-open", wifi(Page::Entry, Some(OPEN), false, 0.0, None)),
            ("wifi-connecting", wifi(Page::Connecting, Some(LONG), false, 0.0, Some("Connecting to the network"))),
            ("wifi-forget", wifi(Page::ForgetConfirm, Some(HOME), true, 0.0, None)),
        ];
        for (name, view) in pages {
            render_route_with_views(&out.join(format!("{name}-{w}x{h}.png")), w, h, Route::Settings, view, None);
        }
        render_route_with_views(
            &out.join(format!("theme-chooser-{w}x{h}.png")),
            w,
            h,
            Route::Settings,
            ServiceView { settings: Some(fixture_settings()), ..ServiceView::default() },
            Some(fixture_theme_view(7)),
        );
        for members in [3usize, 9] {
            render_home_with_open_folder(&out.join(format!("folder-{members}-{w}x{h}.png")), w, h, &apps, members);
        }
        for count in [1usize, 4, 6] {
            let view = ServiceView {
                settings: Some(fixture_settings()),
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
            render_route_with_views(&out.join(format!("shade-{count}-notifications-{w}x{h}.png")), w, h, Route::Shade, view, None);
        }
        eprintln!("rendered {w}x{h}");
    }
}

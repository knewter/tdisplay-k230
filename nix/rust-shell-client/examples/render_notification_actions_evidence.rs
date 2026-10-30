//! Host renders of an app's notification actions in the shade
//! (pending-timers-survive-restarts-and-apps-hear-dismissals 2.3): a row with
//! two action buttons, a row with one, and a plain row, at the landscape
//! panel (1232x568) and the native portrait panel (568x1232), at the 100% and
//! the 200% vision text step.
//!
//! `cargo run --offline --example render_notification_actions_evidence --
//! <out-dir>` writes `shade-actions-<step>-<WxH>.png`, and a `-scrolled`
//! twin when the first row (taller with its buttons) does not fit the list at
//! rest. Host render only: it proves paint and layout, not the board's glass.
//! The notifications are FIXTURE values.
use cairo::{Format, ImageSurface};
use k230_shell_rust::{
    appearance::{AppearanceSnapshot, AppearanceToken},
    evidence_render::fixture_settings,
    render::{RenderParams, RendererCache},
    service_data::{NotificationEvent, NotificationSnapshot, Priority},
    service_ui::{
        notification_action_rect, notification_max_scroll, notification_pitch, shade_layout, ServiceView,
        NOTIFICATION_ACTION_H,
    },
    Route,
};
use std::{collections::BTreeMap, env, fs, path::PathBuf};

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

fn event(id: u64, source: &str, summary: &str, body: &str, actions: &[&str]) -> NotificationEvent {
    NotificationEvent {
        id,
        source: source.into(),
        icon: None,
        summary: summary.into(),
        body: body.into(),
        priority: Priority::Ordinary,
        timestamp: 1_790_000_000,
        error: None,
        dismissible: true,
        action_available: false,
        actions: actions.iter().map(|label| label.to_string()).collect(),
    }
}

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_notification_actions_evidence <out-dir>"));
    fs::create_dir_all(&out).unwrap();
    let events = vec![
        event(1, "Calculator", "Timer done", "Two actions", &["Open", "Snooze"]),
        event(2, "Messages", "New message from Alex", "One action", &["Reply"]),
        event(3, "Mail", "3 new emails", "No action", &[]),
    ];
    for (step_name, step) in [("100", 1.0), ("200", 2.0)] {
        k230_shell_rust::set_layout_text_scale(step);
        for (w, h) in [(1232u32, 568u32), (568, 1232)] {
            let layout = shade_layout(w, h);
            let list_h = layout.list_bottom - layout.list_top;
            let first = notification_action_rect(2, 0, layout.list_w - 48.0);
            let button_bottom = first.1 + NOTIFICATION_ACTION_H;
            let mut scrolls = vec![("", 0.0)];
            if button_bottom > list_h {
                let scroll = (button_bottom + 8.0 - list_h).min(notification_max_scroll(&events, w, h));
                scrolls.push(("-scrolled", scroll));
            }
            eprintln!("{w}x{h} step {step_name}: list {list_h}, first row pitch {}", notification_pitch(&events[0]));
            for (suffix, scroll) in scrolls {
                let mut cache = RendererCache::default();
                cache.set_appearance(Some(theme(step)));
                cache.set_services(ServiceView {
                    settings: Some(fixture_settings()),
                    notifications: Some(NotificationSnapshot { count: 3, events: events.clone(), preview: None }),
                    notification_scroll: scroll,
                    ..ServiceView::default()
                });
                let mut canvas = vec![0u8; (w * h * 4) as usize];
                cache
                    .draw(&mut canvas, RenderParams { width: w, height: h, route: Route::Shade, progress: 1.0, scroll: 0.0 }, &[])
                    .unwrap();
                write_png(&out.join(format!("shade-actions-{step_name}-{w}x{h}{suffix}.png")), &mut canvas, w, h);
            }
        }
    }
    k230_shell_rust::set_layout_text_scale(1.0);
}

fn write_png(path: &std::path::Path, canvas: &mut [u8], w: u32, h: u32) {
    let surface = unsafe {
        ImageSurface::create_for_data_unsafe(canvas.as_mut_ptr(), Format::ARgb32, w as i32, h as i32, (w * 4) as i32)
    }
    .unwrap();
    surface.write_to_png(&mut fs::File::create(path).unwrap()).unwrap();
}

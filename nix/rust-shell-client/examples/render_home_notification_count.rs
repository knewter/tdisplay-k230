//! Host renders of Home's pending-notification count
//! (home-shows-how-many-notifications-wait 1.3a): counts 0, 3 and 100 at the
//! landscape (1232x568) and portrait (568x1232) panel, at the 100% and the
//! largest (200%) vision step. `cargo run --example render_home_notification_count
//! -- <out-dir>`. Host render only: it proves paint and layout, not the glass.
use k230_shell_rust::evidence_render::{render_home_with_count, synthetic_apps};
use std::{env, fs, path::PathBuf};

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("usage: render_home_notification_count <out-dir>"));
    fs::create_dir_all(&out).unwrap();
    let apps = synthetic_apps(30);
    for (step_name, step) in [("100", 1.0), ("200", 2.0)] {
        for (w, h) in [(1232u32, 568u32), (568, 1232)] {
            for count in [0usize, 3, 100] {
                render_home_with_count(&out.join(format!("home-count{count}-{step_name}-{w}x{h}.png")), w, h, &apps, count, step);
            }
        }
    }
}

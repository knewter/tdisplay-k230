//! Host renders of the Help guide (Touch and Keys groups) at the top and
//! scrolled to the end. Production Cairo/Pango; no compositor, board or input.
use k230_shell_rust::{evidence_render, help, service_ui::ServiceView, Route};
use std::{env, fs, path::PathBuf};

fn main() {
    let out = PathBuf::from(env::args().nth(1).expect("render_help_refresh OUT"));
    fs::create_dir_all(&out).unwrap();
    for (w, h, name) in [(1232, 568, "landscape"), (568, 1232, "portrait")] {
        let max = help::layout(w, h, false).max_scroll(h);
        for (scroll, part) in [(0.0, "top"), (max, "end")] {
            let view = ServiceView { help_scroll: scroll, ..ServiceView::default() };
            evidence_render::render_route_with_views(
                &out.join(format!("help-{name}-{w}x{h}-{part}.png")),
                w,
                h,
                Route::Help,
                view,
                None,
            );
        }
    }
}

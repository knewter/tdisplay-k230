//! Host render harness for `openspec/changes/the-shell-adapts-to-output-
//! resolution`'s evidence captures.
//!
//! Renders Home, the wallpaper background, the Drawer and Settings through
//! the exact same production paths (`render::paint_home`,
//! `render::RendererCache::draw_wallpaper`, `render::export_png`) the real
//! Wayland client calls, at each of four surface sizes this change targets:
//! the native panel (568x1232, must stay pixel-identical to before this
//! change -- `tests/responsive_pixel_identity.rs` asserts exactly that
//! against this same 568x1232 render) and three whole-output HDMI sizes
//! that `feat/hdmi-pillarbox` used to letterbox down to a centered
//! 568-aspect column and that `feat/shell-responsive` now fills instead
//! (768x1024, 1080x1920 rotated portrait, 1920x1080 landscape).
//!
//! The actual rendering lives in `k230_shell_rust::evidence_render`, shared
//! with that pixel-identity test so the evidence and the test that guards
//! it can never quietly drift apart. This proves render geometry
//! reflows/fills correctly; it does not open a Wayland connection, so it
//! does not prove the compositor actually hands this client a whole-output
//! configure at these sizes (that is `main.rs`'s `is_whole_output`/
//! `configure_preserves_aspect`, covered by `lib.rs`'s own unit tests) or
//! anything about real touch/board behavior.
//!
//! `cargo run --example render_responsive_evidence -- <out-dir>` writes
//! every PNG into `<out-dir>`.
use k230_shell_rust::{evidence_render, Route};
use std::{env, path::PathBuf};

fn main() {
    let out_dir = PathBuf::from(env::args().nth(1).expect("usage: render_responsive_evidence <out-dir>"));
    std::fs::create_dir_all(&out_dir).unwrap();
    let apps = evidence_render::synthetic_apps(30);
    // (label, width, height) -- 568x1232 first, and its own render must
    // stay pixel-identical across a future re-run of this same harness:
    // that is what "pixel-identical to today" means for a headless,
    // no-Wayland capture like this one.
    let sizes: [(&str, u32, u32); 4] = [
        ("568x1232", 568, 1232),
        ("768x1024", 768, 1024),
        ("1080x1920", 1080, 1920),
        ("1920x1080", 1920, 1080),
    ];
    for (label, width, height) in sizes {
        evidence_render::render_home(&out_dir.join(format!("home-{label}.png")), width, height, &apps);
        evidence_render::render_wallpaper(&out_dir.join(format!("wallpaper-{label}.png")), width, height);
        evidence_render::render_route(&out_dir.join(format!("drawer-{label}.png")), width, height, Route::Drawer, &apps);
        evidence_render::render_route(&out_dir.join(format!("settings-{label}.png")), width, height, Route::Settings, &apps);
        eprintln!("rendered {label}");
    }
}

//! Proves the native 568x1232 panel render is byte-for-byte unchanged by
//! `feat/shell-responsive`: decodes each committed
//! `docs/evidence/shell-responsive/*-568x1232.png` and compares it, pixel
//! for pixel, against a fresh render through
//! `k230_shell_rust::evidence_render` -- the exact module
//! `examples/render_responsive_evidence.rs` used to produce that evidence
//! in the first place, so a future change to that module's own rendering
//! calls (not just to the density-scale/reflow logic this change adds)
//! still gets caught here.
//!
//! This is a host-render check, like the evidence PNGs themselves and
//! `examples/render_widget_evidence.rs` before it -- no Wayland connection,
//! no board, no QEMU. It says the *pixels this client would paint* at
//! 568x1232 have not moved; it does not by itself say the compositor still
//! hands this client that exact configure (see `lib.rs`'s own
//! `configure_preserves_aspect`/`is_whole_output`-adjacent tests for that).
use image::ImageReader;
use k230_shell_rust::{evidence_render, Route};
use std::path::{Path, PathBuf};

/// `docs/evidence/shell-responsive/`, resolved from this crate's own
/// manifest directory so the test works regardless of the caller's current
/// directory (`cargo test` from the repo root, from this crate's own
/// directory, or from a CI runner all resolve `CARGO_MANIFEST_DIR`
/// identically).
fn evidence_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../docs/evidence/shell-responsive")
}

/// A fresh, process/call-unique scratch directory under the system temp
/// dir -- the same manual pattern `home_state.rs`'s own tests already use
/// (`save_then_load_round_trips_exactly` and friends) rather than adding a
/// `tempfile` dev-dependency for one test file.
fn scratch_dir(label: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "k230-responsive-pixel-identity-{label}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
    ));
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

fn decode_rgba(path: &Path) -> Vec<u8> {
    ImageReader::open(path)
        .unwrap_or_else(|e| panic!("open {path:?}: {e}"))
        .decode()
        .unwrap_or_else(|e| panic!("decode {path:?}: {e}"))
        .into_rgba8()
        .into_raw()
}

fn assert_pixel_identical(committed: &Path, fresh: &Path, label: &str) {
    let committed_bytes = decode_rgba(committed);
    let fresh_bytes = decode_rgba(fresh);
    assert_eq!(
        committed_bytes.len(),
        fresh_bytes.len(),
        "{label}: committed and fresh renders are different sizes"
    );
    let mismatches = committed_bytes
        .iter()
        .zip(fresh_bytes.iter())
        .filter(|(a, b)| a != b)
        .count();
    assert_eq!(
        mismatches, 0,
        "{label}: {mismatches} byte(s) differ between the committed 568x1232 evidence \
         ({committed:?}) and a fresh render through the same evidence_render module -- \
         568x1232 must stay pixel-identical. Re-run `cargo run --example \
         render_responsive_evidence -- <dir>` and inspect the {label} output if this \
         change was intentional, then re-commit the updated PNG."
    );
}

#[test]
fn home_568x1232_matches_the_committed_evidence_exactly() {
    let dir = scratch_dir("home");
    let apps = evidence_render::synthetic_apps(30);
    let fresh = dir.join("home-568x1232.png");
    evidence_render::render_home(&fresh, 568, 1232, &apps);
    assert_pixel_identical(&evidence_dir().join("home-568x1232.png"), &fresh, "home");
    std::fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn wallpaper_568x1232_matches_the_committed_evidence_exactly() {
    let dir = scratch_dir("wallpaper");
    let fresh = dir.join("wallpaper-568x1232.png");
    evidence_render::render_wallpaper(&fresh, 568, 1232);
    assert_pixel_identical(&evidence_dir().join("wallpaper-568x1232.png"), &fresh, "wallpaper");
    std::fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn drawer_568x1232_matches_the_committed_evidence_exactly() {
    let dir = scratch_dir("drawer");
    let apps = evidence_render::synthetic_apps(30);
    let fresh = dir.join("drawer-568x1232.png");
    evidence_render::render_route(&fresh, 568, 1232, Route::Drawer, &apps);
    assert_pixel_identical(&evidence_dir().join("drawer-568x1232.png"), &fresh, "drawer");
    std::fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn settings_568x1232_matches_the_committed_evidence_exactly() {
    let dir = scratch_dir("settings");
    let apps = evidence_render::synthetic_apps(30);
    let fresh = dir.join("settings-568x1232.png");
    evidence_render::render_route(&fresh, 568, 1232, Route::Settings, &apps);
    assert_pixel_identical(&evidence_dir().join("settings-568x1232.png"), &fresh, "settings");
    std::fs::remove_dir_all(&dir).unwrap();
}

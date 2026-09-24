//! Host check that the exact Nix default passes the runtime loader and decoder.
use k230_shell_rust::{
    appearance::AppearanceReceiver,
    background_decode::{BackgroundCache, FitMode},
};
use serde_json::Value;
use std::{
    collections::BTreeSet,
    env, fs,
    os::unix::fs::PermissionsExt,
    path::PathBuf,
    process,
    time::{SystemTime, UNIX_EPOCH},
};

fn main() -> Result<(), String> {
    let package = PathBuf::from(env::args().nth(1).ok_or("expected package path")?);
    let expected: Value = serde_json::from_str(include_str!(
        "../../handheld-theme-default/bundled-report.json"
    ))
    .map_err(|error| error.to_string())?;
    let id = expected["generation"]
        .as_str()
        .ok_or("missing bundled generation")?;
    let generation = package.join("generations").join(id);
    let report: Value = serde_json::from_slice(
        &fs::read(generation.join("report.json")).map_err(|error| error.to_string())?,
    )
    .map_err(|error| error.to_string())?;
    if report != expected {
        return Err("installed default report differs from source".into());
    }
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_nanos();
    let root = env::temp_dir().join(format!("k230-default-{}-{nonce}", process::id()));
    let runtime = root.join("runtime");
    fs::create_dir_all(&runtime).map_err(|error| error.to_string())?;
    fs::set_permissions(&runtime, fs::Permissions::from_mode(0o700))
        .map_err(|error| error.to_string())?;
    let state = root.join("state");
    fs::create_dir_all(state.join("generations")).map_err(|error| error.to_string())?;
    let result = (|| {
        let receiver = AppearanceReceiver::bind_with_roots(
            runtime.join("appearance.sock"),
            Some(generation),
            state.clone(),
        )?;
        let snapshot = receiver.active().ok_or("default was not adopted")?;
        let image = snapshot
            .background
            .as_ref()
            .ok_or("default has no still image")?;
        if snapshot.backgrounds.len() != 4 {
            return Err("default background list is incomplete".into());
        }
        let mut cache = BackgroundCache::new();
        let frame = cache.render(image, Some(snapshot.path.as_path()), 568, 1232, FitMode::Crop)?;
        if frame.len() != 568 * 1232 * 4 {
            return Err("invalid decoded wallpaper frame".into());
        }
        let colors: BTreeSet<_> = frame
            .chunks_exact(4)
            .step_by(97)
            .map(|p| p.to_vec())
            .collect();
        if colors.len() < 8 {
            return Err("decoded wallpaper is unexpectedly flat".into());
        }
        let recovery: Value = serde_json::from_str(include_str!(
            "../../handheld-theme-default/default-report.json"
        ))
        .map_err(|error| error.to_string())?;
        let recovery_id = recovery["generation"]
            .as_str()
            .ok_or("missing recovery generation")?;
        let old = AppearanceReceiver::bind_with_roots(
            runtime.join("recovery.sock"),
            Some(package.join("generations").join(recovery_id)),
            state,
        )?;
        if old
            .active()
            .is_none_or(|snapshot| snapshot.background.is_some())
        {
            return Err("palette-only recovery generation is unavailable".into());
        }
        println!(
            "PASS: generation {id}, {} source backgrounds, 568x1232 decoded wallpaper; recovery {recovery_id}",
            snapshot.backgrounds.len()
        );
        Ok(())
    })();
    let _ = fs::remove_dir_all(root);
    result
}

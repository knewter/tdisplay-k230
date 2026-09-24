//! Private, bounded wallpaper telemetry. The file contains no source path,
//! title, network locator or application text. Wayland callbacks are not
//! physical presentation acknowledgements.
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::{
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
    path::Path,
};

#[derive(Serialize)]
pub struct VideoStatus<'a> {
    pub schema: u8,
    pub generation: Option<&'a str>,
    pub background_fingerprint: Option<String>,
    pub decoder_pid: Option<u64>,
    pub state: &'a str,
    pub error_category: Option<&'a str>,
    pub frames_decoded: u64,
    pub frames_submitted: u64,
    pub frame_callbacks: u64,
    pub last_decoded_monotonic_ms: Option<u64>,
    pub last_submitted_monotonic_ms: Option<u64>,
    pub last_callback_monotonic_ms: Option<u64>,
}

pub fn fingerprint(generation: &str, relative: &str) -> String {
    let digest = Sha256::digest(format!("{generation}\n{relative}").as_bytes());
    digest[..12]
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

pub fn monotonic_ms() -> u64 {
    let mut time = libc::timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    if unsafe { libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut time) } != 0 {
        return 0;
    }
    (time.tv_sec as u64)
        .saturating_mul(1000)
        .saturating_add(time.tv_nsec as u64 / 1_000_000)
}

pub fn write_private(runtime: &Path, status: &VideoStatus<'_>) -> Result<(), String> {
    let meta = fs::symlink_metadata(runtime).map_err(|_| "wallpaper runtime unavailable")?;
    if !meta.file_type().is_dir()
        || meta.uid() != unsafe { libc::geteuid() }
        || meta.permissions().mode() & 0o077 != 0
    {
        return Err("wallpaper runtime is not private".into());
    }
    let bytes = serde_json::to_vec(status).map_err(|_| "wallpaper status encoding failed")?;
    if bytes.len() > 4096 {
        return Err("wallpaper status exceeds bound".into());
    }
    let destination = runtime.join("k230-wallpaper-status.json");
    let temporary = runtime.join(format!(
        ".k230-wallpaper-status-{}-{}",
        std::process::id(),
        monotonic_ms()
    ));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .custom_flags(libc::O_NOFOLLOW)
        .open(&temporary)
        .map_err(|_| "wallpaper status temporary unavailable")?;
    let result = (|| -> Result<(), String> {
        file.write_all(&bytes)
            .map_err(|_| "wallpaper status write failed")?;
        file.write_all(b"\n")
            .map_err(|_| "wallpaper status write failed")?;
        file.sync_all()
            .map_err(|_| "wallpaper status sync failed")?;
        fs::rename(&temporary, &destination).map_err(|_| "wallpaper status publish failed")?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn fingerprint_is_stable_and_status_has_no_source_path() {
        assert_eq!(
            fingerprint("a".repeat(24).as_str(), "backgrounds/clip.mp4"),
            "7a9593f1f18a98154a1aefd8"
        );
        let status = VideoStatus {
            schema: 1,
            generation: Some("aaaaaaaaaaaaaaaaaaaaaaaa"),
            background_fingerprint: Some(fingerprint(
                "a".repeat(24).as_str(),
                "backgrounds/clip.mp4",
            )),
            decoder_pid: Some(123),
            state: "playing",
            error_category: None,
            frames_decoded: 2,
            frames_submitted: 1,
            frame_callbacks: 1,
            last_decoded_monotonic_ms: Some(10),
            last_submitted_monotonic_ms: Some(11),
            last_callback_monotonic_ms: Some(12),
        };
        let json = serde_json::to_string(&status).unwrap();
        assert!(!json.contains("backgrounds/") && !json.contains("clip.mp4"));
    }
}

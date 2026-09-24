//! Conservative coverage signal from the compositor. Missing, stale or
//! malformed input means the wallpaper may be visible.
use serde::Deserialize;
use std::{
    fs::OpenOptions,
    io::Read,
    os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt},
    path::Path,
};

#[derive(Deserialize)]
struct Cover {
    schema: u8,
    covered: bool,
    monotonic_ms: u64,
    width: u32,
    height: u32,
}

pub fn certified(path: &Path, width: u32, height: u32, now_ms: u64) -> bool {
    let Ok(file) = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)
    else {
        return false;
    };
    let Ok(meta) = file.metadata() else {
        return false;
    };
    if !meta.is_file()
        || meta.uid() != unsafe { libc::geteuid() }
        || meta.permissions().mode() & 0o077 != 0
        || meta.len() > 256
    {
        return false;
    }
    let mut bytes = Vec::with_capacity(256);
    if file.take(257).read_to_end(&mut bytes).is_err() || bytes.len() > 256 {
        return false;
    }
    let Ok(signal) = serde_json::from_slice::<Cover>(&bytes) else {
        return false;
    };
    signal.schema == 1
        && signal.covered
        && signal.width == width
        && signal.height == height
        && now_ms >= signal.monotonic_ms
        && now_ms - signal.monotonic_ms <= 1500
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_partial_transparent_stale_and_wrong_geometry() {
        let path =
            std::env::temp_dir().join(format!("k230-cover-test-{}.json", std::process::id()));
        std::fs::write(
            &path,
            b"{\"schema\":1,\"covered\":false,\"monotonic_ms\":100,\"width\":568,\"height\":1232}",
        )
        .unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600)).unwrap();
        assert!(!certified(&path, 568, 1232, 100));
        std::fs::write(
            &path,
            b"{\"schema\":1,\"covered\":true,\"monotonic_ms\":100,\"width\":568,\"height\":1232}",
        )
        .unwrap();
        assert!(certified(&path, 568, 1232, 101));
        assert!(!certified(&path, 568, 1232, 1601));
        assert!(!certified(&path, 600, 1232, 101));
        std::fs::remove_file(&path).unwrap();
        std::os::unix::fs::symlink("/dev/zero", &path).unwrap();
        assert!(!certified(&path, 568, 1232, 101));
        std::fs::remove_file(path).unwrap();
    }

    /// A missing coverage file (compositor never published, or was removed)
    /// must not certify coverage, so the wallpaper stays visible rather than
    /// being hidden on unproven ground.
    #[test]
    fn missing_signal_keeps_wallpaper_visible() {
        let path = std::env::temp_dir().join(format!(
            "k230-cover-missing-{}-{}.json",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        assert!(!path.exists());
        assert!(!certified(&path, 568, 1232, 100));
    }

    /// The freshness window is exactly 1500ms: a signal at the boundary is
    /// still certified, one millisecond past it is expired and must fall
    /// back to visible, matching the compositor's own tick cadence.
    #[test]
    fn freshness_boundary_expires_exactly_after_1500ms() {
        let path = std::env::temp_dir().join(format!(
            "k230-cover-boundary-{}-{}.json",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::write(
            &path,
            b"{\"schema\":1,\"covered\":true,\"monotonic_ms\":1000,\"width\":568,\"height\":1232}",
        )
        .unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600)).unwrap();
        assert!(certified(&path, 568, 1232, 2500));
        assert!(!certified(&path, 568, 1232, 2501));
        std::fs::remove_file(path).unwrap();
    }
}

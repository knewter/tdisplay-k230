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

/// Whether the decoder child may run: never under reduced motion, and not
/// while the compositor certifies the wallpaper fully covered. Every start,
/// resume and pause decision in `main.rs` goes through this one predicate.
pub fn should_decode(reduced_motion: bool, covered: bool) -> bool {
    !reduced_motion && !covered
}

/// True when every connected DRM connector under `root` reports DPMS Off.
/// A powered-off output renders nothing, so the cover file goes stale and
/// would read as visible; this is the other reason to stop decoding. Missing
/// or unreadable sysfs means the display may be on. Same rule as the clock
/// screen's `display_on` (nix/term-apps/k230_exhibition.py).
pub fn display_off(root: &Path) -> bool {
    let Ok(entries) = std::fs::read_dir(root) else {
        return false;
    };
    let mut seen = false;
    for entry in entries.flatten() {
        let dir = entry.path();
        let (Ok(status), Ok(dpms)) = (
            std::fs::read_to_string(dir.join("status")),
            std::fs::read_to_string(dir.join("dpms")),
        ) else {
            continue;
        };
        if status.trim() != "connected" {
            continue;
        }
        if dpms.trim().eq_ignore_ascii_case("on") {
            return false;
        }
        seen = true;
    }
    seen
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
    fn decoding_needs_motion_allowed_and_wallpaper_uncovered() {
        assert!(should_decode(false, false));
        assert!(!should_decode(true, false));
        assert!(!should_decode(false, true));
        assert!(!should_decode(true, true));
    }

    #[test]
    fn a_display_counts_as_off_only_when_every_connected_output_is_off() {
        let root = std::env::temp_dir().join(format!("k230-dpms-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        assert!(!display_off(&root), "missing sysfs means maybe on");
        let connector = |name: &str, status: &str, dpms: &str| {
            let dir = root.join(name);
            std::fs::create_dir_all(&dir).unwrap();
            std::fs::write(dir.join("status"), status).unwrap();
            std::fs::write(dir.join("dpms"), dpms).unwrap();
        };
        connector("card0-DSI-1", "connected\n", "On\n");
        assert!(!display_off(&root));
        connector("card0-DSI-1", "connected\n", "Off\n");
        assert!(display_off(&root));
        connector("card0-HDMI-A-1", "disconnected\n", "On\n");
        assert!(display_off(&root), "a disconnected connector does not count");
        connector("card0-HDMI-A-1", "connected\n", "On\n");
        assert!(!display_off(&root));
        std::fs::remove_dir_all(&root).unwrap();
    }

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

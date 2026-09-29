//! Automatic trackpad/direct-touch mode detection.
//!
//! `openspec/changes/plugging-in-hdmi-moves-the-display` makes HDMI a
//! *reboot-based* device-tree swap today (task group 4's no-reboot
//! automation is explicitly speculative and may never land) -- so at any
//! given moment exactly one of the panel's `DSI-1` connector or the
//! bridge's `HDMI-A-1` connector is the one Linux actually drives, and
//! that fact is visible in `/sys/class/drm/*/status` without needing Sway
//! running at all. Reading DRM sysfs directly (rather than `swaymsg -t
//! get_outputs` over the Sway IPC socket) means this daemon can decide its
//! mode before the Sway session exists, doesn't depend on `$SWAYSOCK`, and
//! costs one directory listing plus a handful of tiny file reads.
//!
//! Polling this (rather than reacting to a udev/DRM hotplug event) is a
//! deliberate simplification for the prototype: it is cheap enough (a few
//! sysfs reads a second) to be correct today (boot-time-fixed mode) and
//! ready if `plugging-in-hdmi-moves-the-display` group 4's live switching
//! ever lands, without this crate needing to know which case it's in.

use std::fs;
use std::path::Path;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// The panel is the active output: leave the touchscreen alone so
    /// Sway's `map_to_output` absolute-touch mapping (owned by the
    /// coordinator's parallel change) keeps working.
    DirectTouch,
    /// An HDMI connector is `connected`: the panel is dark, so grab the
    /// touchscreen and re-emit it as a virtual touchpad.
    Trackpad,
}

/// Connector *directory* name fragments, not full names -- DRM names a
/// connector `<card>-<connector-type>-<index>`, e.g. `card0-HDMI-A-1` or
/// `card1-DSI-1`, and this project's own evidence
/// (`docs/evidence/plugging-in-hdmi-moves-the-display/probe/`) confirms
/// both spellings show up verbatim from this kernel's `canaan` DRM driver.
const HDMI_MARKER: &str = "HDMI";
const PANEL_MARKERS: [&str; 2] = ["DSI", "eDP"];

fn connector_status(dir: &Path) -> Option<String> {
    fs::read_to_string(dir.join("status")).ok().map(|s| s.trim().to_string())
}

/// Decides the mode from a DRM sysfs root (normally `/sys/class/drm`, but
/// parameterized so host tests can point it at a fixture directory without
/// touching real hardware). Any connector whose directory name contains
/// `HDMI_MARKER` and whose `status` file reads `connected` selects
/// `Trackpad`; everything else -- no such connector, not found, unreadable,
/// any other status string -- defaults to `DirectTouch`, the safe fallback
/// that never touches the touchscreen if the board's state can't be read.
pub fn detect_mode(drm_root: &Path) -> Mode {
    let entries = match fs::read_dir(drm_root) {
        Ok(e) => e,
        Err(_) => return Mode::DirectTouch,
    };
    for entry in entries.flatten() {
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if name.contains(HDMI_MARKER) && connector_status(&entry.path()).as_deref() == Some("connected") {
            return Mode::Trackpad;
        }
    }
    Mode::DirectTouch
}

/// True if `drm_root` has a panel connector (`DSI`/`eDP`) reporting
/// `connected`. Not used to choose the mode (an HDMI `connected` status
/// always wins per `detect_mode`, matching the reboot-swap model where
/// only one of the two is ever real at a time) -- exposed for diagnostics
/// and for a host test asserting the panel-only case resolves to
/// `DirectTouch`.
pub fn panel_connected(drm_root: &Path) -> bool {
    let entries = match fs::read_dir(drm_root) {
        Ok(e) => e,
        Err(_) => return false,
    };
    for entry in entries.flatten() {
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if PANEL_MARKERS.iter().any(|m| name.contains(m))
            && connector_status(&entry.path()).as_deref() == Some("connected")
        {
            return true;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::sync::atomic::{AtomicU32, Ordering};

    /// A minimal self-cleaning temp directory, hand-rolled rather than
    /// pulling in a crate: this workspace pins `libc = "=0.2.175"`
    /// (matching `nix/rust-shell-client/Cargo.toml`'s own exact pin, for
    /// the same untouched-cross-build-proof reason), and every current
    /// `tempfile` release now requires a newer `libc` via `rustix`, so it
    /// cannot resolve against that pin. The fixture only needs "an empty
    /// directory unique to this test, removed afterwards" -- a handful of
    /// lines under `std::env::temp_dir()` covers that without a new
    /// dependency.
    struct TestDir(std::path::PathBuf);
    impl TestDir {
        fn new() -> Self {
            static COUNTER: AtomicU32 = AtomicU32::new(0);
            let n = COUNTER.fetch_add(1, Ordering::Relaxed);
            let path = std::env::temp_dir()
                .join(format!("k230-drm-fixture-{}-{}-{}", std::process::id(), n, std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
            fs::create_dir_all(&path).unwrap();
            TestDir(path)
        }
        fn path(&self) -> &std::path::Path {
            &self.0
        }
    }
    impl Drop for TestDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn fixture(connectors: &[(&str, &str)]) -> TestDir {
        let dir = TestDir::new();
        for (name, status) in connectors {
            let cdir = dir.path().join(name);
            fs::create_dir(&cdir).unwrap();
            fs::write(cdir.join("status"), format!("{status}\n")).unwrap();
        }
        dir
    }

    #[test]
    fn panel_only_boot_is_direct_touch() {
        let dir = fixture(&[("card1-DSI-1", "connected"), ("card1-HDMI-A-1", "disconnected")]);
        assert_eq!(detect_mode(dir.path()), Mode::DirectTouch);
        assert!(panel_connected(dir.path()));
    }

    #[test]
    fn hdmi_connected_boot_is_trackpad() {
        // Matches the reboot-swap model: once the HDMI DTB is booted the
        // panel connector need not even exist, but this must not matter.
        let dir = fixture(&[("card0-HDMI-A-1", "connected")]);
        assert_eq!(detect_mode(dir.path()), Mode::Trackpad);
    }

    #[test]
    fn hdmi_present_but_unplugged_stays_direct_touch() {
        let dir = fixture(&[("card1-DSI-1", "connected"), ("card1-HDMI-A-1", "disconnected")]);
        assert_eq!(detect_mode(dir.path()), Mode::DirectTouch);
    }

    #[test]
    fn missing_drm_root_defaults_to_direct_touch() {
        assert_eq!(detect_mode(Path::new("/nonexistent/k230-drm-fixture-missing")), Mode::DirectTouch);
    }

    #[test]
    fn no_connectors_at_all_defaults_to_direct_touch() {
        let dir = fixture(&[]);
        assert_eq!(detect_mode(dir.path()), Mode::DirectTouch);
    }
}

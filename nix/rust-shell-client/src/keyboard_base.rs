//! The keyboard base's two shell-visible devices: the fuel gauge (shown in
//! the shade, read through `home_widgets::battery`) and the key backlight LED
//! (a Settings preference). Both are hidden when the device is absent.
//!
//! The key backlight preference is "light the keys while typing". It is not
//! a brightness write: `nix/keyboard-base/keyboard_based.py` owns the LED and
//! re-reads this file, keeping the LED off while the preference is off.
//! The file lives in `/var/lib/k230-keyboard-base`, a shell-owned directory
//! created by tmpfiles in `nix/hardware.nix`. That is system state that
//! survives a reboot and is not in a home directory (device-settings spec).
//! It is a sibling of `/var/lib/k230`, not a child: that directory is
//! root-only 0700 (it guards the Wi-Fi credential), so the unprivileged
//! `shell` user could not reach a child of it, and opening its search bit
//! would weaken the documented credential layout. A missing file means the
//! default: on.
use crate::home_widgets::battery::{self, BatteryState};
use std::path::{Path, PathBuf};

pub const LED_ROOT: &str = "/sys/class/leds";
pub const BACKLIGHT_LED: &str = "k230::kbd_backlight";
pub const PREFERENCE_DIR: &str = "/var/lib/k230-keyboard-base";
pub const PREFERENCE_FILE: &str = "key-backlight";

pub fn preference_path() -> PathBuf {
    Path::new(PREFERENCE_DIR).join(PREFERENCE_FILE)
}

/// True when the key backlight LED exists under `led_root` (ordinarily
/// [`LED_ROOT`], injectable so tests never touch the host's sysfs).
pub fn backlight_present(led_root: &Path) -> bool {
    led_root.join(BACKLIGHT_LED).join("brightness").exists()
}

/// The stored preference; anything but an explicit off (including a missing
/// or unreadable file) is on, matching the service's default.
pub fn read_preference(path: &Path) -> bool {
    !std::fs::read_to_string(path).is_ok_and(|text| matches!(text.trim(), "off" | "0"))
}

pub fn write_preference(path: &Path, on: bool) -> std::io::Result<()> {
    std::fs::write(path, if on { "on\n" } else { "off\n" })
}

/// `Some(preference)` when the base's backlight exists, else `None` and
/// Settings shows no control.
pub fn backlight_state(led_root: &Path, preference: &Path) -> Option<bool> {
    backlight_present(led_root).then(|| read_preference(preference))
}

/// Everything the shade and Settings show about the base, from injectable
/// sysfs roots: the battery (`Absent` hides the shade's battery text) and the
/// key backlight preference (`None` hides Settings' row).
pub fn read_view_state(
    power_supply_root: &Path,
    led_root: &Path,
    preference: &Path,
) -> (BatteryState, Option<bool>) {
    (
        battery::read_state(power_supply_root),
        backlight_state(led_root, preference),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tempdir(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "k230-kbd-{tag}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn fake_led(root: &Path) {
        let led = root.join(BACKLIGHT_LED);
        std::fs::create_dir_all(&led).unwrap();
        std::fs::write(led.join("brightness"), "0\n").unwrap();
    }

    #[test]
    fn no_led_tree_means_no_backlight_control() {
        let dir = tempdir("absent");
        assert!(!backlight_present(&dir));
        assert!(!backlight_present(&dir.join("missing")));
        assert_eq!(backlight_state(&dir, &dir.join("pref")), None);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn another_led_does_not_count_as_the_key_backlight() {
        let dir = tempdir("other-led");
        std::fs::create_dir_all(dir.join("k230:green:capslock")).unwrap();
        std::fs::write(dir.join("k230:green:capslock/brightness"), "0\n").unwrap();
        assert!(!backlight_present(&dir));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn the_preference_defaults_to_on_and_round_trips() {
        let dir = tempdir("pref");
        fake_led(&dir);
        let pref = dir.join(PREFERENCE_FILE);
        assert_eq!(backlight_state(&dir, &pref), Some(true));
        write_preference(&pref, false).unwrap();
        assert_eq!(std::fs::read_to_string(&pref).unwrap(), "off\n");
        assert_eq!(backlight_state(&dir, &pref), Some(false));
        write_preference(&pref, true).unwrap();
        assert_eq!(backlight_state(&dir, &pref), Some(true));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn view_state_follows_the_fake_trees() {
        let dir = tempdir("view");
        let (power, leds) = (dir.join("power_supply"), dir.join("leds"));
        let pref = dir.join(PREFERENCE_FILE);
        std::fs::create_dir_all(&power).unwrap();
        assert_eq!(read_view_state(&power, &leds, &pref), (BatteryState::Absent, None));
        let gauge = power.join("bq27220-0");
        std::fs::create_dir_all(&gauge).unwrap();
        std::fs::write(gauge.join("type"), "Battery\n").unwrap();
        std::fs::write(gauge.join("capacity"), "64\n").unwrap();
        std::fs::write(gauge.join("status"), "Discharging\n").unwrap();
        fake_led(&leds);
        write_preference(&pref, false).unwrap();
        assert_eq!(
            read_view_state(&power, &leds, &pref),
            (BatteryState::Present { percent: 64, status: "Discharging".into() }, Some(false))
        );
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn writing_into_a_missing_directory_fails_without_panicking() {
        let dir = tempdir("nodir");
        assert!(write_preference(&dir.join("gone").join(PREFERENCE_FILE), false).is_err());
        std::fs::remove_dir_all(&dir).unwrap();
    }
}

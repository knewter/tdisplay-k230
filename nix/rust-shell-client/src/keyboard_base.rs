//! The keyboard base's two shell-visible devices: the fuel gauge (shown in
//! the shade, read through `home_widgets::battery`) and the key backlight LED
//! (a Settings preference). Both are hidden when the device is absent.
//!
//! The key backlight preference is how brightly to light the keys while
//! typing: Off, Low, Medium or High. It is not a brightness write:
//! `nix/keyboard-base/keyboard_based.py` owns the LED, re-reads this file,
//! and scales the PWM LED's `max_brightness` by the level.
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

/// Settings' Key backlight level. A tap steps High, Medium, Low, Off and
/// round to High again.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum KeyBacklight {
    Off,
    Low,
    Medium,
    High,
}

impl KeyBacklight {
    /// Anything unrecognised, including the pre-PWM "on", is High.
    pub fn parse(text: &str) -> Self {
        match text.trim() {
            "off" | "0" => Self::Off,
            "low" => Self::Low,
            "medium" => Self::Medium,
            _ => Self::High,
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Off => "off",
            Self::Low => "low",
            Self::Medium => "medium",
            Self::High => "high",
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Off => "Off",
            Self::Low => "Low",
            Self::Medium => "Medium",
            Self::High => "High",
        }
    }

    pub fn next(self) -> Self {
        match self {
            Self::High => Self::Medium,
            Self::Medium => Self::Low,
            Self::Low => Self::Off,
            Self::Off => Self::High,
        }
    }
}

pub fn preference_path() -> PathBuf {
    Path::new(PREFERENCE_DIR).join(PREFERENCE_FILE)
}

/// True when the key backlight LED exists under `led_root` (ordinarily
/// [`LED_ROOT`], injectable so tests never touch the host's sysfs).
pub fn backlight_present(led_root: &Path) -> bool {
    led_root.join(BACKLIGHT_LED).join("brightness").exists()
}

/// The stored level; a missing or unreadable file is High, matching the
/// service's default.
pub fn read_preference(path: &Path) -> KeyBacklight {
    std::fs::read_to_string(path).map_or(KeyBacklight::High, |text| KeyBacklight::parse(&text))
}

pub fn write_preference(path: &Path, level: KeyBacklight) -> std::io::Result<()> {
    std::fs::write(path, format!("{}\n", level.as_str()))
}

/// `Some(preference)` when the base's backlight exists, else `None` and
/// Settings shows no control.
pub fn backlight_state(led_root: &Path, preference: &Path) -> Option<KeyBacklight> {
    backlight_present(led_root).then(|| read_preference(preference))
}

/// Everything the shade and Settings show about the base, from injectable
/// sysfs roots: the battery (`Absent` hides the shade's battery text) and the
/// key backlight preference (`None` hides Settings' row).
pub fn read_view_state(
    power_supply_root: &Path,
    led_root: &Path,
    preference: &Path,
) -> (BatteryState, Option<KeyBacklight>) {
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
        assert_eq!(backlight_state(&dir, &pref), Some(KeyBacklight::High));
        write_preference(&pref, KeyBacklight::Off).unwrap();
        assert_eq!(std::fs::read_to_string(&pref).unwrap(), "off\n");
        assert_eq!(backlight_state(&dir, &pref), Some(KeyBacklight::Off));
        for level in [KeyBacklight::Low, KeyBacklight::Medium, KeyBacklight::High] {
            write_preference(&pref, level).unwrap();
            assert_eq!(backlight_state(&dir, &pref), Some(level));
        }
        // The pre-PWM file still reads as the brightest level.
        std::fs::write(&pref, "on\n").unwrap();
        assert_eq!(backlight_state(&dir, &pref), Some(KeyBacklight::High));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn a_tap_steps_down_through_the_levels_and_wraps_to_high() {
        let mut level = KeyBacklight::High;
        let mut seen = Vec::new();
        for _ in 0..4 {
            level = level.next();
            seen.push(level);
        }
        assert_eq!(
            seen,
            [KeyBacklight::Medium, KeyBacklight::Low, KeyBacklight::Off, KeyBacklight::High]
        );
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
        write_preference(&pref, KeyBacklight::Off).unwrap();
        assert_eq!(
            read_view_state(&power, &leds, &pref),
            (BatteryState::Present { percent: 64, status: "Discharging".into() }, Some(KeyBacklight::Off))
        );
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn writing_into_a_missing_directory_fails_without_panicking() {
        let dir = tempdir("nodir");
        assert!(write_preference(&dir.join("gone").join(PREFERENCE_FILE), KeyBacklight::Off).is_err());
        std::fs::remove_dir_all(&dir).unwrap();
    }
}

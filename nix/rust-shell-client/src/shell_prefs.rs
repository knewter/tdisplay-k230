//! Shell-owned preferences kept in `/var/lib/k230-shell-prefs`, a
//! shell-user directory created by `systemd.tmpfiles.rules` in
//! `nix/shell.nix`. Do Not Disturb is the first: one word, `on` or `off`.
//! "Idle on charger" is the second: `clock` or `sleep`, read by the idle
//! step (`nix/idle-dimmer/idle_dimmer.py`), which keeps its own copy of the
//! parse rule.
//!
//! The directory is new rather than `/var/lib/k230-keyboard-base`, which is
//! named for the base. A missing, unreadable or unrecognised file means off,
//! so a bad file can only let banners through.
use crate::service_data::NotificationPreview;
use std::path::{Path, PathBuf};

pub const PREFERENCE_DIR: &str = "/var/lib/k230-shell-prefs";
pub const DO_NOT_DISTURB_FILE: &str = "do-not-disturb";

pub fn do_not_disturb_path() -> PathBuf {
    Path::new(PREFERENCE_DIR).join(DO_NOT_DISTURB_FILE)
}

pub const IDLE_ON_CHARGER_FILE: &str = "idle-on-charger";

/// What an idle display does while the charger is connected.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum ChargerIdle {
    /// The exhibition clock instead of blanking (the default).
    #[default]
    Clock,
    /// Dim and blank, exactly as on battery.
    Sleep,
}

impl ChargerIdle {
    pub fn word(self) -> &'static str {
        match self {
            ChargerIdle::Clock => "clock",
            ChargerIdle::Sleep => "sleep",
        }
    }

    /// The Settings row's value text.
    pub fn label(self) -> &'static str {
        match self {
            ChargerIdle::Clock => "Clock",
            ChargerIdle::Sleep => "Sleep",
        }
    }

    pub fn toggled(self) -> Self {
        match self {
            ChargerIdle::Clock => ChargerIdle::Sleep,
            ChargerIdle::Sleep => ChargerIdle::Clock,
        }
    }
}

pub fn idle_on_charger_path() -> PathBuf {
    Path::new(PREFERENCE_DIR).join(IDLE_ON_CHARGER_FILE)
}

/// Only the exact word `sleep` (whitespace aside) selects sleep. Anything
/// else, including a missing file, is the default: clock.
pub fn parse_idle_on_charger(text: &str) -> ChargerIdle {
    if text.trim() == "sleep" { ChargerIdle::Sleep } else { ChargerIdle::Clock }
}

pub fn read_idle_on_charger(path: &Path) -> ChargerIdle {
    std::fs::read_to_string(path).map_or(ChargerIdle::Clock, |text| parse_idle_on_charger(&text))
}

pub fn write_idle_on_charger(path: &Path, choice: ChargerIdle) -> std::io::Result<()> {
    std::fs::write(path, format!("{}\n", choice.word()))
}

/// Only the exact word `on` (whitespace aside) turns the mode on.
pub fn parse_do_not_disturb(text: &str) -> bool {
    text.trim() == "on"
}

pub fn read_do_not_disturb(path: &Path) -> bool {
    std::fs::read_to_string(path).is_ok_and(|text| parse_do_not_disturb(&text))
}

pub fn write_do_not_disturb(path: &Path, on: bool) -> std::io::Result<()> {
    std::fs::write(path, if on { "on\n" } else { "off\n" })
}

/// The banner a quiet shell may show. With the mode off every preview
/// passes; while quiet only one the broker marked as breaking through does.
/// History, the count and the shade's list never go through this.
pub fn banner_allowed(
    quiet: bool,
    preview: Option<NotificationPreview>,
) -> Option<NotificationPreview> {
    preview.filter(|preview| !quiet || preview.breakthrough)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::service_data::Priority;

    fn tempdir(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "k230-prefs-{tag}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn preview(id: u64, breakthrough: bool) -> NotificationPreview {
        NotificationPreview {
            id,
            source: "Notification".into(),
            icon: None,
            summary: "New notification".into(),
            priority: Priority::Ordinary,
            ongoing: false,
            breakthrough,
        }
    }

    #[test]
    fn a_missing_file_means_off() {
        let dir = tempdir("missing");
        assert!(!read_do_not_disturb(&dir.join(DO_NOT_DISTURB_FILE)));
        assert!(!read_do_not_disturb(&dir.join("gone").join(DO_NOT_DISTURB_FILE)));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn the_choice_round_trips_as_one_word() {
        let dir = tempdir("round");
        let path = dir.join(DO_NOT_DISTURB_FILE);
        write_do_not_disturb(&path, true).unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "on\n");
        assert!(read_do_not_disturb(&path));
        write_do_not_disturb(&path, false).unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "off\n");
        assert!(!read_do_not_disturb(&path));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn a_corrupt_or_unreadable_file_means_off() {
        let dir = tempdir("corrupt");
        let path = dir.join(DO_NOT_DISTURB_FILE);
        for junk in ["", "ON", "onn", "1", "true", "on off"] {
            std::fs::write(&path, junk).unwrap();
            assert!(!read_do_not_disturb(&path), "{junk:?}");
        }
        std::fs::write(&path, [0xff_u8, 0xfe, 0x00]).unwrap();
        assert!(!read_do_not_disturb(&path), "invalid UTF-8");
        std::fs::remove_file(&path).unwrap();
        std::fs::create_dir(&path).unwrap();
        assert!(!read_do_not_disturb(&path), "a directory is unreadable");
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn writing_into_a_missing_directory_fails_without_panicking() {
        let dir = tempdir("nodir");
        assert!(write_do_not_disturb(&dir.join("gone").join(DO_NOT_DISTURB_FILE), true).is_err());
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn idle_on_charger_defaults_to_clock_and_only_sleep_disables_it() {
        let dir = tempdir("charger-idle");
        let path = dir.join(IDLE_ON_CHARGER_FILE);
        assert_eq!(read_idle_on_charger(&path), ChargerIdle::Clock, "missing");
        assert_eq!(ChargerIdle::default(), ChargerIdle::Clock);
        for (junk, want) in [
            ("sleep\n", ChargerIdle::Sleep),
            (" sleep ", ChargerIdle::Sleep),
            ("clock\n", ChargerIdle::Clock),
            ("", ChargerIdle::Clock),
            ("SLEEP", ChargerIdle::Clock),
            ("sleeping", ChargerIdle::Clock),
            ("sleep clock", ChargerIdle::Clock),
        ] {
            std::fs::write(&path, junk).unwrap();
            assert_eq!(read_idle_on_charger(&path), want, "{junk:?}");
        }
        std::fs::write(&path, [0xff_u8, 0xfe]).unwrap();
        assert_eq!(read_idle_on_charger(&path), ChargerIdle::Clock, "invalid UTF-8");
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn idle_on_charger_round_trips_as_one_word_and_toggles() {
        let dir = tempdir("charger-idle-round");
        let path = dir.join(IDLE_ON_CHARGER_FILE);
        write_idle_on_charger(&path, ChargerIdle::Sleep).unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "sleep\n");
        assert_eq!(read_idle_on_charger(&path), ChargerIdle::Sleep);
        write_idle_on_charger(&path, ChargerIdle::Clock).unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "clock\n");
        assert_eq!(ChargerIdle::Clock.toggled(), ChargerIdle::Sleep);
        assert_eq!(ChargerIdle::Sleep.toggled(), ChargerIdle::Clock);
        assert_eq!((ChargerIdle::Clock.label(), ChargerIdle::Sleep.label()), ("Clock", "Sleep"));
        assert!(write_idle_on_charger(&dir.join("gone").join(IDLE_ON_CHARGER_FILE), ChargerIdle::Sleep).is_err());
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn quiet_mode_drops_every_banner_that_does_not_break_through() {
        let ordinary = preview(1, false);
        let alert = preview(2, true);
        assert_eq!(banner_allowed(false, Some(ordinary.clone())), Some(ordinary.clone()));
        assert_eq!(banner_allowed(false, Some(alert.clone())), Some(alert.clone()));
        assert_eq!(banner_allowed(true, Some(ordinary)), None);
        assert_eq!(banner_allowed(true, Some(alert.clone())), Some(alert));
        assert_eq!(banner_allowed(true, None), None);
    }
}

//! Shell-owned preferences kept in `/var/lib/k230-shell-prefs`, a
//! shell-user directory created by `systemd.tmpfiles.rules` in
//! `nix/shell.nix`. Do Not Disturb is the first: one word, `on` or `off`.
//! "Idle on charger" is the second: `clock` or `sleep`, read by the idle
//! step (`nix/idle-dimmer/idle_dimmer.py`), which keeps its own copy of the
//! parse rule. "Idle timeout" (`idle-timeout`: `off`, `1m`, `5m`) is read by
//! `k230-swayidle` at its start, and "Clock brightness" (`dim`, `half`,
//! `full`), "Clock effects" (`5m`, `15m`, `off`) and "Clock limit" (`2h`,
//! `8h`, `none`) by the idle step and the clock screen
//! (`nix/term-apps/k230_exhibition.py`), each with its own copy of the rule.
//! "Clock format" (`clock-format`: `24-hour` or `12-hour`) is read by the
//! shell's clocks and by the terminal apps' clocks (`k230_term_apps.py`,
//! `k230_exhibition.py`), again each with its own copy of the rule.
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

/// A Settings row that cycles through a few words stored in one file. Only
/// an exact word (whitespace aside) selects a choice; a missing, unreadable
/// or unrecognised file is the default, which is today's behaviour.
macro_rules! cycling_pref {
    ($(#[$meta:meta])* $name:ident, $file:expr, $path:ident, $read:ident, $write:ident,
     $default:ident, [$($variant:ident => ($word:expr, $label:expr)),+ $(,)?]) => {
        $(#[$meta])*
        #[derive(Clone, Copy, Debug, PartialEq, Eq)]
        pub enum $name {
            $($variant,)+
        }

        impl Default for $name {
            fn default() -> Self {
                $name::$default
            }
        }

        impl $name {
            pub const ALL: &'static [$name] = &[$($name::$variant),+];

            pub fn word(self) -> &'static str {
                match self { $($name::$variant => $word,)+ }
            }

            /// The Settings row's value text.
            pub fn label(self) -> &'static str {
                match self { $($name::$variant => $label,)+ }
            }

            /// The next choice, wrapping after the last.
            pub fn next(self) -> Self {
                let at = Self::ALL.iter().position(|choice| *choice == self).unwrap_or(0);
                Self::ALL[(at + 1) % Self::ALL.len()]
            }

            pub fn parse(text: &str) -> Self {
                let text = text.trim();
                Self::ALL.iter().copied().find(|choice| choice.word() == text).unwrap_or_default()
            }
        }

        pub fn $path() -> PathBuf {
            Path::new(PREFERENCE_DIR).join($file)
        }

        pub fn $read(path: &Path) -> $name {
            std::fs::read_to_string(path).map_or($name::default(), |text| $name::parse(&text))
        }

        pub fn $write(path: &Path, choice: $name) -> std::io::Result<()> {
            std::fs::write(path, format!("{}\n", choice.word()))
        }
    };
}

cycling_pref!(
    /// When the idle display dims and turns off (`k230-swayidle`): 30 s / 60 s
    /// at one minute, 150 s / 300 s at five, or never.
    IdleTimeout, "idle-timeout", idle_timeout_path, read_idle_timeout, write_idle_timeout,
    OneMinute, [Off => ("off", "Off"), OneMinute => ("1m", "1 min"), FiveMinutes => ("5m", "5 min")]
);

cycling_pref!(
    /// How bright the clock screen runs, as a share of the saved brightness.
    ClockBrightness, "clock-brightness", clock_brightness_path, read_clock_brightness,
    write_clock_brightness, Dim, [Dim => ("dim", "Dim"), Half => ("half", "Half"), Full => ("full", "Full")]
);

cycling_pref!(
    /// How often the clock screen plays a text effect.
    ClockEffects, "clock-effects", clock_effects_path, read_clock_effects, write_clock_effects,
    FiveMinutes, [FiveMinutes => ("5m", "5 min"), FifteenMinutes => ("15m", "15 min"), Off => ("off", "Off")]
);

cycling_pref!(
    /// How long the clock screen stays up before it closes itself.
    ClockLimit, "clock-limit", clock_limit_path, read_clock_limit, write_clock_limit,
    TwoHours, [TwoHours => ("2h", "2 h"), EightHours => ("8h", "8 h"), Unlimited => ("none", "None")]
);

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

pub const CLOCK_FORMAT_FILE: &str = "clock-format";

pub fn clock_format_path() -> PathBuf {
    Path::new(PREFERENCE_DIR).join(CLOCK_FORMAT_FILE)
}

/// Only the exact word `12-hour` (whitespace aside) selects a 12-hour clock;
/// anything else, or no file, keeps the 24-hour default.
pub fn parse_twelve_hour(text: &str) -> bool {
    text.trim() == "12-hour"
}

pub fn read_twelve_hour(path: &Path) -> bool {
    std::fs::read_to_string(path).is_ok_and(|text| parse_twelve_hour(&text))
}

pub fn write_twelve_hour(path: &Path, twelve: bool) -> std::io::Result<()> {
    std::fs::write(path, if twelve { "12-hour\n" } else { "24-hour\n" })
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
    fn the_clock_format_defaults_to_24_hour_and_round_trips() {
        let dir = tempdir("clock");
        let path = dir.join(CLOCK_FORMAT_FILE);
        assert!(!read_twelve_hour(&path));
        write_twelve_hour(&path, true).unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), "12-hour\n");
        assert!(read_twelve_hour(&path));
        write_twelve_hour(&path, false).unwrap();
        assert!(!read_twelve_hour(&path));
        for junk in ["", "12", "12 hour", "12-HOUR", "am/pm"] {
            std::fs::write(&path, junk).unwrap();
            assert!(!read_twelve_hour(&path), "{junk:?}");
        }
        std::fs::remove_dir_all(&dir).unwrap();
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
    fn idle_timeout_defaults_to_one_minute_and_reads_only_exact_words() {
        let dir = tempdir("idle-timeout");
        let path = dir.join("idle-timeout");
        assert_eq!(read_idle_timeout(&path), IdleTimeout::OneMinute, "missing");
        assert_eq!(IdleTimeout::default(), IdleTimeout::OneMinute);
        for (junk, want) in [
            ("off\n", IdleTimeout::Off),
            ("1m\n", IdleTimeout::OneMinute),
            (" 5m ", IdleTimeout::FiveMinutes),
            ("", IdleTimeout::OneMinute),
            ("OFF", IdleTimeout::OneMinute),
            ("5", IdleTimeout::OneMinute),
            ("5m 1m", IdleTimeout::OneMinute),
        ] {
            std::fs::write(&path, junk).unwrap();
            assert_eq!(read_idle_timeout(&path), want, "{junk:?}");
        }
        std::fs::write(&path, [0xff_u8, 0xfe]).unwrap();
        assert_eq!(read_idle_timeout(&path), IdleTimeout::OneMinute, "invalid UTF-8");
        assert_eq!(idle_timeout_path(), Path::new(PREFERENCE_DIR).join("idle-timeout"));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn clock_prefs_default_to_todays_behaviour_and_cycle_through_their_words() {
        assert_eq!(ClockBrightness::default(), ClockBrightness::Dim);
        assert_eq!(ClockEffects::default(), ClockEffects::FiveMinutes);
        assert_eq!(ClockLimit::default(), ClockLimit::TwoHours);
        fn cycle<T: Copy>(start: T, next: fn(T) -> T, show: fn(T) -> String) -> Vec<String> {
            let mut seen = Vec::new();
            let mut at = start;
            for _ in 0..3 {
                at = next(at);
                seen.push(show(at));
            }
            seen
        }
        assert_eq!(
            cycle(ClockBrightness::Dim, ClockBrightness::next, |c| format!("{}/{}", c.word(), c.label())),
            ["half/Half", "full/Full", "dim/Dim"]
        );
        assert_eq!(
            cycle(ClockEffects::FiveMinutes, ClockEffects::next, |c| format!("{}/{}", c.word(), c.label())),
            ["15m/15 min", "off/Off", "5m/5 min"]
        );
        assert_eq!(
            cycle(ClockLimit::TwoHours, ClockLimit::next, |c| format!("{}/{}", c.word(), c.label())),
            ["8h/8 h", "none/None", "2h/2 h"]
        );
        assert_eq!(
            cycle(IdleTimeout::Off, IdleTimeout::next, |c| format!("{}/{}", c.word(), c.label())),
            ["1m/1 min", "5m/5 min", "off/Off"]
        );
        for junk in ["", "DIM", "bright", "half full"] {
            assert_eq!(ClockBrightness::parse(junk), ClockBrightness::Dim, "{junk:?}");
        }
        for junk in ["", "1m", "OFF", "15", "off now"] {
            assert_eq!(ClockEffects::parse(junk), ClockEffects::FiveMinutes, "{junk:?}");
        }
        assert_eq!(ClockLimit::parse("NONE"), ClockLimit::TwoHours);
        assert_eq!(ClockLimit::parse("off"), ClockLimit::TwoHours);
        assert_eq!(ClockLimit::parse(" none\n"), ClockLimit::Unlimited);
    }

    #[test]
    fn clock_prefs_write_one_word_to_their_own_files() {
        let dir = tempdir("clock-prefs");
        let write = |name: &str, f: &dyn Fn(&Path) -> std::io::Result<()>| {
            let path = dir.join(name);
            f(&path).unwrap();
            std::fs::read_to_string(path).unwrap()
        };
        assert_eq!(write("b", &|p| write_clock_brightness(p, ClockBrightness::Half)), "half\n");
        assert_eq!(write("e", &|p| write_clock_effects(p, ClockEffects::Off)), "off\n");
        assert_eq!(write("l", &|p| write_clock_limit(p, ClockLimit::Unlimited)), "none\n");
        assert_eq!(write("t", &|p| write_idle_timeout(p, IdleTimeout::FiveMinutes)), "5m\n");
        assert_eq!(read_clock_brightness(&dir.join("b")), ClockBrightness::Half);
        assert_eq!(read_clock_effects(&dir.join("e")), ClockEffects::Off);
        assert_eq!(read_clock_limit(&dir.join("l")), ClockLimit::Unlimited);
        assert_eq!(read_idle_timeout(&dir.join("t")), IdleTimeout::FiveMinutes);
        assert_eq!(read_clock_limit(&dir.join("missing")), ClockLimit::TwoHours);
        for (path, name) in [
            (clock_brightness_path(), "clock-brightness"),
            (clock_effects_path(), "clock-effects"),
            (clock_limit_path(), "clock-limit"),
        ] {
            assert_eq!(path, Path::new(PREFERENCE_DIR).join(name));
        }
        assert!(write_clock_limit(&dir.join("gone").join("x"), ClockLimit::TwoHours).is_err());
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

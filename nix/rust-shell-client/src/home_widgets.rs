//! Content for Home's shell-drawn widgets (task: "Widgets, drawn by the
//! shell itself, cheap and themed"). Each widget's *placement* on the grid
//! is `home_state::HomeItem::Widget`; this module is only the live content
//! each one shows, kept separate so it is host-testable with no touch
//! surface, panel, or real hardware involved:
//!
//! - [`battery`]: reads `/sys/class/power_supply/*`, which this board
//!   currently has none of (the fuel gauge lives on a not-yet-connected
//!   keyboard base) -- the absent case is the *common* case today, not an
//!   error state, and is rendered as a clean "No battery info" rather than
//!   a spinner or a dash.
//! - [`weather`]: a disk-cached, throttled wrapper around the same wttr.in
//!   host `nix/shell.nix`'s `k230-weather` desktop entry already uses, at
//!   its structured `j1` JSON format instead of that entry's human-readable
//!   paragraph -- current conditions, today's high/low, a short forecast
//!   strip, and a location name.
//! - [`clock`]: no state at all -- `home_screen`/`render.rs` format the
//!   current local time directly; see this module's `clock` submodule for
//!   the once-a-minute-aligned redraw timer only.

pub mod battery {
    use std::path::{Path, PathBuf};
    use std::time::Duration;

    /// Matches the task's "a slow poll of about 30 s" fallback -- this
    /// board has no inotify-worthy battery driver to watch yet (no supply
    /// exists at all today), so a plain poll is the only mechanism that
    /// also naturally covers "a supply appears" without a udev/inotify
    /// dependency this crate does not otherwise pull in.
    pub const POLL_INTERVAL: Duration = Duration::from_secs(30);

    #[derive(Clone, Debug, PartialEq, Eq)]
    pub enum BatteryState {
        /// No `power_supply` class device of type `Battery` exists at all --
        /// this board's current, real, everyday state (task: "there's
        /// currently NO battery device").
        Absent,
        /// `capacity` (0-100) and `status` (e.g. "Charging"/"Discharging"/
        /// "Full"/"Not charging"/"Unknown") as the kernel reports them,
        /// verbatim -- this module does no rounding or renaming beyond what
        /// `format` below does for display.
        Present { percent: u8, status: String },
    }

    impl BatteryState {
        pub fn is_charging(&self) -> bool {
            matches!(self, BatteryState::Present { status, .. } if status.eq_ignore_ascii_case("charging"))
        }
    }

    /// The exact widget text for a state (task: "a clean 'No battery info'
    /// state"). Kept here, not in `render.rs`, so a test can assert the
    /// wording without touching Cairo/Pango.
    pub fn format(state: &BatteryState) -> String {
        match state {
            BatteryState::Absent => "No battery info".to_string(),
            BatteryState::Present { percent, status } if status.eq_ignore_ascii_case("charging") => {
                format!("{percent}% - Charging")
            }
            BatteryState::Present { percent, status } if status.eq_ignore_ascii_case("full") => {
                format!("{percent}% - Full")
            }
            BatteryState::Present { percent, .. } => format!("{percent}%"),
        }
    }

    /// Reads one `power_supply` entry's `type`/`capacity`/`status` files
    /// (each a single trimmed line, exactly how the kernel's sysfs class
    /// exposes them) -- a missing or unreadable file, or one that will not
    /// parse, makes the whole entry unusable rather than partially trusted.
    fn read_entry(entry: &Path) -> Option<(u8, String)> {
        let kind = std::fs::read_to_string(entry.join("type")).ok()?;
        if kind.trim() != "Battery" {
            return None;
        }
        let capacity = std::fs::read_to_string(entry.join("capacity")).ok()?;
        let percent: u8 = capacity.trim().parse().ok()?;
        let status = std::fs::read_to_string(entry.join("status"))
            .map(|value| value.trim().to_string())
            .unwrap_or_else(|_| "Unknown".to_string());
        Some((percent.min(100), status))
    }

    /// Scans `power_supply_root` (ordinarily `/sys/class/power_supply`,
    /// injectable so tests never touch the real host's sysfs) for the first
    /// `type == "Battery"` entry, in directory-listing order -- this board
    /// has at most one, and a person's keyboard-base fuel gauge, once
    /// connected, is expected to be the only one that ever appears.
    pub fn read_state(power_supply_root: &Path) -> BatteryState {
        let Ok(entries) = std::fs::read_dir(power_supply_root) else {
            return BatteryState::Absent;
        };
        let mut names: Vec<PathBuf> = entries.filter_map(|entry| entry.ok().map(|entry| entry.path())).collect();
        names.sort();
        for path in names {
            if let Some((percent, status)) = read_entry(&path) {
                return BatteryState::Present { percent, status };
            }
        }
        BatteryState::Absent
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        fn tempdir(tag: &str) -> PathBuf {
            let dir = std::env::temp_dir().join(format!(
                "k230-battery-{tag}-{}-{}",
                std::process::id(),
                std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
            ));
            std::fs::create_dir_all(&dir).unwrap();
            dir
        }

        #[test]
        fn no_power_supply_directory_at_all_reads_as_absent() {
            let dir = tempdir("missing-root");
            let missing = dir.join("does-not-exist");
            assert_eq!(read_state(&missing), BatteryState::Absent);
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn an_empty_power_supply_directory_reads_as_absent() {
            let dir = tempdir("empty-root");
            assert_eq!(read_state(&dir), BatteryState::Absent);
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn a_non_battery_supply_such_as_line_power_is_ignored() {
            let dir = tempdir("ac-only");
            let ac = dir.join("AC0");
            std::fs::create_dir_all(&ac).unwrap();
            std::fs::write(ac.join("type"), "Mains\n").unwrap();
            assert_eq!(read_state(&dir), BatteryState::Absent);
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn a_present_battery_reports_percent_and_status() {
            let dir = tempdir("present");
            let battery = dir.join("BAT0");
            std::fs::create_dir_all(&battery).unwrap();
            std::fs::write(battery.join("type"), "Battery\n").unwrap();
            std::fs::write(battery.join("capacity"), "72\n").unwrap();
            std::fs::write(battery.join("status"), "Charging\n").unwrap();
            let state = read_state(&dir);
            assert_eq!(state, BatteryState::Present { percent: 72, status: "Charging".into() });
            assert!(state.is_charging());
            assert_eq!(format(&state), "72% - Charging");
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn absent_formats_as_the_clean_no_battery_info_string() {
            assert_eq!(format(&BatteryState::Absent), "No battery info");
        }

        #[test]
        fn a_full_battery_formats_distinctly_from_a_plain_percent() {
            let full = BatteryState::Present { percent: 100, status: "Full".into() };
            assert_eq!(format(&full), "100% - Full");
            let discharging = BatteryState::Present { percent: 54, status: "Discharging".into() };
            assert_eq!(format(&discharging), "54%");
            assert!(!discharging.is_charging());
        }

        #[test]
        fn a_battery_entry_missing_capacity_is_unusable_and_falls_back_to_absent() {
            let dir = tempdir("partial");
            let battery = dir.join("BAT0");
            std::fs::create_dir_all(&battery).unwrap();
            std::fs::write(battery.join("type"), "Battery\n").unwrap();
            // No `capacity` file written -- some drivers expose it late.
            assert_eq!(read_state(&dir), BatteryState::Absent);
            std::fs::remove_dir_all(&dir).unwrap();
        }
    }
}

pub mod clock {
    //! Local wall-clock time and date formatting for the Clock widget, and
    //! the once-a-minute, minute-aligned redraw timer (task: "redraw once a
    //! minute, aligned to the minute"). Uses `libc` (already a dependency)
    //! rather than pulling in a timezone crate: this board has no
    //! timezone-database story of its own yet, so this reads the C
    //! library's own local-time conversion (`localtime_r`, respecting
    //! `TZ`/`/etc/localtime` exactly like every other program on the
    //! system) instead of reimplementing it.

    /// A broken-down local time, split out from `libc::tm` so the
    /// formatting/scheduling functions below are plain, host-testable
    /// functions with no libc call of their own.
    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub struct LocalTime {
        pub hour: i32,
        pub minute: i32,
        pub second: i32,
        pub month: i32, // 1-12
        pub day: i32,   // day of month
        pub weekday: i32, // 0 = Sunday, matching `tm_wday`
    }

    /// Reads the current local time via `libc::localtime_r`. `None` only if
    /// the C library itself reports failure (never expected on a real
    /// system; kept `Option` so a caller degrades to a placeholder rather
    /// than panicking).
    pub fn now_local() -> Option<LocalTime> {
        let now = unsafe { libc::time(std::ptr::null_mut()) };
        let mut tm: libc::tm = unsafe { std::mem::zeroed() };
        let result = unsafe { libc::localtime_r(&now, &mut tm) };
        if result.is_null() {
            return None;
        }
        Some(LocalTime {
            hour: tm.tm_hour,
            minute: tm.tm_min,
            second: tm.tm_sec,
            month: tm.tm_mon + 1,
            day: tm.tm_mday,
            weekday: tm.tm_wday,
        })
    }

    const WEEKDAYS: [&str; 7] = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const MONTHS: [&str; 12] =
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    /// `HH:MM`, 24-hour -- large, theme-colored display text (task: "time
    /// and date, large, in theme colours").
    pub fn format_time(t: LocalTime) -> String {
        format!("{:02}:{:02}", t.hour, t.minute)
    }

    /// `Wed, Jan 5` -- a short, locale-agnostic date line under the time.
    pub fn format_date(t: LocalTime) -> String {
        let weekday = WEEKDAYS.get(t.weekday as usize).copied().unwrap_or("");
        let month = MONTHS.get((t.month - 1).clamp(0, 11) as usize).copied().unwrap_or("");
        format!("{weekday}, {month} {}", t.day)
    }

    /// Milliseconds until the next minute boundary, from the current
    /// second-within-minute -- what the caller schedules its next redraw
    /// tick at, instead of redrawing the clock every frame.
    pub fn ms_until_next_minute(second: i32) -> u32 {
        let remaining_seconds = (60 - second.clamp(0, 59)) as u32;
        remaining_seconds.saturating_mul(1000)
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        fn t(hour: i32, minute: i32, second: i32) -> LocalTime {
            LocalTime { hour, minute, second, month: 1, day: 5, weekday: 3 }
        }

        #[test]
        fn format_time_is_zero_padded_24_hour() {
            assert_eq!(format_time(t(9, 5, 0)), "09:05");
            assert_eq!(format_time(t(23, 59, 0)), "23:59");
            assert_eq!(format_time(t(0, 0, 0)), "00:00");
        }

        #[test]
        fn format_date_reads_as_a_short_weekday_month_day_line() {
            assert_eq!(format_date(t(9, 5, 0)), "Wed, Jan 5");
        }

        #[test]
        fn ms_until_next_minute_counts_down_to_the_boundary() {
            assert_eq!(ms_until_next_minute(0), 60_000);
            assert_eq!(ms_until_next_minute(59), 1_000);
            assert_eq!(ms_until_next_minute(30), 30_000);
        }

        #[test]
        fn now_local_returns_a_plausible_reading_on_this_host() {
            let now = now_local().expect("libc localtime_r should succeed on any real host");
            assert!((0..24).contains(&now.hour));
            assert!((0..60).contains(&now.minute));
        }
    }
}

pub mod weather {
    use serde::{Deserialize, Serialize};
    use std::io::Write;
    use std::path::{Path, PathBuf};
    use std::process::Command;
    use std::time::{Duration, SystemTime};

    /// Task: "Fetch at most every 30 min".
    pub const REFRESH_INTERVAL: Duration = Duration::from_secs(30 * 60);
    /// wttr.in's structured JSON format (`home-widget-design`: "switch the
    /// fetch to it"), replacing the old compact `%C|%t` one-liner --
    /// `j1` is the only format that carries a high/low, an hourly forecast,
    /// and a location name, all of which the redesigned Weather widget
    /// shows.
    const WTTR_URL: &str = "https://wttr.in/?format=j1";

    /// One entry in the widget's short forecast strip: a short clock-style
    /// label (`3pm`) and enough to draw the same condition glyph the
    /// current-conditions card uses ([`condition_glyph`]).
    #[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
    pub struct ForecastEntry {
        pub label: String,
        pub temp_c: i32,
        pub condition: String,
    }

    #[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
    pub struct WeatherSnapshot {
        /// `nearest_area[0].areaName[0].value`, e.g. "Boston" -- empty when
        /// wttr.in's response omits it (never expected, but not load-
        /// bearing: the renderer just leaves the location line out).
        pub location: String,
        pub condition: String,
        pub temperature_c: i32,
        pub feels_like_c: i32,
        pub high_c: i32,
        pub low_c: i32,
        /// Up to 5 entries, nearest hour first (task: "a small 3-5 hour or
        /// day forecast strip").
        pub forecast: Vec<ForecastEntry>,
        pub fetched_unix_secs: u64,
    }

    /// What the widget actually shows, folding "no cache yet" and "cache
    /// exists but is old" into the same tri-state a renderer needs (task:
    /// "Handle offline gracefully").
    #[derive(Clone, Debug, PartialEq)]
    pub enum WeatherDisplay {
        Fresh(WeatherSnapshot),
        Stale(WeatherSnapshot),
        Unavailable,
    }

    /// `$XDG_CACHE_HOME/k230-shell/weather.json`, or
    /// `$HOME/.cache/k230-shell/weather.json` -- same fallback shape as
    /// `theme_thumbnails::disk_cache_dir_from`, one file instead of a
    /// directory since there is only ever one cached snapshot.
    pub fn cache_path() -> Option<PathBuf> {
        cache_path_from(std::env::var("XDG_CACHE_HOME").ok().as_deref(), std::env::var("HOME").ok().as_deref())
    }

    fn cache_path_from(xdg_cache_home: Option<&str>, home: Option<&str>) -> Option<PathBuf> {
        if let Some(dir) = xdg_cache_home {
            if !dir.trim().is_empty() {
                return Some(PathBuf::from(dir).join("k230-shell/weather.json"));
            }
        }
        let home = home?;
        if home.trim().is_empty() {
            return None;
        }
        Some(PathBuf::from(home).join(".cache/k230-shell/weather.json"))
    }

    pub fn load_cache(path: &Path) -> Option<WeatherSnapshot> {
        let bytes = std::fs::read(path).ok()?;
        serde_json::from_slice(&bytes).ok()
    }

    /// Best-effort write -- a failed cache write only costs an extra fetch
    /// next time, never correctness, so this deliberately does not use the
    /// heavier atomic-rename convention `home_state::save` needs for a file
    /// whose loss would be user-visible data loss.
    pub fn save_cache(path: &Path, snapshot: &WeatherSnapshot) -> Result<(), String> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
        }
        let bytes = serde_json::to_vec(snapshot).map_err(|error| error.to_string())?;
        let mut file = std::fs::File::create(path).map_err(|error| error.to_string())?;
        file.write_all(&bytes).map_err(|error| error.to_string())
    }

    /// Whether a fetch is due: no cache at all, or the cache is older than
    /// [`REFRESH_INTERVAL`]. `now`/`cache` are both plain values (not read
    /// from disk/the clock inside this function) so this is host-testable
    /// without mocking time.
    pub fn should_fetch(cache: Option<&WeatherSnapshot>, now: SystemTime) -> bool {
        let Some(cache) = cache else { return true };
        let now_secs = now.duration_since(SystemTime::UNIX_EPOCH).map(|duration| duration.as_secs()).unwrap_or(0);
        now_secs.saturating_sub(cache.fetched_unix_secs) >= REFRESH_INTERVAL.as_secs()
    }

    /// Folds a possibly-missing cache and a possibly-stale one into what
    /// the widget shows: fresh, stale-but-something, or nothing at all yet.
    pub fn display_for(cache: Option<WeatherSnapshot>, now: SystemTime) -> WeatherDisplay {
        match cache {
            Some(snapshot) if !should_fetch(Some(&snapshot), now) => WeatherDisplay::Fresh(snapshot),
            Some(snapshot) => WeatherDisplay::Stale(snapshot),
            None => WeatherDisplay::Unavailable,
        }
    }

    // -- wttr.in's own j1 JSON shape, just the fields this widget uses.
    // Field names mirror wttr.in's exactly (via `#[serde(rename)]`) rather
    // than being guessed at; unrecognized fields are simply never
    // deserialized (`serde_json` ignores unknown keys by default), so this
    // stays forward-compatible with anything else wttr.in's response adds.

    #[derive(Deserialize)]
    struct WttrValue {
        value: String,
    }

    #[derive(Deserialize)]
    struct WttrCurrent {
        #[serde(rename = "temp_C")]
        temp_c: String,
        #[serde(rename = "FeelsLikeC")]
        feels_like_c: String,
        #[serde(rename = "weatherDesc")]
        weather_desc: Vec<WttrValue>,
    }

    #[derive(Deserialize)]
    struct WttrHourly {
        time: String,
        #[serde(rename = "tempC")]
        temp_c: String,
        #[serde(rename = "weatherDesc")]
        weather_desc: Vec<WttrValue>,
    }

    #[derive(Deserialize)]
    struct WttrDay {
        #[serde(rename = "maxtempC")]
        maxtemp_c: String,
        #[serde(rename = "mintempC")]
        mintemp_c: String,
        hourly: Vec<WttrHourly>,
    }

    #[derive(Deserialize)]
    struct WttrArea {
        #[serde(rename = "areaName")]
        area_name: Vec<WttrValue>,
    }

    #[derive(Deserialize)]
    struct WttrResponse {
        current_condition: Vec<WttrCurrent>,
        weather: Vec<WttrDay>,
        #[serde(default)]
        nearest_area: Vec<WttrArea>,
    }

    /// wttr.in's hourly `time` field is `"0"`, `"300"`, ... `"2100"` (the
    /// hour times 100, no leading zeros) -- this recovers just the hour.
    fn hour_from_wttr_time(time: &str) -> i32 {
        time.trim().parse::<i32>().unwrap_or(0) / 100
    }

    /// `15` -> `"3pm"`, `0`/`24` -> `"12am"` -- a short clock-style label for
    /// the forecast strip, matching how a person reads a analog/12-hour
    /// clock rather than wttr.in's own 24-hour hour-times-100 encoding.
    fn hour_label(hour_abs: i32) -> String {
        let hour = hour_abs.rem_euclid(24);
        let period = if hour < 12 { "am" } else { "pm" };
        let display = match hour % 12 {
            0 => 12,
            other => other,
        };
        format!("{display}{period}")
    }

    fn parse_c(value: &str) -> i32 {
        value.trim().parse().unwrap_or(0)
    }

    /// Parses wttr.in's `j1` JSON body into a [`WeatherSnapshot`], selecting
    /// up to 5 upcoming hourly forecast entries starting at-or-after
    /// `current_hour` (today's remaining hours, then tomorrow's, in order --
    /// wttr.in's default `j1` response covers 3 days, more than enough to
    /// always find 5). `current_hour` is a plain parameter (not read from
    /// the clock inside this function) so this stays host-testable with a
    /// fixed time. `None` for a body that does not parse as `j1` at all (a
    /// network error page, empty body, or rate-limit message) or is missing
    /// `current_condition`/`weather` -- [`fetch_now`]'s caller treats that
    /// uniformly as "offline".
    pub fn parse_wttr_j1(raw: &str, current_hour: i32) -> Option<WeatherSnapshot> {
        let parsed: WttrResponse = serde_json::from_str(raw).ok()?;
        let current = parsed.current_condition.first()?;
        let today = parsed.weather.first()?;
        let condition = current.weather_desc.first().map(|value| value.value.clone()).unwrap_or_default();
        let location = parsed
            .nearest_area
            .first()
            .and_then(|area| area.area_name.first())
            .map(|value| value.value.clone())
            .unwrap_or_default();

        let mut forecast = Vec::new();
        for (day_index, day) in parsed.weather.iter().take(2).enumerate() {
            let day_offset_hours = (day_index as i32) * 24;
            for hour in &day.hourly {
                let hour_abs = day_offset_hours + hour_from_wttr_time(&hour.time);
                if hour_abs < current_hour {
                    continue;
                }
                forecast.push(ForecastEntry {
                    label: hour_label(hour_abs),
                    temp_c: parse_c(&hour.temp_c),
                    condition: hour.weather_desc.first().map(|value| value.value.clone()).unwrap_or_default(),
                });
                if forecast.len() >= 5 {
                    break;
                }
            }
            if forecast.len() >= 5 {
                break;
            }
        }

        Some(WeatherSnapshot {
            location,
            condition,
            temperature_c: parse_c(&current.temp_c),
            feels_like_c: parse_c(&current.feels_like_c),
            high_c: parse_c(&today.maxtemp_c),
            low_c: parse_c(&today.mintemp_c),
            forecast,
            fetched_unix_secs: 0, // filled in by the caller (refresh) with the real fetch time
        })
    }

    /// A short, cheap-to-draw glyph key for `condition`'s free text --
    /// intentionally coarse (task: "a condition glyph and temperature"),
    /// matched by substring against wttr.in's own vocabulary rather than an
    /// exhaustive enum, so an unrecognized string still degrades to a
    /// sensible default glyph instead of `None`.
    pub fn condition_glyph(condition: &str) -> &'static str {
        let text = condition.to_lowercase();
        if text.contains("thunder") {
            "storm"
        } else if text.contains("snow") || text.contains("sleet") || text.contains("ice") {
            "snow"
        } else if text.contains("rain") || text.contains("drizzle") || text.contains("shower") {
            "rain"
        } else if text.contains("fog") || text.contains("mist") || text.contains("haze") {
            "fog"
        } else if text.contains("overcast") || text.contains("cloud") {
            "cloud"
        } else {
            // "clear"/"sunny" and anything unrecognized both land here --
            // an unrecognized condition string degrades to the same
            // sensible default glyph rather than `None` (see this
            // function's own doc).
            "sun"
        }
    }

    /// Shells out to `curl` for a fresh `j1` reading, the same source
    /// (`https://wttr.in`) `nix/shell.nix`'s `k230-weather` desktop entry
    /// already uses, just the structured format this widget needs instead
    /// of that entry's human paragraph. Any network failure, timeout, or
    /// unparseable body returns `Err` uniformly -- the caller
    /// (`should_fetch`/`display_for`) already treats "no fresh reading" and
    /// "offline" the same way, by keeping whatever cache it has. `curl_bin`
    /// is injectable so a test can point this at a fake binary instead of
    /// touching the real network; production callers pass `"curl"`.
    pub fn fetch_now(curl_bin: &str) -> Result<WeatherSnapshot, String> {
        let output = Command::new(curl_bin)
            .args([
                "--silent",
                "--show-error",
                "--max-time",
                "8",
                "--user-agent",
                "curl", // wttr.in serves its terse machine format only to a curl-like UA
                WTTR_URL,
            ])
            .output()
            .map_err(|error| error.to_string())?;
        if !output.status.success() {
            return Err(format!("curl exited with {:?}", output.status.code()));
        }
        let body = String::from_utf8_lossy(&output.stdout);
        let current_hour = crate::home_widgets::clock::now_local().map(|local| local.hour).unwrap_or(0);
        parse_wttr_j1(&body, current_hour).ok_or_else(|| "unparseable wttr.in response (likely offline)".to_string())
    }

    /// Fetches (if due) and folds the result into an updated on-disk cache
    /// and the display state to show right now -- the one call a caller off
    /// the Wayland thread needs; a failed fetch keeps whatever cache
    /// already existed rather than clearing it (task: "Handle offline
    /// gracefully").
    pub fn refresh(cache_file: &Path, curl_bin: &str, now: SystemTime) -> WeatherDisplay {
        let existing = load_cache(cache_file);
        if !should_fetch(existing.as_ref(), now) {
            return display_for(existing, now);
        }
        match fetch_now(curl_bin) {
            Ok(mut snapshot) => {
                snapshot.fetched_unix_secs =
                    now.duration_since(SystemTime::UNIX_EPOCH).map(|duration| duration.as_secs()).unwrap_or(0);
                let _ = save_cache(cache_file, &snapshot);
                WeatherDisplay::Fresh(snapshot)
            }
            Err(_) => display_for(existing, now),
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[test]
        fn cache_path_prefers_xdg_then_home_then_none() {
            assert_eq!(
                cache_path_from(Some("/xdg"), Some("/home/user")),
                Some(PathBuf::from("/xdg/k230-shell/weather.json"))
            );
            assert_eq!(
                cache_path_from(Some(""), Some("/home/user")),
                Some(PathBuf::from("/home/user/.cache/k230-shell/weather.json"))
            );
            assert_eq!(cache_path_from(None, None), None);
        }

        /// A minimal but shape-accurate `j1` body -- 2 days, 3 hourly
        /// entries per day (wttr.in's default gives 8 per day; 3 is plenty
        /// to exercise "today's remaining hours, then tomorrow's").
        fn sample_j1(current_temp_c: &str) -> String {
            format!(
                r#"{{
                    "current_condition": [{{
                        "temp_C": "{current_temp_c}",
                        "FeelsLikeC": "19",
                        "weatherDesc": [{{"value": "Partly cloudy"}}]
                    }}],
                    "weather": [
                        {{
                            "maxtempC": "23",
                            "mintempC": "14",
                            "hourly": [
                                {{"time": "0", "tempC": "15", "weatherDesc": [{{"value": "Clear"}}]}},
                                {{"time": "1200", "tempC": "22", "weatherDesc": [{{"value": "Sunny"}}]}},
                                {{"time": "1500", "tempC": "23", "weatherDesc": [{{"value": "Partly cloudy"}}]}}
                            ]
                        }},
                        {{
                            "maxtempC": "20",
                            "mintempC": "12",
                            "hourly": [
                                {{"time": "0", "tempC": "13", "weatherDesc": [{{"value": "Clear"}}]}},
                                {{"time": "900", "tempC": "17", "weatherDesc": [{{"value": "Light rain"}}]}},
                                {{"time": "1800", "tempC": "16", "weatherDesc": [{{"value": "Overcast"}}]}}
                            ]
                        }}
                    ],
                    "nearest_area": [{{"areaName": [{{"value": "Boston"}}]}}]
                }}"#
            )
        }

        #[test]
        fn parse_wttr_j1_reads_current_conditions_high_low_and_location() {
            let snapshot = parse_wttr_j1(&sample_j1("21"), 10).expect("valid j1 body");
            assert_eq!(snapshot.location, "Boston");
            assert_eq!(snapshot.condition, "Partly cloudy");
            assert_eq!(snapshot.temperature_c, 21);
            assert_eq!(snapshot.feels_like_c, 19);
            assert_eq!(snapshot.high_c, 23);
            assert_eq!(snapshot.low_c, 14);
        }

        #[test]
        fn parse_wttr_j1_forecast_starts_at_the_current_hour_and_spills_into_tomorrow() {
            // current_hour = 13 (1pm): today's 0h and 12h entries are in the
            // past, so the strip starts at today's 3pm, then continues into
            // tomorrow's hours in order.
            let snapshot = parse_wttr_j1(&sample_j1("21"), 13).expect("valid j1 body");
            let labels: Vec<&str> = snapshot.forecast.iter().map(|entry| entry.label.as_str()).collect();
            assert_eq!(labels, vec!["3pm", "12am", "9am", "6pm"]);
            assert_eq!(snapshot.forecast[0].temp_c, 23);
            assert_eq!(snapshot.forecast[0].condition, "Partly cloudy");
        }

        #[test]
        fn parse_wttr_j1_caps_the_forecast_at_five_entries() {
            let snapshot = parse_wttr_j1(&sample_j1("21"), 0).expect("valid j1 body");
            assert!(snapshot.forecast.len() <= 5);
        }

        #[test]
        fn parse_wttr_j1_rejects_anything_that_is_not_a_j1_body() {
            assert_eq!(parse_wttr_j1("", 12), None);
            assert_eq!(parse_wttr_j1("Unknown location", 12), None);
            assert_eq!(parse_wttr_j1("<html>rate limited</html>", 12), None);
            assert_eq!(parse_wttr_j1("{}", 12), None, "missing current_condition/weather");
        }

        #[test]
        fn condition_glyph_buckets_common_wttr_vocabulary() {
            assert_eq!(condition_glyph("Partly cloudy"), "cloud");
            assert_eq!(condition_glyph("Light rain shower"), "rain");
            assert_eq!(condition_glyph("Thundery outbreaks possible"), "storm");
            assert_eq!(condition_glyph("Clear"), "sun");
            assert_eq!(condition_glyph("Freezing fog"), "fog");
            assert_eq!(condition_glyph("Patchy snow possible"), "snow");
            assert_eq!(condition_glyph("something wttr.in has never printed before"), "sun");
        }

        fn sample_snapshot(fetched_unix_secs: u64) -> WeatherSnapshot {
            WeatherSnapshot {
                location: "Boston".into(),
                condition: "Clear".into(),
                temperature_c: 20,
                feels_like_c: 19,
                high_c: 23,
                low_c: 14,
                forecast: vec![ForecastEntry { label: "3pm".into(), temp_c: 21, condition: "Sunny".into() }],
                fetched_unix_secs,
            }
        }

        #[test]
        fn should_fetch_is_true_with_no_cache_and_false_just_after_a_fetch() {
            let now = SystemTime::UNIX_EPOCH + Duration::from_secs(1_000_000);
            assert!(should_fetch(None, now));
            let fresh = sample_snapshot(1_000_000 - 60);
            assert!(!should_fetch(Some(&fresh), now));
        }

        #[test]
        fn should_fetch_is_true_once_the_refresh_interval_has_passed() {
            let now = SystemTime::UNIX_EPOCH + Duration::from_secs(1_000_000);
            let old = sample_snapshot(1_000_000 - REFRESH_INTERVAL.as_secs() - 1);
            assert!(should_fetch(Some(&old), now));
        }

        #[test]
        fn display_for_distinguishes_fresh_stale_and_unavailable() {
            let now = SystemTime::UNIX_EPOCH + Duration::from_secs(1_000_000);
            assert_eq!(display_for(None, now), WeatherDisplay::Unavailable);
            let fresh = sample_snapshot(1_000_000 - 60);
            assert_eq!(display_for(Some(fresh.clone()), now), WeatherDisplay::Fresh(fresh));
            let old = sample_snapshot(0);
            assert_eq!(display_for(Some(old.clone()), now), WeatherDisplay::Stale(old));
        }

        #[test]
        fn save_then_load_cache_round_trips() {
            let dir = std::env::temp_dir().join(format!(
                "k230-weather-cache-{}-{}",
                std::process::id(),
                std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
            ));
            let path = dir.join("weather.json");
            let snapshot = sample_snapshot(42);
            save_cache(&path, &snapshot).unwrap();
            assert_eq!(load_cache(&path), Some(snapshot));
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn refresh_keeps_the_existing_cache_when_the_fetch_binary_fails() {
            let dir = std::env::temp_dir().join(format!(
                "k230-weather-offline-{}-{}",
                std::process::id(),
                std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
            ));
            std::fs::create_dir_all(&dir).unwrap();
            let path = dir.join("weather.json");
            let stale = sample_snapshot(0);
            save_cache(&path, &stale).unwrap();
            let now = SystemTime::UNIX_EPOCH + Duration::from_secs(10_000_000);
            // "/nonexistent-curl-binary" always fails to spawn -- stands in
            // for "offline" without touching the real network.
            let display = refresh(&path, "/nonexistent-curl-binary", now);
            assert_eq!(display, WeatherDisplay::Stale(stale), "offline keeps showing the last good reading");
        }
    }
}

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

    #[derive(Clone, Debug, Default, PartialEq, Eq)]
    pub enum BatteryState {
        /// No `power_supply` class device of type `Battery` exists at all --
        /// this board's current, real, everyday state (task: "there's
        /// currently NO battery device").
        #[default]
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
                format!("{percent}% · Charging")
            }
            BatteryState::Present { percent, status } if status.eq_ignore_ascii_case("full") => {
                format!("{percent}% · Full")
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

    // ---- Battery - Details -------------------------------------------------

    /// Poll period while a Battery - Details widget is placed on Home.
    pub const DETAILS_POLL_INTERVAL: Duration = Duration::from_secs(10);

    /// The poll period to use: the faster one only while a details widget is
    /// on Home (any page), otherwise the ordinary [`POLL_INTERVAL`].
    pub fn poll_interval(details_widget_placed: bool) -> Duration {
        if details_widget_placed {
            DETAILS_POLL_INTERVAL
        } else {
            POLL_INTERVAL
        }
    }

    /// The charger / input-power side (any non-Battery supply), every field
    /// optional because drivers expose different subsets.
    #[derive(Clone, Debug, Default, PartialEq, Eq)]
    pub struct Input {
        /// `ONLINE`: whether input power is present.
        pub online: Option<bool>,
        /// Supply `TYPE` as the kernel names it ("USB", "Mains", "USB_C"...).
        pub kind: Option<String>,
        pub charge_type: Option<String>,
        pub health: Option<String>,
        pub input_limit_ua: Option<i64>,
        pub charge_current_ua: Option<i64>,
        pub charge_voltage_uv: Option<i64>,
    }

    /// Everything the battery's gauge exposes, all in kernel units (uV, uA,
    /// uW, uAh, tenths of a degree C, seconds), each optional but the
    /// percentage.
    #[derive(Clone, Debug, Default, PartialEq, Eq)]
    pub struct Details {
        pub percent: u8,
        pub status: String,
        pub health: Option<String>,
        pub time_to_full_s: Option<i64>,
        pub time_to_empty_s: Option<i64>,
        /// Signed: positive charging, negative discharging (gauge convention).
        pub current_ua: Option<i64>,
        pub power_uw: Option<i64>,
        pub voltage_uv: Option<i64>,
        pub charge_now_uah: Option<i64>,
        pub charge_full_uah: Option<i64>,
        pub charge_design_uah: Option<i64>,
        pub cycles: Option<i64>,
        pub temp_deci_c: Option<i64>,
        pub input: Option<Input>,
    }

    #[derive(Clone, Debug, Default, PartialEq, Eq)]
    pub enum DetailsState {
        #[default]
        Absent,
        Present(Box<Details>),
    }

    type Uevent<'a> = std::collections::HashMap<&'a str, &'a str>;

    fn uevent_map(raw: &str) -> Uevent<'_> {
        raw.lines()
            .filter_map(|line| line.split_once('='))
            .map(|(key, value)| (key.strip_prefix("POWER_SUPPLY_").unwrap_or(key), value.trim()))
            .collect()
    }

    fn num(map: &Uevent, key: &str) -> Option<i64> {
        map.get(key)?.parse().ok()
    }

    fn text(map: &Uevent, key: &str) -> Option<String> {
        map.get(key).filter(|value| !value.is_empty()).map(|value| (*value).to_string())
    }

    fn details_from_uevent(map: &Uevent) -> Option<Details> {
        if map.get("TYPE") != Some(&"Battery") {
            return None;
        }
        let percent: u8 = map.get("CAPACITY")?.parse().ok()?;
        // The kernel reports an unknown time as a huge or non-positive value.
        let seconds = |key: &str| num(map, key).filter(|value| *value > 0 && *value < 0xffff);
        Some(Details {
            percent: percent.min(100),
            status: text(map, "STATUS").unwrap_or_else(|| "Unknown".to_string()),
            health: text(map, "HEALTH"),
            time_to_full_s: seconds("TIME_TO_FULL_NOW"),
            time_to_empty_s: seconds("TIME_TO_EMPTY_NOW"),
            current_ua: num(map, "CURRENT_NOW"),
            power_uw: num(map, "POWER_AVG").or_else(|| num(map, "POWER_NOW")),
            voltage_uv: num(map, "VOLTAGE_NOW"),
            charge_now_uah: num(map, "CHARGE_NOW"),
            charge_full_uah: num(map, "CHARGE_FULL").filter(|value| *value > 0),
            charge_design_uah: num(map, "CHARGE_FULL_DESIGN").filter(|value| *value > 0),
            cycles: num(map, "CYCLE_COUNT"),
            temp_deci_c: num(map, "TEMP"),
            input: None,
        })
    }

    fn input_from_uevent(map: &Uevent) -> Option<Input> {
        let kind = map.get("TYPE")?;
        if *kind == "Battery" {
            return None;
        }
        Some(Input {
            online: num(map, "ONLINE").map(|value| value != 0),
            kind: Some((*kind).to_string()),
            charge_type: text(map, "CHARGE_TYPE").filter(|value| value != "N/A"),
            health: text(map, "HEALTH"),
            input_limit_ua: num(map, "INPUT_CURRENT_LIMIT"),
            charge_current_ua: num(map, "CONSTANT_CHARGE_CURRENT"),
            charge_voltage_uv: num(map, "CONSTANT_CHARGE_VOLTAGE"),
        })
    }

    /// Scans `power_supply_root` once, reading each supply's single `uevent`
    /// file: the first (sorted) `Battery` becomes the details, and the best
    /// other supply (one that is online, else the first) its input side.
    pub fn read_details(power_supply_root: &Path) -> DetailsState {
        let Ok(entries) = std::fs::read_dir(power_supply_root) else {
            return DetailsState::Absent;
        };
        let mut paths: Vec<PathBuf> = entries.filter_map(|entry| entry.ok().map(|entry| entry.path())).collect();
        paths.sort();
        let mut battery: Option<Details> = None;
        let mut input: Option<Input> = None;
        for path in paths {
            let Ok(raw) = std::fs::read_to_string(path.join("uevent")) else {
                continue;
            };
            let map = uevent_map(&raw);
            if battery.is_none() {
                if let Some(found) = details_from_uevent(&map) {
                    battery = Some(found);
                    continue;
                }
            }
            if let Some(found) = input_from_uevent(&map) {
                let better = match &input {
                    None => true,
                    Some(current) => current.online != Some(true) && found.online == Some(true),
                };
                if better {
                    input = Some(found);
                }
            }
        }
        match battery {
            Some(mut details) => {
                details.input = input;
                DetailsState::Present(Box::new(details))
            }
            None => DetailsState::Absent,
        }
    }

    fn round_to(value: i64, step: i64) -> i64 {
        let half = step / 2;
        if value >= 0 {
            (value + half) / step * step
        } else {
            -((-value + half) / step * step)
        }
    }

    impl DetailsState {
        /// The same snapshot rounded to what the widget displays, so two
        /// snapshots that paint identically compare equal and Home repaints
        /// only on a visible change.
        pub fn quantized(&self) -> DetailsState {
            match self {
                DetailsState::Absent => DetailsState::Absent,
                DetailsState::Present(details) => DetailsState::Present(Box::new(details.quantized())),
            }
        }
    }

    impl Details {
        pub fn quantized(&self) -> Details {
            let mut out = self.clone();
            out.current_ua = out.current_ua.map(|v| round_to(v, 10_000));
            out.power_uw = out.power_uw.map(|v| round_to(v, 100_000));
            out.voltage_uv = out.voltage_uv.map(|v| round_to(v, 10_000));
            out.charge_now_uah = out.charge_now_uah.map(|v| round_to(v, 1_000));
            out.charge_full_uah = out.charge_full_uah.map(|v| round_to(v, 1_000));
            out.charge_design_uah = out.charge_design_uah.map(|v| round_to(v, 1_000));
            out.time_to_full_s = out.time_to_full_s.map(|v| round_to(v, 60));
            out.time_to_empty_s = out.time_to_empty_s.map(|v| round_to(v, 60));
            if let Some(input) = out.input.as_mut() {
                input.input_limit_ua = input.input_limit_ua.map(|v| round_to(v, 10_000));
                input.charge_current_ua = input.charge_current_ua.map(|v| round_to(v, 10_000));
                input.charge_voltage_uv = input.charge_voltage_uv.map(|v| round_to(v, 10_000));
            }
            out
        }

        pub fn is_charging(&self) -> bool {
            self.status.eq_ignore_ascii_case("charging")
        }

        pub fn is_discharging(&self) -> bool {
            self.status.eq_ignore_ascii_case("discharging")
        }

        /// The state word, with the charge type while charging
        /// ("Charging · Fast"). `Not charging`/`Full` pass through.
        pub fn state_label(&self) -> String {
            if self.is_charging() {
                if let Some(kind) = self.input.as_ref().and_then(|input| input.charge_type.as_deref()) {
                    if !kind.eq_ignore_ascii_case("none") && !kind.eq_ignore_ascii_case("unknown") {
                        return format!("Charging · {kind}");
                    }
                }
            }
            self.status.clone()
        }

        /// "2 h 16 m to full" / "45 m left", from whichever time the gauge
        /// reports for the current direction.
        pub fn time_label(&self) -> Option<String> {
            let (seconds, suffix) = if self.is_discharging() {
                (self.time_to_empty_s?, "left")
            } else if self.is_charging() {
                (self.time_to_full_s?, "to full")
            } else {
                // Full or not charging: say where the power comes from
                // rather than leave the line empty.
                return self.on_charger().then(|| "On charger".to_string());
            };
            Some(format!("{} {suffix}", format_duration(seconds)))
        }

        /// External power is present (the charger reports online).
        pub fn on_charger(&self) -> bool {
            self.input.as_ref().is_some_and(|input| input.online == Some(true))
        }

        /// Neither charging nor discharging: a gauge's zero current and power
        /// then say nothing, so those readings are left out.
        fn idle(&self) -> bool {
            !self.is_charging() && !self.is_discharging()
        }

        /// Signed battery current, "+600 mA" / "\u{2212}412 mA".
        pub fn current_label(&self) -> Option<String> {
            let ua = round_to(self.current_ua?, 10_000);
            (ua != 0 || !self.idle()).then(|| format_signed_ma(ua))
        }

        /// Power in watts, signed like the current when known; the gauge's
        /// `POWER_AVG`, else volts times amps.
        pub fn power_label(&self) -> Option<String> {
            let magnitude = match self.power_uw {
                Some(power) => power.abs(),
                None => {
                    let (volts, amps) = (self.voltage_uv?, self.current_ua?);
                    ((i128::from(volts) * i128::from(amps.abs())) / 1_000_000) as i64
                }
            };
            let negative = match self.current_ua {
                Some(ua) => ua < 0,
                None => self.power_uw.is_some_and(|power| power < 0),
            };
            let rounded = round_to(magnitude, 100_000);
            (rounded != 0 || !self.idle()).then(|| format_watts(rounded, negative))
        }

        pub fn voltage_label(&self) -> Option<String> {
            self.voltage_uv.map(|uv| format!("{:.2} V", round_to(uv, 10_000) as f64 / 1_000_000.0))
        }

        pub fn temperature_label(&self) -> Option<String> {
            self.temp_deci_c.map(format_temperature)
        }

        /// "1627 / 3000 mAh" (stored over full); just the known figure
        /// when only one is.
        pub fn charge_label(&self) -> Option<String> {
            let mah = |ua: i64| round_to(ua, 1_000) / 1_000;
            match (self.charge_now_uah, self.charge_full_uah) {
                (Some(now), Some(full)) => Some(format!("{} / {} mAh", mah(now), mah(full))),
                (Some(now), None) => Some(format!("{} mAh", mah(now))),
                (None, Some(full)) => Some(format!("{} mAh full", mah(full))),
                (None, None) => None,
            }
        }

        /// Full charge over design charge, whole percent (capped at 100).
        pub fn health_percent(&self) -> Option<u32> {
            let (full, design) = (self.charge_full_uah?, self.charge_design_uah?);
            if design <= 0 {
                return None;
            }
            Some(((full as f64 / design as f64 * 100.0).round() as i64).clamp(0, 100) as u32)
        }

        pub fn health_label(&self) -> Option<String> {
            self.health_percent().map(|percent| format!("{percent}%"))
        }

        /// A gauge that reports zero cycles is not counting them.
        pub fn cycles_label(&self) -> Option<String> {
            self.cycles.filter(|count| *count > 0).map(|count| count.to_string())
        }

        /// The input line: where power comes from, then limit and targets.
        /// E.g. "USB power · limit 3.25 A · 2.05 A @ 4.21 V".
        pub fn input_label(&self) -> Option<String> {
            self.input_label_with(true, true)
        }

        /// The input line from most to least detailed, for a widget too
        /// narrow for the whole line: the charge target goes first, then
        /// the limit. The source and a charger fault always stay.
        pub fn input_label_choices(&self) -> Vec<String> {
            let mut choices: Vec<String> = Vec::new();
            for (limit, target) in [(true, true), (true, false), (false, false)] {
                if let Some(label) = self.input_label_with(limit, target) {
                    if !choices.contains(&label) {
                        choices.push(label);
                    }
                }
            }
            choices
        }

        fn input_label_with(&self, show_limit: bool, show_target: bool) -> Option<String> {
            let mut parts: Vec<String> = Vec::new();
            match &self.input {
                Some(input) => {
                    match input.online {
                        Some(true) => parts.push(source_label(input.kind.as_deref())),
                        Some(false) => parts.push("On battery".to_string()),
                        None => {}
                    }
                    if input.online != Some(false) {
                        if let Some(limit) = input.input_limit_ua.filter(|_| show_limit) {
                            parts.push(format!("limit {}", format_amps(limit)));
                        }
                        let volts = |uv: i64| format!("{:.2} V", round_to(uv, 10_000) as f64 / 1_000_000.0);
                        let target = (input.charge_current_ua, input.charge_voltage_uv);
                        match if show_target { target } else { (None, None) } {
                            (Some(amps), Some(uv)) => parts.push(format!("{} @ {}", format_amps(amps), volts(uv))),
                            (Some(amps), None) => parts.push(format!("{} target", format_amps(amps))),
                            (None, Some(uv)) => parts.push(format!("{} target", volts(uv))),
                            (None, None) => {}
                        }
                    }
                    if let Some(health) = input.health.as_deref() {
                        if !health.eq_ignore_ascii_case("good") && !health.eq_ignore_ascii_case("unknown") {
                            parts.push(format!("charger {}", health.to_lowercase()));
                        }
                    }
                }
                None => {
                    if self.is_discharging() {
                        parts.push("On battery".to_string());
                    }
                }
            }
            if parts.is_empty() {
                None
            } else {
                Some(parts.join(" · "))
            }
        }
    }

    fn source_label(kind: Option<&str>) -> String {
        match kind {
            Some("USB_C") => "USB-C power".to_string(),
            Some(kind) if kind.starts_with("USB") => "USB power".to_string(),
            Some("Mains") => "AC power".to_string(),
            Some("Wireless") => "Wireless power".to_string(),
            _ => "External power".to_string(),
        }
    }

    pub fn format_duration(seconds: i64) -> String {
        let minutes = (seconds.max(0) + 30) / 60;
        if minutes >= 60 {
            format!("{} h {} m", minutes / 60, minutes % 60)
        } else {
            format!("{minutes} m")
        }
    }

    fn format_signed_ma(microamps: i64) -> String {
        let ma = microamps / 1_000;
        match ma {
            0 => "0 mA".to_string(),
            value if value > 0 => format!("+{value} mA"),
            value => format!("\u{2212}{} mA", -value),
        }
    }

    fn format_watts(microwatts: i64, negative: bool) -> String {
        let tenths = microwatts / 100_000;
        let sign = if tenths == 0 {
            ""
        } else if negative {
            "\u{2212}"
        } else {
            "+"
        };
        format!("{sign}{}.{} W", tenths / 10, tenths % 10)
    }

    fn format_amps(microamps: i64) -> String {
        if microamps >= 1_000_000 {
            format!("{:.2} A", microamps as f64 / 1_000_000.0)
        } else {
            format!("{} mA", microamps / 1_000)
        }
    }

    fn format_temperature(deci_c: i64) -> String {
        let sign = if deci_c < 0 { "\u{2212}" } else { "" };
        format!("{sign}{}.{} \u{b0}C", deci_c.abs() / 10, deci_c.abs() % 10)
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
            assert_eq!(format(&state), "72% · Charging");
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn absent_formats_as_the_clean_no_battery_info_string() {
            assert_eq!(format(&BatteryState::Absent), "No battery info");
        }

        #[test]
        fn a_full_battery_formats_distinctly_from_a_plain_percent() {
            let full = BatteryState::Present { percent: 100, status: "Full".into() };
            assert_eq!(format(&full), "100% · Full");
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

    #[cfg(test)]
    mod details_tests {
        use super::*;

        const GAUGE_CHARGING: &str = "POWER_SUPPLY_NAME=bq27220-0\nPOWER_SUPPLY_TYPE=Battery\nPOWER_SUPPLY_STATUS=Charging\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\nPOWER_SUPPLY_TECHNOLOGY=Li-ion\nPOWER_SUPPLY_CYCLE_COUNT=0\nPOWER_SUPPLY_VOLTAGE_NOW=4202000\nPOWER_SUPPLY_CURRENT_NOW=600000\nPOWER_SUPPLY_POWER_AVG=2540000\nPOWER_SUPPLY_CHARGE_FULL_DESIGN=3000000\nPOWER_SUPPLY_CHARGE_FULL=3000000\nPOWER_SUPPLY_CHARGE_NOW=1627000\nPOWER_SUPPLY_CAPACITY=55\nPOWER_SUPPLY_CAPACITY_LEVEL=Normal\nPOWER_SUPPLY_TEMP=381\nPOWER_SUPPLY_TIME_TO_FULL_NOW=8160\nPOWER_SUPPLY_MANUFACTURER=Texas Instruments\n";
        const CHARGER_ONLINE: &str = "POWER_SUPPLY_NAME=bq25890-charger-0\nPOWER_SUPPLY_TYPE=USB\nPOWER_SUPPLY_STATUS=Charging\nPOWER_SUPPLY_CHARGE_TYPE=Fast\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_VOLTAGE_NOW=4204000\nPOWER_SUPPLY_CURRENT_NOW=-550000\nPOWER_SUPPLY_CONSTANT_CHARGE_CURRENT=2048000\nPOWER_SUPPLY_CONSTANT_CHARGE_VOLTAGE=4208000\nPOWER_SUPPLY_INPUT_CURRENT_LIMIT=3250000\nPOWER_SUPPLY_TEMP=380\nPOWER_SUPPLY_MODEL_NAME=BQ25896\n";
        const GAUGE_DISCHARGING: &str = "POWER_SUPPLY_TYPE=Battery\nPOWER_SUPPLY_STATUS=Discharging\nPOWER_SUPPLY_VOLTAGE_NOW=3890000\nPOWER_SUPPLY_CURRENT_NOW=-412000\nPOWER_SUPPLY_CAPACITY=71\nPOWER_SUPPLY_TIME_TO_EMPTY_NOW=2700\nPOWER_SUPPLY_CHARGE_FULL=2850000\nPOWER_SUPPLY_CHARGE_FULL_DESIGN=3000000\nPOWER_SUPPLY_CHARGE_NOW=2000000\nPOWER_SUPPLY_CYCLE_COUNT=12\nPOWER_SUPPLY_TEMP=-25\n";
        const CHARGER_OFFLINE: &str = "POWER_SUPPLY_TYPE=USB\nPOWER_SUPPLY_ONLINE=0\nPOWER_SUPPLY_HEALTH=Good\n";

        fn root(tag: &str, supplies: &[(&str, &str)]) -> PathBuf {
            let dir = std::env::temp_dir().join(format!(
                "k230-details-{tag}-{}-{}",
                std::process::id(),
                std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
            ));
            for (name, uevent) in supplies {
                std::fs::create_dir_all(dir.join(name)).unwrap();
                std::fs::write(dir.join(name).join("uevent"), uevent).unwrap();
            }
            std::fs::create_dir_all(&dir).unwrap();
            dir
        }

        fn present(state: DetailsState) -> Details {
            match state {
                DetailsState::Present(details) => *details,
                DetailsState::Absent => panic!("expected a battery"),
            }
        }

        #[test]
        fn the_charging_board_fixture_parses_every_metric() {
            let dir = root("charging", &[("bq25890-charger-0", CHARGER_ONLINE), ("bq27220-0", GAUGE_CHARGING)]);
            let d = present(read_details(&dir));
            assert_eq!(d.percent, 55);
            assert_eq!(d.state_label(), "Charging · Fast");
            assert_eq!(d.time_label().as_deref(), Some("2 h 16 m to full"));
            assert_eq!(d.current_label().as_deref(), Some("+600 mA"));
            assert_eq!(d.power_label().as_deref(), Some("+2.5 W"));
            assert_eq!(d.voltage_label().as_deref(), Some("4.20 V"));
            assert_eq!(d.charge_label().as_deref(), Some("1627 / 3000 mAh"));
            assert_eq!(d.health_label().as_deref(), Some("100%"));
            assert_eq!(d.cycles_label(), None, "a zero cycle count is not shown");
            assert_eq!(d.temperature_label().as_deref(), Some("38.1 \u{b0}C"));
            assert_eq!(d.input_label().as_deref(), Some("USB power · limit 3.25 A · 2.05 A @ 4.21 V"));
            assert_eq!(d.input_label_choices(), ["USB power · limit 3.25 A · 2.05 A @ 4.21 V", "USB power · limit 3.25 A", "USB power"]);
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn a_discharging_gauge_shows_negative_current_and_time_left() {
            let dir = root("discharging", &[("bq25890-charger-0", CHARGER_OFFLINE), ("bq27220-0", GAUGE_DISCHARGING)]);
            let d = present(read_details(&dir));
            assert_eq!(d.state_label(), "Discharging");
            assert_eq!(d.time_label().as_deref(), Some("45 m left"));
            assert_eq!(d.current_label().as_deref(), Some("\u{2212}410 mA"));
            // No POWER_AVG: volts times amps, signed like the current.
            assert_eq!(d.power_label().as_deref(), Some("\u{2212}1.6 W"));
            assert_eq!(d.health_label().as_deref(), Some("95%"));
            assert_eq!(d.cycles_label().as_deref(), Some("12"));
            assert_eq!(d.temperature_label().as_deref(), Some("\u{2212}2.5 \u{b0}C"));
            assert_eq!(d.input_label().as_deref(), Some("On battery"));
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn missing_attributes_are_simply_omitted() {
            let dir = root("sparse", &[("BAT0", "POWER_SUPPLY_TYPE=Battery\nPOWER_SUPPLY_CAPACITY=40\n")]);
            let d = present(read_details(&dir));
            assert_eq!(d.percent, 40);
            assert_eq!(d.status, "Unknown");
            for label in [d.time_label(), d.current_label(), d.power_label(), d.voltage_label(), d.charge_label(), d.health_label(), d.cycles_label(), d.temperature_label(), d.input_label()] {
                assert_eq!(label, None);
            }
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn a_discharging_battery_with_no_charger_supply_still_says_on_battery() {
            let dir = root("nocharger", &[("bq27220-0", GAUGE_DISCHARGING)]);
            assert_eq!(present(read_details(&dir)).input_label().as_deref(), Some("On battery"));
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn no_battery_or_no_root_is_absent() {
            let dir = root("none", &[("ucs1", CHARGER_ONLINE)]);
            assert_eq!(read_details(&dir), DetailsState::Absent);
            assert_eq!(read_details(&dir.join("missing")), DetailsState::Absent);
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn an_online_supply_wins_over_an_offline_one_and_bad_charger_health_shows() {
            let sick = CHARGER_ONLINE.replace("HEALTH=Good", "HEALTH=Overheat");
            let dir = root("pick", &[("a-offline", CHARGER_OFFLINE), ("b-online", &sick), ("gauge", GAUGE_CHARGING)]);
            let label = present(read_details(&dir)).input_label().unwrap();
            assert!(label.starts_with("USB power"), "{label}");
            assert!(label.ends_with("charger overheat"), "{label}");
            let shortest = present(read_details(&dir)).input_label_choices().pop().unwrap();
            assert_eq!(shortest, "USB power · charger overheat");
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn durations_and_signs_format_as_displayed() {
            assert_eq!(format_duration(8160), "2 h 16 m");
            assert_eq!(format_duration(2700), "45 m");
            assert_eq!(format_duration(3600), "1 h 0 m");
            assert_eq!(format_signed_ma(-412_000), "\u{2212}412 mA");
            assert_eq!(format_signed_ma(0), "0 mA");
            assert_eq!(format_amps(500_000), "500 mA");
            assert_eq!(format_amps(3_250_000), "3.25 A");
        }

        #[test]
        fn unknown_gauge_times_are_dropped() {
            let raw = GAUGE_CHARGING.replace("TIME_TO_FULL_NOW=8160", "TIME_TO_FULL_NOW=65535");
            let dir = root("badtime", &[("g", &raw)]);
            assert_eq!(present(read_details(&dir)).time_label(), None);
            std::fs::remove_dir_all(&dir).unwrap();
        }

        #[test]
        fn noise_below_the_displayed_precision_quantizes_equal() {
            let dir = root("quant", &[("g", GAUGE_CHARGING)]);
            let a = read_details(&dir);
            let noisy = GAUGE_CHARGING.replace("CURRENT_NOW=600000", "CURRENT_NOW=603000").replace("VOLTAGE_NOW=4202000", "VOLTAGE_NOW=4204000").replace("TIME_TO_FULL_NOW=8160", "TIME_TO_FULL_NOW=8140");
            let dir2 = root("quant2", &[("g", &noisy)]);
            let b = read_details(&dir2);
            assert_ne!(a, b);
            assert_eq!(a.quantized(), b.quantized());
            let moved = GAUGE_CHARGING.replace("CAPACITY=55", "CAPACITY=56");
            let dir3 = root("quant3", &[("g", &moved)]);
            assert_ne!(a.quantized(), read_details(&dir3).quantized());
            for d in [dir, dir2, dir3] {
                std::fs::remove_dir_all(&d).unwrap();
            }
        }

        #[test]
        fn polling_is_faster_only_while_a_details_widget_is_placed() {
            assert_eq!(poll_interval(true), Duration::from_secs(10));
            assert_eq!(poll_interval(false), Duration::from_secs(30));
        }
    }

    /// The charge-over-time record behind the Battery - Details graph: one
    /// `<unix seconds> <percent> <c|d>` line per sample in
    /// `$XDG_STATE_HOME/k230-shell/battery-history`, appended about once a
    /// minute (and on a charging change) whether or not the widget is
    /// placed, kept to the last day, and rewritten through a temp file and a
    /// rename once it has grown to twice that.
    pub mod history {
        use std::io::Write;
        use std::path::{Path, PathBuf};

        /// How far back the widget graphs.
        pub const WINDOW_S: i64 = 12 * 3600;
        /// How far back the file keeps.
        pub const KEEP_S: i64 = 24 * 3600;
        pub const SAMPLE_EVERY_S: i64 = 60;
        /// A longer silence than this (the shell was not running) breaks the line.
        pub const GAP_S: i64 = 300;
        const MAX_FILE_BYTES: u64 = 1 << 20;

        #[derive(Clone, Copy, Debug, PartialEq, Eq)]
        pub struct Sample {
            pub at: i64,
            pub percent: u8,
            pub charging: bool,
        }

        /// What the widget paints: the samples in the window ending at `now`.
        #[derive(Clone, Debug, Default, PartialEq, Eq)]
        pub struct View {
            pub now: i64,
            pub samples: Vec<Sample>,
        }

        impl View {
            /// The graph's time span: the recorded history rounded up to whole
            /// hours, at least one hour and at most [`WINDOW_S`], so a short
            /// history fills the graph instead of being a sliver at its edge.
            pub fn span_s(&self) -> i64 {
                let recorded = self.samples.first().map_or(0, |first| self.now - first.at);
                let hours = (recorded + 3599) / 3600;
                (hours * 3600).clamp(3600, WINDOW_S)
            }

            /// Runs of samples with no silence longer than [`GAP_S`]; each run
            /// is drawn as one line.
            pub fn runs(&self) -> Vec<&[Sample]> {
                let mut runs = Vec::new();
                let mut start = 0;
                for i in 1..=self.samples.len() {
                    if i == self.samples.len() || self.samples[i].at - self.samples[i - 1].at > GAP_S {
                        runs.push(&self.samples[start..i]);
                        start = i;
                    }
                }
                runs.retain(|run| !run.is_empty());
                runs
            }
        }

        /// `battery-history` beside `home.json`.
        pub fn path() -> Option<PathBuf> {
            crate::home_state::state_path().and_then(|p| p.parent().map(|dir| dir.join("battery-history")))
        }

        pub fn now_unix() -> i64 {
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs() as i64)
                .unwrap_or(0)
        }

        fn format_line(sample: &Sample) -> String {
            format!("{} {} {}\n", sample.at, sample.percent, if sample.charging { 'c' } else { 'd' })
        }

        /// Parses the file's lines, skipping any that do not parse, are dated
        /// after `now` (a clock step) or are older than [`KEEP_S`]; sorted by
        /// time.
        pub fn parse(raw: &str, now: i64) -> Vec<Sample> {
            let mut samples: Vec<Sample> = raw
                .lines()
                .filter_map(|line| {
                    let mut parts = line.split_whitespace();
                    let at = parts.next()?.parse::<i64>().ok()?;
                    let percent = parts.next()?.parse::<u8>().ok().filter(|p| *p <= 100)?;
                    let charging = match parts.next()? {
                        "c" => true,
                        "d" => false,
                        _ => return None,
                    };
                    parts.next().is_none().then_some(Sample { at, percent, charging })
                })
                .filter(|s| s.at <= now && now - s.at <= KEEP_S)
                .collect();
            samples.sort_by_key(|s| s.at);
            samples
        }

        #[derive(Debug, Default)]
        pub struct History {
            path: Option<PathBuf>,
            samples: Vec<Sample>,
            lines_in_file: usize,
        }

        impl History {
            /// Loads and prunes `path` (rewriting it when anything was
            /// dropped); a missing or unreadable file starts empty.
            pub fn load(path: Option<PathBuf>, now: i64) -> Self {
                let raw = path
                    .as_deref()
                    .filter(|p| std::fs::metadata(p).is_ok_and(|m| m.is_file() && m.len() <= MAX_FILE_BYTES))
                    .and_then(|p| std::fs::read_to_string(p).ok())
                    .unwrap_or_default();
                let lines = raw.lines().count();
                let mut history = History { path, samples: parse(&raw, now), lines_in_file: lines };
                if lines != history.samples.len() {
                    history.rewrite();
                }
                history
            }

            /// Adds a reading if a minute has passed since the last sample or
            /// the charging state changed. Returns whether it was recorded.
            pub fn record(&mut self, now: i64, percent: u8, charging: bool) -> bool {
                if let Some(last) = self.samples.last() {
                    let elapsed = now - last.at;
                    // A clock stepped backwards: drop what is now "future".
                    if elapsed < 0 {
                        self.samples.retain(|s| s.at <= now);
                        self.rewrite();
                    } else if elapsed < SAMPLE_EVERY_S && last.charging == charging {
                        return false;
                    }
                }
                let sample = Sample { at: now, percent: percent.min(100), charging };
                self.samples.push(sample);
                self.samples.retain(|s| now - s.at <= KEEP_S);
                if self.lines_in_file + 1 > 2 * (KEEP_S / SAMPLE_EVERY_S) as usize {
                    self.rewrite();
                } else {
                    self.append(&sample);
                }
                true
            }

            pub fn view(&self, now: i64) -> View {
                View { now, samples: self.samples.iter().copied().filter(|s| now - s.at <= WINDOW_S).collect() }
            }

            fn append(&mut self, sample: &Sample) {
                let Some(path) = self.path.as_deref() else { return };
                if let Some(parent) = path.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                let ok = std::fs::OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(path)
                    .and_then(|mut file| file.write_all(format_line(sample).as_bytes()))
                    .is_ok();
                if ok {
                    self.lines_in_file += 1;
                }
            }

            fn rewrite(&mut self) {
                let Some(path) = self.path.clone() else { return };
                if write_atomically(&path, &self.samples).is_ok() {
                    self.lines_in_file = self.samples.len();
                }
            }
        }

        fn write_atomically(path: &Path, samples: &[Sample]) -> std::io::Result<()> {
            let parent = path.parent().ok_or_else(|| std::io::Error::other("no parent directory"))?;
            std::fs::create_dir_all(parent)?;
            let temp = parent.join(format!(".battery-history.tmp.{}", std::process::id()));
            {
                let mut file = std::fs::File::create(&temp)?;
                for sample in samples {
                    file.write_all(format_line(sample).as_bytes())?;
                }
                file.sync_all()?;
            }
            std::fs::rename(&temp, path)
        }

        #[cfg(test)]
        mod tests {
            use super::*;

            fn temp_file(tag: &str) -> PathBuf {
                let dir = std::env::temp_dir().join(format!("k230-battery-history-{tag}-{}", std::process::id()));
                let _ = std::fs::remove_dir_all(&dir);
                dir.join("battery-history")
            }

            #[test]
            fn parse_skips_bad_future_and_stale_lines_and_sorts() {
                let now = 100_000;
                let raw = "99000 50 d\nnot a line\n98000 60 c\n100500 40 d\n1 90 d\n99500 101 d\n99600 55 x\n99700 55 d extra\n";
                let samples = parse(raw, now);
                assert_eq!(
                    samples,
                    vec![
                        Sample { at: 98000, percent: 60, charging: true },
                        Sample { at: 99000, percent: 50, charging: false },
                    ]
                );
            }

            #[test]
            fn records_once_a_minute_or_on_a_charging_change_and_survives_a_reload() {
                let path = temp_file("record");
                let mut history = History::load(Some(path.clone()), 1000);
                assert!(history.record(1000, 80, false));
                assert!(!history.record(1030, 80, false), "under a minute, same state");
                assert!(history.record(1040, 80, true), "charging change records at once");
                assert!(history.record(1100, 81, true));
                let reloaded = History::load(Some(path.clone()), 1200);
                assert_eq!(reloaded.view(1200).samples.len(), 3);
                assert_eq!(reloaded.view(1200).samples[2], Sample { at: 1100, percent: 81, charging: true });
                std::fs::remove_dir_all(path.parent().unwrap()).unwrap();
            }

            #[test]
            fn load_prunes_the_file_to_the_last_day() {
                let path = temp_file("prune");
                std::fs::create_dir_all(path.parent().unwrap()).unwrap();
                let now = 10 * KEEP_S;
                std::fs::write(&path, format!("{} 10 d\ngarbage\n{} 20 d\n", now - KEEP_S - 1, now - 10)).unwrap();
                let history = History::load(Some(path.clone()), now);
                assert_eq!(history.view(now).samples.len(), 1);
                assert_eq!(std::fs::read_to_string(&path).unwrap(), format!("{} 20 d\n", now - 10));
                std::fs::remove_dir_all(path.parent().unwrap()).unwrap();
            }

            #[test]
            fn the_file_is_rewritten_once_it_reaches_twice_its_budget() {
                let path = temp_file("cap");
                let mut history = History::load(Some(path.clone()), 0);
                let budget = (KEEP_S / SAMPLE_EVERY_S) as i64;
                for i in 0..(3 * budget) {
                    assert!(history.record(i * SAMPLE_EVERY_S, 50, false));
                }
                let lines = std::fs::read_to_string(&path).unwrap().lines().count() as i64;
                assert!(lines <= 2 * budget, "{lines} lines");
                std::fs::remove_dir_all(path.parent().unwrap()).unwrap();
            }

            #[test]
            fn a_clock_stepped_backwards_drops_future_samples() {
                let mut history = History::load(None, 0);
                assert!(history.record(5000, 50, false));
                assert!(history.record(5060, 49, false));
                assert!(history.record(2000, 48, false));
                assert_eq!(history.view(2000).samples, vec![Sample { at: 2000, percent: 48, charging: false }]);
            }

            #[test]
            fn the_view_is_the_last_twelve_hours_split_at_gaps() {
                let mut history = History::load(None, 0);
                let start = 100_000;
                for i in 0..5 {
                    history.record(start + i * 60, 90 - i as u8, false);
                }
                // The shell was off for ten minutes.
                for i in 0..3 {
                    history.record(start + 900 + i * 60, 70 + i as u8, true);
                }
                let view = history.view(start + 1200);
                let runs = view.runs();
                assert_eq!(runs.len(), 2);
                assert_eq!(runs[0].len(), 5);
                assert_eq!(runs[1].len(), 3);
                assert!(history.view(start + WINDOW_S + 2000).samples.is_empty());
            }

            #[test]
            fn the_span_fits_the_history_in_whole_hours_between_one_and_twelve() {
                let view = |first_ago: Option<i64>| View {
                    now: 100_000,
                    samples: first_ago.map(|ago| Sample { at: 100_000 - ago, percent: 50, charging: false }).into_iter().collect(),
                };
                assert_eq!(view(None).span_s(), 3600);
                assert_eq!(view(Some(900)).span_s(), 3600);
                assert_eq!(view(Some(3601)).span_s(), 7200);
                assert_eq!(view(Some(5 * 3600)).span_s(), 5 * 3600);
                assert_eq!(view(Some(WINDOW_S)).span_s(), WINDOW_S);
            }
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

    /// Home displays Fahrenheit while source and cached snapshots retain Celsius.
    pub fn fahrenheit_label(celsius: i32) -> String {
        let fahrenheit = (f64::from(celsius) * 9.0 / 5.0 + 32.0).round();
        format!("{fahrenheit:.0}°F")
    }

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

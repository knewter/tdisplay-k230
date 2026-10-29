//! Settings' About and Date & time pages: read-only device, build and clock
//! identity, independent of Wayland rendering.
//!
//! Every value is read from the running system with no helper process and no
//! D-Bus call: the hostname, the system generation link, the kernel release,
//! uptime and `statvfs` for About; the C library's local time, the
//! `/etc/localtime` link and systemd-timesyncd's `synchronized` stamp for
//! Date & time. Nothing network- or identity-bearing is read: no addresses,
//! MACs, SSIDs, serial numbers or tokens. The one setting either page changes
//! is Date & time's clock format, a shell preference
//! (`shell_prefs::CLOCK_FORMAT_FILE`); zone and network time stay read-only.
use std::path::{Path, PathBuf};

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum Page {
    #[default]
    Closed,
    About,
    DateTime,
}

impl Page {
    pub fn title(self) -> &'static str {
        match self {
            Page::Closed => "",
            Page::About => "About",
            Page::DateTime => "Date & time",
        }
    }
}

/// What the renderer needs: a page and label/value rows, nothing else.
#[derive(Clone, Debug, PartialEq)]
pub struct InfoPublic {
    pub page: Page,
    pub rows: Vec<(&'static str, String)>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Intent {
    Back,
    /// Flip the clock between 24-hour and 12-hour (Date & time only).
    ToggleClockFormat,
}

/// The Date & time row that is also a switch; it is always the page's last
/// row, so its tap region can grow downward to the touch floor.
pub const CLOCK_FORMAT_LABEL: &str = "Clock format";

/// Where the readers look, so host tests can point them at a fixture tree.
#[derive(Clone, Debug)]
pub struct Sources {
    pub root: PathBuf,
    /// The running shell binary, whose store path names the shell build.
    pub exe: Option<PathBuf>,
}

impl Sources {
    pub fn system() -> Self {
        Self { root: PathBuf::from("/"), exe: std::env::current_exe().ok() }
    }
    fn path(&self, absolute: &str) -> PathBuf {
        self.root.join(absolute.trim_start_matches('/'))
    }
    fn read(&self, absolute: &str) -> Option<String> {
        std::fs::read_to_string(self.path(absolute))
            .ok()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
    }
}

#[derive(Debug, Default)]
pub struct InfoView {
    pub page: Page,
    rows: Vec<(&'static str, String)>,
}

impl InfoView {
    pub fn open(&mut self, page: Page, sources: &Sources) {
        self.page = page;
        self.rows.clear();
        self.refresh(sources);
    }

    pub fn close(&mut self) {
        self.page = Page::Closed;
        self.rows.clear();
    }

    /// Re-reads the page's rows; true when any changed.
    pub fn refresh(&mut self, sources: &Sources) -> bool {
        let rows = match self.page {
            Page::Closed => return false,
            Page::About => about_rows(sources),
            Page::DateTime => date_time_rows(sources),
        };
        let changed = rows != self.rows;
        self.rows = rows;
        changed
    }

    pub fn public(&self) -> Option<InfoPublic> {
        (self.page != Page::Closed).then(|| InfoPublic { page: self.page, rows: self.rows.clone() })
    }
}

const UNAVAILABLE: &str = "Unavailable";

/// The short hash and name of a Nix store path's last component:
/// `/nix/store/<32 chars>-nixos-system-k230-26.05` becomes
/// `("<first 8 chars>", "nixos-system-k230-26.05")`.
pub fn store_identity(path: &Path) -> Option<(String, String)> {
    let leaf = path.file_name()?.to_str()?;
    let (hash, name) = leaf.split_once('-')?;
    (hash.len() == 32 && hash.bytes().all(|b| b.is_ascii_alphanumeric()) && !name.is_empty())
        .then(|| (hash[..8].to_string(), name.to_string()))
}

fn store_line(path: Option<PathBuf>) -> String {
    path.and_then(|p| store_identity(&p))
        .map_or_else(|| UNAVAILABLE.to_string(), |(hash, name)| format!("{hash} \u{b7} {name}"))
}

/// `3 d 4 h`, `4 h 12 min`, `12 min`: the two largest units.
pub fn format_uptime(seconds: u64) -> String {
    let (d, h, m) = (seconds / 86_400, seconds % 86_400 / 3_600, seconds % 3_600 / 60);
    match (d, h, m) {
        (0, 0, m) => format!("{m} min"),
        (0, h, m) => format!("{h} h {m} min"),
        (d, h, _) => format!("{d} d {h} h"),
    }
}

/// `1.4 GB`, `812 MB`: decimal units, one decimal at GB and above.
pub fn format_bytes(bytes: u64) -> String {
    const MB: f64 = 1_000_000.0;
    let b = bytes as f64;
    if b >= 1000.0 * MB {
        format!("{:.1} GB", b / (1000.0 * MB))
    } else {
        format!("{:.0} MB", b / MB)
    }
}

/// Free and total bytes of the filesystem holding `path`.
fn storage(path: &Path) -> Option<(u64, u64)> {
    use std::os::unix::ffi::OsStrExt;
    let c = std::ffi::CString::new(path.as_os_str().as_bytes()).ok()?;
    let mut stat: libc::statvfs = unsafe { std::mem::zeroed() };
    (unsafe { libc::statvfs(c.as_ptr(), &mut stat) } == 0).then(|| {
        (stat.f_bavail as u64 * stat.f_frsize as u64, stat.f_blocks as u64 * stat.f_frsize as u64)
    })
}

pub fn about_rows(src: &Sources) -> Vec<(&'static str, String)> {
    let device = src.read("/etc/hostname").unwrap_or_else(|| UNAVAILABLE.into());
    let system = store_line(std::fs::read_link(src.path("/run/current-system")).ok());
    let kernel = src.read("/proc/sys/kernel/osrelease").unwrap_or_else(|| UNAVAILABLE.into());
    let uptime = src
        .read("/proc/uptime")
        .and_then(|s| s.split_whitespace().next()?.parse::<f64>().ok())
        .map_or_else(|| UNAVAILABLE.into(), |s| format_uptime(s as u64));
    let free = storage(&src.path("/")).map_or_else(
        || UNAVAILABLE.into(),
        |(free, total)| format!("{} free of {}", format_bytes(free), format_bytes(total)),
    );
    let build = src
        .exe
        .as_ref()
        .and_then(|exe| exe.ancestors().find(|a| a.parent() == Some(Path::new("/nix/store"))))
        .and_then(store_identity);
    let shell = match build {
        Some((hash, _)) => format!("{} \u{b7} {hash}", env!("CARGO_PKG_VERSION")),
        None => format!("{} (no store path)", env!("CARGO_PKG_VERSION")),
    };
    vec![
        ("Device", device),
        ("System", system),
        ("Kernel", kernel),
        ("Uptime", uptime),
        ("Storage", free),
        ("Shell", shell),
    ]
}

/// A broken-down local time plus the zone's offset, from the C library.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Clock {
    pub year: i32,
    pub month: i32,
    pub day: i32,
    pub weekday: i32,
    pub hour: i32,
    pub minute: i32,
    pub second: i32,
    pub utc_offset_min: i32,
}

pub fn now_clock() -> Option<Clock> {
    let now = unsafe { libc::time(std::ptr::null_mut()) };
    let mut tm: libc::tm = unsafe { std::mem::zeroed() };
    if unsafe { libc::localtime_r(&now, &mut tm) }.is_null() {
        return None;
    }
    Some(Clock {
        year: tm.tm_year + 1900,
        month: tm.tm_mon + 1,
        day: tm.tm_mday,
        weekday: tm.tm_wday,
        hour: tm.tm_hour,
        minute: tm.tm_min,
        second: tm.tm_sec,
        utc_offset_min: (tm.tm_gmtoff / 60) as i32,
    })
}

const WEEKDAYS: [&str; 7] = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS: [&str; 12] = [
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December",
];

pub fn format_date(c: &Clock) -> String {
    format!(
        "{}, {} {} {}",
        WEEKDAYS[c.weekday.rem_euclid(7) as usize],
        MONTHS[(c.month - 1).rem_euclid(12) as usize],
        c.day,
        c.year
    )
}

/// `21:05:03`, or `9:05:03 PM` on a 12-hour clock.
pub fn format_time(c: &Clock, twelve: bool) -> String {
    use crate::home_widgets::clock::{hour_text, meridiem};
    let hms = format!("{}:{:02}:{:02}", hour_text(c.hour, twelve), c.minute, c.second);
    if twelve { format!("{hms} {}", meridiem(c.hour)) } else { hms }
}

/// The clock format as the preference file under `src` says.
pub fn twelve_hour(src: &Sources) -> bool {
    crate::shell_prefs::read_twelve_hour(
        &src.path(crate::shell_prefs::PREFERENCE_DIR).join(crate::shell_prefs::CLOCK_FORMAT_FILE),
    )
}

/// `UTC-05:00`, `UTC+00:00`.
pub fn format_offset(minutes: i32) -> String {
    let sign = if minutes < 0 { '-' } else { '+' };
    format!("UTC{sign}{:02}:{:02}", minutes.abs() / 60, minutes.abs() % 60)
}

/// The zone name from the `/etc/localtime` link target
/// (`.../zoneinfo/America/Chicago` is `America/Chicago`).
pub fn zone_name(target: &Path) -> Option<String> {
    let text = target.to_str()?;
    let (_, zone) = text.rsplit_once("zoneinfo/")?;
    (!zone.is_empty()).then(|| zone.to_string())
}

pub fn date_time_rows(src: &Sources) -> Vec<(&'static str, String)> {
    let clock = now_clock();
    let twelve = twelve_hour(src);
    let zone = std::fs::read_link(src.path("/etc/localtime")).ok().and_then(|t| zone_name(&t));
    let zone_line = match (zone, clock) {
        (Some(z), Some(c)) => format!("{z} ({})", format_offset(c.utc_offset_min)),
        (Some(z), None) => z,
        (None, Some(c)) => format_offset(c.utc_offset_min),
        (None, None) => UNAVAILABLE.into(),
    };
    // systemd-timesyncd creates this stamp once it has set the clock from a
    // server; time-sync.target waits on it. UNVERIFIED on the board.
    let synced = if src.path("/run/systemd/timesync/synchronized").exists() {
        "Synchronized"
    } else {
        "Not synchronized"
    };
    vec![
        ("Date", clock.as_ref().map_or_else(|| UNAVAILABLE.into(), format_date)),
        ("Time", clock.as_ref().map_or_else(|| UNAVAILABLE.into(), |c| format_time(c, twelve))),
        ("Time zone", zone_line),
        ("Network time", synced.into()),
        (CLOCK_FORMAT_LABEL, if twelve { "12-hour" } else { "24-hour" }.into()),
    ]
}

// ---- layout -------------------------------------------------------------

/// `(x, y, width, height)`.
pub type Rect = (f64, f64, f64, f64);

fn line(px: f64) -> f64 {
    (px * 1.25).ceil()
}

/// The shell's touch floor for a tap target, in layout units.
pub const TOUCH_FLOOR: f64 = 99.0;

/// Every rect both painted and hit-tested. Portrait is the 568x1232 artwork
/// scaled to the surface, one column; landscape is real pixels, three
/// columns filled top to bottom, so the largest text step still fits 568 px.
#[derive(Clone, Debug)]
pub struct Layout {
    pub wide: bool,
    pub back_text: (f64, f64, f64, f64),
    pub title: (f64, f64, f64, f64),
    /// Tap region of the back link: `x < .0 && y < .1`.
    pub back_hit: (f64, f64),
    /// One card per row.
    pub cards: Vec<Rect>,
    /// Offsets from a card's top to its label and value lines.
    pub label_dy: f64,
    pub value_dy: f64,
    pub bottom: f64,
}

pub fn layout_scale(width: u32, height: u32) -> (f64, f64) {
    crate::modem_ui::layout_scale(width, height)
}

pub fn layout_for(width: u32, height: u32, rows: usize) -> Layout {
    if crate::modem_ui::wide(width, height) {
        // Two columns give values like "14.2 GB free of 29.8 GB" and a long
        // time zone room to read whole; three only when two would overflow
        // the panel at a large text step.
        let two = build(f64::from(width), true, rows, 2);
        if two.bottom <= f64::from(height) - 12.0 { two } else { build(f64::from(width), true, rows, 3) }
    } else {
        build(568.0, false, rows, 1)
    }
}

fn build(w: f64, wide: bool, rows: usize, columns: usize) -> Layout {
    let s = crate::layout_text_scale().max(1.0) * crate::layout_theme_font();
    let (label, caption, body) = (
        crate::render::TYPE_LABEL * s,
        crate::render::TYPE_CAPTION * s,
        crate::render::TYPE_BODY * s,
    );
    // The wide header, and the portrait one at a larger text step, is the
    // compact form: the title directly under a high Back link.
    let compact = wide || s >= 1.5;
    let top_y = if compact { 14.0 } else { 45.0 };
    let title_y = top_y + line(label) + if compact { 2.0 } else { 16.0 };
    let title_size = if compact { crate::render::TYPE_BODY } else { crate::render::TYPE_TITLE };
    let title_h = if compact { line(body) } else { line(crate::render::TYPE_TITLE * s) };
    let back_w = crate::render::measured_text_width("\u{2039} Settings", label, pango::Weight::Normal) + 8.0;
    let content = title_y + title_h + if compact { 6.0 } else { 14.0 };
    let (pad, gap) = (10.0, 10.0);
    let card_h = 2.0 * pad + line(caption) + 2.0 + line(body);
    let per_column = rows.div_ceil(columns).max(1);
    let col_w = (w - 48.0 - gap * (columns as f64 - 1.0)) / columns as f64;
    let cards: Vec<Rect> = (0..rows)
        .map(|i| {
            let (col, row) = (i / per_column, i % per_column);
            (24.0 + col as f64 * (col_w + gap), content + row as f64 * (card_h + gap), col_w, card_h)
        })
        .collect();
    let bottom = content + per_column as f64 * (card_h + gap) - gap;
    Layout {
        wide,
        back_text: (28.0, top_y, back_w, crate::render::TYPE_LABEL),
        title: (28.0, title_y, w - 56.0, title_size),
        back_hit: ((back_w + 48.0).max(200.0), (title_y + 8.0).max(TOUCH_FLOOR)),
        cards,
        label_dy: pad,
        value_dy: pad + line(caption) + 2.0,
        bottom,
    }
}

/// The clock-format switch on Date & time: the pill drawn at the right of
/// the last card, and the tap region, which is that card grown downward to
/// the touch floor (nothing lies below the last card in its column).
pub fn clock_format_switch(public: &InfoPublic, lay: &Layout) -> Option<(Rect, Rect)> {
    if public.page != Page::DateTime || public.rows.last().map(|r| r.0) != Some(CLOCK_FORMAT_LABEL) {
        return None;
    }
    let &(x, y, w, h) = lay.cards.last()?;
    let (pw, ph) = (76.0, 44.0);
    let pill = (x + w - 18.0 - pw, y + (h - ph) / 2.0, pw, ph);
    Some((pill, (x, y, w, h.max(TOUCH_FLOOR))))
}

fn target(lay: &Layout, switch: Option<Rect>, x: f64, y: f64) -> Option<Intent> {
    if x < lay.back_hit.0 && y < lay.back_hit.1 {
        return Some(Intent::Back);
    }
    let (sx, sy, sw, sh) = switch?;
    (x >= sx && x < sx + sw && y >= sy && y < sy + sh).then_some(Intent::ToggleClockFormat)
}

/// A tap that went down and came up on Back, or on the clock-format switch.
pub fn hit(
    public: &InfoPublic,
    start: (f64, f64),
    end: (f64, f64),
    width: u32,
    height: u32,
) -> Option<Intent> {
    if width == 0 || height == 0 || public.page == Page::Closed {
        return None;
    }
    let lay = layout_for(width, height, public.rows.len());
    let (sx, sy) = layout_scale(width, height);
    let (start, end) = ((start.0 * sx, start.1 * sy), (end.0 * sx, end.1 * sy));
    if (end.0 - start.0).abs() > 18.0 || (end.1 - start.1).abs() > 18.0 {
        return None;
    }
    let switch = clock_format_switch(public, &lay).map(|(_, hit)| hit);
    let down = target(&lay, switch, start.0, start.1);
    let up = target(&lay, switch, end.0, end.1);
    (down == up).then_some(up).flatten()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn fixture() -> (PathBuf, Sources) {
        let root = std::env::temp_dir()
            .join(format!("k230-device-info-{}-{:?}", std::process::id(), std::thread::current().id()));
        let _ = fs::remove_dir_all(&root);
        for dir in ["etc", "run/systemd/timesync", "proc/sys/kernel"] {
            fs::create_dir_all(root.join(dir)).unwrap();
        }
        fs::write(root.join("etc/hostname"), "k230\n").unwrap();
        fs::write(root.join("proc/sys/kernel/osrelease"), "7.0.0-k230\n").unwrap();
        fs::write(root.join("proc/uptime"), "93784.51 1000.00\n").unwrap();
        std::os::unix::fs::symlink(
            "/nix/store/abcdefgh0123456789abcdefgh012345-nixos-system-k230-26.05",
            root.join("run/current-system"),
        )
        .unwrap();
        std::os::unix::fs::symlink("/etc/zoneinfo/America/Chicago", root.join("etc/localtime")).unwrap();
        let sources = Sources {
            root: root.clone(),
            exe: Some(PathBuf::from(
                "/nix/store/zyxwvuts0123456789zyxwvuts012345-k230-shell-0.1.0/bin/k230-shell",
            )),
        };
        (root, sources)
    }

    #[test]
    fn about_reads_identity() {
        let (root, src) = fixture();
        let rows = about_rows(&src);
        let get = |l: &str| rows.iter().find(|r| r.0 == l).unwrap().1.clone();
        assert_eq!(get("Device"), "k230");
        assert_eq!(get("System"), "abcdefgh \u{b7} nixos-system-k230-26.05");
        assert_eq!(get("Kernel"), "7.0.0-k230");
        assert_eq!(get("Uptime"), "1 d 2 h");
        assert!(get("Storage").contains("free of"), "{}", get("Storage"));
        assert_eq!(get("Shell"), "0.1.0 \u{b7} zyxwvuts");
        let labels: Vec<_> = rows.iter().map(|r| r.0).collect();
        assert_eq!(labels, ["Device", "System", "Kernel", "Uptime", "Storage", "Shell"]);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn unreadable_sources_say_unavailable() {
        let src = Sources { root: PathBuf::from("/nonexistent-k230-root"), exe: None };
        let rows = about_rows(&src);
        assert_eq!(rows[0].1, UNAVAILABLE);
        assert_eq!(rows[1].1, UNAVAILABLE);
        assert_eq!(rows[2].1, UNAVAILABLE);
        assert!(rows[5].1.ends_with("(no store path)"));
    }

    #[test]
    fn date_time_reports_zone_and_sync_state() {
        let (root, src) = fixture();
        let rows = date_time_rows(&src);
        let get = |l: &str| rows.iter().find(|r| r.0 == l).unwrap().1.clone();
        assert!(get("Time zone").starts_with("America/Chicago (UTC"), "{}", get("Time zone"));
        assert_eq!(get("Network time"), "Not synchronized");
        assert_eq!(get("Clock format"), "24-hour");
        assert!(!get("Time").ends_with('M'), "{}", get("Time"));
        fs::write(root.join("run/systemd/timesync/synchronized"), "").unwrap();
        assert_eq!(date_time_rows(&src)[3].1, "Synchronized");
        fs::create_dir_all(root.join("var/lib/k230-shell-prefs")).unwrap();
        fs::write(root.join("var/lib/k230-shell-prefs/clock-format"), "12-hour\n").unwrap();
        let rows = date_time_rows(&src);
        assert_eq!(rows.last().unwrap(), &(CLOCK_FORMAT_LABEL, "12-hour".to_string()));
        let time = &rows[1].1;
        assert!(time.ends_with(" AM") || time.ends_with(" PM"), "{time}");
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn formatting_helpers() {
        assert_eq!(format_uptime(59), "0 min");
        assert_eq!(format_uptime(4_320), "1 h 12 min");
        assert_eq!(format_offset(-300), "UTC-05:00");
        assert_eq!(format_offset(330), "UTC+05:30");
        assert_eq!(zone_name(Path::new("/etc/zoneinfo/Europe/Paris")).as_deref(), Some("Europe/Paris"));
        assert_eq!(zone_name(Path::new("/etc/localtime-x")), None);
        let c = Clock { year: 2026, month: 10, day: 26, weekday: 1, hour: 9, minute: 5, second: 3, utc_offset_min: -300 };
        assert_eq!(format_date(&c), "Monday, October 26 2026");
        assert_eq!(format_time(&c, false), "09:05:03");
        assert_eq!(format_time(&c, true), "9:05:03 AM");
        let evening = Clock { hour: 21, ..c };
        assert_eq!(format_time(&evening, true), "9:05:03 PM");
        assert_eq!(format_time(&Clock { hour: 0, ..c }, true), "12:05:03 AM");
        assert_eq!(format_bytes(1_460_000_000), "1.5 GB");
        assert_eq!(format_bytes(812_000_000), "812 MB");
    }

    #[test]
    fn labels_carry_no_network_or_serial_identity() {
        let (root, src) = fixture();
        for (label, _) in about_rows(&src).into_iter().chain(date_time_rows(&src)) {
            let l = label.to_lowercase();
            for word in ["ip", "mac", "ssid", "serial", "address", "imei", "token"] {
                assert!(!l.split_whitespace().any(|w| w == word), "{label}");
            }
        }
        let _ = fs::remove_dir_all(root);
    }

    fn public(page: Page, n: usize) -> InfoPublic {
        InfoPublic { page, rows: (0..n).map(|_| ("Label", "Value".to_string())).collect() }
    }

    #[test]
    fn back_is_the_only_target_and_meets_the_touch_floor() {
        for (w, h) in [(568u32, 1232u32), (1232, 568)] {
            let p = public(Page::About, 6);
            let (sx, sy) = layout_scale(w, h);
            let inside = (40.0 / sx, 98.0 / sy);
            assert_eq!(hit(&p, inside, inside, w, h), Some(Intent::Back), "{w}x{h}");
            let below = (40.0 / sx, 400.0 / sy);
            assert_eq!(hit(&p, below, below, w, h), None, "rows are not targets");
            assert_eq!(hit(&public(Page::Closed, 0), inside, inside, w, h), None);
            assert_eq!(hit(&p, inside, (40.0 / sx, 130.0 / sy), w, h), None);
        }
    }

    #[test]
    fn the_clock_format_switch_is_a_floor_sized_target_on_date_and_time_only() {
        for step in [1.0, 2.0] {
            crate::set_layout_text_scale(step);
            for (w, h) in [(568u32, 1232u32), (1232, 568)] {
                let mut p = public(Page::DateTime, 5);
                p.rows[4].0 = CLOCK_FORMAT_LABEL;
                let lay = layout_for(w, h, 5);
                let (pill, hit_rect) = clock_format_switch(&p, &lay).expect("switch");
                assert!(hit_rect.3 >= TOUCH_FLOOR, "{w}x{h} step {step}");
                let card = *lay.cards.last().unwrap();
                assert!(pill.0 >= card.0 && pill.0 + pill.2 <= card.0 + card.2);
                let (sx, sy) = layout_scale(w, h);
                let centre = ((pill.0 + pill.2 / 2.0) / sx, (pill.1 + pill.3 / 2.0) / sy);
                assert_eq!(hit(&p, centre, centre, w, h), Some(Intent::ToggleClockFormat), "{w}x{h}");
                let low = ((card.0 + 20.0) / sx, (card.1 + TOUCH_FLOOR - 2.0) / sy);
                assert_eq!(hit(&p, low, low, w, h), Some(Intent::ToggleClockFormat), "floor {w}x{h}");
                let other = lay.cards[0];
                let other = ((other.0 + 20.0) / sx, (other.1 + 20.0) / sy);
                assert_eq!(hit(&p, other, other, w, h), None, "other rows are not targets");
                let mut about = p.clone();
                about.page = Page::About;
                assert!(clock_format_switch(&about, &lay).is_none());
            }
        }
        crate::set_layout_text_scale(1.0);
    }

    #[test]
    fn layout_fits_the_panel_at_every_text_step() {
        for step in [1.0, 1.25, 1.5, 1.75, 2.0] {
            crate::set_layout_text_scale(step);
            for (w, h, rows) in [(568u32, 1232.0, 6usize), (568, 1232.0, 5), (1232, 568.0, 6), (1232, 568.0, 5)] {
                let lay = layout_for(w, h as u32, rows);
                assert_eq!(lay.cards.len(), rows);
                assert!(lay.bottom <= h, "step {step} {w}x{h} rows {rows}: bottom {} > {h}", lay.bottom);
                for card in &lay.cards {
                    assert!(card.0 >= 0.0 && card.0 + card.2 <= f64::from(w), "card inside width");
                }
                assert!(lay.back_hit.1 >= TOUCH_FLOOR);
            }
        }
        crate::set_layout_text_scale(1.0);
    }
}

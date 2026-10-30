//! Settings' About and Date & time pages, and Date & time's time zone
//! chooser, independent of Wayland rendering.
//!
//! Every value is read from the running system with no helper process and no
//! D-Bus call: the hostname, the system generation link, the kernel release,
//! uptime and `statvfs` for About; the C library's local time, the
//! `/etc/localtime` link and systemd-timesyncd's `synchronized` stamp for
//! Date & time; tzdata's `zone1970.tab` for the chooser. Nothing network- or
//! identity-bearing is read: no addresses, MACs, SSIDs, serial numbers or
//! tokens. Date & time changes three settings: the clock format, a shell
//! preference (`shell_prefs::CLOCK_FORMAT_FILE`), and the zone and network
//! time, which only the root helper behind `/run/k230-time.sock` applies
//! (`tools/k230_time_helper.py`); this module only names what to ask for.
use std::borrow::Cow;
use std::path::{Path, PathBuf};

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum Page {
    #[default]
    Closed,
    About,
    DateTime,
    /// The time zone chooser's first step: tzdata's areas, then UTC.
    Regions,
    /// The zones of one area.
    Zones,
}

impl Page {
    pub fn title(self) -> &'static str {
        match self {
            Page::Closed => "",
            Page::About => "About",
            Page::DateTime => "Date & time",
            Page::Regions | Page::Zones => "Time zone",
        }
    }

    /// Where Back goes, as the link names it.
    pub fn back_label(self) -> &'static str {
        match self {
            Page::Regions => "\u{2039} Date & time",
            Page::Zones => "\u{2039} Time zone",
            _ => "\u{2039} Settings",
        }
    }

    /// The chooser pages page their rows when they do not fit the panel.
    pub fn paged(self) -> bool {
        matches!(self, Page::Regions | Page::Zones)
    }
}

/// A card's caption and value. Captions are fixed words except on the
/// chooser, where they are zone names.
pub type Row = (Cow<'static, str>, String);

/// What the renderer needs: a page and label/value rows, nothing else.
#[derive(Clone, Debug, PartialEq)]
pub struct InfoPublic {
    pub page: Page,
    pub rows: Vec<Row>,
    /// The chooser area whose zones `Page::Zones` lists.
    pub region: Option<String>,
    /// Which page of a paged chooser is shown (`window` clamps it).
    pub page_index: usize,
}

impl InfoPublic {
    /// A page of fixed-caption rows, first page shown.
    pub fn new(page: Page, rows: Vec<(&'static str, String)>) -> Self {
        Self { page, rows: borrowed(rows), region: None, page_index: 0 }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Intent {
    Back,
    /// Flip the clock between 24-hour and 12-hour (Date & time only).
    ToggleClockFormat,
    /// Turn network time on or off (Date & time only).
    ToggleNetworkTime,
    /// Open the time zone chooser (Date & time's zone row).
    OpenZones,
    /// The chooser row at this index of `InfoPublic::rows`.
    Choose(usize),
    /// The chooser's pager: false is Previous, true is Next.
    Turn(bool),
}

/// Date & time's switch rows and its link to the chooser. Every card on
/// Date & time and the chooser is at least `TOUCH_FLOOR` tall, so a whole
/// card is the tap region.
pub const CLOCK_FORMAT_LABEL: &str = "Clock format";
pub const NETWORK_TIME_LABEL: &str = "Network time";
pub const TIME_ZONE_LABEL: &str = "Time zone \u{203a}";
/// The flag the root helper writes while network time is off; timesyncd's
/// unit is conditioned on it (`nix/time-settings.nix`).
pub const NETWORK_TIME_OFF: &str = "/var/lib/k230-time/network-time-off";
pub const NETWORK_TIME_OFF_VALUE: &str = "Off";
/// The value of the chooser's UTC row, which applies directly.
pub const UTC: &str = "UTC";

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
    rows: Vec<Row>,
    region: Option<String>,
    page_index: usize,
    /// tzdata's zone names, read when the chooser opens.
    zones: Vec<String>,
}

impl InfoView {
    pub fn open(&mut self, page: Page, sources: &Sources) {
        if page.paged() && self.zones.is_empty() {
            self.zones = zone_table(sources);
        }
        self.page = page;
        self.page_index = 0;
        self.rows.clear();
        self.refresh(sources);
    }

    pub fn close(&mut self) {
        *self = Self::default();
    }

    /// Back one level: a zone list returns to the areas, the areas to Date &
    /// time, and About or Date & time closes. True when the page closed.
    pub fn back(&mut self, sources: &Sources) -> bool {
        match self.page {
            Page::Zones => self.open(Page::Regions, sources),
            Page::Regions => self.open(Page::DateTime, sources),
            _ => {
                self.close();
                return true;
            }
        }
        false
    }

    /// A tap on chooser row `index`: an area opens its zones; a zone (or
    /// UTC) is returned for the caller to apply, and Date & time reopens.
    pub fn choose(&mut self, index: usize, sources: &Sources) -> Option<String> {
        let (caption, value) = self.rows.get(index)?.clone();
        match self.page {
            Page::Regions if value != UTC => {
                self.region = Some(value);
                self.open(Page::Zones, sources);
                None
            }
            Page::Regions | Page::Zones => {
                let zone = if self.page == Page::Regions { value } else { caption.into_owned() };
                self.open(Page::DateTime, sources);
                Some(zone)
            }
            _ => None,
        }
    }

    /// Previous or Next on a paged chooser with `pages` pages.
    pub fn turn(&mut self, next: bool, pages: usize) {
        let last = pages.saturating_sub(1);
        self.page_index = if next { (self.page_index + 1).min(last) } else { self.page_index.saturating_sub(1) };
    }

    /// Re-reads the page's rows; true when any changed.
    pub fn refresh(&mut self, sources: &Sources) -> bool {
        let rows: Vec<Row> = match self.page {
            Page::Closed => return false,
            Page::About => borrowed(about_rows(sources)),
            Page::DateTime => borrowed(date_time_rows(sources)),
            Page::Regions => region_rows(&self.zones),
            Page::Zones => zone_rows(&self.zones, self.region.as_deref().unwrap_or("")),
        };
        let changed = rows != self.rows;
        self.rows = rows;
        changed
    }

    pub fn public(&self) -> Option<InfoPublic> {
        (self.page != Page::Closed).then(|| InfoPublic {
            page: self.page,
            rows: self.rows.clone(),
            region: self.region.clone(),
            page_index: self.page_index,
        })
    }
}

fn borrowed(rows: Vec<(&'static str, String)>) -> Vec<Row> {
    rows.into_iter().map(|(label, value)| (Cow::Borrowed(label), value)).collect()
}

/// Canonical zone names from tzdata's `zone1970.tab`, sorted; the root
/// helper accepts exactly these and UTC.
pub fn zone_table(src: &Sources) -> Vec<String> {
    let text = std::fs::read_to_string(src.path("/etc/zoneinfo/zone1970.tab")).unwrap_or_default();
    let mut zones: Vec<String> = text
        .lines()
        .filter(|line| !line.starts_with('#'))
        .filter_map(|line| line.split('\t').nth(2))
        .map(|zone| zone.trim().to_string())
        .filter(|zone| zone.contains('/'))
        .collect();
    zones.sort();
    zones.dedup();
    zones
}

/// The chooser's first page: each area with its zone count, then UTC.
pub fn region_rows(zones: &[String]) -> Vec<Row> {
    let mut rows: Vec<Row> = Vec::new();
    for zone in zones {
        let area = zone.split('/').next().unwrap_or_default();
        match rows.last_mut() {
            Some((count, value)) if value == area => {
                let n = count.split(' ').next().and_then(|n| n.parse::<usize>().ok()).unwrap_or(0) + 1;
                *count = Cow::Owned(format!("{n} zones"));
            }
            _ => rows.push((Cow::Borrowed("1 zone"), area.to_string())),
        }
    }
    rows.push((Cow::Borrowed("Coordinated Universal Time"), UTC.to_string()));
    rows
}

/// One area's zones: the full name as the caption, the place as the value.
pub fn zone_rows(zones: &[String], area: &str) -> Vec<Row> {
    zones
        .iter()
        .filter(|zone| zone.split('/').next() == Some(area))
        .map(|zone| (Cow::Owned(zone.clone()), place_name(zone)))
        .collect()
}

/// `America/Argentina/Buenos_Aires` reads `Buenos Aires, Argentina`.
pub fn place_name(zone: &str) -> String {
    let parts: Vec<String> = zone.split('/').skip(1).map(|p| p.replace('_', " ")).collect();
    match parts.as_slice() {
        [place] => place.clone(),
        [sub, place] => format!("{place}, {sub}"),
        _ => zone.replace('_', " "),
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
    // Re-read /etc/localtime: Settings changes the zone while the shell runs.
    crate::home_widgets::clock::reread_zone();
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
    // server; time-sync.target waits on it.
    // Network time switched off outranks a stale stamp from before.
    let synced = if src.path(NETWORK_TIME_OFF).exists() {
        NETWORK_TIME_OFF_VALUE
    } else if src.path("/run/systemd/timesync/synchronized").exists() {
        "Synchronized"
    } else {
        "Not synchronized"
    };
    vec![
        ("Date", clock.as_ref().map_or_else(|| UNAVAILABLE.into(), format_date)),
        ("Time", clock.as_ref().map_or_else(|| UNAVAILABLE.into(), |c| format_time(c, twelve))),
        (TIME_ZONE_LABEL, zone_line),
        (NETWORK_TIME_LABEL, synced.into()),
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
    layout_for_page(width, height, rows, Page::About)
}

/// The layout of `cards` cards on `page`. Every page but About has tap
/// targets on its cards, so their cards are at least `TOUCH_FLOOR` tall.
pub fn layout_for_page(width: u32, height: u32, cards: usize, page: Page) -> Layout {
    let floor = page != Page::About;
    if crate::modem_ui::wide(width, height) {
        // Two columns give values like "14.2 GB free of 29.8 GB" and a long
        // time zone room to read whole; three only when two would overflow
        // the panel at a large text step.
        let two = build(f64::from(width), true, cards, 2, page, floor);
        if two.bottom <= f64::from(height) - 12.0 { two } else { build(f64::from(width), true, cards, 3, page, floor) }
    } else {
        build(568.0, false, cards, 1, page, floor)
    }
}

fn build(w: f64, wide: bool, rows: usize, columns: usize, page: Page, floor: bool) -> Layout {
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
    let back_w = crate::render::measured_text_width(page.back_label(), label, pango::Weight::Normal) + 8.0;
    let content = title_y + title_h + if compact { 6.0 } else { 14.0 };
    let (pad, gap) = (10.0, 10.0);
    let natural = 2.0 * pad + line(caption) + 2.0 + line(body);
    let card_h = if floor { natural.max(TOUCH_FLOOR) } else { natural };
    // Centre the two lines in a card the floor made taller.
    let inset = pad + (card_h - natural) / 2.0;
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
        label_dy: inset,
        value_dy: inset + line(caption) + 2.0,
        bottom,
    }
}

/// The rows a page shows, as a range of `InfoPublic::rows`, and, on a
/// chooser too long for the panel, `(page, pages)` for the pager card that
/// follows them. Everything else shows all its rows.
pub fn window(public: &InfoPublic, width: u32, height: u32) -> (std::ops::Range<usize>, Option<(usize, usize)>) {
    let n = public.rows.len();
    let fits = |cards: usize| {
        let lay = layout_for_page(width, height, cards, public.page);
        lay.bottom <= if lay.wide { f64::from(height) } else { 1232.0 } - 12.0
    };
    if !public.page.paged() || n == 0 || fits(n) {
        return (0..n, None);
    }
    // Rows per page: as many as fit with the pager card after them.
    let per = (1..n).rev().find(|&k| fits(k + 1)).unwrap_or(1);
    let pages = n.div_ceil(per);
    let index = public.page_index.min(pages - 1);
    (index * per..((index + 1) * per).min(n), Some((index, pages)))
}

/// The page's layout: one card per shown row, plus the pager card.
pub fn page_layout(public: &InfoPublic, width: u32, height: u32) -> Layout {
    let (shown, pager) = window(public, width, height);
    layout_for_page(width, height, shown.len() + usize::from(pager.is_some()), public.page)
}

/// A switch pill at the right of a card.
pub fn switch_pill(card: Rect) -> Rect {
    let (x, y, w, h) = card;
    let (pw, ph) = (76.0, 44.0);
    (x + w - 18.0 - pw, y + (h - ph) / 2.0, pw, ph)
}

/// Date & time's switches: `(card index, pill, on)`.
pub fn switches(public: &InfoPublic, lay: &Layout) -> Vec<(usize, Rect, bool)> {
    if public.page != Page::DateTime {
        return Vec::new();
    }
    public
        .rows
        .iter()
        .zip(&lay.cards)
        .enumerate()
        .filter_map(|(i, ((label, value), card))| match label.as_ref() {
            CLOCK_FORMAT_LABEL => Some((i, switch_pill(*card), value == "12-hour")),
            NETWORK_TIME_LABEL => Some((i, switch_pill(*card), value != NETWORK_TIME_OFF_VALUE)),
            _ => None,
        })
        .collect()
}

/// Every tap target but Back: `(rect, intent)`.
pub fn targets(public: &InfoPublic, lay: &Layout, width: u32, height: u32) -> Vec<(Rect, Intent)> {
    let (shown, pager) = window(public, width, height);
    let mut out = Vec::new();
    for (slot, index) in shown.clone().enumerate() {
        let Some(&card) = lay.cards.get(slot) else { break };
        let intent = match (public.page, public.rows[index].0.as_ref()) {
            (Page::DateTime, CLOCK_FORMAT_LABEL) => Intent::ToggleClockFormat,
            (Page::DateTime, NETWORK_TIME_LABEL) => Intent::ToggleNetworkTime,
            (Page::DateTime, TIME_ZONE_LABEL) => Intent::OpenZones,
            (Page::Regions | Page::Zones, _) => Intent::Choose(index),
            _ => continue,
        };
        out.push((card, intent));
    }
    if let (Some(_), Some(&(x, y, w, h))) = (pager, lay.cards.get(shown.len())) {
        out.push(((x, y, w / 2.0, h), Intent::Turn(false)));
        out.push(((x + w / 2.0, y, w / 2.0, h), Intent::Turn(true)));
    }
    out
}

fn target(lay: &Layout, targets: &[(Rect, Intent)], x: f64, y: f64) -> Option<Intent> {
    if x < lay.back_hit.0 && y < lay.back_hit.1 {
        return Some(Intent::Back);
    }
    targets.iter().find(|((tx, ty, tw, th), _)| x >= *tx && x < tx + tw && y >= *ty && y < ty + th).map(|t| t.1)
}

/// A tap that went down and came up on the same target.
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
    let lay = page_layout(public, width, height);
    let (sx, sy) = layout_scale(width, height);
    let (start, end) = ((start.0 * sx, start.1 * sy), (end.0 * sx, end.1 * sy));
    if (end.0 - start.0).abs() > 18.0 || (end.1 - start.1).abs() > 18.0 {
        return None;
    }
    let targets = targets(public, &lay, width, height);
    let down = target(&lay, &targets, start.0, start.1);
    let up = target(&lay, &targets, end.0, end.1);
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
        assert!(get(TIME_ZONE_LABEL).starts_with("America/Chicago (UTC"), "{}", get(TIME_ZONE_LABEL));
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
        // Switched off, network time says so even with a stamp from before.
        fs::create_dir_all(root.join("var/lib/k230-time")).unwrap();
        fs::write(root.join("var/lib/k230-time/network-time-off"), "off\n").unwrap();
        assert_eq!(date_time_rows(&src)[3].1, NETWORK_TIME_OFF_VALUE);
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
        InfoPublic {
            page,
            rows: (0..n).map(|_| (Cow::Borrowed("Label"), "Value".to_string())).collect(),
            region: None,
            page_index: 0,
        }
    }

    fn date_time_public() -> InfoPublic {
        let mut p = public(Page::DateTime, 5);
        for (i, label) in ["Date", "Time", TIME_ZONE_LABEL, NETWORK_TIME_LABEL, CLOCK_FORMAT_LABEL].iter().enumerate() {
            p.rows[i].0 = Cow::Borrowed(label);
        }
        p.rows[3].1 = "Synchronized".into();
        p.rows[4].1 = "24-hour".into();
        p
    }

    fn centre((x, y, w, h): Rect, width: u32, height: u32) -> (f64, f64) {
        let (sx, sy) = layout_scale(width, height);
        ((x + w / 2.0) / sx, (y + h / 2.0) / sy)
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
    fn date_and_time_rows_are_floor_sized_targets_with_two_switches() {
        for step in [1.0, 2.0] {
            crate::set_layout_text_scale(step);
            for (w, h) in [(568u32, 1232u32), (1232, 568)] {
                let p = date_time_public();
                let lay = page_layout(&p, w, h);
                assert!(lay.cards.iter().all(|c| c.3 >= TOUCH_FLOOR), "{w}x{h} step {step}");
                let sw = switches(&p, &lay);
                assert_eq!(sw.iter().map(|s| (s.0, s.2)).collect::<Vec<_>>(), [(3, true), (4, false)]);
                for (i, pill, _) in &sw {
                    let card = lay.cards[*i];
                    assert!(pill.0 >= card.0 && pill.0 + pill.2 <= card.0 + card.2);
                }
                let tap = |i: usize| {
                    let c = centre(lay.cards[i], w, h);
                    hit(&p, c, c, w, h)
                };
                assert_eq!(tap(0), None, "Date is not a target");
                assert_eq!(tap(1), None, "Time is not a target");
                assert_eq!(tap(2), Some(Intent::OpenZones), "{w}x{h}");
                assert_eq!(tap(3), Some(Intent::ToggleNetworkTime), "{w}x{h}");
                assert_eq!(tap(4), Some(Intent::ToggleClockFormat), "{w}x{h}");
                let mut about = p.clone();
                about.page = Page::About;
                assert!(switches(&about, &lay).is_empty());
                let c = centre(lay.cards[4], w, h);
                assert_eq!(hit(&about, c, c, w, h), None);
            }
        }
        crate::set_layout_text_scale(1.0);
    }

    #[test]
    fn network_time_off_shows_the_switch_off() {
        let mut p = date_time_public();
        p.rows[3].1 = NETWORK_TIME_OFF_VALUE.into();
        let lay = page_layout(&p, 1232, 568);
        assert_eq!(switches(&p, &lay)[0].2, false);
    }

    const TAB: &str = "# comment\nGB\t+5130-00007\tEurope/London\nFR\t+4852+00220\tEurope/Paris\n\
        US\t+415100-0873900\tAmerica/Chicago\nAR\t-3436-05827\tAmerica/Argentina/Buenos_Aires\n\
        US\t+404251-0740023\tAmerica/New_York\n";

    fn zone_fixture() -> (PathBuf, Sources) {
        let (root, src) = fixture();
        fs::create_dir_all(root.join("etc/zoneinfo")).unwrap();
        fs::write(root.join("etc/zoneinfo/zone1970.tab"), TAB).unwrap();
        (root, src)
    }

    #[test]
    fn the_chooser_lists_areas_then_their_zones() {
        let (root, src) = zone_fixture();
        let zones = zone_table(&src);
        assert_eq!(zones, ["America/Argentina/Buenos_Aires", "America/Chicago", "America/New_York", "Europe/London", "Europe/Paris"]);
        let areas = region_rows(&zones);
        let pairs: Vec<(&str, &str)> = areas.iter().map(|(c, v)| (c.as_ref(), v.as_str())).collect();
        assert_eq!(pairs, [("3 zones", "America"), ("2 zones", "Europe"), ("Coordinated Universal Time", "UTC")]);
        let america = zone_rows(&zones, "America");
        assert_eq!(america[0], (Cow::Owned("America/Argentina/Buenos_Aires".into()), "Buenos Aires, Argentina".into()));
        assert_eq!(america[2].1, "New York");
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn choosing_walks_areas_zones_and_back() {
        let (root, src) = zone_fixture();
        let mut view = InfoView::default();
        view.open(Page::DateTime, &src);
        view.open(Page::Regions, &src);
        assert_eq!(view.public().unwrap().rows.len(), 3);
        assert_eq!(view.choose(1, &src), None, "an area opens its zones");
        let p = view.public().unwrap();
        assert_eq!((p.page, p.region.as_deref()), (Page::Zones, Some("Europe")));
        assert_eq!(p.rows.iter().map(|r| r.1.as_str()).collect::<Vec<_>>(), ["London", "Paris"]);
        assert!(!view.back(&src));
        assert_eq!(view.page, Page::Regions);
        view.choose(1, &src);
        assert_eq!(view.choose(0, &src).as_deref(), Some("Europe/London"));
        assert_eq!(view.page, Page::DateTime, "a choice returns to Date & time");
        view.open(Page::Regions, &src);
        assert_eq!(view.choose(2, &src).as_deref(), Some(UTC), "UTC applies directly");
        assert!(!view.back(&src) || view.page == Page::Closed);
        view.open(Page::Regions, &src);
        assert!(!view.back(&src));
        assert_eq!(view.page, Page::DateTime);
        assert!(view.back(&src));
        assert_eq!(view.page, Page::Closed);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn a_long_chooser_pages_with_floor_sized_cards() {
        for step in [1.0, 1.5, 2.0] {
            crate::set_layout_text_scale(step);
            for (w, h) in [(568u32, 1232u32), (1232, 568)] {
                let zones: Vec<String> = (0..140).map(|i| format!("America/Place_{i:03}")).collect();
                let mut p = public(Page::Zones, 0);
                p.rows = zone_rows(&zones, "America");
                let (shown, pager) = window(&p, w, h);
                let (index, pages) = pager.expect("140 zones need a pager");
                assert_eq!((index, shown.start), (0, 0));
                assert!(shown.len() >= 4, "{w}x{h} step {step}: only {} per page", shown.len());
                assert_eq!(pages, 140usize.div_ceil(shown.len()));
                let lay = page_layout(&p, w, h);
                assert!(lay.cards.iter().all(|c| c.3 >= TOUCH_FLOOR));
                let limit = if lay.wide { f64::from(h) } else { 1232.0 };
                assert!(lay.bottom <= limit, "{w}x{h} step {step}: {} > {limit}", lay.bottom);
                let first = centre(lay.cards[0], w, h);
                assert_eq!(hit(&p, first, first, w, h), Some(Intent::Choose(0)));
                let pager_card = lay.cards[shown.len()];
                let (px, py, pw, ph) = pager_card;
                let left = centre((px, py, pw / 2.0, ph), w, h);
                let right = centre((px + pw / 2.0, py, pw / 2.0, ph), w, h);
                assert_eq!(hit(&p, left, left, w, h), Some(Intent::Turn(false)));
                assert_eq!(hit(&p, right, right, w, h), Some(Intent::Turn(true)));
                p.page_index = 1;
                let (second, _) = window(&p, w, h);
                assert_eq!(second.start, shown.len());
                assert_eq!(hit(&p, first, first, w, h), Some(Intent::Choose(shown.len())));
                p.page_index = 99;
                assert_eq!(window(&p, w, h).1, Some((pages - 1, pages)), "the index clamps");
            }
        }
        crate::set_layout_text_scale(1.0);
    }

    #[test]
    fn turning_stops_at_either_end() {
        let mut view = InfoView::default();
        view.turn(false, 3);
        assert_eq!(view.page_index, 0);
        view.turn(true, 3);
        view.turn(true, 3);
        view.turn(true, 3);
        assert_eq!(view.page_index, 2);
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

//! Touch-only theme chooser state. All command I/O belongs to `ThemeWorker`.
//!
//! User decision (2026-09-28, verbatim): "i don't really think we need an
//! 'apply' window for themes at all. tap theme in the theme picker, apply
//! immediately, so i can compare them easily." Tapping a theme (or a
//! background of the active theme) applies it right away, through the
//! optimistic path; there is no separate preview page and no Apply/Cancel
//! step. Swiping/dragging only browses (`theme_carousel::Carousel`'s own
//! `Confirm`-only-when-already-centred rule makes this automatic). Rapid
//! taps coalesce onto `desired`: at most one request is ever in flight, and
//! a reply that no longer matches `desired` is discarded, with `advance()`
//! immediately moving on to whatever is now desired instead.

use crate::background_decode::{BackgroundCache, FitMode};
use crate::theme_catalog::{
    BackgroundKind, ThemeList, ThemeOrigin, ThemePreview, ThemeReply, ThemeRequest, ThemeResponse,
    VisionChoice,
};
use std::{
    collections::{HashMap, VecDeque},
    path::PathBuf,
    sync::mpsc::{self, Receiver, SyncSender, TryRecvError},
    thread,
};

/// One immutable generation still at a time. Decode runs outside Wayland
/// dispatch; a cancelled/changed preview can discard the returned key.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ThemeImageKey {
    pub generation: String,
    pub path: PathBuf,
    /// The prepared generation directory `path` lives under (the parent of
    /// its `appearance.json` -- see `theme_catalog::ThemePreview::
    /// appearance_path`). `tools/theme_activate.py`'s `prepare()` already
    /// writes this same width/height/`FitMode::Crop` decode as
    /// `background.cache` at generation-prepare time (see
    /// `background_decode.rs`); passing this through lets the worker load
    /// that file directly instead of repeating a full source decode the
    /// activation flow already paid for.
    pub generation_root: PathBuf,
    pub width: u32,
    pub height: u32,
    /// How the still is placed. The chooser's own previews are `Crop`; the
    /// generation's `background.cache` only matches `Crop`, so another mode
    /// is a cache miss and a full decode, never a wrong picture.
    pub fit: FitMode,
}

pub struct ThemeImageReply {
    pub key: ThemeImageKey,
    pub pixels: Result<Vec<u8>, String>,
}

pub struct ThemeImageWorker {
    requests: SyncSender<ThemeImageKey>,
    replies: Receiver<ThemeImageReply>,
}

impl Default for ThemeImageWorker {
    fn default() -> Self {
        let (requests, incoming) = mpsc::sync_channel::<ThemeImageKey>(1);
        let (outgoing, replies) = mpsc::sync_channel::<ThemeImageReply>(1);
        thread::spawn(move || {
            let mut cache = BackgroundCache::new();
            while let Ok(key) = incoming.recv() {
                let pixels = cache
                    .render(
                        &key.path,
                        Some(key.generation_root.as_path()),
                        key.width,
                        key.height,
                        key.fit,
                    )
                    .map(<[u8]>::to_vec);
                if outgoing.send(ThemeImageReply { key, pixels }).is_err() {
                    break;
                }
            }
        });
        Self { requests, replies }
    }
}

impl ThemeImageWorker {
    pub fn try_request(&self, key: ThemeImageKey) -> bool {
        matches!(self.requests.try_send(key), Ok(()))
    }

    pub fn try_recv(&self) -> Option<ThemeImageReply> {
        match self.replies.try_recv() {
            Ok(reply) => Some(reply),
            Err(TryRecvError::Empty | TryRecvError::Disconnected) => None,
        }
    }
}

/// Source filenames are secondary to a readable selection name. Opaque IDs
/// still select the exact staged asset; this changes display text only.
pub fn background_display_label(label: &str) -> String {
    let stem = label.rsplit_once('.').map_or(label, |(stem, _)| stem);
    let stem = stem.trim_start_matches(|ch: char| ch.is_ascii_digit() || ch == '-' || ch == '_');
    let words = stem.replace(['-', '_'], " ");
    let words = words.trim();
    if words.is_empty() {
        return "Background".into();
    }
    let mut chars = words.chars();
    let first = chars.next().expect("nonempty background label");
    format!("{}{}", first.to_uppercase(), chars.as_str())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ThemePage {
    Controls,
    /// The one chooser page now: the theme carousel, the active theme's
    /// own background carousel below it, and a "Current"/ring marker on
    /// whichever slice of each is currently, durably active.
    List,
    /// The vision options: a larger text step and a high-contrast palette,
    /// applied to every theme (`tools/theme_vision.py`).
    Vision,
}

/// What a Vision page tap chose: one of the four text-size steps
/// (`theme_catalog::TEXT_SCALE_NAMES` index), or the contrast card.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum VisionToggle {
    TextSize(usize),
    Contrast,
}

/// The Vision cards keep a readable column on a wide output.
pub const VISION_CARD_MAX_W: f64 = 520.0;
/// The 48 dp tap floor on this panel (2.07 px per dp).
pub const VISION_TAP_MIN: f64 = 99.0;

/// Where the Vision page puts its cards at text size `scale` (1.0-2.0).
/// Drawing and hit-testing both read this, so they cannot disagree, and
/// every height grows with the text so nothing clips at 200%.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct VisionLayout {
    pub scale: f64,
    /// The "Text size" card and its four step segments.
    pub text_card: (f64, f64, f64, f64),
    pub segments: [(f64, f64, f64, f64); 4],
    /// The "High contrast" card.
    pub contrast_card: (f64, f64, f64, f64),
    /// Baseline top of the status line under the cards.
    pub status_y: f64,
    /// The bottom of everything the page draws.
    pub bottom: f64,
}

/// The Vision page layout for an output `width` px wide at text `scale`.
/// Side by side when two cards fit (landscape panel, HDMI); stacked in
/// portrait.
pub fn vision_layout(width: f64, scale: f64) -> VisionLayout {
    let s = scale.clamp(1.0, 2.0);
    let line = |size: f64| (size * s * 1.35).ceil();
    let top = (110.0 + 40.0 * s).round();
    let cw = (width - 48.0).min(VISION_CARD_MAX_W).max(0.0);
    // `width` 0 asks for the stacked (portrait) column without a width.
    let side_by_side = cw > 0.0 && width >= 2.0 * cw + 72.0;
    let label_h = line(17.0);
    let seg_h = (line(18.0) + 40.0).max(VISION_TAP_MIN);
    let text_h = 18.0 + label_h + 12.0 + seg_h + 14.0;
    let contrast_h = (18.0 + label_h + 6.0 + line(19.0) + 18.0).max(VISION_TAP_MIN);
    let text_card = (24.0, top, cw, text_h);
    let contrast_card = if side_by_side {
        (24.0 + cw + 24.0, top, cw, contrast_h)
    } else {
        (24.0, top + text_h + 16.0, cw, contrast_h)
    };
    let pad = 12.0;
    let gap = 8.0;
    let seg_w = (cw - 2.0 * pad - 3.0 * gap) / 4.0;
    let seg_y = top + 18.0 + label_h + 12.0;
    let segments = std::array::from_fn(|i| (24.0 + pad + i as f64 * (seg_w + gap), seg_y, seg_w, seg_h));
    let cards_bottom = (text_card.1 + text_card.3).max(contrast_card.1 + contrast_card.3);
    let status_y = cards_bottom + 12.0;
    VisionLayout { scale: s, text_card, segments, contrast_card, status_y, bottom: status_y + line(18.0) + 24.0 }
}

/// The theme (and, once a theme is active, which of its own backgrounds)
/// a tap most recently asked for. Coalescing owns this: a new tap always
/// overwrites it, whether or not a request for the previous one is still
/// in flight, and a reply that no longer matches it is discarded rather
/// than shown.
#[derive(Clone, Debug, PartialEq)]
pub struct Desired {
    theme_id: String,
    background_id: Option<String>,
    /// Learned once the matching `Preview` reply arrives; `Activate` (the
    /// real, durable step) needs it and cannot be sent before then.
    generation: Option<String>,
    /// True when this target was already the reported active theme/
    /// background at the moment it was set (the initial chooser-open
    /// load, or a re-tap of what is already active): settling then never
    /// needs an `Activate` at all, just the one `Preview` to (re)load its
    /// own detail.
    already_active: bool,
}

#[derive(Clone, Debug)]
pub struct ThemeView {
    pub page: ThemePage,
    pub list: Option<ThemeList>,
    /// Name of the packaged default theme (`catppuccin` today), read from
    /// `K230_THEME_DEFAULT_GENERATION`'s own `report.json`. A board with no
    /// durable theme choice yet shows this theme, so the chooser loads its
    /// backgrounds instead of waiting for an active theme that does not exist.
    pub default_theme_name: Option<String>,
    /// The *active* theme's own detail (palette/backgrounds) -- what the
    /// background carousel below the theme carousel is drawn from. Kept
    /// stable while a candidate is merely being applied (optimistically
    /// shown or durably settling): this only ever changes once a tap's own
    /// target actually becomes active (an `activated: true`/`already_
    /// active` reply), matching what is genuinely on screen.
    pub preview: Option<ThemePreview>,
    pub pending: Option<ThemeRequest>,
    pub pending_id: Option<u64>,
    pub error: Option<String>,
    pub message: Option<String>,
    /// The theme carousel's continuous position (`theme_carousel::Carousel`
    /// in `main.rs` owns the drag/momentum physics; this is just the
    /// latest value, mirrored here so the renderer -- which only ever sees
    /// a cloned `ThemeView`, never the live carousel -- can paint it).
    pub theme_position: f64,
    /// Same, for the background carousel.
    pub background_position: f64,
    /// Which theme-carousel slice, if any, currently shows an immediate
    /// "pressed" highlight -- mirrored each frame from
    /// `theme_carousel::Carousel::pressed` (`main.rs` owns the live
    /// carousel; the renderer only ever sees this cloned snapshot). See
    /// `render.rs::paint_carousel`.
    pub theme_pressed: Option<usize>,
    /// Same, for the background carousel.
    pub background_pressed: Option<usize>,
    /// A slow, deliberately throttled 0.0..1.0 animation phase driving every
    /// loading spinner this page paints (pending thumbnails, a preparing
    /// still preview, a tap still being applied). `main.rs` advances this on
    /// its own bounded cadence -- see its `THEME_PULSE_INTERVAL` -- rather
    /// than every event-loop tick, which is what previously caused a
    /// continuous full redraw at rest while thumbnails were still decoding
    /// (the idle-redraw fix this field is part of).
    pub pulse_phase: f64,
    /// Task 3.2: index whose centred dwell time is accumulating, on the
    /// theme carousel only. Reset (to `None`/`0`) whenever the carousel
    /// is not settled on one index -- a drag, a coast, or a settle
    /// animation in progress -- so a fast flick across many themes never
    /// fires a warm-up per slice ("cancelled on scroll-away"). `pub` only
    /// because `render.rs`'s test fixtures build a `ThemeView` with `..`
    /// struct-update syntax, same as every other field here; nothing
    /// outside this module has a reason to read or set these directly --
    /// use `poll_prepare_ahead`/`prepare_ahead_submitted`/
    /// `prepare_ahead_reply` instead.
    pub prepare_ahead_watch: Option<usize>,
    pub prepare_ahead_elapsed_ms: u32,
    /// The index a warm-up request has already been sent (or is in flight)
    /// for, so a long dwell on the same item does not resend once it has
    /// been asked for once.
    pub prepare_ahead_sent_for: Option<usize>,
    /// The single in-flight warm-up request's id, recognised and consumed
    /// by `prepare_ahead_reply` so `main.rs` never feeds that reply to
    /// `accept` -- it must never navigate or repaint the chooser, only free
    /// this one slot for the next settled candidate. Bounding this to one
    /// (rather than a queue) is deliberately the stricter half of "one or
    /// two in flight": it also keeps this from crowding the same
    /// `ThemeWorker` queue a real Preview/Activate tap needs.
    pub prepare_ahead_inflight: Option<u64>,
    /// Indices still queued for an unconditional, dwell-independent
    /// warm-up: the active theme's immediate carousel neighbours, queued
    /// once when its own `list` reply lands (board evidence, 2026-09-25:
    /// browsing to a never-before-prepared theme cost ~4 s the first time,
    /// dominating the felt "instant" experience even after Apply itself
    /// got fast). Drained one at a time, only when `poll_prepare_ahead` has
    /// no dwell-driven request of its own to make and the single in-flight
    /// slot is free, so this never competes with -- or delays -- warming
    /// whatever a person is actually looking at right now.
    pub pending_neighbor_warms: VecDeque<usize>,
    /// The generation a warm-up (`poll_prepare_ahead`) reply reported for
    /// a theme id, remembered even though the reply itself is otherwise
    /// discarded (`prepare_ahead_reply`) -- the optimistic-apply pre-render
    /// trigger (`main.rs`) needs a centred-but-not-yet-tapped theme's own
    /// generation to know what to pre-render *for*, and re-deriving it
    /// with a fresh Preview call there would itself cost the round trip
    /// this cache exists to avoid. Bounded only by the theme catalog's own
    /// size (typically well under a hundred entries); never persisted.
    pub known_generations: HashMap<String, String>,
    /// What a tap most recently asked for; see `Desired`'s own doc. `pub`
    /// only because `render.rs`'s test fixtures build a `ThemeView` with
    /// `..` struct-update syntax, same as `prepare_ahead_watch` and its
    /// neighbours above -- nothing outside this module has a reason to
    /// read or set it directly; use `tap_theme`/`tap_background`/
    /// `advance`/`accept` instead.
    pub desired: Option<Desired>,
    /// The fit mode (`background_decode::FitMode::NAMES`) of the active
    /// generation, read from its `report.json` each time a preview settles.
    /// Shown on the "Backgrounds" heading; tapping the heading cycles it.
    pub fit: String,
    /// A fit change in progress: the requested name and, once its preview
    /// step has returned, the generation to activate. Independent of
    /// `desired` (a theme or background tap clears it).
    pub fit_wanted: Option<(String, Option<String>)>,
    /// The saved vision choice, as the last `list` or `vision` reply said.
    pub vision: VisionChoice,
    /// False until a reply has said what the saved choice is, so the Vision
    /// page never toggles from a guessed starting point.
    pub vision_loaded: bool,
}

/// The `fit_mode` recorded in the generation directory that holds
/// `appearance_path` (`crop` when absent, unreadable or unrecognised).
fn generation_fit(appearance_path: &std::path::Path) -> String {
    let name = appearance_path
        .parent()
        .and_then(|root| std::fs::read(root.join("report.json")).ok())
        .filter(|bytes| bytes.len() <= 1 << 20)
        .and_then(|bytes| serde_json::from_slice::<serde_json::Value>(&bytes).ok())
        .and_then(|report| report.get("fit_mode")?.as_str().map(str::to_owned));
    match name {
        Some(name) if FitMode::NAMES.contains(&name.as_str()) => name,
        _ => "crop".into(),
    }
}

/// How long a theme must stay the carousel's centred item, with the
/// carousel otherwise at rest, before task 3.2 treats it as "browsed to"
/// and warms it ahead of a possible tap-apply. Long enough that a flick
/// past several themes on the way to a specific one fires nothing for the
/// ones only passed through; short enough that a person who pauses to
/// look at a theme is very likely already warmed by the time they tap it.
const PREPARE_AHEAD_DEBOUNCE_MS: u32 = 220;

/// The packaged default theme's name: the last segment of its generation
/// report's `source` (`omacom/omarchy@<rev>/themes/catppuccin`). `None` when
/// the report is missing, oversized or not of that shape.
pub fn default_theme_name(generation: &std::path::Path) -> Option<String> {
    let bytes = std::fs::read(generation.join("report.json")).ok()?;
    if bytes.len() > 1 << 20 {
        return None;
    }
    let report: serde_json::Value = serde_json::from_slice(&bytes).ok()?;
    let (_, name) = report.get("source")?.as_str()?.rsplit_once("/themes/")?;
    (!name.is_empty() && !name.contains('/')).then(|| name.to_owned())
}

impl Default for ThemeView {
    fn default() -> Self {
        Self {
            page: ThemePage::Controls,
            list: None,
            default_theme_name: None,
            preview: None,
            pending: None,
            pending_id: None,
            error: None,
            message: None,
            theme_position: 0.0,
            background_position: 0.0,
            theme_pressed: None,
            background_pressed: None,
            pulse_phase: 0.0,
            prepare_ahead_watch: None,
            prepare_ahead_elapsed_ms: 0,
            prepare_ahead_sent_for: None,
            prepare_ahead_inflight: None,
            pending_neighbor_warms: VecDeque::new(),
            known_generations: HashMap::new(),
            desired: None,
            fit: "crop".into(),
            fit_wanted: None,
            vision: VisionChoice::default(),
            vision_loaded: false,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ThemeIntent {
    Open,
    Back,
    Close,
    /// Tap-confirm on the theme carousel's own centred slice (never an
    /// off-centre one -- `theme_carousel::Carousel::up`'s own
    /// `Confirm`-only-when-already-centred rule keeps a mere recentring
    /// tap from reaching here at all): apply that theme now.
    Theme(usize),
    /// Same, for the background carousel: apply that background of the
    /// active theme now.
    Background(usize),
    /// Tap on the "Backgrounds" heading: cycle the active background's fit
    /// mode (crop, fit, center, fill, solid).
    Fit,
    /// "Vision ›" in the Settings header.
    OpenVision,
    /// A Vision page card.
    Vision(VisionToggle),
}

/// Top of the theme carousel band (below the "Themes" heading/subtext).
/// Task: tap-to-apply (2026-09-25) put the active theme's own background
/// carousel on this same page, below this one, so this moved up from the
/// old single-carousel page's own `204.0` to leave the extra room a
/// second carousel plus its own labels need within the fixed 1232-tall
/// panel (board evidence still outstanding for this exact layout -- see
/// this task's own evidence doc).
pub const THEME_CAROUSEL_TOP: f64 = 132.0;
/// Top of the background carousel band, directly below the theme
/// carousel's own name label and origin caption (`paint_theme_chooser`'s
/// own fixed layout: a 12px gap, a 24px name line, a 26px-offset 16px
/// status line, a 16px gap, a 22px "Backgrounds" heading, then an 8px
/// gap -- `100.0` total). Both carousels live on the one chooser page
/// now; there is no longer a separate page transition between them.
pub const BACKGROUND_CAROUSEL_TOP: f64 =
    THEME_CAROUSEL_TOP + crate::theme_carousel::THEME_GEOMETRY.expanded_h + 100.0;

/// Where the theme chooser's pieces sit. The portrait panel and the HDMI
/// outputs keep the stacked layout (the theme carousel over the backgrounds
/// carousel); the landscape panel (`help::wide`) puts them side by side, each
/// in its own half of the output, so both carousels and their labels fit the
/// 568 px height. `render.rs` paints and `main.rs` hit-tests from this one
/// struct, so a touch and its paint cannot drift apart.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ChooserLayout {
    pub wide: bool,
    pub theme_geometry: crate::theme_carousel::CarouselGeometry,
    pub background_geometry: crate::theme_carousel::CarouselGeometry,
    pub theme_top: f64,
    pub background_top: f64,
    pub theme_cx: f64,
    pub background_cx: f64,
    /// Horizontal extent each carousel is clipped and hit-tested to.
    pub theme_cols: (f64, f64),
    pub background_cols: (f64, f64),
    /// Left edge and width of the text above and below each carousel.
    pub theme_text: (f64, f64),
    pub background_text: (f64, f64),
    /// Y of the header's "‹ Settings" and "Close", and how far down a touch
    /// still counts as the header.
    pub header_y: f64,
    pub header_hit_h: f64,
    /// "Themes" heading, its hint line, and the "Backgrounds" heading:
    /// `(x, y)` each (the hint's width is the theme column's).
    pub themes_heading: (f64, f64),
    pub themes_hint: (f64, f64),
    pub backgrounds_heading: (f64, f64),
    /// Where the background carousel's "Applying…" feedback sits and how wide it may be.
    pub feedback: (f64, f64, f64),
    /// Y of the single pending/error/message line at the bottom of the
    /// background column.
    pub message_y: f64,
    /// Wide surfaces show every theme and every background at once as a
    /// grid of cards (tap a card to apply) instead of the two carousels.
    pub theme_grid: Option<Grid>,
    pub background_grid: Option<Grid>,
}

/// Card grid of one column: `count` cards of `card_w`x`card_h`, `cols`
/// across, each with a label line below it.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Grid {
    pub x: f64,
    pub y: f64,
    pub cols: usize,
    pub count: usize,
    pub card_w: f64,
    pub card_h: f64,
    pub gap: f64,
}

/// Height of the name line under each grid card.
pub const GRID_LABEL_H: f64 = 26.0;

impl Grid {
    /// The largest cards of aspect `h_per_w` that fit `count` of them in
    /// `(x, y, w, h)`, aligned with the column's text, never wider than `max_w`.
    pub fn fit(count: usize, (x, y, w, h): (f64, f64, f64, f64), h_per_w: f64, max_w: f64) -> Grid {
        let gap = 16.0;
        let count = count.max(1);
        let mut best = (1, 0.0);
        for cols in 1..=count {
            let rows = count.div_ceil(cols) as f64;
            let by_width = (w - gap * (cols - 1) as f64) / cols as f64;
            let by_height = ((h - gap * (rows - 1.0)) / rows - GRID_LABEL_H) / h_per_w;
            let card_w = by_width.min(by_height).min(max_w);
            if card_w > best.1 {
                best = (cols, card_w);
            }
        }
        let (cols, card_w) = (best.0, best.1.max(1.0).floor());
        Grid {
            x: x.round(),
            y,
            cols,
            count,
            card_w,
            card_h: (card_w * h_per_w).round(),
            gap,
        }
    }

    pub fn rect(&self, index: usize) -> (f64, f64, f64, f64) {
        let (col, row) = ((index % self.cols) as f64, (index / self.cols) as f64);
        (
            self.x + col * (self.card_w + self.gap),
            self.y + row * (self.card_h + GRID_LABEL_H + self.gap),
            self.card_w,
            self.card_h,
        )
    }

    /// The card (its image or its label line) under `pos`.
    pub fn hit(&self, pos: (f64, f64)) -> Option<usize> {
        (0..self.count).find(|&index| {
            let (x, y, w, h) = self.rect(index);
            pos.0 >= x && pos.0 < x + w && pos.1 >= y && pos.1 < y + h + GRID_LABEL_H
        })
    }
}

/// `chooser_layout` with the grids sized for the themes and backgrounds
/// actually listed. Without counts (`chooser_layout`) the wide layout has
/// no grids and falls back to the carousels.
pub fn chooser_layout_for(width: u32, height: u32, themes: usize, backgrounds: usize) -> ChooserLayout {
    let mut lay = chooser_layout(width, height);
    if lay.wide {
        let h = f64::from(height);
        let bottom = h - 48.0;
        let (tx, tw) = lay.theme_text;
        let (bx, bw) = lay.background_text;
        lay.theme_grid = (themes > 0).then(|| Grid::fit(themes, (tx, lay.theme_top, tw, bottom - lay.theme_top), 4.0 / 3.0, 240.0));
        lay.background_grid = (backgrounds > 0).then(|| Grid::fit(backgrounds, (bx, lay.background_top, bw, bottom - lay.background_top), 475.0 / 768.0, 360.0));
        lay.message_y = h - 34.0;
    }
    lay
}

impl ThemeView {
    /// The chooser layout for this view's own lists at a surface size.
    pub fn layout(&self, width: u32, height: u32) -> ChooserLayout {
        chooser_layout_for(
            width,
            height,
            self.list.as_ref().map_or(0, |l| l.themes.len()),
            self.preview.as_ref().map_or(0, |p| p.backgrounds.len()),
        )
    }
}

pub fn chooser_layout(width: u32, height: u32) -> ChooserLayout {
    let w = f64::from(width);
    if width > 0 && height > 0 && crate::help::wide(width, height) {
        let half = w / 2.0;
        let top = 100.0;
        let bg_h = crate::theme_carousel::BACKGROUND_GEOMETRY.expanded_h;
        ChooserLayout {
            wide: true,
            theme_geometry: crate::theme_carousel::THEME_GEOMETRY_WIDE,
            background_geometry: crate::theme_carousel::BACKGROUND_GEOMETRY,
            theme_top: top,
            background_top: top,
            theme_cx: half / 2.0,
            background_cx: half + half / 2.0,
            theme_cols: (0.0, half),
            background_cols: (half, w),
            theme_text: (28.0, half - 56.0),
            background_text: (half + 28.0, half - 56.0),
            header_y: 14.0,
            header_hit_h: 48.0,
            themes_heading: (28.0, 48.0),
            themes_hint: (150.0, 54.0),
            backgrounds_heading: (half + 28.0, 48.0),
            feedback: (half + 190.0, 50.0, half - 218.0),
            message_y: (top + bg_h + 64.0).min(f64::from(height) - 30.0),
            theme_grid: None,
            background_grid: None,
        }
    } else {
        let center = w / 2.0;
        let message_y = (BACKGROUND_CAROUSEL_TOP
            + crate::theme_carousel::BACKGROUND_GEOMETRY.expanded_h
            + 64.0)
            .min(f64::from(height) - 30.0);
        ChooserLayout {
            wide: false,
            theme_geometry: crate::theme_carousel::THEME_GEOMETRY,
            background_geometry: crate::theme_carousel::BACKGROUND_GEOMETRY,
            theme_top: THEME_CAROUSEL_TOP,
            background_top: BACKGROUND_CAROUSEL_TOP,
            theme_cx: center,
            background_cx: center,
            theme_cols: (0.0, w),
            background_cols: (0.0, w),
            theme_text: (28.0, w - 56.0),
            background_text: (28.0, w - 56.0),
            header_y: 42.0,
            header_hit_h: 104.0,
            themes_heading: (28.0, 84.0),
            themes_hint: (28.0, 112.0),
            backgrounds_heading: (28.0, BACKGROUND_CAROUSEL_TOP - 30.0),
            feedback: (center, BACKGROUND_CAROUSEL_TOP - 30.0, center - 28.0),
            message_y,
            theme_grid: None,
            background_grid: None,
        }
    }
}

impl ChooserLayout {
    /// Whether a touch at `pos` lands in the theme carousel's band.
    pub fn in_theme_band(&self, pos: (f64, f64)) -> bool {
        self.theme_grid.is_none()
            && pos.0 >= self.theme_cols.0
            && pos.0 < self.theme_cols.1
            && pos.1 >= self.theme_top
            && pos.1 < self.theme_top + self.theme_geometry.expanded_h
    }

    /// Same, for the background carousel's band.
    pub fn in_background_band(&self, pos: (f64, f64)) -> bool {
        self.background_grid.is_none()
            && pos.0 >= self.background_cols.0
            && pos.0 < self.background_cols.1
            && pos.1 >= self.background_top
            && pos.1 < self.background_top + self.background_geometry.expanded_h
    }
}

fn request_target(request: &ThemeRequest) -> Option<(&str, Option<&str>)> {
    match request {
        ThemeRequest::Preview {
            theme_id,
            background_id,
        }
        | ThemeRequest::Activate {
            theme_id,
            background_id,
            ..
        } => Some((theme_id.as_str(), background_id.as_deref())),
        ThemeRequest::List | ThemeRequest::Fit { .. } | ThemeRequest::Vision(_) => None,
    }
}

impl ThemeView {
    pub fn open(&mut self) -> ThemeRequest {
        self.page = ThemePage::List;
        self.preview = None;
        self.error = None;
        self.message = None;
        self.theme_pressed = None;
        self.background_pressed = None;
        self.desired = None;
        self.reset_prepare_ahead_debounce();
        ThemeRequest::List
    }

    /// Opens the Vision page and asks for the saved choice; the `list`
    /// reply fills `vision` without leaving the page.
    pub fn open_vision(&mut self) -> ThemeRequest {
        self.page = ThemePage::Vision;
        self.error = None;
        self.message = None;
        self.desired = None;
        self.fit_wanted = None;
        ThemeRequest::List
    }

    /// The request for a Vision tap: the saved choice with that text step
    /// chosen or the contrast flipped. Nothing while another request is in
    /// flight, before the saved choice is known, or when the step tapped is
    /// already the saved one.
    pub fn toggle_vision(&mut self, toggle: VisionToggle) -> Option<ThemeRequest> {
        if self.pending.is_some() || !self.vision_loaded {
            return None;
        }
        let mut next = self.vision.clone();
        match toggle {
            VisionToggle::TextSize(step) => {
                let name = *crate::theme_catalog::TEXT_SCALE_NAMES.get(step)?;
                if name == next.text_scale {
                    return None; // Already the saved step: nothing to apply.
                }
                next.text_scale = name.into()
            }
            VisionToggle::Contrast => {
                next.contrast = if next.high_contrast() { "standard" } else { "high" }.into()
            }
        }
        self.error = None;
        self.message = None;
        Some(ThemeRequest::Vision(next))
    }

    /// The choice a Vision request in flight is applying, if any.
    pub fn vision_pending(&self) -> Option<&VisionChoice> {
        match self.pending.as_ref() {
            Some(ThemeRequest::Vision(choice)) => Some(choice),
            _ => None,
        }
    }

    /// Clears task 3.2's debounce/dedupe bookkeeping (never the one
    /// in-flight request id: that reply, whenever it lands, must still be
    /// recognised by `prepare_ahead_reply` rather than falling through to
    /// `accept`). Called whenever the theme carousel's own centred-item
    /// context stops applying -- leaving the page, or reloading the list.
    fn reset_prepare_ahead_debounce(&mut self) {
        self.prepare_ahead_watch = None;
        self.prepare_ahead_elapsed_ms = 0;
        self.prepare_ahead_sent_for = None;
        // A fresh `list` reply (from re-opening) always repopulates this
        // with that reply's own active theme's neighbours in `accept()`; a
        // queue left over from a now-stale list would otherwise persist
        // and warm the wrong themes.
        self.pending_neighbor_warms.clear();
    }

    pub fn back(&mut self) -> Option<ThemeRequest> {
        if self.pending.as_ref().is_some_and(ThemeRequest::is_activation) {
            return None; // A durable activation cannot be cancelled after dispatch.
        }
        self.pending = None; // A late reply must not reopen a dismissed view.
        self.pending_id = None;
        self.desired = None;
        self.fit_wanted = None;
        self.error = None;
        self.message = None;
        self.theme_pressed = None;
        self.background_pressed = None;
        self.reset_prepare_ahead_debounce();
        match self.page {
            ThemePage::List | ThemePage::Vision => {
                self.page = ThemePage::Controls;
                None
            }
            ThemePage::Controls => None,
        }
    }

    pub fn submitted(&mut self, request: ThemeRequest, id: u64) {
        self.pending = Some(request);
        self.pending_id = Some(id);
        self.error = None;
        self.message = None;
    }

    pub fn failed_to_submit(&mut self, error: &str) {
        self.error = Some(error.into());
    }

    pub fn accept(&mut self, reply: ThemeReply) -> bool {
        if self.pending_id != Some(reply.id) || self.pending.as_ref() != Some(&reply.request) {
            return false;
        }
        self.pending = None;
        self.pending_id = None;
        if let ThemeRequest::Fit { fit, .. } = &reply.request {
            self.accept_fit(fit, reply.result);
            return true;
        }
        if let ThemeRequest::Vision(_) = &reply.request {
            match reply.result {
                Ok(ThemeResponse::Vision { choice, activated }) => {
                    self.vision = choice;
                    self.vision_loaded = true;
                    // Every generation's identity includes the choice, so a
                    // remembered one for any theme would now be rejected.
                    self.known_generations.clear();
                    self.message = Some(if activated {
                        "Applied to every theme".into()
                    } else {
                        "Saved; applies with the next theme".into()
                    });
                    self.error = None;
                }
                Ok(_) => self.error = Some("wrong theme response".into()),
                Err(error) => self.error = Some(error),
            }
            return true;
        }
        let matches_desired = request_target(&reply.request).is_some_and(|(theme_id, background_id)| {
            self.desired
                .as_ref()
                .is_some_and(|desired| desired.theme_id == theme_id && desired.background_id.as_deref() == background_id)
        });
        match reply.result {
            Err(error) => {
                if matches_desired {
                    if let ThemeRequest::Activate { theme_id, background_id: None, .. } = &reply.request {
                        // The generation we activated against may be stale;
                        // force the next tap through a fresh Preview.
                        self.known_generations.remove(theme_id);
                    }
                    self.error = Some(error);
                    self.desired = None;
                }
                // A stale error (superseded by a later tap) is silently
                // discarded: `advance()` moves on to whatever is now
                // desired instead of reporting a failure for something no
                // longer wanted.
            }
            Ok(ThemeResponse::List(list)) => {
                if let Some(vision) = list.vision.clone() {
                    self.vision = vision;
                    self.vision_loaded = true;
                }
                if self.page == ThemePage::Vision {
                    // Opened only to read the saved vision choice.
                    self.list = Some(list);
                    self.error = None;
                    return true;
                }
                // Center the theme carousel on the currently active theme,
                // like Quattro's own picker opening on `selectedImage`.
                // With no durable choice yet, the shell shows the packaged
                // default theme: centre on it and load its backgrounds as
                // if it were active (the first slice when it is unknown).
                // It is not marked "Current theme", and tapping it applies
                // it durably.
                let shown_index = match list.active.id.as_deref() {
                    Some(active_id) => list.themes.iter().position(|entry| entry.id == active_id),
                    None => Some(
                        self.default_theme_name
                            .as_deref()
                            .and_then(|name| {
                                list.themes.iter().position(|entry| {
                                    entry.origin == ThemeOrigin::Builtin && entry.name == name
                                })
                            })
                            .unwrap_or(0),
                    )
                    .filter(|&index| index < list.themes.len()),
                };
                let active_index = shown_index.unwrap_or(0);
                self.theme_position = active_index as f64;
                // Queue the active theme's immediate neighbours for an
                // unconditional warm-up (see `pending_neighbor_warms`'s own
                // doc): whichever way a person scrolls first from the
                // theme they are already on, that first move is very
                // likely into one of these two.
                self.pending_neighbor_warms.clear();
                for neighbor in [active_index.checked_sub(1), active_index.checked_add(1)] {
                    if let Some(index) = neighbor {
                        if index < list.themes.len() && index != active_index {
                            self.pending_neighbor_warms.push_back(index);
                        }
                    }
                }
                // Load the active theme's own detail (backgrounds, for the
                // background carousel) right away, exactly like a re-tap
                // of it would -- see `Desired::already_active`'s own doc.
                let shown_id = list
                    .active
                    .id
                    .clone()
                    .or_else(|| shown_index.map(|index| list.themes[index].id.clone()));
                if let Some(shown_id) = shown_id {
                    self.desired = Some(Desired {
                        theme_id: shown_id,
                        background_id: None,
                        generation: None,
                        already_active: true,
                    });
                }
                self.list = Some(list);
                self.page = ThemePage::List;
                self.error = None;
            }
            Ok(ThemeResponse::Vision { .. }) => {}
            Ok(ThemeResponse::Preview(preview)) => {
                if !matches_desired {
                    // Superseded by a later tap; `advance()` (called by the
                    // caller right after `accept`) moves on to whatever is
                    // now desired instead.
                } else if preview.activated || self.desired.as_ref().is_some_and(|d| d.already_active) {
                    // Durably settled -- this theme/background is now (or
                    // already was) genuinely active. Only now does the
                    // background carousel switch to it.
                    self.message = if preview.activated {
                        if let Some(list) = self.list.as_mut() {
                            list.active.id = Some(preview.theme.id.clone());
                            list.active.generation = Some(preview.generation.clone());
                        }
                        let applied = if matches!(&reply.request, ThemeRequest::Activate {
                            background_id: Some(_), ..
                        }) { "Background applied to Home" } else { "Theme applied" };
                        Some(match preview.app_appearance.as_ref() {
                            Some(app) if !matches!(app.state.as_str(), "applied" | "deferred") => {
                                format!("{applied}; app reload {}", app.state)
                            }
                            _ => applied.into(),
                        })
                    } else {
                        None
                    };
                    self.background_position = preview
                        .backgrounds
                        .iter()
                        .position(|row| row.selected)
                        .unwrap_or(0) as f64;
                    self.fit = generation_fit(&preview.appearance_path);
                    self.preview = Some(*preview);
                    self.desired = None;
                    self.error = None;
                } else {
                    // The preview step of a real apply completed: the
                    // generation `Activate` needs is now known. The
                    // background carousel deliberately does not switch yet
                    // -- see `preview`'s own doc -- so this only records
                    // the generation.
                    if let Some(desired) = self.desired.as_mut() {
                        desired.generation = Some(preview.generation.clone());
                    }
                    self.error = None;
                }
            }
        }
        true
    }

    /// Builds the next request toward `desired`, if any, and if nothing is
    /// already in flight: a `Preview` while the generation is not yet
    /// known (or the target was already active and only needs its own
    /// detail (re)loaded), or the real `Activate` once it is. The caller
    /// submits this exactly like any other request (`main.rs`'s
    /// `submit_theme`); this is what actually drives coalescing -- called
    /// once right after every `accept()` that returns `true`, it is what
    /// lets a reply that turned out stale immediately move on to whatever
    /// is now desired instead, with no separate "cancel" step needed.
    pub fn advance(&mut self) -> Option<ThemeRequest> {
        if self.pending.is_some() {
            return None;
        }
        if let Some((fit, generation)) = self.fit_wanted.as_ref() {
            let theme_id = self.preview.as_ref()?.theme.id.clone();
            return Some(ThemeRequest::Fit {
                theme_id,
                expected_generation: generation.clone(),
                fit: fit.clone(),
            });
        }
        let desired = self.desired.as_ref()?;
        if desired.already_active && desired.generation.is_some() {
            return None; // settled by `accept` already; nothing further to do
        }
        Some(match &desired.generation {
            Some(generation) if !desired.already_active => ThemeRequest::Activate {
                theme_id: desired.theme_id.clone(),
                expected_generation: generation.clone(),
                background_id: desired.background_id.clone(),
            },
            _ => ThemeRequest::Preview {
                theme_id: desired.theme_id.clone(),
                background_id: desired.background_id.clone(),
            },
        })
    }

    /// Tapping the theme carousel's own already-centred slice: sets it as
    /// the newest desired target (superseding whatever was previously
    /// desired, in flight or not -- see `Desired`'s own doc) and returns
    /// the first step toward applying it, if nothing else is already in
    /// flight.
    pub fn tap_theme(&mut self, index: usize) -> Option<ThemeRequest> {
        let list = self.list.as_ref()?;
        let theme = list.themes.get(index)?;
        let already_active = list.active.id.as_deref() == Some(theme.id.as_str());
        // Browse-time warm-ups already learned this theme's generation
        // (`known_generations`) and left it prepared in both receivers. The
        // `Preview` step of a tap exists only to learn that generation, and
        // re-running it costs a second helper prepare (255-288 ms, board
        // evidence 2026-10-12) before the optimistic frame; go straight to
        // `Activate`. The helper re-derives the generation and rejects the
        // request ("theme changed since preview") if the cached value is
        // stale, in which case `accept` evicts it and the next tap previews.
        let known = (!already_active)
            .then(|| self.known_generations.get(&theme.id).cloned())
            .flatten();
        self.fit_wanted = None;
        self.desired = Some(Desired {
            theme_id: theme.id.clone(),
            background_id: None,
            generation: known,
            already_active,
        });
        self.error = None;
        self.advance()
    }

    /// Tapping the background carousel's own already-centred slice: same
    /// shape as `tap_theme`, for one of the *active* theme's own
    /// backgrounds (the only kind shown -- see `preview`'s own doc).
    /// A generation includes its background choice. Prepare this exact
    /// selection first; the current preview's generation belongs to the
    /// previous background and cannot authorize a different one.
    pub fn tap_background(&mut self, index: usize) -> Option<ThemeRequest> {
        let preview = self.preview.as_ref()?;
        let background = preview.backgrounds.get(index)?;
        if background.kind == BackgroundKind::Video {
            self.error = Some("Video playback is not available in this shell".into());
            return None;
        }
        if background.selected {
            return None; // already the active background: nothing to do
        }
        self.fit_wanted = None;
        self.desired = Some(Desired {
            theme_id: preview.theme.id.clone(),
            background_id: Some(background.id.clone()),
            generation: None,
            already_active: false, // a background change always needs a real Activate
        });
        self.error = None;
        self.advance()
    }

    /// Tapping the "Backgrounds" heading: ask for the active background in
    /// the next fit mode. Returns the first step (a `Preview`; `advance`
    /// supplies the `Activate` once its generation is known). Nothing
    /// happens while another request is in flight or before the active
    /// theme's detail has loaded.
    pub fn cycle_fit(&mut self) -> Option<ThemeRequest> {
        if self.pending.is_some() {
            return None;
        }
        self.preview.as_ref()?;
        self.fit_wanted = Some((FitMode::next_name(&self.fit).to_owned(), None));
        self.desired = None;
        self.error = None;
        self.advance()
    }

    /// The reply to a `ThemeRequest::Fit`: the preview step records the
    /// generation to activate; the activation settles the new fit.
    fn accept_fit(&mut self, fit: &str, result: Result<ThemeResponse, String>) {
        let wanted = self.fit_wanted.as_ref().is_some_and(|(name, _)| name == fit);
        match result {
            Err(error) => {
                if wanted {
                    self.fit_wanted = None;
                    self.error = Some(error);
                }
            }
            Ok(ThemeResponse::Preview(preview)) if wanted && preview.activated => {
                if let Some(list) = self.list.as_mut() {
                    list.active.id = Some(preview.theme.id.clone());
                    list.active.generation = Some(preview.generation.clone());
                }
                // The generation identity changed with the fit: a cached
                // pre-fit generation for this theme would be rejected.
                self.known_generations.remove(&preview.theme.id);
                self.message = Some(format!("Background fit: {fit}"));
                self.fit = fit.to_owned();
                self.background_position = preview
                    .backgrounds
                    .iter()
                    .position(|row| row.selected)
                    .unwrap_or(0) as f64;
                self.preview = Some(*preview);
                self.fit_wanted = None;
                self.error = None;
            }
            Ok(ThemeResponse::Preview(preview)) if wanted => {
                if let Some((_, generation)) = self.fit_wanted.as_mut() {
                    *generation = Some(preview.generation.clone());
                }
                self.error = None;
            }
            Ok(_) => {}
        }
    }

    /// Task 3.2: called once per tick while the theme carousel is shown.
    /// `centered` is the carousel's committed index when it is not
    /// mid-drag/coast/settle, `None` otherwise. Returns a warm-up request
    /// once the same index has stayed centred, at rest, for
    /// `PREPARE_AHEAD_DEBOUNCE_MS` -- the caller submits it directly to the
    /// `ThemeWorker` (bypassing `submitted`/`self.pending`, since this must
    /// never be mistaken for a real navigational Preview) and reports the
    /// id back via `prepare_ahead_submitted`.
    ///
    /// This reuses the existing `Preview` request/action rather than adding
    /// a new one: `tools/theme_catalog.py`'s `preview` action already calls
    /// `prepare_only()` (task 3.1a) whenever `--rust-socket`/`--deck-socket`
    /// are configured, so a discarded `Preview` reply here has exactly the
    /// warming side effect this task wants, with no new protocol.
    /// Admission is paused during either row's contact, coast or settle.
    /// Keep queued neighbors and an executing request intact; a reply may
    /// finish while paused, but cannot admit its successor. A new settled
    /// center must earn its own dwell after movement ends.
    pub fn poll_prepare_ahead_at_rest(
        &mut self,
        elapsed_ms: u32,
        centered: Option<usize>,
        both_rows_at_rest: bool,
    ) -> Option<(usize, ThemeRequest)> {
        if !both_rows_at_rest {
            self.prepare_ahead_watch = None;
            self.prepare_ahead_elapsed_ms = 0;
            return None;
        }
        self.poll_prepare_ahead(elapsed_ms, centered)
    }

    pub fn poll_prepare_ahead(
        &mut self,
        elapsed_ms: u32,
        centered: Option<usize>,
    ) -> Option<(usize, ThemeRequest)> {
        if let Some(index) = centered {
            if self.prepare_ahead_watch != Some(index) {
                self.prepare_ahead_watch = Some(index);
                self.prepare_ahead_elapsed_ms = elapsed_ms;
            } else {
                self.prepare_ahead_elapsed_ms = self.prepare_ahead_elapsed_ms.saturating_add(elapsed_ms);
            }
        } else {
            self.prepare_ahead_watch = None;
            self.prepare_ahead_elapsed_ms = 0;
        }
        if self.prepare_ahead_inflight.is_some() {
            return None;
        }
        if self.pending.is_some() {
            // A real, explicit request (a tap-apply's own Preview or
            // Activate) is awaiting its reply. `ThemeWorker` processes
            // requests strictly in submission order, and each receiver
            // keeps only its single most-recently-prepared candidate
            // (`AppearanceReceiver::prepared`/`card-shell`'s own
            // `service.prepared`) -- so a warm-up submitted now could
            // reach that same slot *after* the real request's own
            // "prepare" and silently replace it with an unrelated theme's
            // generation before its reply is even back, exactly the race
            // that made an otherwise-already-prepared apply miss its own
            // optimistic show (board evidence, 2026-09-26). Warming simply
            // resumes the next tick once `pending` clears; the dwell clock
            // above keeps accumulating in the meantime, so nothing already
            // waited out is lost.
            return None;
        }
        if let Some(index) = centered {
            if self.prepare_ahead_sent_for != Some(index) {
                if let Some(request) = self.warm_request_for(index) {
                    // Reserve the free slot for the latest settled center
                    // throughout its dwell. A neighbor admitted now could
                    // delay this candidate and replace its prepared slot.
                    if self.prepare_ahead_elapsed_ms < PREPARE_AHEAD_DEBOUNCE_MS {
                        return None;
                    }
                    return Some((index, request));
                }
            }
        }
        // Nothing dwell-driven is due right now: spend the one free slot on
        // the neighbour queue instead (see `pending_neighbor_warms`'s own
        // doc), so it can never delay whatever a person is actually
        // settled on -- that branch above always takes priority.
        while let Some(index) = self.pending_neighbor_warms.pop_front() {
            if self.prepare_ahead_sent_for == Some(index) {
                continue;
            }
            if let Some(request) = self.warm_request_for(index) {
                return Some((index, request));
            }
        }
        None
    }

    fn warm_request_for(&self, index: usize) -> Option<ThemeRequest> {
        let list = self.list.as_ref()?;
        let theme = list.themes.get(index)?;
        if list.active.id.as_deref() == Some(theme.id.as_str()) {
            return None; // already active: nothing to warm
        }
        Some(ThemeRequest::Preview {
            theme_id: theme.id.clone(),
            background_id: None,
        })
    }

    /// Records that `poll_prepare_ahead`'s request for `index` was actually
    /// submitted to the worker as request `id`.
    pub fn prepare_ahead_submitted(&mut self, index: usize, id: u64) {
        self.prepare_ahead_sent_for = Some(index);
        self.prepare_ahead_inflight = Some(id);
    }

    /// True (and clears the in-flight slot) when `reply` is this chooser's
    /// own warm-up call. `main.rs` checks this before `accept`, so a
    /// warm-up reply is always discarded from the chooser's own navigation
    /// state -- it is never mistaken for the (structurally identical)
    /// reply to a real, tap-driven Preview request, because `submitted`/
    /// `self.pending`/`self.pending_id` were never touched for it in the
    /// first place. The reply's own generation, if any, is still worth
    /// keeping -- see `record_known_generation`.
    pub fn prepare_ahead_reply(&mut self, reply: &ThemeReply) -> bool {
        if self.prepare_ahead_inflight == Some(reply.id) {
            self.prepare_ahead_inflight = None;
            true
        } else {
            false
        }
    }

    /// Remembers a warm-up reply's own `(theme_id, generation)` in
    /// `known_generations`, even though the reply itself is otherwise
    /// entirely discarded (`prepare_ahead_reply`). This is what lets the
    /// optimistic-apply pre-render trigger (`main.rs`) target a centred,
    /// already-warmed-but-not-yet-tapped theme without a fresh Preview
    /// round trip.
    pub fn record_known_generation(&mut self, theme_id: &str, generation: &str) {
        self.known_generations
            .insert(theme_id.to_owned(), generation.to_owned());
    }

    /// Which theme-carousel slice, if any, a tap-apply currently pending
    /// (`self.pending`) targets -- painted with a brief, in-place busy
    /// indicator (`render.rs`'s own live overlay) rather than blocking the
    /// carousel. `None` whenever the pending request is a background
    /// selection instead (`background_id.is_some()`) or nothing is pending.
    pub fn applying_theme_index(&self) -> Option<usize> {
        let (theme_id, background_id) = request_target(self.pending.as_ref()?)?;
        if background_id.is_some() {
            return None;
        }
        self.list
            .as_ref()?
            .themes
            .iter()
            .position(|entry| entry.id == theme_id)
    }

    /// Same, for the background carousel: which of the active theme's own
    /// backgrounds a pending background-selection tap-apply targets.
    pub fn applying_background_index(&self) -> Option<usize> {
        let (_, background_id) = request_target(self.pending.as_ref()?)?;
        let background_id = background_id?;
        self.preview
            .as_ref()?
            .backgrounds
            .iter()
            .position(|row| row.id == background_id)
    }

    /// Header (Back/Close) hits. Everything else belongs to a carousel band
    /// now -- `theme_carousel::Carousel::up` resolves those touches
    /// directly (see `main.rs`), returning `CarouselOutcome::Consumed` for
    /// anything that should not fall through to here.
    pub fn hit(&self, start: (f64, f64), end: (f64, f64), width: u32, height: u32) -> Option<ThemeIntent> {
        let w = f64::from(width);
        let header_h = chooser_layout(width, height).header_hit_h;
        let dx = end.0 - start.0;
        let dy = end.1 - start.1;
        if dx.abs() > 18.0 || dy.abs() > 18.0 {
            return None;
        }
        if self.pending.as_ref().is_some_and(ThemeRequest::is_activation) {
            return None;
        }
        match self.page {
            ThemePage::Controls => {
                if !(104.0..162.0).contains(&end.1) {
                    None
                } else if end.0 > w - 185.0 {
                    Some(ThemeIntent::Open)
                } else if end.0 > w - 310.0 {
                    Some(ThemeIntent::OpenVision)
                } else {
                    None
                }
            }
            ThemePage::Vision => {
                if end.1 < header_h {
                    return if end.0 < 190.0 {
                        Some(ThemeIntent::Back)
                    } else if end.0 > w - 150.0 {
                        Some(ThemeIntent::Close)
                    } else {
                        None
                    };
                }
                let lay = vision_layout(w, self.vision.text_scale_value());
                let inside = |(x, y, rw, rh): (f64, f64, f64, f64), p: (f64, f64)| {
                    (x..x + rw).contains(&p.0) && (y..y + rh).contains(&p.1)
                };
                // A step counts only when the touch starts and ends on it.
                if let Some(step) = (0..4).find(|&i| inside(lay.segments[i], start) && inside(lay.segments[i], end)) {
                    return Some(ThemeIntent::Vision(VisionToggle::TextSize(step)));
                }
                if inside(lay.contrast_card, end) {
                    return Some(ThemeIntent::Vision(VisionToggle::Contrast));
                }
                None
            }
            ThemePage::List => {
                let lay = self.layout(width, height);
                let same = |grid: Option<Grid>| grid.and_then(|g| g.hit(start).filter(|&i| g.hit(end) == Some(i)));
                if let Some(index) = same(lay.theme_grid) {
                    return Some(ThemeIntent::Theme(index));
                }
                if let Some(index) = same(lay.background_grid) {
                    return Some(ThemeIntent::Background(index));
                }
                // The "Backgrounds" heading (and the fit mode it names).
                let (hx, hy) = lay.backgrounds_heading;
                if end.0 >= hx
                    && end.0 < hx + 260.0
                    && end.1 >= hy - 6.0
                    && end.1 < hy + 34.0
                    && start.0 >= hx
                    && start.0 < hx + 260.0
                    && start.1 >= hy - 6.0
                    && start.1 < hy + 34.0
                {
                    return Some(ThemeIntent::Fit);
                }
                if end.1 < header_h {
                    return if end.0 < 190.0 {
                        Some(ThemeIntent::Back)
                    } else if end.0 > w - 150.0 {
                        Some(ThemeIntent::Close)
                    } else {
                        None
                    };
                }
                None
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::theme_catalog::{
        ActiveTheme, AppAppearance, BackgroundChoice, Compatibility, ThemeEntry, ThemeOrigin,
    };
    use std::{collections::BTreeMap, path::PathBuf};

    fn id(ch: char) -> String {
        std::iter::repeat_n(ch, 24).collect()
    }
    fn preview() -> ThemePreview {
        ThemePreview {
            theme: ThemeEntry {
                id: id('a'),
                name: "Night".into(),
                label: "Night".into(),
                origin: ThemeOrigin::Builtin,
                preview_path: None,
            },
            generation: id('b'),
            appearance_path: PathBuf::from("/tmp/generation/appearance.json"),
            palette: BTreeMap::from([("background".into(), "#101020".into())]),
            icon_theme: None,
            backgrounds: vec![
                BackgroundChoice {
                    id: id('c'),
                    label: "Still".into(),
                    kind: BackgroundKind::Image,
                    path: PathBuf::from("/tmp/still.png"),
                    selected: true,
                    decode_status: "unverified".into(),
                },
                BackgroundChoice {
                    id: id('d'),
                    label: "Motion".into(),
                    kind: BackgroundKind::Video,
                    path: PathBuf::from("/tmp/video.webm"),
                    selected: false,
                    decode_status: "unverified".into(),
                },
            ],
            compatibility: Compatibility {
                adapted: vec![],
                applied: vec![],
                unavailable: vec![],
                unknown: vec![],
            },
            activated: false,
            app_appearance: None,
        }
    }

    fn theme_list(active_index: Option<usize>) -> ThemeList {
        theme_list_of(3, active_index)
    }

    fn theme_list_of(count: usize, active_index: Option<usize>) -> ThemeList {
        let themes: Vec<ThemeEntry> = (0..count)
            .map(|index| {
                let mut theme = preview().theme;
                theme.id = std::iter::repeat_n(
                    char::from_digit(index as u32, 16).expect("test fixture stays under 16 themes"),
                    24,
                )
                .collect();
                theme
            })
            .collect();
        ThemeList {
            active: ActiveTheme {
                id: active_index.map(|index| themes[index].id.clone()),
                generation: None,
            },
            themes,
            vision: None,
        }
    }

    /// Drives a `List` reply through the same `submitted`/`accept` path
    /// `main.rs` uses for a real list load, so the neighbour queue (and, for
    /// the active theme, `desired`) is populated the way it would be on the
    /// board, not poked directly.
    fn load_list(view: &mut ThemeView, count: usize, active_index: Option<usize>) {
        let list = theme_list_of(count, active_index);
        view.submitted(ThemeRequest::List, 1);
        assert!(view.accept(ThemeReply {
            id: 1,
            request: ThemeRequest::List,
            result: Ok(ThemeResponse::List(list)),
        }));
    }

    #[test]
    fn tap_theme_on_a_cold_slice_previews_then_activates_and_switches_the_background_carousel() {
        // The full tap-to-apply round trip for a theme the receiver has
        // never prepared before (task: tap-to-apply, 2026-09-25, user
        // decision: "tap theme in the theme picker, apply immediately").
        // `known_generations` starts empty, so `tap_theme` must send a
        // `Preview` first -- there is no way to build a valid `Activate`
        // (it needs `expected_generation`) without first learning it.
        let mut view = ThemeView::default();
        load_list(&mut view, 3, Some(0));
        // The just-loaded active theme (index 0) has its own `desired`
        // pending from `accept`'s own List handling; settle it out of the
        // way first so it does not interfere with the tap under test.
        let settle = view.advance().expect("active theme detail loads itself");
        view.submitted(settle.clone(), 50);
        assert!(view.accept(ThemeReply {
            id: 50,
            request: settle,
            result: Ok(ThemeResponse::Preview(Box::new(preview()))),
        }));
        assert_eq!(view.advance(), None, "already-active target needs no Activate");

        let target_id = view.list.as_ref().unwrap().themes[1].id.clone();
        let request = view.tap_theme(1).expect("index 1 exists");
        assert_eq!(
            request,
            ThemeRequest::Preview {
                theme_id: target_id.clone(),
                background_id: None,
            },
            "a theme with no known generation previews first"
        );
        assert_eq!(view.applying_theme_index(), None, "not submitted yet");
        view.submitted(request.clone(), 1);
        assert_eq!(view.applying_theme_index(), Some(1));

        let mut candidate = preview();
        candidate.theme.id = target_id.clone();
        candidate.generation = id('e');
        assert!(view.accept(ThemeReply {
            id: 1,
            request,
            result: Ok(ThemeResponse::Preview(Box::new(candidate))),
        }));
        // The generation is now known, but nothing has actually activated
        // yet -- the background carousel must not have switched.
        assert_eq!(view.preview.as_ref().unwrap().theme.id, id('a'));

        let activate = view.advance().expect("generation now known");
        assert_eq!(
            activate,
            ThemeRequest::Activate {
                theme_id: target_id.clone(),
                expected_generation: id('e'),
                background_id: None,
            }
        );
        view.submitted(activate.clone(), 2);
        assert_eq!(view.applying_theme_index(), Some(1));

        let mut activated = preview();
        activated.theme.id = target_id.clone();
        activated.generation = id('e');
        activated.activated = true;
        assert!(view.accept(ThemeReply {
            id: 2,
            request: activate,
            result: Ok(ThemeResponse::Preview(Box::new(activated))),
        }));
        assert_eq!(view.applying_theme_index(), None, "settled");
        assert_eq!(
            view.preview.as_ref().unwrap().theme.id,
            target_id,
            "the background carousel now reflects the newly-active theme"
        );
        assert_eq!(view.message.as_deref(), Some("Theme applied"));
        assert_eq!(view.advance(), None);
        assert_eq!(view.list.as_ref().unwrap().active.id.as_deref(), Some(target_id.as_str()));
        assert_eq!(view.list.as_ref().unwrap().active.generation.as_deref(), Some(id('e').as_str()));
        // The original theme must now activate again rather than being treated as current.
        view.tap_theme(0).unwrap();
        assert!(!view.desired.as_ref().unwrap().already_active);
    }

    #[test]
    fn tap_theme_on_a_warmed_slice_skips_the_preview_and_activates_directly() {
        // Task 6.6 (board 2026-10-12): a tap on a theme the browse-time warm
        // already prepared used to send a second `Preview` (255-288 ms, a
        // second `appearance-prepare-accepted`) before the `Activate`.
        let mut view = ThemeView::default();
        load_list(&mut view, 3, Some(0));
        let settle = view.advance().expect("active theme detail loads itself");
        view.submitted(settle.clone(), 50);
        assert!(view.accept(ThemeReply {
            id: 50,
            request: settle,
            result: Ok(ThemeResponse::Preview(Box::new(preview()))),
        }));
        let target_id = view.list.as_ref().unwrap().themes[1].id.clone();
        view.record_known_generation(&target_id, &id('e'));

        let request = view.tap_theme(1).expect("index 1 exists");
        assert_eq!(
            request,
            ThemeRequest::Activate {
                theme_id: target_id.clone(),
                expected_generation: id('e'),
                background_id: None,
            },
            "a warmed theme goes straight to Activate"
        );
        view.submitted(request.clone(), 2);
        assert_eq!(view.applying_theme_index(), Some(1));

        let mut activated = preview();
        activated.theme.id = target_id.clone();
        activated.generation = id('e');
        activated.activated = true;
        assert!(view.accept(ThemeReply {
            id: 2,
            request,
            result: Ok(ThemeResponse::Preview(Box::new(activated))),
        }));
        assert_eq!(view.message.as_deref(), Some("Theme applied"));
        assert_eq!(view.advance(), None);
        assert_eq!(view.list.as_ref().unwrap().active.id.as_deref(), Some(target_id.as_str()));
    }

    #[test]
    fn a_rejected_direct_activate_evicts_the_known_generation_so_the_next_tap_previews() {
        let mut view = ThemeView::default();
        load_list(&mut view, 3, Some(0));
        let settle = view.advance().expect("active theme detail loads itself");
        view.submitted(settle.clone(), 50);
        assert!(view.accept(ThemeReply {
            id: 50,
            request: settle,
            result: Ok(ThemeResponse::Preview(Box::new(preview()))),
        }));
        let target_id = view.list.as_ref().unwrap().themes[1].id.clone();
        view.record_known_generation(&target_id, &id('e'));

        let request = view.tap_theme(1).unwrap();
        assert!(matches!(request, ThemeRequest::Activate { .. }));
        view.submitted(request.clone(), 2);
        assert!(view.accept(ThemeReply {
            id: 2,
            request,
            result: Err("theme changed since preview; preview it again".into()),
        }));
        assert!(view.error.is_some());
        assert!(!view.known_generations.contains_key(&target_id));
        assert_eq!(
            view.tap_theme(1),
            Some(ThemeRequest::Preview { theme_id: target_id, background_id: None }),
            "the retry learns a fresh generation"
        );
    }

    #[test]
    fn tap_theme_on_the_active_slice_ignores_a_known_generation() {
        let mut view = ThemeView::default();
        load_list(&mut view, 3, Some(0));
        let active_id = view.list.as_ref().unwrap().active.id.clone().unwrap();
        view.record_known_generation(&active_id, &id('e'));
        assert_eq!(
            view.tap_theme(0),
            Some(ThemeRequest::Preview { theme_id: active_id, background_id: None })
        );
    }

    #[test]
    fn tap_theme_on_the_already_active_slice_never_sends_an_activate() {
        let mut view = ThemeView::default();
        load_list(&mut view, 3, Some(0));
        let active_id = view.list.as_ref().unwrap().active.id.clone().unwrap();

        let request = view.tap_theme(0).expect("index 0 exists");
        assert_eq!(
            request,
            ThemeRequest::Preview {
                theme_id: active_id.clone(),
                background_id: None,
            }
        );
        view.submitted(request.clone(), 9);
        let mut own_detail = preview();
        own_detail.theme.id = active_id.clone();
        assert!(view.accept(ThemeReply {
            id: 9,
            request,
            result: Ok(ThemeResponse::Preview(Box::new(own_detail))),
        }));
        // `already_active` settles straight from the `Preview` reply --
        // never needs (or sends) an `Activate` at all.
        assert_eq!(view.advance(), None);
        assert_eq!(view.preview.as_ref().unwrap().theme.id, active_id);
    }

    /// `preview()` (above) has only one non-video background, and it is
    /// already `selected` -- no valid target for a *successful* background
    /// tap. This variant adds a second, unselected still specifically for
    /// that case.
    fn preview_with_an_unselected_still() -> ThemePreview {
        let mut view = preview();
        view.backgrounds.push(BackgroundChoice {
            id: id('e'),
            label: "Dawn".into(),
            kind: BackgroundKind::Image,
            path: PathBuf::from("/tmp/dawn.png"),
            selected: false,
            decode_status: "unverified".into(),
        });
        view
    }

    #[test]
    fn background_apply_uses_the_selected_background_generation_and_waits_for_commit() {
        let mut view = ThemeView {
            page: ThemePage::List,
            preview: Some(preview_with_an_unselected_still()),
            ..ThemeView::default()
        };
        let request = view.tap_background(2).unwrap();
        assert_eq!(request, ThemeRequest::Preview {
            theme_id: id('a'), background_id: Some(id('e')),
        });
        view.submitted(request.clone(), 1);
        assert_eq!(view.applying_background_index(), Some(2));
        let mut candidate = preview_with_an_unselected_still();
        candidate.generation = id('f'); // Background choice changes the generation.
        candidate.backgrounds[0].selected = false;
        candidate.backgrounds[2].selected = true;
        view.accept(ThemeReply { id: 1, request,
            result: Ok(ThemeResponse::Preview(Box::new(candidate.clone()))) });
        assert!(view.preview.as_ref().unwrap().backgrounds[0].selected);
        assert!(view.message.is_none());
        let activate = view.advance().unwrap();
        assert_eq!(activate, ThemeRequest::Activate {
            theme_id: id('a'), expected_generation: id('f'), background_id: Some(id('e')),
        });
        view.submitted(activate.clone(), 2);
        candidate.activated = true;
        view.accept(ThemeReply { id: 2, request: activate,
            result: Ok(ThemeResponse::Preview(Box::new(candidate))) });
        assert!(view.preview.as_ref().unwrap().backgrounds[2].selected);
        assert_eq!(view.message.as_deref(), Some("Background applied to Home"));
        assert_eq!(view.applying_background_index(), None);
        assert!(view.advance().is_none());
    }

    #[test]
    fn fit_names_agree_across_the_standalone_catalog_module() {
        assert_eq!(crate::theme_catalog::FIT_NAMES, FitMode::NAMES);
    }

    #[test]
    fn tapping_the_backgrounds_heading_is_the_fit_intent_and_only_there() {
        let view = ThemeView {
            page: ThemePage::List,
            ..ThemeView::default()
        };
        let (w, h) = (568, 1232);
        let (hx, hy) = chooser_layout(w, h).backgrounds_heading;
        let tap = |x: f64, y: f64| view.hit((x, y), (x, y), w, h);
        assert_eq!(tap(hx + 20.0, hy + 10.0), Some(ThemeIntent::Fit));
        assert_eq!(tap(hx + 400.0, hy + 10.0), None);
        assert_eq!(tap(hx + 20.0, hy + 80.0), None);
    }

    #[test]
    fn cycling_fit_previews_then_activates_the_new_generation_and_settles_it() {
        let mut view = ThemeView {
            page: ThemePage::List,
            preview: Some(preview()),
            ..ThemeView::default()
        };
        assert_eq!(view.fit, "crop");
        let request = view.cycle_fit().unwrap();
        assert_eq!(request, ThemeRequest::Fit {
            theme_id: id('a'), expected_generation: None, fit: "fit".into(),
        });
        // One at a time: nothing further while that request is in flight.
        view.submitted(request.clone(), 1);
        assert!(view.cycle_fit().is_none());
        let mut candidate = preview();
        candidate.generation = id('f'); // The fit is part of the generation identity.
        view.accept(ThemeReply { id: 1, request,
            result: Ok(ThemeResponse::Preview(Box::new(candidate.clone()))) });
        assert_eq!(view.preview.as_ref().unwrap().generation, id('b'));
        assert_eq!(view.fit, "crop"); // Not settled until the durable step.
        let activate = view.advance().unwrap();
        assert_eq!(activate, ThemeRequest::Fit {
            theme_id: id('a'), expected_generation: Some(id('f')), fit: "fit".into(),
        });
        assert!(activate.is_activation());
        view.submitted(activate.clone(), 2);
        candidate.activated = true;
        view.known_generations.insert(id('a'), id('b'));
        view.accept(ThemeReply { id: 2, request: activate,
            result: Ok(ThemeResponse::Preview(Box::new(candidate))) });
        assert_eq!(view.fit, "fit");
        assert_eq!(view.preview.as_ref().unwrap().generation, id('f'));
        assert_eq!(view.message.as_deref(), Some("Background fit: fit"));
        assert!(!view.known_generations.contains_key(&id('a')));
        assert!(view.advance().is_none());
        // The next tap continues the cycle from the settled mode.
        assert!(matches!(view.cycle_fit(), Some(ThemeRequest::Fit { fit, .. }) if fit == "center"));
    }

    #[test]
    fn a_failed_fit_change_keeps_the_old_fit_and_reports_the_error() {
        let mut view = ThemeView {
            page: ThemePage::List,
            preview: Some(preview()),
            fit: "fill".into(),
            ..ThemeView::default()
        };
        let request = view.cycle_fit().unwrap();
        assert!(matches!(&request, ThemeRequest::Fit { fit, .. } if fit == "solid"));
        view.submitted(request.clone(), 1);
        view.accept(ThemeReply { id: 1, request, result: Err("helper failed".into()) });
        assert_eq!(view.fit, "fill");
        assert_eq!(view.error.as_deref(), Some("helper failed"));
        assert!(view.advance().is_none());
    }

    #[test]
    fn a_theme_or_background_tap_supersedes_a_pending_fit_change() {
        let mut view = ThemeView {
            page: ThemePage::List,
            preview: Some(preview_with_an_unselected_still()),
            list: Some(theme_list(Some(0))),
            ..ThemeView::default()
        };
        view.cycle_fit().unwrap();
        assert!(view.fit_wanted.is_some());
        view.tap_background(2).unwrap();
        assert!(view.fit_wanted.is_none());
        assert!(view.desired.is_some());
    }

    #[test]
    fn vision_sits_left_of_themes_in_the_settings_header() {
        let view = ThemeView::default();
        for (w, h) in [(568u32, 1232u32), (1280, 800)] {
            let tap = |x: f64, y: f64| view.hit((x, y), (x, y), w, h);
            let w = f64::from(w);
            assert_eq!(tap(w - 100.0, 120.0), Some(ThemeIntent::Open));
            assert_eq!(tap(w - 250.0, 120.0), Some(ThemeIntent::OpenVision));
            assert_eq!(tap(w - 400.0, 120.0), None);
            assert_eq!(tap(w - 250.0, 200.0), None);
        }
    }

    fn vision_list(choice: Option<VisionChoice>) -> ThemeList {
        ThemeList { vision: choice, ..theme_list(Some(0)) }
    }

    fn open_vision_page(view: &mut ThemeView, choice: Option<VisionChoice>) {
        let request = view.open_vision();
        assert_eq!(request, ThemeRequest::List);
        view.submitted(request.clone(), 1);
        assert!(view.accept(ThemeReply {
            id: 1,
            request,
            result: Ok(ThemeResponse::List(vision_list(choice))),
        }));
    }

    #[test]
    fn opening_vision_reads_the_saved_choice_and_stays_on_the_page() {
        let mut view = ThemeView::default();
        let large = VisionChoice { text_scale: "large".into(), contrast: "standard".into() };
        open_vision_page(&mut view, Some(large.clone()));
        assert_eq!(view.page, ThemePage::Vision);
        assert!(view.vision_loaded);
        assert_eq!(view.vision, large);
        // Not the chooser's own list handling: no theme detail is requested.
        assert!(view.desired.is_none());
        assert!(view.advance().is_none());
        assert_eq!(view.back(), None);
        assert_eq!(view.page, ThemePage::Controls);
    }

    #[test]
    fn a_helper_without_vision_support_leaves_the_toggles_inert() {
        let mut view = ThemeView::default();
        open_vision_page(&mut view, None);
        assert!(!view.vision_loaded);
        assert!(view.toggle_vision(VisionToggle::TextSize(3)).is_none());
    }

    fn centre((x, y, w, h): (f64, f64, f64, f64)) -> (f64, f64) {
        (x + w / 2.0, y + h / 2.0)
    }

    #[test]
    fn the_vision_layout_never_clips_and_keeps_the_tap_floor_at_every_step() {
        for (w, h) in [(568.0, 1232.0), (1232.0, 568.0), (1280.0, 800.0)] {
            for scale in crate::theme_catalog::TEXT_SCALE_VALUES {
                let lay = vision_layout(w, scale);
                let rects = lay.segments.iter().copied().chain([lay.text_card, lay.contrast_card]);
                for (x, y, rw, rh) in rects {
                    assert!(x >= 0.0 && x + rw <= w, "{w}x{h} at {scale}: inside the width");
                    assert!(rh >= VISION_TAP_MIN, "{w}x{h} at {scale}: 48 dp tap floor");
                    assert!(y + rh <= h, "{w}x{h} at {scale}: inside the height");
                }
                // A segment holds its "200%" label (DejaVu Sans Bold is under
                // 0.7 em per glyph) and its line.
                let (_, _, sw, sh) = lay.segments[0];
                assert!(sw >= 4.0 * 0.7 * 18.0 * scale, "{w}x{h} at {scale}: segment width {sw}");
                assert!(sh >= 18.0 * scale * 1.35, "{w}x{h} at {scale}: segment height");
                // Segments sit inside the text card and do not overlap.
                let (tx, ty, tw, th) = lay.text_card;
                for pair in lay.segments.windows(2) {
                    assert!(pair[0].0 + pair[0].2 <= pair[1].0);
                }
                for (x, y, rw, rh) in lay.segments {
                    assert!(x >= tx && x + rw <= tx + tw && y >= ty && y + rh <= ty + th);
                }
                assert!(lay.bottom <= h, "{w}x{h} at {scale}: page fits ({})", lay.bottom);
            }
        }
        // The landscape panel puts the two cards side by side, portrait stacks them.
        assert_eq!(vision_layout(1232.0, 2.0).contrast_card.1, vision_layout(1232.0, 2.0).text_card.1);
        assert!(vision_layout(568.0, 2.0).contrast_card.1 > vision_layout(568.0, 2.0).text_card.1);
    }

    #[test]
    fn each_text_step_and_the_contrast_card_send_one_request() {
        let mut view = ThemeView::default();
        open_vision_page(&mut view, Some(VisionChoice::default()));
        let (w, h) = (568u32, 1232u32);
        let lay = vision_layout(w as f64, 1.0);
        let tap = |view: &ThemeView, p: (f64, f64)| view.hit(p, p, w, h);
        for step in 0..4 {
            assert_eq!(tap(&view, centre(lay.segments[step])),
                       Some(ThemeIntent::Vision(VisionToggle::TextSize(step))));
        }
        assert_eq!(tap(&view, centre(lay.contrast_card)), Some(ThemeIntent::Vision(VisionToggle::Contrast)));
        // A drag from one step to another chooses neither.
        let (a, b) = (centre(lay.segments[0]), centre(lay.segments[2]));
        assert_eq!(view.hit(a, b, w, h), None);
        // Below the cards is dead.
        assert_eq!(tap(&view, (200.0, lay.bottom + 10.0)), None);
        // The saved step is not re-applied.
        assert!(view.toggle_vision(VisionToggle::TextSize(0)).is_none());
        assert!(view.toggle_vision(VisionToggle::TextSize(4)).is_none());

        let request = view.toggle_vision(VisionToggle::TextSize(3)).unwrap();
        assert_eq!(request, ThemeRequest::Vision(VisionChoice {
            text_scale: "largest".into(), contrast: "standard".into(),
        }));
        assert!(request.is_activation());
        view.submitted(request.clone(), 2);
        // In flight: no second request, and the page cannot be tapped.
        assert!(view.toggle_vision(VisionToggle::Contrast).is_none());
        assert_eq!(view.vision_pending().map(|c| c.text_scale.as_str()), Some("largest"));
        view.known_generations.insert(id('a'), id('b'));
        let ThemeRequest::Vision(choice) = request.clone() else { unreachable!() };
        assert!(view.accept(ThemeReply {
            id: 2,
            request,
            result: Ok(ThemeResponse::Vision { choice, activated: true }),
        }));
        assert_eq!(view.vision.text_step(), 3);
        assert_eq!(view.vision.text_scale_value(), 2.0);
        assert_eq!(view.message.as_deref(), Some("Applied to every theme"));
        // Every generation identity changed with the choice.
        assert!(view.known_generations.is_empty());
        // Hit-testing now follows the 200% layout.
        let big = vision_layout(w as f64, 2.0);
        assert_eq!(tap(&view, centre(big.contrast_card)), Some(ThemeIntent::Vision(VisionToggle::Contrast)));
        assert_eq!(view.toggle_vision(VisionToggle::Contrast), Some(ThemeRequest::Vision(VisionChoice {
            text_scale: "largest".into(), contrast: "high".into(),
        })));
    }

    #[test]
    fn a_failed_vision_change_keeps_the_saved_choice_and_says_why() {
        let mut view = ThemeView::default();
        open_vision_page(&mut view, Some(VisionChoice::default()));
        let request = view.toggle_vision(VisionToggle::TextSize(2)).unwrap();
        view.submitted(request.clone(), 2);
        assert!(view.accept(ThemeReply { id: 2, request, result: Err("theme command failed".into()) }));
        assert_eq!(view.vision, VisionChoice::default());
        assert_eq!(view.error.as_deref(), Some("theme command failed"));
        assert!(view.vision_pending().is_none());
    }

    #[test]
    fn a_vision_choice_saved_with_no_active_theme_says_when_it_applies() {
        let mut view = ThemeView::default();
        open_vision_page(&mut view, Some(VisionChoice::default()));
        let request = view.toggle_vision(VisionToggle::TextSize(1)).unwrap();
        view.submitted(request.clone(), 2);
        let ThemeRequest::Vision(choice) = request.clone() else { unreachable!() };
        view.accept(ThemeReply { id: 2, request, result: Ok(ThemeResponse::Vision { choice, activated: false }) });
        assert_eq!(view.message.as_deref(), Some("Saved; applies with the next theme"));
        assert_eq!(view.vision.text_scale, "large");
    }

    #[test]
    fn the_fit_mode_is_read_from_the_generation_report() {
        let root = std::env::temp_dir().join(format!("k230-fit-{}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        let appearance = root.join("appearance.json");
        assert_eq!(generation_fit(&appearance), "crop"); // no report at all
        for (body, want) in [
            (r#"{"fit_mode":"fill"}"#, "fill"),
            (r#"{"fit_mode":"solid"}"#, "solid"),
            (r#"{"fit_mode":"bogus"}"#, "crop"),
            (r#"{}"#, "crop"),
            ("not json", "crop"),
        ] {
            std::fs::write(root.join("report.json"), body).unwrap();
            assert_eq!(generation_fit(&appearance), want, "{body}");
        }
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn tap_background_on_the_video_slice_sets_a_visible_error_and_sends_nothing() {
        let mut view = ThemeView {
            page: ThemePage::List,
            preview: Some(preview()),
            ..ThemeView::default()
        };
        // Index 1 (`Motion`) is `BackgroundKind::Video` in the `preview()`
        // fixture -- video playback is not available in this shell.
        assert_eq!(view.tap_background(1), None);
        assert_eq!(
            view.error.as_deref(),
            Some("Video playback is not available in this shell")
        );
    }

    #[test]
    fn tap_background_on_the_already_selected_slice_is_a_silent_no_op() {
        let mut view = ThemeView {
            page: ThemePage::List,
            preview: Some(preview()),
            ..ThemeView::default()
        };
        assert_eq!(view.tap_background(0), None, "index 0 (Still) is already selected");
        assert_eq!(view.error, None);
    }

    #[test]
    fn rapid_taps_across_themes_coalesce_onto_the_last_one() {
        // "Rapid taps across themes should coalesce: the last tap wins,
        // with no queue of stale activations, and an in-flight apply is
        // superseded safely" (user requirement, verbatim).
        let mut view = ThemeView::default();
        load_list(&mut view, 3, Some(0));
        let settle = view.advance().unwrap();
        view.submitted(settle.clone(), 50);
        assert!(view.accept(ThemeReply {
            id: 50,
            request: settle,
            result: Ok(ThemeResponse::Preview(Box::new(preview()))),
        }));

        let theme1 = view.list.as_ref().unwrap().themes[1].id.clone();
        let theme2 = view.list.as_ref().unwrap().themes[2].id.clone();

        let first_request = view.tap_theme(1).expect("index 1");
        view.submitted(first_request.clone(), 1);
        assert_eq!(view.applying_theme_index(), Some(1));

        // Before the first tap's own reply lands, a second tap on a
        // *different* theme supersedes it -- `desired` is overwritten
        // immediately, with no queue.
        let second_request = view.tap_theme(2);
        assert_eq!(
            second_request, None,
            "a request is already in flight; advance() has nothing to submit yet"
        );
        // The visible busy state is bounded by `pending` (what is
        // physically in flight), not by `desired` (what is now wanted):
        // slice 1 keeps showing busy until its own stale reply actually
        // lands and clears `pending` -- the documented tradeoff (see this
        // task's own evidence) is that a second rapid tap's own visible
        // effect is bounded by the first tap's own in-flight round trip,
        // not instantaneous.
        assert_eq!(view.applying_theme_index(), Some(1));

        // The first tap's own (now-stale) reply arrives: discarded, not
        // shown, and `pending`/`pending_id` still clear correctly.
        let mut stale_candidate = preview();
        stale_candidate.theme.id = theme1.clone();
        stale_candidate.generation = id('f');
        assert!(view.accept(ThemeReply {
            id: 1,
            request: first_request,
            result: Ok(ThemeResponse::Preview(Box::new(stale_candidate))),
        }));
        assert_eq!(view.pending, None);
        assert_eq!(
            view.preview.as_ref().unwrap().theme.id,
            id('a'),
            "the stale reply must never be shown"
        );

        // `advance()` immediately moves on to what is now desired: theme 2.
        let request = view.advance().expect("theme 2 is still desired");
        assert_eq!(
            request,
            ThemeRequest::Preview {
                theme_id: theme2.clone(),
                background_id: None,
            }
        );
        view.submitted(request.clone(), 2);
        let mut candidate2 = preview();
        candidate2.theme.id = theme2.clone();
        candidate2.generation = id('g');
        assert!(view.accept(ThemeReply {
            id: 2,
            request,
            result: Ok(ThemeResponse::Preview(Box::new(candidate2))),
        }));
        let activate = view.advance().expect("theme 2's generation is now known");
        assert_eq!(
            activate,
            ThemeRequest::Activate {
                theme_id: theme2,
                expected_generation: id('g'),
                background_id: None,
            }
        );
    }

    #[test]
    fn a_failed_activate_rolls_back_with_a_visible_error_and_clears_pending() {
        let mut view = ThemeView::default();
        load_list(&mut view, 3, Some(0));
        let settle = view.advance().unwrap();
        view.submitted(settle.clone(), 50);
        assert!(view.accept(ThemeReply {
            id: 50,
            request: settle,
            result: Ok(ThemeResponse::Preview(Box::new(preview_with_an_unselected_still()))),
        }));

        let prepare = view.tap_background(2).expect("Dawn is not selected");
        view.submitted(prepare.clone(), 2);
        let mut candidate = preview_with_an_unselected_still();
        candidate.generation = id('f');
        candidate.backgrounds[0].selected = false;
        candidate.backgrounds[2].selected = true;
        view.accept(ThemeReply { id: 2, request: prepare,
            result: Ok(ThemeResponse::Preview(Box::new(candidate))) });
        let request = view.advance().unwrap();
        assert!(matches!(request, ThemeRequest::Activate { .. }));
        view.submitted(request.clone(), 3);
        assert!(view.accept(ThemeReply {
            id: 3,
            request,
            result: Err("commit failed; previous generation restored".into()),
        }));
        assert_eq!(
            view.error.as_deref(),
            Some("commit failed; previous generation restored")
        );
        assert_eq!(view.pending, None);
        assert_eq!(view.pending_id, None);
        assert_eq!(view.advance(), None, "a failed target is no longer desired");
        assert_eq!(
            view.applying_background_index(),
            None,
            "rollback must not leave the slice looking busy"
        );
    }

    #[test]
    fn app_reload_status_reaches_the_message_on_a_successful_activate() {
        for (state, message) in [
            ("failed", "Background applied to Home; app reload failed"),
            ("deferred", "Background applied to Home"),
        ] {
            let mut view = ThemeView {
                page: ThemePage::List,
                preview: Some(preview()),
                desired: Some(Desired {
                    theme_id: id('a'),
                    background_id: Some(id('d')),
                    generation: Some(id('b')),
                    already_active: false,
                }),
                ..ThemeView::default()
            };
            let request = ThemeRequest::Activate {
                theme_id: id('a'),
                expected_generation: id('b'),
                background_id: Some(id('d')),
            };
            view.submitted(request.clone(), 2);
            let mut applied = preview();
            applied.activated = true;
            applied.app_appearance = Some(AppAppearance {
                state: state.into(),
                generation: Some(id('b')),
                error: Some("reload-failed".into()),
                kind: None,
            });
            assert!(view.accept(ThemeReply {
                id: 2,
                request,
                result: Ok(ThemeResponse::Preview(Box::new(applied))),
            }));
            assert_eq!(
                view.message.as_deref(),
                Some(message)
            );
        }
    }

    #[test]
    fn applying_theme_index_ignores_a_pending_background_selection() {
        let mut view = ThemeView::default();
        load_list(&mut view, 3, Some(0));
        view.preview = Some(preview());
        view.pending = Some(ThemeRequest::Activate {
            theme_id: id('a'),
            expected_generation: id('b'),
            background_id: Some(id('d')),
        });
        assert_eq!(view.applying_theme_index(), None);
        assert_eq!(view.applying_background_index(), Some(1));
    }

    #[test]
    fn record_known_generation_is_read_by_the_map_directly() {
        let mut view = ThemeView::default();
        assert!(view.known_generations.is_empty());
        view.record_known_generation("theme-x", "generation-x");
        assert_eq!(
            view.known_generations.get("theme-x"),
            Some(&"generation-x".to_string())
        );
    }

    #[test]
    fn activation_cannot_be_cancelled_mid_transaction() {
        let mut view = ThemeView {
            page: ThemePage::List,
            preview: Some(preview()),
            ..ThemeView::default()
        };
        let activation = ThemeRequest::Activate {
            theme_id: id('a'),
            expected_generation: id('b'),
            background_id: Some(id('c')),
        };
        view.submitted(activation, 1);
        assert_eq!(view.back(), None);
        assert_eq!(view.page, ThemePage::List);
    }

    #[test]
    fn wallpaper_labels_are_readable_without_changing_opaque_selection() {
        assert_eq!(background_display_label("2-waves.webp"), "Waves");
        assert_eq!(background_display_label("1-color-fade.webp"), "Color fade");
        assert_eq!(background_display_label("Blue hour"), "Blue hour");
        assert_eq!(background_display_label("001.png"), "Background");
    }

    #[test]
    fn still_preview_worker_returns_output_crop_outside_dispatch() {
        // `ThemeImageWorker` itself is unused by any paint path now (task:
        // tap-to-apply, 2026-09-25 removed the single large still preview
        // it fed -- see `RendererCache::poll_theme_image`'s own doc), but
        // the worker's own decode contract is still exercised here in case
        // a later task revives a consumer for it.
        let path = std::env::temp_dir().join(format!(
            "k230-theme-preview-{}-{}.png",
            std::process::id(),
            std::thread::current().name().unwrap_or("test")
        ));
        let image = image::RgbaImage::from_fn(80, 160, |_, y| {
            if y < 80 {
                image::Rgba([220, 40, 30, 255])
            } else {
                image::Rgba([20, 80, 220, 255])
            }
        });
        image.save(&path).unwrap();
        let key = ThemeImageKey {
            fit: FitMode::Crop,
            generation: "fixture-generation".into(),
            path: path.canonicalize().unwrap(),
            generation_root: std::env::temp_dir(),
            width: 56,
            height: 123,
        };
        let worker = ThemeImageWorker::default();
        assert!(worker.try_request(key.clone()));
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        let reply = loop {
            if let Some(reply) = worker.try_recv() {
                break reply;
            }
            assert!(std::time::Instant::now() < deadline);
            std::thread::sleep(std::time::Duration::from_millis(5));
        };
        assert_eq!(reply.key, key);
        let pixels = reply.pixels.unwrap();
        assert_eq!(pixels.len(), 56 * 123 * 4);
        assert_eq!(&pixels[..4], &[30, 40, 220, 255]);
        assert_eq!(&pixels[pixels.len() - 4..], &[220, 80, 20, 255]);
        std::fs::remove_file(path).unwrap();
    }

    #[test]
    fn still_preview_reuses_the_generations_background_cache_instead_of_redecoding() {
        let generation_root = std::env::temp_dir().join(format!(
            "k230-theme-preview-cache-reuse-{}-{}",
            std::process::id(),
            std::thread::current().name().unwrap_or("test")
        ));
        std::fs::create_dir_all(&generation_root).unwrap();
        let source_path = generation_root.join("source.png");
        image::RgbaImage::from_pixel(40, 80, image::Rgba([9, 99, 199, 255]))
            .save(&source_path)
            .unwrap();
        let source_path = source_path.canonicalize().unwrap();
        crate::background_decode::write_wallpaper_cache(&source_path, &generation_root, 20, 40)
            .expect("cache precompute must succeed while the source still exists");
        std::fs::remove_file(&source_path).unwrap();

        let worker = ThemeImageWorker::default();
        let key = ThemeImageKey {
            fit: FitMode::Crop,
            generation: "fixture-generation-cache-reuse".into(),
            path: source_path,
            generation_root: generation_root.clone(),
            width: 20,
            height: 40,
        };
        assert!(worker.try_request(key.clone()));
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        let reply = loop {
            if let Some(reply) = worker.try_recv() {
                break reply;
            }
            assert!(
                std::time::Instant::now() < deadline,
                "worker never replied"
            );
            std::thread::sleep(std::time::Duration::from_millis(5));
        };
        assert_eq!(reply.key, key);
        let pixels = reply
            .pixels
            .expect("a matching background.cache must be used instead of a failed re-decode");
        assert_eq!(pixels.len(), 20 * 40 * 4);
        std::fs::remove_dir_all(&generation_root).unwrap();
    }

    #[test]
    fn prepare_ahead_waits_out_the_debounce_and_never_resends_for_the_same_index() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        view.list = Some(theme_list(None));

        assert_eq!(view.poll_prepare_ahead(50, None), None);
        assert_eq!(view.poll_prepare_ahead(50, None), None);

        assert_eq!(view.poll_prepare_ahead(100, Some(1)), None);
        assert_eq!(view.poll_prepare_ahead(100, Some(1)), None);
        let (index, request) = view
            .poll_prepare_ahead(50, Some(1))
            .expect("debounce elapsed while centred on the same index");
        assert_eq!(index, 1);
        assert_eq!(
            request,
            ThemeRequest::Preview {
                theme_id: view.list.as_ref().unwrap().themes[1].id.clone(),
                background_id: None,
            }
        );
        view.prepare_ahead_submitted(1, 7);

        assert_eq!(view.poll_prepare_ahead(1000, Some(1)), None);
        assert!(view.prepare_ahead_reply(&ThemeReply {
            id: 7,
            request,
            result: Err("irrelevant".into()),
        }));
        assert_eq!(view.poll_prepare_ahead(1000, Some(1)), None);

        assert_eq!(view.poll_prepare_ahead(50, Some(2)), None);
        let (second_index, second_request) = view
            .poll_prepare_ahead(200, Some(2))
            .expect("a new centred index gets its own debounce window");
        assert_eq!(second_index, 2);
        assert_eq!(
            second_request,
            ThemeRequest::Preview {
                theme_id: view.list.as_ref().unwrap().themes[2].id.clone(),
                background_id: None,
            }
        );
    }

    #[test]
    fn prepare_ahead_reply_records_the_known_generation() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        view.list = Some(theme_list(None));
        let (index, request) = view
            .poll_prepare_ahead(PREPARE_AHEAD_DEBOUNCE_MS, Some(1))
            .expect("debounce elapsed");
        view.prepare_ahead_submitted(index, 7);
        let mut warmed = preview();
        warmed.theme.id = view.list.as_ref().unwrap().themes[1].id.clone();
        warmed.generation = id('z');
        assert!(view.prepare_ahead_reply(&ThemeReply {
            id: 7,
            request,
            result: Ok(ThemeResponse::Preview(Box::new(warmed))),
        }));
        // `main.rs`'s own `theme_reply` is what actually calls
        // `record_known_generation` (the warm-up reply's `Ok` payload is
        // available to it, not to `prepare_ahead_reply` itself, which only
        // ever sees the *request*) -- proven directly here instead.
        view.record_known_generation(&view.list.as_ref().unwrap().themes[1].id.clone(), &id('z'));
        assert_eq!(
            view.known_generations.get(&view.list.as_ref().unwrap().themes[1].id),
            Some(&id('z'))
        );
    }

    #[test]
    fn prepare_ahead_skips_the_already_active_theme_and_a_stray_reply_never_reaches_accept() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        view.list = Some(theme_list(Some(0)));

        assert_eq!(view.poll_prepare_ahead(500, Some(0)), None);

        let stray = ThemeReply {
            id: 999,
            request: ThemeRequest::Preview {
                theme_id: view.list.as_ref().unwrap().themes[1].id.clone(),
                background_id: None,
            },
            result: Err("irrelevant".into()),
        };
        assert!(!view.prepare_ahead_reply(&stray));
        assert!(!view.accept(stray));
    }

    #[test]
    fn leaving_the_list_page_resets_the_debounce_but_keeps_the_in_flight_slot_recognisable() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        view.list = Some(theme_list(None));
        assert!(view.poll_prepare_ahead(300, Some(1)).is_some());
        view.prepare_ahead_submitted(1, 3);

        assert_eq!(view.back(), None); // List -> Controls
        assert_eq!(view.page, ThemePage::Controls);

        let reply = ThemeReply {
            id: 3,
            request: ThemeRequest::Preview {
                theme_id: view.list.as_ref().unwrap().themes[1].id.clone(),
                background_id: None,
            },
            result: Err("irrelevant".into()),
        };
        assert!(view.prepare_ahead_reply(&reply));
    }

    fn accept_list(view: &mut ThemeView, list: ThemeList) {
        view.submitted(ThemeRequest::List, 1);
        assert!(view.accept(ThemeReply {
            id: 1,
            request: ThemeRequest::List,
            result: Ok(ThemeResponse::List(list)),
        }));
    }

    #[test]
    fn without_a_durable_theme_the_chooser_loads_the_packaged_defaults_backgrounds() {
        let mut list = theme_list_of(3, None);
        list.themes[2].name = "catppuccin".into();
        let default_id = list.themes[2].id.clone();
        let mut view = ThemeView {
            page: ThemePage::List,
            default_theme_name: Some("catppuccin".into()),
            ..ThemeView::default()
        };
        accept_list(&mut view, list);

        assert_eq!(view.theme_position, 2.0);
        assert_eq!(view.list.as_ref().unwrap().active.id, None, "the default is not claimed as durably active");
        let request = view.advance().expect("the default theme's detail is requested");
        assert_eq!(request, ThemeRequest::Preview { theme_id: default_id.clone(), background_id: None });
        view.submitted(request.clone(), 2);
        let mut reply = preview();
        reply.theme.id = default_id;
        assert!(view.accept(ThemeReply { id: 2, request, result: Ok(ThemeResponse::Preview(Box::new(reply))) }));
        assert!(view.preview.as_ref().is_some_and(|preview| !preview.backgrounds.is_empty()));
        assert_eq!(view.advance(), None);
    }

    #[test]
    fn without_a_durable_theme_or_a_known_default_the_first_slice_loads() {
        let mut view = ThemeView { page: ThemePage::List, ..ThemeView::default() };
        let list = theme_list_of(3, None);
        let first = list.themes[0].id.clone();
        accept_list(&mut view, list);
        assert_eq!(view.theme_position, 0.0);
        assert_eq!(view.advance(), Some(ThemeRequest::Preview { theme_id: first, background_id: None }));
    }

    #[test]
    fn a_user_theme_sharing_the_defaults_name_is_not_taken_for_it() {
        let mut list = theme_list_of(3, None);
        list.themes[1].name = "catppuccin".into();
        list.themes[1].origin = ThemeOrigin::User;
        let mut view = ThemeView {
            page: ThemePage::List,
            default_theme_name: Some("catppuccin".into()),
            ..ThemeView::default()
        };
        accept_list(&mut view, list);
        assert_eq!(view.theme_position, 0.0);
    }

    #[test]
    fn tapping_the_shown_default_applies_it_durably() {
        let mut list = theme_list_of(3, None);
        list.themes[0].name = "catppuccin".into();
        let mut view = ThemeView {
            page: ThemePage::List,
            default_theme_name: Some("catppuccin".into()),
            ..ThemeView::default()
        };
        accept_list(&mut view, list);
        view.tap_theme(0);
        assert!(view.desired.as_ref().is_some_and(|desired| !desired.already_active));
    }

    #[test]
    fn the_default_theme_name_comes_from_its_generation_report() {
        let dir = std::env::temp_dir().join(format!("k230-default-theme-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(
            dir.join("report.json"),
            br#"{"source": "omacom/omarchy@28ceaae70ebac3a0edcc21f2faa77a90dc6d404c/themes/catppuccin"}"#,
        )
        .unwrap();
        assert_eq!(default_theme_name(&dir).as_deref(), Some("catppuccin"));
        std::fs::write(dir.join("report.json"), br#"{"source": "elsewhere"}"#).unwrap();
        assert_eq!(default_theme_name(&dir), None);
        std::fs::remove_dir_all(&dir).unwrap();
        assert_eq!(default_theme_name(&dir), None);
    }

    #[test]
    fn a_list_reply_queues_both_neighbours_of_a_mid_list_active_theme() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        load_list(&mut view, 3, Some(1));

        assert_eq!(
            view.pending_neighbor_warms,
            std::collections::VecDeque::from([0, 2])
        );
    }

    #[test]
    fn a_list_reply_queues_only_the_one_neighbour_at_each_end_of_the_list() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        load_list(&mut view, 3, Some(0));
        assert_eq!(view.pending_neighbor_warms, std::collections::VecDeque::from([1]));

        load_list(&mut view, 3, Some(2));
        assert_eq!(view.pending_neighbor_warms, std::collections::VecDeque::from([1]));
    }

    #[test]
    fn a_single_theme_list_queues_no_neighbours() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        load_list(&mut view, 1, Some(0));

        assert!(view.pending_neighbor_warms.is_empty());
        assert_eq!(view.poll_prepare_ahead(500, Some(0)), None);
    }

    #[test]
    fn the_neighbour_queue_drains_when_nothing_is_dwell_driven() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        load_list(&mut view, 3, Some(1));

        let (index, request) = view.poll_prepare_ahead(16, None).expect("a queued neighbour");
        assert_eq!(index, 0);
        assert_eq!(
            request,
            ThemeRequest::Preview {
                theme_id: view.list.as_ref().unwrap().themes[0].id.clone(),
                background_id: None,
            }
        );
        view.prepare_ahead_submitted(index, 42);

        assert_eq!(view.pending_neighbor_warms, std::collections::VecDeque::from([2]));
    }

    #[test]
    fn a_dwell_driven_request_takes_priority_over_the_neighbour_queue() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        load_list(&mut view, 3, Some(1));
        assert_eq!(
            view.pending_neighbor_warms,
            std::collections::VecDeque::from([0, 2])
        );

        let (index, request) = view
            .poll_prepare_ahead(PREPARE_AHEAD_DEBOUNCE_MS, Some(2))
            .expect("dwell-driven warm");
        assert_eq!(index, 2);
        assert_eq!(
            request,
            ThemeRequest::Preview {
                theme_id: view.list.as_ref().unwrap().themes[2].id.clone(),
                background_id: None,
            }
        );

        assert_eq!(
            view.pending_neighbor_warms,
            std::collections::VecDeque::from([0, 2])
        );
    }

    #[test]
    fn a_pending_confirm_pauses_every_warm_up_until_its_own_reply_lands() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        load_list(&mut view, 3, Some(1));
        assert_eq!(
            view.pending_neighbor_warms,
            std::collections::VecDeque::from([0, 2])
        );

        let (index, warm_request) = view
            .poll_prepare_ahead(16, None)
            .expect("neighbour 0 warms while nothing is pending");
        assert_eq!(index, 0);
        view.prepare_ahead_submitted(0, 100);
        assert!(view.prepare_ahead_reply(&ThemeReply {
            id: 100,
            request: warm_request,
            result: Err("irrelevant".into()),
        }));
        assert_eq!(
            view.pending_neighbor_warms,
            std::collections::VecDeque::from([2])
        );

        let confirm = view.tap_theme(2).expect("index 2 exists");
        view.submitted(confirm.clone(), 101);
        assert_eq!(view.pending, Some(confirm.clone()));

        for centered in [Some(2), Some(2), None, Some(2)] {
            assert_eq!(view.poll_prepare_ahead(500, centered), None);
        }
        assert_eq!(
            view.pending_neighbor_warms,
            std::collections::VecDeque::from([2])
        );

        let mut preview_of_two = preview();
        preview_of_two.theme.id = view.list.as_ref().unwrap().themes[2].id.clone();
        preview_of_two.generation = id('e');
        assert!(view.accept(ThemeReply {
            id: view.pending_id.unwrap(),
            request: confirm,
            result: Ok(ThemeResponse::Preview(Box::new(preview_of_two))),
        }));
        assert_eq!(view.pending, None);

        let activate = view.advance().expect("generation now known, not already active");
        assert_eq!(
            activate,
            ThemeRequest::Activate {
                theme_id: view.list.as_ref().unwrap().themes[2].id.clone(),
                expected_generation: id('e'),
                background_id: None,
            }
        );
    }

    #[test]
    fn prepare_ahead_latest_center_gets_its_full_dwell_before_neighbors_resume() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        load_list(&mut view, 7, Some(3));
        let queued = view.pending_neighbor_warms.clone();
        assert_eq!(queued.len(), 2);
        // Changes of direction during motion never spend or grow this queue.
        for center in [6, 1, 5, 2, 4].into_iter().cycle().take(200) {
            assert_eq!(view.poll_prepare_ahead_at_rest(1000, Some(center), false), None);
            assert_eq!(view.pending_neighbor_warms, queued);
        }
        // A neighbor must not occupy the single prepared slot while the
        // newly settled center is still earning its 250ms dwell.
        assert_eq!(view.poll_prepare_ahead_at_rest(100, Some(6), true), None);
        assert_eq!(view.pending_neighbor_warms, queued);
        // A different settled center restarts that dwell, even without a
        // movement poll between the two observations.
        assert_eq!(view.poll_prepare_ahead_at_rest(100, Some(0), true), None);
        assert_eq!(view.poll_prepare_ahead_at_rest(100, Some(0), true), None);
        let (index, request) = view.poll_prepare_ahead_at_rest(50, Some(0), true).unwrap();
        assert_eq!(index, 0);
        assert_eq!(view.pending_neighbor_warms, queued);
        view.prepare_ahead_submitted(index, 42);
        assert_eq!(view.poll_prepare_ahead_at_rest(1000, Some(0), true), None);
        assert!(view.prepare_ahead_reply(&ThemeReply {
            id: 42, request, result: Err("fixture completion".into()),
        }));
        // Once the chosen center has been handled, neighbors may resume.
        assert_eq!(view.poll_prepare_ahead_at_rest(16, Some(0), true).unwrap().0, 2);
    }

    #[test]
    fn prepare_ahead_motion_preserves_neighbors_and_expires_dwell() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        load_list(&mut view, 5, Some(2));
        let queued = view.pending_neighbor_warms.clone();
        view.prepare_ahead_watch = Some(4);
        view.prepare_ahead_elapsed_ms = PREPARE_AHEAD_DEBOUNCE_MS;
        for centered in [None, Some(4), Some(1), None] {
            assert_eq!(view.poll_prepare_ahead_at_rest(1000, centered, false), None);
            assert_eq!(view.pending_neighbor_warms, queued);
            assert_eq!(view.prepare_ahead_watch, None);
            assert_eq!(view.prepare_ahead_elapsed_ms, 0);
        }
        // Latest settled center wins over the old neighbors.
        let (index, _) = view.poll_prepare_ahead_at_rest(
            PREPARE_AHEAD_DEBOUNCE_MS, Some(4), true,
        ).unwrap();
        assert_eq!(index, 4);
        assert_eq!(view.pending_neighbor_warms, queued);
    }

    #[test]
    fn prepare_ahead_inflight_completion_cannot_admit_during_motion() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        load_list(&mut view, 5, Some(2));
        let (index, request) = view.poll_prepare_ahead_at_rest(16, None, true).unwrap();
        view.prepare_ahead_submitted(index, 42);
        let queued = view.pending_neighbor_warms.clone();
        assert_eq!(view.poll_prepare_ahead_at_rest(1000, None, false), None);
        assert_eq!(view.prepare_ahead_inflight, Some(42));
        assert!(view.prepare_ahead_reply(&ThemeReply {
            id: 42, request, result: Err("fixture completion".into()),
        }));
        assert_eq!(view.poll_prepare_ahead_at_rest(1000, Some(3), false), None);
        assert_eq!(view.pending_neighbor_warms, queued);
        // An at-rest caller without a center may still drain its bounded queue.
        assert_eq!(view.poll_prepare_ahead_at_rest(16, None, true).unwrap().0, 3);
    }

    #[test]
    fn prepare_ahead_foreground_request_keeps_priority_after_motion() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        load_list(&mut view, 5, Some(2));
        let request = view.tap_theme(4).unwrap();
        view.submitted(request, 99);
        let queued = view.pending_neighbor_warms.clone();
        for at_rest in [false, true] {
            assert_eq!(view.poll_prepare_ahead_at_rest(1000, Some(4), at_rest), None);
            assert_eq!(view.pending_neighbor_warms, queued);
            assert_eq!(view.pending_id, Some(99));
        }
    }

    #[test]
    fn the_portrait_chooser_layout_keeps_the_stacked_constants() {
        for (w, h) in [(568, 1232), (768, 1024), (1080, 1920), (1280, 1024), (0, 0)] {
            let lay = chooser_layout(w, h);
            assert!(!lay.wide, "{w}x{h}");
            assert_eq!(
                (lay.theme_top, lay.background_top, lay.header_hit_h),
                (THEME_CAROUSEL_TOP, BACKGROUND_CAROUSEL_TOP, 104.0)
            );
            assert_eq!(lay.theme_geometry, crate::theme_carousel::THEME_GEOMETRY);
            assert_eq!(lay.theme_cx, f64::from(w) / 2.0);
        }
    }

    #[test]
    fn the_wide_chooser_fits_both_carousels_and_their_labels_on_the_landscape_panel() {
        let lay = chooser_layout(1232, 568);
        assert!(lay.wide);
        // The two carousels are in disjoint halves, inside the panel.
        assert!(lay.theme_cols.1 <= lay.background_cols.0 && lay.background_cols.1 <= 1232.0);
        for (name, cx, cols, geometry, top, text) in [
            ("themes", lay.theme_cx, lay.theme_cols, lay.theme_geometry, lay.theme_top, lay.theme_text),
            ("backgrounds", lay.background_cx, lay.background_cols, lay.background_geometry, lay.background_top, lay.background_text),
        ] {
            assert!(cx - geometry.expanded_w / 2.0 >= cols.0 && cx + geometry.expanded_w / 2.0 <= cols.1, "{name} centred card in its half");
            assert!(top >= lay.themes_heading.1 + 26.0, "{name} starts below its heading");
            // The label (12 px gap, 24 px name, 26 px offset 16 px status) ends on the panel.
            assert!(top + geometry.expanded_h + 12.0 + 26.0 + 16.0 <= 568.0, "{name} label ends at {}", top + geometry.expanded_h + 54.0);
            assert!(text.0 >= cols.0 && text.0 + text.1 <= cols.1, "{name} text inside its half");
        }
        assert!(lay.message_y + 18.0 <= 568.0);
        assert!(lay.message_y >= lay.background_top + lay.background_geometry.expanded_h + 12.0 + 26.0 + 16.0, "message below the background label");
        // Header: back and Close are above both carousels.
        assert!(lay.header_y + 22.0 <= lay.themes_heading.1 && lay.header_hit_h <= lay.theme_top);
    }

    #[test]
    fn wide_choosers_show_every_theme_and_background_as_a_tappable_grid() {
        for (w, h) in [(1232u32, 568u32), (1280, 720), (1280, 800), (1920, 1080)] {
            for themes in [1usize, 7, 12] {
                let view = crate::evidence_render::fixture_theme_view(themes);
                let backgrounds = view.preview.as_ref().unwrap().backgrounds.len();
                let lay = view.layout(w, h);
                let (tg, bg) = (lay.theme_grid.unwrap(), lay.background_grid.unwrap());
                let (fw, fh) = (f64::from(w), f64::from(h));
                for (name, grid, count, cols) in [("theme", tg, themes, lay.theme_cols), ("background", bg, backgrounds, lay.background_cols)] {
                    assert!(grid.card_w >= 80.0, "{w}x{h} {themes}: {name} cards readable: {}", grid.card_w);
                    for i in 0..count {
                        let (x, y, cw, ch) = grid.rect(i);
                        assert!(x >= cols.0 && x + cw <= cols.1 && x + cw <= fw, "{w}x{h} {name} {i} inside its column");
                        assert!(y >= lay.theme_top && y + ch + GRID_LABEL_H <= fh - 48.0 + 1e-9, "{w}x{h} {themes}: {name} {i} label above the message line");
                        for j in 0..i {
                            let (ox, oy, ow, oh) = grid.rect(j);
                            assert!(x >= ox + ow || ox >= x + cw || y >= oy + oh + GRID_LABEL_H || oy >= y + ch + GRID_LABEL_H, "{name} {i} overlaps {j}");
                        }
                        let centre = (x + cw / 2.0, y + ch / 2.0);
                        let want = if name == "theme" { ThemeIntent::Theme(i) } else { ThemeIntent::Background(i) };
                        assert_eq!(view.hit(centre, centre, w, h), Some(want), "{w}x{h} {themes} {name} {i}");
                        // A drag across a card applies nothing.
                        assert_eq!(view.hit(centre, (centre.0 + 30.0, centre.1), w, h), None);
                    }
                }
                assert!(tg.rect(0).0 + tg.card_w <= bg.rect(0).0, "grids side by side");
                assert!(lay.message_y + 18.0 <= fh && !lay.in_theme_band((tg.rect(0).0 + 5.0, tg.rect(0).1 + 5.0)));
                // The header still works above the grids.
                assert_eq!(view.hit((60.0, 30.0), (60.0, 30.0), w, h), Some(ThemeIntent::Back));
                assert_eq!(view.hit((fw - 50.0, 30.0), (fw - 50.0, 30.0), w, h), Some(ThemeIntent::Close));
            }
        }
        // Portrait keeps the carousels.
        let view = crate::evidence_render::fixture_theme_view(7);
        assert!(view.layout(568, 1232).theme_grid.is_none() && view.layout(1280, 1024).theme_grid.is_none());
    }

    #[test]
    fn a_tap_at_the_centre_of_each_wide_carousel_reaches_its_own_centred_slice() {
        use crate::theme_carousel::hit_test;
        let lay = chooser_layout(1232, 568);
        let theme = (lay.theme_cx, lay.theme_top + lay.theme_geometry.expanded_h / 2.0);
        let background = (lay.background_cx, lay.background_top + lay.background_geometry.expanded_h / 2.0);
        assert!(lay.in_theme_band(theme) && !lay.in_background_band(theme));
        assert!(lay.in_background_band(background) && !lay.in_theme_band(background));
        assert_eq!(hit_test(&lay.theme_geometry, theme, 2.0, 7, lay.theme_cx, lay.theme_top), Some(2));
        assert_eq!(hit_test(&lay.background_geometry, background, 3.0, 5, lay.background_cx, lay.background_top), Some(3));
        // A touch between the halves belongs to neither carousel, and a
        // theme-side slice never answers a touch in the background half.
        let seam = (616.0, lay.theme_top + 50.0);
        assert!(!(lay.in_theme_band(seam) && lay.in_background_band(seam)));
        // Header taps: back on the left, Close on the right, only above the carousels.
        let view = ThemeView { page: ThemePage::List, ..ThemeView::default() };
        assert_eq!(view.hit((60.0, 30.0), (60.0, 30.0), 1232, 568), Some(ThemeIntent::Back));
        assert_eq!(view.hit((1180.0, 30.0), (1180.0, 30.0), 1232, 568), Some(ThemeIntent::Close));
        assert_eq!(view.hit((60.0, 70.0), (60.0, 70.0), 1232, 568), None);
    }
}

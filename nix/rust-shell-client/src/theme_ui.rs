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
    BackgroundKind, ThemeList, ThemePreview, ThemeReply, ThemeRequest, ThemeResponse,
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
                        FitMode::Crop,
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
}

/// How long a theme must stay the carousel's centred item, with the
/// carousel otherwise at rest, before task 3.2 treats it as "browsed to"
/// and warms it ahead of a possible tap-apply. Long enough that a flick
/// past several themes on the way to a specific one fires nothing for the
/// ones only passed through; short enough that a person who pauses to
/// look at a theme is very likely already warmed by the time they tap it.
const PREPARE_AHEAD_DEBOUNCE_MS: u32 = 220;

impl Default for ThemeView {
    fn default() -> Self {
        Self {
            page: ThemePage::Controls,
            list: None,
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
        ThemeRequest::List => None,
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
        if matches!(self.pending, Some(ThemeRequest::Activate { .. })) {
            return None; // A durable activation cannot be cancelled after dispatch.
        }
        self.pending = None; // A late reply must not reopen a dismissed view.
        self.pending_id = None;
        self.desired = None;
        self.error = None;
        self.message = None;
        self.theme_pressed = None;
        self.background_pressed = None;
        self.reset_prepare_ahead_debounce();
        match self.page {
            ThemePage::List => {
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
        let matches_desired = request_target(&reply.request).is_some_and(|(theme_id, background_id)| {
            self.desired
                .as_ref()
                .is_some_and(|desired| desired.theme_id == theme_id && desired.background_id.as_deref() == background_id)
        });
        match reply.result {
            Err(error) => {
                if matches_desired {
                    self.error = Some(error);
                    self.desired = None;
                }
                // A stale error (superseded by a later tap) is silently
                // discarded: `advance()` moves on to whatever is now
                // desired instead of reporting a failure for something no
                // longer wanted.
            }
            Ok(ThemeResponse::List(list)) => {
                // Center the theme carousel on the currently active theme,
                // like Quattro's own picker opening on `selectedImage`.
                let active_index = list
                    .themes
                    .iter()
                    .position(|entry| Some(entry.id.as_str()) == list.active.id.as_deref())
                    .unwrap_or(0);
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
                if let Some(active_id) = list.active.id.clone() {
                    self.desired = Some(Desired {
                        theme_id: active_id,
                        background_id: None,
                        generation: None,
                        already_active: true,
                    });
                }
                self.list = Some(list);
                self.page = ThemePage::List;
                self.error = None;
            }
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
                        Some(match preview.app_appearance.as_ref() {
                            Some(app) if app.state != "applied" => {
                                format!("Theme applied; app reload {}", app.state)
                            }
                            _ => "Theme applied".into(),
                        })
                    } else {
                        None
                    };
                    self.background_position = preview
                        .backgrounds
                        .iter()
                        .position(|row| row.selected)
                        .unwrap_or(0) as f64;
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
        self.desired = Some(Desired {
            theme_id: theme.id.clone(),
            background_id: None,
            generation: None,
            already_active,
        });
        self.error = None;
        self.advance()
    }

    /// Tapping the background carousel's own already-centred slice: same
    /// shape as `tap_theme`, for one of the *active* theme's own
    /// backgrounds (the only kind shown -- see `preview`'s own doc).
    /// Unlike a theme tap, the target's own generation is already known
    /// (`preview.generation`, loaded alongside this same list of
    /// backgrounds) -- so this goes straight to `Activate`, with no
    /// `Preview` round trip first.
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
        self.desired = Some(Desired {
            theme_id: preview.theme.id.clone(),
            background_id: Some(background.id.clone()),
            generation: Some(preview.generation.clone()),
            already_active: false, // a background change always needs a real Activate
        });
        self.error = None;
        self.advance()
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
            if self.prepare_ahead_sent_for != Some(index)
                && self.prepare_ahead_elapsed_ms >= PREPARE_AHEAD_DEBOUNCE_MS
            {
                if let Some(request) = self.warm_request_for(index) {
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
    pub fn hit(&self, start: (f64, f64), end: (f64, f64), width: u32, _height: u32) -> Option<ThemeIntent> {
        let w = f64::from(width);
        let dx = end.0 - start.0;
        let dy = end.1 - start.1;
        if dx.abs() > 18.0 || dy.abs() > 18.0 {
            return None;
        }
        if matches!(self.pending, Some(ThemeRequest::Activate { .. })) {
            return None;
        }
        match self.page {
            ThemePage::Controls => {
                ((104.0..162.0).contains(&end.1) && end.0 > w - 185.0).then_some(ThemeIntent::Open)
            }
            ThemePage::List => {
                if end.1 < 104.0 {
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
    fn tap_background_activates_directly_since_the_generation_is_already_known() {
        // Unlike a theme tap, a background tap always already knows the
        // active theme's own generation (from `preview.generation`, just
        // loaded), so it goes straight to `Activate` -- no `Preview` step.
        let mut view = ThemeView {
            page: ThemePage::List,
            preview: Some(preview_with_an_unselected_still()),
            ..ThemeView::default()
        };
        let request = view.tap_background(2).expect("index 2 (Dawn) is not yet selected");
        assert_eq!(
            request,
            ThemeRequest::Activate {
                theme_id: id('a'),
                expected_generation: id('b'),
                background_id: Some(id('e')),
            }
        );
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

        let request = view.tap_background(2).expect("Dawn is not selected");
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
            state: "failed".into(),
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
            Some("Theme applied; app reload failed")
        );
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
}

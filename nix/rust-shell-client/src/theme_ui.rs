//! Touch-only theme chooser state. All command I/O belongs to `ThemeWorker`.
//! Preview is reversible; only an explicit Apply may request activation.

use crate::background_decode::{BackgroundCache, FitMode};
use crate::theme_catalog::{
    BackgroundKind, ThemeList, ThemePreview, ThemeReply, ThemeRequest, ThemeResponse,
};
use std::{
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
    List,
    Preview,
}

#[derive(Clone, Debug)]
pub struct ThemeView {
    pub page: ThemePage,
    pub list: Option<ThemeList>,
    pub preview: Option<ThemePreview>,
    pub pending: Option<ThemeRequest>,
    pub pending_id: Option<u64>,
    /// A failed background choice must not leave the previous Apply enabled.
    pub selection_error: bool,
    pub error: Option<String>,
    pub message: Option<String>,
    /// The theme carousel's continuous position (`theme_carousel::Carousel`
    /// in `main.rs` owns the drag/momentum physics; this is just the
    /// latest value, mirrored here so the renderer -- which only ever sees
    /// a cloned `ThemeView`, never the live carousel -- can paint it).
    pub theme_position: f64,
    /// Same, for the Preview page's background carousel.
    pub background_position: f64,
    /// Which theme-carousel slice, if any, currently shows an immediate
    /// "pressed" highlight -- mirrored each frame from
    /// `theme_carousel::Carousel::pressed` (`main.rs` owns the live
    /// carousel; the renderer only ever sees this cloned snapshot). See
    /// `render.rs::paint_carousel`.
    pub theme_pressed: Option<usize>,
    /// Same, for the Preview page's background carousel.
    pub background_pressed: Option<usize>,
    /// A slow, deliberately throttled 0.0..1.0 animation phase driving every
    /// loading spinner this page paints (pending thumbnails, a preparing
    /// still preview, a pending Apply). `main.rs` advances this on its own
    /// bounded cadence -- see its `THEME_PULSE_INTERVAL` -- rather than
    /// every event-loop tick, which is what previously caused a continuous
    /// full redraw at rest while thumbnails were still decoding (the
    /// idle-redraw fix this field is part of).
    pub pulse_phase: f64,
    /// Task 3.2: index whose centred dwell time is accumulating, on the
    /// Themes list page only. Reset (to `None`/`0`) whenever the carousel
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
}

/// How long a theme must stay the carousel's centred item, with the
/// carousel otherwise at rest, before task 3.2 treats it as "browsed to"
/// and warms it ahead of a possible Apply. Long enough that a flick past
/// several themes on the way to a specific one fires nothing for the ones
/// only passed through; short enough that a person who pauses to look at a
/// theme is very likely already warmed by the time they decide to open it.
const PREPARE_AHEAD_DEBOUNCE_MS: u32 = 220;

impl Default for ThemeView {
    fn default() -> Self {
        Self {
            page: ThemePage::Controls,
            list: None,
            preview: None,
            pending: None,
            pending_id: None,
            selection_error: false,
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
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ThemeIntent {
    Open,
    Back,
    Close,
    Theme(usize),
    Background(usize),
    Apply,
}

/// Top of the theme carousel band (below the "Themes" heading/subtext).
/// This page's carousel is the Themes page's hero content (see
/// `theme_carousel::THEME_GEOMETRY`'s own doc), so almost everything below
/// this line is the carousel itself, its name label, and its origin
/// caption -- the page is otherwise deliberately uncluttered.
pub const THEME_CAROUSEL_TOP: f64 = 204.0;
/// Top of the background carousel band on the Preview page (below the
/// palette swatches, screen-crop preview, and "Backgrounds" heading). This
/// carousel is smaller than the Themes page's hero
/// (`theme_carousel::BACKGROUND_GEOMETRY`) because everything above this
/// line already fills a meaningful share of the page.
pub const BACKGROUND_CAROUSEL_TOP: f64 = 662.0;
/// The Preview page's Cancel/Apply footer card's own top y. Unlike the old
/// scrolling row list, the background carousel's height never depends on
/// how many backgrounds a theme has, so this footer is a fixed offset
/// below the carousel band, not a floating one. The `120.0` gap (not the
/// smaller `104.0` this used before the carousel grew) leaves clear space
/// between the background's own name/status caption and this footer, both
/// of which now share this same headroom regardless of geometry size.
pub const PREVIEW_FOOTER_Y: f64 =
    BACKGROUND_CAROUSEL_TOP + crate::theme_carousel::BACKGROUND_GEOMETRY.expanded_h + 120.0;

impl ThemeView {
    pub fn open(&mut self) -> ThemeRequest {
        self.page = ThemePage::List;
        self.preview = None;
        self.selection_error = false;
        self.error = None;
        self.message = None;
        self.theme_pressed = None;
        self.background_pressed = None;
        self.reset_prepare_ahead_debounce();
        ThemeRequest::List
    }

    /// Clears task 3.2's debounce/dedupe bookkeeping (never the one
    /// in-flight request id: that reply, whenever it lands, must still be
    /// recognised by `prepare_ahead_reply` rather than falling through to
    /// `accept`). Called whenever the list page's own centred-item context
    /// stops applying -- leaving the page, or reloading the list.
    fn reset_prepare_ahead_debounce(&mut self) {
        self.prepare_ahead_watch = None;
        self.prepare_ahead_elapsed_ms = 0;
        self.prepare_ahead_sent_for = None;
    }

    pub fn back(&mut self) -> Option<ThemeRequest> {
        if matches!(self.pending, Some(ThemeRequest::Activate { .. })) {
            return None; // Activation cannot be cancelled after dispatch.
        }
        self.pending = None; // A late preview/activation reply must not reopen a dismissed view.
        self.pending_id = None;
        self.selection_error = false;
        self.error = None;
        self.message = None;
        self.theme_pressed = None;
        self.background_pressed = None;
        self.reset_prepare_ahead_debounce();
        match self.page {
            ThemePage::Preview => {
                self.page = ThemePage::List;
                self.preview = None;
                Some(ThemeRequest::List)
            }
            ThemePage::List => {
                self.page = ThemePage::Controls;
                None
            }
            ThemePage::Controls => None,
        }
    }

    pub fn submitted(&mut self, request: ThemeRequest, id: u64) {
        if matches!(
            &request,
            ThemeRequest::Preview {
                background_id: Some(_),
                ..
            }
        ) {
            self.selection_error = true;
        }
        self.pending = Some(request);
        self.pending_id = Some(id);
        self.error = None;
        self.message = None;
    }

    pub fn failed_to_submit(&mut self, error: &str) {
        self.error = Some(error.into());
    }

    pub fn selection_failed(&mut self, error: &str) {
        self.selection_error = true;
        self.failed_to_submit(error);
    }

    pub fn accept(&mut self, reply: ThemeReply) -> bool {
        if self.pending_id != Some(reply.id) || self.pending.as_ref() != Some(&reply.request) {
            return false;
        }
        self.pending = None;
        self.pending_id = None;
        let was_background_choice = matches!(
            &reply.request,
            ThemeRequest::Preview {
                background_id: Some(_),
                ..
            }
        );
        match reply.result {
            Err(error) => {
                if was_background_choice {
                    self.selection_error = true;
                }
                self.error = Some(error);
            }
            Ok(ThemeResponse::List(list)) => {
                // Center the theme carousel on the currently active theme,
                // like Quattro's own picker opening on `selectedImage`.
                self.theme_position = list
                    .themes
                    .iter()
                    .position(|entry| Some(entry.id.as_str()) == list.active.id.as_deref())
                    .unwrap_or(0) as f64;
                self.list = Some(list);
                self.page = ThemePage::List;
                self.error = None;
            }
            Ok(ThemeResponse::Preview(preview)) => {
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
                // Center the background carousel on whichever background
                // this preview reports selected.
                self.background_position = preview
                    .backgrounds
                    .iter()
                    .position(|row| row.selected)
                    .unwrap_or(0) as f64;
                self.preview = Some(*preview);
                self.selection_error = false;
                self.page = ThemePage::Preview;
                self.error = None;
            }
        }
        true
    }

    /// Task 3.2: called once per tick while the Themes list page is shown.
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
    ) -> Option<ThemeRequest> {
        let Some(index) = centered else {
            self.prepare_ahead_watch = None;
            self.prepare_ahead_elapsed_ms = 0;
            return None;
        };
        if self.prepare_ahead_watch != Some(index) {
            self.prepare_ahead_watch = Some(index);
            self.prepare_ahead_elapsed_ms = elapsed_ms;
        } else {
            self.prepare_ahead_elapsed_ms = self.prepare_ahead_elapsed_ms.saturating_add(elapsed_ms);
        }
        if self.prepare_ahead_inflight.is_some()
            || self.prepare_ahead_sent_for == Some(index)
            || self.prepare_ahead_elapsed_ms < PREPARE_AHEAD_DEBOUNCE_MS
        {
            return None;
        }
        let list = self.list.as_ref()?;
        let theme = list.themes.get(index)?;
        if list.active.id.as_deref() == Some(theme.id.as_str()) {
            return None; // already active/applied: nothing to warm
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
    /// warm-up reply is always discarded -- it is never mistaken for the
    /// (structurally identical) reply to a real, navigational Preview
    /// request, because `submitted`/`self.pending`/`self.pending_id` were
    /// never touched for it in the first place.
    pub fn prepare_ahead_reply(&mut self, reply: &ThemeReply) -> bool {
        if self.prepare_ahead_inflight == Some(reply.id) {
            self.prepare_ahead_inflight = None;
            true
        } else {
            false
        }
    }

    pub fn preview_request(&self, index: usize) -> Option<ThemeRequest> {
        let theme = self.list.as_ref()?.themes.get(index)?;
        Some(ThemeRequest::Preview {
            theme_id: theme.id.clone(),
            background_id: None,
        })
    }

    pub fn background_request(&self, index: usize) -> Result<ThemeRequest, &'static str> {
        let preview = self.preview.as_ref().ok_or("Preview unavailable")?;
        let background = preview
            .backgrounds
            .get(index)
            .ok_or("Background unavailable")?;
        if background.kind == BackgroundKind::Video {
            return Err("Video playback is not available in this shell");
        }
        Ok(ThemeRequest::Preview {
            theme_id: preview.theme.id.clone(),
            background_id: Some(background.id.clone()),
        })
    }

    pub fn apply_request(&self) -> Result<ThemeRequest, &'static str> {
        let preview = self.preview.as_ref().ok_or("Preview unavailable")?;
        if self.pending.is_some() {
            return Err("Wait for theme preview");
        }
        if self.selection_error {
            return Err("Select an available background before applying");
        }
        let selected = preview.backgrounds.iter().find(|row| row.selected);
        if selected.is_some_and(|row| row.kind == BackgroundKind::Video) {
            return Err("Video playback is not available in this shell");
        }
        Ok(ThemeRequest::Activate {
            theme_id: preview.theme.id.clone(),
            expected_generation: preview.generation.clone(),
            background_id: selected.map(|row| row.id.clone()),
        })
    }

    /// Header (Back/Close) and, on the Preview page, footer (Cancel/Apply)
    /// chrome hits. Everything in between belongs to a carousel band now --
    /// `theme_carousel::Carousel::up` resolves those touches directly (see
    /// `main.rs`), returning `CarouselOutcome::Consumed` for anything that
    /// should not fall through to here.
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
            ThemePage::List | ThemePage::Preview => {
                if end.1 < 104.0 {
                    return if end.0 < 190.0 {
                        Some(ThemeIntent::Back)
                    } else if end.0 > w - 150.0 {
                        Some(ThemeIntent::Close)
                    } else {
                        None
                    };
                }
                if self.pending.is_some() {
                    return None;
                }
                if self.page == ThemePage::Preview
                    && (PREVIEW_FOOTER_Y..PREVIEW_FOOTER_Y + 86.0).contains(&end.1)
                {
                    return if end.0 < w / 2.0 {
                        Some(ThemeIntent::Back)
                    } else if self.selection_error {
                        None
                    } else {
                        Some(ThemeIntent::Apply)
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

    #[test]
    fn explicit_preview_apply_identity_and_video_limit() {
        let mut view = ThemeView::default();
        assert_eq!(
            view.hit((500.0, 130.0), (500.0, 130.0), 568, 1232),
            Some(ThemeIntent::Open)
        );
        let list_request = view.open();
        view.submitted(list_request.clone(), 1);
        let list = ThemeList {
            themes: vec![preview().theme],
            active: ActiveTheme {
                id: None,
                generation: None,
            },
        };
        assert!(view.accept(ThemeReply {
            id: 1,
            request: list_request,
            result: Ok(ThemeResponse::List(list))
        }));
        // Which slice a tap lands on is `theme_carousel::Carousel::up`'s job
        // now (covered by its own tests); `ThemeView` just needs to build
        // the right request once a caller says "confirm index 0".
        let request = view.preview_request(0).unwrap();
        view.submitted(request.clone(), 2);
        assert!(view.accept(ThemeReply {
            id: 2,
            request,
            result: Ok(ThemeResponse::Preview(Box::new(preview())))
        }));
        assert_eq!(
            view.apply_request().unwrap(),
            ThemeRequest::Activate {
                theme_id: id('a'),
                expected_generation: id('b'),
                background_id: Some(id('c'))
            }
        );
        assert!(view.background_request(1).is_err());
        assert_eq!(
            view.hit(
                (430.0, PREVIEW_FOOTER_Y + 20.0),
                (430.0, PREVIEW_FOOTER_Y + 20.0),
                568,
                1232
            ),
            Some(ThemeIntent::Apply)
        );
    }

    #[test]
    fn stale_reply_after_cancel_and_app_sync_status_are_explicit() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        view.submitted(
            ThemeRequest::Preview {
                theme_id: id('a'),
                background_id: None,
            },
            1,
        );
        view.back();
        assert!(!view.accept(ThemeReply {
            id: 1,
            request: ThemeRequest::Preview {
                theme_id: id('a'),
                background_id: None
            },
            result: Ok(ThemeResponse::Preview(Box::new(preview())))
        }));
        assert_eq!(view.page, ThemePage::Controls);
        view.page = ThemePage::Preview;
        let mut applied = preview();
        applied.activated = true;
        applied.app_appearance = Some(AppAppearance {
            state: "failed".into(),
            generation: Some(id('b')),
            error: Some("reload-failed".into()),
            kind: None,
        });
        let request = ThemeRequest::Activate {
            theme_id: id('a'),
            expected_generation: id('b'),
            background_id: Some(id('c')),
        };
        view.submitted(request.clone(), 2);
        assert!(view.accept(ThemeReply {
            id: 2,
            request,
            result: Ok(ThemeResponse::Preview(Box::new(applied)))
        }));
        assert_eq!(
            view.message.as_deref(),
            Some("Theme applied; app reload failed")
        );
    }

    #[test]
    fn activation_cannot_be_cancelled_mid_transaction() {
        let mut view = ThemeView {
            page: ThemePage::Preview,
            preview: Some(preview()),
            ..ThemeView::default()
        };
        let activation = view.apply_request().unwrap();
        view.submitted(activation, 1);
        assert_eq!(view.back(), None);
        assert_eq!(view.page, ThemePage::Preview);
        assert_eq!(
            view.hit(
                (430.0, PREVIEW_FOOTER_Y + 20.0),
                (430.0, PREVIEW_FOOTER_Y + 20.0),
                568,
                1232
            ),
            None,
            "a pending activation blocks the footer, not just carousel taps"
        );
    }

    #[test]
    fn list_and_preview_loads_center_the_carousels_on_the_active_selection() {
        let mut view = ThemeView::default();
        let themes: Vec<ThemeEntry> = (0..5)
            .map(|index| {
                let mut theme = preview().theme;
                theme.id = std::iter::repeat_n(char::from_digit(index, 10).unwrap(), 24).collect();
                theme
            })
            .collect();
        let active_id = themes[3].id.clone();
        let request = view.open();
        view.submitted(request.clone(), 1);
        assert!(view.accept(ThemeReply {
            id: 1,
            request,
            result: Ok(ThemeResponse::List(ThemeList {
                themes,
                active: ActiveTheme {
                    id: Some(active_id),
                    generation: None,
                },
            })),
        }));
        assert_eq!(view.theme_position, 3.0);

        let mut staged = preview();
        staged.backgrounds[1].selected = true;
        staged.backgrounds[0].selected = false;
        let request = view.preview_request(0).unwrap();
        view.submitted(request.clone(), 2);
        assert!(view.accept(ThemeReply {
            id: 2,
            request,
            result: Ok(ThemeResponse::Preview(Box::new(staged))),
        }));
        assert_eq!(view.background_position, 1.0);
    }

    #[test]
    fn reopened_list_rejects_old_equal_request_and_failed_background_blocks_apply() {
        let mut view = ThemeView::default();
        let old_request = view.open();
        view.submitted(old_request.clone(), 1);
        view.back();
        let new_request = view.open();
        view.submitted(new_request.clone(), 2);
        let list = ThemeList {
            themes: vec![preview().theme],
            active: ActiveTheme {
                id: None,
                generation: None,
            },
        };
        assert!(!view.accept(ThemeReply {
            id: 1,
            request: old_request,
            result: Ok(ThemeResponse::List(list.clone())),
        }));
        assert_eq!(view.pending_id, Some(2));
        assert!(view.accept(ThemeReply {
            id: 2,
            request: new_request,
            result: Ok(ThemeResponse::List(list)),
        }));
        view.page = ThemePage::Preview;
        view.preview = Some(preview());
        let choice = view.background_request(0).unwrap();
        view.submitted(choice.clone(), 3);
        assert!(view.accept(ThemeReply {
            id: 3,
            request: choice,
            result: Err("background preparation failed".into()),
        }));
        assert!(view.selection_error);
        assert!(view.apply_request().is_err());
        assert_eq!(
            view.hit(
                (430.0, PREVIEW_FOOTER_Y + 20.0),
                (430.0, PREVIEW_FOOTER_Y + 20.0),
                568,
                1232
            ),
            None
        );
        let retry = view.background_request(0).unwrap();
        view.submitted(retry.clone(), 4);
        assert!(view.accept(ThemeReply {
            id: 4,
            request: retry,
            result: Ok(ThemeResponse::Preview(Box::new(preview()))),
        }));
        assert!(!view.selection_error);
        assert!(view.apply_request().is_ok());
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
        // Both vertical regions visible in the actual portrait wallpaper
        // must survive the asynchronous chooser sample. A wide 512x176 crop
        // would sample a different source region.
        assert_eq!(&pixels[..4], &[30, 40, 220, 255]);
        assert_eq!(&pixels[pixels.len() - 4..], &[220, 80, 20, 255]);
        std::fs::remove_file(path).unwrap();
    }

    #[test]
    fn still_preview_reuses_the_generations_background_cache_instead_of_redecoding() {
        // The activation flow (`tools/theme_activate.py`'s `prepare()`)
        // already writes a `background.cache` for the selected background at
        // exactly this width/height/FitMode::Crop (see
        // `background_decode.rs`). The chooser's "Selected background" still
        // preview must reuse that file through `generation_root` rather than
        // repeating a full source decode -- proven here by deleting the
        // source file after the cache is written: a worker that still
        // succeeds only read the cache.
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
        // Now remove the source: any code path that falls through to a full
        // decode fails from here on, so a successful reply proves the cache
        // was actually used.
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

    fn theme_list(active_index: Option<usize>) -> ThemeList {
        let themes: Vec<ThemeEntry> = (0..3)
            .map(|index| {
                let mut theme = preview().theme;
                theme.id = std::iter::repeat_n(char::from_digit(index, 10).unwrap(), 24).collect();
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

    #[test]
    fn prepare_ahead_waits_out_the_debounce_and_never_resends_for_the_same_index() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        view.list = Some(theme_list(None));

        // A fast flick (never settled, `centered` is `None` each tick) asks
        // for nothing.
        assert_eq!(view.poll_prepare_ahead(50, None), None);
        assert_eq!(view.poll_prepare_ahead(50, None), None);

        // Settling on index 1 starts the debounce timer; short of the
        // threshold, still nothing.
        assert_eq!(view.poll_prepare_ahead(100, Some(1)), None);
        assert_eq!(view.poll_prepare_ahead(100, Some(1)), None);
        // Crossing the threshold (100+100+50 >= 220) fires exactly once.
        let request = view
            .poll_prepare_ahead(50, Some(1))
            .expect("debounce elapsed while centred on the same index");
        assert_eq!(
            request,
            ThemeRequest::Preview {
                theme_id: view.list.as_ref().unwrap().themes[1].id.clone(),
                background_id: None,
            }
        );
        view.prepare_ahead_submitted(1, 7);

        // Still centred on 1: no repeat while the in-flight slot is held,
        // and none once it clears either, since index 1 was already asked
        // for.
        assert_eq!(view.poll_prepare_ahead(1000, Some(1)), None);
        assert!(view.prepare_ahead_reply(&ThemeReply {
            id: 7,
            request,
            result: Err("irrelevant".into()),
        }));
        assert_eq!(view.poll_prepare_ahead(1000, Some(1)), None);

        // Moving to a different index resets the dedupe and debounce.
        assert_eq!(view.poll_prepare_ahead(50, Some(2)), None);
        let second = view
            .poll_prepare_ahead(200, Some(2))
            .expect("a new centred index gets its own debounce window");
        assert_eq!(
            second,
            ThemeRequest::Preview {
                theme_id: view.list.as_ref().unwrap().themes[2].id.clone(),
                background_id: None,
            }
        );
    }

    #[test]
    fn prepare_ahead_skips_the_already_active_theme_and_a_stray_reply_never_reaches_accept() {
        let mut view = ThemeView::default();
        view.page = ThemePage::List;
        view.list = Some(theme_list(Some(0)));

        // Index 0 is already active: nothing to warm even after a long dwell.
        assert_eq!(view.poll_prepare_ahead(500, Some(0)), None);

        // A reply for a request this view never tracked as in-flight (a
        // stray/late id) is not claimed by `prepare_ahead_reply`, so
        // `main.rs` would fall through to `accept`, which independently
        // rejects it via the ordinary pending/pending_id mismatch check.
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

        // The in-flight request's own reply must still be recognised (and
        // discarded) even after navigating away, never treated as a real
        // Preview reply that could reopen/repaint the chooser.
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
}

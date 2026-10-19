//! Touch-first Wi-Fi Settings state, independent of Wayland rendering.
//! Only `WifiPublic` is copied to the renderer; it never contains a password.
use crate::wifi_settings::{
    Kind, Network, Secret, Security, Snapshot, WifiReply, WifiRequest, WifiResult,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Page {
    Closed,
    List,
    Entry,
    Connecting,
    ForgetConfirm,
}

#[derive(Clone, Debug)]
pub struct WifiPublic {
    pub page: Page,
    pub snapshot: Option<Snapshot>,
    pub selected: Option<Network>,
    pub password_len: usize,
    pub password_visible: bool,
    pub use_saved: bool,
    pub pending: bool,
    pub message: Option<String>,
    pub scroll: f64,
    /// Reserved height, in the 568x1232 artwork's own coordinate space, of
    /// the system on-screen keyboard currently raised for this page -- 0.0
    /// when it is not raised (an open network, a saved credential, or any
    /// page besides the password editor). Set by the shell alongside the
    /// overlay layer's own `keyboard_interactivity` toggle, never by
    /// `WifiView` itself: this is Wayland-side layout, not Wi-Fi state
    /// (see this module's own header doc). `paint_wifi` and `target` both
    /// read it to keep Cancel/Connect above the keyboard instead of hidden
    /// beneath it, like Android's `adjustResize`.
    pub keyboard_inset: f64,
}

#[derive(Debug, PartialEq)]
pub enum Intent {
    Back,
    Refresh,
    Select(usize),
    Key(char),
    Backspace,
    Connect,
    EditPassword,
    TogglePassword,
    Forget,
    ForgetConfirm,
    ForgetCancel,
    CancelPending,
    Scroll(f64),
}

pub struct WifiView {
    pub page: Page,
    pub snapshot: Option<Snapshot>,
    pub selected: Option<Network>,
    pub message: Option<String>,
    pub scroll: f64,
    password: Secret,
    password_visible: bool,
    pub use_saved: bool,
    pub pending: Option<(u64, Kind)>,
    keyboard_inset: f64,
    /// The surface the list scrolls on, for its `layout_for`.
    surface: (u32, u32),
}
impl Default for WifiView {
    fn default() -> Self {
        Self {
            page: Page::Closed,
            snapshot: None,
            selected: None,
            message: None,
            scroll: 0.0,
            password: Secret::new(String::new()),
            password_visible: false,
            use_saved: false,
            pending: None,
            keyboard_inset: 0.0,
            surface: (568, 1232),
        }
    }
}
impl WifiView {
    /// Sizes the list's scroll range to the layout in use for a
    /// `width`x`height` surface (`layout`'s own `list_view`).
    pub fn set_surface(&mut self, width: u32, height: u32) {
        self.surface = (width, height);
        self.scroll(0.0);
    }
    pub fn public(&self) -> WifiPublic {
        WifiPublic {
            page: self.page,
            snapshot: self.snapshot.clone(),
            selected: self.selected.clone(),
            password_len: self.password.len(),
            password_visible: self.password_visible && self.wants_keyboard(),
            use_saved: self.use_saved,
            pending: self.pending.is_some(),
            message: self.message.clone(),
            scroll: self.scroll,
            keyboard_inset: self.keyboard_inset,
        }
    }
    /// Whether the password editor is on a field that needs typed text right
    /// now -- an unsaved WPA2-Personal entry. Open networks skip the field
    /// entirely and a saved credential needs no re-entry, so neither should
    /// ever raise the system keyboard or reserve space for it. The shell
    /// calls this after every state change that can affect it (see
    /// `ShellClient::sync_wifi_keyboard`) rather than this module reaching
    /// into Wayland itself -- see this file's own header doc.
    pub fn wants_keyboard(&self) -> bool {
        self.page == Page::Entry
            && !self.use_saved
            && self
                .selected
                .as_ref()
                .is_some_and(|network| network.security == Security::Wpa2Psk)
    }
    /// Records how much of the bottom of the screen the system keyboard
    /// currently reserves, in the 568x1232 artwork's own coordinate space
    /// (0.0 when it is not raised). Purely a rendering/hit-testing input;
    /// see `WifiPublic::keyboard_inset`'s own doc.
    pub fn set_keyboard_inset(&mut self, inset: f64) {
        self.keyboard_inset = inset;
    }
    pub fn open(&mut self) -> WifiRequest {
        *self = Self::default();
        self.page = Page::List;
        self.message = Some("Scanning nearby networks…".into());
        WifiRequest::Scan
    }
    pub fn close(&mut self) {
        *self = Self::default();
    }
    pub fn submitted(&mut self, id: u64, kind: Kind) {
        self.pending = Some((id, kind));
    }
    pub fn submit_failed(&mut self, message: &str) {
        self.pending = None;
        self.message = Some(message.into());
        if self.page == Page::Connecting {
            self.page = Page::Entry;
        }
    }
    pub fn accept(&mut self, reply: WifiReply) -> bool {
        if self.page == Page::Closed || self.pending != Some((reply.id, reply.kind)) {
            return false;
        }
        self.pending = None;
        match reply.result {
            Ok(WifiResult::Snapshot(mut snapshot)) => {
                if reply.kind == Kind::Status {
                    if let Some(previous) = &self.snapshot {
                        snapshot.networks = previous.networks.clone();
                    }
                }
                let unavailable = snapshot.error.clone();
                self.snapshot = Some(snapshot);
                self.message = unavailable.map(|code| useful_error(&code).into());
            }
            Ok(WifiResult::Saved) => {
                self.password = Secret::new(String::new());
                self.password_visible = false;
                self.page = Page::List;
                self.message = Some("Saved. Checking current connection…".into());
            }
            Ok(WifiResult::Selected) => {
                self.password = Secret::new(String::new());
                self.password_visible = false;
                self.page = Page::List;
                self.message = Some("Saved network selected. Checking current link…".into());
            }
            Ok(WifiResult::Forgotten) => {
                self.page = Page::List;
                self.selected = None;
                self.message = Some("Network forgotten".into());
            }
            Err(error) => {
                self.message = Some(useful_error(&error).into());
                if matches!(reply.kind, Kind::Connect | Kind::ConnectSaved) {
                    self.page = Page::Entry;
                    if reply.kind == Kind::ConnectSaved && error == "authentication-failed" {
                        self.use_saved = false;
                    }
                }
                if reply.kind == Kind::Forget {
                    self.page = Page::ForgetConfirm;
                }
            }
        }
        true
    }
    pub fn select(&mut self, index: usize) {
        let Some(snapshot) = &self.snapshot else {
            return;
        };
        let Some(network) = all_networks(snapshot).get(index).cloned() else {
            return;
        };
        if network.security == Security::Unsupported {
            self.message =
                Some("This network needs a setup method that is not supported yet".into());
            return;
        }
        self.use_saved = snapshot
            .saved
            .iter()
            .any(|saved| saved.ssid == network.ssid);
        self.selected = Some(network);
        self.password = Secret::new(String::new());
                self.password_visible = false;
        self.page = Page::Entry;
        self.message = None;
    }
    pub fn can_connect(&self) -> bool {
        self.selected
            .as_ref()
            .is_some_and(|selected| match selected.security {
                Security::Open => true,
                Security::Wpa2Psk => self.use_saved || (8..=63).contains(&self.password.len()),
                Security::Unsupported => false,
            })
            && self.pending.is_none()
    }
    pub fn connect_request(&mut self) -> Option<WifiRequest> {
        if !self.can_connect() {
            return None;
        }
        let selected = self.selected.as_ref()?;
        self.password_visible = false;
        self.page = Page::Connecting;
        self.message = Some("Connecting…".into());
        if self.use_saved {
            return Some(WifiRequest::ConnectSaved {
                ssid: selected.ssid.clone(),
            });
        }
        Some(WifiRequest::Connect {
            ssid: selected.ssid.clone(),
            security: selected.security,
            password: Secret::new(self.password.as_str().to_owned()),
        })
    }
    pub fn forget_request(&mut self) -> Option<WifiRequest> {
        if self.page != Page::ForgetConfirm || self.pending.is_some() {
            return None;
        }
        let ssid = self.selected.as_ref()?.ssid.clone();
        if !self
            .snapshot
            .as_ref()?
            .saved
            .iter()
            .any(|item| item.ssid == ssid)
        {
            return None;
        }
        self.message = Some("Forgetting…".into());
        Some(WifiRequest::Forget { ssid })
    }
    pub fn back(&mut self) -> bool {
        match self.page {
            Page::Closed => false,
            Page::List => {
                self.close();
                false
            }
            Page::Connecting => false, // explicit Cancel uses worker cancellation first
            Page::Entry | Page::ForgetConfirm => {
                self.page = Page::List;
                self.selected = None;
                self.password = Secret::new(String::new());
                self.password_visible = false;
                self.use_saved = false;
                self.message = None;
                true
            }
        }
    }
    pub fn key(&mut self, intent: Intent) {
        if self.page != Page::Entry || self.pending.is_some() || self.use_saved {
            return;
        }
        match intent {
            Intent::Key(c) => self.password.push(c),
            Intent::Backspace => self.password.pop(),
            _ => {}
        }
    }
    pub fn edit_password(&mut self) {
        if self.page == Page::Entry
            && self.pending.is_none()
            && self
                .selected
                .as_ref()
                .is_some_and(|network| network.security == Security::Wpa2Psk)
        {
            self.use_saved = false;
            self.password = Secret::new(String::new());
                self.password_visible = false;
            self.message = None;
        }
    }
    /// Only the painter may borrow revealed unsaved input. Public/debug state
    /// contains a visibility flag and length, never this value.
    pub fn password_preview(&self) -> Option<&str> {
        (self.password_visible && self.wants_keyboard())
            .then(|| self.password.as_str())
    }
    pub fn hide_password(&mut self) { self.password_visible = false; }
    pub fn toggle_password(&mut self) {
        if self.wants_keyboard() && self.pending.is_none() {
            self.password_visible = !self.password_visible;
        }
    }

    pub fn scroll(&mut self, delta: f64) {
        if self.page != Page::List {
            return;
        }
        let count = self.snapshot.as_ref().map_or(0, |s| all_networks(s).len());
        let lay = layout_for(self.surface.0, self.surface.1, 0.0);
        let max = (count as f64 * lay.row_pitch - 10.0 - lay.list_view.3).max(0.0);
        self.scroll = (self.scroll + delta).clamp(0.0, max);
    }
}

/// The Entry page's Cancel/Connect row: `(top, bottom)` in the 568x1232
/// artwork's own coordinate space. Normally anchored to the bottom of the
/// screen; once the system keyboard is raised (`keyboard_inset` > 0) the row
/// moves to sit directly above it instead of being hidden underneath, like
/// Android's `adjustResize`. Shared by `target`'s hit-testing and
/// `render::paint_wifi`'s drawing so the two can never drift apart.
pub fn entry_buttons_rect(keyboard_inset: f64) -> (f64, f64) {
    let (_, connect) = layout(false, keyboard_inset).buttons;
    (connect.1, connect.1 + connect.3)
}

/// `(x, y, width, height)`.
pub type Rect = (f64, f64, f64, f64);

fn contains(rect: Rect, x: f64, y: f64) -> bool {
    x >= rect.0 && x < rect.0 + rect.2 && y >= rect.1 && y < rect.1 + rect.3
}

/// Whether `(x, y)`, in the layout's own units, is inside the network list.
pub fn list_contains(lay: &Layout, x: f64, y: f64) -> bool {
    contains(lay.list_view, x, y)
}

/// Whether the Wi-Fi pages use the landscape layout: the same predicate as
/// Help and Settings (`help::wide`), so the landscape surfaces switch
/// together. Everything else keeps the 568x1232 artwork's own layout.
pub fn wide(width: u32, height: u32) -> bool {
    crate::help::wide(width, height)
}

/// The factor taking a real touch/paint coordinate to the units `Layout` is
/// written in: the 568x1232 artwork scales to the surface, the wide layout
/// is in real pixels.
pub fn layout_scale(width: u32, height: u32) -> (f64, f64) {
    if wide(width, height) {
        (1.0, 1.0)
    } else {
        (568.0 / f64::from(width.max(1)), 1232.0 / f64::from(height.max(1)))
    }
}

/// Every Wi-Fi page rect that is both painted and hit-tested, in one place.
/// Text uses the shell's type roles (`render::TYPE_*`) at the current text
/// step and theme size, and every card, row and button is sized from those
/// roles, so text never overlaps or is cut by its card. Portrait values are
/// in the 568x1232 artwork's units; the wide layout lays the same pages out
/// in two columns in real pixels. Text positions are relative to their card
/// so both layouts share the paint code.
#[derive(Clone, Copy, Debug)]
pub struct Layout {
    pub wide: bool,
    /// "‹ Settings" / "‹ Networks" and the page title: `(x, y, width, size)`.
    pub back_text: (f64, f64, f64, f64),
    pub title: (f64, f64, f64, f64),
    /// Tap region of the back link: `x < .0 && y < .1`.
    pub back_hit: (f64, f64),
    pub refresh_text: (f64, f64, f64, f64),
    pub refresh_hit: Rect,
    // List page.
    pub current_card: Rect,
    /// The current card's three lines, as offsets from its top.
    pub current_dy: (f64, f64, f64),
    pub list_label: (f64, f64, f64, f64),
    /// The scrolling list's viewport (clip and tap region both).
    pub list_view: Rect,
    pub list_clip: Rect,
    pub row_x: f64,
    pub row_w: f64,
    /// A network row's card height, and the pitch from one row to the next.
    pub row_h: f64,
    pub row_pitch: f64,
    /// Name, status and chevron offsets from a row's top.
    pub row_dy: (f64, f64, f64),
    pub row_cull: (f64, f64),
    pub list_empty: (f64, f64, f64),
    pub list_message: (f64, f64),
    // Entry page.
    pub net_card: Rect,
    pub net_name_dy: f64,
    pub net_sub_dy: f64,
    pub pw_label: (f64, f64),
    pub field: Rect,
    pub field_text_dy: f64,
    /// Width of the typed (masked) password, left of the counter.
    pub field_text_w: f64,
    pub eye_hit: Rect,
    pub eye_center: (f64, f64),
    /// The "n / 63" counter under the field: `(x, y, width)`.
    pub counter: (f64, f64, f64),
    pub saved_change: Rect,
    pub saved_forget: Rect,
    /// Text offset inside the saved-network buttons.
    pub saved_text_dy: f64,
    pub banner_saved_y: f64,
    pub banner_unsaved_y: f64,
    pub banner: (f64, f64, f64),
    pub buttons: (Rect, Rect),
    pub button_text_dx: (f64, f64),
    pub button_text_dy: f64,
    pub entry_message: (f64, f64),
    // Connecting page.
    pub connecting_card: Rect,
    pub connecting_title_dy: f64,
    pub connecting_sub_dy: f64,
    pub connecting_cancel: Rect,
    pub connecting_cancel_text: (f64, f64),
    // Forget confirmation.
    pub forget_card: Rect,
    pub forget_title_dy: f64,
    pub forget_sub_dy: f64,
    pub forget_keep: Rect,
    pub forget_confirm: Rect,
    pub forget_text_dx: (f64, f64),
    pub forget_text_dy: f64,
    pub status_message: (f64, f64),
    /// Width of a one-line status or error message.
    pub message_w: f64,
    /// How far the Entry page, header included, has panned up.
    pub entry_pan: f64,
}

/// The layout for a real surface: the portrait artwork, or the wide layout
/// sized to the surface itself (the landscape panel or an HDMI monitor).
pub fn layout_for(width: u32, height: u32, keyboard_inset: f64) -> Layout {
    if wide(width, height) {
        build(f64::from(width), f64::from(height), true, keyboard_inset)
    } else {
        layout(false, keyboard_inset)
    }
}

/// `layout(true, …)` is the wide layout at the landscape panel's own size.
pub fn layout(wide: bool, keyboard_inset: f64) -> Layout {
    if wide {
        build(1232.0, 568.0, true, keyboard_inset)
    } else {
        build(568.0, 1232.0, false, keyboard_inset)
    }
}

/// Texts the layout measures to size their cards; `render::paint_wifi`
/// paints these same strings.
pub const SAVED_LINE: &str = "99 saved  ·  tap to connect";
pub const CONNECTING_SUB: &str = "Checking association, then saving for reconnect";
pub const FORGET_SUB: &str = "It will not reconnect automatically.";
pub const LONGEST_SECURITY: &str = "WPA2-Personal · password required";
pub const CURRENT_LABEL: &str = "Current connection";
pub const CHANGE_PASSWORD: &str = "Change password…";
pub const FORGET_NETWORK: &str = "Forget network…";
/// The saved-network buttons' text inset, each side.
pub const SAVED_INSET: f64 = 14.0;
pub const FORGET_TITLE: &str = "Forget saved network?";

/// The type roles at the current step and theme size, as drawn pixels in
/// the layout's units, and the height of one line of each.
struct Roles {
    title: f64,
    body: f64,
    label: f64,
    caption: f64,
}

impl Roles {
    fn current() -> Self {
        let s = crate::layout_text_scale().max(1.0) * crate::layout_theme_font();
        Self {
            title: crate::render::TYPE_TITLE * s,
            body: crate::render::TYPE_BODY * s,
            label: crate::render::TYPE_LABEL * s,
            caption: crate::render::TYPE_CAPTION * s,
        }
    }
}

fn line(px: f64) -> f64 {
    (px * 1.25).ceil()
}

fn width_of(text: &str, px: f64) -> f64 {
    crate::render::measured_text_width(text, px, pango::Weight::Normal)
}

/// Wrapped height, measured a little narrower than painted so hinting can
/// only leave spare room.
fn wrapped(text: &str, px: f64, width: f64) -> f64 {
    f64::from(crate::render::wrapped_line_count(text, px, width - 4.0, pango::Weight::Normal)) * line(px)
}

/// Portrait stacks every page in one 520-wide column of the 568x1232
/// artwork; wide keeps status and password on the left (520/1184 of the
/// content width) and the list and the page's buttons on the right.
fn build(w: f64, h: f64, wide: bool, keyboard_inset: f64) -> Layout {
    let r = Roles::current();
    let (lab, cap, body, title) = (line(r.label), line(r.caption), line(r.body), line(r.title));
    // The short landscape panel packs the left column tighter, so the
    // password field stays clear of its 240 px keyboard at 100%.
    let pad = if wide { 12.0 } else { 16.0 };
    let (lw, rx, rw) = if wide {
        let s = (w - 48.0) / 1184.0;
        let lw = 520.0 * s;
        let rx = 24.0 + lw + 56.0 * s;
        (lw, rx, w - 24.0 - rx)
    } else {
        (w - 48.0, 24.0, w - 48.0)
    };
    // Header: the back link, then the title under it; Refresh at the right.
    let top_y = if wide { 14.0 } else { 45.0 };
    let title_y = top_y + lab + if wide { 2.0 } else { 16.0 };
    let title_size = if wide { crate::render::TYPE_BODY } else { crate::render::TYPE_TITLE };
    let title_h = if wide { body } else { title };
    let back_w = width_of("‹ Settings", r.label).max(width_of("‹ Networks", r.label)) + 8.0;
    let refresh_w = width_of("Refresh", r.label) + 8.0;
    let refresh_x = w - 24.0 - refresh_w;
    let content = title_y + title_h + if wide { 4.0 } else { 12.0 };

    // List page.
    let current_label_h = wrapped(CURRENT_LABEL, r.caption, lw - 36.0);
    let current_dy = (pad, pad + current_label_h + 2.0, pad + current_label_h + 2.0 + body + 2.0);
    let current_h = current_dy.2 + wrapped(SAVED_LINE, r.caption, lw - 36.0) + pad;
    let current_card = (24.0, content, lw, current_h);
    let (list_label, list_y) = if wide {
        ((rx + 4.0, top_y + 8.0, (refresh_x - 24.0 - rx).max(80.0), crate::render::TYPE_CAPTION), top_y + lab + 18.0)
    } else {
        let y = content + current_h + 22.0;
        ((28.0, y, rw - 8.0, crate::render::TYPE_CAPTION), y + cap + 12.0)
    };
    let (list_bottom, list_message) = if wide {
        (h - 24.0, (30.0, content + current_h + 16.0))
    } else {
        let message_y = h - 24.0 - cap - 12.0;
        (message_y - 8.0, (30.0, message_y))
    };
    let list_h = (list_bottom - list_y).max(0.0);
    let row_h = (14.0 + lab + 2.0 + cap + 14.0).max(78.0);
    let row_pitch = row_h + 10.0;

    // Entry page.
    let sub_h = wrapped(LONGEST_SECURITY, r.caption, lw - 50.0);
    let net_card = (24.0, content, lw, pad + body + 4.0 + sub_h + pad);
    let pw_label = (28.0, content + net_card.3 + if wide { 6.0 } else { 14.0 });
    let field_h = (body + 40.0).max(if wide { 78.0 } else { 90.0 });
    let field = (24.0, pw_label.1 + cap + if wide { 2.0 } else { 6.0 }, lw, field_h);
    // The "n / 63" counter sits inside the field, left of the eye.
    let eye_x = 24.0 + lw - 76.0;
    let counter_w = width_of("63 / 63", r.caption) + 8.0;
    let counter = (eye_x - counter_w, field.1 + (field_h - cap) / 2.0, counter_w);
    let below_field = field.1 + field_h + 14.0;
    let gap = if wide { 16.0 } else { 20.0 };
    let half = (rw - gap) / 2.0;
    let second = rx + half + gap;
    let saved_w = if wide { half } else { rw } - 2.0 * SAVED_INSET;
    let saved_lines = wrapped(CHANGE_PASSWORD, r.label, saved_w).max(wrapped(FORGET_NETWORK, r.label, saved_w));
    let saved_h = (saved_lines + 28.0).max(62.0);
    let saved_top = if wide { content } else { below_field };
    // Wide: Change password and Forget side by side; portrait stacks them
    // full width so neither label is shortened.
    let (saved_change, saved_forget) = if wide {
        ((rx, saved_top, half, saved_h), (second, saved_top, half, saved_h))
    } else {
        ((rx, saved_top, rw, saved_h), (rx, saved_top + saved_h + 12.0, rw, saved_h))
    };
    // Portrait has room for a two-line rejection message; the landscape
    // panel's right column, above its keyboard, for one.
    let banner_h = if wide { (cap + 18.0).max(52.0) } else { (2.0 * cap + 30.0).max(64.0) };
    let banner_saved_y = saved_forget.1 + saved_h + 12.0;
    let button_h = (lab + if wide { 32.0 } else { 44.0 }).max(if wide { 72.0 } else { 88.0 });
    let bottom = h - 24.0 - keyboard_inset;
    let top = bottom - button_h;
    let banner_unsaved_y = if wide { top - banner_h - 12.0 } else { below_field };
    // An Entry page too tall for what the keyboard and buttons leave pans
    // up, header included (Android's adjustPan), so the field -- and in
    // portrait the error banner under it -- stays visible. Portrait only
    // needs it with the keyboard raised; at large steps the landscape
    // panel's left column needs it without.
    let pan = if keyboard_inset <= 0.0 && !wide {
        0.0
    } else {
        let (needed, limit) = if wide {
            (field.1 + field_h, h - keyboard_inset - 8.0)
        } else {
            (banner_unsaved_y + banner_h, top - 12.0)
        };
        (needed - limit).max(0.0)
    };
    let up = |rect: Rect| (rect.0, rect.1 - pan, rect.2, rect.3);
    let (net_card, field) = (up(net_card), up(field));
    let pw_label = (pw_label.0, pw_label.1 - pan);
    let counter = (counter.0, counter.1 - pan, counter.2);
    let (saved_change, saved_forget, banner_saved_y, banner_unsaved_y) = if wide {
        (saved_change, saved_forget, banner_saved_y, banner_unsaved_y)
    } else {
        (up(saved_change), up(saved_forget), banner_saved_y - pan, banner_unsaved_y - pan)
    };
    let centred = |label: &str, width: f64| ((width - width_of(label, r.label)) / 2.0).max(12.0);

    // Connecting and Forget pages.
    let card_pad = 28.0;
    let connecting_sub_dy = card_pad + body + 14.0;
    let connecting_card = (
        24.0,
        if wide { content } else { 220.0 },
        lw,
        connecting_sub_dy + wrapped(CONNECTING_SUB, r.caption, lw - 36.0) + card_pad,
    );
    let action_h = (lab + 50.0).max(if wide { 100.0 } else { 110.0 });
    let connecting_cancel = if wide {
        (rx, content, rw, action_h)
    } else {
        // Above where Cancel/Connect sit with no keyboard raised.
        (24.0, h - 112.0 - action_h, rw, action_h)
    };
    let forget_sub_dy = card_pad + wrapped(FORGET_TITLE, r.body, lw - 36.0) + 14.0;
    let forget_card = (
        24.0,
        if wide { content } else { 230.0 },
        lw,
        forget_sub_dy + wrapped(FORGET_SUB, r.caption, lw - 36.0) + card_pad,
    );
    let forget_y = if wide { content } else { (forget_card.1 + forget_card.3 + 40.0).max(850.0) };
    let card_bottom = |card: Rect| card.1 + card.3 + 16.0;
    Layout {
        wide,
        back_text: (28.0, top_y, back_w, crate::render::TYPE_LABEL),
        title: (28.0, title_y, (refresh_x - 40.0).max(200.0), title_size),
        back_hit: ((28.0 + back_w + 24.0).max(150.0), title_y),
        refresh_text: (refresh_x, top_y + if wide { 8.0 } else { 0.0 }, refresh_w, crate::render::TYPE_LABEL),
        refresh_hit: (refresh_x - 46.0, 0.0, w - refresh_x + 46.0, list_y.min(title_y + title_h)),
        current_card,
        current_dy,
        list_label,
        list_view: (rx, list_y, rw, list_h),
        list_clip: (rx - 4.0, list_y, rw + 8.0, list_h),
        row_x: rx,
        row_w: rw,
        row_h,
        row_pitch,
        row_dy: (14.0, 14.0 + lab + 2.0, (row_h - lab) / 2.0),
        row_cull: (list_y - row_pitch, list_y + list_h),
        list_empty: (rx + 18.0, list_y + 26.0, rw - 36.0),
        list_message,
        net_card,
        net_name_dy: pad,
        net_sub_dy: pad + body + 4.0,
        pw_label,
        field,
        field_text_dy: (field_h - body) / 2.0,
        field_text_w: counter.0 - 24.0 - 18.0 - 8.0,
        eye_hit: (eye_x, field.1, 72.0, field_h),
        eye_center: (24.0 + lw - 40.0, field.1 + field_h / 2.0),
        counter,
        saved_change,
        saved_forget,
        saved_text_dy: (saved_h - saved_lines) / 2.0,
        banner_saved_y,
        banner_unsaved_y,
        banner: (rw, banner_h, rw - 72.0),
        buttons: ((rx, top, half, button_h), (second, top, half, button_h)),
        button_text_dx: (centred("Cancel", half), centred("Connect", half)),
        button_text_dy: (button_h - lab) / 2.0,
        entry_message: (rx + 4.0, top - cap - 10.0),
        connecting_card,
        connecting_title_dy: card_pad,
        connecting_sub_dy,
        connecting_cancel,
        connecting_cancel_text: (centred("Cancel connection", connecting_cancel.2), (action_h - lab) / 2.0),
        forget_card,
        forget_title_dy: card_pad,
        forget_sub_dy,
        forget_keep: (rx, forget_y, half, action_h),
        forget_confirm: (second, forget_y, half, action_h),
        forget_text_dx: (centred("Keep", half), centred("Forget", half)),
        forget_text_dy: (action_h - lab) / 2.0,
        status_message: (30.0, card_bottom(connecting_card).max(card_bottom(forget_card))),
        entry_pan: pan,
        message_w: if wide { lw } else { rw },
    }
}

pub fn all_networks(snapshot: &Snapshot) -> Vec<Network> {
    let mut rows = snapshot.saved.clone();
    for item in &snapshot.networks {
        if !rows.iter().any(|other| other.ssid == item.ssid) {
            rows.push(item.clone());
        }
    }
    rows
}

pub fn useful_error(code: &str) -> &'static str {
    match code {
        "authentication-failed" => "Password was not accepted. Check it and try again.",
        "connection-timeout" | "radio-timeout" | "Wi-Fi deadline exceeded" => {
            "Connection timed out. Move closer and try again."
        }
        "radio-unavailable" | "service-unavailable" | "Wi-Fi service unavailable" => {
            "Wi-Fi is unavailable. Check the radio and retry."
        }
        "scan-too-soon" => "Please wait a moment before scanning again.",
        "unsupported-saved-config" => {
            "Saved Wi-Fi settings need operator review; they were not changed."
        }
        "saved-limit" => "Saved network list is full. Forget one before connecting.",
        "cancelled" => "Connection cancelled. Saved networks were kept.",
        "service-restart-failed" | "reconnect-pending" => {
            "Saved network restored; reconnect is pending. Retry status shortly."
        }
        "forget-failed" => "Could not forget this network. Retry later.",
        "invalid-password" => "Use an 8–63 character Wi-Fi password.",
        "unsupported-security" => "This network's security is not supported yet.",
        "not-saved" => "This network is not saved. Refresh the list.",
        "save-failed" | "unsafe-credential" => "Could not save the network securely. Try again.",
        "scan-too-large" | "link-too-large" | "response-too-large" => {
            "The Wi-Fi list is too large. Retry the scan."
        }
        "unsafe-runtime" | "denied" => {
            "Wi-Fi Settings is unavailable. Ask an operator to check it."
        }
        _ => "Wi-Fi request failed. Retry or return to Settings.",
    }
}

// X11/xkbcommon keysym values for the three non-text keys the password
// editor cares about. Kept as plain numbers rather than depending on the
// `xkeysym`/`xkbcommon` crates here: this module is deliberately independent
// of Wayland (see its own header doc), and these three values are stable
// standard keysyms, not something a keymap changes.
const KEYSYM_BACKSPACE: u32 = 0xff08;
const KEYSYM_RETURN: u32 = 0xff0d;
const KEYSYM_KP_ENTER: u32 = 0xff8d;
const KEYSYM_ESCAPE: u32 = 0xff1b;

/// Maps one `wl_keyboard` key-press (from the system keyboard, physical or
/// virtual -- both arrive identically once the overlay surface holds
/// keyboard focus) to a Wi-Fi intent. `keysym` identifies non-text keys;
/// `utf8` is the already-shifted/composed text xkbcommon produced for an
/// ordinary character, so this need not track Shift itself. Only a single
/// printable ASCII character is accepted per event -- multi-character
/// composition (dead keys, IME) and control characters are rejected, same
/// as `Secret::push`'s own guard, and this function never sees or returns
/// the password itself, only which key it maps to.
pub fn key_event_intent(keysym: u32, utf8: Option<&str>) -> Option<Intent> {
    match keysym {
        KEYSYM_BACKSPACE => return Some(Intent::Backspace),
        KEYSYM_RETURN | KEYSYM_KP_ENTER => return Some(Intent::Connect),
        KEYSYM_ESCAPE => return Some(Intent::Back),
        _ => {}
    }
    let mut chars = utf8?.chars();
    let c = chars.next()?;
    if chars.next().is_some() || c.is_control() || !c.is_ascii() {
        return None;
    }
    Some(Intent::Key(c))
}

pub fn hit(
    view: &WifiPublic,
    start: (f64, f64),
    end: (f64, f64),
    width: u32,
    height: u32,
) -> Option<Intent> {
    if width == 0 || height == 0 {
        return None;
    }
    let lay = layout_for(width, height, view.keyboard_inset);
    // Portrait artwork is authored at 568x1232 while Wayland supplies output
    // pixels; the wide layout is in real pixels.
    let (sx, sy) = layout_scale(width, height);
    let scale = |point: (f64, f64)| (point.0 * sx, point.1 * sy);
    let start = scale(start);
    let (x, y) = scale(end);
    let dy = y - start.1;
    if view.page == Page::Closed {
        return None;
    }
    let scroll_start = if lay.wide {
        contains(lay.list_view, start.0, start.1)
    } else {
        start.1 >= lay.list_view.1
    };
    if view.page == Page::List && scroll_start && dy.abs() > 20.0 {
        return Some(Intent::Scroll(-dy));
    }
    if (x - start.0).abs() > 18.0 || dy.abs() > 18.0 {
        return None;
    }
    let down = target(view, &lay, start.0, start.1);
    let up = target(view, &lay, x, y);
    (down == up).then_some(up).flatten()
}

fn target(view: &WifiPublic, lay: &Layout, x: f64, y: f64) -> Option<Intent> {
    let header_pan = if view.page == Page::Entry { lay.entry_pan } else { 0.0 };
    if y < lay.back_hit.1 - header_pan && x < lay.back_hit.0 {
        return Some(Intent::Back);
    }
    if view.page == Page::List {
        if contains(lay.refresh_hit, x, y) {
            return Some(Intent::Refresh);
        }
        if contains(lay.list_view, x, y) {
            let index = ((y - lay.list_view.1 + view.scroll) / lay.row_pitch).floor() as usize;
            let count = view.snapshot.as_ref().map_or(0, |s| all_networks(s).len());
            return (index < count).then_some(Intent::Select(index));
        }
    }
    if view.page == Page::Connecting {
        if contains(lay.connecting_cancel, x, y) {
            return Some(Intent::CancelPending);
        }
        return None;
    }
    if view.page == Page::ForgetConfirm {
        if contains(lay.forget_keep, x, y) {
            return Some(Intent::ForgetCancel);
        }
        if contains(lay.forget_confirm, x, y) {
            return Some(Intent::ForgetConfirm);
        }
        return None;
    }
    if view.page != Page::Entry {
        return None;
    }
    if !view.use_saved && !view.pending
        && view.selected.as_ref().is_some_and(|n| n.security == Security::Wpa2Psk)
        && contains(lay.eye_hit, x, y) {
        return Some(Intent::TogglePassword);
    }
    let (cancel, connect) = lay.buttons;
    if contains(cancel, x, y) {
        return Some(Intent::Back);
    }
    if contains(connect, x, y) {
        return Some(Intent::Connect);
    }
    let is_saved = view.selected.as_ref().is_some_and(|selected| {
        view.snapshot.as_ref().is_some_and(|snapshot| {
            snapshot
                .saved
                .iter()
                .any(|saved| saved.ssid == selected.ssid)
        })
    });
    if is_saved {
        if contains(lay.saved_change, x, y)
            && view.use_saved
            && view
                .selected
                .as_ref()
                .is_some_and(|n| n.security == Security::Wpa2Psk)
        {
            return Some(Intent::EditPassword);
        }
        if contains(lay.saved_forget, x, y) {
            return Some(Intent::Forget);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    fn snapshot() -> Snapshot {
        Snapshot {
            networks: vec![Network {
                ssid: "Example Secure".into(),
                security: Security::Wpa2Psk,
            }],
            current: None,
            saved: Vec::new(),
            error: None,
        }
    }
    #[test]
    fn wifi_password_eye_preserves_input_focus_and_redacts_public_state() {
        let mut view = WifiView::default();
        view.page = Page::List; view.snapshot = Some(snapshot()); view.select(0);
        for ch in "sample-pass".chars() { view.key(Intent::Key(ch)); }
        assert!(view.password_preview().is_none());
        assert!(view.wants_keyboard());
        view.toggle_password();
        assert_eq!(view.password_preview(), Some("sample-pass"));
        assert!(!format!("{:?}", view.public()).contains("sample-pass"));
        assert_eq!(target(&view.public(), &layout(false, 0.0), 504.0, 350.0), Some(Intent::TogglePassword));
        view.key(Intent::Backspace);
        assert_eq!(view.password_preview(), Some("sample-pas"));
        view.toggle_password();
        assert!(view.password_preview().is_none());
        assert_eq!(view.public().password_len, 10);
        assert!(view.wants_keyboard());
        view.toggle_password(); view.back();
        assert!(view.password_preview().is_none());
        view.select(0);
        assert!(!view.public().password_visible);
    }

    #[test]
    fn wifi_password_eye_resets_on_connect_and_saved_entry_never_reveals() {
        let mut view = WifiView::default();
        view.page = Page::List; view.snapshot = Some(snapshot()); view.select(0);
        for ch in "sample-pass".chars() { view.key(Intent::Key(ch)); }
        view.toggle_password();
        assert!(view.connect_request().is_some());
        assert!(view.password_preview().is_none());
        view.submit_failed("Could not connect");
        assert!(!view.public().password_visible);
        view.use_saved = true; view.toggle_password();
        assert!(view.password_preview().is_none());
        assert_ne!(target(&view.public(), &layout(false, 0.0), 504.0, 350.0), Some(Intent::TogglePassword));
        view.close();
        assert_eq!(view.public().password_len, 0);
    }

    #[test]
    fn keyboard_masks_and_cancel_clears() {
        let mut view = WifiView::default();
        view.page = Page::List;
        view.snapshot = Some(snapshot());
        view.select(0);
        for c in "examplepass".chars() {
            view.key(Intent::Key(c));
        }
        assert_eq!(view.public().password_len, 11);
        assert!(view.can_connect());
        assert!(format!("{:?}", view.public()).find("examplepass").is_none());
        view.back();
        assert_eq!(view.public().password_len, 0);
    }
    #[test]
    fn open_network_connects_without_password_editor() {
        let mut view = WifiView::default();
        view.page = Page::List;
        view.snapshot = Some(Snapshot {
            networks: vec![Network {
                ssid: "Example Guest".into(),
                security: Security::Open,
            }],
            current: None,
            saved: Vec::new(),
            error: None,
        });
        view.select(0);
        assert!(!view.use_saved);
        assert_eq!(view.public().password_len, 0);
        assert!(view.can_connect());
        assert!(matches!(
            view.connect_request(),
            Some(WifiRequest::Connect {
                security: Security::Open,
                ..
            })
        ));
    }
    #[test]
    fn scroll_does_not_select_and_back_is_reachable() {
        let mut view = WifiView::default();
        view.page = Page::List;
        view.snapshot = Some(snapshot());
        assert!(matches!(
            hit(&view.public(), (250.0, 400.0), (250.0, 500.0), 568, 1232),
            Some(Intent::Scroll(_))
        ));
        assert!(matches!(
            hit(&view.public(), (50.0, 50.0), (50.0, 50.0), 568, 1232),
            Some(Intent::Back)
        ));
        let mut long = snapshot();
        long.networks = (0..20)
            .map(|index| Network {
                ssid: format!("Example {index}"),
                security: Security::Open,
            })
            .collect();
        view.snapshot = Some(long);
        view.scroll(100.0);
        assert_eq!(view.scroll, 100.0);
        view.scroll(-40.0);
        assert_eq!(view.scroll, 60.0);
    }
    #[test]
    fn hit_uses_rendered_output_scale() {
        let mut view = WifiView::default();
        view.page = Page::List;
        view.snapshot = Some(snapshot());
        let lay = layout(false, 0.0);
        let point = (250.0 * 390.0 / 568.0, (lay.list_view.1 + lay.row_h / 2.0) * 844.0 / 1232.0);
        assert!(matches!(
            hit(&view.public(), point, point, 390, 844),
            Some(Intent::Select(0))
        ));
    }
    #[test]
    fn release_must_stay_on_same_key_or_confirm_control() {
        let mut view = WifiView::default();
        view.page = Page::Entry;
        // A drag that leaves the Connect button between down and up must
        // not fire it -- same rule the old in-app keypad relied on, now
        // covering the Cancel/Connect pair that is the whole Entry-page
        // touch surface once the system keyboard owns the rest.
        assert_eq!(
            hit(&view.public(), (400.0, 1150.0), (100.0, 1150.0), 568, 1232),
            None
        );
        assert_eq!(
            hit(&view.public(), (400.0, 1150.0), (400.0, 1150.0), 568, 1232),
            Some(Intent::Connect)
        );
        assert_eq!(
            hit(&view.public(), (100.0, 1150.0), (100.0, 1150.0), 568, 1232),
            Some(Intent::Back)
        );
        view.page = Page::ForgetConfirm;
        assert_eq!(
            hit(&view.public(), (285.0, 900.0), (295.0, 900.0), 568, 1232),
            None
        );
        assert_eq!(
            hit(&view.public(), (300.0, 900.0), (300.0, 900.0), 568, 1232),
            Some(Intent::ForgetConfirm)
        );
    }
    #[test]
    fn raised_keyboard_moves_cancel_connect_above_it() {
        let mut view = WifiView::default();
        view.page = Page::Entry;
        view.set_keyboard_inset(400.0);
        // The old, unraised position (1150) now hits nothing -- the
        // keyboard covers it -- while the reflowed position just above the
        // keyboard's top edge (1232 - 400 = 832) hits Connect.
        assert_eq!(
            hit(&view.public(), (400.0, 1150.0), (400.0, 1150.0), 568, 1232),
            None
        );
        assert_eq!(
            hit(&view.public(), (400.0, 760.0), (400.0, 760.0), 568, 1232),
            Some(Intent::Connect)
        );
        assert_eq!(
            hit(&view.public(), (100.0, 760.0), (100.0, 760.0), 568, 1232),
            Some(Intent::Back)
        );
    }
    #[test]
    fn wants_keyboard_only_for_an_unsaved_wpa2_field() {
        let mut view = WifiView::default();
        view.page = Page::List;
        view.snapshot = Some(snapshot());
        view.select(0);
        assert!(view.wants_keyboard());
        view.edit_password();
        assert!(view.wants_keyboard());
        let mut saved = snapshot();
        saved.saved = saved.networks.clone();
        view.snapshot = Some(saved);
        view.page = Page::List;
        view.select(0);
        assert!(!view.wants_keyboard(), "a saved credential needs no typing");
        view.page = Page::List;
        view.snapshot = Some(Snapshot {
            networks: vec![Network {
                ssid: "Example Guest".into(),
                security: Security::Open,
            }],
            current: None,
            saved: Vec::new(),
            error: None,
        });
        view.select(0);
        assert!(!view.wants_keyboard(), "an open network has no password field");
    }
    #[test]
    fn key_event_intent_maps_control_keys_and_rejects_composed_text() {
        assert_eq!(key_event_intent(KEYSYM_BACKSPACE, None), Some(Intent::Backspace));
        assert_eq!(key_event_intent(KEYSYM_RETURN, Some("\r")), Some(Intent::Connect));
        assert_eq!(key_event_intent(KEYSYM_KP_ENTER, None), Some(Intent::Connect));
        assert_eq!(key_event_intent(KEYSYM_ESCAPE, None), Some(Intent::Back));
        assert_eq!(key_event_intent(0x0061, Some("a")), Some(Intent::Key('a')));
        assert_eq!(key_event_intent(0x0041, Some("A")), Some(Intent::Key('A')));
        // No text at all (a bare modifier key) maps to nothing.
        assert_eq!(key_event_intent(0xffe1, None), None);
        // Multi-character composition (dead keys, IME) is rejected rather
        // than silently taking the first character of something the user
        // did not type as a single keystroke.
        assert_eq!(key_event_intent(0x0000, Some("ab")), None);
        // A control character slipping through as "utf8" (some compositors
        // report one for Tab) never becomes a password character.
        assert_eq!(key_event_intent(0x0000, Some("\t")), None);
        // Non-ASCII text is rejected -- `Secret::push` only accepts ASCII,
        // matching the 8-63 byte WPA2 passphrase length this app already
        // enforces on `char` count, not UTF-8 byte count.
        assert_eq!(key_event_intent(0x0000, Some("é")), None);
        assert_eq!(key_event_intent(0x0000, None), None);
    }
    #[test]
    fn closed_or_reopened_view_ignores_old_network_reply() {
        let mut view = WifiView::default();
        view.open();
        view.submitted(17, Kind::Scan);
        view.close();
        view.open();
        view.submitted(18, Kind::Scan);
        assert!(!view.accept(WifiReply {
            id: 17,
            kind: Kind::Scan,
            result: Ok(WifiResult::Snapshot(snapshot())),
        }));
        assert!(view.snapshot.is_none());
        assert!(view.accept(WifiReply {
            id: 18,
            kind: Kind::Scan,
            result: Ok(WifiResult::Snapshot(snapshot())),
        }));
        assert_eq!(view.snapshot.as_ref().map(|s| s.networks.len()), Some(1));
    }
    #[test]
    fn status_after_save_updates_current_without_discarding_scan_rows() {
        let mut view = WifiView::default();
        view.page = Page::List;
        view.snapshot = Some(snapshot());
        view.submitted(4, Kind::Status);
        let mut status = snapshot();
        status.networks.clear();
        status.current = Some("Example Secure".into());
        status.saved = vec![Network {
            ssid: "Example Secure".into(),
            security: Security::Wpa2Psk,
        }];
        assert!(view.accept(WifiReply {
            id: 4,
            kind: Kind::Status,
            result: Ok(WifiResult::Snapshot(status))
        }));
        assert_eq!(view.snapshot.as_ref().unwrap().networks.len(), 1);
        assert_eq!(
            view.snapshot.as_ref().unwrap().current.as_deref(),
            Some("Example Secure")
        );
    }
    #[test]
    fn forget_is_explicit_and_does_not_expose_password() {
        let mut view = WifiView::default();
        view.page = Page::List;
        let mut data = snapshot();
        data.saved = data.networks.clone();
        view.snapshot = Some(data);
        view.select(0);
        assert!(view.use_saved);
        assert!(matches!(
            view.connect_request(),
            Some(WifiRequest::ConnectSaved { .. })
        ));
        view.page = Page::Entry;
        view.edit_password();
        assert!(!view.use_saved);
        for ch in "examplepass".chars() {
            view.key(Intent::Key(ch));
        }
        assert!(view.forget_request().is_none());
        view.page = Page::ForgetConfirm;
        assert!(matches!(
            view.forget_request(),
            Some(WifiRequest::Forget { .. })
        ));
        assert!(!format!("{:?}", view.public()).contains("examplepass"));
    }

    const LONG: &str = "A Rather Long Network Name For The Neighbours Upstairs";

    fn inside_panel(name: &str, rect: Rect, keyboard_top: f64) {
        let (x, y, w, h) = rect;
        assert!(
            x >= 0.0 && y >= 0.0 && x + w <= 1232.0 && y + h <= keyboard_top,
            "{name} ({x},{y},{w},{h}) leaves 1232x{keyboard_top}"
        );
    }

    fn disjoint(items: &[(&str, Rect)]) {
        for (i, a) in items.iter().enumerate() {
            for b in &items[i + 1..] {
                let ((ax, ay, aw, ah), (bx, by, bw, bh)) = (a.1, b.1);
                assert!(
                    ax + aw <= bx || bx + bw <= ax || ay + ah <= by || by + bh <= ay,
                    "{} overlaps {}",
                    a.0,
                    b.0
                );
            }
        }
    }

    fn centre(rect: Rect) -> (f64, f64) {
        (rect.0 + rect.2 / 2.0, rect.1 + rect.3 / 2.0)
    }

    fn tap(view: &WifiPublic, point: (f64, f64)) -> Option<Intent> {
        hit(view, point, point, 1232, 568)
    }

    fn fixture(page: Page, selected: Option<&str>, use_saved: bool, inset: f64) -> WifiPublic {
        crate::evidence_render::fixture_wifi(page, selected, use_saved, inset, None)
    }

    #[test]
    fn wifi_cards_grow_with_the_text_step_and_never_overlap() {
        use crate::render::{TYPE_CAPTION, TYPE_LABEL};
        for step in [1.0, 1.5, 2.0] {
            crate::set_layout_text_scale(step);
            for wide in [false, true] {
                let lay = layout(wide, 0.0);
                // A row holds its name and status lines.
                assert!(lay.row_h >= (TYPE_LABEL + TYPE_CAPTION) * step * 1.25 + 28.0, "step {step} wide {wide}");
                assert!(lay.row_dy.1 >= lay.row_dy.0 + TYPE_LABEL * step * 1.25);
                // The current card sits under the title; the list under both.
                assert!(lay.current_card.1 >= lay.title.1 + lay.title.3 * step);
                if !wide {
                    assert!(lay.list_view.1 >= lay.current_card.1 + lay.current_card.3);
                    // Entry: the network card, field and saved buttons stack.
                    assert!(lay.field.1 >= lay.net_card.1 + lay.net_card.3);
                    assert!(lay.saved_change.1 >= lay.field.1 + lay.field.3);
                    assert!(lay.counter.0 + lay.counter.2 <= lay.eye_hit.0);
                    disjoint(&[("change", lay.saved_change), ("forget", lay.saved_forget), ("cancel", lay.buttons.0), ("connect", lay.buttons.1)]);
                }
                for (name, h, size) in [
                    ("button", lay.buttons.0 .3, TYPE_LABEL),
                    ("saved", lay.saved_change.3, TYPE_LABEL),
                    ("keep", lay.forget_keep.3, TYPE_LABEL),
                    ("abort", lay.connecting_cancel.3, TYPE_LABEL),
                ] {
                    assert!(h >= size * step * 1.25 + 24.0, "{name} at step {step} wide {wide}");
                }
            }
        }
        crate::set_layout_text_scale(1.0);
    }

    #[test]
    fn the_portrait_wifi_layout_keeps_the_artworks_literals() {
        assert!(!wide(568, 1232) && !wide(1080, 1920) && !wide(1280, 1024));
        let lay = layout(false, 0.0);
        assert_eq!(lay.buttons, ((24.0, 1120.0, 250.0, 88.0), (294.0, 1120.0, 250.0, 88.0)));
        assert_eq!((lay.list_view.0, lay.list_view.2), (24.0, 520.0));
        assert!(lay.list_view.1 + lay.list_view.3 <= lay.list_message.1);
        assert_eq!(layout(false, 440.0).buttons.0 .1, entry_buttons_rect(440.0).0);
        assert_eq!(layout_scale(568, 1232), (1.0, 1.0));
    }

    #[test]
    fn every_wide_wifi_list_control_is_inside_the_panel_and_taps_at_its_centre() {
        let view = fixture(Page::List, None, false, 0.0);
        let lay = layout(true, 0.0);
        let items = [
            ("current", lay.current_card),
            ("list", lay.list_view),
            ("refresh", lay.refresh_hit),
            ("back", (0.0, 0.0, lay.back_hit.0, lay.back_hit.1)),
        ];
        for (name, rect) in items {
            inside_panel(name, rect, 568.0);
        }
        inside_panel("list clip", lay.list_clip, 568.0);
        disjoint(&items[1..]);
        assert_eq!(tap(&view, centre(items[3].1)), Some(Intent::Back));
        assert_eq!(tap(&view, centre(lay.refresh_hit)), Some(Intent::Refresh));
        // Every row that is fully inside the viewport is hit at its centre,
        // and each row's painted card lies inside the panel.
        let rows = all_networks(view.snapshot.as_ref().unwrap()).len();
        let mut reachable = 0;
        for index in 0..rows {
            let card = (lay.row_x, lay.list_view.1 + index as f64 * lay.row_pitch, lay.row_w, lay.row_h);
            if card.1 + card.3 > lay.list_view.1 + lay.list_view.3 {
                continue;
            }
            inside_panel("row", card, 568.0);
            assert_eq!(tap(&view, centre(card)), Some(Intent::Select(index)), "row {index}");
            reachable += 1;
        }
        assert!(reachable >= 4, "several networks reachable without scrolling: {reachable}");
        // The rest are reached by scrolling the list: a vertical drag inside it.
        let drag = hit(&view, (900.0, 400.0), (900.0, 300.0), 1232, 568);
        assert_eq!(drag, Some(Intent::Scroll(100.0)));
        let mut state = WifiView { snapshot: view.snapshot.clone(), page: Page::List, ..WifiView::default() };
        state.set_surface(1232, 568);
        state.scroll(10_000.0);
        let last_top = lay.list_view.1 + (rows - 1) as f64 * lay.row_pitch - state.scroll;
        assert!(last_top + lay.row_h <= lay.list_view.1 + lay.list_view.3 + 1.0, "the last row scrolls fully into view");
        let scrolled = WifiPublic { scroll: state.scroll, ..view.clone() };
        assert_eq!(
            tap(&scrolled, (900.0, last_top + lay.row_h / 2.0)),
            Some(Intent::Select(rows - 1)),
            "tap on the last row after scrolling"
        );
    }

    #[test]
    fn every_wide_wifi_entry_control_is_inside_the_panel_clear_of_the_keyboard() {
        // The landscape keyboard is 240 px; the page keeps clear of it.
        for inset in [0.0, 240.0] {
            let keyboard_top = 568.0 - inset;
            let view = fixture(Page::Entry, Some(LONG), false, inset);
            let lay = layout(true, inset);
            let (cancel, connect) = lay.buttons;
            let items = [
                ("network", lay.net_card),
                ("field", lay.field),
                ("saved-change", lay.saved_change),
                ("saved-forget", lay.saved_forget),
                ("cancel", cancel),
                ("connect", connect),
            ];
            for (name, rect) in &items {
                inside_panel(name, *rect, keyboard_top);
            }
            // Left column (network, field) and right column (everything else).
            disjoint(&items);
            assert_eq!(tap(&view, centre(cancel)), Some(Intent::Back));
            assert_eq!(tap(&view, centre(connect)), Some(Intent::Connect));
            assert_eq!(tap(&view, centre(lay.eye_hit)), Some(Intent::TogglePassword));
            inside_panel("eye", lay.eye_hit, keyboard_top);
            // The rejected-password banner sits between the saved buttons
            // and the Cancel/Connect row without touching either.
            let (bw, bh, _) = lay.banner;
            for banner_y in [lay.banner_saved_y, lay.banner_unsaved_y] {
                let banner = (cancel.0, banner_y, bw, bh);
                inside_panel("banner", banner, keyboard_top);
                if banner_y == lay.banner_saved_y {
                    disjoint(&[("banner", banner), ("saved-forget", lay.saved_forget), ("saved-change", lay.saved_change)]);
                }
                disjoint(&[("banner", banner), ("cancel", cancel), ("connect", connect)]);
            }
            // The info line above the buttons stays on the panel too.
            assert!(lay.entry_message.1 + 18.0 <= cancel.1 && lay.entry_message.1 >= 0.0);
        }
        // A saved network: Change password and Forget are reachable.
        let saved = fixture(Page::Entry, Some("Home Network"), true, 0.0);
        let lay = layout(true, 0.0);
        assert_eq!(tap(&saved, centre(lay.saved_change)), Some(Intent::EditPassword));
        assert_eq!(tap(&saved, centre(lay.saved_forget)), Some(Intent::Forget));
        // An open network has no eye and no password field to hit.
        let open = fixture(Page::Entry, Some("Guest (open)"), false, 0.0);
        assert_eq!(tap(&open, centre(lay.eye_hit)), None);
    }

    #[test]
    fn the_wide_wifi_layout_keeps_the_panel_literals_and_fills_a_monitor() {
        // The landscape panel keeps its columns and button row.
        let panel = layout_for(1232, 568, 0.0);
        assert_eq!((panel.current_card.0, panel.current_card.2), (24.0, 520.0));
        assert_eq!((panel.list_view.0, panel.list_view.2), (600.0, 608.0));
        assert_eq!(panel.buttons, ((600.0, 472.0, 296.0, 72.0), (912.0, 472.0, 296.0, 72.0)));
        assert_eq!(panel.banner.0, 608.0);
        assert!(panel.refresh_text.0 + panel.refresh_text.2 <= 1208.0 + 1e-9);
        // A monitor: two columns across the whole width, the list to the
        // bottom edge, every control on the surface and reachable.
        for (w, h) in [(1280u32, 800u32), (1920, 1080), (1280, 720)] {
            let (fw, fh) = (f64::from(w), f64::from(h));
            let lay = layout_for(w, h, 0.0);
            assert!(lay.wide);
            let on = |name: &str, (x, y, rw, rh): Rect| {
                assert!(x >= 0.0 && y >= 0.0 && x + rw <= fw && y + rh <= fh, "{name} ({x},{y},{rw},{rh}) leaves {w}x{h}");
            };
            assert_eq!(lay.list_view.0 + lay.list_view.2, fw - 24.0, "{w}x{h} list to the right margin");
            assert_eq!(lay.list_view.1 + lay.list_view.3, fh - 24.0, "{w}x{h} list to the bottom margin");
            assert!(lay.current_card.0 + lay.current_card.2 < lay.list_view.0, "{w}x{h} columns apart");
            let (cancel, connect) = lay.buttons;
            for (name, rect) in [("list", lay.list_view), ("current", lay.current_card), ("field", lay.field), ("eye", lay.eye_hit),
                ("cancel", cancel), ("connect", connect), ("refresh", lay.refresh_hit), ("change", lay.saved_change),
                ("forget", lay.saved_forget), ("keep", lay.forget_keep), ("confirm", lay.forget_confirm), ("abort", lay.connecting_cancel)] {
                on(name, rect);
            }
            assert!(lay.eye_hit.0 + lay.eye_hit.2 <= lay.field.0 + lay.field.2 + 1e-9, "{w}x{h} eye inside the field");
            let list = fixture(Page::List, None, false, 0.0);
            let rows = all_networks(list.snapshot.as_ref().unwrap()).len();
            let last = (lay.row_x + lay.row_w / 2.0, lay.list_view.1 + (rows - 1) as f64 * lay.row_pitch + lay.row_h / 2.0);
            // Scrolled just far enough, the last network taps at its centre.
            let scroll = (last.1 + lay.row_h / 2.0 - lay.list_view.1 - lay.list_view.3).max(0.0);
            let last = (last.0, last.1 - scroll);
            let list = WifiPublic { scroll, ..list };
            assert_eq!(hit(&list, last, last, w, h), Some(Intent::Select(rows - 1)), "{w}x{h} last row");
            let entry = fixture(Page::Entry, Some(LONG), false, 0.0);
            assert_eq!(hit(&entry, centre(connect), centre(connect), w, h), Some(Intent::Connect), "{w}x{h}");
            assert_eq!(hit(&entry, centre(cancel), centre(cancel), w, h), Some(Intent::Back), "{w}x{h}");
            assert_eq!(hit(&entry, centre(lay.eye_hit), centre(lay.eye_hit), w, h), Some(Intent::TogglePassword), "{w}x{h}");
        }
    }

    #[test]
    fn the_wide_connecting_and_forget_pages_are_inside_the_panel_and_reachable() {
        let lay = layout(true, 0.0);
        let connecting = fixture(Page::Connecting, Some(LONG), false, 0.0);
        let items = [("card", lay.connecting_card), ("cancel", lay.connecting_cancel)];
        for (name, rect) in items {
            inside_panel(name, rect, 568.0);
        }
        disjoint(&items);
        assert_eq!(tap(&connecting, centre(lay.connecting_cancel)), Some(Intent::CancelPending));
        let forget = fixture(Page::ForgetConfirm, Some("Home Network"), true, 0.0);
        let items = [("card", lay.forget_card), ("keep", lay.forget_keep), ("forget", lay.forget_confirm)];
        for (name, rect) in items {
            inside_panel(name, rect, 568.0);
        }
        disjoint(&items);
        assert_eq!(tap(&forget, centre(lay.forget_keep)), Some(Intent::ForgetCancel));
        assert_eq!(tap(&forget, centre(lay.forget_confirm)), Some(Intent::ForgetConfirm));
        // The status line under the cards is on the panel and clear of them.
        assert!(lay.status_message.1 + 18.0 <= 568.0);
        assert!(lay.status_message.1 >= lay.connecting_card.1 + lay.connecting_card.3);
        // The back link works on every page.
        for page in [Page::Entry, Page::Connecting, Page::ForgetConfirm] {
            let view = fixture(page, Some(LONG), false, 0.0);
            assert_eq!(tap(&view, (60.0, 40.0)), Some(Intent::Back), "{page:?}");
        }
    }
}

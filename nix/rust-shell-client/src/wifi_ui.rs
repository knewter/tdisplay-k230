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
    /// Height of the network list's viewport, in the layout's own units
    /// (814 in the portrait artwork); the landscape panel's list is shorter.
    list_visible: f64,
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
            list_visible: 814.0,
        }
    }
}
impl WifiView {
    /// Sizes the list's scroll range to the layout in use for a
    /// `width`x`height` surface (`layout`'s own `list_view`).
    pub fn set_surface(&mut self, width: u32, height: u32) {
        self.list_visible = layout_for(width, height, 0.0).list_view.3;
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
        let visible = self.list_visible;
        let max = (count as f64 * 88.0 - visible).max(0.0);
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
    let bottom = 1208.0 - keyboard_inset;
    (bottom - 88.0, bottom)
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
/// The portrait values are the 568x1232 artwork's own literals (they must
/// not move: the native render stays byte-identical); the wide values lay
/// the same pages out in two columns on the short landscape panel. Text
/// positions are relative to their card so both layouts share the paint code.
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
    pub list_label: (f64, f64, f64, f64),
    /// The scrolling list's viewport (clip and tap region both).
    pub list_view: Rect,
    pub list_clip: Rect,
    pub row_x: f64,
    pub row_w: f64,
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
    pub eye_hit: Rect,
    pub eye_center: (f64, f64),
    pub counter: (f64, f64),
    pub saved_change: Rect,
    pub saved_forget: Rect,
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
}

/// The layout for a real surface: the portrait artwork, or the wide layout
/// sized to the surface itself (the landscape panel or an HDMI monitor).
pub fn layout_for(width: u32, height: u32, keyboard_inset: f64) -> Layout {
    if wide(width, height) {
        wide_layout(f64::from(width), f64::from(height), keyboard_inset)
    } else {
        layout(false, keyboard_inset)
    }
}

/// Two columns that grow with the surface: the left (status, password)
/// keeps 520/1184 of the content width, the right (the list and the page's
/// buttons) takes the rest, and the list runs to the bottom edge. At the
/// landscape panel's 1232x568 every value is the panel's own literal.
fn wide_layout(w: f64, h: f64, keyboard_inset: f64) -> Layout {
    let s = (w - 48.0) / 1184.0;
    let lw = 520.0 * s;
    let rx = 24.0 + lw + 56.0 * s;
    let rw = w - 24.0 - rx;
    let half = (rw - 16.0) / 2.0;
    let second = rx + half + 16.0;
    let list_h = h - 88.0;
    let bottom = h - 24.0 - keyboard_inset;
    let top = bottom - 72.0;
    Layout {
        wide: true,
        back_text: (28.0, 14.0, 180.0, 22.0),
        title: (28.0, 44.0, 360.0, 30.0),
        back_hit: (200.0, 84.0),
        refresh_text: (w - 146.0, 22.0, 120.0, 22.0),
        refresh_hit: (w - 192.0, 0.0, 192.0, 64.0),
        current_card: (24.0, 92.0, lw, 116.0),
        list_label: (rx + 4.0, 22.0, rw - 168.0, 19.0),
        list_view: (rx, 64.0, rw, list_h),
        list_clip: (rx - 4.0, 64.0, rw + 8.0, list_h),
        row_x: rx,
        row_w: rw,
        row_cull: (64.0 - 88.0, 64.0 + list_h),
        list_empty: (rx + 22.0, 90.0, rw - 48.0),
        list_message: (30.0, 224.0),
        net_card: (24.0, 92.0, lw, 84.0),
        net_name_dy: 10.0,
        net_sub_dy: 50.0,
        pw_label: (28.0, 186.0),
        field: (24.0, 210.0, lw, 78.0),
        field_text_dy: 22.0,
        eye_hit: (lw - 52.0, 210.0, 72.0, 78.0),
        eye_center: (lw - 16.0, 244.0),
        counter: (lw - 75.0, 264.0),
        saved_change: (rx, 92.0, half, 62.0),
        saved_forget: (second, 92.0, half, 62.0),
        banner_saved_y: 166.0,
        banner_unsaved_y: 92.0,
        banner: (rw, 52.0, rw - 8.0),
        buttons: ((rx, top, half, 72.0), (second, top, half, 72.0)),
        button_text_dx: (half / 2.0 - 74.0, half / 2.0 - 74.0),
        button_text_dy: 22.0,
        entry_message: (rx + 4.0, top - 34.0),
        connecting_card: (24.0, 92.0, lw, 170.0),
        connecting_title_dy: 28.0,
        connecting_sub_dy: 90.0,
        connecting_cancel: (rx, 92.0, rw, 100.0),
        connecting_cancel_text: (rw / 2.0 - 134.0, 34.0),
        forget_card: (24.0, 92.0, lw, 170.0),
        forget_title_dy: 28.0,
        forget_sub_dy: 90.0,
        forget_keep: (rx, 92.0, half, 100.0),
        forget_confirm: (second, 92.0, half, 100.0),
        forget_text_dx: (half / 2.0 - 38.0, half / 2.0 - 42.0),
        forget_text_dy: 34.0,
        status_message: (30.0, 282.0),
    }
}

/// `layout(true, …)` is the wide layout at the landscape panel's own size.
pub fn layout(wide: bool, keyboard_inset: f64) -> Layout {
    if wide {
        wide_layout(1232.0, 568.0, keyboard_inset)
    } else {
        let (top, _) = entry_buttons_rect(keyboard_inset);
        Layout {
            wide,
            back_text: (28.0, 45.0, 180.0, 23.0),
            title: (28.0, 105.0, 360.0, 38.0),
            back_hit: (150.0, 104.0),
            refresh_text: (420.0, 45.0, 125.0, 22.0),
            refresh_hit: (418.0, 0.0, 150.0, 104.0),
            current_card: (24.0, 150.0, 520.0, 116.0),
            list_label: (28.0, 304.0, 480.0, 19.0),
            list_view: (24.0, 338.0, 520.0, 814.0),
            list_clip: (20.0, 338.0, 528.0, 814.0),
            row_x: 24.0,
            row_w: 520.0,
            row_cull: (-88.0, 1152.0),
            list_empty: (42.0, 370.0, 470.0),
            list_message: (30.0, 1163.0),
            net_card: (24.0, 150.0, 520.0, 108.0),
            net_name_dy: 22.0,
            net_sub_dy: 64.0,
            pw_label: (28.0, 281.0),
            field: (24.0, 310.0, 520.0, 90.0),
            field_text_dy: 27.0,
            eye_hit: (468.0, 314.0, 72.0, 74.0),
            eye_center: (504.0, 350.0),
            counter: (445.0, 369.0),
            saved_change: (24.0, 414.0, 250.0, 62.0),
            saved_forget: (294.0, 414.0, 250.0, 62.0),
            banner_saved_y: 486.0,
            banner_unsaved_y: 408.0,
            banner: (520.0, 64.0, 448.0),
            buttons: ((24.0, top, 250.0, 88.0), (294.0, top, 250.0, 88.0)),
            button_text_dx: (66.0, 57.0),
            button_text_dy: 27.0,
            entry_message: (30.0, top - 100.0),
            connecting_card: (24.0, 220.0, 520.0, 210.0),
            connecting_title_dy: 40.0,
            connecting_sub_dy: 104.0,
            connecting_cancel: (24.0, 1010.0, 520.0, 110.0),
            connecting_cancel_text: (111.0, 37.0),
            forget_card: (24.0, 230.0, 520.0, 210.0),
            forget_title_dy: 40.0,
            forget_sub_dy: 96.0,
            forget_keep: (24.0, 850.0, 250.0, 110.0),
            forget_confirm: (294.0, 850.0, 250.0, 110.0),
            forget_text_dx: (77.0, 66.0),
            forget_text_dy: 36.0,
            status_message: (30.0, 480.0),
        }
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
    if y < lay.back_hit.1 && x < lay.back_hit.0 {
        return Some(Intent::Back);
    }
    if view.page == Page::List {
        if contains(lay.refresh_hit, x, y) {
            return Some(Intent::Refresh);
        }
        if contains(lay.list_view, x, y) {
            let index = ((y - lay.list_view.1 + view.scroll) / 88.0).floor() as usize;
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
        let point = (250.0 * 390.0 / 568.0, 370.0 * 844.0 / 1232.0);
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
    fn the_portrait_wifi_layout_keeps_the_artworks_literals() {
        assert!(!wide(568, 1232) && !wide(1080, 1920) && !wide(1280, 1024));
        let lay = layout(false, 0.0);
        assert_eq!(lay.buttons, ((24.0, 1120.0, 250.0, 88.0), (294.0, 1120.0, 250.0, 88.0)));
        assert_eq!(lay.list_view, (24.0, 338.0, 520.0, 814.0));
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
            let card = (lay.row_x, lay.list_view.1 + index as f64 * 88.0, lay.row_w, 78.0);
            if card.1 + card.3 > lay.list_view.1 + lay.list_view.3 {
                continue;
            }
            inside_panel("row", card, 568.0);
            assert_eq!(tap(&view, centre(card)), Some(Intent::Select(index)), "row {index}");
            reachable += 1;
        }
        assert!(reachable >= 5, "several networks reachable without scrolling: {reachable}");
        // The rest are reached by scrolling the list: a vertical drag inside it.
        let drag = hit(&view, (900.0, 400.0), (900.0, 300.0), 1232, 568);
        assert_eq!(drag, Some(Intent::Scroll(100.0)));
        let mut state = WifiView { snapshot: view.snapshot.clone(), page: Page::List, ..WifiView::default() };
        state.set_surface(1232, 568);
        state.scroll(10_000.0);
        let last_top = lay.list_view.1 + (rows - 1) as f64 * 88.0 - state.scroll;
        assert!(last_top + 78.0 <= lay.list_view.1 + lay.list_view.3 + 1.0, "the last row scrolls fully into view");
        let scrolled = WifiPublic { scroll: state.scroll, ..view.clone() };
        assert_eq!(
            tap(&scrolled, (900.0, last_top + 39.0)),
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
        // The landscape panel's board-proven numbers are unchanged.
        let panel = layout_for(1232, 568, 0.0);
        assert_eq!(panel.current_card, (24.0, 92.0, 520.0, 116.0));
        assert_eq!(panel.list_view, (600.0, 64.0, 608.0, 480.0));
        assert_eq!(panel.buttons, ((600.0, 472.0, 296.0, 72.0), (912.0, 472.0, 296.0, 72.0)));
        assert_eq!((panel.refresh_text.0, panel.eye_hit.0, panel.counter.0), (1086.0, 468.0, 445.0));
        assert_eq!((panel.banner, panel.button_text_dx, panel.forget_text_dx), ((608.0, 52.0, 600.0), (74.0, 74.0), (110.0, 106.0)));
        assert_eq!(panel.connecting_cancel_text.0, 170.0);
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
            let last = (lay.row_x + lay.row_w / 2.0, lay.list_view.1 + (rows - 1) as f64 * 88.0 + 39.0);
            assert!(last.1 < lay.list_view.1 + lay.list_view.3, "{w}x{h}: every fixture network fits without scrolling");
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

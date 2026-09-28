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
    pub use_saved: bool,
    pub pending: Option<(u64, Kind)>,
    keyboard_inset: f64,
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
            use_saved: false,
            pending: None,
            keyboard_inset: 0.0,
        }
    }
}
impl WifiView {
    pub fn public(&self) -> WifiPublic {
        WifiPublic {
            page: self.page,
            snapshot: self.snapshot.clone(),
            selected: self.selected.clone(),
            password_len: self.password.len(),
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
                self.page = Page::List;
                self.message = Some("Saved. Checking current connection…".into());
            }
            Ok(WifiResult::Selected) => {
                self.password = Secret::new(String::new());
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
            self.message = None;
        }
    }
    pub fn scroll(&mut self, delta: f64) {
        if self.page != Page::List {
            return;
        }
        let count = self.snapshot.as_ref().map_or(0, |s| all_networks(s).len());
        let visible = 814.0;
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
    // Artwork is authored at 568×1232, while Wayland supplies output pixels.
    let scale = |point: (f64, f64)| {
        (
            point.0 * 568.0 / f64::from(width),
            point.1 * 1232.0 / f64::from(height),
        )
    };
    let start = scale(start);
    let (x, y) = scale(end);
    let dy = y - start.1;
    if view.page == Page::Closed {
        return None;
    }
    if view.page == Page::List && start.1 >= 338.0 && dy.abs() > 20.0 {
        return Some(Intent::Scroll(-dy));
    }
    if (x - start.0).abs() > 18.0 || dy.abs() > 18.0 {
        return None;
    }
    let down = target(view, start.0, start.1);
    let up = target(view, x, y);
    (down == up).then_some(up).flatten()
}

fn target(view: &WifiPublic, x: f64, y: f64) -> Option<Intent> {
    if y < 104.0 && x < 150.0 {
        return Some(Intent::Back);
    }
    if view.page == Page::List {
        if y < 104.0 && x > 418.0 {
            return Some(Intent::Refresh);
        }
        if (338.0..1152.0).contains(&y) && (24.0..544.0).contains(&x) {
            let index = ((y - 338.0 + view.scroll) / 88.0).floor() as usize;
            let count = view.snapshot.as_ref().map_or(0, |s| all_networks(s).len());
            return (index < count).then_some(Intent::Select(index));
        }
    }
    if view.page == Page::Connecting {
        if (1010.0..1120.0).contains(&y) && (24.0..544.0).contains(&x) {
            return Some(Intent::CancelPending);
        }
        return None;
    }
    if view.page == Page::ForgetConfirm {
        if (850.0..960.0).contains(&y) {
            if (24.0..274.0).contains(&x) {
                return Some(Intent::ForgetCancel);
            }
            if (294.0..544.0).contains(&x) {
                return Some(Intent::ForgetConfirm);
            }
        }
        return None;
    }
    if view.page != Page::Entry {
        return None;
    }
    let (button_top, button_bottom) = entry_buttons_rect(view.keyboard_inset);
    if (button_top..button_bottom).contains(&y) {
        if (24.0..274.0).contains(&x) {
            return Some(Intent::Back);
        }
        if (294.0..544.0).contains(&x) {
            return Some(Intent::Connect);
        }
    }
    let is_saved = view.selected.as_ref().is_some_and(|selected| {
        view.snapshot.as_ref().is_some_and(|snapshot| {
            snapshot
                .saved
                .iter()
                .any(|saved| saved.ssid == selected.ssid)
        })
    });
    if (414.0..476.0).contains(&y) && is_saved {
        if (24.0..274.0).contains(&x)
            && view.use_saved
            && view
                .selected
                .as_ref()
                .is_some_and(|n| n.security == Security::Wpa2Psk)
        {
            return Some(Intent::EditPassword);
        }
        if (294.0..544.0).contains(&x) {
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
}

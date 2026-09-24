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
    pub symbols: bool,
    pub shifted: bool,
    pub pending: bool,
    pub message: Option<String>,
    pub scroll: f64,
}

pub enum Intent {
    Back,
    Refresh,
    Select(usize),
    Key(char),
    Backspace,
    Symbols,
    Shift,
    Space,
    Connect,
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
    pub symbols: bool,
    pub shifted: bool,
    pub pending: Option<(u64, Kind)>,
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
            symbols: false,
            shifted: false,
            pending: None,
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
            symbols: self.symbols,
            shifted: self.shifted,
            pending: self.pending.is_some(),
            message: self.message.clone(),
            scroll: self.scroll,
        }
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
            Ok(WifiResult::Snapshot(snapshot)) => {
                let unavailable = snapshot.error.clone();
                self.snapshot = Some(snapshot);
                self.message = unavailable.map(|code| useful_error(&code).into());
            }
            Ok(WifiResult::Saved) => {
                self.password = Secret::new(String::new());
                self.page = Page::List;
                self.message = Some("Saved. Reconnecting with this network…".into());
            }
            Ok(WifiResult::Forgotten) => {
                self.page = Page::List;
                self.selected = None;
                self.message = Some("Network forgotten".into());
            }
            Err(error) => {
                self.message = Some(useful_error(&error).into());
                if reply.kind == Kind::Connect {
                    self.page = Page::Entry;
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
                Security::Wpa2Psk => (8..=63).contains(&self.password.len()),
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
                self.message = None;
                true
            }
        }
    }
    pub fn key(&mut self, intent: Intent) {
        if self.page != Page::Entry || self.pending.is_some() {
            return;
        }
        match intent {
            Intent::Key(c) => self.password.push(if self.shifted {
                c.to_ascii_uppercase()
            } else {
                c
            }),
            Intent::Space => self.password.push(' '),
            Intent::Backspace => self.password.pop(),
            Intent::Symbols => self.symbols = !self.symbols,
            Intent::Shift => self.shifted = !self.shifted,
            _ => {}
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
    if y < 104.0 && x < 150.0 {
        return Some(Intent::Back);
    }
    if view.page == Page::List {
        if y < 104.0 && x > 418.0 {
            return Some(Intent::Refresh);
        }
        if (338.0..1152.0).contains(&y) {
            let index = ((y - 338.0 + view.scroll) / 88.0).floor() as usize;
            let count = view.snapshot.as_ref().map_or(0, |s| all_networks(s).len());
            return (index < count).then_some(Intent::Select(index));
        }
    }
    if view.page == Page::Connecting {
        if (1010.0..1140.0).contains(&y) {
            return Some(Intent::CancelPending);
        }
        return None;
    }
    if view.page == Page::ForgetConfirm {
        if (850.0..1030.0).contains(&y) {
            return Some(if x < 284.0 {
                Intent::ForgetCancel
            } else {
                Intent::ForgetConfirm
            });
        }
        return None;
    }
    if view.page != Page::Entry {
        return None;
    }
    if (1120.0..1210.0).contains(&y) {
        return Some(if x < 284.0 {
            Intent::Back
        } else {
            Intent::Connect
        });
    }
    if (405.0..490.0).contains(&y) && x > 383.0 {
        return Some(Intent::Forget);
    }
    let row = if (530.0..610.0).contains(&y) {
        0
    } else if (620.0..700.0).contains(&y) {
        1
    } else if (710.0..790.0).contains(&y) {
        2
    } else if (800.0..880.0).contains(&y) {
        3
    } else if (890.0..970.0).contains(&y) {
        4
    } else {
        return None;
    };
    let w = 568.0;
    if row == 4 {
        if x < w * 0.23 {
            return Some(Intent::Symbols);
        }
        if x < w * 0.75 {
            return Some(Intent::Space);
        }
        return Some(Intent::Backspace);
    }
    let (keys, left, right): (&str, f64, f64) = match row {
        0 => (
            if view.symbols {
                "!@#$%^&*()"
            } else {
                "1234567890"
            },
            18.0,
            w - 18.0,
        ),
        1 => (
            if view.symbols {
                "-_=+[]{};:"
            } else {
                "qwertyuiop"
            },
            18.0,
            w - 18.0,
        ),
        2 => (
            if view.symbols {
                "'\"\\|/?.<>"
            } else {
                "asdfghjkl"
            },
            28.0,
            w - 28.0,
        ),
        3 => {
            if x < 70.0 {
                return Some(Intent::Shift);
            }
            if x > w - 70.0 {
                return Some(Intent::Backspace);
            }
            (
                if view.symbols { "~`,zxcv" } else { "zxcvbnm" },
                74.0,
                w - 74.0,
            )
        }
        _ => unreachable!(),
    };
    if x < left || x >= right {
        return None;
    }
    let index = ((x - left) / (right - left) * keys.chars().count() as f64).floor() as usize;
    keys.chars().nth(index).map(Intent::Key)
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
    fn forget_is_explicit_and_does_not_expose_password() {
        let mut view = WifiView::default();
        view.page = Page::List;
        let mut data = snapshot();
        data.saved = data.networks.clone();
        view.snapshot = Some(data);
        view.select(0);
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

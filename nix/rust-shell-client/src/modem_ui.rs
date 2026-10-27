//! Touch state, layout and hit-testing for the Settings Cellular and Location
//! pages, independent of Wayland rendering. Only `ModemPublic` is copied to
//! the renderer, and it carries the PIN's length, never its digits.
//!
//! The SIM PIN is typed on the page's own numeric keypad, so it never goes
//! through the system keyboard, a text field, or a key event.
use crate::modem::{Command, Kind, ModemReply, ModemStatus, Pin};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Page {
    Closed,
    Cellular,
    Location,
}

#[derive(Clone, Debug)]
pub struct ModemPublic {
    pub page: Page,
    pub status: ModemStatus,
    pub pin_len: usize,
    pub pending: Option<Kind>,
    pub message: Option<String>,
    /// The first tap on "Clear stored messages" asks again before deleting.
    pub clear_armed: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Intent {
    Back,
    Toggle,
    Digit(u8),
    Backspace,
    SubmitPin,
    ClearMessages,
}

/// The PIN is capped at the service's own limit.
const PIN_MAX: usize = 8;

pub struct ModemView {
    pub page: Page,
    /// `Some` only once the modem has answered; `None` hides every modem UI.
    pub status: Option<ModemStatus>,
    pub pending: Option<Kind>,
    pub message: Option<String>,
    pin: String,
    clear_armed: bool,
}

impl std::fmt::Debug for ModemView {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ModemView")
            .field("page", &self.page)
            .field("pin_len", &self.pin.len())
            .field("pending", &self.pending)
            .finish_non_exhaustive()
    }
}

impl Default for ModemView {
    fn default() -> Self {
        Self { page: Page::Closed, status: None, pending: None, message: None, pin: String::new(), clear_armed: false }
    }
}

impl ModemView {
    pub fn open(&mut self, page: Page) {
        if self.status.is_some() {
            self.page = page;
            self.message = None;
            self.clear_armed = false;
            self.pin.clear();
        }
    }

    pub fn close(&mut self) {
        self.page = Page::Closed;
        self.message = None;
        self.clear_armed = false;
        self.pin.clear();
    }

    /// Adopts the service's latest state. A modem that has not answered
    /// closes the page; a SIM that no longer asks for a PIN drops the digits.
    pub fn set_status(&mut self, status: Option<ModemStatus>) {
        if status.as_ref().is_none_or(|s| !s.pin_needed()) {
            self.pin.clear();
        }
        if status.is_none() {
            self.close();
        }
        self.status = status;
    }

    pub fn public(&self) -> Option<ModemPublic> {
        let status = self.status.clone()?;
        (self.page != Page::Closed).then(|| ModemPublic {
            page: self.page,
            status,
            pin_len: self.pin.len(),
            pending: self.pending,
            message: self.message.clone(),
            clear_armed: self.clear_armed,
        })
    }

    pub fn digit(&mut self, digit: u8) {
        if digit <= 9 && self.pin.len() < PIN_MAX && self.status.as_ref().is_some_and(ModemStatus::pin_needed) {
            self.pin.push(char::from(b'0' + digit));
            self.message = None;
        }
    }

    pub fn backspace(&mut self) {
        self.pin.pop();
    }

    /// The Cellular or Location switch, flipped. `None` while a request is out.
    pub fn toggle_command(&mut self) -> Option<Command> {
        if self.pending.is_some() {
            return None;
        }
        let status = self.status.as_ref()?;
        let command = match self.page {
            Page::Cellular => Command::Cellular(!status.cellular),
            Page::Location => Command::Location(!status.location),
            Page::Closed => return None,
        };
        self.pending = Some(command.kind());
        self.message = None;
        Some(command)
    }

    /// The Shade's Location tile: the same flip with no page open.
    pub fn location_toggle_command(&mut self) -> Option<Command> {
        if self.pending.is_some() {
            return None;
        }
        let command = Command::Location(!self.status.as_ref()?.location);
        self.pending = Some(command.kind());
        self.message = None;
        Some(command)
    }

    /// Takes the typed digits out of the view and into a command.
    pub fn pin_command(&mut self) -> Option<Command> {
        if self.pending.is_some() || !self.status.as_ref().is_some_and(ModemStatus::pin_needed) {
            return None;
        }
        let pin = Pin::new(&self.pin)?;
        self.pin.clear();
        self.pending = Some(Kind::Pin);
        self.message = None;
        Some(Command::SubmitPin(pin))
    }

    /// The first tap arms, the second deletes.
    pub fn clear_command(&mut self) -> Option<Command> {
        if self.pending.is_some() || self.status.as_ref().is_none_or(|s| s.sms_count == 0) {
            return None;
        }
        if !self.clear_armed {
            self.clear_armed = true;
            return None;
        }
        self.clear_armed = false;
        self.pending = Some(Kind::ClearMessages);
        self.message = None;
        Some(Command::ClearMessages)
    }

    /// Takes a worker reply; true when the page changed.
    pub fn accept(&mut self, reply: &ModemReply) -> bool {
        if self.pending != Some(reply.kind) {
            return false;
        }
        self.pending = None;
        self.message = match (&reply.result, reply.kind) {
            (Ok(()), Kind::ClearMessages) => Some("Stored messages cleared".into()),
            (Ok(()), _) => None,
            (Err(code), _) => Some(crate::modem::failure_text(code).into()),
        };
        true
    }

    pub fn submit_failed(&mut self, message: &str) {
        self.pending = None;
        self.message = Some(message.into());
    }
}

/// `(x, y, width, height)`.
pub type Rect = (f64, f64, f64, f64);

fn contains(rect: Rect, x: f64, y: f64) -> bool {
    x >= rect.0 && x < rect.0 + rect.2 && y >= rect.1 && y < rect.1 + rect.3
}

/// The same predicate as Wi-Fi, Help and Settings, so the landscape surfaces
/// switch together.
pub fn wide(width: u32, height: u32) -> bool {
    crate::help::wide(width, height)
}

/// The factor taking a real touch/paint coordinate to the units `Layout` is
/// written in: the 568x1232 artwork scales to the surface, the wide layout
/// is in real pixels.
pub fn layout_scale(width: u32, height: u32) -> (f64, f64) {
    crate::wifi_ui::layout_scale(width, height)
}

/// Every rect both painted and hit-tested, in one place. Sizes follow the
/// shell's type roles at the current text step, so nothing is cut by its card.
#[derive(Clone, Copy, Debug)]
pub struct Layout {
    pub wide: bool,
    /// "‹ Settings" and the page title: `(x, y, width, size)`.
    pub back_text: (f64, f64, f64, f64),
    pub title: (f64, f64, f64, f64),
    /// Tap region of the back link: `x < .0 && y < .1`.
    pub back_hit: (f64, f64),
    pub switch_card: Rect,
    /// The switch card's label and value lines, as offsets from its top.
    pub switch_dy: (f64, f64),
    pub switch_pill: Rect,
    pub status_card: Rect,
    /// The first status row's offset from the card top, and the row pitch.
    pub status_row0: f64,
    pub status_pitch: f64,
    pub status_pad: f64,
    pub message: (f64, f64, f64),
    pub clear: Option<Rect>,
    pub clear_dy: (f64, f64),
    pub pin: Option<PinLayout>,
}

#[derive(Clone, Copy, Debug)]
pub struct PinLayout {
    pub card: Rect,
    /// The prompt line: `(x, y, width)`.
    pub prompt: (f64, f64, f64),
    pub field: Rect,
    pub field_text_dy: f64,
    /// 1 2 3 / 4 5 6 / 7 8 9 / backspace 0 OK, row by row.
    pub keys: [Rect; 12],
    pub key_text_dy: f64,
}

struct Roles {
    body: f64,
    label: f64,
    caption: f64,
}

fn line(px: f64) -> f64 {
    (px * 1.25).ceil()
}

/// The rows of the status card on each page.
pub fn status_rows(page: Page) -> usize {
    match page {
        Page::Cellular => 5,
        _ => 1,
    }
}

pub fn layout_for(width: u32, height: u32, public: &ModemPublic) -> Layout {
    if wide(width, height) {
        build(f64::from(width), f64::from(height), true, public)
    } else {
        build(568.0, 1232.0, false, public)
    }
}

fn build(w: f64, _h: f64, wide: bool, public: &ModemPublic) -> Layout {
    let s = crate::layout_text_scale().max(1.0) * crate::layout_theme_font();
    let r = Roles {
        body: crate::render::TYPE_BODY * s,
        label: crate::render::TYPE_LABEL * s,
        caption: crate::render::TYPE_CAPTION * s,
    };
    let (lab, cap, body) = (line(r.label), line(r.caption), line(r.body));
    let pad = 14.0;
    let (lw, rx, rw) = if wide {
        let lw = (w - 48.0) * 0.48;
        let rx = 24.0 + lw + 32.0;
        (lw, rx, w - 24.0 - rx)
    } else {
        (w - 48.0, 24.0, w - 48.0)
    };
    let top_y = if wide { 14.0 } else { 45.0 };
    let title_y = top_y + lab + if wide { 2.0 } else { 16.0 };
    let title_size = if wide { crate::render::TYPE_BODY } else { crate::render::TYPE_TITLE };
    let title_h = if wide { body } else { line(crate::render::TYPE_TITLE * s) };
    let back_w = crate::render::measured_text_width("‹ Settings", r.label, pango::Weight::Normal) + 8.0;
    let content = title_y + title_h + if wide { 4.0 } else { 12.0 };

    let switch_h = (2.0 * pad + lab + 2.0 + cap).max(76.0);
    let switch_card = (24.0, content, lw, switch_h);
    let pill = (lw + 24.0 - 18.0 - 72.0, content + (switch_h - 40.0) / 2.0, 72.0, 40.0);

    let status_pad = 14.0;
    let status_pitch = body + 10.0;
    let rows = status_rows(public.page);
    let status_h = 2.0 * status_pad + rows as f64 * status_pitch - 10.0;
    let status_card = (24.0, content + switch_h + 12.0, lw, status_h);
    let left_bottom = status_card.1 + status_h;
    let message = (28.0, left_bottom + 10.0, lw - 8.0);

    let cellular = public.page == Page::Cellular;
    let right_top = if wide { content } else { message.1 + cap + 14.0 };
    let pin_needed = cellular && public.status.pin_needed();
    let pin = pin_needed.then(|| {
        let prompt_h = cap;
        let field_h = body + 24.0;
        let key_h = if wide { 52.0 } else { 76.0 };
        let gap = 10.0;
        let prompt = (rx + 18.0, right_top + pad, rw - 36.0);
        let field_y = right_top + pad + prompt_h + 8.0;
        let field = (rx + 18.0, field_y, rw - 36.0, field_h);
        let keys_y = field_y + field_h + 12.0;
        let key_w = (rw - 36.0 - 2.0 * gap) / 3.0;
        let mut keys = [(0.0, 0.0, 0.0, 0.0); 12];
        for (i, key) in keys.iter_mut().enumerate() {
            let (col, row) = ((i % 3) as f64, (i / 3) as f64);
            *key = (rx + 18.0 + col * (key_w + gap), keys_y + row * (key_h + gap), key_w, key_h);
        }
        let card_h = keys_y + 4.0 * key_h + 3.0 * gap + pad - right_top;
        PinLayout {
            card: (rx, right_top, rw, card_h),
            prompt,
            field,
            field_text_dy: (field_h - body) / 2.0,
            keys,
            key_text_dy: (key_h - body) / 2.0,
        }
    });
    let clear_h = (2.0 * pad + lab + 2.0 + cap).max(76.0);
    let clear = (cellular && !pin_needed).then_some((rx, right_top, rw, clear_h));
    Layout {
        wide,
        back_text: (28.0, top_y, back_w, crate::render::TYPE_LABEL),
        title: (28.0, title_y, lw, title_size),
        back_hit: ((back_w + 48.0).max(200.0), title_y + 8.0),
        switch_card,
        switch_dy: (pad, pad + lab + 2.0),
        switch_pill: pill,
        status_card,
        status_row0: status_pad,
        status_pitch,
        status_pad,
        message,
        clear,
        clear_dy: (pad, pad + lab + 2.0),
        pin,
    }
}

fn target(public: &ModemPublic, lay: &Layout, x: f64, y: f64) -> Option<Intent> {
    if x < lay.back_hit.0 && y < lay.back_hit.1 {
        return Some(Intent::Back);
    }
    if contains(lay.switch_card, x, y) {
        return Some(Intent::Toggle);
    }
    if let Some(pin) = &lay.pin {
        let index = pin.keys.iter().position(|key| contains(*key, x, y))?;
        return Some(match index {
            9 => Intent::Backspace,
            10 => Intent::Digit(0),
            11 => Intent::SubmitPin,
            n => Intent::Digit(n as u8 + 1),
        });
    }
    if lay.clear.is_some_and(|rect| contains(rect, x, y)) && public.status.sms_count > 0 {
        return Some(Intent::ClearMessages);
    }
    None
}

/// A tap that went down and came up on the same target.
pub fn hit(
    public: &ModemPublic,
    start: (f64, f64),
    end: (f64, f64),
    width: u32,
    height: u32,
) -> Option<Intent> {
    if width == 0 || height == 0 || public.page == Page::Closed {
        return None;
    }
    let lay = layout_for(width, height, public);
    let (sx, sy) = layout_scale(width, height);
    let (start, end) = ((start.0 * sx, start.1 * sy), (end.0 * sx, end.1 * sy));
    if (end.0 - start.0).abs() > 18.0 || (end.1 - start.1).abs() > 18.0 {
        return None;
    }
    let down = target(public, &lay, start.0, start.1);
    let up = target(public, &lay, end.0, end.1);
    (down == up).then_some(up).flatten()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::modem::parse_status;

    fn status(edit: impl FnOnce(&mut serde_json::Value)) -> ModemStatus {
        let mut value = serde_json::json!({
            "schema":1,"updated":1,"power":"on","present":true,"cellular":true,"location":false,
            "sim":"ready","pin_attempts":null,"registration":"registered_home","operator":"Example Net",
            "rat":"LTE-M","rsrp":-95,"bars":3,"gnss":"off","sms_count":2,"last_error":null
        });
        edit(&mut value);
        parse_status(value.to_string().as_bytes()).unwrap()
    }

    fn view(page: Page, status: ModemStatus) -> ModemView {
        let mut view = ModemView::default();
        view.set_status(Some(status));
        view.open(page);
        view
    }

    fn centre(rect: Rect) -> (f64, f64) {
        (rect.0 + rect.2 / 2.0, rect.1 + rect.3 / 2.0)
    }

    /// A real touch point for a point in the layout's own units.
    fn real(width: u32, height: u32, point: (f64, f64)) -> (f64, f64) {
        let (sx, sy) = layout_scale(width, height);
        (point.0 / sx, point.1 / sy)
    }

    #[test]
    fn nothing_opens_until_the_modem_has_answered() {
        let mut view = ModemView::default();
        view.open(Page::Cellular);
        assert_eq!(view.page, Page::Closed);
        assert!(view.public().is_none());
        view.set_status(Some(status(|_| {})));
        view.open(Page::Location);
        assert_eq!(view.public().unwrap().page, Page::Location);
        view.set_status(None);
        assert_eq!(view.page, Page::Closed, "the page closes when the modem goes quiet");
    }

    #[test]
    fn the_pin_is_typed_on_the_keypad_and_leaves_the_view_as_a_command() {
        let mut v = view(Page::Cellular, status(|s| s["sim"] = "pin_required".into()));
        v.digit(4);
        v.digit(8);
        v.digit(2);
        assert!(v.pin_command().is_none(), "three digits are too few");
        v.digit(9);
        assert_eq!(v.public().unwrap().pin_len, 4);
        let shown = format!("{v:?} {:?}", v.public().unwrap());
        assert!(!shown.contains("4829") && !shown.contains("482"), "{shown}");
        let command = v.pin_command().unwrap();
        assert!(!format!("{command:?}").contains("4829"));
        assert_eq!(v.public().unwrap().pin_len, 0, "digits are gone once submitted");
        assert_eq!(v.pending, Some(Kind::Pin));
        assert!(v.pin_command().is_none());
        for _ in 0..12 {
            v.digit(1);
        }
        assert_eq!(v.public().unwrap().pin_len, 8, "the PIN stops at eight digits");
    }

    #[test]
    fn digits_are_ignored_unless_the_sim_asks() {
        let mut v = view(Page::Cellular, status(|_| {}));
        v.digit(1);
        assert_eq!(v.public().unwrap().pin_len, 0);
        let mut v = view(Page::Cellular, status(|s| s["sim"] = "pin_required".into()));
        v.digit(1);
        v.set_status(Some(status(|_| {})));
        assert_eq!(v.public().unwrap().pin_len, 0, "a satisfied SIM drops the digits");
    }

    #[test]
    fn the_shade_tile_flips_location_with_no_page_open() {
        let mut v = view(Page::Closed, status(|_| {}));
        assert_eq!(v.location_toggle_command(), Some(Command::Location(true)));
        assert!(v.location_toggle_command().is_none(), "one request at a time");
        assert!(v.accept(&ModemReply { kind: Kind::Location, result: Ok(()) }));
        let mut v = view(Page::Closed, status(|s| s["location"] = true.into()));
        assert_eq!(v.location_toggle_command(), Some(Command::Location(false)));
    }

    #[test]
    fn the_switch_sends_the_opposite_of_the_persisted_choice_once() {
        let mut v = view(Page::Location, status(|_| {}));
        assert_eq!(v.toggle_command(), Some(Command::Location(true)));
        assert!(v.toggle_command().is_none(), "one request at a time");
        assert!(v.accept(&ModemReply { kind: Kind::Location, result: Ok(()) }));
        let mut v = view(Page::Cellular, status(|_| {}));
        assert_eq!(v.toggle_command(), Some(Command::Cellular(false)));
        assert!(v.accept(&ModemReply { kind: Kind::Cellular, result: Err("modem_timeout".into()) }));
        assert_eq!(v.message.as_deref(), Some("The modem did not respond"));
    }

    #[test]
    fn clearing_messages_takes_a_second_tap_and_needs_messages() {
        let mut v = view(Page::Cellular, status(|_| {}));
        assert_eq!(v.clear_command(), None);
        assert!(v.public().unwrap().clear_armed);
        assert_eq!(v.clear_command(), Some(Command::ClearMessages));
        assert!(!v.public().unwrap().clear_armed);
        let mut empty = view(Page::Cellular, status(|s| s["sms_count"] = 0.into()));
        assert_eq!(empty.clear_command(), None);
        assert!(!empty.public().unwrap().clear_armed);
    }

    #[test]
    fn a_pin_rejection_names_the_problem_without_the_digits() {
        let mut v = view(Page::Cellular, status(|s| s["sim"] = "pin_required".into()));
        for d in [1, 2, 3, 4] {
            v.digit(d);
        }
        v.pin_command().unwrap();
        v.accept(&ModemReply { kind: Kind::Pin, result: Err("pin_rejected".into()) });
        assert_eq!(v.message.as_deref(), Some("PIN not accepted"));
    }

    fn surfaces() -> [(u32, u32); 2] {
        [(1232, 568), (568, 1232)]
    }

    #[test]
    fn every_control_sits_inside_the_surface_and_clear_of_the_others() {
        let cases = [
            ("cellular", Page::Cellular, status(|_| {})),
            ("pin", Page::Cellular, status(|s| s["sim"] = "pin_required".into())),
            ("no sim", Page::Cellular, status(|s| {
                s["sim"] = "absent".into();
                s["registration"] = "unknown".into();
            })),
            ("location", Page::Location, status(|s| s["location"] = true.into())),
        ];
        for (width, height) in surfaces() {
            let (sx, sy) = layout_scale(width, height);
            let (uw, uh) = (f64::from(width) * sx, f64::from(height) * sy);
            for (name, page, st) in &cases {
                let v = view(*page, st.clone());
                let public = v.public().unwrap();
                let lay = layout_for(width, height, &public);
                let mut rects = vec![("switch", lay.switch_card), ("status", lay.status_card)];
                if let Some(clear) = lay.clear {
                    rects.push(("clear", clear));
                }
                if let Some(pin) = &lay.pin {
                    rects.push(("pin card", pin.card));
                    for (i, key) in pin.keys.iter().enumerate() {
                        assert!(contains(pin.card, key.0, key.1) && contains(pin.card, key.0 + key.2 - 1.0, key.1 + key.3 - 1.0),
                            "{name} {width}x{height}: key {i} outside its card");
                    }
                }
                for (label, r) in &rects {
                    assert!(r.0 >= 0.0 && r.1 >= 0.0 && r.0 + r.2 <= uw && r.1 + r.3 <= uh,
                        "{name} {label} {r:?} leaves {width}x{height}");
                }
                for (i, (a_name, a)) in rects.iter().enumerate() {
                    for (b_name, b) in &rects[i + 1..] {
                        let apart = a.0 + a.2 <= b.0 || b.0 + b.2 <= a.0 || a.1 + a.3 <= b.1 || b.1 + b.3 <= a.1;
                        assert!(apart, "{name} {width}x{height}: {a_name} overlaps {b_name}");
                    }
                }
                let msg = lay.message;
                assert!(msg.1 + line(crate::render::TYPE_CAPTION) <= uh, "{name} message line leaves the surface");
            }
        }
    }

    #[test]
    fn taps_reach_back_the_switch_the_keypad_and_clear() {
        for (width, height) in surfaces() {
            let tap = |public: &ModemPublic, point: (f64, f64)| {
                let p = real(width, height, point);
                hit(public, p, p, width, height)
            };
            let v = view(Page::Cellular, status(|_| {}));
            let public = v.public().unwrap();
            let lay = layout_for(width, height, &public);
            assert_eq!(tap(&public, (40.0, lay.back_text.1 + 4.0)), Some(Intent::Back));
            assert_eq!(tap(&public, centre(lay.switch_card)), Some(Intent::Toggle));
            assert_eq!(tap(&public, centre(lay.clear.unwrap())), Some(Intent::ClearMessages));
            assert_eq!(tap(&public, centre(lay.status_card)), None, "status rows are not buttons");

            let pin = view(Page::Cellular, status(|s| s["sim"] = "pin_required".into())).public().unwrap();
            let lay = layout_for(width, height, &pin);
            assert!(lay.clear.is_none(), "the keypad takes the clear control's place");
            let keys = lay.pin.unwrap().keys;
            for (i, key) in keys.iter().enumerate() {
                let want = match i {
                    9 => Intent::Backspace,
                    10 => Intent::Digit(0),
                    11 => Intent::SubmitPin,
                    n => Intent::Digit(n as u8 + 1),
                };
                assert_eq!(tap(&pin, centre(*key)), Some(want), "key {i} at {width}x{height}");
            }
            let empty = view(Page::Cellular, status(|s| s["sms_count"] = 0.into())).public().unwrap();
            let lay = layout_for(width, height, &empty);
            assert_eq!(tap(&empty, centre(lay.clear.unwrap())), None, "nothing to clear");
        }
    }

    #[test]
    fn a_drag_is_not_a_tap() {
        let (width, height) = (1232, 568);
        let public = view(Page::Location, status(|_| {})).public().unwrap();
        let lay = layout_for(width, height, &public);
        let c = centre(lay.switch_card);
        assert_eq!(hit(&public, c, (c.0, c.1 + 40.0), width, height), None);
        assert_eq!(hit(&public, (c.0, c.1 - 2.0), (c.0 + 3.0, c.1), width, height), Some(Intent::Toggle));
    }

    #[test]
    fn the_layout_grows_with_the_text_step_and_keeps_its_order() {
        let public = view(Page::Cellular, status(|s| s["sim"] = "pin_required".into())).public().unwrap();
        let mut last = 0.0;
        for step in [1.0, 1.25, 1.5] {
            crate::set_layout_text_scale(step);
            let lay = layout_for(568, 1232, &public);
            let pin = lay.pin.unwrap();
            assert!(pin.card.1 >= lay.status_card.1 + lay.status_card.3, "step {step}: keypad under the status card");
            let bottom = pin.card.1 + pin.card.3;
            assert!(bottom > last, "step {step}: taller text, taller page");
            last = bottom;
            if step <= 1.25 {
                assert!(bottom <= 1232.0, "step {step}: the portrait keypad fits ({bottom})");
            }
        }
        crate::set_layout_text_scale(1.0);
    }
}

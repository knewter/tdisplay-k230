//! The touchscreen-to-touchpad protocol translator.
//!
//! Per the operator's design (see `openspec/changes/the-touchscreen-becomes-
//! an-hdmi-trackpad/design.md`), this is deliberately *not* a gesture state
//! machine that recognizes taps/scrolls/pinches itself. It forwards the
//! touchscreen's protocol-B multitouch contacts (`ABS_MT_SLOT`,
//! `ABS_MT_TRACKING_ID`, `ABS_MT_POSITION_X/Y`, `ABS_MT_PRESSURE`) through
//! unchanged, and synthesizes only the handful of legacy touchpad key
//! events (`BTN_TOUCH`, `BTN_TOOL_FINGER`/`DOUBLETAP`/`TRIPLETAP`) that
//! libinput's own device classifier and gesture engine need to see, based
//! purely on how many contact slots are currently active. libinput then
//! does tap-to-click, two-finger scroll, pinch and swipe recognition
//! itself, exactly as it would for a real touchpad -- this relay's whole
//! job is to make libinput believe it is looking at one.
//!
//! This keeps the testable surface small and exact: given a sequence of
//! raw input events, does the relay emit the right synthesized key
//! transitions, at the right point in the frame, without ever touching
//! the position data.

use crate::event::*;

/// One virtual touchpad only ever needs to track as many concurrent
/// contacts as the digitizer reports slots for. The GT9895 reports 10
/// (see `docs/evidence/touch-reports.md`); this is a generous ceiling
/// that costs nothing unused.
const MAX_SLOTS: usize = 16;

/// Tracks per-slot state and the currently-selected slot (protocol B:
/// `ABS_MT_SLOT` selects which slot subsequent `ABS_MT_*` events target,
/// exactly as the kernel documents in
/// `Documentation/input/multi-touch-protocol.rst`).
pub struct Relay {
    slots: [i32; MAX_SLOTS],
    current_slot: usize,
    /// Which of BTN_TOUCH / BTN_TOOL_FINGER / _DOUBLETAP / _TRIPLETAP is
    /// currently held down, so a repeated frame with the same contact
    /// count emits nothing (only transitions are events, per the evdev
    /// convention this device's consumer expects).
    touch_down: bool,
    tool: Option<u16>,
}

impl Default for Relay {
    fn default() -> Self {
        Relay { slots: [NO_TRACKING_ID; MAX_SLOTS], current_slot: 0, touch_down: false, tool: None }
    }
}

impl Relay {
    pub fn new() -> Self {
        Self::default()
    }

    fn active_contact_count(&self) -> usize {
        self.slots.iter().filter(|&&id| id != NO_TRACKING_ID).count()
    }

    fn tool_for_count(count: usize) -> Option<u16> {
        match count {
            0 => None,
            1 => Some(BTN_TOOL_FINGER),
            2 => Some(BTN_TOOL_DOUBLETAP),
            3 => Some(BTN_TOOL_TRIPLETAP),
            // Four-plus-finger contact has no dedicated legacy BTN_TOOL_*
            // bit pair beyond QUADTAP in this codebase's scope; treat it
            // as a (still-recognizable-by-libinput) triple-tap tool state
            // rather than dropping the frame.
            _ => Some(BTN_TOOL_QUADTAP),
        }
    }

    /// Feeds one raw event from the grabbed touchscreen device and
    /// returns the events to write to the virtual touchpad uinput device
    /// in order. Position/tracking events pass straight through; key
    /// synthesis happens immediately before the `SYN_REPORT` that closes
    /// the frame in which the contact count changed, matching how a real
    /// touchpad driver orders its own frame.
    pub fn process(&mut self, ev: InputEvent) -> Vec<InputEvent> {
        match (ev.type_, ev.code) {
            (EV_ABS, ABS_MT_SLOT) => {
                self.current_slot = (ev.value as usize).min(MAX_SLOTS - 1);
                vec![ev]
            }
            (EV_ABS, ABS_MT_TRACKING_ID) => {
                self.slots[self.current_slot] = ev.value;
                vec![ev]
            }
            (EV_SYN, SYN_REPORT) => {
                let mut out = Vec::with_capacity(3);
                let count = self.active_contact_count();

                let want_touch = count > 0;
                if want_touch != self.touch_down {
                    out.push(InputEvent::synthesize(&ev, EV_KEY, BTN_TOUCH, want_touch as i32));
                    self.touch_down = want_touch;
                }

                let want_tool = Self::tool_for_count(count);
                if want_tool != self.tool {
                    if let Some(prev) = self.tool {
                        out.push(InputEvent::synthesize(&ev, EV_KEY, prev, 0));
                    }
                    if let Some(next) = want_tool {
                        out.push(InputEvent::synthesize(&ev, EV_KEY, next, 1));
                    }
                    self.tool = want_tool;
                }

                out.push(ev);
                out
            }
            // ABS_MT_POSITION_X/Y, ABS_MT_PRESSURE, ABS_MT_TOUCH_MAJOR,
            // and anything else the controller emits: forward untouched.
            // libinput needs the real coordinate stream to do pointer
            // motion, two-finger scroll deltas, and pinch distance itself.
            _ => vec![ev],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn syn(t: i64) -> InputEvent {
        InputEvent::new(t, 0, EV_SYN, SYN_REPORT, 0)
    }
    fn slot(t: i64, n: i32) -> InputEvent {
        InputEvent::new(t, 0, EV_ABS, ABS_MT_SLOT, n)
    }
    fn tracking(t: i64, id: i32) -> InputEvent {
        InputEvent::new(t, 0, EV_ABS, ABS_MT_TRACKING_ID, id)
    }
    fn pos_x(t: i64, v: i32) -> InputEvent {
        InputEvent::new(t, 0, EV_ABS, ABS_MT_POSITION_X, v)
    }

    fn key_events(out: &[InputEvent]) -> Vec<(u16, i32)> {
        out.iter().filter(|e| e.type_ == EV_KEY).map(|e| (e.code, e.value)).collect()
    }

    #[test]
    fn one_finger_down_then_up_emits_touch_and_finger_tool() {
        let mut r = Relay::new();
        // Frame 1: finger touches down in slot 0.
        let mut out = Vec::new();
        out.extend(r.process(slot(1, 0)));
        out.extend(r.process(tracking(1, 42)));
        out.extend(r.process(pos_x(1, 500)));
        out.extend(r.process(syn(1)));
        assert_eq!(key_events(&out), vec![(BTN_TOUCH, 1), (BTN_TOOL_FINGER, 1)]);
        // The SYN_REPORT must be last and the position event must have
        // passed through unmodified.
        assert!(out.last().unwrap().is_syn_report());
        assert!(out.iter().any(|e| e.type_ == EV_ABS && e.code == ABS_MT_POSITION_X && e.value == 500));

        // Frame 2: same contact, no state change -> no key events at all.
        let out2 = r.process(syn(2));
        assert!(key_events(&out2).is_empty());
        assert_eq!(out2.len(), 1);

        // Frame 3: finger lifts (tracking id -> -1). Order between
        // BTN_TOUCH and the BTN_TOOL_* pair is not semantically
        // significant to a spec-compliant consumer -- both apply
        // atomically at the frame's SYN_REPORT, per
        // Documentation/input/multi-touch-protocol.rst -- so this asserts
        // the set of transitions, matching this relay's actual (touch,
        // then tool) emission order rather than prescribing one.
        let mut out3 = Vec::new();
        out3.extend(r.process(tracking(3, -1)));
        out3.extend(r.process(syn(3)));
        assert_eq!(key_events(&out3), vec![(BTN_TOUCH, 0), (BTN_TOOL_FINGER, 0)]);
    }

    #[test]
    fn two_finger_tap_reports_doubletap_tool() {
        let mut r = Relay::new();
        let mut out = Vec::new();
        out.extend(r.process(slot(1, 0)));
        out.extend(r.process(tracking(1, 1)));
        out.extend(r.process(slot(1, 1)));
        out.extend(r.process(tracking(1, 2)));
        out.extend(r.process(syn(1)));
        assert_eq!(key_events(&out), vec![(BTN_TOUCH, 1), (BTN_TOOL_DOUBLETAP, 1)]);

        // Both lift in the same frame.
        let mut out2 = Vec::new();
        out2.extend(r.process(slot(2, 0)));
        out2.extend(r.process(tracking(2, -1)));
        out2.extend(r.process(slot(2, 1)));
        out2.extend(r.process(tracking(2, -1)));
        out2.extend(r.process(syn(2)));
        assert_eq!(key_events(&out2), vec![(BTN_TOUCH, 0), (BTN_TOOL_DOUBLETAP, 0)]);
    }

    #[test]
    fn three_finger_drag_reports_tripletap_tool_and_keeps_tracking_positions() {
        let mut r = Relay::new();
        let mut out = Vec::new();
        for (slot_n, id) in [(0, 10), (1, 11), (2, 12)] {
            out.extend(r.process(slot(1, slot_n)));
            out.extend(r.process(tracking(1, id)));
        }
        out.extend(r.process(syn(1)));
        assert_eq!(key_events(&out), vec![(BTN_TOUCH, 1), (BTN_TOOL_TRIPLETAP, 1)]);

        // A drag frame: slot 0 moves, nobody lifts. No new key events --
        // libinput reads the position delta itself from the passthrough
        // ABS_MT_POSITION events (it computes the swipe/scroll itself).
        let mut out2 = Vec::new();
        out2.extend(r.process(slot(2, 0)));
        out2.extend(r.process(pos_x(2, 600)));
        out2.extend(r.process(syn(2)));
        assert!(key_events(&out2).is_empty());
        assert!(out2.iter().any(|e| e.code == ABS_MT_POSITION_X && e.value == 600));
    }

    #[test]
    fn two_to_one_finger_transition_swaps_tool_bit_without_dropping_touch() {
        // Lifting one of two fingers must clear DOUBLETAP and set FINGER
        // in the same frame, and BTN_TOUCH must stay down throughout
        // (never bounces to 0) since a contact remains present.
        let mut r = Relay::new();
        let mut setup = Vec::new();
        setup.extend(r.process(slot(1, 0)));
        setup.extend(r.process(tracking(1, 1)));
        setup.extend(r.process(slot(1, 1)));
        setup.extend(r.process(tracking(1, 2)));
        setup.extend(r.process(syn(1)));
        assert_eq!(key_events(&setup), vec![(BTN_TOUCH, 1), (BTN_TOOL_DOUBLETAP, 1)]);

        let mut out = Vec::new();
        out.extend(r.process(slot(2, 1)));
        out.extend(r.process(tracking(2, -1)));
        out.extend(r.process(syn(2)));
        assert_eq!(key_events(&out), vec![(BTN_TOOL_DOUBLETAP, 0), (BTN_TOOL_FINGER, 1)]);
        assert!(!key_events(&out).contains(&(BTN_TOUCH, 0)));
    }

    #[test]
    fn syn_report_is_always_the_last_event_of_a_frame() {
        let mut r = Relay::new();
        let mut out = Vec::new();
        out.extend(r.process(slot(1, 0)));
        out.extend(r.process(tracking(1, 5)));
        out.extend(r.process(syn(1)));
        assert!(out.last().unwrap().is_syn_report());
    }
}

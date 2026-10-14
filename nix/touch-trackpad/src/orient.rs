//! The trackpad follows the orientation the board is held in, which is the
//! panel's own Sway transform (`k230.shell.panelTransform`): on the landscape
//! image a swipe toward the right edge as the board is held moves the pointer
//! right on the monitor, whatever the monitor's own transform is.
//!
//! Each raw touchscreen event is turned into that held frame as it is read,
//! and the virtual touchpad and the gesture gate are given the turned
//! ranges, so libinput, the gate and the relay all see one consistent frame.
use crate::event::*;
use crate::uinput::AbsRanges;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Orientation {
    /// The panel's native portrait frame (`transform normal`).
    Normal,
    /// `transform 270`, the keyboard case: the glass's native top edge is
    /// on the right as the board is held and its native left edge is at the
    /// top. (Board, 2026-10-14: the opposite turn moved the pointer down for
    /// an upward swipe and right for a leftward one.)
    Turned270,
}

impl Orientation {
    /// From the Sway transform the panel uses. Other values are not
    /// offered by `k230.shell.panelTransform`.
    pub fn from_panel_transform(transform: &str) -> Option<Orientation> {
        match transform {
            "normal" => Some(Orientation::Normal),
            "270" => Some(Orientation::Turned270),
            _ => None,
        }
    }

    /// The ranges as seen in the held frame.
    pub fn ranges(self, native: AbsRanges) -> AbsRanges {
        match self {
            Orientation::Normal => native,
            Orientation::Turned270 => AbsRanges { position_x: native.position_y, position_y: native.position_x, ..native },
        }
    }

    /// One raw event in the held frame. `native` is the touchscreen's own
    /// ranges.
    pub fn event(self, native: &AbsRanges, ev: InputEvent) -> InputEvent {
        if self == Orientation::Normal || ev.type_ != EV_ABS {
            return ev;
        }
        let y = native.position_y;
        match ev.code {
            // Held x runs from the glass's native bottom edge to its top.
            ABS_MT_POSITION_Y => InputEvent { code: ABS_MT_POSITION_X, value: y.minimum + y.maximum - ev.value, ..ev },
            // Held y runs along the native x (left edge at the top).
            ABS_MT_POSITION_X => InputEvent { code: ABS_MT_POSITION_Y, ..ev },
            _ => ev,
        }
    }

    /// A native `(x, y)` contact position in the held frame.
    pub fn point(self, native: &AbsRanges, (x, y): (i32, i32)) -> (i32, i32) {
        match self {
            Orientation::Normal => (x, y),
            Orientation::Turned270 => (native.position_y.minimum + native.position_y.maximum - y, x),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::uinput::InputAbsInfo;

    fn native() -> AbsRanges {
        AbsRanges {
            position_x: InputAbsInfo { value: 0, minimum: 0, maximum: 1079, fuzz: 0, flat: 0, resolution: 26 },
            position_y: InputAbsInfo { value: 0, minimum: 0, maximum: 2399, fuzz: 0, flat: 0, resolution: 27 },
            ..AbsRanges::default()
        }
    }

    fn abs(code: u16, value: i32) -> InputEvent {
        InputEvent::new(1, 2, EV_ABS, code, value)
    }

    #[test]
    fn normal_passes_everything_through() {
        let n = native();
        let o = Orientation::from_panel_transform("normal").unwrap();
        assert_eq!(o.event(&n, abs(ABS_MT_POSITION_X, 10)), abs(ABS_MT_POSITION_X, 10));
        assert_eq!(o.point(&n, (10, 20)), (10, 20));
        assert_eq!(o.ranges(n).position_x.maximum, 1079);
    }

    #[test]
    fn the_keyboard_case_turns_the_glass_into_the_held_landscape_frame() {
        let n = native();
        let o = Orientation::from_panel_transform("270").unwrap();
        // The held frame is wide: the native long axis becomes x.
        let r = o.ranges(n);
        assert_eq!((r.position_x.maximum, r.position_y.maximum), (2399, 1079));
        assert_eq!((r.position_x.resolution, r.position_y.resolution), (27, 26));
        // Native bottom-left corner (x 0, y max) is the held top-left.
        assert_eq!(o.point(&n, (0, 2399)), (0, 0));
        // Native top-right (x max, y 0) is the held bottom-right.
        assert_eq!(o.point(&n, (1079, 0)), (2399, 1079));
        // A finger moving up the native glass (y falling) moves right as held.
        assert_eq!(o.event(&n, abs(ABS_MT_POSITION_Y, 500)), abs(ABS_MT_POSITION_X, 1899));
        // A finger moving toward the native right edge moves down as held.
        assert_eq!(o.event(&n, abs(ABS_MT_POSITION_X, 100)), abs(ABS_MT_POSITION_Y, 100));
        // Everything else is untouched, timestamps included.
        let slot = abs(ABS_MT_SLOT, 2);
        assert_eq!(o.event(&n, slot), slot);
        let key = InputEvent::new(1, 2, EV_KEY, BTN_TOUCH, 1);
        assert_eq!(o.event(&n, key), key);
    }

    #[test]
    fn only_the_offered_transforms_parse() {
        assert_eq!(Orientation::from_panel_transform("90"), None);
        assert_eq!(Orientation::from_panel_transform(""), None);
    }
}

//! `struct input_event` and the handful of `linux/input-event-codes.h`
//! constants this crate needs. Not pulled from a crate: the surface is a
//! dozen numbers and one struct, and every other consumer in this repo
//! (`nix/rust-shell-client`) has no evdev dependency to inherit either.
//!
//! Layout note: `struct input_event`'s embedded `struct timeval` is two
//! `long`s on every ABI this crate targets (x86_64-linux-gnu for host
//! tests, riscv64-linux-gnu for the board) -- both are 64-bit LP64 Linux
//! targets, so `i64`/`i64` matches both without `#[cfg]`. This would need
//! revisiting on a 32-bit target, which this project does not have.

#![allow(dead_code)]

pub const EV_SYN: u16 = 0x00;
pub const EV_KEY: u16 = 0x01;
pub const EV_ABS: u16 = 0x03;

pub const SYN_REPORT: u16 = 0;

pub const BTN_LEFT: u16 = 0x110;
pub const BTN_TOOL_FINGER: u16 = 0x145;
pub const BTN_TOUCH: u16 = 0x14a;
pub const BTN_TOOL_DOUBLETAP: u16 = 0x14e;
pub const BTN_TOOL_TRIPLETAP: u16 = 0x14f;
pub const BTN_TOOL_QUADTAP: u16 = 0x150;

pub const ABS_MT_SLOT: u16 = 0x2f;
pub const ABS_MT_TOUCH_MAJOR: u16 = 0x30;
pub const ABS_MT_PRESSURE: u16 = 0x3a;
pub const ABS_MT_TRACKING_ID: u16 = 0x39;
pub const ABS_MT_POSITION_X: u16 = 0x35;
pub const ABS_MT_POSITION_Y: u16 = 0x36;

pub const INPUT_PROP_POINTER: u16 = 0x00;
pub const INPUT_PROP_DIRECT: u16 = 0x01;
pub const INPUT_PROP_BUTTONPAD: u16 = 0x02;

/// Protocol-B "no contact" tracking id, per `linux/input.h`.
pub const NO_TRACKING_ID: i32 = -1;

/// Bit-for-bit `struct input_event` (see module docs on the timeval ABI
/// assumption). `#[repr(C)]` plus matching field order and widths gives
/// the same layout the kernel writes/reads over the evdev/uinput char
/// devices.
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct InputEvent {
    pub tv_sec: i64,
    pub tv_usec: i64,
    pub type_: u16,
    pub code: u16,
    pub value: i32,
}

impl InputEvent {
    pub const fn new(tv_sec: i64, tv_usec: i64, type_: u16, code: u16, value: i32) -> Self {
        InputEvent { tv_sec, tv_usec, type_, code, value }
    }

    /// A synthesized event that inherits its timestamp from `origin` --
    /// the event (usually the frame's `SYN_REPORT`) that triggered it.
    /// libinput uses event timestamps for velocity/acceleration and tap
    /// timing, so a synthesized key event must carry a real timestamp
    /// from the same frame, not a zeroed or host-clock-drift one.
    pub const fn synthesize(origin: &InputEvent, type_: u16, code: u16, value: i32) -> Self {
        InputEvent { tv_sec: origin.tv_sec, tv_usec: origin.tv_usec, type_, code, value }
    }

    pub const fn is_syn_report(&self) -> bool {
        self.type_ == EV_SYN && self.code == SYN_REPORT
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn input_event_is_24_bytes_on_this_target() {
        // The size the kernel's uinput char device expects a write() of
        // one event to be, on a 64-bit LP64 target.
        assert_eq!(std::mem::size_of::<InputEvent>(), 24);
    }
}

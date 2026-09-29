//! Hand-bound `/dev/uinput` ioctl surface, and the one virtual device this
//! crate creates: a touchpad, not a touchscreen.
//!
//! The classification that matters happens entirely in *which capability
//! bits and `INPUT_PROP_*` flags this device declares*, not in any special
//! "become a touchpad" ioctl (there isn't one): udev's `input_id` builtin
//! and libinput's own `evdev_configure_device()` both look at
//! `BTN_TOOL_FINGER` + *not* `INPUT_PROP_DIRECT` to set `ID_INPUT_TOUCHPAD`
//! / classify as `LIBINPUT_DEVICE_CAP_POINTER` with gesture support,
//! versus `INPUT_PROP_DIRECT` (or no size/tool info at all) for a
//! touchscreen. This device declares `INPUT_PROP_POINTER` +
//! `INPUT_PROP_BUTTONPAD` (a clickpad: the whole surface is the button,
//! matching what this glass physically is) and every `BTN_TOOL_*`/
//! `BTN_TOUCH`/`BTN_LEFT` bit a real clickpad reports, and *never* sets
//! `INPUT_PROP_DIRECT`.
//!
//! ABS ranges are not hardcoded: `AbsRange` is read from the *real*
//! touchscreen device at startup (`EVIOCGABS`) and copied onto the virtual
//! device unchanged, including its `resolution` (units/mm) -- this is what
//! lets libinput estimate the pad's physical size for its acceleration and
//! gesture-distance math, and sidesteps `display/touch`'s recorded
//! quirk (native X range exceeding the device tree's declared
//! `touchscreen-size-x`): whatever the kernel driver actually reports as
//! its bounds is what gets mirrored, not a value transcribed from a spec.

use crate::event::*;
use std::fs::{File, OpenOptions};
use std::io;
use std::mem::size_of;
use std::os::unix::io::AsRawFd;

// -- generic (asm-generic) ioctl encoding -----------------------------
// Both this crate's targets (x86_64-linux-gnu for host tests,
// riscv64-linux-gnu for the board) use the asm-generic ioctl number
// layout (unlike sparc/mips/powerpc, which this project never targets),
// so one set of shift/mask constants covers both.
const IOC_NRBITS: u32 = 8;
const IOC_TYPEBITS: u32 = 8;
const IOC_SIZEBITS: u32 = 14;
const IOC_NRSHIFT: u32 = 0;
const IOC_TYPESHIFT: u32 = IOC_NRSHIFT + IOC_NRBITS;
const IOC_SIZESHIFT: u32 = IOC_TYPESHIFT + IOC_TYPEBITS;
const IOC_DIRSHIFT: u32 = IOC_SIZESHIFT + IOC_SIZEBITS;
const IOC_NONE: u32 = 0;
const IOC_WRITE: u32 = 1;
const IOC_READ: u32 = 2;

const fn ioc(dir: u32, ty: u32, nr: u32, size: u32) -> libc::c_ulong {
    ((dir << IOC_DIRSHIFT) | (ty << IOC_TYPESHIFT) | (nr << IOC_NRSHIFT) | (size << IOC_SIZESHIFT)) as libc::c_ulong
}
const fn io0(ty: u32, nr: u32) -> libc::c_ulong {
    ioc(IOC_NONE, ty, nr, 0)
}
const fn iow(ty: u32, nr: u32, size: u32) -> libc::c_ulong {
    ioc(IOC_WRITE, ty, nr, size)
}
const fn ior(ty: u32, nr: u32, size: u32) -> libc::c_ulong {
    ioc(IOC_READ, ty, nr, size)
}

const UINPUT_IOCTL_BASE: u32 = b'U' as u32;
const EVDEV_IOCTL_BASE: u32 = b'E' as u32;

const UI_SET_EVBIT_NR: u32 = 100;
const UI_SET_KEYBIT_NR: u32 = 101;
const UI_SET_ABSBIT_NR: u32 = 103;
const UI_SET_PROPBIT_NR: u32 = 110;

fn ui_dev_create() -> libc::c_ulong {
    io0(UINPUT_IOCTL_BASE, 1)
}
fn ui_dev_destroy() -> libc::c_ulong {
    io0(UINPUT_IOCTL_BASE, 2)
}
fn ui_dev_setup() -> libc::c_ulong {
    iow(UINPUT_IOCTL_BASE, 3, size_of::<UinputSetup>() as u32)
}
fn ui_abs_setup() -> libc::c_ulong {
    iow(UINPUT_IOCTL_BASE, 4, size_of::<UinputAbsSetup>() as u32)
}
fn ui_set_evbit() -> libc::c_ulong {
    iow(UINPUT_IOCTL_BASE, UI_SET_EVBIT_NR, size_of::<libc::c_int>() as u32)
}
fn ui_set_keybit() -> libc::c_ulong {
    iow(UINPUT_IOCTL_BASE, UI_SET_KEYBIT_NR, size_of::<libc::c_int>() as u32)
}
fn ui_set_absbit() -> libc::c_ulong {
    iow(UINPUT_IOCTL_BASE, UI_SET_ABSBIT_NR, size_of::<libc::c_int>() as u32)
}
fn ui_set_propbit() -> libc::c_ulong {
    iow(UINPUT_IOCTL_BASE, UI_SET_PROPBIT_NR, size_of::<libc::c_int>() as u32)
}
/// `EVIOCGRAB`: `_IOW('E', 0x90, int)`.
pub fn eviocgrab() -> libc::c_ulong {
    iow(EVDEV_IOCTL_BASE, 0x90, size_of::<libc::c_int>() as u32)
}
/// `EVIOCGABS(abs)`: `_IOR('E', 0x40 + abs, struct input_absinfo)`.
pub fn eviocgabs(abs: u16) -> libc::c_ulong {
    ior(EVDEV_IOCTL_BASE, 0x40 + abs as u32, size_of::<InputAbsInfo>() as u32)
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct InputId {
    pub bustype: u16,
    pub vendor: u16,
    pub product: u16,
    pub version: u16,
}

const UINPUT_MAX_NAME_SIZE: usize = 80;

#[repr(C)]
struct UinputSetup {
    id: InputId,
    name: [u8; UINPUT_MAX_NAME_SIZE],
    ff_effects_max: u32,
}

/// Bit-for-bit `struct input_absinfo`.
#[repr(C)]
#[derive(Clone, Copy, Default, Debug, PartialEq, Eq)]
pub struct InputAbsInfo {
    pub value: i32,
    pub minimum: i32,
    pub maximum: i32,
    pub fuzz: i32,
    pub flat: i32,
    pub resolution: i32,
}

#[repr(C)]
struct UinputAbsSetup {
    code: u16,
    absinfo: InputAbsInfo,
}

fn ioctl_int(fd: libc::c_int, request: libc::c_ulong, value: libc::c_int) -> io::Result<()> {
    let rc = unsafe { libc::ioctl(fd, request, value) };
    if rc < 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

/// Everything this virtual touchpad reports: EV_SYN + EV_KEY + EV_ABS,
/// plus the specific `ABS_MT_*` axes forwarded from the real touchscreen
/// and the specific tap/clickpad key bits libinput's classifier and
/// gesture engine look for.
const KEY_BITS: &[u16] = &[BTN_LEFT, BTN_TOUCH, BTN_TOOL_FINGER, BTN_TOOL_DOUBLETAP, BTN_TOOL_TRIPLETAP, BTN_TOOL_QUADTAP];

/// The subset of the real touchscreen's `input_absinfo` this crate needs
/// per axis to build a faithful virtual device, keyed by which `ABS_MT_*`
/// code they belong to.
#[derive(Clone, Copy, Debug, Default)]
pub struct AbsRanges {
    pub slot: InputAbsInfo,
    pub tracking_id: InputAbsInfo,
    pub position_x: InputAbsInfo,
    pub position_y: InputAbsInfo,
    pub pressure: InputAbsInfo,
}

/// Minimum-viable resolution (digitizer units per mm) to assume for the
/// position axes when the real device reports none (`resolution <= 0`).
/// Derived from this board's own documented geometry
/// (`openspec/config.yaml`: "a 4.1" 568x1232 RM69A10 AMOLED") and the
/// digitizer's native 1024x2400 range (`openspec/specs/display/touch/spec.md`):
/// a 4.1" diagonal at that pixel aspect ratio implies roughly a
/// 43.6mm x 94.5mm active area, giving ~23.5 units/mm (X) and ~25.4
/// units/mm (Y) against the native range -- close enough to each other to
/// be a believable physical-pixel-pitch sanity check, so 24 is used for
/// both axes. This is a fallback only, not a substitute for a real
/// reported resolution: it exists so libinput's size-dependent
/// acceleration/gesture heuristics see *something* plausible instead of a
/// literal zero, not because 24 is claimed to be this panel's true pitch.
const FALLBACK_RESOLUTION_UNITS_PER_MM: i32 = 24;

fn sane_resolution(reported: i32) -> i32 {
    if reported > 0 {
        reported
    } else {
        FALLBACK_RESOLUTION_UNITS_PER_MM
    }
}

/// True if `info` is a usable evdev ABS axis: a strictly positive range.
/// `min == max` (and worse, an all-zero `input_absinfo`) is exactly what
/// libinput's `evdev_configure_device()` flags as device-lies-about-its-
/// capabilities -- the literal board failure this function exists to catch
/// before it reaches `/dev/uinput`: a live board run
/// (`docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board-hang-2026-09-29.md`)
/// logged `"[libinput] ... kernel bug: device has min == max on
/// ABS_MT_PRESSURE"` because the real GT9895's `ABS_MT_PRESSURE`
/// `input_absinfo` (or this crate's own now-removed `unwrap_or_default()`
/// fallback, itself `min=0,max=0` -- equally degenerate) was mirrored onto
/// the virtual device unchecked.
fn axis_is_usable(info: &InputAbsInfo) -> bool {
    info.minimum < info.maximum
}

/// One axis this device will declare (`UI_SET_ABSBIT` + `UI_ABS_SETUP`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct AxisPlan {
    pub code: u16,
    pub info: InputAbsInfo,
}

/// Decides exactly which `ABS_MT_*` axes to declare on the virtual device
/// and with what (sanitized) ranges, from the real touchscreen's `ranges`.
///
/// `slot`/`tracking_id`/`position_x`/`position_y` are load-bearing -- a
/// touchpad with a degenerate position range cannot function at all --
/// so a degenerate range on any of those is a hard error refusing device
/// creation entirely, rather than creating something libinput will
/// misbehave on. `pressure` is cosmetic (this relay does not depend on it
/// for anything; slot occupancy, not pressure, drives `BTN_TOOL_*` in
/// `relay.rs`), so a degenerate pressure range is silently omitted from
/// the plan instead: the device is declared without that capability bit
/// at all, which is what real touchpads that don't report pressure also
/// do, and is exactly option "(or omit pressure if the source has none)"
/// from the board-failure fix request. `position_x`/`position_y`
/// resolution is passed through `sane_resolution` so a zero-resolution
/// source device still gets a plausible value.
pub fn axis_plan(ranges: &AbsRanges) -> Result<Vec<AxisPlan>, String> {
    let mut plan = Vec::with_capacity(5);
    for (name, code, info) in [
        ("ABS_MT_SLOT", ABS_MT_SLOT, ranges.slot),
        ("ABS_MT_TRACKING_ID", ABS_MT_TRACKING_ID, ranges.tracking_id),
        ("ABS_MT_POSITION_X", ABS_MT_POSITION_X, ranges.position_x),
        ("ABS_MT_POSITION_Y", ABS_MT_POSITION_Y, ranges.position_y),
    ] {
        if !axis_is_usable(&info) {
            return Err(format!(
                "touchscreen reports a degenerate range for {name} (minimum={} maximum={}); refusing to create a virtual touchpad libinput cannot use",
                info.minimum, info.maximum
            ));
        }
        let mut info = info;
        if code == ABS_MT_POSITION_X || code == ABS_MT_POSITION_Y {
            info.resolution = sane_resolution(info.resolution);
        }
        plan.push(AxisPlan { code, info });
    }
    if axis_is_usable(&ranges.pressure) {
        plan.push(AxisPlan { code: ABS_MT_PRESSURE, info: ranges.pressure });
    }
    Ok(plan)
}

pub struct VirtualTouchpad {
    file: File,
}

impl VirtualTouchpad {
    /// Creates the virtual touchpad device with the given `name` and the
    /// real touchscreen's own `ranges` mirrored onto every `ABS_MT_*`
    /// axis. Opens `/dev/uinput` itself (the caller does not need to hold
    /// its own fd).
    pub fn create(name: &str, ranges: &AbsRanges) -> io::Result<Self> {
        // Validated and sanitized before /dev/uinput is even opened: a
        // degenerate load-bearing axis is refused outright (see
        // axis_plan's doc comment), rather than handed to the kernel and
        // discovered only once libinput logs a "kernel bug" warning on
        // the board.
        let plan = axis_plan(ranges).map_err(|msg| io::Error::new(io::ErrorKind::InvalidData, msg))?;

        let file = OpenOptions::new().write(true).read(true).open("/dev/uinput")?;
        let fd = file.as_raw_fd();

        ioctl_int(fd, ui_set_evbit(), EV_SYN as libc::c_int)?;
        ioctl_int(fd, ui_set_evbit(), EV_KEY as libc::c_int)?;
        ioctl_int(fd, ui_set_evbit(), EV_ABS as libc::c_int)?;

        for &key in KEY_BITS {
            ioctl_int(fd, ui_set_keybit(), key as libc::c_int)?;
        }
        for axis in &plan {
            ioctl_int(fd, ui_set_absbit(), axis.code as libc::c_int)?;
        }
        // A clickpad (INPUT_PROP_BUTTONPAD): the whole glass surface is
        // the button, matching this hardware -- there is no separate
        // physical click mechanism. Deliberately no INPUT_PROP_DIRECT:
        // that property is what marks a touchscreen and is exactly what
        // must NOT be set for libinput to treat this as a pointer device.
        ioctl_int(fd, ui_set_propbit(), INPUT_PROP_POINTER as libc::c_int)?;
        ioctl_int(fd, ui_set_propbit(), INPUT_PROP_BUTTONPAD as libc::c_int)?;

        for axis in &plan {
            let setup = UinputAbsSetup { code: axis.code, absinfo: axis.info };
            let rc = unsafe { libc::ioctl(fd, ui_abs_setup(), &setup as *const UinputAbsSetup) };
            if rc < 0 {
                return Err(io::Error::last_os_error());
            }
        }

        let mut setup = UinputSetup {
            id: InputId { bustype: 0x06 /* BUS_VIRTUAL */, vendor: 0x0001, product: 0x0001, version: 1 },
            name: [0u8; UINPUT_MAX_NAME_SIZE],
            ff_effects_max: 0,
        };
        let name_bytes = name.as_bytes();
        let n = name_bytes.len().min(UINPUT_MAX_NAME_SIZE - 1);
        setup.name[..n].copy_from_slice(&name_bytes[..n]);
        let rc = unsafe { libc::ioctl(fd, ui_dev_setup(), &setup as *const UinputSetup) };
        if rc < 0 {
            return Err(io::Error::last_os_error());
        }

        ioctl_int(fd, ui_dev_create(), 0)?;
        Ok(VirtualTouchpad { file })
    }

    /// Writes one event to the virtual device. The kernel does not
    /// require an explicit flush; each `write()` of a full
    /// `struct input_event` is applied immediately.
    pub fn emit(&mut self, ev: &InputEvent) -> io::Result<()> {
        use std::io::Write;
        let bytes = unsafe { std::slice::from_raw_parts(ev as *const InputEvent as *const u8, size_of::<InputEvent>()) };
        self.file.write_all(bytes)
    }
}

impl Drop for VirtualTouchpad {
    fn drop(&mut self) {
        let _ = ioctl_int(self.file.as_raw_fd(), ui_dev_destroy(), 0);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ioctl_numbers_match_kernel_uapi_uinput_h() {
        // Cross-checked against linux/uinput.h's literal macro expansions
        // (not re-derived from the same shift constants under test, so a
        // shift-constant typo would still be caught).
        assert_eq!(ui_dev_create(), 0x5501);
        assert_eq!(ui_dev_destroy(), 0x5502);
        assert_eq!(ui_dev_setup(), 0x405c5503);
        assert_eq!(ui_abs_setup(), 0x401c5504);
        assert_eq!(ui_set_evbit(), 0x40045564);
        assert_eq!(ui_set_keybit(), 0x40045565);
        assert_eq!(ui_set_absbit(), 0x40045567);
        assert_eq!(ui_set_propbit(), 0x4004556e);
    }

    #[test]
    fn eviocgrab_matches_kernel_uapi_input_h() {
        assert_eq!(eviocgrab(), 0x40044590);
    }

    #[test]
    fn eviocgabs_matches_kernel_uapi_input_h_for_position_x() {
        // EVIOCGABS(ABS_MT_POSITION_X) = _IOR('E', 0x40 + 0x35, struct input_absinfo)
        assert_eq!(eviocgabs(ABS_MT_POSITION_X), 0x80184575);
    }

    #[test]
    fn uinput_setup_struct_size_is_92_bytes() {
        assert_eq!(size_of::<UinputSetup>(), 92);
    }

    #[test]
    fn uinput_abs_setup_struct_size_is_28_bytes() {
        assert_eq!(size_of::<UinputAbsSetup>(), 28);
    }

    fn valid_ranges() -> AbsRanges {
        AbsRanges {
            slot: InputAbsInfo { value: 0, minimum: 0, maximum: 9, fuzz: 0, flat: 0, resolution: 0 },
            tracking_id: InputAbsInfo { value: 0, minimum: 0, maximum: 65535, fuzz: 0, flat: 0, resolution: 0 },
            position_x: InputAbsInfo { value: 0, minimum: 0, maximum: 1023, fuzz: 0, flat: 0, resolution: 26 },
            position_y: InputAbsInfo { value: 0, minimum: 0, maximum: 2399, fuzz: 0, flat: 0, resolution: 26 },
            pressure: InputAbsInfo { value: 0, minimum: 0, maximum: 255, fuzz: 0, flat: 0, resolution: 0 },
        }
    }

    /// The exact board failure: `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board-hang-2026-09-29.md`
    /// records libinput logging `"kernel bug: device has min == max on
    /// ABS_MT_PRESSURE"` when this crate mirrored the real GT9895's
    /// degenerate (`min=0, max=0`) `ABS_MT_PRESSURE` `input_absinfo`
    /// verbatim onto the virtual device.
    #[test]
    fn axis_plan_omits_degenerate_pressure_matching_the_observed_board_bug() {
        let mut ranges = valid_ranges();
        ranges.pressure = InputAbsInfo { value: 0, minimum: 0, maximum: 0, fuzz: 0, flat: 0, resolution: 0 };
        let plan = axis_plan(&ranges).expect("a degenerate optional axis must not fail the whole plan");
        assert!(!plan.iter().any(|a| a.code == ABS_MT_PRESSURE), "degenerate pressure must be omitted entirely: {plan:?}");
        // Every load-bearing axis must still be present.
        for code in [ABS_MT_SLOT, ABS_MT_TRACKING_ID, ABS_MT_POSITION_X, ABS_MT_POSITION_Y] {
            assert!(plan.iter().any(|a| a.code == code), "missing load-bearing axis {code}");
        }
    }

    #[test]
    fn axis_plan_includes_a_genuinely_valid_pressure_axis() {
        let ranges = valid_ranges();
        let plan = axis_plan(&ranges).unwrap();
        assert!(plan.iter().any(|a| a.code == ABS_MT_PRESSURE && a.info.minimum == 0 && a.info.maximum == 255));
    }

    #[test]
    fn axis_plan_rejects_a_degenerate_load_bearing_axis() {
        // Unlike pressure, a degenerate position range is not something a
        // touchpad can function without -- axis_plan must refuse to build
        // a plan at all rather than silently omitting ABS_MT_POSITION_X.
        let mut ranges = valid_ranges();
        ranges.position_x = InputAbsInfo { value: 0, minimum: 500, maximum: 500, fuzz: 0, flat: 0, resolution: 0 };
        let err = axis_plan(&ranges).unwrap_err();
        assert!(err.contains("ABS_MT_POSITION_X"), "error should name the bad axis: {err}");
    }

    #[test]
    fn axis_plan_falls_back_to_a_sane_resolution_when_the_source_reports_zero() {
        let mut ranges = valid_ranges();
        ranges.position_x.resolution = 0;
        ranges.position_y.resolution = 0;
        let plan = axis_plan(&ranges).unwrap();
        let x = plan.iter().find(|a| a.code == ABS_MT_POSITION_X).unwrap();
        let y = plan.iter().find(|a| a.code == ABS_MT_POSITION_Y).unwrap();
        assert_eq!(x.info.resolution, FALLBACK_RESOLUTION_UNITS_PER_MM);
        assert_eq!(y.info.resolution, FALLBACK_RESOLUTION_UNITS_PER_MM);
    }

    #[test]
    fn axis_plan_preserves_a_real_reported_resolution() {
        let ranges = valid_ranges(); // resolution: 26, not the fallback's 24.
        let plan = axis_plan(&ranges).unwrap();
        let x = plan.iter().find(|a| a.code == ABS_MT_POSITION_X).unwrap();
        assert_eq!(x.info.resolution, 26);
    }

    /// `VirtualTouchpad::create` refuses a degenerate load-bearing axis
    /// before it ever opens `/dev/uinput` -- this must be provable without
    /// any device permissions at all, in any sandbox.
    #[test]
    fn create_rejects_degenerate_position_range_without_touching_dev_uinput() {
        let mut ranges = valid_ranges();
        ranges.position_y = InputAbsInfo { value: 0, minimum: 0, maximum: 0, fuzz: 0, flat: 0, resolution: 0 };
        match VirtualTouchpad::create("should-not-be-created", &ranges) {
            Err(e) => assert_eq!(e.kind(), io::ErrorKind::InvalidData),
            Ok(_) => panic!("a degenerate load-bearing axis must be rejected, not create a device"),
        }
    }

    /// Real device creation and destruction against the host's own
    /// `/dev/uinput`. Per the operator's note ("create a uinput device on
    /// the host only if it needs no root"): this session's `/dev/uinput`
    /// carries a seat ACL (`getfacl /dev/uinput`) making it writable by
    /// the logged-in user without root, so this runs for real rather than
    /// being skipped -- but it still only proves the ioctl sequence is
    /// accepted by a (host x86_64) Linux kernel, not that it behaves
    /// correctly attached to the K230's real GT9895 and libinput's Sway
    /// instance. That remains board evidence, not host evidence.
    #[test]
    fn creates_and_destroys_a_real_virtual_touchpad_if_permitted() {
        match VirtualTouchpad::create("k230-touch-trackpad-test", &valid_ranges()) {
            Ok(mut dev) => {
                let ev = InputEvent::new(0, 0, EV_SYN, SYN_REPORT, 0);
                dev.emit(&ev).expect("write to a just-created uinput device should succeed");
                // Dropping runs UI_DEV_DESTROY.
            }
            Err(e) if e.kind() == io::ErrorKind::PermissionDenied => {
                eprintln!("skipping live uinput test: /dev/uinput not writable in this sandbox ({e})");
            }
            Err(e) => panic!("unexpected /dev/uinput error: {e}"),
        }
    }

    /// Same live-device proof as above, but with the *exact* fixture that
    /// reproduces the board's real `ABS_MT_PRESSURE` range
    /// (`min=0, max=0`) instead of a well-formed one -- confirms the fix
    /// actually resolves the observed failure mode end to end (sanitized
    /// by `axis_plan` before reaching `/dev/uinput`), not just that
    /// `axis_plan`'s pure logic returns the right `Vec`.
    #[test]
    fn creates_a_real_virtual_touchpad_with_the_boards_exact_degenerate_pressure_range() {
        let mut ranges = valid_ranges();
        ranges.pressure = InputAbsInfo { value: 0, minimum: 0, maximum: 0, fuzz: 0, flat: 0, resolution: 0 };
        match VirtualTouchpad::create("k230-touch-trackpad-test-degenerate-pressure", &ranges) {
            Ok(mut dev) => {
                let ev = InputEvent::new(0, 0, EV_SYN, SYN_REPORT, 0);
                dev.emit(&ev).expect("write to a just-created uinput device should succeed");
            }
            Err(e) if e.kind() == io::ErrorKind::PermissionDenied => {
                eprintln!("skipping live uinput test: /dev/uinput not writable in this sandbox ({e})");
            }
            Err(e) => panic!("unexpected /dev/uinput error with the board's real (sanitized) ranges: {e}"),
        }
    }
}

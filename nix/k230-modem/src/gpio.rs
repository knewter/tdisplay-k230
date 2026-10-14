//! The enable line through the GPIO character device, uAPI v2.

use crate::engine::EnableLine;
use std::fs::{self, File};
use std::io;
use std::os::fd::{AsRawFd, FromRawFd, RawFd};

#[repr(C)]
#[derive(Clone, Copy)]
struct LineAttr {
    id: u32,
    padding: u32,
    value: u64,
}

#[repr(C)]
#[derive(Clone, Copy)]
struct ConfigAttr {
    attr: LineAttr,
    mask: u64,
}

#[repr(C)]
struct LineConfig {
    flags: u64,
    num_attrs: u32,
    padding: [u32; 5],
    attrs: [ConfigAttr; 10],
}

#[repr(C)]
struct LineRequest {
    offsets: [u32; 64],
    consumer: [u8; 32],
    config: LineConfig,
    num_lines: u32,
    event_buffer_size: u32,
    padding: [u32; 5],
    fd: i32,
}

#[repr(C)]
struct LineValues {
    bits: u64,
    mask: u64,
}

#[repr(C)]
struct ChipInfo {
    name: [u8; 32],
    label: [u8; 32],
    lines: u32,
}

#[repr(C)]
struct LineInfo {
    name: [u8; 32],
    consumer: [u8; 32],
    offset: u32,
    num_attrs: u32,
    flags: u64,
    attrs: [LineAttr; 10],
    padding: [u32; 4],
}

const fn ioc(dir: u32, nr: u32, size: usize) -> libc::c_ulong {
    ((dir << 30) | ((size as u32) << 16) | (0xB4 << 8) | nr) as libc::c_ulong
}

const GET_CHIPINFO: libc::c_ulong = ioc(2, 0x01, std::mem::size_of::<ChipInfo>());
const GET_LINEINFO: libc::c_ulong = ioc(3, 0x05, std::mem::size_of::<LineInfo>());
const GET_LINE: libc::c_ulong = ioc(3, 0x07, std::mem::size_of::<LineRequest>());
const SET_VALUES: libc::c_ulong = ioc(3, 0x0F, std::mem::size_of::<LineValues>());

const FLAG_OUTPUT: u64 = 1 << 3;
const ATTR_ID_OUTPUT_VALUES: u32 = 2;

fn cstr(b: &[u8]) -> String {
    let end = b.iter().position(|c| *c == 0).unwrap_or(b.len());
    String::from_utf8_lossy(&b[..end]).into_owned()
}

fn ioctl<T>(fd: RawFd, req: libc::c_ulong, arg: &mut T) -> io::Result<()> {
    // SAFETY: arg is a live, correctly sized repr(C) struct for this request.
    let r = unsafe { libc::ioctl(fd, req as _, arg as *mut T) };
    if r < 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(())
    }
}

/// Find a line by its name across `/dev/gpiochip*`.
pub fn find_line(name: &str) -> io::Result<(String, u32)> {
    let mut chips: Vec<_> = fs::read_dir("/dev")?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.file_name().map(|n| n.to_string_lossy().starts_with("gpiochip")).unwrap_or(false))
        .collect();
    chips.sort();
    for chip in chips {
        let f = File::open(&chip)?;
        // SAFETY: all-zero is a valid value for these plain C structs.
        let mut info: ChipInfo = unsafe { std::mem::zeroed() };
        ioctl(f.as_raw_fd(), GET_CHIPINFO, &mut info)?;
        for off in 0..info.lines {
            let mut li: LineInfo = unsafe { std::mem::zeroed() };
            li.offset = off;
            ioctl(f.as_raw_fd(), GET_LINEINFO, &mut li)?;
            if cstr(&li.name) == name {
                return Ok((chip.to_string_lossy().into_owned(), off));
            }
        }
    }
    Err(io::Error::new(io::ErrorKind::NotFound, format!("no GPIO line named {name}")))
}

/// The requested enable line. Holding this object holds the line.
pub struct GpioEnable {
    line: File,
}

impl GpioEnable {
    /// Request the named line as an output, driven low.
    pub fn open_named(name: &str) -> io::Result<GpioEnable> {
        let (chip, offset) = find_line(name)?;
        let chip = File::open(chip)?;
        // SAFETY: zeroed plain C struct.
        let mut req: LineRequest = unsafe { std::mem::zeroed() };
        req.offsets[0] = offset;
        req.num_lines = 1;
        let label = b"k230-modem";
        req.consumer[..label.len()].copy_from_slice(label);
        req.config.flags = FLAG_OUTPUT;
        req.config.num_attrs = 1;
        req.config.attrs[0] = ConfigAttr {
            attr: LineAttr { id: ATTR_ID_OUTPUT_VALUES, padding: 0, value: 0 },
            mask: 1,
        };
        ioctl(chip.as_raw_fd(), GET_LINE, &mut req)?;
        // SAFETY: the kernel returned a new fd for the line request.
        Ok(GpioEnable { line: unsafe { File::from_raw_fd(req.fd) } })
    }
}

impl EnableLine for GpioEnable {
    fn set(&mut self, on: bool) -> io::Result<()> {
        let mut v = LineValues { bits: on as u64, mask: 1 };
        ioctl(self.line.as_raw_fd(), SET_VALUES, &mut v)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::mem::size_of;

    #[test]
    fn uapi_struct_sizes_and_request_numbers() {
        assert_eq!(size_of::<LineAttr>(), 16);
        assert_eq!(size_of::<ConfigAttr>(), 24);
        assert_eq!(size_of::<LineConfig>(), 272);
        assert_eq!(size_of::<LineRequest>(), 592);
        assert_eq!(size_of::<LineInfo>(), 256);
        assert_eq!(size_of::<ChipInfo>(), 68);
        assert_eq!(GET_LINE, 0xC250_B407);
        assert_eq!(GET_LINEINFO, 0xC100_B405);
        assert_eq!(GET_CHIPINFO, 0x8044_B401);
        assert_eq!(SET_VALUES, 0xC010_B40F);
    }
}

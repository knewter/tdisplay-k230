//! The modem's UART: 115200 8N1, no flow control, opened exclusively.

use crate::at::LineBuf;
use crate::engine::Link;
use std::io;
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd, RawFd};
use std::time::{Duration, Instant};

pub struct SerialLink {
    fd: OwnedFd,
    buf: LineBuf,
}

fn cvt(r: libc::c_int) -> io::Result<libc::c_int> {
    if r < 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(r)
    }
}

fn wait(fd: RawFd, events: i16, timeout: Duration) -> io::Result<bool> {
    let ms = timeout.as_millis().min(i32::MAX as u128) as i32 + i32::from(timeout.subsec_nanos() % 1_000_000 != 0);
    let mut p = libc::pollfd { fd, events, revents: 0 };
    // SAFETY: p is a valid pollfd for one descriptor.
    let n = unsafe { libc::poll(&mut p, 1, ms) };
    if n < 0 {
        let e = io::Error::last_os_error();
        if e.kind() == io::ErrorKind::Interrupted {
            return Ok(false);
        }
        return Err(e);
    }
    Ok(n > 0)
}

impl SerialLink {
    pub fn open(path: &str) -> io::Result<SerialLink> {
        let c = std::ffi::CString::new(path).map_err(|_| io::Error::from(io::ErrorKind::InvalidInput))?;
        // SAFETY: valid NUL-terminated path.
        let raw = cvt(unsafe { libc::open(c.as_ptr(), libc::O_RDWR | libc::O_NOCTTY | libc::O_NONBLOCK | libc::O_CLOEXEC) })?;
        // SAFETY: freshly opened descriptor that nothing else owns.
        let fd = unsafe { OwnedFd::from_raw_fd(raw) };
        // Refuse every other non-privileged opener while we hold it.
        cvt(unsafe { libc::ioctl(raw, libc::TIOCEXCL as _) })?;
        // SAFETY: tcgetattr fills a zeroed termios.
        let mut t: libc::termios = unsafe { std::mem::zeroed() };
        cvt(unsafe { libc::tcgetattr(raw, &mut t) })?;
        unsafe { libc::cfmakeraw(&mut t) };
        t.c_cflag |= libc::CLOCAL | libc::CREAD | libc::CS8;
        t.c_cflag &= !(libc::CRTSCTS | libc::CSTOPB | libc::PARENB);
        t.c_cc[libc::VMIN] = 0;
        t.c_cc[libc::VTIME] = 0;
        // glibc 2.42 takes speed_t as the plain baud rate, so the libc
        // crate's legacy B115200 (0o010002) would set 4098 baud; older glibc
        // rejects a plain number. Try the number first, then the constant.
        // SAFETY: t is an initialised termios.
        if unsafe { libc::cfsetspeed(&mut t, 115_200) } != 0 {
            cvt(unsafe { libc::cfsetspeed(&mut t, libc::B115200) })?;
        }
        cvt(unsafe { libc::tcsetattr(raw, libc::TCSANOW, &t) })?;
        cvt(unsafe { libc::tcflush(raw, libc::TCIOFLUSH) })?;
        Ok(SerialLink { fd, buf: LineBuf::default() })
    }
}

impl Link for SerialLink {
    fn send(&mut self, data: &[u8]) -> io::Result<()> {
        let mut off = 0;
        while off < data.len() {
            // SAFETY: the pointer and length describe the unwritten tail of data.
            let n = unsafe { libc::write(self.fd.as_raw_fd(), data[off..].as_ptr().cast(), data.len() - off) };
            if n < 0 {
                let e = io::Error::last_os_error();
                if e.kind() == io::ErrorKind::WouldBlock {
                    wait(self.fd.as_raw_fd(), libc::POLLOUT, Duration::from_millis(200))?;
                    continue;
                }
                if e.kind() == io::ErrorKind::Interrupted {
                    continue;
                }
                return Err(e);
            }
            off += n as usize;
        }
        Ok(())
    }

    fn recv_line(&mut self, timeout: Duration) -> io::Result<Option<String>> {
        let deadline = Instant::now() + timeout;
        loop {
            if let Some(l) = self.buf.next_line() {
                return Ok(Some(l));
            }
            let Some(left) = deadline.checked_duration_since(Instant::now()) else { return Ok(None) };
            if !wait(self.fd.as_raw_fd(), libc::POLLIN, left)? {
                continue;
            }
            let mut tmp = [0u8; 512];
            // SAFETY: tmp is a writable buffer of the stated length.
            let n = unsafe { libc::read(self.fd.as_raw_fd(), tmp.as_mut_ptr().cast(), tmp.len()) };
            if n < 0 {
                let e = io::Error::last_os_error();
                if matches!(e.kind(), io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted) {
                    continue;
                }
                return Err(e);
            }
            if n == 0 {
                // VMIN=0 non-blocking: nothing to read right now.
                continue;
            }
            self.buf.push(&tmp[..n as usize]);
        }
    }
}

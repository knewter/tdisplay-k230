//! The NMEA pty `gpsd` reads. The service holds both ends, so `gpsd` can
//! open and close the slave without the master seeing a hangup.

use std::ffi::{CStr, CString};
use std::io;
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
use std::os::unix::fs::symlink;
use std::path::Path;

pub struct NmeaPty {
    master: OwnedFd,
    slave: OwnedFd,
}

fn cvt(r: libc::c_int) -> io::Result<libc::c_int> {
    if r < 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(r)
    }
}

impl NmeaPty {
    /// Create the pty and point `link` at its slave, group-owned by `gid`
    /// with mode 0660.
    pub fn create(link: &Path, gid: Option<u32>) -> io::Result<NmeaPty> {
        // SAFETY: standard pty setup; every return value is checked.
        unsafe {
            let m = cvt(libc::posix_openpt(libc::O_RDWR | libc::O_NOCTTY | libc::O_CLOEXEC | libc::O_NONBLOCK))?;
            let master = OwnedFd::from_raw_fd(m);
            cvt(libc::grantpt(m))?;
            cvt(libc::unlockpt(m))?;
            let mut name = [0 as libc::c_char; 128];
            cvt(libc::ptsname_r(m, name.as_mut_ptr(), name.len()))?;
            let path = CStr::from_ptr(name.as_ptr()).to_owned();
            let s = cvt(libc::open(path.as_ptr(), libc::O_RDWR | libc::O_NOCTTY | libc::O_CLOEXEC))?;
            let slave = OwnedFd::from_raw_fd(s);
            let mut t: libc::termios = std::mem::zeroed();
            cvt(libc::tcgetattr(s, &mut t))?;
            libc::cfmakeraw(&mut t);
            cvt(libc::tcsetattr(s, libc::TCSANOW, &t))?;
            cvt(libc::fchmod(s, 0o660))?;
            cvt(libc::fchown(s, 0, gid.unwrap_or(u32::MAX)))?;
            let _ = std::fs::remove_file(link);
            let target = CString::new(path.to_bytes()).expect("no NUL");
            symlink(Path::new(&*target.to_string_lossy()), link)?;
            Ok(NmeaPty { master, slave })
        }
    }

    /// Write one sentence. A full buffer (nobody reading) drops it.
    pub fn write_line(&mut self, s: &str) {
        let mut data = s.as_bytes().to_vec();
        data.extend_from_slice(b"\r\n");
        // SAFETY: data outlives the call.
        unsafe { libc::write(self.master.as_raw_fd(), data.as_ptr().cast(), data.len()) };
    }

    /// Discard anything buffered, so a reader that connects later never
    /// sees a stale sentence.
    pub fn flush(&mut self) {
        // SAFETY: plain tcflush on a descriptor we own.
        unsafe { libc::tcflush(self.slave.as_raw_fd(), libc::TCIFLUSH) };
        unsafe { libc::tcflush(self.master.as_raw_fd(), libc::TCOFLUSH) };
    }
}

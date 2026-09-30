//! Opens the real touchscreen event device: reads its `ABS_MT_*` ranges
//! (to build a faithful `uinput::AbsRanges`), and grabs/ungrabs it with
//! `EVIOCGRAB` to switch it exclusively to this daemon (trackpad mode) or
//! back to normal (direct-touch mode, letting Sway's `map_to_output`
//! absolute mapping see it again).

use crate::event::*;
use crate::uinput::{eviocgabs, eviocgrab, AbsRanges, InputAbsInfo};
use std::fs::{File, OpenOptions};
use std::io;
use std::mem::size_of;
use std::os::unix::io::AsRawFd;

pub struct TouchDevice {
    file: File,
}

impl TouchDevice {
    /// Opens the device non-blocking: the caller (`main.rs`'s poll loop)
    /// drains whatever events are immediately available and then must
    /// re-check the HDMI/panel mode rather than blocking indefinitely on
    /// the next touch, or a switch back to direct-touch mode would only
    /// be noticed after the next finger contact.
    pub fn open(path: &std::path::Path) -> io::Result<Self> {
        let file = OpenOptions::new().read(true).write(false).open(path)?;
        let flags = unsafe { libc::fcntl(file.as_raw_fd(), libc::F_GETFL, 0) };
        if flags < 0 {
            return Err(io::Error::last_os_error());
        }
        let rc = unsafe { libc::fcntl(file.as_raw_fd(), libc::F_SETFL, flags | libc::O_NONBLOCK) };
        if rc < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(TouchDevice { file })
    }

    fn get_abs(&self, code: u16) -> io::Result<InputAbsInfo> {
        let mut info = InputAbsInfo::default();
        let rc = unsafe { libc::ioctl(self.file.as_raw_fd(), eviocgabs(code), &mut info as *mut InputAbsInfo) };
        if rc < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(info)
    }

    /// Reads the real device's `ABS_MT_*` ranges to mirror onto the
    /// virtual touchpad. `ABS_MT_TRACKING_ID` has no natural absinfo on
    /// many touchscreens (it's often unbounded/driver-specific); if the
    /// ioctl fails for it specifically, falls back to a wide 16-bit range
    /// rather than failing the whole read, since libinput does not use
    /// this axis's bounds for classification or gesture math.
    ///
    /// The returned ranges are **not** sanitized here -- a real board run
    /// (`docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board-hang-2026-09-29.md`)
    /// found the GT9895 reports a degenerate (`min == max`) `ABS_MT_PRESSURE`
    /// range; `uinput::axis_plan` is what validates and sanitizes these
    /// before any axis reaches `/dev/uinput`, deliberately kept as one
    /// place so it can be unit tested against exactly that observed case.
    /// If the `ABS_MT_PRESSURE` ioctl itself fails, the fallback here is
    /// `InputAbsInfo::default()` (`min=0,max=0`) -- also degenerate, and
    /// also caught by the same `axis_plan` check, rather than needing its
    /// own special case.
    pub fn read_ranges(&self) -> io::Result<AbsRanges> {
        let tracking_id = self
            .get_abs(ABS_MT_TRACKING_ID)
            .unwrap_or(InputAbsInfo { value: 0, minimum: 0, maximum: 65535, fuzz: 0, flat: 0, resolution: 0 });
        Ok(AbsRanges {
            slot: self.get_abs(ABS_MT_SLOT)?,
            tracking_id,
            position_x: self.get_abs(ABS_MT_POSITION_X)?,
            position_y: self.get_abs(ABS_MT_POSITION_Y)?,
            pressure: self.get_abs(ABS_MT_PRESSURE).unwrap_or_default(),
        })
    }

    /// Read persistent protocol-B positions before receiving a fresh contact.
    /// Unchanged axes need not be resent with a new tracking ID.
    pub fn slot_positions(&self) -> io::Result<Vec<(i32, i32)>> {
        const COUNT: usize = 16;
        fn request_size() -> libc::c_ulong { (2 << 30) | (68 << 16) | ((b'E' as libc::c_ulong) << 8) | 0x0a }
        let mut xs = [0i32; COUNT + 1]; xs[0] = ABS_MT_POSITION_X as i32;
        let mut ys = [0i32; COUNT + 1]; ys[0] = ABS_MT_POSITION_Y as i32;
        for values in [&mut xs, &mut ys] {
            if unsafe { libc::ioctl(self.file.as_raw_fd(), request_size(), values.as_mut_ptr()) } < 0 {
                return Err(io::Error::last_os_error());
            }
        }
        let count = (self.get_abs(ABS_MT_SLOT)?.maximum + 1).clamp(0, COUNT as i32) as usize;
        Ok((1..=count).map(|i| (xs[i], ys[i])).collect())
    }

    /// `EVIOCGRAB(1)`: takes exclusive delivery of this device's events --
    /// libinput/Sway stop seeing them the instant this succeeds.
    pub fn grab(&self) -> io::Result<()> {
        let rc = unsafe { libc::ioctl(self.file.as_raw_fd(), eviocgrab(), 1 as libc::c_int) };
        if rc < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }

    /// `EVIOCGRAB(0)`: releases the grab, letting the touchscreen resume
    /// delivering to every other listener (Sway's direct-touch mapping)
    /// immediately.
    pub fn ungrab(&self) -> io::Result<()> {
        let rc = unsafe { libc::ioctl(self.file.as_raw_fd(), eviocgrab(), 0 as libc::c_int) };
        if rc < 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }

    /// Reads exactly one `struct input_event`, or `ErrorKind::WouldBlock`
    /// if none is available right now (the fd is non-blocking).
    pub fn read_event(&mut self) -> io::Result<InputEvent> {
        use std::io::Read;
        let mut buf = [0u8; size_of::<InputEvent>()];
        self.file.read_exact(&mut buf)?;
        Ok(unsafe { std::ptr::read(buf.as_ptr() as *const InputEvent) })
    }

    /// Blocks (via `poll(2)`) for up to `timeout_ms` for the device to
    /// become readable. Returns `Ok(true)` if it did, `Ok(false)` on
    /// timeout -- the caller uses a timeout so it still re-checks the
    /// HDMI/panel mode periodically even while the touchscreen stays
    /// silent, without busy-polling in between.
    ///
    /// Checks `revents` explicitly rather than just `poll`'s return code:
    /// an earlier version returned `Ok(rc > 0)` for *any* reported event,
    /// including `POLLERR`/`POLLHUP`/`POLLNVAL` with no `POLLIN` at all.
    /// If a device ever reaches a state where the kernel reports one of
    /// those on every `poll()` call without actually blocking (a hung-up
    /// or erroring fd that never legitimately blocks again), that bug
    /// turns this into an unbounded tight loop -- `poll()` returns
    /// instantly forever, the caller believes data is ready, and nothing
    /// ever sleeps. Surfacing those as a real `Err` instead makes the
    /// caller tear the session down (see `main.rs`), which does sleep
    /// afterwards, closing off that failure mode regardless of whether it
    /// is what actually produced the board hang this was added in
    /// response to (`docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board-hang-2026-09-29.md`).
    pub fn wait_readable(&self, timeout_ms: i32) -> io::Result<bool> {
        let mut pfd = libc::pollfd { fd: self.file.as_raw_fd(), events: libc::POLLIN, revents: 0 };
        let rc = unsafe { libc::poll(&mut pfd as *mut libc::pollfd, 1, timeout_ms) };
        if rc < 0 {
            return Err(io::Error::last_os_error());
        }
        if rc == 0 {
            return Ok(false);
        }
        if pfd.revents & (libc::POLLERR | libc::POLLHUP | libc::POLLNVAL) != 0 {
            return Err(io::Error::other(format!("touchscreen fd reported revents=0x{:x}", pfd.revents)));
        }
        Ok(pfd.revents & libc::POLLIN != 0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::time::{Duration, Instant};

    /// Proves `wait_readable` really blocks (does not busy-spin) for the
    /// requested timeout when there is nothing to read, and returns
    /// promptly once there is -- the exact mechanism `main.rs`'s poll loop
    /// depends on to avoid becoming an unbounded tight loop. Can't use a
    /// real evdev device for this on the host (`/dev/input/event*` nodes
    /// are `root:input` with no seat ACL in this sandbox, unlike
    /// `/dev/uinput`); a FIFO exercises the same `poll(2)`-on-a-char/pipe-
    /// like-fd code path `wait_readable` itself uses, which is what's
    /// under test here, not evdev-specific behavior.
    #[test]
    fn wait_readable_blocks_for_the_timeout_then_returns_promptly_once_data_arrives() {
        let path = std::env::temp_dir().join(format!("k230-tt-wait-readable-fifo-{}", std::process::id()));
        let _ = std::fs::remove_file(&path);
        let c_path = std::ffi::CString::new(path.to_str().unwrap()).unwrap();
        let rc = unsafe { libc::mkfifo(c_path.as_ptr(), 0o600) };
        assert_eq!(rc, 0, "mkfifo failed: {}", io::Error::last_os_error());

        // FIFO open semantics deadlock two ways here if done naively:
        // open(O_RDONLY) blocks until a writer exists, and open(O_WRONLY)
        // blocks until a reader exists. A throwaway O_RDONLY|O_NONBLOCK
        // "pin" fd is opened first -- valid immediately with no writer,
        // per open(2) -- so a writer can then open without blocking, and
        // TouchDevice::open's own (blocking) O_RDONLY open right after
        // that also returns immediately, since a writer now exists.
        let pin_reader_fd = unsafe { libc::open(c_path.as_ptr(), libc::O_RDONLY | libc::O_NONBLOCK) };
        assert!(pin_reader_fd >= 0, "pin-reader open failed: {}", io::Error::last_os_error());

        let mut writer = OpenOptions::new().write(true).open(&path).expect("open FIFO write end");

        let dev = TouchDevice::open(&path).expect("open FIFO read end");

        // Nothing written yet: must block for roughly the timeout, not
        // return instantly (which would indicate the POLLHUP/POLLERR-
        // masking bug this function was fixed to close off).
        let start = Instant::now();
        let ready = dev.wait_readable(150).expect("poll on an idle FIFO should not error");
        let elapsed = start.elapsed();
        assert!(!ready, "an idle FIFO must not report readable");
        assert!(elapsed >= Duration::from_millis(100), "wait_readable returned after only {elapsed:?}, should have blocked ~150ms");
        assert!(elapsed < Duration::from_secs(2), "wait_readable took {elapsed:?}, far longer than its 150ms timeout");

        // Now write a byte and confirm it returns quickly (not waiting out
        // a full second timeout).
        writer.write_all(&[0u8]).unwrap();
        writer.flush().unwrap();
        let start = Instant::now();
        let ready = dev.wait_readable(1000).expect("poll on a written-to FIFO should not error");
        assert!(ready, "a FIFO with a byte written to it must report readable");
        assert!(start.elapsed() < Duration::from_millis(500), "wait_readable took {:?} to notice ready data", start.elapsed());

        unsafe {
            libc::close(pin_reader_fd);
        }
        let _ = std::fs::remove_file(&path);
    }
}

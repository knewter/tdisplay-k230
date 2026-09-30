//! One bounded worker and persistent Sway IPC stream, never per-frame forks.
use crate::gestures::Begin;
use std::collections::VecDeque;
use std::io::{self, Read, Write};
use std::os::unix::{
    fs::{FileTypeExt, MetadataExt},
    net::UnixStream,
};
use std::path::PathBuf;
use std::sync::{mpsc, Arc, Condvar, Mutex};
use std::time::{Duration, Instant};

const TIMEOUT: Duration = Duration::from_millis(250);
// Movement/release run off the input thread. Allow a slow board frame to
// finish without abandoning a valid stream; still below its 1s watchdog.
const STREAM_TIMEOUT: Duration = Duration::from_millis(750);
const HEARTBEAT: Duration = Duration::from_millis(200);
const MAX_REPLY: usize = 4096;
type Point = (f64, f64, u32);
enum Control {
    Begin(u64, Begin, mpsc::SyncSender<bool>),
    End(u64, bool, u32),
}
#[derive(Default)]
struct Pending {
    controls: VecDeque<Control>,
    latest: Option<(u64, Point)>,
    stop: bool,
}
type Mailbox = Arc<(Mutex<Pending>, Condvar)>;

pub fn monotonic_ms() -> u64 {
    let mut value = libc::timespec {
        tv_sec: 0,
        tv_nsec: 0,
    };
    unsafe {
        libc::clock_gettime(libc::CLOCK_MONOTONIC, &mut value);
    }
    value.tv_sec as u64 * 1000 + value.tv_nsec as u64 / 1_000_000
}
pub struct Shell {
    box_: Mailbox,
    worker: Option<std::thread::JoinHandle<()>>,
    seq: u64,
}
impl Shell {
    pub fn new(path: PathBuf) -> Self {
        let box_: Mailbox = Arc::new((Mutex::new(Pending::default()), Condvar::new()));
        let copy = box_.clone();
        let worker = std::thread::spawn(move || run(path, copy));
        Self {
            box_,
            worker: Some(worker),
            seq: (monotonic_ms() << 16) ^ (std::process::id() as u64),
        }
    }
    pub fn begin(&mut self, begin: Begin) -> bool {
        // Refresh the epoch on every begin, including after an idle interval
        // or a separate controller's recovery probe. A long-lived worker
        // must not remain below the compositor's last accepted sequence.
        self.seq = (self.seq + 1).max((monotonic_ms() << 16) ^ (std::process::id() as u64));
        let (tx, rx) = mpsc::sync_channel(1);
        {
            let mut pending = self.box_.0.lock().unwrap();
            if pending.stop || pending.controls.len() >= 4 {
                return false;
            }
            pending
                .controls
                .push_back(Control::Begin(self.seq, begin, tx));
        }
        self.box_.1.notify_one();
        rx.recv_timeout(TIMEOUT + Duration::from_millis(20))
            .unwrap_or(false)
    }
    pub fn motion(&self, dx: f64, dy: f64, time_ms: u32) {
        let mut pending = self.box_.0.lock().unwrap();
        pending.latest = Some((self.seq, (dx, dy, time_ms)));
        self.box_.1.notify_one();
    }
    pub fn end(&self, cancel: bool, time_ms: u32) {
        let mut pending = self.box_.0.lock().unwrap();
        if pending.controls.len() >= 4 {
            pending.stop = true;
        } else {
            pending
                .controls
                .push_back(Control::End(self.seq, cancel, time_ms));
        }
        self.box_.1.notify_one();
    }
}
impl Drop for Shell {
    fn drop(&mut self) {
        self.box_.0.lock().unwrap().stop = true;
        self.box_.1.notify_one();
        if let Some(worker) = self.worker.take() {
            let _ = worker.join();
        }
    }
}
fn read_deadline(stream: &mut UnixStream, buf: &mut [u8], deadline: Instant) -> io::Result<()> {
    let mut offset = 0;
    while offset < buf.len() {
        let left = deadline.saturating_duration_since(Instant::now());
        if left.is_zero() {
            return Err(io::Error::new(
                io::ErrorKind::TimedOut,
                "Sway reply deadline",
            ));
        }
        stream.set_read_timeout(Some(left))?;
        let n = stream.read(&mut buf[offset..])?;
        if n == 0 {
            return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "Sway closed"));
        }
        offset += n;
    }
    Ok(())
}
fn command(stream: &mut UnixStream, text: &str) -> io::Result<bool> {
    let timeout = if text.starts_with("card_shell trackpad begin ") {
        TIMEOUT
    } else {
        STREAM_TIMEOUT
    };
    let deadline = Instant::now() + timeout;
    stream.set_write_timeout(Some(timeout))?;
    let mut frame = b"i3-ipc".to_vec();
    frame.extend((text.len() as u32).to_ne_bytes());
    frame.extend(0u32.to_ne_bytes());
    frame.extend(text.as_bytes());
    stream.write_all(&frame)?;
    let mut header = [0u8; 14];
    read_deadline(stream, &mut header, deadline)?;
    if &header[..6] != b"i3-ipc" || header[10..14] != 0u32.to_ne_bytes() {
        return Err(io::Error::other("Unexpected Sway IPC reply"));
    }
    let length = u32::from_ne_bytes(header[6..10].try_into().unwrap()) as usize;
    if length > MAX_REPLY {
        return Err(io::Error::other("Oversized Sway reply"));
    }
    let mut reply = vec![0u8; length];
    read_deadline(stream, &mut reply, deadline)?;
    // Only fixed, single typed commands are issued, on the private Sway
    // socket. Accept the one success boolean; never execute reply contents.
    let compact: Vec<u8> = reply
        .into_iter()
        .filter(|b| !b.is_ascii_whitespace())
        .collect();
    Ok(compact.starts_with(b"[{\"success\":true")
        && !compact.windows(15).any(|s| s == b"\"success\":false"))
}
fn connect(path: &PathBuf) -> io::Result<UnixStream> {
    let meta = std::fs::symlink_metadata(path)?;
    let parent = path
        .parent()
        .and_then(|p| std::fs::symlink_metadata(p).ok());
    let protected_parent = parent
        .is_some_and(|p| p.file_type().is_dir() && p.mode() & 0o077 == 0 && p.uid() == meta.uid());
    if !path.is_absolute()
        || !meta.file_type().is_socket()
        || (meta.mode() & 0o077 != 0 && !protected_parent)
    {
        return Err(io::Error::other(
            "Shell socket must be private and absolute",
        ));
    }
    use std::os::unix::{ffi::OsStrExt, io::FromRawFd};
    let bytes = path.as_os_str().as_bytes();
    let mut address: libc::sockaddr_un = unsafe { std::mem::zeroed() };
    address.sun_family = libc::AF_UNIX as libc::sa_family_t;
    if bytes.len() >= address.sun_path.len() {
        return Err(io::Error::other("Shell socket path too long"));
    }
    for (out, byte) in address.sun_path.iter_mut().zip(bytes) {
        *out = *byte as libc::c_char;
    }
    let fd = unsafe {
        libc::socket(
            libc::AF_UNIX,
            libc::SOCK_STREAM | libc::SOCK_NONBLOCK | libc::SOCK_CLOEXEC,
            0,
        )
    };
    if fd < 0 {
        return Err(io::Error::last_os_error());
    }
    let stream = unsafe { UnixStream::from_raw_fd(fd) };
    let connected = unsafe {
        libc::connect(
            fd,
            &address as *const _ as *const libc::sockaddr,
            (std::mem::offset_of!(libc::sockaddr_un, sun_path) + bytes.len() + 1)
                as libc::socklen_t,
        )
    };
    if connected < 0 {
        let error = io::Error::last_os_error();
        if error.raw_os_error() != Some(libc::EINPROGRESS) {
            return Err(error);
        }
        let mut ready = libc::pollfd {
            fd,
            events: libc::POLLOUT,
            revents: 0,
        };
        if unsafe { libc::poll(&mut ready, 1, TIMEOUT.as_millis() as i32) } <= 0 {
            return Err(io::Error::new(
                io::ErrorKind::TimedOut,
                "Shell connect deadline",
            ));
        }
        if let Some(error) = stream.take_error()? {
            return Err(error);
        }
    }
    stream.set_nonblocking(false)?;
    Ok(stream)
}
fn move_command(seq: u64, point: Point) -> String {
    format!(
        "card_shell trackpad move {seq} {:.6} {:.6} {}",
        point.0, point.1, point.2
    )
}
fn checked_command(stream: &mut UnixStream, text: &str) -> io::Result<bool> {
    let result = command(stream, text);
    if matches!(result, Ok(false)) && !text.starts_with("card_shell trackpad begin ") {
        eprintln!(
            "k230-touch-trackpad: shell IPC phase={} error=Rejected",
            text.split_whitespace().nth(2).unwrap_or("unknown")
        );
    }
    if let Err(error) = &result {
        eprintln!(
            "k230-touch-trackpad: shell IPC phase={} error={:?}",
            text.split_whitespace().nth(2).unwrap_or("unknown"),
            error.kind()
        );
    }
    result
}
fn run(path: PathBuf, box_: Mailbox) {
    let mut socket: Option<UnixStream> = None;
    let mut active = 0u64;
    let mut last: Point = (0.0, 0.0, 0);
    loop {
        let mut pending = box_.0.lock().unwrap();
        if pending.controls.is_empty() && pending.latest.is_none() && !pending.stop {
            pending = box_.1.wait_timeout(pending, HEARTBEAT).unwrap().0;
        }
        if pending.stop {
            drop(pending);
            if active != 0 {
                if let Some(s) = socket.as_mut() {
                    let _ = checked_command(
                        s,
                        &format!(
                            "card_shell trackpad cancel {active} {}",
                            monotonic_ms() as u32
                        ),
                    );
                }
            }
            break;
        }
        let control = pending.controls.pop_front();
        let latest = pending.latest.take();
        drop(pending);
        // Consume the final point before its terminal event, even when
        // intermediate updates were coalesced by a busy compositor.
        if active != 0 {
            if let Some((seq, point)) = latest.filter(|(seq, _)| *seq == active) {
                last = point;
                if !socket
                    .as_mut()
                    .is_some_and(|s| checked_command(s, &move_command(seq, point)).unwrap_or(false))
                {
                    socket = None;
                    active = 0;
                }
            } else if control.is_none() {
                last.2 = monotonic_ms() as u32;
                if !socket.as_mut().is_some_and(|s| {
                    checked_command(s, &move_command(active, last)).unwrap_or(false)
                }) {
                    socket = None;
                    active = 0;
                }
            }
        }
        match control {
            Some(Control::Begin(seq, begin, ack)) => {
                if socket.is_none() {
                    socket = connect(&path).ok();
                }
                let accepted = socket.as_mut().is_some_and(|s| {
                    checked_command(
                        s,
                        &format!(
                            "card_shell trackpad begin {seq} {} {:.6} {:.6} {:.6} {:.6} {}",
                            begin.fingers, begin.x, begin.y, begin.dx, begin.dy, begin.start_ms
                        ),
                    )
                    .unwrap_or(false)
                });
                if accepted {
                    active = seq;
                    last = (0.0, 0.0, monotonic_ms() as u32);
                } else {
                    socket = None;
                    active = 0;
                }
                if ack.send(accepted).is_err() && accepted {
                    if let Some(s) = socket.as_mut() {
                        let _ = checked_command(
                            s,
                            &format!("card_shell trackpad cancel {seq} {}", monotonic_ms() as u32),
                        );
                    }
                    active = 0;
                }
            }
            Some(Control::End(seq, cancel, time)) if seq == active => {
                if let Some(s) = socket.as_mut() {
                    if checked_command(
                        s,
                        &format!(
                            "card_shell trackpad {} {seq} {time}",
                            if cancel { "cancel" } else { "end" }
                        ),
                    )
                    .is_err()
                    {
                        socket = None;
                    }
                }
                active = 0;
            }
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn protected_runtime_socket_keeps_final_motion_before_lift() {
        use std::os::unix::{fs::PermissionsExt, net::UnixListener};
        let path = std::env::temp_dir().join(format!(
            "k230-trackpad-ipc-{}-{}",
            std::process::id(),
            monotonic_ms()
        ));
        std::fs::create_dir(&path).unwrap();
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).unwrap();
        let socket = path.join("sway.sock");
        let listener = UnixListener::bind(&socket).unwrap();
        // The actual Sway socket is 0755 within an owned 0700 runtime.
        std::fs::set_permissions(&socket, std::fs::Permissions::from_mode(0o755)).unwrap();
        let (tx, rx) = mpsc::sync_channel(1);
        let controller = std::thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(2)))
                .unwrap();
            let mut commands = Vec::new();
            loop {
                let mut head = [0; 14];
                stream.read_exact(&mut head).unwrap();
                let length = u32::from_ne_bytes(head[6..10].try_into().unwrap()) as usize;
                let mut body = vec![0; length];
                stream.read_exact(&mut body).unwrap();
                let command = String::from_utf8(body).unwrap();
                let end = command.starts_with("card_shell trackpad end ");
                commands.push(command);
                let reply = b"[{\"success\":true}]";
                let mut frame = b"i3-ipc".to_vec();
                frame.extend((reply.len() as u32).to_ne_bytes());
                frame.extend(0u32.to_ne_bytes());
                frame.extend(reply);
                stream.write_all(&frame).unwrap();
                if end && commands.iter().filter(|c| c.contains(" end ")).count() == 2 {
                    tx.send(commands).unwrap();
                    break;
                }
            }
        });
        let mut shell = Shell::new(socket);
        assert!(shell.begin(Begin {
            fingers: 2,
            start_ms: monotonic_ms() as u32,
            time_ms: monotonic_ms() as u32,
            x: 0.5,
            y: 0.98,
            dx: 0.,
            dy: -0.02
        }));
        for i in 0..100 {
            shell.motion(i as f64 / 200.0, -i as f64 / 200.0, monotonic_ms() as u32);
        }
        shell.end(false, monotonic_ms() as u32);
        std::thread::sleep(Duration::from_millis(30));
        // Simulate an old epoch after recovery by a separate controller.
        // The next on-wire begin must still be newer than the first.
        shell.seq = 1;
        assert!(shell.begin(Begin {
            fingers: 2,
            start_ms: monotonic_ms() as u32,
            time_ms: monotonic_ms() as u32,
            x: 0.5,
            y: 0.98,
            dx: 0.,
            dy: -0.02
        }));
        shell.motion(0.495, -0.495, monotonic_ms() as u32);
        shell.end(false, monotonic_ms() as u32);
        let commands = rx.recv_timeout(Duration::from_secs(2)).unwrap();
        assert!(commands[0].contains(" begin "));
        let begins: Vec<u64> = commands
            .iter()
            .filter(|c| c.contains(" begin "))
            .map(|c| c.split_whitespace().nth(3).unwrap().parse().unwrap())
            .collect();
        assert!(begins[1] > begins[0]);
        assert!(commands[commands.len() - 2].contains("0.495000 -0.495000"));
        assert!(commands.last().unwrap().contains(" end "));
        drop(shell);
        controller.join().unwrap();
        std::fs::remove_dir_all(path).unwrap();
    }

    #[test]
    fn fragmented_reply_is_bounded_and_success_is_explicit() {
        for reply in [
            b"[{\"success\":true}]".as_slice(),
            b"[{\"success\":false}]".as_slice(),
        ] {
            let (mut a, mut b) = UnixStream::pair().unwrap();
            let reply = reply.to_vec();
            let good = reply.windows(4).any(|s| s == b"true");
            let thread = std::thread::spawn(move || {
                let mut head = [0; 14];
                b.read_exact(&mut head).unwrap();
                let n = u32::from_ne_bytes(head[6..10].try_into().unwrap()) as usize;
                let mut text = vec![0; n];
                b.read_exact(&mut text).unwrap();
                let mut response = b"i3-ipc".to_vec();
                response.extend((reply.len() as u32).to_ne_bytes());
                response.extend(0u32.to_ne_bytes());
                response.extend(reply);
                for byte in response {
                    b.write_all(&[byte]).unwrap();
                }
            });
            assert_eq!(
                command(&mut a, "card_shell trackpad begin 1 2 0.5 0.02 0 0.02").unwrap(),
                good
            );
            thread.join().unwrap();
        }
    }
    #[test]
    fn nonresponsive_controller_does_not_block_forever() {
        let (mut a, _b) = UnixStream::pair().unwrap();
        let start = Instant::now();
        assert!(command(&mut a, "card_shell trackpad begin 1 2 0.5 0.02 0 0.02").is_err());
        assert!(start.elapsed() < Duration::from_millis(350));
        let (mut a, _b) = UnixStream::pair().unwrap();
        let start = Instant::now();
        assert!(command(&mut a, "card_shell trackpad end 1 100").is_err());
        assert!(start.elapsed() < Duration::from_millis(850));
    }
    #[test]
    fn asynchronous_release_survives_a_slow_frame() {
        let (mut a, mut b) = UnixStream::pair().unwrap();
        let controller = std::thread::spawn(move || {
            let mut header = [0; 14];
            b.read_exact(&mut header).unwrap();
            let mut body = vec![0; u32::from_ne_bytes(header[6..10].try_into().unwrap()) as usize];
            b.read_exact(&mut body).unwrap();
            assert!(body.starts_with(b"card_shell trackpad end "));
            std::thread::sleep(Duration::from_millis(300));
            let reply = b"[{\"success\":true}]";
            let mut frame = b"i3-ipc".to_vec();
            frame.extend((reply.len() as u32).to_ne_bytes());
            frame.extend(0u32.to_ne_bytes());
            frame.extend(reply);
            b.write_all(&frame).unwrap();
        });
        assert!(command(&mut a, "card_shell trackpad end 1 100").unwrap());
        controller.join().unwrap();
    }
    #[test]
    fn missing_shell_falls_back_without_leaking_a_worker() {
        let mut shell = Shell::new(PathBuf::from("/nonexistent/k230-sway.sock"));
        assert!(!shell.begin(Begin {
            fingers: 2,
            start_ms: monotonic_ms() as u32,
            time_ms: monotonic_ms() as u32,
            x: 0.5,
            y: 0.02,
            dx: 0.,
            dy: 0.02
        }));
        shell.motion(0.0, 0.5, monotonic_ms() as u32);
        shell.end(false, monotonic_ms() as u32);
    }
}

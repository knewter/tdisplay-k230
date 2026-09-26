//! A minimal, read-mostly sway IPC client: just enough to subscribe to
//! `window` events and decode them. This client had no sway-IPC code at
//! all before the launch splash (`main.rs`'s existing `running_con_id`/
//! `focus_con`/`swaymsg_back` all shell out to the `swaymsg` binary
//! instead) -- there is no `swayipc` crate dependency to reuse, and the
//! wire format is small enough that hand-rolling it is cheaper than a new
//! dependency. The framing here mirrors `tests/card_shell_runtime.py`'s own
//! `ipc()` helper byte for byte (`i3-ipc` magic, then a native-endian
//! `u32` length and `u32` type, matching `sway-ipc(7)`'s documented
//! "32-bit integer in native byte order"), so this is proven-compatible
//! wire format, not a guess.
use std::{
    io::{self, Read, Write},
    os::unix::net::UnixStream,
    path::Path,
    time::Duration,
};

const MAGIC: &[u8; 6] = b"i3-ipc";
const HEADER_LEN: usize = 14;
/// Bounds a single message's payload. A `window` event's single-container
/// payload never approaches this; matches the existing `running_con_id`'s
/// own `2 * 1024 * 1024` bound on a (much larger) `get_tree` reply.
const MAX_PAYLOAD: usize = 2 * 1024 * 1024;

pub const MESSAGE_SUBSCRIBE: u32 = 2;
/// `sway-ipc(7)`, "0x80000003. WINDOW": the event's own type byte carries
/// the same 3 the plain `SUBSCRIBE` payload names, with the high bit set
/// to mark it as a push rather than a reply.
pub const EVENT_WINDOW: u32 = 0x8000_0003;

/// Writes one framed i3-ipc message. Exposed mainly for the round-trip
/// test below; production use is entirely inside `watch_window_events`.
pub fn write_message(stream: &mut impl Write, message_type: u32, payload: &[u8]) -> io::Result<()> {
    let mut header = Vec::with_capacity(HEADER_LEN + payload.len());
    header.extend_from_slice(MAGIC);
    header.extend_from_slice(&(payload.len() as u32).to_ne_bytes());
    header.extend_from_slice(&message_type.to_ne_bytes());
    header.extend_from_slice(payload);
    stream.write_all(&header)
}

/// Parses one complete frame from the *front* of `buffer` without
/// consuming it -- the caller drains `consumed` bytes on `Some`. Returns
/// `Ok(None)` when `buffer` does not yet hold a whole frame (the normal
/// case immediately after a short socket read), so this never has to
/// assume a single `read()` call delivers a whole message -- a real risk
/// on a busy single-core board, and the reason this is a length-prefixed
/// buffer parser rather than a chain of `read_exact` calls against the
/// socket directly (a `read_exact` that times out partway through a
/// message would desynchronize the framing for good).
pub fn try_parse_frame(buffer: &[u8]) -> Result<Option<(usize, u32, Vec<u8>)>, String> {
    if buffer.len() < HEADER_LEN {
        return Ok(None);
    }
    if &buffer[..6] != MAGIC {
        return Err("bad i3-ipc magic".into());
    }
    let length = u32::from_ne_bytes(buffer[6..10].try_into().map_err(|_| "short length field")?) as usize;
    if length > MAX_PAYLOAD {
        return Err(format!("oversized i3-ipc payload ({length} bytes)"));
    }
    let message_type = u32::from_ne_bytes(buffer[10..14].try_into().map_err(|_| "short type field")?);
    let total = HEADER_LEN + length;
    if buffer.len() < total {
        return Ok(None);
    }
    Ok(Some((total, message_type, buffer[HEADER_LEN..total].to_vec())))
}

/// One `window` event's fields this client actually needs. Every other
/// property `sway-ipc(7)` documents for the event (title, `container`'s
/// full tree shape, etc.) is left unparsed.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WindowEvent {
    pub change: String,
    pub pid: Option<i32>,
}

pub fn parse_window_event(payload: &[u8]) -> Option<WindowEvent> {
    let value: serde_json::Value = serde_json::from_slice(payload).ok()?;
    let change = value.get("change")?.as_str()?.to_string();
    let pid = value
        .get("container")
        .and_then(|container| container.get("pid"))
        .and_then(serde_json::Value::as_i64)
        .and_then(|pid| i32::try_from(pid).ok());
    Some(WindowEvent { change, pid })
}

/// Connects to `socket_path`, subscribes to `window` events, and calls
/// `on_event` for each one until it returns `true` (a match was found),
/// `should_stop` returns `true` (the splash was dismissed or superseded
/// some other way), or the connection ends. The read timeout is what
/// makes `should_stop` actually get polled instead of blocking forever on
/// a launch whose splash has already timed out with no more events ever
/// arriving.
pub fn watch_window_events(
    socket_path: &Path,
    mut on_event: impl FnMut(&WindowEvent) -> bool,
    mut should_stop: impl FnMut() -> bool,
) -> io::Result<()> {
    let mut stream = UnixStream::connect(socket_path)?;
    stream.set_read_timeout(Some(Duration::from_millis(200)))?;
    write_message(&mut stream, MESSAGE_SUBSCRIBE, br#"["window"]"#)?;
    let mut buffer = Vec::new();
    let mut chunk = [0u8; 4096];
    loop {
        loop {
            match try_parse_frame(&buffer) {
                Ok(Some((consumed, message_type, message_payload))) => {
                    buffer.drain(..consumed);
                    if message_type == EVENT_WINDOW {
                        if let Some(event) = parse_window_event(&message_payload) {
                            if on_event(&event) {
                                return Ok(());
                            }
                        }
                    }
                }
                Ok(None) => break,
                Err(reason) => return Err(io::Error::new(io::ErrorKind::InvalidData, reason)),
            }
        }
        if should_stop() {
            return Ok(());
        }
        match stream.read(&mut chunk) {
            Ok(0) => return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "sway ipc closed")),
            Ok(n) => buffer.extend_from_slice(&chunk[..n]),
            Err(error)
                if matches!(error.kind(), io::ErrorKind::WouldBlock | io::ErrorKind::TimedOut) => {}
            Err(error) => return Err(error),
        }
    }
}

/// The parent pid of `pid`, read fresh from `/proc/<pid>/stat`. The comm
/// field (`(...)`) can itself contain spaces or closing parens, so this
/// finds the *last* `)` rather than splitting naively on whitespace --
/// the same care `man 5 proc` calls out for parsing this file.
pub fn parent_pid(pid: i32) -> Option<i32> {
    let content = std::fs::read_to_string(format!("/proc/{pid}/stat")).ok()?;
    let close = content.rfind(')')?;
    let rest = content.get(close + 2..)?;
    let mut fields = rest.split_whitespace();
    let _state = fields.next()?;
    fields.next()?.parse::<i32>().ok()
}

/// Whether `pid` still names a running process. Used to detect "the
/// process exited before any window mapped" without needing a `window`
/// `close` event (which sway would never send for a process that spawned
/// no window at all).
pub fn process_alive(pid: i32) -> bool {
    Path::new(&format!("/proc/{pid}")).exists()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::net::UnixListener;

    #[test]
    fn try_parse_frame_waits_for_a_complete_header_then_payload() {
        let mut message = Vec::new();
        message.extend_from_slice(MAGIC);
        message.extend_from_slice(&5u32.to_ne_bytes());
        message.extend_from_slice(&EVENT_WINDOW.to_ne_bytes());
        message.extend_from_slice(b"hello");
        // Not even a full header yet.
        assert_eq!(try_parse_frame(&message[..10]).unwrap(), None);
        // Full header, payload still short.
        assert_eq!(try_parse_frame(&message[..14]).unwrap(), None);
        assert_eq!(try_parse_frame(&message[..17]).unwrap(), None);
        // Complete frame, with a trailing byte from the next message left
        // in place -- `consumed` must name exactly this frame's length.
        let mut with_trailer = message.clone();
        with_trailer.push(b'X');
        let (consumed, message_type, payload) = try_parse_frame(&with_trailer).unwrap().unwrap();
        assert_eq!(consumed, message.len());
        assert_eq!(message_type, EVENT_WINDOW);
        assert_eq!(payload, b"hello");
    }

    #[test]
    fn try_parse_frame_rejects_bad_magic_and_oversized_length() {
        assert!(try_parse_frame(b"xxxxxx\x00\x00\x00\x00\x00\x00\x00\x00").is_err());
        let mut oversized = Vec::new();
        oversized.extend_from_slice(MAGIC);
        oversized.extend_from_slice(&(MAX_PAYLOAD as u32 + 1).to_ne_bytes());
        oversized.extend_from_slice(&0u32.to_ne_bytes());
        assert!(try_parse_frame(&oversized).is_err());
    }

    #[test]
    fn parse_window_event_reads_change_and_container_pid() {
        let payload = br#"{"change":"new","container":{"pid":4242,"app_id":"foot"}}"#;
        let event = parse_window_event(payload).unwrap();
        assert_eq!(event.change, "new");
        assert_eq!(event.pid, Some(4242));

        let no_pid = br#"{"change":"close","container":{"app_id":"foot"}}"#;
        let event = parse_window_event(no_pid).unwrap();
        assert_eq!(event.change, "close");
        assert_eq!(event.pid, None);

        assert!(parse_window_event(b"not json").is_none());
    }

    #[test]
    fn write_message_produces_the_documented_header_layout() {
        let mut buffer = Vec::new();
        write_message(&mut buffer, MESSAGE_SUBSCRIBE, br#"["window"]"#).unwrap();
        assert_eq!(&buffer[..6], MAGIC);
        assert_eq!(
            u32::from_ne_bytes(buffer[6..10].try_into().unwrap()),
            10 // br#"["window"]"# is 10 bytes
        );
        assert_eq!(
            u32::from_ne_bytes(buffer[10..14].try_into().unwrap()),
            MESSAGE_SUBSCRIBE
        );
        assert_eq!(&buffer[14..], br#"["window"]"#);
    }

    /// A real, local Unix-socket round trip: a fake "sway" that accepts one
    /// connection, replies to SUBSCRIBE, then pushes one `window new` event
    /// with a pid -- proving `watch_window_events` actually parses a frame
    /// delivered over a real socket, not just an in-memory buffer.
    #[test]
    fn watch_window_events_matches_a_pid_delivered_over_a_real_socket() {
        let dir = std::env::temp_dir().join(format!(
            "k230-sway-ipc-test-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let socket_path = dir.join("sway-ipc.sock");
        let listener = UnixListener::bind(&socket_path).unwrap();
        let server = std::thread::spawn({
            let socket_path = socket_path.clone();
            move || {
                let _ = &socket_path;
                let (mut stream, _) = listener.accept().unwrap();
                // Drain the SUBSCRIBE request.
                let mut buffer = [0u8; 256];
                let _ = stream.read(&mut buffer);
                // Reply to SUBSCRIBE (type 2), then push a matching event.
                write_message(&mut stream, MESSAGE_SUBSCRIBE, br#"{"success":true}"#).unwrap();
                let event = br#"{"change":"new","container":{"pid":777}}"#;
                write_message(&mut stream, EVENT_WINDOW, event).unwrap();
                // Keep the connection open briefly so a slow reader still
                // sees the event before EOF would otherwise end the watch.
                std::thread::sleep(Duration::from_millis(200));
            }
        });
        let mut seen = None;
        watch_window_events(
            &socket_path,
            |event| {
                seen = Some(event.clone());
                true
            },
            || false,
        )
        .unwrap();
        server.join().unwrap();
        assert_eq!(
            seen,
            Some(WindowEvent {
                change: "new".into(),
                pid: Some(777),
            })
        );
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn process_alive_reflects_the_current_process_and_a_bogus_pid() {
        assert!(process_alive(std::process::id() as i32));
        assert!(!process_alive(i32::MAX));
    }

    #[test]
    fn parent_pid_of_self_matches_libc_getppid() {
        let expected = unsafe { libc::getppid() };
        assert_eq!(parent_pid(std::process::id() as i32), Some(expected));
    }
}

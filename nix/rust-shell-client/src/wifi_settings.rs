//! Bounded Wi-Fi Settings client. Only the root broker touches the radio or
//! persistent credential; this worker keeps socket I/O off the Wayland loop.
use serde_json::{json, Value};
use std::{
    fs,
    io::{Read, Write},
    os::{
        fd::{AsRawFd, FromRawFd},
        unix::{
            ffi::OsStrExt,
            fs::{FileTypeExt, MetadataExt, PermissionsExt},
            net::UnixStream,
        },
    },
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicU64, Ordering},
        mpsc::{self, Receiver, SyncSender, TrySendError},
        Arc,
    },
    thread,
    time::{Duration, Instant},
};

const REQUEST_LIMIT: usize = 4096;
const RESPONSE_LIMIT: usize = 16384;
const SCAN_LIMIT: usize = 48;
const SAVED_LIMIT: usize = 8;
const DEADLINE: Duration = Duration::from_secs(29);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Security {
    Open,
    Wpa2Psk,
    Unsupported,
}

impl Security {
    fn parse(value: &Value) -> Result<Self, String> {
        match value.as_str() {
            Some("open") => Ok(Self::Open),
            Some("wpa2-psk") => Ok(Self::Wpa2Psk),
            Some("unsupported") => Ok(Self::Unsupported),
            _ => Err("invalid Wi-Fi security".into()),
        }
    }
    fn protocol(self) -> &'static str {
        match self {
            Self::Open => "open",
            Self::Wpa2Psk => "wpa2-psk",
            Self::Unsupported => "unsupported",
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Network {
    pub ssid: String,
    pub security: Security,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Snapshot {
    pub networks: Vec<Network>,
    pub current: Option<String>,
    pub saved: Vec<Network>,
    pub error: Option<String>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum WifiResult {
    Snapshot(Snapshot),
    Saved,
    Selected,
    Forgotten,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Kind {
    Status,
    Scan,
    Connect,
    ConnectSaved,
    Forget,
}

/// Deliberately has no Debug/Clone: a credential must not be formatted into
/// shell logs or retained by request retries.
pub enum WifiRequest {
    Status,
    Scan,
    Connect {
        ssid: String,
        security: Security,
        password: Secret,
    },
    ConnectSaved {
        ssid: String,
    },
    Forget {
        ssid: String,
    },
}
impl WifiRequest {
    pub fn kind(&self) -> Kind {
        match self {
            Self::Status => Kind::Status,
            Self::Scan => Kind::Scan,
            Self::Connect { .. } => Kind::Connect,
            Self::ConnectSaved { .. } => Kind::ConnectSaved,
            Self::Forget { .. } => Kind::Forget,
        }
    }
}

pub struct Secret(String);
impl Secret {
    pub fn new(value: String) -> Self {
        Self(value)
    }
    pub fn len(&self) -> usize {
        self.0.len()
    }
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }
    pub fn push(&mut self, c: char) {
        if self.0.len() < 63 && c.is_ascii() && !c.is_control() {
            self.0.push(c);
        }
    }
    pub fn pop(&mut self) {
        self.0.pop();
    }
    pub(crate) fn as_str(&self) -> &str {
        &self.0
    }
}
impl Drop for Secret {
    fn drop(&mut self) {
        // ASCII-only Wi-Fi passphrases make a byte overwrite valid UTF-8.
        unsafe {
            self.0.as_bytes_mut().fill(0);
        }
    }
}

struct PrivatePayload(Vec<u8>);
impl Drop for PrivatePayload {
    fn drop(&mut self) {
        // Minimize lifetime of the serialized password on every exit path.
        self.0.fill(0);
    }
}

pub struct WifiReply {
    pub id: u64,
    pub kind: Kind,
    pub result: Result<WifiResult, String>,
}

pub struct WifiWorker {
    requests: SyncSender<(u64, WifiRequest)>,
    replies: Receiver<WifiReply>,
    next_id: u64,
    cancelled: Arc<AtomicU64>,
}

impl WifiWorker {
    pub fn spawn(socket: PathBuf) -> Self {
        let (requests, incoming) = mpsc::sync_channel::<(u64, WifiRequest)>(4);
        let (outgoing, replies) = mpsc::sync_channel(4);
        let cancelled = Arc::new(AtomicU64::new(0));
        let worker_cancelled = Arc::clone(&cancelled);
        thread::spawn(move || {
            while let Ok((id, request)) = incoming.recv() {
                let kind = request.kind();
                let result = execute(&socket, request, id, &worker_cancelled);
                if outgoing.send(WifiReply { id, kind, result }).is_err() {
                    break;
                }
            }
        });
        Self {
            requests,
            replies,
            next_id: 1,
            cancelled,
        }
    }
    pub fn try_submit(&mut self, request: WifiRequest) -> Result<u64, &'static str> {
        let id = self.next_id;
        self.next_id = self
            .next_id
            .checked_add(1)
            .ok_or("Wi-Fi request IDs exhausted")?;
        match self.requests.try_send((id, request)) {
            Ok(()) => Ok(id),
            Err(TrySendError::Full(_)) => Err("Wi-Fi is busy"),
            Err(TrySendError::Disconnected(_)) => Err("Wi-Fi service unavailable"),
        }
    }
    pub fn cancel(&self, id: u64) {
        self.cancelled.fetch_max(id, Ordering::AcqRel);
    }
    pub fn try_recv(&self) -> Option<WifiReply> {
        self.replies.try_recv().ok()
    }
}

fn name(value: &Value) -> Result<String, String> {
    let s = value.as_str().ok_or("invalid network")?;
    if s.is_empty() || s.len() > 32 || s.chars().any(char::is_control) {
        return Err("invalid network".into());
    }
    Ok(s.into())
}
fn network(value: &Value) -> Result<Network, String> {
    Ok(Network {
        ssid: name(value.get("ssid").ok_or("missing network")?)?,
        security: Security::parse(value.get("security").ok_or("missing security")?)?,
    })
}
fn error_code(value: &Value) -> Result<Option<String>, String> {
    match value {
        Value::Null => Ok(None),
        Value::String(code)
            if matches!(
                code.as_str(),
                "radio-unavailable"
                    | "radio-timeout"
                    | "authentication-failed"
                    | "connection-timeout"
                    | "scan-too-soon"
                    | "scan-too-large"
                    | "link-too-large"
                    | "unsupported-saved-config"
                    | "unsupported-security"
                    | "saved-limit"
                    | "unsafe-credential"
                    | "unsafe-runtime"
                    | "service-unavailable"
                    | "service-restart-failed"
                    | "forget-failed"
                    | "save-failed"
                    | "not-saved"
                    | "invalid-network"
                    | "invalid-password"
                    | "invalid-request"
                    | "request-too-large"
                    | "response-too-large"
                    | "unknown-operation"
                    | "denied"
                    | "cancelled"
            ) =>
        {
            Ok(Some(code.clone()))
        }
        _ => Err("invalid Wi-Fi error".into()),
    }
}
pub fn parse_response(bytes: &[u8], kind: Kind) -> Result<WifiResult, String> {
    if bytes.len() > RESPONSE_LIMIT {
        return Err("Wi-Fi response too large".into());
    }
    let value: Value = serde_json::from_slice(bytes).map_err(|_| "invalid Wi-Fi response")?;
    if value.get("schema").and_then(Value::as_u64) != Some(1) {
        return Err("unsupported Wi-Fi response".into());
    }
    if value.get("state").and_then(Value::as_str) == Some("failed") {
        return Err(
            error_code(value.get("error").ok_or("missing Wi-Fi error")?)?
                .ok_or("missing Wi-Fi error")?,
        );
    }
    if value.get("state").and_then(Value::as_str) != Some("ok") {
        return Err("invalid Wi-Fi response state".into());
    }
    match kind {
        Kind::Status | Kind::Scan => {
            let current = value.get("current").ok_or("missing current network")?;
            let current = if current.is_null() {
                None
            } else {
                Some(name(current)?)
            };
            let saved = value
                .get("saved")
                .and_then(Value::as_array)
                .ok_or("missing saved networks")?;
            if saved.len() > SAVED_LIMIT {
                return Err("too many saved networks".into());
            }
            let saved = saved.iter().map(network).collect::<Result<Vec<_>, _>>()?;
            let networks = if kind == Kind::Scan {
                let rows = value
                    .get("networks")
                    .and_then(Value::as_array)
                    .ok_or("missing scan rows")?;
                if rows.len() > SCAN_LIMIT {
                    return Err("too many scan rows".into());
                }
                rows.iter().map(network).collect::<Result<Vec<_>, _>>()?
            } else {
                Vec::new()
            };
            let error = error_code(value.get("error").ok_or("missing radio state")?)?;
            Ok(WifiResult::Snapshot(Snapshot {
                networks,
                current,
                saved,
                error,
            }))
        }
        Kind::Connect if value.get("result").and_then(Value::as_str) == Some("saved") => {
            name(value.get("ssid").ok_or("missing saved network")?)?;
            Ok(WifiResult::Saved)
        }
        Kind::ConnectSaved if value.get("result").and_then(Value::as_str) == Some("selected") => {
            name(value.get("ssid").ok_or("missing selected network")?)?;
            Ok(WifiResult::Selected)
        }
        Kind::Forget if value.get("result").and_then(Value::as_str) == Some("forgotten") => {
            Ok(WifiResult::Forgotten)
        }
        _ => Err("unexpected Wi-Fi outcome".into()),
    }
}

fn valid_request(request: &WifiRequest) -> Result<Value, String> {
    Ok(match request {
        WifiRequest::Status => json!({"schema":1,"op":"status"}),
        WifiRequest::Scan => json!({"schema":1,"op":"scan"}),
        WifiRequest::Forget { ssid } => {
            name(&Value::String(ssid.clone()))?;
            json!({"schema":1,"op":"forget","ssid":ssid})
        }
        WifiRequest::ConnectSaved { ssid } => {
            name(&Value::String(ssid.clone()))?;
            json!({"schema":1,"op":"connect-saved","ssid":ssid})
        }
        WifiRequest::Connect {
            ssid,
            security,
            password,
        } => {
            name(&Value::String(ssid.clone()))?;
            match security {
                Security::Open if password.is_empty() => {}
                Security::Wpa2Psk if (8..=63).contains(&password.len()) => {}
                _ => return Err("unsupported Wi-Fi connection".into()),
            }
            json!({"schema":1,"op":"connect","ssid":ssid,
                   "security":security.protocol(),"password":password.as_str()})
        }
    })
}

fn socket_identity(path: &Path, expected_uid: u32, expected_gid: u32) -> Result<(), String> {
    let parent = path.parent().ok_or("invalid Wi-Fi socket path")?;
    let dir = fs::symlink_metadata(parent).map_err(|_| "Wi-Fi service unavailable")?;
    let socket = fs::symlink_metadata(path).map_err(|_| "Wi-Fi service unavailable")?;
    if !dir.is_dir()
        || dir.uid() != expected_uid
        || dir.gid() != expected_gid
        || dir.permissions().mode() & 0o007 != 0
        || !socket.file_type().is_socket()
        || socket.uid() != expected_uid
        || socket.gid() != expected_gid
        || socket.permissions().mode() & 0o007 != 0
    {
        return Err("unsafe Wi-Fi socket".into());
    }
    Ok(())
}
fn poll_fd(fd: i32, events: i16, deadline: Instant) -> Result<(), String> {
    let remaining = deadline.saturating_duration_since(Instant::now());
    if remaining.is_zero() {
        return Err("Wi-Fi deadline exceeded".into());
    }
    let mut descriptor = libc::pollfd {
        fd,
        events,
        revents: 0,
    };
    let result = unsafe { libc::poll(&mut descriptor, 1, remaining.as_millis().min(250) as i32) };
    if result < 0 {
        return Err("Wi-Fi poll failed".into());
    }
    if descriptor.revents & (libc::POLLERR | libc::POLLNVAL) != 0 {
        return Err("Wi-Fi socket closed".into());
    }
    Ok(())
}
fn connect_nonblocking(path: &Path, deadline: Instant, uid: u32) -> Result<UnixStream, String> {
    let bytes = path.as_os_str().as_bytes();
    if bytes.len() >= 108 || bytes.contains(&0) {
        return Err("invalid Wi-Fi socket path".into());
    }
    let fd = unsafe {
        libc::socket(
            libc::AF_UNIX,
            libc::SOCK_STREAM | libc::SOCK_NONBLOCK | libc::SOCK_CLOEXEC,
            0,
        )
    };
    if fd < 0 {
        return Err("Wi-Fi socket unavailable".into());
    }
    let mut address: libc::sockaddr_un = unsafe { std::mem::zeroed() };
    address.sun_family = libc::AF_UNIX as libc::sa_family_t;
    for (index, byte) in bytes.iter().enumerate() {
        address.sun_path[index] = *byte as libc::c_char;
    }
    let length = (std::mem::size_of::<libc::sa_family_t>() + bytes.len() + 1) as libc::socklen_t;
    let status =
        unsafe { libc::connect(fd, (&address as *const libc::sockaddr_un).cast(), length) };
    let stream = unsafe { UnixStream::from_raw_fd(fd) };
    if status < 0 {
        if std::io::Error::last_os_error().raw_os_error() != Some(libc::EINPROGRESS) {
            return Err("Wi-Fi connect failed".into());
        }
        poll_fd(stream.as_raw_fd(), libc::POLLOUT, deadline)?;
        let mut error = 0i32;
        let mut size = std::mem::size_of::<i32>() as libc::socklen_t;
        if unsafe {
            libc::getsockopt(
                stream.as_raw_fd(),
                libc::SOL_SOCKET,
                libc::SO_ERROR,
                (&mut error as *mut i32).cast(),
                &mut size,
            )
        } < 0
            || error != 0
        {
            return Err("Wi-Fi connect failed".into());
        }
    }
    let mut peer: libc::ucred = unsafe { std::mem::zeroed() };
    let mut size = std::mem::size_of::<libc::ucred>() as libc::socklen_t;
    if unsafe {
        libc::getsockopt(
            stream.as_raw_fd(),
            libc::SOL_SOCKET,
            libc::SO_PEERCRED,
            (&mut peer as *mut libc::ucred).cast(),
            &mut size,
        )
    } < 0
        || peer.uid != uid
    {
        return Err("foreign Wi-Fi peer".into());
    }
    Ok(stream)
}
fn execute(
    path: &Path,
    request: WifiRequest,
    id: u64,
    cancelled: &AtomicU64,
) -> Result<WifiResult, String> {
    execute_identity(path, request, id, cancelled, 0, unsafe { libc::getegid() })
}

fn execute_identity(
    path: &Path,
    request: WifiRequest,
    id: u64,
    cancelled: &AtomicU64,
    uid: u32,
    gid: u32,
) -> Result<WifiResult, String> {
    let kind = request.kind();
    let mut payload = PrivatePayload({
        let value = valid_request(&request)?;
        serde_json::to_vec(&value).map_err(|_| "invalid Wi-Fi request")?
    });
    drop(request);
    payload.0.push(b'\n');
    if payload.0.len() > REQUEST_LIMIT {
        return Err("Wi-Fi request too large".into());
    }
    let deadline = Instant::now() + DEADLINE;
    socket_identity(path, uid, gid)?;
    let mut stream = connect_nonblocking(path, deadline, uid)?;
    let mut written = 0;
    while written < payload.0.len() {
        if cancelled.load(Ordering::Acquire) >= id {
            return Err("cancelled".into());
        }
        match stream.write(&payload.0[written..]) {
            Ok(0) => return Err("Wi-Fi write closed".into()),
            Ok(n) => written += n,
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                poll_fd(stream.as_raw_fd(), libc::POLLOUT, deadline)?
            }
            Err(_) => return Err("Wi-Fi write failed".into()),
        }
    }
    payload.0.fill(0);
    let mut response = Vec::new();
    loop {
        if cancelled.load(Ordering::Acquire) >= id {
            return Err("cancelled".into());
        }
        let mut chunk = [0u8; 2048];
        match stream.read(&mut chunk) {
            Ok(0) => return Err("Wi-Fi response closed".into()),
            Ok(n) => response.extend_from_slice(&chunk[..n]),
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                poll_fd(stream.as_raw_fd(), libc::POLLIN, deadline)?
            }
            Err(_) => return Err("Wi-Fi read failed".into()),
        }
        if response.len() > RESPONSE_LIMIT {
            return Err("Wi-Fi response too large".into());
        }
        if let Some(end) = response.iter().position(|byte| *byte == b'\n') {
            if end + 1 != response.len() {
                return Err("multiple Wi-Fi responses".into());
            }
            response.truncate(end);
            return parse_response(&response, kind);
        }
        if Instant::now() >= deadline {
            return Err("Wi-Fi deadline exceeded".into());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::net::UnixListener;
    #[test]
    fn parse_scan_and_saved_with_fake_names() {
        let bytes = br#"{"schema":1,"state":"ok","current":"Example Guest","saved":[{"ssid":"Example Guest","security":"open"}],"networks":[{"ssid":"Example Guest","security":"open"},{"ssid":"Example Secure","security":"wpa2-psk"}],"error":null}"#;
        let WifiResult::Snapshot(snapshot) = parse_response(bytes, Kind::Scan).unwrap() else {
            panic!()
        };
        assert_eq!(snapshot.networks.len(), 2);
        assert_eq!(snapshot.saved.len(), 1);
        assert_eq!(snapshot.current.as_deref(), Some("Example Guest"));
    }
    #[test]
    fn connect_ack_is_parsed_without_echoing_password() {
        let reply = br#"{"schema":1,"state":"ok","result":"saved","ssid":"Example Secure"}"#;
        assert_eq!(
            parse_response(reply, Kind::Connect).unwrap(),
            WifiResult::Saved
        );
        let failed = br#"{"schema":1,"state":"failed","error":"authentication-failed"}"#;
        assert_eq!(
            parse_response(failed, Kind::Connect).unwrap_err(),
            "authentication-failed"
        );
    }
    #[test]
    fn later_cancel_keeps_earlier_queued_request_cancelled() {
        let watermark = AtomicU64::new(0);
        watermark.fetch_max(7, Ordering::AcqRel);
        watermark.fetch_max(9, Ordering::AcqRel);
        assert!(watermark.load(Ordering::Acquire) >= 7);
        assert!(watermark.load(Ordering::Acquire) >= 9);
        assert!(watermark.load(Ordering::Acquire) < 10);
    }
    #[test]
    fn fake_broker_socket_carries_saved_selection_without_password() {
        let root = std::env::temp_dir().join(format!(
            "k230-wifi-fixture-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&root).unwrap();
        fs::set_permissions(&root, fs::Permissions::from_mode(0o700)).unwrap();
        let path = root.join("broker.sock");
        let listener = UnixListener::bind(&path).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o600)).unwrap();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut request = Vec::new();
            while !request.ends_with(b"\n") {
                let mut one = [0u8];
                stream.read_exact(&mut one).unwrap();
                request.push(one[0]);
                assert!(request.len() < REQUEST_LIMIT);
            }
            let value: Value = serde_json::from_slice(&request).unwrap();
            assert_eq!(value["op"], "connect-saved");
            assert_eq!(value["ssid"], "Example Secure");
            assert!(value.get("password").is_none());
            stream.write_all(b"{\"schema\":1,\"state\":\"ok\",\"result\":\"selected\",\"ssid\":\"Example Secure\"}\n").unwrap();
        });
        let result = execute_identity(
            &path,
            WifiRequest::ConnectSaved {
                ssid: "Example Secure".into(),
            },
            1,
            &AtomicU64::new(0),
            unsafe { libc::geteuid() },
            unsafe { libc::getegid() },
        );
        server.join().unwrap();
        assert_eq!(result.unwrap(), WifiResult::Selected);
        fs::remove_file(path).unwrap();
        let cancelled_path = root.join("cancel.sock");
        let listener = UnixListener::bind(&cancelled_path).unwrap();
        fs::set_permissions(&cancelled_path, fs::Permissions::from_mode(0o600)).unwrap();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut byte = [0u8];
            assert_eq!(stream.read(&mut byte).unwrap(), 0);
        });
        let watermark = AtomicU64::new(9); // later B cancelled after queued A
        let result = execute_identity(
            &cancelled_path,
            WifiRequest::ConnectSaved {
                ssid: "Example Secure".into(),
            },
            7,
            &watermark,
            unsafe { libc::geteuid() },
            unsafe { libc::getegid() },
        );
        assert_eq!(result.unwrap_err(), "cancelled");
        server.join().unwrap();
        fs::remove_file(cancelled_path).unwrap();
        fs::remove_dir(root).unwrap();
    }
    #[test]
    fn reject_oversized_untrusted_and_secret_leaks() {
        assert!(parse_response(&vec![b'x'; RESPONSE_LIMIT + 1], Kind::Scan).is_err());
        let bad = br#"{"schema":1,"state":"failed","error":"examplepass"}"#;
        assert!(parse_response(bad, Kind::Connect).is_err());
        let secret = Secret::new("examplepass".into());
        let request = WifiRequest::Connect {
            ssid: "Example Secure".into(),
            security: Security::Wpa2Psk,
            password: secret,
        };
        assert_eq!(request.kind(), Kind::Connect);
    }
}

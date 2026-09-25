//! Bounded asynchronous bridge to the installed, trusted `k230-theme` command.
//!
//! The UI never waits for theme preparation or endpoint acknowledgements on
//! the Wayland thread. A preview only stages immutable data; activation needs
//! the exact generation returned by preview. Opaque IDs are argv values, not
//! paths or shell text.

use serde_json::{json, Value};
use std::{
    collections::BTreeMap,
    io::{Read, Write},
    os::{
        fd::AsRawFd,
        unix::{net::UnixStream, process::CommandExt},
    },
    path::{Component, Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicU64, AtomicUsize, Ordering},
        mpsc::{self, Receiver, SyncSender, TryRecvError, TrySendError},
        Arc,
    },
    thread,
    time::{Duration, Instant},
};

const QUEUE: usize = 4;
const RESPONSE_LIMIT: usize = 1024 * 1024;
const ERROR_LIMIT: usize = 8 * 1024;
const MAX_THEMES: usize = 512;
const MAX_BACKGROUNDS: usize = 512;
const MAX_PALETTE: usize = 512;
const MAX_COMPATIBILITY: usize = 512;
const COMMAND_DEADLINE: Duration = Duration::from_secs(20);
/// Matches `tools/theme_client.py`'s own `DEFAULT_TIMEOUT_S` (raised from
/// 0.3 to 10.0 for the same reason: comfortably above the slowest
/// legitimate `theme-helper.service` reply -- see that module's own
/// comment -- so a working daemon is never abandoned mid-response for the
/// strictly worse subprocess fallback. This worker thread blocks on it, but
/// it is never the Wayland thread (see this module's own doc), so a slow
/// daemon only delays this one theme request, not input or animation.
const HELPER_SOCKET_TIMEOUT: Duration = Duration::from_secs(10);
const HELPER_RESPONSE_LIMIT: usize = RESPONSE_LIMIT + 4096;

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ThemeRequest {
    List,
    Preview {
        theme_id: String,
        background_id: Option<String>,
    },
    Activate {
        theme_id: String,
        expected_generation: String,
        background_id: Option<String>,
    },
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ThemeOrigin {
    User,
    Builtin,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ThemeEntry {
    pub id: String,
    pub name: String,
    pub label: String,
    pub origin: ThemeOrigin,
    /// The theme's own `preview.png` (Omarchy's convention), or a
    /// representative background image when a theme ships none. `None`
    /// leaves the chooser row as text only, same as before this field
    /// existed.
    pub preview_path: Option<PathBuf>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ActiveTheme {
    pub id: Option<String>,
    pub generation: Option<String>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ThemeList {
    pub themes: Vec<ThemeEntry>,
    pub active: ActiveTheme,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BackgroundKind {
    Image,
    Video,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BackgroundChoice {
    pub id: String,
    pub label: String,
    pub kind: BackgroundKind,
    pub path: PathBuf,
    pub selected: bool,
    /// `k230-theme` currently reports unverified; decode is another consumer.
    pub decode_status: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Compatibility {
    pub applied: Vec<String>,
    pub unavailable: Vec<String>,
    pub unknown: Vec<String>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AppAppearance {
    pub state: String,
    pub generation: Option<String>,
    pub error: Option<String>,
    pub kind: Option<String>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ThemePreview {
    pub theme: ThemeEntry,
    pub generation: String,
    pub appearance_path: PathBuf,
    pub palette: BTreeMap<String, String>,
    pub icon_theme: Option<String>,
    pub backgrounds: Vec<BackgroundChoice>,
    pub compatibility: Compatibility,
    pub activated: bool,
    /// App reload may fail after both shell endpoint ACKs. It is not folded
    /// into a false shell activation failure.
    pub app_appearance: Option<AppAppearance>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ThemeResponse {
    List(ThemeList),
    Preview(Box<ThemePreview>),
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ThemeReply {
    pub id: u64,
    pub request: ThemeRequest,
    pub result: Result<ThemeResponse, String>,
}

pub struct ThemeWorker {
    requests: SyncSender<(u64, ThemeRequest)>,
    replies: Receiver<ThemeReply>,
    outstanding: Arc<AtomicUsize>,
    next_id: AtomicU64,
}

impl ThemeWorker {
    /// `helper_socket` is `theme-helper.service`'s own socket
    /// (`/run/shell/theme-helper.sock`, matching `theme_client.py`'s
    /// `DEFAULT_SOCKET`); an empty path disables the direct-socket path
    /// entirely (every request goes straight to the `command` subprocess,
    /// today's behaviour), the same convention `command` itself already
    /// uses when `K230_THEME_COMMAND` is unset.
    pub fn spawn(command: PathBuf, helper_socket: PathBuf) -> Self {
        let (requests, incoming) = mpsc::sync_channel(QUEUE);
        let (outgoing, replies) = mpsc::sync_channel(QUEUE);
        let outstanding = Arc::new(AtomicUsize::new(0));
        // Close enough to `main.rs`'s own `state.started` (set a few lines
        // after this worker is spawned) for this thread's own
        // `rust-shell <ms>ms <event>` log lines to sort correctly into the
        // same merged timeline `tools/theme-swap-jank.py` already builds
        // from `main.rs`'s `fn log`.
        let process_started = Instant::now();
        thread::spawn(move || {
            while let Ok((id, request)) = incoming.recv() {
                let result = execute(&command, &helper_socket, &request, process_started);
                if outgoing
                    .send(ThemeReply {
                        id,
                        request,
                        result,
                    })
                    .is_err()
                {
                    break;
                }
            }
        });
        Self {
            requests,
            replies,
            outstanding,
            next_id: AtomicU64::new(1),
        }
    }

    pub fn try_submit(&self, request: ThemeRequest) -> Result<u64, &'static str> {
        if !valid_request(&request) {
            return Err("invalid theme or generation identity");
        }
        if self.outstanding.fetch_add(1, Ordering::AcqRel) >= QUEUE {
            self.outstanding.fetch_sub(1, Ordering::AcqRel);
            return Err("theme queue full");
        }
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        match self.requests.try_send((id, request)) {
            Ok(()) => Ok(id),
            Err(TrySendError::Full(_)) | Err(TrySendError::Disconnected(_)) => {
                self.outstanding.fetch_sub(1, Ordering::AcqRel);
                Err("theme worker unavailable")
            }
        }
    }

    pub fn try_recv(&self) -> Option<ThemeReply> {
        match self.replies.try_recv() {
            Ok(reply) => {
                self.outstanding.fetch_sub(1, Ordering::AcqRel);
                Some(reply)
            }
            Err(TryRecvError::Empty | TryRecvError::Disconnected) => None,
        }
    }
}

fn identity(value: &str) -> bool {
    value.len() == 24
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn valid_request(request: &ThemeRequest) -> bool {
    match request {
        ThemeRequest::List => true,
        ThemeRequest::Preview {
            theme_id,
            background_id,
        } => identity(theme_id) && background_id.as_deref().is_none_or(identity),
        ThemeRequest::Activate {
            theme_id,
            expected_generation,
            background_id,
        } => {
            identity(theme_id)
                && identity(expected_generation)
                && background_id.as_deref().is_none_or(identity)
        }
    }
}

/// The exact JSON object `tools/theme_client.py`'s own `as_request()` sends
/// to `theme-helper.service` -- see that function's doc: `list` carries no
/// `id`/`background` at all, `preview` adds both (the second nullable),
/// `activate` adds `expected_generation` too. Kept byte-for-byte
/// compatible with the daemon's own `theme_helperd.request_argv()`, which
/// is what actually validates and acts on it -- this is a second caller of
/// the exact same protocol, never a second, drifting one.
fn helper_request(request: &ThemeRequest) -> Value {
    match request {
        ThemeRequest::List => json!({"action": "list"}),
        ThemeRequest::Preview {
            theme_id,
            background_id,
        } => json!({"action": "preview", "id": theme_id, "background": background_id}),
        ThemeRequest::Activate {
            theme_id,
            expected_generation,
            background_id,
        } => json!({
            "action": "activate",
            "id": theme_id,
            "background": background_id,
            "expected_generation": expected_generation,
        }),
    }
}

/// One request/reply round trip directly against `theme-helper.service`'s
/// Unix socket, speaking the exact line protocol `tools/theme_client.py`
/// and `tools/theme_helperd.py` already speak to each other (one JSON
/// object, newline-terminated, half-closing the write side; one JSON reply
/// `{"result": ..., "exit_code": ...}`, also newline-terminated) -- no new
/// protocol, no subprocess, no Python interpreter start-up. Returns
/// `Err` for anything that should fall back to the subprocess path
/// (missing/refused socket, timeout, malformed reply); a *daemon-reported*
/// theme error (`exit_code != 0`) is returned as `Ok(Err(message))` so the
/// caller does not retry a request the daemon already validated and
/// rejected on its merits.
fn helper_socket_request(
    socket_path: &Path,
    request: &ThemeRequest,
) -> Result<Result<Value, String>, String> {
    let mut line = serde_json::to_vec(&helper_request(request))
        .map_err(|_| "theme request encode failed".to_string())?;
    line.push(b'\n');
    let deadline = Instant::now() + HELPER_SOCKET_TIMEOUT;
    let mut stream =
        UnixStream::connect(socket_path).map_err(|error| format!("helper socket: {error}"))?;
    stream
        .set_write_timeout(Some(HELPER_SOCKET_TIMEOUT))
        .map_err(|error| format!("helper socket: {error}"))?;
    stream
        .write_all(&line)
        .map_err(|error| format!("helper socket write failed: {error}"))?;
    stream
        .shutdown(std::net::Shutdown::Write)
        .map_err(|error| format!("helper socket shutdown failed: {error}"))?;
    let mut buffer = Vec::new();
    let mut chunk = [0u8; 65536];
    loop {
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            return Err("helper socket timed out".into());
        }
        stream
            .set_read_timeout(Some(remaining))
            .map_err(|error| format!("helper socket: {error}"))?;
        match stream.read(&mut chunk) {
            Ok(0) => break,
            Ok(count) => {
                if buffer.len().saturating_add(count) > HELPER_RESPONSE_LIMIT {
                    return Err("helper socket response exceeds bound".into());
                }
                buffer.extend_from_slice(&chunk[..count]);
                if buffer.contains(&b'\n') {
                    break;
                }
            }
            Err(error)
                if matches!(
                    error.kind(),
                    std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut
                ) =>
            {
                return Err("helper socket timed out".into());
            }
            Err(error) => return Err(format!("helper socket read failed: {error}")),
        }
    }
    let end = buffer
        .iter()
        .position(|byte| *byte == b'\n')
        .ok_or("helper socket reply missing terminator")?;
    let reply: Value = serde_json::from_slice(&buffer[..end])
        .map_err(|_| "invalid helper socket reply".to_string())?;
    let exit_code = reply
        .get("exit_code")
        .and_then(Value::as_i64)
        .ok_or("helper socket reply missing exit_code")?;
    let result = reply
        .get("result")
        .cloned()
        .ok_or("helper socket reply missing result")?;
    if exit_code == 0 {
        Ok(Ok(result))
    } else {
        Ok(Err(result
            .get("error")
            .and_then(Value::as_str)
            .filter(|text| text.chars().count() <= 240 && !text.chars().any(char::is_control))
            .map(str::to_owned)
            .unwrap_or_else(|| "theme command failed".into())))
    }
}

fn execute(
    command: &Path,
    helper_socket: &Path,
    request: &ThemeRequest,
    process_started: Instant,
) -> Result<ThemeResponse, String> {
    if !command.is_absolute() || !valid_request(request) {
        return Err("theme command or request is invalid".into());
    }
    let mut args = Vec::new();
    match request {
        ThemeRequest::List => args.push("list"),
        ThemeRequest::Preview {
            theme_id,
            background_id,
        } => {
            args.extend(["preview", theme_id]);
            if let Some(id) = background_id {
                args.extend(["--background", id]);
            }
        }
        ThemeRequest::Activate {
            theme_id,
            expected_generation,
            background_id,
        } => {
            args.extend([
                "activate",
                theme_id,
                "--expected-generation",
                expected_generation,
            ]);
            if let Some(id) = background_id {
                args.extend(["--background", id]);
            }
        }
    }
    let call_name = args.first().copied().unwrap_or("-");
    let theme_id = args.get(1).copied().unwrap_or("-");

    if helper_socket.as_os_str().len() > 0 {
        let call_started = Instant::now();
        let outcome = helper_socket_request(helper_socket, request);
        // Coordinator's own ask: "add the Rust-side timing log (rust-shell
        // … theme-command … path=socket ms=…)". Logged for every attempt,
        // including one that falls back below, so a board run can see
        // exactly how much of a request's total time the socket attempt
        // itself cost even when it did not win.
        eprintln!(
            "rust-shell {}ms theme-command {call_name} {theme_id} path=socket ms={}",
            process_started.elapsed().as_millis(),
            call_started.elapsed().as_millis()
        );
        match outcome {
            Ok(Ok(value)) => return parse_response_value(request, value),
            Ok(Err(message)) => return Err(message),
            Err(_) => {} // socket missing/refused/timed out/malformed: fall back below
        }
    }

    let call_started = Instant::now();
    let outcome = run(command, &args);
    // Named stage marker (coordinator's own ask: "make sure that [chooser]
    // path uses the daemon too, and time it"): this is the whole `k230-theme`
    // subprocess's wall time as the chooser actually waits on it -- whether
    // that command itself was served by `theme-helper.service` or fell back
    // is `theme_client.py`'s own THEME_TIMING syslog line (journalctl), not
    // observable from here; this line is what the chooser's own worker
    // thread (not the Wayland thread -- see this module's own doc) actually
    // blocked on for this one request, logged regardless of success so a
    // spawn failure is timed too. Same `rust-shell <ms>ms <event>` shape
    // `main.rs`'s own `fn log` uses, so `tools/theme-swap-jank.py`'s
    // existing journal parsing (`RUST_LOG_RE`) picks this up for free.
    eprintln!(
        "rust-shell {}ms theme-command {call_name} {theme_id} path=subprocess ms={}",
        process_started.elapsed().as_millis(),
        call_started.elapsed().as_millis()
    );
    let (stdout, stderr, success) = outcome?;
    if !success {
        return Err(command_error(&stderr));
    }
    parse_response(request, &stdout)
}

fn nonblocking(fd: i32) -> Result<(), String> {
    let flags = unsafe { libc::fcntl(fd, libc::F_GETFL) };
    if flags < 0 || unsafe { libc::fcntl(fd, libc::F_SETFL, flags | libc::O_NONBLOCK) } < 0 {
        return Err("theme output unavailable".into());
    }
    Ok(())
}

fn stop(child: &mut Child) {
    // A trusted packaged helper may fork its own bounded conversion process.
    // The process group prevents a timed-out descendant retaining both pipes.
    unsafe { libc::kill(-(child.id() as i32), libc::SIGKILL) };
    let _ = child.kill();
    let _ = child.wait();
}

fn drain(pipe: &mut impl Read, bytes: &mut Vec<u8>, limit: usize) -> Result<bool, String> {
    let mut chunk = [0u8; 4096];
    let mut eof = false;
    loop {
        match pipe.read(&mut chunk) {
            Ok(0) => {
                eof = true;
                break;
            }
            Ok(count) => {
                if bytes.len().saturating_add(count) > limit {
                    return Err("theme command output exceeds bound".into());
                }
                bytes.extend_from_slice(&chunk[..count]);
            }
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => break,
            Err(_) => return Err("theme command output read failed".into()),
        }
    }
    Ok(eof)
}

fn run(command: &Path, args: &[&str]) -> Result<(Vec<u8>, Vec<u8>, bool), String> {
    let mut child = Command::new(command)
        .args(args)
        .process_group(0)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|_| "theme command unavailable")?;
    let mut stdout = child.stdout.take().ok_or("theme stdout unavailable")?;
    let mut stderr = child.stderr.take().ok_or("theme stderr unavailable")?;
    if let Err(error) =
        nonblocking(stdout.as_raw_fd()).and_then(|_| nonblocking(stderr.as_raw_fd()))
    {
        stop(&mut child);
        return Err(error);
    }
    let deadline = Instant::now() + COMMAND_DEADLINE;
    let mut out = Vec::new();
    let mut err = Vec::new();
    let (mut out_eof, mut err_eof) = (false, false);
    loop {
        let progress = (|| {
            if !out_eof {
                out_eof = drain(&mut stdout, &mut out, RESPONSE_LIMIT)?;
            }
            if !err_eof {
                err_eof = drain(&mut stderr, &mut err, ERROR_LIMIT)?;
            }
            if out_eof && err_eof {
                if let Some(status) = child.try_wait().map_err(|_| "theme wait failed")? {
                    return Ok(Some(status.success()));
                }
            }
            if Instant::now() >= deadline {
                return Err("theme command timed out".into());
            }
            let mut fds = [
                libc::pollfd {
                    fd: if out_eof { -1 } else { stdout.as_raw_fd() },
                    events: libc::POLLIN | libc::POLLHUP,
                    revents: 0,
                },
                libc::pollfd {
                    fd: if err_eof { -1 } else { stderr.as_raw_fd() },
                    events: libc::POLLIN | libc::POLLHUP,
                    revents: 0,
                },
            ];
            let remaining = deadline.saturating_duration_since(Instant::now());
            let timeout = remaining.as_millis().min(50) as i32;
            let polled =
                unsafe { libc::poll(fds.as_mut_ptr(), fds.len() as libc::nfds_t, timeout) };
            if polled < 0
                && std::io::Error::last_os_error().kind() != std::io::ErrorKind::Interrupted
            {
                return Err("theme command poll failed".into());
            }
            Ok(None)
        })();
        match progress {
            Ok(Some(success)) => return Ok((out, err, success)),
            Ok(None) => {}
            Err(error) => {
                stop(&mut child);
                return Err(error);
            }
        }
    }
}

fn command_error(bytes: &[u8]) -> String {
    let Ok(value) = serde_json::from_slice::<Value>(bytes) else {
        return "theme command failed".into();
    };
    let Some(error) = value.get("error").and_then(Value::as_str) else {
        return "theme command failed".into();
    };
    if error.chars().count() > 240 || error.chars().any(char::is_control) {
        return "theme command failed".into();
    }
    error.to_owned()
}

fn required_text(value: Option<&Value>, limit: usize) -> Result<String, String> {
    let text = value.and_then(Value::as_str).ok_or("missing theme text")?;
    if text.is_empty() || text.chars().count() > limit || text.chars().any(char::is_control) {
        return Err("invalid theme text".into());
    }
    Ok(text.to_owned())
}

fn optional_text(value: Option<&Value>, limit: usize) -> Result<Option<String>, String> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(value) => required_text(Some(value), limit).map(Some),
    }
}

fn required_id(value: Option<&Value>) -> Result<String, String> {
    let id = required_text(value, 24)?;
    if !identity(&id) {
        return Err("invalid theme identity".into());
    }
    Ok(id)
}

fn optional_id(value: Option<&Value>) -> Result<Option<String>, String> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(value) => required_id(Some(value)).map(Some),
    }
}

fn clean_absolute(value: Option<&Value>) -> Result<PathBuf, String> {
    let raw = required_text(value, 4096)?;
    let path = PathBuf::from(raw);
    if !path.is_absolute()
        || path
            .components()
            .any(|component| matches!(component, Component::ParentDir | Component::CurDir))
    {
        return Err("invalid theme asset path".into());
    }
    Ok(path)
}

fn optional_absolute(value: Option<&Value>) -> Result<Option<PathBuf>, String> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(value) => clean_absolute(Some(value)).map(Some),
    }
}

fn entry(value: &Value) -> Result<ThemeEntry, String> {
    let origin = match value.get("origin").and_then(Value::as_str) {
        Some("user") => ThemeOrigin::User,
        Some("builtin") => ThemeOrigin::Builtin,
        _ => return Err("invalid theme origin".into()),
    };
    Ok(ThemeEntry {
        id: required_id(value.get("id"))?,
        name: required_text(value.get("name"), 80)?,
        label: required_text(value.get("label"), 80)?,
        origin,
        preview_path: optional_absolute(value.get("preview_path"))?,
    })
}

fn string_list(value: Option<&Value>) -> Result<Vec<String>, String> {
    let rows = value
        .and_then(Value::as_array)
        .ok_or("invalid compatibility list")?;
    if rows.len() > MAX_COMPATIBILITY {
        return Err("compatibility list exceeds bound".into());
    }
    rows.iter()
        .map(|row| required_text(Some(row), 512))
        .collect()
}

fn preview(value: &Value, request: &ThemeRequest) -> Result<ThemePreview, String> {
    let theme = entry(value.get("theme").ok_or("missing theme")?)?;
    let (requested, expected, background) = match request {
        ThemeRequest::Preview {
            theme_id,
            background_id,
        } => (theme_id, None, background_id.as_deref()),
        ThemeRequest::Activate {
            theme_id,
            expected_generation,
            background_id,
        } => (
            theme_id,
            Some(expected_generation.as_str()),
            background_id.as_deref(),
        ),
        ThemeRequest::List => return Err("wrong theme response".into()),
    };
    if theme.id != *requested {
        return Err("theme reply identity changed".into());
    }
    let generation = required_id(value.get("generation"))?;
    if expected.is_some_and(|id| id != generation) {
        return Err("theme changed since preview; preview it again".into());
    }
    let appearance_path = clean_absolute(value.get("appearance_path"))?;
    if appearance_path
        .file_name()
        .is_none_or(|name| name != "appearance.json")
        || appearance_path
            .parent()
            .and_then(Path::file_name)
            .and_then(|name| name.to_str())
            != Some(generation.as_str())
    {
        return Err("appearance path/generation mismatch".into());
    }
    let palette_raw = value
        .get("palette")
        .and_then(Value::as_object)
        .ok_or("missing theme palette")?;
    if palette_raw.len() > MAX_PALETTE {
        return Err("theme palette exceeds bound".into());
    }
    let mut palette = BTreeMap::new();
    for (key, color) in palette_raw {
        let key = required_text(Some(&Value::String(key.clone())), 128)?;
        let color = required_text(Some(color), 128)?;
        palette.insert(key, color);
    }
    let rows = value
        .get("backgrounds")
        .and_then(Value::as_array)
        .ok_or("missing theme backgrounds")?;
    if rows.len() > MAX_BACKGROUNDS {
        return Err("theme backgrounds exceed bound".into());
    }
    let generation_dir = appearance_path.parent().ok_or("invalid appearance path")?;
    let background_dir = generation_dir.join("theme/backgrounds");
    let mut backgrounds = Vec::with_capacity(rows.len());
    let mut selected_count = 0;
    for row in rows {
        let id = required_id(row.get("id"))?;
        let kind = match row.get("kind").and_then(Value::as_str) {
            Some("image") => BackgroundKind::Image,
            Some("video") => BackgroundKind::Video,
            _ => return Err("invalid background kind".into()),
        };
        let path = clean_absolute(row.get("path"))?;
        if path.parent() != Some(background_dir.as_path()) {
            return Err("background escapes staged generation".into());
        }
        let selected = row
            .get("selected")
            .and_then(Value::as_bool)
            .ok_or("invalid background selection")?;
        selected_count += usize::from(selected);
        let decode_status = required_text(row.get("decode_status"), 64)?;
        if decode_status != "unverified" {
            return Err("unsupported background decode status".into());
        }
        backgrounds.push(BackgroundChoice {
            id,
            label: required_text(row.get("label"), 255)?,
            kind,
            path,
            selected,
            decode_status,
        });
    }
    if selected_count > 1
        || background.is_some_and(|id| !backgrounds.iter().any(|row| row.id == id && row.selected))
    {
        return Err("selected background changed".into());
    }
    let compatibility = value.get("compatibility").ok_or("missing compatibility")?;
    let activated = value
        .get("activated")
        .and_then(Value::as_bool)
        .ok_or("missing activation state")?;
    if activated != matches!(request, ThemeRequest::Activate { .. }) {
        return Err("unexpected theme activation state".into());
    }
    let app_appearance = match value.get("app_appearance") {
        None if !activated => None,
        Some(item) if activated => {
            let state = required_text(item.get("state"), 32)?;
            if !matches!(state.as_str(), "applied" | "failed" | "superseded") {
                return Err("invalid app appearance state".into());
            }
            Some(AppAppearance {
                state,
                generation: optional_id(item.get("generation"))?,
                error: optional_text(item.get("error"), 160)?,
                kind: optional_text(item.get("kind"), 96)?,
            })
        }
        _ => return Err("missing app appearance status".into()),
    };
    Ok(ThemePreview {
        theme,
        generation,
        appearance_path,
        palette,
        icon_theme: optional_text(value.get("icon_theme"), 160)?,
        backgrounds,
        compatibility: Compatibility {
            applied: string_list(compatibility.get("applied"))?,
            unavailable: string_list(compatibility.get("unavailable"))?,
            unknown: string_list(compatibility.get("unknown"))?,
        },
        activated,
        app_appearance,
    })
}

pub fn parse_response(request: &ThemeRequest, bytes: &[u8]) -> Result<ThemeResponse, String> {
    if bytes.len() > RESPONSE_LIMIT {
        return Err("theme response exceeds bound".into());
    }
    let value: Value = serde_json::from_slice(bytes).map_err(|_| "invalid theme JSON")?;
    parse_response_value(request, value)
}

/// Same validation/shape checks as `parse_response`, on an already-parsed
/// `Value` -- used by the direct helper-socket path (`helper_socket_request`
/// already parsed the reply's `result` object) so a successful daemon
/// answer is never re-serialized to bytes just to be re-parsed here.
fn parse_response_value(request: &ThemeRequest, value: Value) -> Result<ThemeResponse, String> {
    if value.get("schema").and_then(Value::as_u64) != Some(1) {
        return Err("unsupported theme catalog schema".into());
    }
    match request {
        ThemeRequest::List => {
            let rows = value
                .get("themes")
                .and_then(Value::as_array)
                .ok_or("missing theme list")?;
            if rows.len() > MAX_THEMES {
                return Err("theme list exceeds bound".into());
            }
            let themes = rows.iter().map(entry).collect::<Result<Vec<_>, _>>()?;
            let active = value.get("active").ok_or("missing active theme")?;
            Ok(ThemeResponse::List(ThemeList {
                themes,
                active: ActiveTheme {
                    id: optional_id(active.get("id"))?,
                    generation: optional_id(active.get("generation"))?,
                },
            }))
        }
        _ => preview(&value, request).map(|value| ThemeResponse::Preview(Box::new(value))),
    }
}

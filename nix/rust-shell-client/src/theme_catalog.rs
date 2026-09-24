//! Bounded asynchronous bridge to the installed, trusted `k230-theme` command.
//!
//! The UI never waits for theme preparation or endpoint acknowledgements on
//! the Wayland thread. A preview only stages immutable data; activation needs
//! the exact generation returned by preview. Opaque IDs are argv values, not
//! paths or shell text.

use serde_json::Value;
use std::{
    collections::BTreeMap,
    io::Read,
    os::{fd::AsRawFd, unix::process::CommandExt},
    path::{Component, Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicUsize, Ordering},
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
    pub request: ThemeRequest,
    pub result: Result<ThemeResponse, String>,
}

pub struct ThemeWorker {
    requests: SyncSender<ThemeRequest>,
    replies: Receiver<ThemeReply>,
    outstanding: Arc<AtomicUsize>,
}

impl ThemeWorker {
    pub fn spawn(command: PathBuf) -> Self {
        let (requests, incoming) = mpsc::sync_channel(QUEUE);
        let (outgoing, replies) = mpsc::sync_channel(QUEUE);
        let outstanding = Arc::new(AtomicUsize::new(0));
        thread::spawn(move || {
            while let Ok(request) = incoming.recv() {
                let result = execute(&command, &request);
                if outgoing.send(ThemeReply { request, result }).is_err() {
                    break;
                }
            }
        });
        Self {
            requests,
            replies,
            outstanding,
        }
    }

    pub fn try_submit(&self, request: ThemeRequest) -> Result<(), &'static str> {
        if !valid_request(&request) {
            return Err("invalid theme or generation identity");
        }
        if self.outstanding.fetch_add(1, Ordering::AcqRel) >= QUEUE {
            self.outstanding.fetch_sub(1, Ordering::AcqRel);
            return Err("theme queue full");
        }
        match self.requests.try_send(request) {
            Ok(()) => Ok(()),
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

fn execute(command: &Path, request: &ThemeRequest) -> Result<ThemeResponse, String> {
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
    let (stdout, stderr, success) = run(command, &args)?;
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

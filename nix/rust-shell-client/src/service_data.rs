//! Bounded, typed service data for the handheld shell.
//!
//! The caller owns polling and rendering. These parsers accept only bytes that
//! an asynchronous worker has already read from the trusted settings command
//! or the private notification socket.

use serde_json::{json, Value};
use std::{
    fs,
    io::{Read, Write},
    os::{
        fd::{AsRawFd, FromRawFd},
        unix::{
            fs::{FileTypeExt, MetadataExt, PermissionsExt},
            net::UnixStream,
        },
    },
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, AtomicUsize, Ordering},
        mpsc::{self, Receiver, SyncSender, TryRecvError, TrySendError},
        Arc,
    },
    thread,
    time::{Duration, Instant},
};

const MAX_SETTINGS: usize = 16 * 1024;
const MAX_HISTORY: usize = 128 * 1024;
const MAX_EVENTS: usize = 64;
const MAX_REQUEST: usize = 4096;
const QUEUE: usize = 8;
const SERVICE_DEADLINE: Duration = Duration::from_secs(4);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ControlState {
    Writable,
    ReadOnly,
    Action,
    Unavailable,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ControlValue {
    Text(String),
    Percent(u8),
    Boolean(bool),
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Control {
    pub state: ControlState,
    pub value: Option<ControlValue>,
    pub label: String,
    pub detail: Option<String>,
    pub action: Option<String>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SettingsSnapshot {
    pub network: Control,
    pub brightness: Control,
    pub keyboard: Control,
    pub motion: Control,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Priority {
    Ordinary,
    Important,
    Critical,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NotificationEvent {
    pub id: u64,
    pub source: String,
    pub icon: Option<String>,
    pub summary: String,
    pub body: String,
    pub priority: Priority,
    pub timestamp: i64,
    pub error: Option<String>,
    pub dismissible: bool,
    pub action_available: bool,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NotificationPreview {
    pub id: u64,
    pub source: String,
    pub icon: Option<String>,
    pub summary: String,
    pub priority: Priority,
    pub ongoing: bool,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NotificationSnapshot {
    pub count: usize,
    pub events: Vec<NotificationEvent>,
    /// Already privacy-filtered by the notification broker. Do not synthesize
    /// a preview from the history rows, which may contain private text.
    pub preview: Option<NotificationPreview>,
}

fn bounded_json(bytes: &[u8], limit: usize) -> Result<Value, String> {
    if bytes.len() > limit {
        return Err("service response exceeds bound".into());
    }
    serde_json::from_slice(bytes).map_err(|_| "invalid service JSON".into())
}

fn string(value: &Value, limit: usize) -> Result<String, String> {
    let text = value.as_str().ok_or("invalid service text")?;
    if text.len() > limit || text.chars().any(|c| c.is_control()) {
        return Err("invalid service text".into());
    }
    Ok(text.to_owned())
}

fn optional_string(value: Option<&Value>, limit: usize) -> Result<Option<String>, String> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(value) => string(value, limit).map(Some),
    }
}

fn control(value: &Value, kind: &str) -> Result<Control, String> {
    let state = match value.get("state").and_then(Value::as_str) {
        Some("writable") => ControlState::Writable,
        Some("read-only") => ControlState::ReadOnly,
        Some("action") => ControlState::Action,
        Some("unavailable") => ControlState::Unavailable,
        _ => return Err("invalid control state".into()),
    };
    let raw = value.get("value");
    let parsed = match kind {
        "brightness" => match raw {
            Some(Value::Number(value)) if value.as_u64().is_some_and(|n| n <= 100) => {
                Some(ControlValue::Percent(value.as_u64().unwrap() as u8))
            }
            None | Some(Value::Null) => None,
            _ => return Err("invalid brightness value".into()),
        },
        "motion" => match raw {
            Some(Value::Bool(value)) => Some(ControlValue::Boolean(*value)),
            None | Some(Value::Null) => None,
            _ => return Err("invalid motion value".into()),
        },
        "network" => match raw {
            Some(Value::String(value)) if matches!(value.as_str(), "link-up" | "disconnected") => {
                Some(ControlValue::Text(value.clone()))
            }
            None | Some(Value::Null) => None,
            _ => return Err("invalid network value".into()),
        },
        "keyboard" => match raw {
            None | Some(Value::Null) => None,
            _ => return Err("invalid keyboard value".into()),
        },
        _ => return Err("unknown control".into()),
    };
    if state == ControlState::Unavailable && parsed.is_some() {
        return Err("unavailable control has value".into());
    }
    let action = optional_string(value.get("action"), 64)?;
    if action.as_deref().is_some_and(|a| a != "keyboard-toggle")
        || (kind != "keyboard" && action.is_some())
        || (state == ControlState::Action) != action.is_some()
    {
        return Err("invalid control action".into());
    }
    Ok(Control {
        state,
        value: parsed,
        label: string(value.get("label").ok_or("missing control label")?, 96)?,
        detail: optional_string(value.get("detail"), 160)?,
        action,
    })
}

pub fn parse_settings(bytes: &[u8]) -> Result<SettingsSnapshot, String> {
    let data = bounded_json(bytes, MAX_SETTINGS)?;
    if data.get("schema").and_then(Value::as_u64) != Some(1) {
        return Err("unsupported settings schema".into());
    }
    let controls = data.get("controls").ok_or("missing settings controls")?;
    Ok(SettingsSnapshot {
        network: control(controls.get("network").ok_or("missing network")?, "network")?,
        brightness: control(
            controls.get("brightness").ok_or("missing brightness")?,
            "brightness",
        )?,
        keyboard: control(
            controls.get("keyboard").ok_or("missing keyboard")?,
            "keyboard",
        )?,
        motion: control(controls.get("motion").ok_or("missing motion")?, "motion")?,
    })
}

fn priority(value: &Value) -> Result<Priority, String> {
    match value.as_str() {
        Some("ordinary") => Ok(Priority::Ordinary),
        Some("important") => Ok(Priority::Important),
        Some("critical") => Ok(Priority::Critical),
        _ => Err("invalid notification priority".into()),
    }
}

fn icon(value: Option<&Value>) -> Result<Option<String>, String> {
    let icon = optional_string(value, 160)?;
    if icon
        .as_deref()
        .is_some_and(|s| s.is_empty() || s.contains('/') || s.contains('\\'))
    {
        return Err("invalid notification icon".into());
    }
    Ok(icon)
}

fn id(value: &Value) -> Result<u64, String> {
    let id = value.as_u64().ok_or("invalid notification id")?;
    if id == 0 || id >= (1 << 53) {
        return Err("notification id out of range".into());
    }
    Ok(id)
}

pub fn parse_history(bytes: &[u8]) -> Result<NotificationSnapshot, String> {
    let data = bounded_json(bytes, MAX_HISTORY)?;
    if data.get("schema").and_then(Value::as_u64) != Some(1) {
        return Err("unsupported notification schema".into());
    }
    let rows = data
        .get("events")
        .and_then(Value::as_array)
        .ok_or("missing notification events")?;
    if rows.len() > MAX_EVENTS
        || data.get("count").and_then(Value::as_u64) != Some(rows.len() as u64)
    {
        return Err("invalid notification count".into());
    }
    let mut events = Vec::with_capacity(rows.len());
    for row in rows {
        events.push(NotificationEvent {
            id: id(row.get("id").ok_or("missing notification id")?)?,
            source: string(row.get("source").ok_or("missing source")?, 160)?,
            icon: icon(row.get("icon"))?,
            summary: string(row.get("summary").ok_or("missing summary")?, 160)?,
            body: string(row.get("body").ok_or("missing body")?, 512)?,
            priority: priority(row.get("priority").ok_or("missing priority")?)?,
            timestamp: row
                .get("timestamp")
                .and_then(Value::as_i64)
                .ok_or("invalid timestamp")?,
            error: optional_string(row.get("error"), 160)?,
            dismissible: row
                .get("dismissible")
                .and_then(Value::as_bool)
                .ok_or("invalid dismissible")?,
            action_available: row
                .get("action_available")
                .and_then(Value::as_bool)
                .ok_or("invalid action availability")?,
        });
    }
    let preview = match data.get("preview") {
        None | Some(Value::Null) => None,
        Some(row) => {
            if row.get("focus").and_then(Value::as_bool) != Some(false) {
                return Err("preview may not take focus".into());
            }
            let preview_id = id(row.get("id").ok_or("missing preview id")?)?;
            if !events.iter().any(|event| event.id == preview_id) {
                return Err("preview absent from history".into());
            }
            Some(NotificationPreview {
                id: preview_id,
                source: string(row.get("source").ok_or("missing preview source")?, 160)?,
                icon: icon(row.get("icon"))?,
                summary: string(row.get("summary").ok_or("missing preview summary")?, 160)?,
                priority: priority(row.get("priority").ok_or("missing preview priority")?)?,
                ongoing: row
                    .get("ongoing")
                    .and_then(Value::as_bool)
                    .ok_or("invalid preview ongoing")?,
            })
        }
    };
    Ok(NotificationSnapshot {
        count: events.len(),
        events,
        preview,
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PowerAction {
    Reboot,
    Poweroff,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ServiceRequest {
    RefreshSettings,
    RefreshNotifications,
    Brightness(u8),
    KeyboardToggle,
    PowerRequest(PowerAction),
    PowerConfirm(String),
    PowerCancel(String),
    NotificationDismiss(u64),
    NotificationDismissAll,
    NotificationAction(u64),
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ActionOutcome {
    pub state: String,
    pub error: Option<String>,
    pub token: Option<String>,
    pub label: Option<String>,
    pub power_action: Option<PowerAction>,
    pub expires_in_seconds: Option<u32>,
    pub requested_percent: Option<u8>,
    pub brightness: Option<Control>,
    pub retry: bool,
    pub remaining: Option<usize>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ServiceResponse {
    Settings(SettingsSnapshot),
    Notifications(NotificationSnapshot),
    Action(ActionOutcome),
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ServiceReply {
    pub request: ServiceRequest,
    pub result: Result<ServiceResponse, String>,
}

/// The UI uses `try_submit`/`try_recv` only. This worker owns all blocking
/// process and socket work; every request has one bounded result slot.
pub struct ServiceWorker {
    requests: SyncSender<ServiceRequest>,
    replies: Receiver<ServiceReply>,
    outstanding: Arc<AtomicUsize>,
    settings_queued: Arc<AtomicBool>,
    notifications_queued: Arc<AtomicBool>,
}

impl ServiceWorker {
    pub fn spawn(settings_command: PathBuf, notification_socket: PathBuf) -> Self {
        let (requests, incoming) = mpsc::sync_channel(QUEUE);
        let (outgoing, replies) = mpsc::sync_channel(QUEUE);
        let outstanding = Arc::new(AtomicUsize::new(0));
        let settings_queued = Arc::new(AtomicBool::new(false));
        let notifications_queued = Arc::new(AtomicBool::new(false));
        let settings_flag = Arc::clone(&settings_queued);
        let notifications_flag = Arc::clone(&notifications_queued);
        thread::spawn(move || {
            while let Ok(request) = incoming.recv() {
                let result = execute(&settings_command, &notification_socket, &request);
                match request {
                    ServiceRequest::RefreshSettings => {
                        settings_flag.store(false, Ordering::Release)
                    }
                    ServiceRequest::RefreshNotifications => {
                        notifications_flag.store(false, Ordering::Release)
                    }
                    _ => {}
                }
                if outgoing.send(ServiceReply { request, result }).is_err() {
                    break;
                }
            }
        });
        Self {
            requests,
            replies,
            outstanding,
            settings_queued,
            notifications_queued,
        }
    }

    pub fn try_submit(&self, request: ServiceRequest) -> Result<(), &'static str> {
        let flag = match request {
            ServiceRequest::RefreshSettings => Some(&self.settings_queued),
            ServiceRequest::RefreshNotifications => Some(&self.notifications_queued),
            _ => None,
        };
        if flag.is_some_and(|flag| flag.swap(true, Ordering::AcqRel)) {
            return Ok(()); // Refresh already pending or running.
        }
        if self.outstanding.fetch_add(1, Ordering::AcqRel) >= QUEUE {
            self.outstanding.fetch_sub(1, Ordering::AcqRel);
            if let Some(flag) = flag {
                flag.store(false, Ordering::Release);
            }
            return Err("service queue full");
        }
        match self.requests.try_send(request) {
            Ok(()) => Ok(()),
            Err(TrySendError::Full(_)) | Err(TrySendError::Disconnected(_)) => {
                self.outstanding.fetch_sub(1, Ordering::AcqRel);
                if let Some(flag) = flag {
                    flag.store(false, Ordering::Release);
                }
                Err("service worker unavailable")
            }
        }
    }

    pub fn try_recv(&self) -> Option<ServiceReply> {
        match self.replies.try_recv() {
            Ok(reply) => {
                self.outstanding.fetch_sub(1, Ordering::AcqRel);
                Some(reply)
            }
            Err(TryRecvError::Empty | TryRecvError::Disconnected) => None,
        }
    }
}

fn execute(
    settings: &Path,
    socket: &Path,
    request: &ServiceRequest,
) -> Result<ServiceResponse, String> {
    match request {
        ServiceRequest::RefreshSettings => {
            parse_settings(&settings_command(settings, &["status"])?).map(ServiceResponse::Settings)
        }
        ServiceRequest::RefreshNotifications => parse_history(&notification_request(
            socket,
            json!({"operation":"history"}),
        )?)
        .map(ServiceResponse::Notifications),
        ServiceRequest::Brightness(percent) => {
            if *percent > 100 {
                return Err("invalid brightness request".into());
            }
            parse_action(&settings_command(
                settings,
                &["brightness", &percent.to_string()],
            )?)
            .map(ServiceResponse::Action)
        }
        ServiceRequest::KeyboardToggle => {
            parse_action(&settings_command(settings, &["keyboard-toggle"])?)
                .map(ServiceResponse::Action)
        }
        ServiceRequest::PowerRequest(action) => {
            let action = match action {
                PowerAction::Reboot => "reboot",
                PowerAction::Poweroff => "poweroff",
            };
            parse_action(&settings_command(settings, &["request", action])?)
                .map(ServiceResponse::Action)
        }
        ServiceRequest::PowerConfirm(token) | ServiceRequest::PowerCancel(token) => {
            if !confirmation_token(token) {
                return Err("invalid confirmation token".into());
            }
            let operation = if matches!(request, ServiceRequest::PowerConfirm(_)) {
                "confirm"
            } else {
                "cancel"
            };
            parse_action(&settings_command(settings, &[operation, token])?)
                .map(ServiceResponse::Action)
        }
        ServiceRequest::NotificationDismiss(id) | ServiceRequest::NotificationAction(id) => {
            if *id == 0 || *id >= 1 << 53 {
                return Err("invalid notification id".into());
            }
            let operation = if matches!(request, ServiceRequest::NotificationDismiss(_)) {
                "dismiss"
            } else {
                "action"
            };
            parse_action(&notification_request(
                socket,
                json!({"operation":operation,"id":id}),
            )?)
            .map(ServiceResponse::Action)
        }
        ServiceRequest::NotificationDismissAll => parse_action(&notification_request(
            socket,
            json!({"operation":"dismiss-all"}),
        )?)
        .map(ServiceResponse::Action),
    }
}

fn confirmation_token(token: &str) -> bool {
    token.len() == 32
        && token
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
}

fn parse_action(bytes: &[u8]) -> Result<ActionOutcome, String> {
    let data = bounded_json(bytes, MAX_SETTINGS)?;
    let state = string(data.get("state").ok_or("missing action state")?, 32)?;
    if !matches!(
        state.as_str(),
        "applied"
            | "pending"
            | "requested"
            | "failed"
            | "confirmation"
            | "cancelled"
            | "dismissed"
            | "accepted"
    ) {
        return Err("invalid action state".into());
    }
    let token = optional_string(data.get("token"), 64)?;
    if token
        .as_deref()
        .is_some_and(|token| !confirmation_token(token))
    {
        return Err("invalid action token".into());
    }
    let remaining = data
        .get("remaining")
        .map(|value| value.as_u64().ok_or("invalid remaining count"))
        .transpose()?
        .map(|n| usize::try_from(n).map_err(|_| "remaining count overflow"))
        .transpose()?;
    if remaining.is_some_and(|count| count > MAX_EVENTS) {
        return Err("remaining count exceeds bound".into());
    }
    let power_action = match data.get("action").and_then(Value::as_str) {
        None => None,
        Some("reboot") => Some(PowerAction::Reboot),
        Some("poweroff") => Some(PowerAction::Poweroff),
        _ => return Err("invalid power action".into()),
    };
    let expires_in_seconds = data
        .get("expires_in_seconds")
        .map(|value| value.as_u64().ok_or("invalid confirmation expiry"))
        .transpose()?
        .map(|seconds| u32::try_from(seconds).map_err(|_| "confirmation expiry overflow"))
        .transpose()?;
    if expires_in_seconds.is_some_and(|seconds| seconds > 30) {
        return Err("confirmation expiry exceeds bound".into());
    }
    let requested_percent = data
        .get("requested")
        .map(|value| value.as_u64().ok_or("invalid requested brightness"))
        .transpose()?
        .map(|percent| u8::try_from(percent).map_err(|_| "requested brightness overflow"))
        .transpose()?;
    if requested_percent.is_some_and(|percent| percent > 100) {
        return Err("requested brightness exceeds range".into());
    }
    let brightness = data
        .get("control")
        .map(|value| control(value, "brightness"))
        .transpose()?;
    Ok(ActionOutcome {
        state,
        error: optional_string(data.get("error"), 160)?,
        token,
        label: optional_string(data.get("label"), 160)?,
        power_action,
        expires_in_seconds,
        requested_percent,
        brightness,
        retry: data.get("retry").and_then(Value::as_bool).unwrap_or(false),
        remaining,
    })
}

fn settings_command(command: &Path, args: &[&str]) -> Result<Vec<u8>, String> {
    let mut child = Command::new(command)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "settings command unavailable")?;
    let mut stdout = child.stdout.take().ok_or("missing settings output")?;
    let flags = unsafe { libc::fcntl(stdout.as_raw_fd(), libc::F_GETFL) };
    if flags < 0
        || unsafe { libc::fcntl(stdout.as_raw_fd(), libc::F_SETFL, flags | libc::O_NONBLOCK) } < 0
    {
        let _ = child.kill();
        let _ = child.wait();
        return Err("settings output unavailable".into());
    }
    let deadline = Instant::now() + SERVICE_DEADLINE;
    let mut bytes = Vec::new();
    let mut eof = false;
    loop {
        let mut chunk = [0u8; 4096];
        match stdout.read(&mut chunk) {
            Ok(0) => eof = true,
            Ok(n) => bytes.extend_from_slice(&chunk[..n]),
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {}
            Err(_) => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("settings read failed".into());
            }
        }
        if bytes.len() > MAX_SETTINGS || Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            return Err("settings response exceeded bound or deadline".into());
        }
        if eof {
            match child.try_wait().map_err(|_| "settings wait failed")? {
                Some(status) if status.success() => return Ok(bytes),
                Some(_) => return Err("settings command failed".into()),
                None => {}
            }
        }
        thread::sleep(Duration::from_millis(10));
    }
}

fn notification_request(path: &Path, request: Value) -> Result<Vec<u8>, String> {
    let parent = path.parent().ok_or("invalid notification socket path")?;
    let dir = fs::symlink_metadata(parent).map_err(|_| "notification runtime unavailable")?;
    let socket = fs::symlink_metadata(path).map_err(|_| "notification socket unavailable")?;
    let uid = unsafe { libc::geteuid() };
    if !dir.is_dir()
        || dir.uid() != uid
        || dir.permissions().mode() & 0o077 != 0
        || !socket.file_type().is_socket()
        || socket.uid() != uid
        || socket.permissions().mode() & 0o077 != 0
    {
        return Err("unsafe notification socket".into());
    }
    let deadline = Instant::now() + SERVICE_DEADLINE;
    let mut stream = connect_nonblocking(path, deadline)?;
    let mut line = serde_json::to_vec(&request).map_err(|_| "invalid notification request")?;
    line.push(b'\n');
    if line.len() > MAX_REQUEST {
        return Err("notification request exceeds bound".into());
    }
    let mut written = 0;
    while written < line.len() {
        match stream.write(&line[written..]) {
            Ok(0) => return Err("notification write closed".into()),
            Ok(n) => written += n,
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                poll_fd(stream.as_raw_fd(), libc::POLLOUT, deadline)?
            }
            Err(_) => return Err("notification write failed".into()),
        }
    }
    let mut response = Vec::new();
    loop {
        let mut chunk = [0u8; 4096];
        match stream.read(&mut chunk) {
            Ok(0) => return Err("notification response closed".into()),
            Ok(n) => response.extend_from_slice(&chunk[..n]),
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                poll_fd(stream.as_raw_fd(), libc::POLLIN, deadline)?
            }
            Err(_) => return Err("notification read failed".into()),
        }
        if response.len() > MAX_HISTORY {
            return Err("notification response exceeds bound".into());
        }
        if let Some(end) = response.iter().position(|byte| *byte == b'\n') {
            if end + 1 != response.len() {
                return Err("multiple notification responses".into());
            }
            response.truncate(end);
            return Ok(response);
        }
        if Instant::now() >= deadline {
            return Err("notification deadline exceeded".into());
        }
    }
}

fn poll_fd(fd: i32, events: i16, deadline: Instant) -> Result<(), String> {
    let remaining = deadline.saturating_duration_since(Instant::now());
    if remaining.is_zero() {
        return Err("service deadline exceeded".into());
    }
    let millis = remaining.as_millis().min(i32::MAX as u128) as i32;
    let mut descriptor = libc::pollfd {
        fd,
        events,
        revents: 0,
    };
    let result = unsafe { libc::poll(&mut descriptor, 1, millis) };
    if result <= 0 {
        return Err("service poll deadline or error".into());
    }
    if descriptor.revents & (libc::POLLERR | libc::POLLHUP | libc::POLLNVAL) != 0
        && descriptor.revents & events == 0
    {
        return Err("service socket closed".into());
    }
    Ok(())
}

fn connect_nonblocking(path: &Path, deadline: Instant) -> Result<UnixStream, String> {
    use std::os::unix::ffi::OsStrExt;
    let bytes = path.as_os_str().as_bytes();
    if bytes.len() >= 108 || bytes.contains(&0) {
        return Err("notification socket path too long".into());
    }
    let fd = unsafe {
        libc::socket(
            libc::AF_UNIX,
            libc::SOCK_STREAM | libc::SOCK_NONBLOCK | libc::SOCK_CLOEXEC,
            0,
        )
    };
    if fd < 0 {
        return Err("notification socket unavailable".into());
    }
    let mut address: libc::sockaddr_un = unsafe { std::mem::zeroed() };
    address.sun_family = libc::AF_UNIX as libc::sa_family_t;
    for (index, byte) in bytes.iter().enumerate() {
        address.sun_path[index] = *byte as libc::c_char;
    }
    let length = (std::mem::size_of::<libc::sa_family_t>() + bytes.len() + 1) as libc::socklen_t;
    let result =
        unsafe { libc::connect(fd, (&address as *const libc::sockaddr_un).cast(), length) };
    let stream = unsafe { UnixStream::from_raw_fd(fd) };
    if result < 0 {
        let error = std::io::Error::last_os_error();
        if error.raw_os_error() != Some(libc::EINPROGRESS) {
            return Err("notification connect failed".into());
        }
        poll_fd(stream.as_raw_fd(), libc::POLLOUT, deadline)?;
        let mut socket_error = 0i32;
        let mut size = std::mem::size_of::<i32>() as libc::socklen_t;
        if unsafe {
            libc::getsockopt(
                stream.as_raw_fd(),
                libc::SOL_SOCKET,
                libc::SO_ERROR,
                (&mut socket_error as *mut i32).cast(),
                &mut size,
            )
        } < 0
            || socket_error != 0
        {
            return Err("notification connect failed".into());
        }
    }
    let mut credentials: libc::ucred = unsafe { std::mem::zeroed() };
    let mut size = std::mem::size_of::<libc::ucred>() as libc::socklen_t;
    if unsafe {
        libc::getsockopt(
            stream.as_raw_fd(),
            libc::SOL_SOCKET,
            libc::SO_PEERCRED,
            (&mut credentials as *mut libc::ucred).cast(),
            &mut size,
        )
    } < 0
        || credentials.uid != unsafe { libc::geteuid() }
    {
        return Err("foreign notification peer".into());
    }
    Ok(stream)
}

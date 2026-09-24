//! Bounded protocol-1 appearance receiver for the Rust handheld shell.
//!
//! This module owns only transport and validated snapshots. The compositor
//! scene owner must adopt/draw/flush a commit or rollback before `respond(ok)`.

use serde_json::{json, Value};
use std::{
    collections::BTreeMap,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    os::{
        fd::{AsRawFd, RawFd},
        unix::{
            fs::{FileTypeExt, MetadataExt, OpenOptionsExt, PermissionsExt},
            net::{UnixListener, UnixStream},
        },
    },
    path::{Path, PathBuf},
    time::{Duration, Instant},
};

const MAX_LINE: usize = 4096;
const MAX_APPEARANCE: u64 = 256 * 1024;
const MAX_REPORT: u64 = 256 * 1024;
const MAX_SECTIONS: usize = 32;
const MAX_KEYS: usize = 512;
const MAX_BACKGROUNDS: usize = 512;
const PEER_DEADLINE: Duration = Duration::from_secs(2);

#[derive(Clone, Debug, PartialEq)]
pub struct BrushStop {
    pub offset: f64,
    pub argb: String,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Brush {
    pub stops: Vec<BrushStop>,
    pub angle_degrees: f64,
    pub alpha: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub enum AppearanceToken {
    Brush(Brush),
    Width([f64; 4]),
    Number(f64),
    Boolean(bool),
    Raw(Value),
}

#[derive(Clone, Debug, PartialEq)]
pub struct BackgroundChoice {
    pub relative: String,
    pub staged_path: PathBuf,
    pub is_video: bool,
    pub selected: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PaletteColor {
    pub red: u8,
    pub green: u8,
    pub blue: u8,
    pub alpha: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PaletteValue {
    Color(PaletteColor),
    Light,
    Dark,
}

#[derive(Clone, Debug, PartialEq)]
pub struct AppearanceSnapshot {
    pub generation: String,
    pub path: PathBuf,
    pub icon_theme: Option<String>,
    pub background: Option<PathBuf>,
    pub selected_background: Option<PathBuf>,
    pub backgrounds: Vec<BackgroundChoice>,
    pub palette: BTreeMap<String, PaletteValue>,
    pub sections: BTreeMap<String, BTreeMap<String, AppearanceToken>>,
    pub applied: Vec<String>,
    pub unavailable: Vec<String>,
    pub unknown: Vec<String>,
}

impl AppearanceSnapshot {
    pub fn token(&self, section: &str, key: &str) -> Option<&AppearanceToken> {
        self.sections.get(section)?.get(key)
    }

    pub fn palette_color(&self, key: &str) -> Option<PaletteColor> {
        match self.palette.get(key)? {
            PaletteValue::Color(color) => Some(*color),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AppearancePhase {
    Prepare,
    Commit,
    Rollback,
}

#[derive(Clone, Debug)]
pub struct AppearanceEvent {
    pub phase: AppearancePhase,
    pub requested_generation: Option<String>,
    pub snapshot: Option<AppearanceSnapshot>,
    serial: u64,
}

struct Peer {
    stream: UnixStream,
    bytes: Vec<u8>,
    deadline: Instant,
}

pub struct AppearanceReceiver {
    listener: UnixListener,
    peer: Option<Peer>,
    pending: Option<u64>,
    serial: u64,
    socket_path: PathBuf,
    _lock: File,
    generation_root: PathBuf,
    default_path: Option<PathBuf>,
    prepared: Option<AppearanceSnapshot>,
    active: Option<AppearanceSnapshot>,
}

fn identity(value: &str) -> bool {
    value.len() == 24
        && value
            .bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

fn icon_name(value: &str) -> bool {
    let mut bytes = value.bytes();
    value.len() <= 160
        && bytes.next().is_some_and(|b| b.is_ascii_alphanumeric())
        && bytes.all(|b| b.is_ascii_alphanumeric() || b"._+-".contains(&b))
}

fn name(value: &str) -> bool {
    !value.is_empty() && value.len() <= 128 && value.chars().all(|c| !c.is_control())
}

fn hex_argb(value: &str) -> bool {
    value.len() == 9 && value.starts_with('#') && value[1..].bytes().all(|b| b.is_ascii_hexdigit())
}

fn palette_value(key: &str, value: &str) -> Result<PaletteValue, String> {
    if key == "mode" || key == "theme_type" {
        return match value {
            "light" => Ok(PaletteValue::Light),
            "dark" => Ok(PaletteValue::Dark),
            _ => Err("invalid palette mode".into()),
        };
    }
    // Omarchy permits Hyprland-only border values in rgba(RRGGBBAA)/
    // rgb(RRGGBB) syntax, and several built-in themes (hackerman,
    // last-horizon, solitude) set these two keys to a multi-stop gradient,
    // e.g. "rgba(26a269ee) rgba(2ec27eee) 45deg". They are still colors,
    // but are not written as #RRGGBBAA in the resolved palette. This flat
    // map holds one representative color per key; the full gradient (every
    // stop and the angle) is preserved and rendered separately through the
    // resolved shell.toml brush tokens. Limit this spelling to those two
    // source keys; other shell roles must remain strict hexadecimal colors.
    let hex = if let Some(hex) = value.strip_prefix('#') {
        hex
    } else if key == "hyprland_active_border" || key == "hyprland_inactive_border" {
        let first = value
            .split_whitespace()
            .find(|part| part.starts_with("rgba(") || part.starts_with("rgb("))
            .ok_or("invalid palette color")?;
        // "rgba(...)" promises an alpha byte and "rgb(...)" does not; keep
        // that distinction exact instead of accepting either length for both.
        let (hex, expected_len) = if let Some(inner) = first.strip_prefix("rgba(") {
            (inner.strip_suffix(')'), 8)
        } else {
            (
                first.strip_prefix("rgb(").and_then(|inner| inner.strip_suffix(')')),
                6,
            )
        };
        let hex = hex.ok_or("invalid palette color")?;
        if hex.len() != expected_len {
            return Err("invalid palette color".into());
        }
        hex
    } else {
        return Err("invalid palette color".into());
    };
    if !matches!(hex.len(), 6 | 8) || !hex.bytes().all(|c| c.is_ascii_hexdigit()) {
        return Err("invalid palette color".into());
    }
    let component = |start| u8::from_str_radix(&hex[start..start + 2], 16).unwrap();
    Ok(PaletteValue::Color(PaletteColor {
        red: component(0),
        green: component(2),
        blue: component(4),
        alpha: if hex.len() == 8 { component(6) } else { 255 },
    }))
}

fn number(value: &Value, low: f64, high: f64) -> Result<f64, String> {
    let n = value.as_f64().ok_or("appearance number is not numeric")?;
    if !n.is_finite() || !(low..=high).contains(&n) {
        return Err("appearance number out of range".into());
    }
    Ok(n)
}

fn token(value: &Value) -> Result<AppearanceToken, String> {
    let kind = value
        .get("kind")
        .and_then(Value::as_str)
        .ok_or("appearance token has no kind")?;
    match kind {
        "brush" => {
            let list = value
                .get("stops")
                .and_then(Value::as_array)
                .ok_or("brush has no stops")?;
            if !(1..=4).contains(&list.len()) {
                return Err("brush stop count out of range".into());
            }
            let mut stops = Vec::with_capacity(list.len());
            let mut last = -1.0;
            for stop in list {
                let argb = stop
                    .get("argb")
                    .and_then(Value::as_str)
                    .ok_or("brush stop has no color")?;
                if !hex_argb(argb) {
                    return Err("invalid brush ARGB color".into());
                }
                let offset = number(
                    stop.get("offset").ok_or("brush stop has no offset")?,
                    0.0,
                    1.0,
                )?;
                if offset < last {
                    return Err("brush offsets out of order".into());
                }
                last = offset;
                stops.push(BrushStop {
                    offset,
                    argb: argb.to_owned(),
                });
            }
            Ok(AppearanceToken::Brush(Brush {
                stops,
                angle_degrees: number(
                    value.get("angle_degrees").ok_or("brush has no angle")?,
                    -3600.0,
                    3600.0,
                )?,
                alpha: number(value.get("alpha").ok_or("brush has no alpha")?, 0.0, 1.0)?,
            }))
        }
        "width" => {
            let values = value
                .get("value")
                .and_then(Value::as_array)
                .ok_or("width has no values")?;
            if values.len() != 4 {
                return Err("width needs four sides".into());
            }
            let mut sides = [0.0; 4];
            for (index, item) in values.iter().enumerate() {
                sides[index] = number(item, 0.0, 128.0)?;
            }
            Ok(AppearanceToken::Width(sides))
        }
        "number" => Ok(AppearanceToken::Number(number(
            value.get("value").ok_or("number has no value")?,
            -10000.0,
            10000.0,
        )?)),
        "boolean" => Ok(AppearanceToken::Boolean(
            value
                .get("value")
                .and_then(Value::as_bool)
                .ok_or("boolean has no value")?,
        )),
        "raw" => {
            let raw = value.get("value").ok_or("raw token has no value")?;
            Ok(AppearanceToken::Raw(raw.clone()))
        }
        _ => Err("unknown appearance token kind".into()),
    }
}

fn bounded_json(path: &Path, limit: u64) -> Result<Value, String> {
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)
        .map_err(|e| e.to_string())?;
    let meta = file.metadata().map_err(|e| e.to_string())?;
    if !meta.file_type().is_file() || meta.len() > limit {
        return Err("invalid appearance file".into());
    }
    let mut bytes = Vec::new();
    file.take(limit + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() as u64 > limit {
        return Err("appearance file exceeded read bound".into());
    }
    serde_json::from_slice(&bytes).map_err(|_| "malformed appearance JSON".into())
}

fn text_list(report: &Value, key: &str) -> Result<Vec<String>, String> {
    let Some(value) = report.get(key) else {
        return Ok(Vec::new());
    };
    let list = value.as_array().ok_or("invalid compatibility list")?;
    if list.len() > MAX_BACKGROUNDS {
        return Err("compatibility list exceeds bound".into());
    }
    list.iter()
        .map(|item| {
            let text = item.as_str().ok_or("invalid compatibility item")?;
            if text.len() > 512 {
                return Err("compatibility item exceeds bound".into());
            }
            Ok(text.to_owned())
        })
        .collect()
}

fn background_relative(value: &str) -> bool {
    let Some(rest) = value.strip_prefix("backgrounds/") else {
        return false;
    };
    !rest.is_empty()
        && rest.len() <= 255
        && rest != "."
        && rest != ".."
        && !rest.contains('/')
        && !rest.contains('\0')
}

fn load_snapshot(
    path: &Path,
    expected: &str,
    root: &Path,
    default: Option<&Path>,
) -> Result<AppearanceSnapshot, String> {
    if !identity(expected) || !path.is_absolute() {
        return Err("invalid generation identity/path".into());
    }
    if fs::symlink_metadata(path)
        .map_err(|e| e.to_string())?
        .file_type()
        .is_symlink()
    {
        return Err("generation path is a symlink".into());
    }
    let canonical = path.canonicalize().map_err(|e| e.to_string())?;
    if canonical.file_name().and_then(|n| n.to_str()) != Some(expected) {
        return Err("generation path/id mismatch".into());
    }
    let allowed_default = default.is_some_and(|p| canonical == p);
    if !allowed_default {
        let cache = root
            .join("generations")
            .canonicalize()
            .map_err(|e| e.to_string())?;
        if canonical.parent() != Some(cache.as_path()) {
            return Err("generation outside private cache".into());
        }
    }
    let appearance = bounded_json(&canonical.join("appearance.json"), MAX_APPEARANCE)?;
    let report = bounded_json(&canonical.join("report.json"), MAX_REPORT)?;
    if appearance.get("version").and_then(Value::as_u64) != Some(1)
        || appearance.get("generation").and_then(Value::as_str) != Some(expected)
        || report.get("generation").and_then(Value::as_str) != Some(expected)
    {
        return Err("appearance generation identity mismatch".into());
    }
    let icon_theme = match appearance.get("icon_theme") {
        Some(Value::String(value)) if icon_name(value) => Some(value.clone()),
        Some(Value::Null) | None => None,
        _ => return Err("invalid icon theme".into()),
    };
    if let Some(report_icon) = report.get("icon_theme") {
        if report_icon.as_str() != icon_theme.as_deref() {
            return Err("icon theme report mismatch".into());
        }
    }
    let palette_value_map = report
        .get("palette")
        .and_then(Value::as_object)
        .ok_or("missing report palette")?;
    if palette_value_map.len() > MAX_KEYS {
        return Err("report palette exceeds bound".into());
    }
    let mut palette = BTreeMap::new();
    for (key, value) in palette_value_map {
        if !name(key) {
            return Err("invalid palette key".into());
        }
        let value = value.as_str().ok_or("invalid palette value")?;
        palette.insert(key.clone(), palette_value(key, value)?);
    }
    for required in ["background", "foreground", "accent"] {
        if !matches!(palette.get(required), Some(PaletteValue::Color(_))) {
            return Err("report palette lacks a required color".into());
        }
    }
    let sections_value = appearance
        .get("sections")
        .and_then(Value::as_object)
        .ok_or("missing appearance sections")?;
    if sections_value.len() > MAX_SECTIONS {
        return Err("appearance section count exceeds bound".into());
    }
    let mut sections = BTreeMap::new();
    let mut total = 0usize;
    for (section_name, fields) in sections_value {
        if !name(section_name) {
            return Err("invalid appearance section name".into());
        }
        let fields = fields.as_object().ok_or("invalid appearance section")?;
        total += fields.len();
        if total > MAX_KEYS {
            return Err("appearance token count exceeds bound".into());
        }
        let mut typed = BTreeMap::new();
        for (key, value) in fields {
            if !name(key) {
                return Err("invalid appearance token name".into());
            }
            typed.insert(key.clone(), token(value)?);
        }
        sections.insert(section_name.clone(), typed);
    }
    let choices = report
        .get("backgrounds")
        .and_then(Value::as_array)
        .ok_or("missing background list")?;
    if choices.len() > MAX_BACKGROUNDS {
        return Err("background list exceeds bound".into());
    }
    let selected = report.get("selected_background").and_then(Value::as_str);
    let mut backgrounds = Vec::new();
    for choice in choices {
        let relative = choice.as_str().ok_or("invalid background name")?;
        if !background_relative(relative) {
            return Err("background escapes staged theme".into());
        }
        let asset = canonical.join("theme").join(relative);
        let meta = fs::symlink_metadata(&asset).map_err(|e| e.to_string())?;
        if !meta.file_type().is_file() || meta.len() > 256 * 1024 * 1024 {
            return Err("invalid background asset".into());
        }
        let canonical_asset = asset.canonicalize().map_err(|e| e.to_string())?;
        if canonical_asset.parent() != Some(canonical.join("theme/backgrounds").as_path()) {
            return Err("background escapes staged theme".into());
        }
        let suffix = Path::new(relative)
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        let is_video = matches!(
            suffix.as_str(),
            "mp4" | "m4v" | "mov" | "webm" | "mkv" | "avi"
        );
        backgrounds.push(BackgroundChoice {
            relative: relative.to_owned(),
            staged_path: canonical_asset,
            is_video,
            selected: selected == Some(relative),
        });
    }
    if selected.is_some() && !backgrounds.iter().any(|b| b.selected) {
        return Err("selected background missing".into());
    }
    let background = match appearance.get("background") {
        Some(Value::String(value)) if value == "background" => {
            let choice = backgrounds
                .iter()
                .find(|b| b.selected && !b.is_video)
                .ok_or("still background mismatch")?;
            Some(choice.staged_path.clone())
        }
        Some(Value::Null) | None => None,
        _ => return Err("invalid selected background path".into()),
    };
    if background.is_none() && backgrounds.iter().any(|b| b.selected && !b.is_video) {
        return Err("selected still background missing from appearance".into());
    }
    let selected_background = backgrounds
        .iter()
        .find(|b| b.selected)
        .map(|b| b.staged_path.clone());
    Ok(AppearanceSnapshot {
        generation: expected.to_owned(),
        path: canonical,
        icon_theme,
        background,
        selected_background,
        backgrounds,
        palette,
        sections,
        applied: text_list(&report, "applied")?,
        unavailable: text_list(&report, "unavailable")?,
        unknown: text_list(&report, "unknown")?,
    })
}

fn selected_snapshot(root: &Path) -> Option<AppearanceSnapshot> {
    let pointer = root.join("active");
    if !fs::symlink_metadata(&pointer)
        .ok()?
        .file_type()
        .is_symlink()
    {
        return None;
    }
    let target = pointer.canonicalize().ok()?;
    let id = target.file_name()?.to_str()?;
    // The active pointer may select only an immutable generation within the
    // private cache. Invalid/stale pointers fall back to the pinned default.
    load_snapshot(&target, id, root, None).ok()
}

fn request_pair(
    value: &Value,
    generation_key: &str,
    path_key: &str,
) -> Result<(Option<String>, Option<PathBuf>), String> {
    let generation = match value.get(generation_key) {
        Some(Value::String(text)) if identity(text) => Some(text.clone()),
        Some(Value::Null) | None => None,
        _ => return Err("invalid request generation".into()),
    };
    let path = match value.get(path_key) {
        Some(Value::String(text)) if !text.is_empty() && text.len() <= 4096 => {
            Some(PathBuf::from(text))
        }
        Some(Value::Null) | None => None,
        _ => return Err("invalid request path".into()),
    };
    if generation.is_some() != path.is_some() {
        return Err("generation/path pair mismatch".into());
    }
    Ok((generation, path))
}

impl AppearanceReceiver {
    /// Bind the private theme endpoint. The user cache root matches the Python
    /// coordinator; a Nix service may set `K230_THEME_STATE_ROOT` explicitly.
    pub fn bind(socket_path: PathBuf, default_generation: Option<PathBuf>) -> Result<Self, String> {
        let root = std::env::var_os("K230_THEME_STATE_ROOT")
            .map(PathBuf::from)
            .or_else(|| {
                std::env::var_os("HOME")
                    .map(|home| PathBuf::from(home).join(".local/state/omarchy/current"))
            })
            .ok_or("theme state root is unset")?;
        Self::bind_with_roots(socket_path, default_generation, root)
    }

    pub fn bind_with_roots(
        socket_path: PathBuf,
        default_generation: Option<PathBuf>,
        generation_root: PathBuf,
    ) -> Result<Self, String> {
        let runtime = socket_path
            .parent()
            .ok_or("appearance socket has no parent")?;
        let meta = fs::symlink_metadata(runtime).map_err(|e| e.to_string())?;
        if !meta.file_type().is_dir()
            || meta.uid() != unsafe { libc::geteuid() }
            || meta.permissions().mode() & 0o077 != 0
        {
            return Err("appearance runtime directory must be private and owned".into());
        }
        if !generation_root.is_absolute() {
            return Err("theme state root must be absolute".into());
        }
        let default_path = match default_generation {
            Some(path) => Some(path.canonicalize().map_err(|e| e.to_string())?),
            None => None,
        };
        let default_snapshot = match &default_path {
            Some(path) => {
                let identity = path
                    .file_name()
                    .and_then(|part| part.to_str())
                    .ok_or("invalid pinned default path")?;
                Some(load_snapshot(path, identity, &generation_root, Some(path))?)
            }
            None => None,
        };
        let lock_path = socket_path.with_extension("lock");
        let lock = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(lock_path)
            .map_err(|e| e.to_string())?;
        if unsafe { libc::flock(lock.as_raw_fd(), libc::LOCK_EX | libc::LOCK_NB) } != 0 {
            return Err("appearance receiver is already running".into());
        }
        if let Ok(existing) = fs::symlink_metadata(&socket_path) {
            if !existing.file_type().is_socket() || existing.uid() != unsafe { libc::geteuid() } {
                return Err("unsafe appearance socket exists".into());
            }
            fs::remove_file(&socket_path).map_err(|e| e.to_string())?;
        }
        let old_mask = unsafe { libc::umask(0o077) };
        let bound = UnixListener::bind(&socket_path);
        unsafe { libc::umask(old_mask) };
        let listener = bound.map_err(|e| e.to_string())?;
        fs::set_permissions(&socket_path, fs::Permissions::from_mode(0o600))
            .map_err(|e| e.to_string())?;
        listener.set_nonblocking(true).map_err(|e| e.to_string())?;
        let active = selected_snapshot(&generation_root).or(default_snapshot);
        Ok(Self {
            listener,
            peer: None,
            pending: None,
            serial: 0,
            socket_path,
            _lock: lock,
            generation_root,
            default_path,
            prepared: None,
            active,
        })
    }

    pub fn listener_fd(&self) -> RawFd {
        self.listener.as_raw_fd()
    }
    pub fn peer_fd(&self) -> Option<RawFd> {
        self.peer.as_ref().map(|peer| peer.stream.as_raw_fd())
    }
    pub fn active(&self) -> Option<&AppearanceSnapshot> {
        self.active.as_ref()
    }
    pub fn prepared(&self) -> Option<&AppearanceSnapshot> {
        self.prepared.as_ref()
    }

    pub fn accept(&mut self) -> Result<(), String> {
        if self.peer.is_some() {
            return Ok(());
        }
        match self.listener.accept() {
            Ok((stream, _)) => {
                let mut credentials: libc::ucred = unsafe { std::mem::zeroed() };
                let mut length = std::mem::size_of::<libc::ucred>() as libc::socklen_t;
                let checked = unsafe {
                    libc::getsockopt(
                        stream.as_raw_fd(),
                        libc::SOL_SOCKET,
                        libc::SO_PEERCRED,
                        &mut credentials as *mut _ as *mut libc::c_void,
                        &mut length,
                    )
                };
                if checked != 0 || credentials.uid != unsafe { libc::geteuid() } {
                    return Err("appearance peer has wrong UID".into());
                }
                stream.set_nonblocking(true).map_err(|e| e.to_string())?;
                self.peer = Some(Peer {
                    stream,
                    bytes: Vec::new(),
                    deadline: Instant::now() + PEER_DEADLINE,
                });
                Ok(())
            }
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => Ok(()),
            Err(error) => Err(error.to_string()),
        }
    }

    pub fn receive(&mut self) -> Result<Option<AppearanceEvent>, String> {
        // `PEER_DEADLINE` bounds how long a peer may take to finish sending
        // one well-formed request; it is not a bound on how long the scene
        // owner may take to act on a request already parsed. Once a request
        // is pending, the caller (main.rs's event loop) legitimately keeps
        // calling `receive()` every tick while it decodes/renders and waits
        // for a free buffer -- a bounded but nonzero delay of its own,
        // tracked independently by the caller. Checking the transport
        // deadline here too would silently clear `peer`/`pending` out from
        // under a commit/rollback that is still genuinely in progress, so
        // the eventual `respond()` for that same event fails as a "stale
        // appearance event" even though the peer never disconnected and the
        // shell never gave up. Only a peer that has NOT yet delivered a
        // complete request can be considered stalled here; once fully
        // parsed and handed off, `respond()`'s own write-side deadline is
        // what protects against a peer that stops reading the ack.
        if self.pending.is_some() {
            return Ok(None);
        }
        if self
            .peer
            .as_ref()
            .is_some_and(|peer| Instant::now() >= peer.deadline)
        {
            self.peer = None;
            self.pending = None;
            return Err("appearance peer timed out".into());
        }
        let Some(peer) = self.peer.as_mut() else {
            return Ok(None);
        };
        let mut chunk = [0u8; 512];
        loop {
            match peer.stream.read(&mut chunk) {
                Ok(0) => {
                    self.peer = None;
                    return Err("appearance peer closed".into());
                }
                Ok(count) => {
                    peer.bytes.extend_from_slice(&chunk[..count]);
                    if peer.bytes.len() > MAX_LINE {
                        self.peer = None;
                        return Err("appearance request exceeds bound".into());
                    }
                    if let Some(end) = peer.bytes.iter().position(|b| *b == b'\n') {
                        if end + 1 != peer.bytes.len() {
                            self.peer = None;
                            return Err("appearance request has trailing data".into());
                        }
                        let bytes = peer.bytes[..end].to_vec();
                        let request: Value = match serde_json::from_slice(&bytes) {
                            Ok(value) => value,
                            Err(_) => {
                                self.peer = None;
                                return Err("malformed appearance request".into());
                            }
                        };
                        let event = match self.parse_request(&request) {
                            Ok(event) => event,
                            Err(error) => {
                                self.peer = None;
                                return Err(error);
                            }
                        };
                        self.serial = self.serial.wrapping_add(1);
                        self.pending = Some(self.serial);
                        return Ok(Some(AppearanceEvent {
                            serial: self.serial,
                            ..event
                        }));
                    }
                }
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => return Ok(None),
                Err(error) => {
                    self.peer = None;
                    return Err(error.to_string());
                }
            }
        }
    }

    fn parse_request(&self, request: &Value) -> Result<AppearanceEvent, String> {
        if request.get("protocol").and_then(Value::as_u64) != Some(1) {
            return Err("unsupported appearance protocol".into());
        }
        let phase = match request.get("phase").and_then(Value::as_str) {
            Some("prepare") => AppearancePhase::Prepare,
            Some("commit") => AppearancePhase::Commit,
            Some("rollback") => AppearancePhase::Rollback,
            _ => return Err("invalid appearance phase".into()),
        };
        let (generation, path) = request_pair(request, "generation", "path")?;
        if phase == AppearancePhase::Prepare {
            let (previous, previous_path) =
                request_pair(request, "previous_generation", "previous_path")?;
            if let (Some(id), Some(path)) = (previous, previous_path) {
                load_snapshot(
                    &path,
                    &id,
                    &self.generation_root,
                    self.default_path.as_deref(),
                )?;
            }
        } else if request.get("previous_generation").is_some()
            || request.get("previous_path").is_some()
        {
            return Err("unexpected previous generation fields".into());
        }
        let snapshot = match phase {
            AppearancePhase::Prepare => {
                let (id, path) = (
                    generation.as_deref().ok_or("prepare has no generation")?,
                    path.as_deref().ok_or("prepare has no path")?,
                );
                Some(load_snapshot(
                    path,
                    id,
                    &self.generation_root,
                    self.default_path.as_deref(),
                )?)
            }
            AppearancePhase::Commit => {
                let (id, path) = (
                    generation.as_deref().ok_or("commit has no generation")?,
                    path.as_deref().ok_or("commit has no path")?,
                );
                let staged = self.prepared.as_ref().ok_or("commit without prepare")?;
                if staged.generation != id
                    || staged.path != path.canonicalize().map_err(|e| e.to_string())?
                {
                    return Err("commit does not match prepared generation".into());
                }
                Some(staged.clone())
            }
            AppearancePhase::Rollback => match (generation.as_deref(), path.as_deref()) {
                (Some(id), Some(path)) => Some(load_snapshot(
                    path,
                    id,
                    &self.generation_root,
                    self.default_path.as_deref(),
                )?),
                (None, None) => self
                    .default_path
                    .as_ref()
                    .map(|path| {
                        let id = path
                            .file_name()
                            .and_then(|part| part.to_str())
                            .unwrap_or("");
                        load_snapshot(
                            path,
                            id,
                            &self.generation_root,
                            self.default_path.as_deref(),
                        )
                    })
                    .transpose()?,
                _ => return Err("invalid rollback generation".into()),
            },
        };
        Ok(AppearanceEvent {
            phase,
            requested_generation: generation,
            snapshot,
            serial: 0,
        })
    }

    /// Call only after the scene owner accepts prepare or adopts and flushes
    /// the commit/rollback snapshot. Idle ACK is in-memory adoption, not panel
    /// presentation proof.
    pub fn respond(&mut self, event: AppearanceEvent, accepted: bool) -> Result<(), String> {
        if self.pending != Some(event.serial) {
            return Err("stale appearance event".into());
        }
        let mut peer = self.peer.take().ok_or("appearance peer disappeared")?;
        self.pending = None;
        if accepted {
            match event.phase {
                AppearancePhase::Prepare => self.prepared = event.snapshot.clone(),
                AppearancePhase::Commit | AppearancePhase::Rollback => {
                    self.active = event.snapshot.clone();
                    self.prepared = None;
                }
            }
        }
        let phase = match event.phase {
            AppearancePhase::Prepare => "prepare",
            AppearancePhase::Commit => "commit",
            AppearancePhase::Rollback => "rollback",
        };
        let reply = json!({"protocol": 1, "phase": phase,
                           "generation": event.requested_generation,
                           "status": if accepted { "ok" } else { "error" }});
        let mut bytes = serde_json::to_vec(&reply).map_err(|e| e.to_string())?;
        bytes.push(b'\n');
        let deadline = Instant::now() + Duration::from_millis(250);
        let mut sent = 0;
        while sent < bytes.len() {
            match peer.stream.write(&bytes[sent..]) {
                Ok(0) => return Err("appearance ACK peer closed".into()),
                Ok(count) => sent += count,
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                    let remaining = deadline.saturating_duration_since(Instant::now());
                    if remaining.is_zero() {
                        return Err("appearance ACK timed out".into());
                    }
                    let mut pollfd = libc::pollfd {
                        fd: peer.stream.as_raw_fd(),
                        events: libc::POLLOUT,
                        revents: 0,
                    };
                    let result = unsafe {
                        libc::poll(
                            &mut pollfd,
                            1,
                            remaining.as_millis().min(i32::MAX as u128) as i32,
                        )
                    };
                    if result <= 0 {
                        return Err("appearance ACK timed out".into());
                    }
                }
                Err(error) => return Err(error.to_string()),
            }
        }
        Ok(())
    }
}

impl Drop for AppearanceReceiver {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.socket_path);
    }
}

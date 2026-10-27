//! The shell's side of the nRF9151 modem service (`nix/k230-modem`): it reads
//! `state.json`, tails the stored-message file for new texts, and writes
//! one-line commands to the control socket. Nothing here speaks AT.
//!
//! Everything cellular stays hidden until the service reports `present`
//! (the modem answered once), so a board without the keyboard base shows
//! no Cellular or Location UI at all.
//!
//! A SIM PIN and a message body are secrets of this module: both types print
//! as `<redacted>` in `Debug`, no log line mentions either, and the only
//! places they leave are the control socket (the PIN) and the notification
//! broker (the body).

use serde_json::Value;
use std::{
    collections::hash_map::DefaultHasher,
    fs,
    hash::{Hash, Hasher},
    io::{Read, Write},
    net::Shutdown,
    os::unix::{fs::MetadataExt, net::UnixStream},
    path::{Path, PathBuf},
    sync::mpsc::{self, Receiver, SyncSender, TrySendError},
    thread,
    time::Duration,
};

pub const STATE_PATH: &str = "/run/k230/modem/state.json";
pub const CONTROL_PATH: &str = "/run/k230/modem/control";
/// The service's bounded store of received texts, one JSON object per line.
pub const SMS_PATH: &str = "/var/lib/k230-modem/sms.jsonl";

const MAX_STATE: u64 = 8 * 1024;
const MAX_SMS_FILE: u64 = 256 * 1024;
/// Texts announced per poll; a flood is capped rather than flooding the shade.
const MAX_ANNOUNCED: usize = 8;
const QUEUE: usize = 4;
/// A PIN or power change waits on the radio; the service answers when done.
const REPLY_DEADLINE: Duration = Duration::from_secs(60);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Power {
    Off,
    PoweringOn,
    On,
    PoweringOff,
    Error,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Sim {
    Unknown,
    Absent,
    PinRequired,
    PukRequired,
    Ready,
    Error,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Registration {
    Unknown,
    NotRegistered,
    RegisteredHome,
    Searching,
    Denied,
    RegisteredRoaming,
    SimFailure,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Gnss {
    Off,
    Searching,
    Fix,
}

/// What the shade's signal glyph shows while Cellular is on.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CellularIndicator {
    NoService,
    /// 0..=4 lit bars.
    Bars(u8),
}

/// What the shade's location glyph shows while Location is on.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LocationIndicator {
    Searching,
    Fix,
}

/// The service's published state, only ever built from a `present` file.
/// Deliberately has no position: the service never publishes one.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ModemStatus {
    pub power: Power,
    pub cellular: bool,
    pub location: bool,
    pub sim: Sim,
    pub pin_attempts: Option<u8>,
    pub registration: Registration,
    pub operator: Option<String>,
    pub rat: Option<String>,
    pub bars: u8,
    pub gnss: Gnss,
    pub sms_count: u32,
    pub last_error: Option<String>,
}

fn word(value: Option<&Value>) -> &str {
    value.and_then(Value::as_str).unwrap_or("")
}

fn short_text(value: Option<&Value>, limit: usize) -> Option<String> {
    let text: String = value?.as_str()?.chars().filter(|c| !c.is_control()).take(limit).collect();
    let text = text.trim().to_string();
    (!text.is_empty()).then_some(text)
}

/// Parses `state.json`. `None` for anything but a well-formed file of a known
/// schema in which the modem has answered.
pub fn parse_status(bytes: &[u8]) -> Option<ModemStatus> {
    if bytes.len() as u64 > MAX_STATE {
        return None;
    }
    let data: Value = serde_json::from_slice(bytes).ok()?;
    if data.get("schema")?.as_u64()? < 1 || data.get("present")?.as_bool() != Some(true) {
        return None;
    }
    let flag = |key: &str| data.get(key).and_then(Value::as_bool).unwrap_or(false);
    Some(ModemStatus {
        power: match word(data.get("power")) {
            "on" => Power::On,
            "powering_on" => Power::PoweringOn,
            "powering_off" => Power::PoweringOff,
            "error" => Power::Error,
            _ => Power::Off,
        },
        cellular: flag("cellular"),
        location: flag("location"),
        sim: match word(data.get("sim")) {
            "absent" => Sim::Absent,
            "pin_required" => Sim::PinRequired,
            "puk_required" => Sim::PukRequired,
            "ready" => Sim::Ready,
            "error" => Sim::Error,
            _ => Sim::Unknown,
        },
        pin_attempts: data
            .get("pin_attempts")
            .and_then(Value::as_u64)
            .map(|n| n.min(99) as u8),
        registration: match word(data.get("registration")) {
            "not_registered" => Registration::NotRegistered,
            "registered_home" => Registration::RegisteredHome,
            "searching" => Registration::Searching,
            "denied" => Registration::Denied,
            "registered_roaming" => Registration::RegisteredRoaming,
            "sim_failure" => Registration::SimFailure,
            _ => Registration::Unknown,
        },
        operator: short_text(data.get("operator"), 32),
        rat: short_text(data.get("rat"), 16),
        bars: data.get("bars").and_then(Value::as_u64).unwrap_or(0).min(4) as u8,
        gnss: match word(data.get("gnss")) {
            "searching" => Gnss::Searching,
            "fix" => Gnss::Fix,
            _ => Gnss::Off,
        },
        sms_count: data.get("sms_count").and_then(Value::as_u64).unwrap_or(0).min(u64::from(u32::MAX)) as u32,
        last_error: short_text(data.get("last_error"), 48),
    })
}

/// The file at `path`, or `None` (missing, unreadable, not yet answered).
pub fn read_status(path: &Path) -> Option<ModemStatus> {
    let file = fs::File::open(path).ok()?;
    let mut bytes = Vec::new();
    file.take(MAX_STATE + 1).read_to_end(&mut bytes).ok()?;
    parse_status(&bytes)
}

impl ModemStatus {
    pub fn registered(&self) -> bool {
        matches!(self.registration, Registration::RegisteredHome | Registration::RegisteredRoaming)
    }

    /// The shade's signal glyph; `None` while Cellular is off.
    pub fn cellular_indicator(&self) -> Option<CellularIndicator> {
        self.cellular.then(|| {
            if self.registered() {
                CellularIndicator::Bars(self.bars.min(4))
            } else {
                CellularIndicator::NoService
            }
        })
    }

    /// The shade's location glyph; `None` while Location is off. Location on
    /// is searching until the service reports a fix.
    pub fn location_indicator(&self) -> Option<LocationIndicator> {
        self.location.then(|| {
            if self.gnss == Gnss::Fix {
                LocationIndicator::Fix
            } else {
                LocationIndicator::Searching
            }
        })
    }

    /// The Cellular page asks for a PIN only while the radio is up and the
    /// SIM says so.
    pub fn pin_needed(&self) -> bool {
        self.cellular && self.sim == Sim::PinRequired
    }

    pub fn sim_label(&self) -> &'static str {
        match self.sim {
            Sim::Absent => "No SIM",
            Sim::PinRequired => "PIN required",
            Sim::PukRequired => "Locked (PUK needed)",
            Sim::Ready => "Ready",
            Sim::Error => "SIM error",
            // GNSS alone powers the modem without reading the SIM.
            Sim::Unknown if self.power == Power::On && self.cellular => "Reading…",
            Sim::Unknown if self.cellular => "Not read",
            Sim::Unknown => "—",
        }
    }

    pub fn registration_label(&self) -> &'static str {
        match self.registration {
            Registration::NotRegistered => "Not registered",
            Registration::RegisteredHome => "Registered",
            Registration::Searching => "Searching…",
            Registration::Denied => "Denied",
            Registration::RegisteredRoaming => "Roaming",
            Registration::SimFailure => "SIM failure",
            Registration::Unknown => "—",
        }
    }

    pub fn signal_label(&self) -> &'static str {
        if !self.registered() {
            return "No signal";
        }
        match self.bars {
            0 => "No signal",
            1 => "Weak",
            2 => "Fair",
            3 => "Good",
            _ => "Excellent",
        }
    }

    /// The Settings row's one-line value for Cellular.
    pub fn cellular_summary(&self) -> String {
        if !self.cellular {
            return "Off".into();
        }
        if self.power != Power::On {
            return if self.power == Power::Error { "Modem error".into() } else { "Starting…".into() };
        }
        match self.sim {
            Sim::Absent | Sim::PinRequired | Sim::PukRequired | Sim::Error => self.sim_label().into(),
            _ if self.registered() => match (&self.operator, &self.rat) {
                (Some(operator), Some(rat)) => format!("{operator} · {rat}"),
                (Some(operator), None) => operator.clone(),
                _ => self.registration_label().into(),
            },
            _ => match self.registration {
                Registration::Unknown => "On".into(),
                _ => self.registration_label().into(),
            },
        }
    }

    pub fn location_label(&self) -> &'static str {
        match self.location_indicator() {
            None => "Off",
            Some(LocationIndicator::Searching) => "Searching…",
            Some(LocationIndicator::Fix) => "Fix",
        }
    }
}

/// A SIM PIN on its way to the control socket.
#[derive(Clone, Eq, PartialEq)]
pub struct Pin(String);

impl Pin {
    /// 4 to 8 ASCII digits, as the service requires.
    pub fn new(digits: &str) -> Option<Pin> {
        ((4..=8).contains(&digits.len()) && digits.bytes().all(|b| b.is_ascii_digit()))
            .then(|| Pin(digits.to_string()))
    }
}

impl std::fmt::Debug for Pin {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("Pin(<redacted>)")
    }
}

/// A received text's body. Only the notification it becomes may show it.
pub use crate::service_data::SecretText as Body;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Kind {
    Cellular,
    Location,
    Pin,
    ClearMessages,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Command {
    Cellular(bool),
    Location(bool),
    SubmitPin(Pin),
    ClearMessages,
}

impl Command {
    pub fn kind(&self) -> Kind {
        match self {
            Command::Cellular(_) => Kind::Cellular,
            Command::Location(_) => Kind::Location,
            Command::SubmitPin(_) => Kind::Pin,
            Command::ClearMessages => Kind::ClearMessages,
        }
    }

    /// The request line, newline included. The PIN's digits exist only in
    /// this buffer on their way to the socket.
    fn wire(&self) -> Vec<u8> {
        match self {
            Command::Cellular(on) => format!("power {}\n", if *on { "on" } else { "off" }).into_bytes(),
            Command::Location(on) => format!("gnss {}\n", if *on { "on" } else { "off" }).into_bytes(),
            Command::SubmitPin(pin) => format!("pin {}\n", pin.0).into_bytes(),
            Command::ClearMessages => b"sms clear\n".to_vec(),
        }
    }
}

/// The service's one-line reply as a result carrying a fixed, printable
/// reason. Replies never repeat request arguments, and only the code word is
/// kept.
pub fn parse_reply(reply: &str) -> Result<(), String> {
    let reply = reply.trim();
    if reply == "ok" || reply.starts_with("ok ") {
        return Ok(());
    }
    let code = reply.strip_prefix("err ").unwrap_or("").split(' ').next().unwrap_or("");
    let code: String = code.chars().filter(|c| c.is_ascii_alphanumeric() || *c == '_').take(40).collect();
    Err(if code.is_empty() { "no_reply".into() } else { code })
}

/// What the person reads for a failed request's code.
pub fn failure_text(code: &str) -> &'static str {
    match code {
        "pin_rejected" => "PIN not accepted",
        "bad_pin" => "Enter 4 to 8 digits",
        "cellular_off" => "Turn Cellular on first",
        "store" => "Could not clear messages",
        "unreachable" => "Modem service unavailable",
        c if c.starts_with("modem_") || c.starts_with("pin_failed_") => "The modem did not respond",
        _ => "Request failed",
    }
}

/// Sends `command` to the service at `socket` and waits for its answer.
pub fn send(socket: &Path, command: &Command) -> Result<(), String> {
    let mut stream = UnixStream::connect(socket).map_err(|_| "unreachable".to_string())?;
    let _ = stream.set_read_timeout(Some(REPLY_DEADLINE));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(5)));
    let mut line = command.wire();
    let written = stream.write_all(&line);
    line.fill(0);
    written.map_err(|_| "unreachable".to_string())?;
    let _ = stream.shutdown(Shutdown::Write);
    let mut reply = String::new();
    stream.take(4096).read_to_string(&mut reply).map_err(|_| "no_reply".to_string())?;
    parse_reply(&reply)
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ModemReply {
    pub kind: Kind,
    pub result: Result<(), String>,
}

/// Runs control-socket requests off the Wayland loop, one at a time, with the
/// same `try_submit`/`try_recv` shape as the Wi-Fi worker.
pub struct ModemWorker {
    requests: SyncSender<Command>,
    replies: Receiver<ModemReply>,
}

impl ModemWorker {
    pub fn spawn(socket: PathBuf) -> Self {
        let (requests, incoming) = mpsc::sync_channel::<Command>(QUEUE);
        let (outgoing, replies) = mpsc::sync_channel(QUEUE);
        thread::spawn(move || {
            while let Ok(command) = incoming.recv() {
                let kind = command.kind();
                let result = send(&socket, &command);
                drop(command);
                if outgoing.send(ModemReply { kind, result }).is_err() {
                    break;
                }
            }
        });
        Self { requests, replies }
    }

    pub fn try_submit(&self, command: Command) -> Result<(), &'static str> {
        match self.requests.try_send(command) {
            Ok(()) => Ok(()),
            Err(TrySendError::Full(_)) => Err("modem queue full"),
            Err(TrySendError::Disconnected(_)) => Err("modem worker unavailable"),
        }
    }

    pub fn try_recv(&self) -> Option<ModemReply> {
        self.replies.try_recv().ok()
    }
}

/// One received text from the service's store.
#[derive(Clone, Eq, PartialEq)]
pub struct Text {
    pub from: String,
    pub body: Body,
}

impl std::fmt::Debug for Text {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Text").field("body", &self.body).finish_non_exhaustive()
    }
}

fn parse_text(line: &str) -> Option<Text> {
    let data: Value = serde_json::from_str(line).ok()?;
    let from: String = data.get("from")?.as_str()?.chars().filter(|c| !c.is_control()).take(24).collect();
    let body = data.get("body")?.as_str()?.to_string();
    (!from.is_empty()).then_some(Text { from, body: Body(body) })
}

/// The notification a text becomes: sender in the summary, text in the body.
/// The broker's privacy default (no `private: false`) keeps the body out of
/// the preview and leaves the full text in the shade's history.
pub fn notification_for(text: &Text) -> (String, Body) {
    (format!("Text from {}", text.from), text.body.clone())
}

fn line_hash(line: &str) -> u64 {
    let mut hasher = DefaultHasher::new();
    line.hash(&mut hasher);
    hasher.finish()
}

/// Watches the stored-message file for texts that arrived after the shell
/// started. Texts already stored when it first looks are not announced.
pub struct SmsTail {
    path: PathBuf,
    stamp: Option<(u64, i64, i64, u64)>,
    count: Option<usize>,
    last: u64,
}

impl SmsTail {
    pub fn new(path: PathBuf) -> Self {
        Self { path, stamp: None, count: None, last: 0 }
    }

    /// New texts since the previous poll, oldest first.
    pub fn poll(&mut self) -> Vec<Text> {
        let stamp = fs::metadata(&self.path).ok().map(|m| (m.len(), m.mtime(), m.mtime_nsec(), m.ino()));
        if stamp == self.stamp && self.count.is_some() {
            return Vec::new();
        }
        self.stamp = stamp;
        let lines: Vec<String> = match stamp {
            Some((len, ..)) if len <= MAX_SMS_FILE => fs::read_to_string(&self.path)
                .map(|text| text.lines().filter(|l| !l.is_empty()).map(str::to_string).collect())
                .unwrap_or_default(),
            _ => Vec::new(),
        };
        let now = lines.len();
        let last = lines.last().map_or(0, |l| line_hash(l));
        let fresh: &[String] = match self.count {
            // First look: whatever is stored is already history.
            None => &[],
            Some(before) if now > before => &lines[before..],
            Some(before) if now < before => &lines[..],
            // The store is capped, so a full file drops its oldest line.
            Some(_) if now > 0 && last != self.last => &lines[now - 1..],
            Some(_) => &[],
        };
        let texts = fresh.iter().rev().take(MAX_ANNOUNCED).rev().filter_map(|l| parse_text(l)).collect();
        self.count = Some(now);
        self.last = last;
        texts
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::net::UnixListener;

    const PRESENT: &str = r#"{"schema":1,"updated":1,"power":"on","present":true,"cellular":true,"location":false,"sim":"ready","pin_attempts":null,"registration":"registered_home","operator":"Example Net","rat":"LTE-M","rsrp":-95,"bars":3,"gnss":"off","modem_firmware":"mfw","slm_version":"2.9.0","sms_count":2,"last_error":null}"#;

    fn status(edit: impl FnOnce(&mut Value)) -> ModemStatus {
        let mut value: Value = serde_json::from_str(PRESENT).unwrap();
        edit(&mut value);
        parse_status(value.to_string().as_bytes()).expect("present")
    }

    fn tempdir(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "k230-modem-{tag}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
        ));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn the_modem_is_hidden_until_it_has_answered() {
        let dir = tempdir("hidden");
        assert_eq!(read_status(&dir.join("missing.json")), None, "no file");
        let off = PRESENT.replace("\"present\":true", "\"present\":false");
        fs::write(dir.join("state.json"), &off).unwrap();
        assert_eq!(read_status(&dir.join("state.json")), None, "present false");
        fs::write(dir.join("state.json"), "not json").unwrap();
        assert_eq!(read_status(&dir.join("state.json")), None, "garbage");
        fs::write(dir.join("state.json"), PRESENT).unwrap();
        assert!(read_status(&dir.join("state.json")).is_some());
        fs::write(dir.join("big.json"), " ".repeat(9000) + PRESENT).unwrap();
        assert_eq!(read_status(&dir.join("big.json")), None, "oversize");
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn the_shade_shows_nothing_while_both_are_off() {
        let s = status(|v| {
            v["cellular"] = false.into();
            v["location"] = false.into();
        });
        assert_eq!((s.cellular_indicator(), s.location_indicator()), (None, None));
    }

    #[test]
    fn the_signal_glyph_follows_bars_or_says_no_service() {
        for bars in 0..=4u8 {
            assert_eq!(status(|v| v["bars"] = bars.into()).cellular_indicator(), Some(CellularIndicator::Bars(bars)));
        }
        assert_eq!(status(|v| v["bars"] = 9.into()).cellular_indicator(), Some(CellularIndicator::Bars(4)), "clamped");
        for reg in ["not_registered", "searching", "denied", "sim_failure", "unknown"] {
            let s = status(|v| v["registration"] = reg.into());
            assert_eq!(s.cellular_indicator(), Some(CellularIndicator::NoService), "{reg}");
        }
        let roaming = status(|v| v["registration"] = "registered_roaming".into());
        assert_eq!(roaming.cellular_indicator(), Some(CellularIndicator::Bars(3)));
    }

    #[test]
    fn location_is_searching_until_the_service_reports_a_fix() {
        let on = |gnss: &str| status(|v| {
            v["location"] = true.into();
            v["gnss"] = gnss.into();
        });
        assert_eq!(on("off").location_indicator(), Some(LocationIndicator::Searching), "powering up");
        assert_eq!(on("searching").location_indicator(), Some(LocationIndicator::Searching));
        assert_eq!(on("fix").location_indicator(), Some(LocationIndicator::Fix));
        assert_eq!(on("fix").location_label(), "Fix");
        assert_eq!(on("searching").location_label(), "Searching…");
        assert_eq!(status(|_| {}).location_label(), "Off");
    }

    #[test]
    fn location_alone_does_not_claim_to_read_the_sim() {
        let s = status(|v| {
            v["sim"] = "unknown".into();
            v["power"] = "on".into();
            v["cellular"] = false.into();
            v["location"] = true.into();
        });
        assert_eq!(s.sim_label(), "—");
        let s = status(|v| {
            v["sim"] = "unknown".into();
            v["power"] = "on".into();
            v["cellular"] = true.into();
        });
        assert_eq!(s.sim_label(), "Reading…");
    }

    #[test]
    fn a_boardless_sim_reads_sensibly() {
        for sim in ["absent", "unknown"] {
            let s = status(|v| {
                v["sim"] = sim.into();
                v["registration"] = "unknown".into();
                v["operator"] = Value::Null;
                v["rat"] = Value::Null;
                v["bars"] = 0.into();
                v["power"] = "off".into();
            });
            assert!(!s.pin_needed());
            assert_eq!(s.signal_label(), "No signal");
            assert_eq!(s.registration_label(), "—");
            assert!(s.sim_label() == "No SIM" || s.sim_label() == "Not read");
        }
    }

    #[test]
    fn the_settings_row_summarises_cellular_in_one_line() {
        assert_eq!(status(|v| v["cellular"] = false.into()).cellular_summary(), "Off");
        assert_eq!(status(|_| {}).cellular_summary(), "Example Net · LTE-M");
        assert_eq!(status(|v| v["sim"] = "absent".into()).cellular_summary(), "No SIM");
        assert_eq!(status(|v| v["sim"] = "pin_required".into()).cellular_summary(), "PIN required");
        assert_eq!(status(|v| v["power"] = "powering_on".into()).cellular_summary(), "Starting…");
        let searching = status(|v| v["registration"] = "searching".into());
        assert_eq!(searching.cellular_summary(), "Searching…");
    }

    #[test]
    fn the_pin_is_asked_for_only_when_the_radio_is_up_and_the_sim_says_so() {
        assert!(status(|v| v["sim"] = "pin_required".into()).pin_needed());
        assert!(!status(|v| {
            v["sim"] = "pin_required".into();
            v["cellular"] = false.into();
        })
        .pin_needed());
        assert!(!status(|_| {}).pin_needed());
    }

    #[test]
    fn pins_validate_and_never_print() {
        assert!(Pin::new("123").is_none());
        assert!(Pin::new("123456789").is_none());
        assert!(Pin::new("12a4").is_none());
        let pin = Pin::new("4829").unwrap();
        let command = Command::SubmitPin(pin.clone());
        for shown in [format!("{pin:?}"), format!("{command:?}"), format!("{:?}", Some(&command))] {
            assert!(!shown.contains("4829"), "{shown}");
        }
        assert_eq!(command.wire(), b"pin 4829\n");
    }

    #[test]
    fn wire_lines_match_the_services_protocol() {
        assert_eq!(Command::Cellular(true).wire(), b"power on\n");
        assert_eq!(Command::Cellular(false).wire(), b"power off\n");
        assert_eq!(Command::Location(true).wire(), b"gnss on\n");
        assert_eq!(Command::Location(false).wire(), b"gnss off\n");
        assert_eq!(Command::ClearMessages.wire(), b"sms clear\n");
    }

    #[test]
    fn replies_keep_only_the_code_word() {
        assert_eq!(parse_reply("ok\n"), Ok(()));
        assert_eq!(parse_reply("ok {\"x\":1}"), Ok(()));
        assert_eq!(parse_reply("err pin_rejected attempts=2"), Err("pin_rejected".into()));
        assert_eq!(parse_reply("err modem_timeout"), Err("modem_timeout".into()));
        assert_eq!(parse_reply(""), Err("no_reply".into()));
        assert_eq!(failure_text("pin_rejected"), "PIN not accepted");
        assert_eq!(failure_text("modem_timeout"), "The modem did not respond");
    }

    #[test]
    fn a_command_reaches_a_fake_service_and_its_answer_comes_back() {
        let dir = tempdir("socket");
        let path = dir.join("control");
        let listener = UnixListener::bind(&path).unwrap();
        let server = thread::spawn(move || {
            let mut seen = Vec::new();
            for answer in ["ok\n", "err pin_rejected attempts=2\n"] {
                let (mut stream, _) = listener.accept().unwrap();
                let mut request = String::new();
                stream.read_to_string(&mut request).unwrap();
                seen.push(request);
                stream.write_all(answer.as_bytes()).unwrap();
            }
            seen
        });
        let worker = ModemWorker::spawn(path.clone());
        worker.try_submit(Command::Location(true)).unwrap();
        worker.try_submit(Command::SubmitPin(Pin::new("0000").unwrap())).unwrap();
        let mut replies = Vec::new();
        for _ in 0..200 {
            while let Some(reply) = worker.try_recv() {
                replies.push(reply);
            }
            if replies.len() == 2 {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        assert_eq!(
            replies,
            vec![
                ModemReply { kind: Kind::Location, result: Ok(()) },
                ModemReply { kind: Kind::Pin, result: Err("pin_rejected".into()) },
            ]
        );
        assert_eq!(server.join().unwrap(), vec!["gnss on\n".to_string(), "pin 0000\n".to_string()]);
        assert_eq!(send(&dir.join("absent"), &Command::ClearMessages), Err("unreachable".into()));
        fs::remove_dir_all(&dir).unwrap();
    }

    fn line(from: &str, body: &str) -> String {
        format!("{{\"from\":\"{from}\",\"time\":\"26/10/26,10:00:00+00\",\"body\":\"{body}\",\"parts\":1}}\n")
    }

    #[test]
    fn a_new_text_becomes_a_private_notification_and_old_ones_stay_quiet() {
        let dir = tempdir("sms");
        let path = dir.join("sms.jsonl");
        fs::write(&path, line("+15555550100", "stored before start")).unwrap();
        let mut tail = SmsTail::new(path.clone());
        assert!(tail.poll().is_empty(), "history is not announced");
        assert!(tail.poll().is_empty(), "nothing changed");
        let mut file = fs::OpenOptions::new().append(true).open(&path).unwrap();
        file.write_all(line("+15555550101", "meet at noon").as_bytes()).unwrap();
        let fresh = tail.poll();
        assert_eq!(fresh.len(), 1);
        let (summary, body) = notification_for(&fresh[0]);
        assert_eq!(summary, "Text from +15555550101");
        assert_eq!(body.0, "meet at noon");
        assert!(!format!("{fresh:?}").contains("noon"), "debug hides the body");
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn a_missing_store_then_a_first_text_is_announced() {
        let dir = tempdir("sms-late");
        let path = dir.join("sms.jsonl");
        let mut tail = SmsTail::new(path.clone());
        assert!(tail.poll().is_empty());
        fs::write(&path, line("+15555550102", "hello")).unwrap();
        assert_eq!(tail.poll().len(), 1);
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn clearing_and_the_capped_store_still_announce_what_is_new() {
        let dir = tempdir("sms-cap");
        let path = dir.join("sms.jsonl");
        fs::write(&path, line("+1555000001", "a") + &line("+1555000002", "b")).unwrap();
        let mut tail = SmsTail::new(path.clone());
        tail.poll();
        // The store is full: its oldest line drops as a new one arrives.
        fs::write(&path, line("+1555000002", "b") + &line("+1555000003", "c")).unwrap();
        let rotated = tail.poll();
        assert_eq!(rotated.len(), 1);
        assert_eq!(rotated[0].from, "+1555000003");
        // Cleared by the service, then a text arrives.
        fs::write(&path, "").unwrap();
        assert!(tail.poll().is_empty());
        fs::write(&path, line("+1555000004", "d")).unwrap();
        assert_eq!(tail.poll().len(), 1);
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn a_flood_is_capped_and_garbage_lines_are_skipped() {
        let dir = tempdir("sms-flood");
        let path = dir.join("sms.jsonl");
        fs::write(&path, "").unwrap();
        let mut tail = SmsTail::new(path.clone());
        tail.poll();
        let mut text = String::from("not json\n");
        for n in 0..20 {
            text.push_str(&line("+1555000009", &format!("m{n}")));
        }
        fs::write(&path, text).unwrap();
        let fresh = tail.poll();
        assert_eq!(fresh.len(), MAX_ANNOUNCED);
        assert_eq!(fresh.last().unwrap().body.0, "m19", "the newest are kept");
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn a_fake_sms_event_reaches_the_broker_as_a_private_notification() {
        use crate::service_data::{ServiceRequest, ServiceWorker};
        use std::os::unix::fs::PermissionsExt;
        let dir = tempdir("broker");
        fs::set_permissions(&dir, fs::Permissions::from_mode(0o700)).unwrap();
        let socket = dir.join("events.sock");
        let listener = UnixListener::bind(&socket).unwrap();
        fs::set_permissions(&socket, fs::Permissions::from_mode(0o600)).unwrap();
        let broker = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut line = String::new();
            let mut byte = [0u8; 1];
            while stream.read(&mut byte).unwrap() == 1 && byte[0] != b'\n' {
                line.push(char::from(byte[0]));
            }
            stream.write_all(b"{\"state\":\"accepted\",\"id\":7}\n").unwrap();
            line
        });

        // The path the shell takes: the store gains a line, the tail finds it,
        // `notification_for` shapes it, the worker emits it.
        let sms = dir.join("sms.jsonl");
        fs::write(&sms, "").unwrap();
        let mut tail = SmsTail::new(sms.clone());
        tail.poll();
        fs::write(&sms, line("+15555550123", "the door code is 4471")).unwrap();
        let text = tail.poll().pop().expect("the new text");
        let (summary, body) = notification_for(&text);
        let request = ServiceRequest::NotificationEmit { summary, body };
        assert!(!format!("{request:?}").contains("4471"), "a logged request never carries the text");
        let worker = ServiceWorker::spawn(PathBuf::from("/nonexistent"), socket);
        worker.try_submit(request).unwrap();
        let mut reply = None;
        for _ in 0..300 {
            reply = worker.try_recv();
            if reply.is_some() {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }
        assert!(reply.expect("the broker answered").result.is_ok());

        let sent: Value = serde_json::from_str(&broker.join().unwrap()).unwrap();
        assert_eq!(sent["operation"], "emit");
        assert_eq!(sent["summary"], "Text from +15555550123");
        assert_eq!(sent["body"], "the door code is 4471");
        assert!(sent.get("private").is_none(), "the broker's privacy default applies");
        fs::remove_dir_all(&dir).unwrap();
    }
}

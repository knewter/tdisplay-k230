//! Bounded, typed service data for the handheld shell.
//!
//! The caller owns polling and rendering. These parsers accept only bytes that
//! an asynchronous worker has already read from the trusted settings command
//! or the private notification socket.

use serde_json::Value;

const MAX_SETTINGS: usize = 16 * 1024;
const MAX_HISTORY: usize = 128 * 1024;
const MAX_EVENTS: usize = 64;

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

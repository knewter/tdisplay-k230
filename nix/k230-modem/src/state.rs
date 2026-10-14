//! The published state: `state.json`, written atomically.

use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Write;
use std::os::unix::fs::OpenOptionsExt;
use std::path::Path;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PowerState {
    Off,
    PoweringOn,
    On,
    PoweringOff,
    Error,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SimState {
    Unknown,
    Absent,
    PinRequired,
    PukRequired,
    Ready,
    Error,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Registration {
    Unknown,
    NotRegistered,
    RegisteredHome,
    Searching,
    Denied,
    RegisteredRoaming,
    SimFailure,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum GnssState {
    Off,
    Searching,
    Fix,
}

/// Schema version 1. Fields are only ever added.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct State {
    pub schema: u32,
    /// Unix seconds of the write; set by the writer, not compared.
    pub updated: u64,
    pub power: PowerState,
    /// True once the modem has answered an AT command since this service
    /// started. The shell hides cellular UI until then.
    pub present: bool,
    /// The persisted choices.
    pub cellular: bool,
    pub location: bool,
    pub sim: SimState,
    /// Remaining SIM PIN attempts, when the modem said.
    pub pin_attempts: Option<u8>,
    pub registration: Registration,
    pub operator: Option<String>,
    /// "LTE-M" or "NB-IoT".
    pub rat: Option<String>,
    /// dBm.
    pub rsrp: Option<i32>,
    /// 0..=4.
    pub bars: u8,
    pub gnss: GnssState,
    pub modem_firmware: Option<String>,
    pub slm_version: Option<String>,
    pub sms_count: u32,
    pub last_error: Option<String>,
}

impl Default for State {
    fn default() -> Self {
        State {
            schema: 1,
            updated: 0,
            power: PowerState::Off,
            present: false,
            cellular: false,
            location: false,
            sim: SimState::Unknown,
            pin_attempts: None,
            registration: Registration::Unknown,
            operator: None,
            rat: None,
            rsrp: None,
            bars: 0,
            gnss: GnssState::Off,
            modem_firmware: None,
            slm_version: None,
            sms_count: 0,
            last_error: None,
        }
    }
}

impl State {
    /// Forget everything learned from the radio (power went away).
    pub fn clear_radio(&mut self) {
        self.sim = SimState::Unknown;
        self.pin_attempts = None;
        self.registration = Registration::Unknown;
        self.operator = None;
        self.rat = None;
        self.rsrp = None;
        self.bars = 0;
        self.gnss = GnssState::Off;
    }

    pub fn to_json(&self) -> String {
        serde_json::to_string(self).expect("state serializes")
    }
}

/// Map an RSRP in dBm to 0..=4 bars.
pub fn bars_for_rsrp(dbm: Option<i32>) -> u8 {
    match dbm {
        None => 0,
        Some(d) if d >= -95 => 4,
        Some(d) if d >= -105 => 3,
        Some(d) if d >= -115 => 2,
        Some(d) if d >= -125 => 1,
        Some(_) => 0,
    }
}

/// Write `bytes` to `path` through a temporary file in the same directory
/// and a rename, so a reader never sees a partial file.
pub fn write_atomic(path: &Path, bytes: &[u8], mode: u32) -> std::io::Result<()> {
    let dir = path.parent().unwrap_or_else(|| Path::new("."));
    let tmp = dir.join(format!(
        ".{}.tmp",
        path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default()
    ));
    {
        let mut f = fs::OpenOptions::new().write(true).create(true).truncate(true).mode(mode).open(&tmp)?;
        f.write_all(bytes)?;
        f.sync_all()?;
    }
    fs::rename(&tmp, path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn json_schema_is_stable() {
        let v: serde_json::Value = serde_json::from_str(&State::default().to_json()).unwrap();
        for k in [
            "schema", "updated", "power", "present", "cellular", "location", "sim", "pin_attempts",
            "registration", "operator", "rat", "rsrp", "bars", "gnss", "modem_firmware",
            "slm_version", "sms_count", "last_error",
        ] {
            assert!(v.get(k).is_some(), "missing {k}");
        }
        assert_eq!(v["power"], "off");
        assert_eq!(v["sim"], "unknown");
    }

    #[test]
    fn atomic_write_replaces_without_leaving_the_temp_file() {
        let dir = std::env::temp_dir().join(format!("k230-modem-test-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let p = dir.join("state.json");
        write_atomic(&p, b"one", 0o640).unwrap();
        write_atomic(&p, b"two", 0o640).unwrap();
        assert_eq!(fs::read_to_string(&p).unwrap(), "two");
        assert_eq!(fs::read_dir(&dir).unwrap().count(), 1);
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn bars() {
        assert_eq!(bars_for_rsrp(None), 0);
        assert_eq!(bars_for_rsrp(Some(-90)), 4);
        assert_eq!(bars_for_rsrp(Some(-110)), 2);
        assert_eq!(bars_for_rsrp(Some(-140)), 0);
    }
}

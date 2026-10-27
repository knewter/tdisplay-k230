//! The persisted choices, `/var/lib/k230-modem/settings.json`.

use crate::state::write_atomic;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Settings {
    #[serde(default)]
    pub cellular: bool,
    #[serde(default)]
    pub location: bool,
    /// The modem has answered at least once on this installation, so the
    /// shell may offer Cellular and Location even before it is powered.
    #[serde(default)]
    pub seen: bool,
}

impl Settings {
    /// Missing or unreadable settings mean both off.
    pub fn load(path: &Path) -> Settings {
        fs::read_to_string(path).ok().and_then(|s| serde_json::from_str(&s).ok()).unwrap_or_default()
    }

    pub fn save(&self, path: &Path) -> std::io::Result<()> {
        write_atomic(path, serde_json::to_string(self).expect("settings serialize").as_bytes(), 0o640)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_off_and_round_trips() {
        let dir = std::env::temp_dir().join(format!("k230-settings-test-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let p = dir.join("settings.json");
        assert_eq!(Settings::load(&p), Settings::default());
        let on = Settings { cellular: true, location: false, seen: true };
        on.save(&p).unwrap();
        assert_eq!(Settings::load(&p), on);
        fs::write(&p, r#"{"cellular":true,"location":false}"#).unwrap();
        assert!(!Settings::load(&p).seen, "older files load with seen false");
        fs::write(&p, "not json").unwrap();
        assert_eq!(Settings::load(&p), Settings::default());
        fs::remove_dir_all(&dir).unwrap();
    }
}

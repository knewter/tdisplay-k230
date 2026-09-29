//! Finds the touchscreen's `/dev/input/eventN` node by the input device
//! name Linux already reports for it -- `"Goodix Berlin Capacitive
//! TouchScreen"`, per `docs/evidence/touch-evtest.txt` and
//! `docs/evidence/shell-real-touch-keyboard/touch-events.txt`, both
//! captured on this board. Parses `/proc/bus/input/devices`'s text format
//! rather than walking `/sys/class/input/*/device/name` + `.../uevent`
//! purely because the former is one file read instead of N; the format is
//! stable stanza text documented in `Documentation/input/input.rst`.

use std::path::PathBuf;

/// Parses `text` (the verbatim contents of `/proc/bus/input/devices`) and
/// returns the `/dev/input/eventN` path of the first device stanza whose
/// `N: Name="..."` line matches `name` exactly.
///
/// A stanza looks like:
/// ```text
/// I: Bus=0018 Vendor=0000 Product=0000 Version=0000
/// N: Name="Goodix Berlin Capacitive TouchScreen"
/// P: Phys=i2c-5-005d/input0
/// S: Sysfs=/devices/platform/soc/.../input/input3
/// U: Uniq=
/// H: Handlers=event3
/// B: PROP=0
/// ...
/// ```
/// and stanzas are separated by a blank line.
pub fn find_event_device(text: &str, name: &str) -> Option<PathBuf> {
    let quoted = format!("N: Name=\"{name}\"");
    let mut in_match = false;
    for line in text.lines() {
        if line.trim() == quoted {
            in_match = true;
            continue;
        }
        if line.is_empty() {
            in_match = false;
            continue;
        }
        if in_match {
            if let Some(handlers) = line.strip_prefix("H: Handlers=") {
                if let Some(token) = handlers.split_whitespace().find(|t| t.starts_with("event")) {
                    return Some(PathBuf::from(format!("/dev/input/{token}")));
                }
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = "I: Bus=0018 Vendor=0000 Product=0000 Version=0000\n\
N: Name=\"gpio-keys\"\n\
P: Phys=gpio-keys/input0\n\
S: Sysfs=/devices/platform/gpio-keys/input/input1\n\
U: Uniq=\n\
H: Handlers=kbd event1\n\
B: PROP=0\n\
B: EV=3\n\
\n\
I: Bus=0018 Vendor=0000 Product=0000 Version=0000\n\
N: Name=\"Goodix Berlin Capacitive TouchScreen\"\n\
P: Phys=i2c-5-005d/input0\n\
S: Sysfs=/devices/platform/soc/fc000000.i2c5/i2c-5/5-005d/input/input3\n\
U: Uniq=\n\
H: Handlers=event3\n\
B: PROP=0\n\
B: EV=b\n\
\n\
I: Bus=0003 Vendor=0000 Product=0000 Version=0000\n\
N: Name=\"Some Other Device\"\n\
H: Handlers=event7\n\
\n";

    #[test]
    fn finds_the_touchscreen_among_other_stanzas() {
        let found = find_event_device(SAMPLE, "Goodix Berlin Capacitive TouchScreen");
        assert_eq!(found, Some(PathBuf::from("/dev/input/event3")));
    }

    #[test]
    fn returns_none_when_name_is_absent() {
        assert_eq!(find_event_device(SAMPLE, "Nonexistent Device"), None);
    }

    #[test]
    fn does_not_match_a_substring_of_another_name() {
        // "Goodix Berlin Capacitive TouchScreen Pro" must not match a
        // lookup for the plain "...TouchScreen" name, and vice versa.
        assert_eq!(find_event_device(SAMPLE, "Goodix Berlin Capacitive TouchScreen Pro"), None);
    }
}

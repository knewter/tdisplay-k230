//! The control socket protocol.
//!
//! Requests are one line, `\n` terminated:
//!
//! ```text
//! status
//! power on | power off          (Cellular on / off)
//! gnss on | gnss off            (Location on / off)
//! pin <digits>                  (4 to 8 digits)
//! sms send <number>             (then the body, ended by closing the write side)
//! sms clear
//! ```
//!
//! Replies are one line: `ok`, `ok <json>` (status) or `err <code> [detail]`.
//! No reply ever repeats a request argument.

use crate::at::Secret;

#[derive(Debug)]
pub enum Command {
    Status,
    PowerOn,
    PowerOff,
    GnssOn,
    GnssOff,
    Pin(Secret),
    SmsSend { number: String },
    SmsClear,
}

/// Parse a request line. The error is a fixed code, never the input.
pub fn parse(line: &str) -> Result<Command, &'static str> {
    let line = line.trim_end_matches(['\r', '\n']);
    let mut it = line.split(' ');
    let verb = it.next().unwrap_or("");
    let a = it.next();
    let b = it.next();
    let extra = it.next();
    match (verb, a, b, extra) {
        ("status", None, ..) => Ok(Command::Status),
        ("power", Some("on"), None, _) => Ok(Command::PowerOn),
        ("power", Some("off"), None, _) => Ok(Command::PowerOff),
        ("gnss", Some("on"), None, _) => Ok(Command::GnssOn),
        ("gnss", Some("off"), None, _) => Ok(Command::GnssOff),
        ("pin", Some(d), None, _) => {
            if (4..=8).contains(&d.len()) && d.bytes().all(|c| c.is_ascii_digit()) {
                Ok(Command::Pin(Secret::new(d.to_string())))
            } else {
                Err("bad_pin")
            }
        }
        ("sms", Some("send"), Some(n), None) => {
            if valid_number(n) {
                Ok(Command::SmsSend { number: n.to_string() })
            } else {
                Err("bad_number")
            }
        }
        ("sms", Some("clear"), None, _) => Ok(Command::SmsClear),
        _ => Err("bad_request"),
    }
}

pub fn valid_number(n: &str) -> bool {
    let digits = n.strip_prefix('+').unwrap_or(n);
    (3..=20).contains(&digits.len()) && digits.bytes().all(|c| c.is_ascii_digit())
}

/// A text-mode body: printable ASCII and newlines, at most one message.
pub fn valid_body(b: &str) -> Result<(), &'static str> {
    if b.is_empty() {
        return Err("empty_body");
    }
    if b.len() > 160 {
        return Err("body_too_long");
    }
    if b.bytes().all(|c| (0x20..0x7f).contains(&c) || c == b'\n') {
        Ok(())
    } else {
        Err("unsupported_text")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_the_documented_requests() {
        assert!(matches!(parse("status\n"), Ok(Command::Status)));
        assert!(matches!(parse("power on"), Ok(Command::PowerOn)));
        assert!(matches!(parse("gnss off"), Ok(Command::GnssOff)));
        assert!(matches!(parse("sms send +15555550100"), Ok(Command::SmsSend { .. })));
        assert!(matches!(parse("sms clear"), Ok(Command::SmsClear)));
        match parse("pin 0000") {
            Ok(Command::Pin(p)) => assert_eq!(p.expose(), "0000"),
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn rejects_malformed_requests_without_echoing_them() {
        for bad in ["", "pin 12", "pin 12a4", "pin", "sms send", "sms send ab", "power", "reboot", "status now"] {
            assert!(parse(bad).is_err(), "{bad}");
        }
        assert_eq!(parse("pin 4829 extra").err(), Some("bad_request"));
    }

    #[test]
    fn debug_of_a_pin_command_hides_the_digits() {
        let c = parse("pin 4829").unwrap();
        assert!(!format!("{c:?}").contains("4829"));
    }

    #[test]
    fn bodies() {
        assert!(valid_body("hello\nworld").is_ok());
        assert_eq!(valid_body(""), Err("empty_body"));
        assert_eq!(valid_body(&"x".repeat(161)), Err("body_too_long"));
        assert_eq!(valid_body("caf\u{e9}"), Err("unsupported_text"));
        assert_eq!(valid_body("a\u{1a}b"), Err("unsupported_text"));
    }
}

//! AT line framing, final-result classification, field splitting and
//! command redaction.

use std::fmt;

pub const REDACTED: &str = "<redacted>";

/// Commands whose argument is a secret or a phone number. The argument is
/// replaced before the command reaches any log.
const REDACTED_PREFIXES: [&str; 4] = ["AT+CPIN=", "AT+CPWD=", "AT+CLCK=", "AT+CMGS="];

pub fn redact_command(cmd: &str) -> String {
    let upper = cmd.to_ascii_uppercase();
    for p in REDACTED_PREFIXES {
        if upper.starts_with(p) {
            return format!("{}{}", &cmd[..p.len()], REDACTED);
        }
    }
    cmd.to_string()
}

/// A received line as it may appear in a log. Registration reports keep
/// their status but lose the tracking area and cell id (a coarse location),
/// and identity answers (IMEI, IMSI, ICCID, own number) are withheld.
pub fn redact_line(l: &str) -> String {
    // An echo the engine did not recognise as its own (case or spacing
    // differs) must not carry a PIN or number into the log either.
    let echo = redact_command(l.trim_start());
    if echo != l.trim_start() {
        return echo;
    }
    if let Some(r) = l.strip_prefix("+CEREG:") {
        let f = split_fields(r);
        // `<n>,<stat>,...` (read form, numeric second field) or `<stat>,...`.
        let read_form = f.get(1).map(|s| !s.is_empty() && s.parse::<u32>().is_ok()).unwrap_or(false);
        let keep = if read_form { 2 } else { 1 };
        if f.len() > keep {
            return format!("+CEREG: {},{REDACTED}", f[..keep].join(","));
        }
        return l.to_string();
    }
    let upper = l.to_ascii_uppercase();
    for p in ["+CNUM:", "%XICCID:", "+CGSN:", "+CIMI:", "%XMONITOR:", "%NCELLMEAS:"] {
        if upper.starts_with(p) {
            return format!("{}{REDACTED}", &l[..p.len()]);
        }
    }
    let t = l.trim();
    if t.len() >= 10 && t.bytes().all(|b| b.is_ascii_digit()) {
        return REDACTED.to_string();
    }
    l.to_string()
}

/// A secret (a SIM PIN). It has no Display and no serde impls, and its Debug
/// prints a placeholder, so formatting it by accident cannot leak it.
pub struct Secret(String);

impl Secret {
    pub fn new(s: String) -> Secret {
        Secret(s)
    }
    pub fn expose(&self) -> &str {
        &self.0
    }
}

impl fmt::Debug for Secret {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Secret({REDACTED})")
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AtError {
    Timeout,
    Error,
    Cme(String),
    Cms(String),
    Io(String),
}

impl fmt::Display for AtError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AtError::Timeout => write!(f, "timeout"),
            AtError::Error => write!(f, "error"),
            AtError::Cme(c) => write!(f, "cme_error_{c}"),
            AtError::Cms(c) => write!(f, "cms_error_{c}"),
            AtError::Io(e) => write!(f, "io_{e}"),
        }
    }
}

impl From<std::io::Error> for AtError {
    fn from(e: std::io::Error) -> Self {
        AtError::Io(e.kind().to_string().replace(' ', "_"))
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Final {
    Ok,
    Err(AtError),
}

pub fn final_result(line: &str) -> Option<Final> {
    if line == "OK" {
        return Some(Final::Ok);
    }
    if line == "ERROR" {
        return Some(Final::Err(AtError::Error));
    }
    if let Some(c) = line.strip_prefix("+CME ERROR:") {
        return Some(Final::Err(AtError::Cme(c.trim().to_string())));
    }
    if let Some(c) = line.strip_prefix("+CMS ERROR:") {
        return Some(Final::Err(AtError::Cms(c.trim().to_string())));
    }
    None
}

/// Split a comma-separated AT parameter list. Quotes are kept on the
/// returned tokens so a caller can tell `"1"` from `1`; commas inside quotes
/// do not split.
pub fn split_fields(s: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    let mut quoted = false;
    for ch in s.chars() {
        match ch {
            '"' => {
                quoted = !quoted;
                cur.push(ch);
            }
            ',' if !quoted => {
                out.push(cur.trim().to_string());
                cur.clear();
            }
            _ => cur.push(ch),
        }
    }
    out.push(cur.trim().to_string());
    out
}

pub fn unquote(s: &str) -> &str {
    let s = s.trim();
    s.strip_prefix('"').and_then(|x| x.strip_suffix('"')).unwrap_or(s)
}

/// Accumulates serial bytes and yields complete non-empty lines. The text
/// mode `> ` prompt has no line ending and is yielded as soon as it is the
/// whole buffer.
#[derive(Default)]
pub struct LineBuf {
    buf: Vec<u8>,
}

impl LineBuf {
    pub fn push(&mut self, bytes: &[u8]) {
        self.buf.extend_from_slice(bytes);
        if self.buf.len() > 4096 && !self.buf.contains(&b'\n') {
            self.buf.clear();
        }
    }

    pub fn next_line(&mut self) -> Option<String> {
        loop {
            if let Some(pos) = self.buf.iter().position(|b| *b == b'\n') {
                let raw: Vec<u8> = self.buf.drain(..=pos).collect();
                let line = String::from_utf8_lossy(&raw).trim_end_matches(['\r', '\n']).to_string();
                if line.is_empty() {
                    continue;
                }
                return Some(line);
            }
            let trimmed: &[u8] = {
                let mut s = &self.buf[..];
                while let Some((b'\r', rest)) = s.split_first() {
                    s = rest;
                }
                s
            };
            if trimmed == b"> " {
                self.buf.clear();
                return Some("> ".to_string());
            }
            return None;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redacts_cell_location_and_identities_from_received_lines() {
        assert_eq!(redact_line("+CEREG: 5,1,\"0A1B\",\"01C2D3E4\",7"), "+CEREG: 5,1,<redacted>");
        assert_eq!(redact_line("+CEREG: 1,\"0A1B\",\"01C2D3E4\",7"), "+CEREG: 1,<redacted>");
        assert_eq!(redact_line("+CEREG: 5,4"), "+CEREG: 5,4");
        assert_eq!(redact_line("+CEREG: 90"), "+CEREG: 90");
        assert_eq!(redact_line("351234567890123"), REDACTED);
        assert_eq!(redact_line("%XICCID: 8901234567890123456"), "%XICCID:<redacted>");
        assert_eq!(redact_line("OK"), "OK");
        assert_eq!(redact_line("+COPS: 0"), "+COPS: 0");
    }

    #[test]
    fn redacts_pin_number_and_leaves_queries() {
        assert_eq!(redact_command("AT+CPIN=\"4829\""), "AT+CPIN=<redacted>");
        assert_eq!(redact_command("at+cpin=\"4829\",\"0000\""), "at+cpin=<redacted>");
        assert_eq!(redact_command("AT+CMGS=\"+15555550100\""), "AT+CMGS=<redacted>");
        assert_eq!(redact_command("AT+CPIN?"), "AT+CPIN?");
        // An echo that differs from what was sent is still redacted.
        assert_eq!(redact_line(" at+cpin=\"4829\""), "at+cpin=<redacted>");
    }

    #[test]
    fn classifies_finals() {
        assert_eq!(final_result("OK"), Some(Final::Ok));
        assert_eq!(final_result("ERROR"), Some(Final::Err(AtError::Error)));
        assert_eq!(final_result("+CME ERROR: 16"), Some(Final::Err(AtError::Cme("16".into()))));
        assert_eq!(final_result("+CEREG: 90"), None);
    }

    #[test]
    fn splits_quoted_fields() {
        assert_eq!(split_fields("0,0,\"A,B\",7"), vec!["0", "0", "\"A,B\"", "7"]);
        assert_eq!(unquote("\"A,B\""), "A,B");
    }

    #[test]
    fn frames_lines_across_chunks_and_the_prompt() {
        let mut b = LineBuf::default();
        b.push(b"\r\nOK\r\n\r\n+CE");
        assert_eq!(b.next_line().as_deref(), Some("OK"));
        assert_eq!(b.next_line(), None);
        b.push(b"REG: 90\r\n");
        assert_eq!(b.next_line().as_deref(), Some("+CEREG: 90"));
        b.push(b"\r\n> ");
        assert_eq!(b.next_line().as_deref(), Some("> "));
        assert_eq!(b.next_line(), None);
    }
}

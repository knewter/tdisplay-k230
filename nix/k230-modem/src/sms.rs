//! SMS: concatenation of multi-part messages and the bounded store.

use crate::state::write_atomic;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap};
use std::fs;
use std::io::Write;
use std::os::unix::fs::OpenOptionsExt;
use std::path::PathBuf;
use std::time::{Duration, Instant};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Sms {
    pub from: String,
    /// The service-centre timestamp exactly as the modem reported it.
    pub time: String,
    pub body: String,
    /// How many parts were joined; 1 for a plain message.
    pub parts: u8,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Concat {
    pub reference: u16,
    pub total: u8,
    pub seq: u8,
}

fn hex_byte(s: &str, at: usize) -> Option<u8> {
    u8::from_str_radix(s.get(at..at + 2)?, 16).ok()
}

/// A concatenation header at the start of a text-mode body whose UDHI bit
/// is set: `050003 RR TT NN` (8-bit reference) or `060804 RRRR TT NN`
/// (16-bit), as hex text. Returns the header and the remaining text.
pub fn parse_udh(body: &str) -> Option<(Concat, &str)> {
    let udhl = hex_byte(body, 0)?;
    let iei = hex_byte(body, 2)?;
    let iedl = hex_byte(body, 4)?;
    let (c, used) = match (udhl, iei, iedl) {
        (5, 0x00, 3) => (
            Concat { reference: hex_byte(body, 6)? as u16, total: hex_byte(body, 8)?, seq: hex_byte(body, 10)? },
            12,
        ),
        (6, 0x08, 4) => (
            Concat {
                reference: ((hex_byte(body, 6)? as u16) << 8) | hex_byte(body, 8)? as u16,
                total: hex_byte(body, 10)?,
                seq: hex_byte(body, 12)?,
            },
            14,
        ),
        _ => return None,
    };
    if c.total == 0 || c.seq == 0 || c.seq > c.total {
        return None;
    }
    Some((c, body.get(used..)?))
}

struct Group {
    time: String,
    parts: BTreeMap<u8, String>,
    first_seen: Instant,
}

#[derive(Default)]
pub struct Assembler {
    groups: HashMap<(String, u16, u8), Group>,
}

impl Assembler {
    /// Add one received part. Returns the messages that are now complete.
    pub fn add(&mut self, from: &str, time: &str, concat: Option<Concat>, body: &str, now: Instant) -> Vec<Sms> {
        let Some(c) = concat else {
            return vec![Sms { from: from.into(), time: time.into(), body: body.into(), parts: 1 }];
        };
        let key = (from.to_string(), c.reference, c.total);
        let g = self.groups.entry(key.clone()).or_insert_with(|| Group {
            time: time.to_string(),
            parts: BTreeMap::new(),
            first_seen: now,
        });
        g.parts.insert(c.seq, body.to_string());
        if g.parts.len() == c.total as usize {
            let g = self.groups.remove(&key).expect("present");
            let body: String = g.parts.values().cloned().collect();
            return vec![Sms { from: from.into(), time: g.time, body, parts: c.total }];
        }
        Vec::new()
    }

    /// Groups that never completed are released as separate parts.
    pub fn flush_stale(&mut self, now: Instant, max_age: Duration) -> Vec<Sms> {
        let stale: Vec<_> = self
            .groups
            .iter()
            .filter(|(_, g)| now.saturating_duration_since(g.first_seen) >= max_age)
            .map(|(k, _)| k.clone())
            .collect();
        let mut out = Vec::new();
        for k in stale {
            let g = self.groups.remove(&k).expect("present");
            for (_, body) in g.parts {
                out.push(Sms { from: k.0.clone(), time: g.time.clone(), body, parts: 1 });
            }
        }
        out
    }
}

/// The last `cap` received messages, one JSON object per line.
pub struct SmsStore {
    path: PathBuf,
    cap: usize,
    count: usize,
}

impl SmsStore {
    pub fn open(path: PathBuf, cap: usize) -> SmsStore {
        let count = fs::read_to_string(&path).map(|s| s.lines().count()).unwrap_or(0);
        SmsStore { path, cap, count }
    }

    pub fn count(&self) -> usize {
        self.count
    }

    pub fn append(&mut self, sms: &Sms) -> std::io::Result<()> {
        let line = serde_json::to_string(sms).expect("sms serializes");
        if self.count >= self.cap {
            let old = fs::read_to_string(&self.path).unwrap_or_default();
            let keep = self.cap.saturating_sub(1);
            let lines: Vec<&str> = old.lines().collect();
            let mut out = String::new();
            for l in &lines[lines.len().saturating_sub(keep)..] {
                out.push_str(l);
                out.push('\n');
            }
            out.push_str(&line);
            out.push('\n');
            write_atomic(&self.path, out.as_bytes(), 0o640)?;
            self.count = out.lines().count();
            return Ok(());
        }
        let mut f = fs::OpenOptions::new().create(true).append(true).mode(0o640).open(&self.path)?;
        writeln!(f, "{line}")?;
        self.count += 1;
        Ok(())
    }

    pub fn clear(&mut self) -> std::io::Result<()> {
        write_atomic(&self.path, b"", 0o640)?;
        self.count = 0;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn udh_forms() {
        let (c, rest) = parse_udh("050003A70201Hello ").unwrap();
        assert_eq!((c.reference, c.total, c.seq, rest), (0xA7, 2, 1, "Hello "));
        let (c, rest) = parse_udh("060804012C0302abc").unwrap();
        assert_eq!((c.reference, c.total, c.seq, rest), (0x012C, 3, 2, "abc"));
        assert!(parse_udh("Hello there").is_none());
        assert!(parse_udh("050003A70103x").is_none(), "seq beyond total");
    }

    #[test]
    fn joins_out_of_order_parts_and_releases_stale_ones() {
        let t0 = Instant::now();
        let mut a = Assembler::default();
        let c = |seq| Some(Concat { reference: 7, total: 2, seq });
        assert!(a.add("+15555550100", "t", c(2), "world", t0).is_empty());
        let done = a.add("+15555550100", "t", c(1), "Hello ", t0);
        assert_eq!(done.len(), 1);
        assert_eq!(done[0].body, "Hello world");
        assert_eq!(done[0].parts, 2);

        assert!(a.add("+15555550100", "t", c(1), "lonely", t0).is_empty());
        assert!(a.flush_stale(t0 + Duration::from_secs(10), Duration::from_secs(300)).is_empty());
        let stale = a.flush_stale(t0 + Duration::from_secs(301), Duration::from_secs(300));
        assert_eq!(stale.len(), 1);
        assert_eq!(stale[0].body, "lonely");
    }

    #[test]
    fn store_is_bounded_and_clearable() {
        let dir = std::env::temp_dir().join(format!("k230-sms-test-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let mut s = SmsStore::open(dir.join("sms.jsonl"), 3);
        for i in 0..5 {
            s.append(&Sms { from: "+15555550100".into(), time: "t".into(), body: format!("m{i}"), parts: 1 }).unwrap();
        }
        assert_eq!(s.count(), 3);
        let text = fs::read_to_string(dir.join("sms.jsonl")).unwrap();
        assert!(text.contains("m4") && text.contains("m2") && !text.contains("m1"));
        assert_eq!(SmsStore::open(dir.join("sms.jsonl"), 3).count(), 3);
        s.clear().unwrap();
        assert_eq!(s.count(), 0);
        fs::remove_dir_all(&dir).unwrap();
    }
}

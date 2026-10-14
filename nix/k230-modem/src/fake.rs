//! A scripted AT link for the transcript tests.
//!
//! Transcript syntax, one item per line (blank lines and `#` comments are
//! ignored):
//!
//! ```text
//! < text     the modem sends `text`; before the first `>` it is unsolicited
//! > AT+X     the service must send the command `AT+X`; the `<` lines that
//!            follow are its answer
//! >> body    the service must send raw bytes (`^Z` = Ctrl-Z, `^[` = Esc)
//! !          silence: a read that times out
//! ```

use crate::engine::{EnableLine, Link};
use std::cell::RefCell;
use std::collections::VecDeque;
use std::io;
use std::rc::Rc;
use std::time::Duration;

#[derive(Default)]
pub struct Inner {
    rx: VecDeque<Option<String>>,
    script: VecDeque<(String, Vec<Option<String>>)>,
    /// What the service actually sent, redaction not applied.
    pub sent: Vec<String>,
    pub enable: Vec<bool>,
}

#[derive(Clone, Default)]
pub struct Handle(pub Rc<RefCell<Inner>>);

impl Handle {
    pub fn push_rx(&self, line: &str) {
        self.0.borrow_mut().rx.push_back(Some(line.to_string()));
    }
    pub fn sent(&self) -> Vec<String> {
        self.0.borrow().sent.clone()
    }
    pub fn enable_history(&self) -> Vec<bool> {
        self.0.borrow().enable.clone()
    }
    /// True when every scripted expectation was consumed.
    pub fn script_done(&self) -> bool {
        self.0.borrow().script.is_empty()
    }
}

pub struct ScriptLink(Handle);
pub struct FakeEnable(Handle);

/// Build a link, an enable line and a handle from a transcript.
pub fn from_transcript(text: &str) -> (ScriptLink, FakeEnable, Handle) {
    let h = Handle::default();
    {
        let mut i = h.0.borrow_mut();
        for raw in text.lines() {
            let line = raw.trim_end_matches(['\r']);
            if line.trim().is_empty() || line.trim_start().starts_with('#') {
                continue;
            }
            if let Some(c) = line.strip_prefix(">> ") {
                i.script.push_back((format!("raw:{c}"), Vec::new()));
            } else if let Some(c) = line.strip_prefix("> ") {
                i.script.push_back((c.to_string(), Vec::new()));
            } else if let Some(r) = line.strip_prefix("< ") {
                match i.script.back_mut() {
                    Some(last) => last.1.push(Some(r.to_string())),
                    None => i.rx.push_back(Some(r.to_string())),
                }
            } else if line == "!" {
                match i.script.back_mut() {
                    Some(last) => last.1.push(None),
                    None => i.rx.push_back(None),
                }
            } else {
                panic!("bad transcript line: {line}");
            }
        }
    }
    (ScriptLink(h.clone()), FakeEnable(h.clone()), h)
}

impl Link for ScriptLink {
    fn send(&mut self, data: &[u8]) -> io::Result<()> {
        let mut i = self.0 .0.borrow_mut();
        let shown = if data.ends_with(b"\r\n") {
            String::from_utf8_lossy(&data[..data.len() - 2]).into_owned()
        } else {
            let t = String::from_utf8_lossy(data).replace('\u{1a}', "^Z").replace('\u{1b}', "^[");
            format!("raw:{t}")
        };
        i.sent.push(shown.clone());
        let Some((want, reply)) = i.script.pop_front() else {
            panic!("unexpected send {shown:?} (script exhausted)");
        };
        assert_eq!(shown, want, "service sent something other than the transcript expects");
        i.rx.extend(reply);
        Ok(())
    }

    fn recv_line(&mut self, _timeout: Duration) -> io::Result<Option<String>> {
        Ok(self.0 .0.borrow_mut().rx.pop_front().flatten())
    }
}

impl EnableLine for FakeEnable {
    fn set(&mut self, on: bool) -> io::Result<()> {
        self.0 .0.borrow_mut().enable.push(on);
        Ok(())
    }
}

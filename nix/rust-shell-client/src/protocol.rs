//! Bounded compositor-to-client reveal stream. Sway owns the touch; this
//! model owns only overlay pixels and a reversible settle from current state.
use crate::Route;
use serde::Deserialize;

pub const MAX_LINE: usize = 128;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Phase {
    Begin,
    Update,
    Finish,
    Cancel,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RevealMessage {
    pub surface: Route,
    pub phase: Phase,
    pub seq: u64,
    pub progress: u16,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct WireMessage {
    v: u8,
    kind: String,
    surface: String,
    phase: String,
    seq: u64,
    progress: u16,
}

impl RevealMessage {
    pub fn parse(line: &[u8]) -> Option<Self> {
        if line.len() > MAX_LINE || !line.ends_with(b"\n") {
            return None;
        }
        let wire: WireMessage = serde_json::from_slice(&line[..line.len() - 1]).ok()?;
        if wire.v != 1 || wire.kind != "reveal" || wire.progress > 1000 {
            return None;
        }
        let surface = match wire.surface.as_str() {
            "drawer" => Route::Drawer,
            "shade" => Route::Shade,
            _ => return None,
        };
        let phase = match wire.phase.as_str() {
            "begin" => Phase::Begin,
            "update" => Phase::Update,
            "finish" => Phase::Finish,
            "cancel" => Phase::Cancel,
            _ => return None,
        };
        if (matches!(phase, Phase::Finish) && wire.progress != 0 && wire.progress != 1000)
            || (matches!(phase, Phase::Begin | Phase::Cancel) && wire.progress != 0)
        {
            return None;
        }
        Some(Self {
            surface,
            phase,
            seq: wire.seq,
            progress: wire.progress,
        })
    }
}

#[derive(Clone, Copy, Debug)]
struct Settle {
    from: f64,
    target: f64,
    started_ms: u64,
    duration_ms: u64,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct RevealState {
    surface: Option<Route>,
    seq: u64,
    progress: f64,
    settle: Option<Settle>,
    complete: bool,
    open_target: bool,
}

impl RevealState {
    pub fn surface(&self) -> Option<Route> {
        self.surface
    }
    pub fn progress(&self) -> f64 {
        self.progress
    }
    pub fn tracking(&self) -> bool {
        self.surface.is_some() && !self.complete
    }
    pub fn settling(&self) -> bool {
        self.settle.is_some()
    }
    pub fn input_ready(&self) -> bool {
        self.surface.is_some() && self.complete && self.open_target && self.settle.is_none()
    }
    pub fn clear(&mut self) {
        *self = Self::default();
    }

    pub fn apply(&mut self, message: RevealMessage, now_ms: u64, reduced_motion: bool) -> bool {
        match message.phase {
            Phase::Begin => {
                if self.surface.is_some() {
                    return false;
                }
                self.surface = Some(message.surface);
                self.seq = message.seq;
                self.progress = f64::from(message.progress) / 1000.0;
                self.complete = false;
                self.open_target = false;
                self.settle = None;
            }
            Phase::Update => {
                if !self.matches(message) || self.complete {
                    return false;
                }
                self.progress = f64::from(message.progress) / 1000.0;
            }
            Phase::Finish | Phase::Cancel => {
                if !self.matches(message) || self.complete {
                    return false;
                }
                let target = if matches!(message.phase, Phase::Cancel) {
                    0.0
                } else {
                    f64::from(message.progress) / 1000.0
                };
                self.settle_to(target, now_ms, reduced_motion);
            }
        }
        true
    }

    fn matches(&self, message: RevealMessage) -> bool {
        self.surface == Some(message.surface) && self.seq == message.seq
    }

    fn settle_to(&mut self, target: f64, now_ms: u64, reduced_motion: bool) {
        self.complete = true;
        self.open_target = target == 1.0;
        self.settle = Some(Settle {
            from: self.progress,
            target,
            started_ms: now_ms,
            duration_ms: if reduced_motion { 60 } else { 160 },
        });
    }

    /// EOF after a complete finish is normal; a broken in-flight stream
    /// reverses instead of leaving an unowned partial overlay.
    pub fn eof(&mut self, now_ms: u64, reduced_motion: bool) {
        if self.tracking() {
            self.settle_to(0.0, now_ms, reduced_motion);
        }
    }

    pub fn tick(&mut self, now_ms: u64) -> bool {
        let Some(settle) = self.settle else {
            return false;
        };
        let fraction = (now_ms.saturating_sub(settle.started_ms) as f64
            / settle.duration_ms as f64)
            .clamp(0.0, 1.0);
        self.progress = settle.from + (settle.target - settle.from) * fraction;
        if fraction >= 1.0 {
            self.settle = None;
            if !self.open_target {
                self.clear();
            }
        }
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn line(phase: &str, progress: u16, seq: u64) -> Vec<u8> {
        format!("{{\"v\":1,\"kind\":\"reveal\",\"surface\":\"drawer\",\"phase\":\"{phase}\",\"seq\":{seq},\"progress\":{progress}}}\n").into_bytes()
    }

    #[test]
    fn strict_bounded_wire_and_stale_sequence() {
        assert!(RevealMessage::parse(&line("begin", 0, 7)).is_some());
        assert!(RevealMessage::parse(&line("finish", 500, 7)).is_none());
        assert!(RevealMessage::parse(&line("update", 1001, 7)).is_none());
        assert!(RevealMessage::parse(&[b'x'; MAX_LINE + 1]).is_none());
        let mut state = RevealState::default();
        assert!(state.apply(
            RevealMessage::parse(&line("begin", 0, 7)).unwrap(),
            0,
            false
        ));
        assert!(!state.apply(
            RevealMessage::parse(&line("update", 700, 8)).unwrap(),
            5,
            false
        ));
    }

    #[test]
    fn reverse_mid_drag_and_eof_after_finish() {
        let mut state = RevealState::default();
        for (phase, progress, now) in [
            ("begin", 0, 0),
            ("update", 700, 10),
            ("update", 400, 20),
            ("finish", 1000, 25),
        ] {
            assert!(state.apply(
                RevealMessage::parse(&line(phase, progress, 3)).unwrap(),
                now,
                false
            ));
        }
        state.eof(26, false);
        assert_eq!(state.surface(), Some(Route::Drawer));
        assert!(!state.input_ready());
        state.tick(105);
        assert!(state.progress() > 0.4 && state.progress() < 1.0);
        state.tick(185);
        assert!(state.input_ready());
        assert_eq!(state.progress(), 1.0);
    }

    #[test]
    fn early_eof_and_cancel_settle_closed() {
        let mut state = RevealState::default();
        state.apply(RevealMessage::parse(&line("begin", 0, 4)).unwrap(), 0, true);
        state.apply(
            RevealMessage::parse(&line("update", 600, 4)).unwrap(),
            5,
            true,
        );
        state.eof(10, true);
        state.tick(40);
        assert!(state.progress() < 0.6 && state.surface().is_some());
        state.tick(70);
        assert_eq!(state.surface(), None);
        state.apply(
            RevealMessage::parse(&line("begin", 0, 5)).unwrap(),
            80,
            false,
        );
        state.apply(
            RevealMessage::parse(&line("update", 800, 5)).unwrap(),
            90,
            false,
        );
        state.apply(
            RevealMessage::parse(&line("cancel", 0, 5)).unwrap(),
            100,
            false,
        );
        state.eof(101, false);
        state.tick(260);
        assert_eq!(state.surface(), None);
    }
}

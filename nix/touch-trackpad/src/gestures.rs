//! Translate qualified shell pans into existing touch interactions. Declined
//! streams retain their original events for libinput, including timestamps.
use crate::event::*;
use crate::uinput::AbsRanges;

const SLOTS: usize = 16;
const MAX_BUFFER: usize = 1024;
const PAIR_MS: u64 = 45;
const DECIDE_MS: u64 = 250;

#[derive(Clone, Copy, Debug)]
pub struct Begin {
    pub fingers: u8,
    pub start_ms: u32,
    pub time_ms: u32,
    pub x: f64,
    pub y: f64,
    pub dx: f64,
    pub dy: f64,
}
#[derive(Debug)]
pub enum Action {
    Pass(Vec<InputEvent>),
    Begin(Begin),
    Move { dx: f64, dy: f64, time_ms: u32 },
    End(u32),
    Cancel(u32),
}
#[derive(Clone, Copy, Default)]
struct Contact {
    id: Option<i32>,
    x: Option<i32>,
    y: Option<i32>,
}
#[derive(Clone, Copy, Debug)]
enum State {
    Idle,
    Pass,
    Suppress,
    Owned,
    Candidate {
        since: u64,
        origin: (f64, f64),
        fingers: usize,
        spread: f64,
        source_ms: u32,
    },
}
pub struct Gate {
    slots: [Contact; SLOTS],
    slot: usize,
    ranges: AbsRanges,
    state: State,
    buffer: Vec<InputEvent>,
    frame: Vec<InputEvent>,
    origin: (f64, f64),
    owned_ids: Vec<i32>,
}
impl Gate {
    pub fn new(ranges: AbsRanges) -> Self {
        Self {
            slots: [Contact::default(); SLOTS],
            slot: 0,
            ranges,
            state: State::Idle,
            buffer: Vec::new(),
            frame: Vec::new(),
            origin: (0.0, 0.0),
            owned_ids: Vec::new(),
        }
    }
    pub fn prime(&mut self, positions: &[(i32, i32)]) {
        for (slot, &(x, y)) in self.slots.iter_mut().zip(positions) {
            slot.x = Some(x);
            slot.y = Some(y);
        }
    }
    pub fn pending(&self) -> bool {
        matches!(self.state, State::Candidate { .. })
    }
    fn points(&self) -> Option<Vec<(f64, f64)>> {
        self.slots
            .iter()
            .filter(|s| s.id.is_some())
            .map(|s| {
                let x = (s.x? - self.ranges.position_x.minimum) as f64
                    / (self.ranges.position_x.maximum - self.ranges.position_x.minimum) as f64;
                let y = (s.y? - self.ranges.position_y.minimum) as f64
                    / (self.ranges.position_y.maximum - self.ranges.position_y.minimum) as f64;
                ((0.0..=1.0).contains(&x) && (0.0..=1.0).contains(&y)).then_some((x, y))
            })
            .collect()
    }
    fn flush(&mut self) -> Action {
        self.state = State::Pass;
        self.buffer.append(&mut self.frame);
        Action::Pass(std::mem::take(&mut self.buffer))
    }
    pub fn acknowledge(&mut self, accepted: bool) -> Option<Action> {
        if accepted {
            self.buffer.clear();
            None
        } else {
            Some(self.flush())
        }
    }
    pub fn expire(&mut self, now: u64) -> Option<Action> {
        if let State::Candidate { since, fingers, .. } = self.state {
            if now.saturating_sub(since) >= if fingers == 1 { PAIR_MS } else { DECIDE_MS } {
                return Some(self.flush());
            }
        }
        None
    }
    pub fn push(&mut self, ev: InputEvent, now: u64) -> Option<Action> {
        let time_ms = (ev.tv_sec as u64 * 1000 + ev.tv_usec as u64 / 1000) as u32;
        match (ev.type_, ev.code) {
            (EV_ABS, ABS_MT_SLOT) => self.slot = (ev.value as usize).min(SLOTS - 1),
            (EV_ABS, ABS_MT_TRACKING_ID) => {
                self.slots[self.slot].id = (ev.value >= 0).then_some(ev.value)
            }
            // Protocol B axes survive tracking-ID changes; Linux filters
            // unchanged coordinates even for a new contact.
            (EV_ABS, ABS_MT_POSITION_X) => self.slots[self.slot].x = Some(ev.value),
            (EV_ABS, ABS_MT_POSITION_Y) => self.slots[self.slot].y = Some(ev.value),
            _ => {}
        }
        self.frame.push(ev);
        if self.frame.len() + self.buffer.len() > MAX_BUFFER {
            if matches!(self.state, State::Owned | State::Suppress) {
                self.frame.clear();
                self.buffer.clear();
                self.state = State::Suppress;
                return Some(Action::Cancel(time_ms));
            }
            return Some(self.flush());
        }
        if !ev.is_syn_report() {
            return None;
        }
        let count = self.slots.iter().filter(|s| s.id.is_some()).count();
        if matches!(self.state, State::Suppress) {
            self.frame.clear();
            if count == 0 {
                self.state = State::Idle;
            }
            return None;
        }
        if matches!(self.state, State::Owned) {
            self.frame.clear();
            if count < self.owned_ids.len() {
                self.state = if count == 0 {
                    State::Idle
                } else {
                    State::Suppress
                };
                return Some(Action::End(time_ms));
            }
            if self.slots.iter().filter_map(|s| s.id).collect::<Vec<_>>() != self.owned_ids {
                self.state = State::Suppress;
                return Some(Action::Cancel(time_ms));
            }
            let Some(points) = self.points() else {
                self.state = State::Suppress;
                return Some(Action::Cancel(time_ms));
            };
            let center = centroid(&points);
            return Some(Action::Move {
                dx: center.0 - self.origin.0,
                dy: center.1 - self.origin.1,
                time_ms,
            });
        }
        if count == 0 {
            let action = self.flush();
            self.state = State::Idle;
            return Some(action);
        }
        if matches!(self.state, State::Pass) {
            return Some(Action::Pass(std::mem::take(&mut self.frame)));
        }
        let Some(points) = self.points() else {
            return Some(self.flush());
        };
        let center = centroid(&points);
        let spread = points
            .iter()
            .map(|p| (p.0 - center.0).hypot((p.1 - center.1) * 2.17))
            .sum::<f64>()
            / count as f64;
        if count > 3 {
            return Some(self.flush());
        }
        if matches!(self.state, State::Idle) {
            self.state = State::Candidate {
                since: now,
                origin: center,
                fingers: count,
                spread,
                source_ms: time_ms,
            };
        }
        let State::Candidate {
            since,
            origin,
            fingers,
            spread: initial_spread,
            source_ms,
        } = self.state
        else {
            unreachable!()
        };
        if count < fingers {
            return Some(self.flush());
        }
        if count > fingers {
            // A third contact may arrive before ownership. Reset only on a
            // contact-count change, never every motion frame.
            self.state = State::Candidate {
                since: now,
                origin: center,
                fingers: count,
                spread,
                source_ms: time_ms,
            };
        } else {
            let dx = center.0 - origin.0;
            let dy = center.1 - origin.1;
            let movement = (dx * 568.0).hypot(dy * 1232.0);
            if fingers == 1 && movement > 4.0 {
                return Some(self.flush());
            }
            if fingers > 1 && (spread - initial_spread).abs() > 0.015 {
                return Some(self.flush());
            }
            // Give a chord a short assembly window. Otherwise its first two
            // contacts can steal a three-finger keyboard gesture.
            if fingers > 1 && movement >= 8.0 && now.saturating_sub(since) >= PAIR_MS {
                self.buffer.append(&mut self.frame);
                self.origin = origin;
                self.state = State::Owned;
                self.owned_ids = self.slots.iter().filter_map(|s| s.id).collect();
                return Some(Action::Begin(Begin {
                    fingers: fingers as u8,
                    start_ms: source_ms,
                    time_ms,
                    x: origin.0,
                    y: origin.1,
                    dx,
                    dy,
                }));
            }
            if now.saturating_sub(since) >= if fingers == 1 { PAIR_MS } else { DECIDE_MS } {
                return Some(self.flush());
            }
        }
        self.buffer.append(&mut self.frame);
        None
    }
}
fn centroid(points: &[(f64, f64)]) -> (f64, f64) {
    (
        points.iter().map(|p| p.0).sum::<f64>() / points.len() as f64,
        points.iter().map(|p| p.1).sum::<f64>() / points.len() as f64,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    fn gate() -> Gate {
        Gate::new(AbsRanges {
            position_x: crate::uinput::InputAbsInfo {
                maximum: 1000,
                ..Default::default()
            },
            position_y: crate::uinput::InputAbsInfo {
                maximum: 2000,
                ..Default::default()
            },
            ..Default::default()
        })
    }
    fn frame(g: &mut Gate, t: u64, points: &[(i32, i32, i32, i32)]) -> Option<Action> {
        for &(slot, id, x, y) in points {
            for (code, value) in [
                (ABS_MT_SLOT, slot),
                (ABS_MT_TRACKING_ID, id),
                (ABS_MT_POSITION_X, x),
                (ABS_MT_POSITION_Y, y),
            ] {
                assert!(g
                    .push(InputEvent::new(0, t as i64 * 1000, EV_ABS, code, value), t)
                    .is_none());
            }
        }
        g.push(
            InputEvent::new(0, t as i64 * 1000, EV_SYN, SYN_REPORT, 0),
            t,
        )
    }
    #[test]
    fn center_pan_tracks_reversal_and_refusal_preserves_timestamps() {
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 400, 1000), (1, 2, 600, 1000)]);
        assert!(frame(&mut g, 20, &[(0, 1, 400, 1040), (1, 2, 600, 1040)]).is_none());
        let Some(Action::Begin(begin)) = frame(&mut g, 50, &[(0, 1, 400, 1100), (1, 2, 600, 1100)])
        else {
            panic!()
        };
        assert_eq!(begin.fingers, 2);
        assert_eq!(begin.start_ms, 0);
        assert_eq!(begin.time_ms, 50);
        assert_eq!(begin.y, 0.5);
        assert!((begin.dy - 0.05).abs() < 1e-6);
        let Some(Action::Pass(events)) = g.acknowledge(false) else {
            panic!()
        };
        assert_eq!(events.iter().filter(|e| e.is_syn_report()).count(), 3);
        assert_eq!(
            events
                .iter()
                .filter(|e| e.is_syn_report())
                .map(|e| e.tv_usec)
                .collect::<Vec<_>>(),
            vec![0, 20000, 50000]
        );
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 400, 1000), (1, 2, 600, 1000)]);
        frame(&mut g, 50, &[(0, 1, 400, 1100), (1, 2, 600, 1100)]);
        g.acknowledge(true);
        assert!(
            matches!(frame(&mut g,60,&[(0,1,400,1000),(1,2,600,1000)]),Some(Action::Move {dy,..}) if dy==0.0)
        );
    }
    #[test]
    fn buffered_motion_retains_source_time_instead_of_reader_time() {
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 400, 1000), (1, 2, 600, 1000)]);
        frame(&mut g, 50, &[(0, 1, 400, 1100), (1, 2, 600, 1100)]);
        g.acknowledge(true);
        g.push(InputEvent::new(0, 60000, EV_ABS, ABS_MT_POSITION_Y, 1200), 200);
        let Some(Action::Move { time_ms, .. }) =
            g.push(InputEvent::new(0, 60000, EV_SYN, SYN_REPORT, 0), 200)
        else { panic!() };
        assert_eq!(time_ms, 60);
    }
    #[test]
    fn third_contact_before_ownership_is_keyboard_count_not_navigation() {
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 300, 1980), (1, 2, 700, 1980)]);
        assert!(frame(&mut g, 10, &[(0, 1, 300, 1950), (1, 2, 700, 1950)]).is_none());
        frame(&mut g, 20, &[(2, 3, 500, 1950)]);
        let Some(Action::Begin(begin)) = frame(
            &mut g,
            70,
            &[(0, 1, 300, 1800), (1, 2, 700, 1800), (2, 3, 500, 1800)],
        ) else {
            panic!()
        };
        assert_eq!(begin.fingers, 3);
        assert!(begin.dy < 0.0);
        g.acknowledge(true);
        assert!(matches!(
            frame(&mut g, 80, &[(1, -1, 0, 0)]),
            Some(Action::End(_))
        ));
        assert!(frame(&mut g, 90, &[(0, -1, 0, 0), (2, -1, 0, 0)]).is_none());
    }
    #[test]
    fn pinch_and_four_contact_streams_remain_libinput_owned() {
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 400, 1000), (1, 2, 600, 1000)]);
        assert!(matches!(
            frame(&mut g, 50, &[(0, 1, 350, 1000), (1, 2, 650, 1000)]),
            Some(Action::Pass(_))
        ));
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 400, 1000), (1, 2, 600, 1000)]);
        assert!(matches!(
            frame(&mut g, 10, &[(2, 3, 400, 1500), (3, 4, 600, 1500)]),
            Some(Action::Pass(_))
        ));
    }
    #[test]
    fn single_pointer_motion_has_prompt_fallthrough_and_idle_taps_expire() {
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 500, 1000)]);
        assert!(matches!(
            frame(&mut g, 10, &[(0, 1, 520, 1000)]),
            Some(Action::Pass(_))
        ));
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 500, 1000)]);
        assert!(matches!(g.expire(45), Some(Action::Pass(_))));
    }
    #[test]
    fn pair_timeout_and_staggered_lift_never_leave_a_click() {
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 400, 1000), (1, 2, 600, 1000)]);
        assert!(matches!(g.expire(250), Some(Action::Pass(_))));
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 400, 1000), (1, 2, 600, 1000)]);
        frame(&mut g, 50, &[(0, 1, 500, 1000), (1, 2, 700, 1000)]);
        g.acknowledge(true);
        assert!(matches!(
            frame(&mut g, 60, &[(1, -1, 0, 0)]),
            Some(Action::End(_))
        ));
        assert!(frame(&mut g, 70, &[(0, -1, 0, 0)]).is_none());
        frame(&mut g, 80, &[(0, 3, 500, 1000)]);
        assert!(matches!(
            frame(&mut g, 90, &[(0, 3, 520, 1000)]),
            Some(Action::Pass(_))
        ));
    }
    #[test]
    fn unchanged_axes_survive_restart_and_new_contact() {
        let mut g = gate();
        g.prime(&[(400, 20), (600, 20)]);
        for t in [0, 100] {
            for (slot, id) in [(0, 1), (1, 2)] {
                g.push(InputEvent::new(0, 0, EV_ABS, ABS_MT_SLOT, slot), t);
                g.push(InputEvent::new(0, 0, EV_ABS, ABS_MT_TRACKING_ID, id), t);
            }
            g.push(InputEvent::new(0, 0, EV_SYN, SYN_REPORT, 0), t);
            for slot in [0, 1] {
                g.push(InputEvent::new(0, 0, EV_ABS, ABS_MT_SLOT, slot), t + 50);
                g.push(
                    InputEvent::new(0, 0, EV_ABS, ABS_MT_POSITION_Y, 100),
                    t + 50,
                );
            }
            assert!(matches!(
                g.push(InputEvent::new(0, 0, EV_SYN, SYN_REPORT, 0), t + 50),
                Some(Action::Begin(_))
            ));
            g.acknowledge(true);
            frame(&mut g, t + 60, &[(0, -1, 400, 20), (1, -1, 600, 20)]);
        }
    }
    #[test]
    fn additional_contact_during_owned_pan_cancels_without_fallthrough() {
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 400, 1000), (1, 2, 600, 1000)]);
        frame(&mut g, 50, &[(0, 1, 400, 1100), (1, 2, 600, 1100)]);
        g.acknowledge(true);
        assert!(matches!(
            frame(&mut g, 60, &[(2, 3, 500, 1100)]),
            Some(Action::Cancel(_))
        ));
        assert!(frame(&mut g, 70, &[(0, -1, 0, 0), (1, -1, 0, 0), (2, -1, 0, 0)]).is_none());
    }
}

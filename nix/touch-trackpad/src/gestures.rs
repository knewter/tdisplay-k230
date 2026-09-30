//! Frame-level shell-edge arbitration. The ordinary libinput relay stays
//! unchanged; an owned edge sequence never emits a synthetic app click.
use crate::event::*;
use crate::uinput::AbsRanges;

const SLOTS: usize = 16;
const MAX_BUFFER: usize = 1024;
const PAIR_MS: u64 = 45;
const DECIDE_MS: u64 = 250;
const EDGE: f64 = 0.12;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Edge {
    Top,
    Bottom,
}
impl Edge {
    pub fn name(self) -> &'static str {
        match self {
            Self::Top => "top",
            Self::Bottom => "bottom",
        }
    }
}

#[derive(Debug)]
pub enum Action {
    Pass(Vec<InputEvent>),
    Begin {
        edge: Edge,
        outward: bool,
        dx: f64,
        dy: f64,
    },
    Move {
        dx: f64,
        dy: f64,
    },
    End,
    Cancel,
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
        edge: Edge,
        since: u64,
        origin: (f64, f64),
        pair: bool,
        distance: f64,
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
    /// A refused begin preserves the original events, including timestamps.
    pub fn acknowledge(&mut self, accepted: bool) -> Option<Action> {
        if accepted {
            self.buffer.clear();
            None
        } else {
            Some(self.flush())
        }
    }
    pub fn expire(&mut self, now: u64) -> Option<Action> {
        if let State::Candidate { since, pair, .. } = self.state {
            if now.saturating_sub(since) >= if pair { DECIDE_MS } else { PAIR_MS } {
                return Some(self.flush());
            }
        }
        None
    }
    pub fn push(&mut self, ev: InputEvent, now: u64) -> Option<Action> {
        match (ev.type_, ev.code) {
            (EV_ABS, ABS_MT_SLOT) => self.slot = (ev.value as usize).min(SLOTS - 1),
            (EV_ABS, ABS_MT_TRACKING_ID) => {
                self.slots[self.slot].id = (ev.value >= 0).then_some(ev.value);
                // Protocol B slot axes persist across tracking IDs. Linux
                // filters unchanged positions even on a fresh contact; do not
                // require a driver to resend an unchanged X or Y.
            }
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
                return Some(Action::Cancel);
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
            // Real fingers usually lift in separate hardware frames. The
            // first lift ends the gesture; remaining fingers stay suppressed.
            if count < 2 {
                self.state = if count == 0 {
                    State::Idle
                } else {
                    State::Suppress
                };
                return Some(Action::End);
            }
            if count > 2
                || self.slots.iter().filter_map(|s| s.id).collect::<Vec<_>>() != self.owned_ids
            {
                self.state = State::Suppress;
                return Some(Action::Cancel);
            }
            let Some(points) = self.points() else {
                self.state = State::Suppress;
                return Some(Action::Cancel);
            };
            let center = (
                (points[0].0 + points[1].0) / 2.0,
                (points[0].1 + points[1].1) / 2.0,
            );
            return Some(Action::Move {
                dx: center.0 - self.origin.0,
                dy: center.1 - self.origin.1,
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
        let center = (
            points.iter().map(|p| p.0).sum::<f64>() / count as f64,
            points.iter().map(|p| p.1).sum::<f64>() / count as f64,
        );
        let distance = if count == 2 {
            ((points[1].0 - points[0].0).powi(2) + ((points[1].1 - points[0].1) * 2.17).powi(2))
                .sqrt()
        } else {
            0.0
        };
        if matches!(self.state, State::Idle) {
            let edge = if points.iter().all(|p| p.1 <= EDGE) {
                Edge::Top
            } else if points.iter().all(|p| p.1 >= 1.0 - EDGE) {
                Edge::Bottom
            } else {
                return Some(self.flush());
            };
            if count > 2 {
                return Some(self.flush());
            }
            self.state = State::Candidate {
                edge,
                since: now,
                origin: center,
                pair: count == 2,
                distance,
            };
        }
        let State::Candidate {
            edge,
            since,
            origin,
            pair,
            distance: initial_distance,
        } = self.state
        else {
            unreachable!()
        };
        if count > 2
            || !points.iter().all(|p| match edge {
                Edge::Top => p.1 <= EDGE * 1.5,
                Edge::Bottom => p.1 >= 1.0 - EDGE * 1.5,
            }) && !pair
        {
            return Some(self.flush());
        }
        if count == 2 && !pair {
            self.state = State::Candidate {
                edge,
                since: now,
                origin: center,
                pair: true,
                distance,
            };
        } else {
            let dx = center.0 - origin.0;
            let dy = center.1 - origin.1;
            if !pair && (dx.abs() * 568.0 > 4.0 || dy.abs() * 1232.0 > 4.0) {
                return Some(self.flush());
            }
            if pair && count != 2 {
                return Some(self.flush());
            }
            if pair && (distance - initial_distance).abs() > 0.03 {
                return Some(self.flush());
            }
            if pair && dx.abs() * 568.0 > 8.0 && dx.abs() * 568.0 > dy.abs() * 1232.0 * 1.25 {
                return Some(self.flush());
            }
            if pair && dy.abs() * 1232.0 >= 8.0 && dy.abs() * 1232.0 > dx.abs() * 568.0 * 1.25 {
                self.buffer.append(&mut self.frame);
                self.origin = origin;
                self.state = State::Owned;
                self.owned_ids = self.slots.iter().filter_map(|s| s.id).collect();
                return Some(Action::Begin {
                    edge,
                    outward: match edge {
                        Edge::Top => dy < 0.0,
                        Edge::Bottom => dy > 0.0,
                    },
                    dx,
                    dy,
                });
            }
            if now.saturating_sub(since) >= if pair { DECIDE_MS } else { PAIR_MS } {
                return Some(self.flush());
            }
        }
        self.buffer.append(&mut self.frame);
        None
    }
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
    fn unchanged_slot_axes_survive_lift_and_restart() {
        let mut g = gate();
        g.prime(&[(400, 20), (600, 20)]);
        for time in [0, 30] {
            for (slot, id) in [(0, 1), (1, 2)] {
                g.push(InputEvent::new(0, 0, EV_ABS, ABS_MT_SLOT, slot), time);
                g.push(InputEvent::new(0, 0, EV_ABS, ABS_MT_TRACKING_ID, id), time);
            }
            assert!(g
                .push(InputEvent::new(0, 0, EV_SYN, SYN_REPORT, 0), time)
                .is_none());
            for slot in [0, 1] {
                g.push(InputEvent::new(0, 0, EV_ABS, ABS_MT_SLOT, slot), time + 10);
                g.push(
                    InputEvent::new(0, 0, EV_ABS, ABS_MT_POSITION_Y, 60),
                    time + 10,
                );
            }
            assert!(matches!(
                g.push(InputEvent::new(0, 0, EV_SYN, SYN_REPORT, 0), time + 10),
                Some(Action::Begin { .. })
            ));
            g.acknowledge(true);
            frame(&mut g, time + 20, &[(0, -1, 400, 20), (1, -1, 600, 20)]);
        }
    }
    #[test]
    fn center_and_one_finger_motion_keep_original_input() {
        let mut g = gate();
        assert!(matches!(
            frame(&mut g, 0, &[(0, 1, 500, 1000)]),
            Some(Action::Pass(_))
        ));
        let mut g = gate();
        assert!(frame(&mut g, 0, &[(0, 1, 500, 20)]).is_none());
        assert!(matches!(
            frame(&mut g, 10, &[(0, 1, 520, 20)]),
            Some(Action::Pass(_))
        ));
    }
    #[test]
    fn candidate_timeout_has_no_missing_down_or_reordered_time() {
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 500, 20)]);
        let Some(Action::Pass(events)) = g.expire(45) else {
            panic!()
        };
        assert!(events
            .iter()
            .any(|e| e.code == ABS_MT_TRACKING_ID && e.value == 1));
        assert!(events.last().unwrap().is_syn_report());
        assert!(events.iter().all(|e| e.tv_usec == 0));
    }
    #[test]
    fn top_bottom_pairs_reversal_and_refusal() {
        for (start, end, edge) in [(20, 60, Edge::Top), (1980, 1940, Edge::Bottom)] {
            let mut g = gate();
            frame(&mut g, 0, &[(0, 1, 400, start), (1, 2, 600, start)]);
            assert!(
                matches!(frame(&mut g,10,&[(0,1,400,end),(1,2,600,end)]),Some(Action::Begin { edge:e,.. }) if e==edge)
            );
            let Some(Action::Pass(events)) = g.acknowledge(false) else {
                panic!()
            };
            assert_eq!(events.iter().filter(|e| e.is_syn_report()).count(), 2);
            let mut g = gate();
            frame(&mut g, 0, &[(0, 1, 400, start), (1, 2, 600, start)]);
            frame(&mut g, 10, &[(0, 1, 400, end), (1, 2, 600, end)]);
            g.acknowledge(true);
            assert!(
                matches!(frame(&mut g,20,&[(0,1,400,start),(1,2,600,start)]),Some(Action::Move { dy,.. }) if dy==0.0)
            );
            assert!(matches!(
                frame(&mut g, 30, &[(0, -1, 0, 0), (1, -1, 0, 0)]),
                Some(Action::End)
            ));
        }
    }
    #[test]
    fn pinch_horizontal_and_extra_contacts_are_not_shell_edges() {
        for next in [
            vec![(0, 1, 350, 20), (1, 2, 650, 20)],
            vec![(0, 1, 450, 20), (1, 2, 650, 20)],
            vec![(2, 3, 500, 20)],
        ] {
            let mut g = gate();
            frame(&mut g, 0, &[(0, 1, 400, 20), (1, 2, 600, 20)]);
            assert!(matches!(frame(&mut g, 10, &next), Some(Action::Pass(_))));
        }
    }
    #[test]
    fn staggered_lift_finishes_without_a_stray_click() {
        let mut g = gate();
        frame(&mut g, 0, &[(0, 1, 400, 20), (1, 2, 600, 20)]);
        frame(&mut g, 10, &[(0, 1, 400, 60), (1, 2, 600, 60)]);
        g.acknowledge(true);
        assert!(matches!(
            frame(&mut g, 20, &[(1, -1, 0, 0)]),
            Some(Action::End)
        ));
        assert!(frame(&mut g, 30, &[(0, -1, 0, 0)]).is_none());
        assert!(matches!(
            frame(&mut g, 40, &[(0, 3, 500, 1000)]),
            Some(Action::Pass(_))
        ));
    }
}

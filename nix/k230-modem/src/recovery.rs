//! The recovery gate: at most one power-cycle per interval.

use std::time::{Duration, Instant};

pub struct RecoveryGate {
    min_interval: Duration,
    last: Option<Instant>,
}

impl RecoveryGate {
    pub fn new(min_interval: Duration) -> Self {
        RecoveryGate { min_interval, last: None }
    }

    /// True (and records the attempt) when a recovery may run now.
    pub fn permit(&mut self, now: Instant) -> bool {
        match self.last {
            Some(t) if now.saturating_duration_since(t) < self.min_interval => false,
            _ => {
                self.last = Some(now);
                true
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn at_most_one_per_minute() {
        let t0 = Instant::now();
        let mut g = RecoveryGate::new(Duration::from_secs(60));
        assert!(g.permit(t0));
        assert!(!g.permit(t0 + Duration::from_secs(10)));
        assert!(!g.permit(t0 + Duration::from_secs(59)));
        assert!(g.permit(t0 + Duration::from_secs(61)));
        assert!(!g.permit(t0 + Duration::from_secs(100)));
    }
}

//! Pure state for `k230-osk-focus`: when a focused text field should raise
//! or lower the on-screen keyboard.
//!
//! The input-method-v2 protocol double-buffers `activate`/`deactivate` and
//! applies them at `done`. A focused text field is "active"; a field that
//! loses focus (or an app that stops asking for text input) is "inactive".
//! This module turns that stream into at most one `show` or `hide` action
//! per `done`, and decides whether a `show` is suppressed because a person
//! has just been typing on the keyboard base.
//!
//! Nothing here touches Wayland, files or the clock, so the host tests cover
//! every decision.

use std::time::Duration;

/// How long after the last physical key press from the base a newly focused
/// field does not raise the on-screen keyboard.
pub const DEFAULT_SUPPRESS: Duration = Duration::from_secs(10);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Event {
    Activate,
    Deactivate,
    Done,
    /// Another client owns the input method; nothing will ever arrive.
    Unavailable,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Action {
    Show,
    Hide,
}

#[derive(Debug, Default)]
pub struct Focus {
    /// State applied at the last `done`.
    active: bool,
    /// State announced since, applied at the next `done`.
    pending: bool,
    unavailable: bool,
}

impl Focus {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn is_active(&self) -> bool {
        self.active
    }

    pub fn is_unavailable(&self) -> bool {
        self.unavailable
    }

    /// Feed one protocol event. `since_last_key` is the time since the last
    /// physical key press from the base (`None` when there never was one or
    /// it cannot be read); it is only consulted when a `Show` is possible.
    pub fn handle(
        &mut self,
        event: Event,
        since_last_key: impl FnOnce() -> Option<Duration>,
        suppress: Duration,
    ) -> Option<Action> {
        match event {
            Event::Activate => {
                self.pending = true;
                None
            }
            Event::Deactivate => {
                self.pending = false;
                None
            }
            Event::Unavailable => {
                self.unavailable = true;
                None
            }
            Event::Done => {
                if self.pending == self.active {
                    return None;
                }
                self.active = self.pending;
                if self.active {
                    if show_suppressed(since_last_key(), suppress) {
                        None
                    } else {
                        Some(Action::Show)
                    }
                } else {
                    Some(Action::Hide)
                }
            }
        }
    }
}

/// A `show` is suppressed while the last base key press is younger than
/// `suppress`.
pub fn show_suppressed(since_last_key: Option<Duration>, suppress: Duration) -> bool {
    matches!(since_last_key, Some(age) if age < suppress)
}

/// Age of a stamp whose mtime is `mtime_secs` when it is `now_secs`.
/// A stamp slightly ahead of the clock has age zero (just pressed); one more
/// than a minute ahead is ignored, so a clock step cannot silence the
/// keyboard indefinitely.
pub fn stamp_age(now_secs: f64, mtime_secs: f64) -> Option<Duration> {
    let delta = now_secs - mtime_secs;
    if delta >= 0.0 {
        Some(Duration::from_secs_f64(delta))
    } else if delta > -60.0 {
        Some(Duration::ZERO)
    } else {
        None
    }
}

/// Parse `K230_OSK_SUPPRESS_SECONDS`; anything unusable is the default.
pub fn parse_suppress(text: Option<&str>) -> Duration {
    text.and_then(|t| t.trim().parse::<f64>().ok())
        .filter(|s| s.is_finite() && *s >= 0.0 && *s <= 3600.0)
        .map(Duration::from_secs_f64)
        .unwrap_or(DEFAULT_SUPPRESS)
}

/// App ids whose focused window never raises the keyboard, from a comma or
/// whitespace separated list. Terminal-hosted apps such as the Timer run in
/// foot, which enables text input for every window, but take only touch.
pub fn parse_ignore(text: Option<&str>) -> Vec<String> {
    text.unwrap_or("")
        .split(|c: char| c == ',' || c.is_whitespace())
        .filter(|id| !id.is_empty())
        .map(str::to_string)
        .collect()
}

/// The `app_id` of the focused window in a `get_tree` reply. The walk is
/// bounded so a malformed tree cannot stall the client.
pub fn focused_app_id(tree: &serde_json::Value) -> Option<String> {
    let mut stack = vec![tree];
    let mut budget = 4096;
    while let Some(node) = stack.pop() {
        budget -= 1;
        if budget == 0 {
            return None;
        }
        if node.get("focused").and_then(|f| f.as_bool()) == Some(true) {
            return node.get("app_id").and_then(|a| a.as_str()).map(str::to_string);
        }
        for key in ["nodes", "floating_nodes"] {
            if let Some(children) = node.get(key).and_then(|c| c.as_array()) {
                stack.extend(children);
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    const S: Duration = Duration::from_secs(10);

    fn feed(f: &mut Focus, evs: &[Event], age: Option<Duration>) -> Option<Action> {
        let mut last = None;
        for e in evs {
            if let Some(a) = f.handle(*e, || age, S) {
                last = Some(a);
            }
        }
        last
    }

    #[test]
    fn activate_applies_only_at_done() {
        let mut f = Focus::new();
        assert_eq!(f.handle(Event::Activate, || None, S), None);
        assert!(!f.is_active());
        assert_eq!(f.handle(Event::Done, || None, S), Some(Action::Show));
        assert!(f.is_active());
    }

    #[test]
    fn deactivate_hides() {
        let mut f = Focus::new();
        feed(&mut f, &[Event::Activate, Event::Done], None);
        assert_eq!(
            feed(&mut f, &[Event::Deactivate, Event::Done], None),
            Some(Action::Hide)
        );
        assert!(!f.is_active());
    }

    #[test]
    fn done_without_change_is_quiet() {
        let mut f = Focus::new();
        assert_eq!(feed(&mut f, &[Event::Done], None), None);
        feed(&mut f, &[Event::Activate, Event::Done], None);
        assert_eq!(feed(&mut f, &[Event::Activate, Event::Done], None), None);
    }

    #[test]
    fn deactivate_then_activate_in_one_batch_is_no_change() {
        let mut f = Focus::new();
        feed(&mut f, &[Event::Activate, Event::Done], None);
        assert_eq!(
            feed(&mut f, &[Event::Deactivate, Event::Activate, Event::Done], None),
            None
        );
        assert!(f.is_active());
    }

    #[test]
    fn recent_key_press_suppresses_show_but_not_hide() {
        let mut f = Focus::new();
        let recent = Some(Duration::from_secs(3));
        assert_eq!(feed(&mut f, &[Event::Activate, Event::Done], recent), None);
        assert!(f.is_active());
        assert_eq!(
            feed(&mut f, &[Event::Deactivate, Event::Done], recent),
            Some(Action::Hide)
        );
    }

    #[test]
    fn old_key_press_does_not_suppress() {
        let mut f = Focus::new();
        let old = Some(Duration::from_secs(10));
        assert_eq!(
            feed(&mut f, &[Event::Activate, Event::Done], old),
            Some(Action::Show)
        );
    }

    #[test]
    fn key_age_is_not_read_unless_a_show_is_possible() {
        let mut f = Focus::new();
        assert_eq!(f.handle(Event::Done, || panic!("read"), S), None);
        f.handle(Event::Activate, || panic!("read"), S);
        f.handle(Event::Deactivate, || panic!("read"), S);
        assert_eq!(f.handle(Event::Done, || panic!("read"), S), None);
    }

    #[test]
    fn unavailable_is_recorded_and_silent() {
        let mut f = Focus::new();
        assert_eq!(f.handle(Event::Unavailable, || None, S), None);
        assert!(f.is_unavailable());
    }

    #[test]
    fn suppression_boundaries() {
        assert!(!show_suppressed(None, S));
        assert!(show_suppressed(Some(Duration::ZERO), S));
        assert!(show_suppressed(Some(Duration::from_millis(9999)), S));
        assert!(!show_suppressed(Some(S), S));
        assert!(!show_suppressed(Some(Duration::from_secs(1)), Duration::ZERO));
    }

    #[test]
    fn stamp_age_handles_clock_steps() {
        assert_eq!(stamp_age(100.0, 97.5), Some(Duration::from_millis(2500)));
        assert_eq!(stamp_age(100.0, 101.0), Some(Duration::ZERO));
        assert_eq!(stamp_age(100.0, 500.0), None);
    }

    #[test]
    fn suppress_setting_parses_or_defaults() {
        assert_eq!(parse_suppress(None), DEFAULT_SUPPRESS);
        assert_eq!(parse_suppress(Some("4")), Duration::from_secs(4));
        assert_eq!(parse_suppress(Some(" 0.5 ")), Duration::from_millis(500));
        assert_eq!(parse_suppress(Some("0")), Duration::ZERO);
        assert_eq!(parse_suppress(Some("-1")), DEFAULT_SUPPRESS);
        assert_eq!(parse_suppress(Some("abc")), DEFAULT_SUPPRESS);
        assert_eq!(parse_suppress(Some("1e9")), DEFAULT_SUPPRESS);
    }

    #[test]
    fn the_ignore_list_and_the_focused_app_id_are_read() {
        assert_eq!(parse_ignore(Some("k230-timer, k230-clock k230-weather")), ["k230-timer", "k230-clock", "k230-weather"]);
        assert!(parse_ignore(None).is_empty());
        let tree = serde_json::json!({"focused": false, "nodes": [
            {"focused": false, "nodes": [{"focused": false, "app_id": "k230-terminal"}],
             "floating_nodes": [{"focused": true, "app_id": "k230-timer"}]}]});
        assert_eq!(focused_app_id(&tree).as_deref(), Some("k230-timer"));
        assert_eq!(focused_app_id(&serde_json::json!({"focused": false})), None);
    }
}

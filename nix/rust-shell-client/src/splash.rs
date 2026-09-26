//! Pure state for the Android-12-style instant app-launch splash: what is
//! being shown, when a pending splash should time out, how its icon fades
//! in, and whether a live sway `window` IPC event is the window it is
//! waiting for. Deliberately no rendering and no I/O here -- see
//! `render.rs`'s `ensure_splash_bake`/`draw_splash` for the bitmap and
//! `sway_ipc.rs` for the live event source and `/proc` process-tree walk
//! this reacts to. Kept separate so every transition (launch -> mapped,
//! launch -> timeout, launch -> process exit, already-running -> no
//! splash) is testable without a compositor, a socket, or a real process.
use std::time::{Duration, Instant};

/// How long a splash may sit `Pending` before becoming the recoverable
/// "taking longer than usual" state. Ten seconds: long enough that an
/// ordinary cold start (icon decode, catalog re-parse, process exec, first
/// frame) never trips it on this hardware, short enough that a genuinely
/// stuck launch does not leave a person staring at an icon indefinitely.
/// Matches the task's own "about 10s" figure.
pub const SPLASH_TIMEOUT: Duration = Duration::from_secs(10);

/// The icon/name fade-in duration. 220ms sits inside the requested
/// 200-250ms band. See `design.md`'s recorded rejection of a grow-from-rect
/// scale animation on this hardware: the backdrop itself is painted opaque
/// on the very first frame (so the previously active app can never show
/// through, even transiently) and only the icon/name ease in on top of it,
/// which is cheaper than animating a clip rect on a software rasterizer.
pub const SPLASH_FADE: Duration = Duration::from_millis(220);

/// How long the "Couldn't open <Name>" failure state stays up before
/// dismissing itself automatically -- long enough to actually read, short
/// enough that "and dismiss" (the task's own wording) reads as automatic,
/// not stuck. A tap dismisses it sooner regardless (`main.rs`'s
/// `dismiss_splash`, reachable the whole time this state is up).
pub const FAILED_AUTO_DISMISS: Duration = Duration::from_millis(1600);

/// How this splash will recognize the window it is waiting for.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SplashTarget {
    /// The PID `gio::AppLaunchContext` reported for the spawned process
    /// (see `main.rs`'s `launch_selected`). A `window` event's own `pid` is
    /// accepted if it equals this exactly, or is a descendant of it within
    /// a bounded number of `/proc` parent hops -- see `pid_or_ancestor`'s
    /// own doc for why a hop count is needed at all (a `Terminal=true`
    /// entry maps as its terminal's own process, and a shell-wrapped
    /// `Exec=` can add one intermediate process either way).
    Pid(i32),
    /// No PID was available (gio reported none -- e.g. a launch whose
    /// platform data carried no `pid` key). Falls back to "the next new
    /// window sway reports at all". Sound only because `launch_in_flight`
    /// already guarantees this client never has two launches racing at
    /// once, so there is never a second candidate to confuse it with.
    LaunchOrder,
}

/// What a `Splash` is currently telling the person.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SplashStatus {
    /// Waiting for the target window to map.
    Pending,
    /// `SPLASH_TIMEOUT` elapsed with no matching window: "Taking longer
    /// than usual...", with a tap-to-dismiss/Home way out.
    TimedOut,
    /// The spawned process exited before any matching window mapped:
    /// "Couldn't open <Name>", dismissed automatically shortly after or by
    /// a tap.
    Failed,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Splash {
    pub name: String,
    pub icon: Option<String>,
    pub target: SplashTarget,
    /// When this splash first appeared -- fixed for its whole lifetime,
    /// and what `fade_alpha` measures the icon's fade-in against.
    pub started: Instant,
    pub status: SplashStatus,
    /// When `status` last changed -- what `should_auto_dismiss_failed`
    /// measures against, kept separate from `started` so a status change
    /// (e.g. `Pending` -> `Failed`) does not also have to replay the
    /// icon's own one-time fade-in.
    pub status_since: Instant,
}

impl Splash {
    pub fn new(name: String, icon: Option<String>, target: SplashTarget, started: Instant) -> Self {
        Self {
            name,
            icon,
            target,
            started,
            status: SplashStatus::Pending,
            status_since: started,
        }
    }

    pub fn set_status(&mut self, status: SplashStatus, now: Instant) {
        self.status = status;
        self.status_since = now;
    }
}

/// Whether the `Failed` state (entered at `status_since`) has been up long
/// enough (measured at `now`) to dismiss itself automatically.
pub fn should_auto_dismiss_failed(status_since: Instant, now: Instant) -> bool {
    now.saturating_duration_since(status_since) >= FAILED_AUTO_DISMISS
}

/// Whether a `Pending` splash started at `started` has been waiting long
/// enough (measured at `now`) to become `TimedOut`. Pure so the boundary is
/// testable without a real sleep.
pub fn should_time_out(started: Instant, now: Instant) -> bool {
    now.saturating_duration_since(started) >= SPLASH_TIMEOUT
}

/// The icon/name's current fade-in alpha: an ease-out cubic
/// (`1 - (1-t)^3`) over `SPLASH_FADE` from `started`, matching the
/// existing `tray_backdrop_alpha` easing convention in `render.rs`. Pure,
/// monotonic in `now`, and saturates at exactly `1.0`.
pub fn fade_alpha(started: Instant, now: Instant) -> f64 {
    let elapsed = now.saturating_duration_since(started).as_secs_f64();
    let total = SPLASH_FADE.as_secs_f64();
    let t = if total <= 0.0 {
        1.0
    } else {
        (elapsed / total).clamp(0.0, 1.0)
    };
    1.0 - (1.0 - t).powi(3)
}

/// Walks `candidate`'s ancestry (via `parent_of`, real callers use
/// `sway_ipc::parent_pid`, which reads `/proc/<pid>/stat`'s ppid field) up
/// to `max_depth` hops looking for `target`. Bounded so a `/proc` ppid
/// cycle or a pid-reuse coincidence can never loop forever; `parent_of` is
/// a plain closure so this is testable against a fixed map instead of live
/// `/proc`.
pub fn pid_or_ancestor<F: Fn(i32) -> Option<i32>>(
    target: i32,
    candidate: i32,
    parent_of: F,
    max_depth: u32,
) -> bool {
    let mut pid = candidate;
    for _ in 0..=max_depth {
        if pid == target {
            return true;
        }
        match parent_of(pid) {
            Some(parent) if parent > 0 && parent != pid => pid = parent,
            _ => return false,
        }
    }
    false
}

/// Whether a sway `window` event with the given `change` and `event_pid` is
/// the window `target` is waiting for. Only a `"new"` change is ever a
/// match: `focus`/`title`/`close`/etc. say nothing about first mapping, and
/// treating them as a match would let an unrelated existing window's title
/// change dismiss the splash early.
pub fn window_event_matches<F: Fn(i32) -> Option<i32>>(
    target: SplashTarget,
    change: &str,
    event_pid: Option<i32>,
    parent_of: F,
) -> bool {
    if change != "new" {
        return false;
    }
    match target {
        SplashTarget::LaunchOrder => true,
        SplashTarget::Pid(pid) => {
            event_pid.is_some_and(|candidate| pid_or_ancestor(pid, candidate, parent_of, 4))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn instant_plus(base: Instant, millis: u64) -> Instant {
        base + Duration::from_millis(millis)
    }

    #[test]
    fn launch_to_mapped_dismisses_only_on_a_new_window_change() {
        let target = SplashTarget::Pid(100);
        let parent_of = |_pid: i32| None;
        assert!(!window_event_matches(target, "focus", Some(100), parent_of));
        assert!(!window_event_matches(target, "title", Some(100), parent_of));
        assert!(!window_event_matches(target, "close", Some(100), parent_of));
        assert!(window_event_matches(target, "new", Some(100), parent_of));
    }

    #[test]
    fn launch_to_mapped_matches_exact_pid() {
        let target = SplashTarget::Pid(4242);
        assert!(window_event_matches(target, "new", Some(4242), |_| None));
        assert!(!window_event_matches(target, "new", Some(4243), |_| None));
        assert!(!window_event_matches(target, "new", None, |_| None));
    }

    #[test]
    fn launch_to_mapped_matches_a_bounded_descendant_pid() {
        // A shell wrapper (or a terminal indirection) spawned as the
        // captured pid, whose own child is the window's real owner.
        let target = SplashTarget::Pid(10);
        let parent_of = |pid: i32| match pid {
            13 => Some(12),
            12 => Some(11),
            11 => Some(10),
            _ => None,
        };
        assert!(window_event_matches(target, "new", Some(13), parent_of));
        assert!(window_event_matches(target, "new", Some(11), parent_of));
        // Five hops from the target exceeds the bounded walk (max_depth=4).
        let deep_parent_of = |pid: i32| match pid {
            20 => Some(19),
            19 => Some(18),
            18 => Some(17),
            17 => Some(16),
            16 => Some(15),
            15 => Some(10),
            _ => None,
        };
        assert!(!window_event_matches(target, "new", Some(20), deep_parent_of));
    }

    #[test]
    fn a_ppid_cycle_terminates_instead_of_looping() {
        let target = SplashTarget::Pid(999);
        // 5 -> 6 -> 5 -> 6 ... never reaches 999 and never a plain None.
        let parent_of = |pid: i32| if pid == 5 { Some(6) } else { Some(5) };
        assert!(!window_event_matches(target, "new", Some(5), parent_of));
    }

    #[test]
    fn launch_order_matches_the_first_new_window_regardless_of_pid() {
        let target = SplashTarget::LaunchOrder;
        assert!(window_event_matches(target, "new", None, |_| None));
        assert!(window_event_matches(target, "new", Some(1), |_| None));
        assert!(!window_event_matches(target, "focus", None, |_| None));
    }

    #[test]
    fn launch_to_timeout_trips_at_exactly_ten_seconds() {
        let base = Instant::now();
        assert!(!should_time_out(base, instant_plus(base, 9_999)));
        assert!(should_time_out(base, instant_plus(base, 10_000)));
        assert!(should_time_out(base, instant_plus(base, 20_000)));
    }

    #[test]
    fn fade_alpha_eases_from_zero_to_one_and_saturates() {
        let base = Instant::now();
        assert_eq!(fade_alpha(base, base), 0.0);
        let mid = fade_alpha(base, instant_plus(base, 110));
        assert!(mid > 0.4 && mid < 0.95, "expected an eased mid-point, got {mid}");
        assert_eq!(fade_alpha(base, instant_plus(base, 220)), 1.0);
        assert_eq!(fade_alpha(base, instant_plus(base, 10_000)), 1.0);
    }

    #[test]
    fn fade_alpha_is_monotonic() {
        let base = Instant::now();
        let mut previous = 0.0;
        for millis in (0..=220).step_by(10) {
            let alpha = fade_alpha(base, instant_plus(base, millis));
            assert!(alpha + 1e-9 >= previous, "alpha regressed at {millis}ms");
            previous = alpha;
        }
    }

    #[test]
    fn a_failed_splash_auto_dismisses_after_its_own_hold_but_not_before() {
        let base = Instant::now();
        let mut splash = Splash::new("Foot".into(), None, SplashTarget::Pid(1), base);
        // A status change well after `started` (e.g. the process exited
        // several seconds into a launch) resets only `status_since`.
        let failed_at = instant_plus(base, 5_000);
        splash.set_status(SplashStatus::Failed, failed_at);
        assert_eq!(splash.status, SplashStatus::Failed);
        assert_eq!(splash.status_since, failed_at);
        assert_eq!(splash.started, base);
        assert!(!should_auto_dismiss_failed(failed_at, instant_plus(failed_at, 1_599)));
        assert!(should_auto_dismiss_failed(failed_at, instant_plus(failed_at, 1_600)));
    }

    #[test]
    fn already_running_never_needs_a_target_at_all() {
        // `main.rs`'s `LaunchOutcome::Focused` path never constructs a
        // `Splash` in the first place -- this test just documents that a
        // `Splash` is meaningless without one of the two `SplashTarget`
        // variants, i.e. the type system itself keeps "no splash for an
        // already-focused app" true rather than a runtime check.
        let splash = Splash::new("Foot".into(), Some("foot".into()), SplashTarget::Pid(1), Instant::now());
        assert_eq!(splash.status, SplashStatus::Pending);
    }
}

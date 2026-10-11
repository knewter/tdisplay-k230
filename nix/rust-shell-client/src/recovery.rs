//! Person-facing copy for the shell's loading, empty, stale, denied and
//! ended states, each paired with the one recovery action the surface
//! offers. Pure data: callers keep owning their window, menu, service and
//! video lifecycles and only ask here what to say. Raw helper codes,
//! filesystem paths and GLib diagnostics belong in the shell log, never in
//! this copy -- `person_safe` is the guard the tests hold every string to.

/// The one way out a recovery state names. `label` is the default wording;
/// a surface whose own exit control already reads differently (Settings'
/// "Done", Power's "Cancel") passes that label to [`RecoveryState::message`]
/// so the copy names the control the person can actually see.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RecoveryAction {
    Back,
    Apps,
    Home,
    Retry,
    Cancel,
    Stop,
}

impl RecoveryAction {
    pub fn label(self) -> &'static str {
        match self {
            RecoveryAction::Back => "Back",
            RecoveryAction::Apps => "Apps",
            RecoveryAction::Home => "Home",
            RecoveryAction::Retry => "Retry",
            RecoveryAction::Cancel => "Cancel",
            RecoveryAction::Stop => "Stop",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RecoveryState {
    /// An app's window list has been requested but not received.
    WindowsLoading,
    /// The list arrived with nothing selectable in it.
    WindowsEmpty,
    /// The window a person picked closed before it could be focused. The
    /// shell must not silently focus a different window instead.
    WindowStale,
    /// A system action was refused.
    ActionDenied,
    /// A system action failed for any other reason.
    ActionFailed,
    VideoStopped,
    VideoEnded,
    VideoCancelled,
}

pub const ALL: [RecoveryState; 8] = [
    RecoveryState::WindowsLoading,
    RecoveryState::WindowsEmpty,
    RecoveryState::WindowStale,
    RecoveryState::ActionDenied,
    RecoveryState::ActionFailed,
    RecoveryState::VideoStopped,
    RecoveryState::VideoEnded,
    RecoveryState::VideoCancelled,
];

impl RecoveryState {
    /// Stable identifier for logs and evidence; never shown to a person.
    pub fn id(self) -> &'static str {
        match self {
            RecoveryState::WindowsLoading => "windows-loading",
            RecoveryState::WindowsEmpty => "windows-empty",
            RecoveryState::WindowStale => "window-stale",
            RecoveryState::ActionDenied => "action-denied",
            RecoveryState::ActionFailed => "action-failed",
            RecoveryState::VideoStopped => "video-stopped",
            RecoveryState::VideoEnded => "video-ended",
            RecoveryState::VideoCancelled => "video-cancelled",
        }
    }

    pub fn copy(self) -> &'static str {
        match self {
            RecoveryState::WindowsLoading => "Loading windows…",
            RecoveryState::WindowsEmpty => "No open windows",
            RecoveryState::WindowStale => "That window has closed",
            RecoveryState::ActionDenied => "That action isn't allowed",
            RecoveryState::ActionFailed => "That didn't work",
            RecoveryState::VideoStopped => "Video stopped",
            RecoveryState::VideoEnded => "Video ended",
            RecoveryState::VideoCancelled => "Video cancelled",
        }
    }

    pub fn action(self) -> RecoveryAction {
        match self {
            RecoveryState::WindowsLoading => RecoveryAction::Back,
            RecoveryState::WindowsEmpty | RecoveryState::WindowStale => RecoveryAction::Apps,
            RecoveryState::ActionDenied => RecoveryAction::Back,
            RecoveryState::ActionFailed => RecoveryAction::Back,
            RecoveryState::VideoStopped | RecoveryState::VideoCancelled => RecoveryAction::Back,
            RecoveryState::VideoEnded => RecoveryAction::Apps,
        }
    }

    /// `copy · label`, with `label` defaulting to the action's own wording.
    pub fn message(self, label: Option<&str>) -> String {
        format!("{} · {}", self.copy(), label.unwrap_or(self.action().label()))
    }
}

/// `run_app_action`'s error when the picked window vanished between the
/// menu opening and the tap -- matched by the launch path to show
/// [`RecoveryState::WindowStale`] instead of a generic launch failure.
pub const STALE_WINDOW_ERROR: &str = "window is no longer available";

/// Maps a settings/notification helper error code to the state a person
/// sees. Unknown codes are a failure, not a denial; the code itself is
/// logged by the caller and never rendered.
pub fn action_error_state(code: &str) -> RecoveryState {
    if code == "denied" || code.ends_with("-denied") {
        RecoveryState::ActionDenied
    } else {
        RecoveryState::ActionFailed
    }
}

/// Whether `text` is fit to render: no filesystem path, no helper/GLib
/// diagnostic, no machine error code, and nothing secret-shaped.
pub fn person_safe(text: &str) -> bool {
    let lower = text.to_ascii_lowercase();
    !text.contains('/')
        && !text.contains('\\')
        && !text.chars().any(char::is_control)
        && !["glib", "gio", "gdbus", "critical", "traceback", "errno", "token", "password", "psk", "secret"]
            .iter()
            .any(|word| lower.contains(word))
        // kebab-case machine codes ("action-denied", "target-unavailable")
        && !text
            .split(|c: char| c.is_whitespace() || c == '·')
            .any(|word| word.contains('-') && word.chars().all(|c| c.is_ascii_lowercase() || c == '-'))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_state_has_distinct_id_safe_copy_and_a_named_action() {
        let mut ids: Vec<_> = ALL.iter().map(|s| s.id()).collect();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), ALL.len());
        for state in ALL {
            assert!(person_safe(state.copy()), "{}", state.id());
            assert!(person_safe(&state.message(None)), "{}", state.id());
            assert!(state.message(None).ends_with(state.action().label()));
            assert!(state.copy().chars().count() <= 32, "{} copy is not short", state.id());
        }
    }

    #[test]
    fn each_state_offers_the_required_recovery_action() {
        use RecoveryAction::*;
        use RecoveryState::*;
        for (state, allowed) in [
            (WindowsLoading, &[Back][..]),
            (WindowsEmpty, &[Apps, Back, Home][..]),
            (WindowStale, &[Apps, Back, Home][..]),
            (ActionDenied, &[Back, Retry][..]),
            (VideoStopped, &[Back, Apps, Home][..]),
            (VideoEnded, &[Back, Apps][..]),
            (VideoCancelled, &[Back][..]),
        ] {
            assert!(allowed.contains(&state.action()), "{}", state.id());
        }
    }

    #[test]
    fn a_surface_names_its_own_visible_exit_control() {
        assert_eq!(
            RecoveryState::ActionDenied.message(Some("Done")),
            "That action isn't allowed · Done"
        );
    }

    #[test]
    fn helper_codes_map_to_states_and_are_never_the_copy() {
        for code in ["action-denied", "brightness-denied", "denied"] {
            assert_eq!(action_error_state(code), RecoveryState::ActionDenied);
            assert!(!action_error_state(code).message(None).contains(code));
        }
        for code in ["target-unavailable", "stale-confirmation", "keyboard-unavailable", "x"] {
            assert_eq!(action_error_state(code), RecoveryState::ActionFailed);
        }
    }

    #[test]
    fn person_safe_rejects_paths_diagnostics_codes_and_secrets() {
        for raw in [
            "/run/shell/k230-video.log",
            "GLib-GIO-CRITICAL: g_app_info failed",
            "gdbus: org.freedesktop.DBus.Error.AccessDenied",
            "action-denied",
            "target-unavailable · try again",
            "psk=hunter2",
            "Traceback (most recent call last)",
            "line\nbreak",
        ] {
            assert!(!person_safe(raw), "{raw}");
        }
        assert!(person_safe("Restart device?"));
        assert!(person_safe("Working…"));
    }
}

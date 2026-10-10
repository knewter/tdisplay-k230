//! A deliberately opened Help/navigation aid; no app Back key is synthesized.
use std::{
    path::Path,
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Action {
    OpenAid,
    Home,
    Apps,
    Notifications,
    Settings,
    Back,
}

pub const GUIDE: &[(&str, &str)] = &[
    (
        "Home and running apps",
        "Swipe up from the bottom to leave an app.",
    ),
    ("All apps", "Swipe up on Home to open the app drawer."),
    (
        "Notifications and Settings",
        "Pull down from the top edge to open the shade.",
    ),
    (
        "Close a panel",
        "Close a panel with its handle or Done control.",
    ),
    ("Keyboard", "Use two fingers up at the bottom to show it."),
];

pub fn buttons(aid: bool) -> &'static [(Action, &'static str, &'static str)] {
    if aid {
        &[
            (Action::Home, "Home", "Show your pinned apps"),
            (Action::Apps, "All apps", "Open the app drawer"),
            (
                Action::Notifications,
                "Notifications",
                "Open the notification shade",
            ),
            (Action::Settings, "Settings", "Open device controls"),
            (Action::Back, "Return to Help", "Close navigation buttons"),
        ]
    } else {
        &[
            (
                Action::OpenAid,
                "Navigation buttons",
                "Open large labeled route controls",
            ),
            (Action::Back, "Return to All apps", "Close Help"),
        ]
    }
}

/// A centered column, sized to fit both panel and supported HDMI outputs.
/// Even the smallest accepted output keeps buttons at least 56px high.
pub fn transform(width: u32, height: u32) -> (f64, f64) {
    let scale = (f64::from(width) / 568.0)
        .min(f64::from(height) / 1100.0)
        .clamp(0.5, 2.0);
    (scale, (f64::from(width) - 568.0 * scale) / 2.0)
}

pub fn button_rect(aid: bool, index: usize) -> (f64, f64, f64, f64) {
    (
        24.0,
        if aid { 192.0 } else { 640.0 } + index as f64 * 128.0,
        520.0,
        112.0,
    )
}

fn contains(point: (f64, f64), rect: (f64, f64, f64, f64)) -> bool {
    let (x, y, w, h) = rect;
    point.0 >= x && point.0 < x + w && point.1 >= y && point.1 < y + h
}

pub fn hit(
    start: (f64, f64),
    end: (f64, f64),
    width: u32,
    height: u32,
    aid: bool,
) -> Option<Action> {
    if ![start.0, start.1, end.0, end.1]
        .iter()
        .all(|v| v.is_finite())
        || (end.0 - start.0).abs() > 12.0
        || (end.1 - start.1).abs() > 12.0
    {
        return None;
    }
    let (scale, x) = transform(width, height);
    let local = |p: (f64, f64)| ((p.0 - x) / scale, p.1 / scale);
    buttons(aid)
        .iter()
        .enumerate()
        .find_map(|(i, (action, _, _))| {
            let rect = button_rect(aid, i);
            (contains(local(start), rect) && contains(local(end), rect)).then_some(*action)
        })
}

/// Called only on a worker. A failed or stalled compositor leaves Help usable.
pub fn request_home(command: &Path) -> Result<(), String> {
    if !command.is_absolute() || !command.is_file() {
        return Err("Home unavailable".into());
    }
    let mut child = Command::new(command)
        .args(["card_shell", "home"])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "Home request failed".to_string())?;
    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        match child.try_wait() {
            Ok(Some(status)) if status.success() => return Ok(()),
            Ok(Some(_)) => return Err("Home request failed · try again".into()),
            Ok(None) if Instant::now() < deadline => thread::sleep(Duration::from_millis(10)),
            _ => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("Home request timed out · try again".into());
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::navigation;
    #[test]
    fn aid_is_deliberate_and_routes_share_painted_geometry() {
        for (w, h) in [(300, 600), (568, 1232), (1920, 1080), (1080, 1920)] {
            let (scale, offset) = transform(w, h);
            for aid in [false, true] {
                for (i, (action, _, _)) in buttons(aid).iter().enumerate() {
                    let (x, y, width, height) = button_rect(aid, i);
                    let center = (
                        offset + (x + width / 2.0) * scale,
                        (y + height / 2.0) * scale,
                    );
                    assert_eq!(hit(center, center, w, h, aid), Some(*action));
                    assert!(height * scale >= 56.0);
                    assert!((y + height) * scale <= f64::from(h));
                    assert!(
                        offset + x * scale >= 0.0 && offset + (x + width) * scale <= f64::from(w)
                    );
                }
            }
            // A direct route cannot be activated before opting into the aid.
            let hidden_home = (f64::from(w) / 2.0, 248.0 * scale);
            assert_eq!(hit(hidden_home, hidden_home, w, h, false), None);
            let (x, y, width, height) = navigation::help_rect(w, h);
            let help = (x + width / 2.0, y + height / 2.0);
            assert!(navigation::help_hit(help, w, h));
            assert!(!navigation::search_field_hit(help, w, h));
            assert_eq!(navigation::tile_at(help, w, h, 64, 0.0), None);
        }
    }
    #[test]
    fn drag_crossing_gap_or_nonfinite_touch_never_activates_a_route() {
        assert_eq!(hit((280.0, 240.0), (280.0, 380.0), 568, 1232, true), None);
        assert_eq!(hit((280.0, 303.0), (280.0, 305.0), 568, 1232, true), None);
        assert_eq!(
            hit((f64::NAN, 240.0), (280.0, 240.0), 568, 1232, true),
            None
        );
        assert_eq!(hit((280.0, 240.0), (280.0, 240.0), 568, 1232, false), None);
    }
    #[test]
    fn home_request_uses_the_compositor_and_reports_failure_and_timeout() {
        use std::os::unix::fs::PermissionsExt;
        let path = std::env::temp_dir().join(format!("k230-help-{}.sh", std::process::id()));
        for (body, expected) in [
            ("[ \"$1\" = card_shell ] && [ \"$2\" = home ]", None),
            ("exit 1", Some("failed")),
            ("exec sleep 5", Some("timed out")),
        ] {
            std::fs::write(&path, format!("#!/bin/sh\n{body}\n")).unwrap();
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700)).unwrap();
            let start = Instant::now();
            let result = request_home(&path);
            match expected {
                None => assert!(result.is_ok()),
                Some(s) => assert!(result.unwrap_err().contains(s)),
            }
            assert!(start.elapsed() < Duration::from_secs(3));
        }
        std::fs::remove_file(path).unwrap();
        assert!(request_home(Path::new("swaymsg")).is_err());
    }
}

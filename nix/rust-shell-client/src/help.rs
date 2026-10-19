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

/// Help's text and buttons on the shell's type roles at the current text
/// step, in design units that `scale` maps to output pixels (`x` is the
/// left offset). Text wraps rather than being shortened; content taller
/// than the output scrolls (`max_scroll`). `render.rs` paints and `hit`
/// tests from this one struct.
#[derive(Clone, Debug, PartialEq)]
pub struct HelpLayout {
    pub scale: f64,
    pub x: f64,
    /// Role sizes at the current step, in design units.
    pub title_px: f64,
    pub label_px: f64,
    pub caption_px: f64,
    pub heading_y: f64,
    pub intro: (f64, f64),
    /// Each guide entry's title and detail origins.
    pub guide: Vec<((f64, f64), (f64, f64))>,
    pub buttons: Vec<(f64, f64, f64, f64)>,
    /// Each button's label and detail y.
    pub button_text: Vec<(f64, f64)>,
    pub message: (f64, f64),
    /// The column text width, in design units.
    pub column_w: f64,
    pub content_h: f64,
}

/// One design column: 568 units wide with a 24-unit margin each side.
const COLUMN: f64 = 568.0;
const MARGIN: f64 = 24.0;
/// The wide layout's design height.
const WIDE_HEIGHT: f64 = 600.0;
const TEXT_W: f64 = COLUMN - 2.0 * MARGIN;
/// A button's text sits this far inside its card.
const BUTTON_PAD: f64 = 24.0;
pub const INTRO: &str = "These controls appear only while this view is open.";

/// The landscape panel (1232x568) would shrink the single column to about
/// half size. An output at least 1.6 times as wide as it is tall gets two
/// columns instead -- the guide on the left and the buttons on the right.
/// That includes landscape HDMI monitors (16:10 and 16:9, 1280x800 up to
/// 1920x1080). The portrait panel and a portrait HDMI monitor keep the
/// single column.
pub fn wide(width: u32, height: u32) -> bool {
    height > 0 && f64::from(width) >= 1.6 * f64::from(height)
}

fn line(px: f64) -> f64 {
    (px * 1.25).ceil()
}

/// Measured a little narrower than it is painted, so hinting at the
/// painted scale can only leave spare room, never overlap the next line.
fn wrapped_h(text: &str, px: f64, width: f64, weight: pango::Weight) -> f64 {
    f64::from(crate::render::wrapped_line_count(text, px, width - 4.0, weight)) * line(px)
}

pub fn layout(width: u32, height: u32, aid: bool) -> HelpLayout {
    let wide = wide(width, height);
    let columns = if wide { 2.0 } else { 1.0 };
    // Portrait fits the width only; a step that makes the content taller
    // scrolls. Wide also fits a 600-unit height, so the landscape panel
    // shows all of Help at 100%.
    let fit = f64::from(width) / (COLUMN * columns);
    let scale = if wide { fit.min(f64::from(height) / WIDE_HEIGHT) } else { fit }.clamp(0.5, 2.0);
    let x = (f64::from(width) - COLUMN * columns * scale) / 2.0;
    // The theme's own size times the vision step, as `context_font_size`.
    let step = crate::layout_text_scale().max(1.0) * crate::layout_theme_font();
    let title_px = crate::render::TYPE_TITLE * step;
    let label_px = crate::render::TYPE_LABEL * step;
    let caption_px = crate::render::TYPE_CAPTION * step;
    let heading_y = 32.0;
    let intro_y = heading_y + line(title_px) + 8.0;
    let mut left = intro_y + wrapped_h(INTRO, caption_px, TEXT_W, pango::Weight::Normal) + 24.0;
    // Wide: the buttons start beside the heading in the right column,
    // except that the aid's first buttons stay under its intro on the left.
    let mut right = heading_y;
    let mut rects = Vec::new();
    let mut button_text = Vec::new();
    let mut place_button = |index: usize, label: &str, detail: &str, left: &mut f64, right: &mut f64| {
        let on_left = !wide || (aid && index < WIDE_AID_LEFT);
        let column_x = if on_left { 0.0 } else { COLUMN };
        let top = if on_left { *left } else { *right };
        let inner = TEXT_W - 2.0 * BUTTON_PAD;
        let label_h = wrapped_h(label, label_px, inner, pango::Weight::Normal);
        let detail_h = wrapped_h(detail, caption_px, inner, pango::Weight::Normal);
        let h = (18.0 + label_h + 6.0 + detail_h + 18.0).max(112.0);
        rects.push((column_x + MARGIN, top, TEXT_W, h));
        button_text.push((top + 18.0, top + 18.0 + label_h + 6.0));
        if on_left { *left = top + h + 16.0 } else { *right = top + h + 16.0 }
    };
    if wide {
        // The right column's buttons go first, so the guide can continue
        // under them once the left column is full.
        for (index, (_, label, detail)) in buttons(aid).iter().enumerate() {
            place_button(index, label, detail, &mut left, &mut right);
        }
    }
    let mut guide = Vec::new();
    if !aid {
        let items: Vec<(f64, f64)> = GUIDE
            .iter()
            .map(|(title, detail)| {
                let title_h = wrapped_h(title, label_px, TEXT_W, pango::Weight::Medium);
                (title_h, title_h + 2.0 + wrapped_h(detail, caption_px, TEXT_W, pango::Weight::Normal))
            })
            .collect();
        let stack = |top: f64, items: &[(f64, f64)]| top + items.iter().map(|(_, h)| h + 20.0).sum::<f64>();
        // Wide: the entries stay in reading order, the first `split` on the
        // left and the rest under the buttons, split to keep the taller
        // column as short as possible (ties keep more on the left).
        let split = if wide {
            (1..=items.len())
                .rev()
                .min_by(|a, b| {
                    let tall = |k: usize| stack(left, &items[..k]).max(stack(right, &items[k..]));
                    tall(*a).total_cmp(&tall(*b))
                })
                .unwrap_or(items.len())
        } else {
            items.len()
        };
        for (index, (title_h, item_h)) in items.into_iter().enumerate() {
            let (column_x, top) = if index < split { (0.0, &mut left) } else { (COLUMN, &mut right) };
            guide.push(((column_x + MARGIN, *top), (column_x + MARGIN, *top + title_h + 2.0)));
            *top += item_h + 20.0;
        }
    }
    if !wide {
        for (index, (_, label, detail)) in buttons(aid).iter().enumerate() {
            place_button(index, label, detail, &mut left, &mut right);
        }
    }
    let message = if wide { (COLUMN + MARGIN, right + 8.0) } else { (MARGIN, left + 8.0) };
    // Room for a one-line message under the last column.
    let content_h = left.max(right) + 8.0 + line(caption_px) + 16.0;
    HelpLayout {
        scale,
        x,
        title_px,
        label_px,
        caption_px,
        heading_y,
        intro: (MARGIN, intro_y),
        guide,
        buttons: rects,
        button_text,
        message,
        column_w: TEXT_W,
        content_h,
    }
}

/// Buttons that fit in the wide layout's left column under the aid's
/// heading; the rest continue at the top of the right column.
const WIDE_AID_LEFT: usize = 2;

impl HelpLayout {
    /// How far Help can scroll, in output pixels.
    pub fn max_scroll(&self, height: u32) -> f64 {
        (self.content_h * self.scale - f64::from(height)).max(0.0)
    }
}

fn contains(point: (f64, f64), rect: (f64, f64, f64, f64)) -> bool {
    let (x, y, w, h) = rect;
    point.0 >= x && point.0 < x + w && point.1 >= y && point.1 < y + h
}

/// The button a stationary tap lands on, with Help scrolled by `scroll`
/// output pixels.
pub fn hit(
    start: (f64, f64),
    end: (f64, f64),
    width: u32,
    height: u32,
    aid: bool,
    scroll: f64,
) -> Option<Action> {
    if ![start.0, start.1, end.0, end.1]
        .iter()
        .all(|v| v.is_finite())
        || (end.0 - start.0).abs() > 12.0
        || (end.1 - start.1).abs() > 12.0
    {
        return None;
    }
    let lay = layout(width, height, aid);
    let local = |p: (f64, f64)| ((p.0 - lay.x) / lay.scale, (p.1 + scroll) / lay.scale);
    buttons(aid)
        .iter()
        .zip(&lay.buttons)
        .find_map(|((action, _, _), rect)| {
            (contains(local(start), *rect) && contains(local(end), *rect)).then_some(*action)
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
        // Landscape HDMI monitors take the wide layout too; a 5:4 one does not.
        assert!(wide(1232, 568) && wide(1920, 1080) && wide(1280, 800) && wide(1280, 720));
        assert!(!wide(568, 1232) && !wide(1080, 1920) && !wide(1280, 1024));
        for step in [1.0, 1.5, 2.0] {
            crate::set_layout_text_scale(step);
            for (w, h) in [(300, 600), (568, 1232), (1920, 1080), (1080, 1920), (1232, 568), (1280, 800), (1280, 1024)] {
                for aid in [false, true] {
                    let lay = layout(w, h, aid);
                    let max = lay.max_scroll(h);
                    if wide(w, h) {
                        assert!(lay.scale >= 0.9, "the landscape Help stays near full size: {}", lay.scale);
                    }
                    for ((action, _, _), &(x, y, width, height)) in buttons(aid).iter().zip(&lay.buttons) {
                        assert!(height * lay.scale >= 56.0);
                        assert!(lay.x + x * lay.scale >= 0.0 && lay.x + (x + width) * lay.scale <= f64::from(w));
                        assert!((y + height) * lay.scale <= f64::from(h) + max, "a button is reachable by scrolling");
                        // Scrolled to bring the button on screen, its centre taps it.
                        let scroll = ((y + height) * lay.scale - f64::from(h)).clamp(0.0, max);
                        let center = (
                            lay.x + (x + width / 2.0) * lay.scale,
                            (y + height / 2.0) * lay.scale - scroll,
                        );
                        assert_eq!(hit(center, center, w, h, aid, scroll), Some(*action));
                    }
                }
                // A direct route cannot be activated before opting into the aid.
                let lay = layout(w, h, true);
                let home = lay.buttons[buttons(true).iter().position(|b| b.0 == Action::Home).unwrap()];
                let hidden_home = (lay.x + (home.0 + home.2 / 2.0) * lay.scale, (home.1 + home.3 / 2.0) * lay.scale);
                assert_ne!(hit(hidden_home, hidden_home, w, h, false, 0.0), Some(Action::Home));
                let (x, y, width, height) = navigation::help_rect(w, h);
                let help = (x + width / 2.0, y + height / 2.0);
                assert!(navigation::help_hit(help, w, h));
                assert!(!navigation::search_field_hit(help, w, h));
                assert_eq!(navigation::tile_at(help, w, h, 64, 0.0), None);
            }
        }
        // At 100% the panel needs no scrolling in either orientation.
        crate::set_layout_text_scale(1.0);
        for (w, h) in [(568, 1232), (1232, 568)] {
            for aid in [false, true] {
                assert_eq!(layout(w, h, aid).max_scroll(h), 0.0, "{w}x{h} aid={aid}");
            }
        }
    }
    #[test]
    fn drag_crossing_gap_or_nonfinite_touch_never_activates_a_route() {
        let lay = layout(568, 1232, true);
        let (x, y, w, h) = lay.buttons[0];
        let (_, next_y, _, _) = lay.buttons[1];
        let cx = lay.x + (x + w / 2.0) * lay.scale;
        let center = (y + h / 2.0) * lay.scale;
        let gap = (y + h + next_y) / 2.0 * lay.scale;
        assert_eq!(hit((cx, center), (cx, next_y * lay.scale + 20.0), 568, 1232, true, 0.0), None);
        assert_eq!(hit((cx, gap - 1.0), (cx, gap + 1.0), 568, 1232, true, 0.0), None);
        assert_eq!(hit((f64::NAN, center), (cx, center), 568, 1232, true, 0.0), None);
        assert_eq!(hit((cx, center), (cx, center), 568, 1232, true, 0.0), Some(Action::Home));
        // The same point, scrolled, lands somewhere else.
        assert_ne!(hit((cx, center), (cx, center), 568, 1232, true, h * lay.scale), Some(Action::Home));
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

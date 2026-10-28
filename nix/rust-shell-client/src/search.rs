//! The drawer's search: installed apps, their desktop-entry actions and the
//! Settings destinations, ranked into one list.
//!
//! The only inputs are the catalog (`AppEntry`, whose action names the scan
//! already read), a static destination table and two hardware flags. Nothing
//! here reads notifications, window titles, the filesystem or the network, so
//! no result can carry them, and nothing here logs the query. Painting,
//! hit-testing and Enter all read the one vector `search` returns, so the
//! outlined first row is Enter's target by construction.
use crate::{
    app_actions::AppAction, catalog::AppEntry, glyph::Glyph, service_ui::PanelIntent,
    theme_ui::ThemeIntent,
};

/// Which hardware-gated Settings rows exist right now: the same two facts the
/// Settings screen draws its rows from (`ServiceView::modem`, `key_backlight`).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Hardware {
    pub modem: bool,
    pub key_backlight: bool,
}

/// A Settings page or inline row the search can open.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SettingsDest {
    Wifi,
    Cellular,
    Location,
    DateTime,
    About,
    Themes,
    Vision,
    DoNotDisturb,
    Brightness,
    Volume,
    Keyboard,
    ReduceMotion,
    KeyBacklight,
}

/// A row of the Settings screen to scroll into view, by the index the screen
/// itself lays rows out with.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SettingsRow {
    /// A capability row (`render::settings_row_y`).
    Capability(u32),
    /// A plain label-and-value row after them (`render::settings_info_row_index`):
    /// 0 is Do Not Disturb.
    Info(u32),
}

/// Where choosing a destination goes: an existing Settings page through the
/// intent a tap would send, or Settings itself scrolled to an inline row.
/// Never a switch flip or a value change.
#[derive(Clone, Debug, PartialEq)]
pub enum SettingsRoute {
    Panel(PanelIntent),
    Theme(ThemeIntent),
    Inline(SettingsRow),
}

impl SettingsDest {
    pub fn route(self) -> SettingsRoute {
        match self {
            Self::Wifi => SettingsRoute::Panel(PanelIntent::OpenWifi),
            Self::Cellular => SettingsRoute::Panel(PanelIntent::OpenCellular),
            Self::Location => SettingsRoute::Panel(PanelIntent::OpenLocation),
            Self::DateTime => SettingsRoute::Panel(PanelIntent::OpenDateTime),
            Self::About => SettingsRoute::Panel(PanelIntent::OpenAbout),
            Self::Themes => SettingsRoute::Theme(ThemeIntent::Open),
            Self::Vision => SettingsRoute::Theme(ThemeIntent::OpenVision),
            Self::DoNotDisturb => SettingsRoute::Inline(SettingsRow::Info(0)),
            Self::Brightness => SettingsRoute::Inline(SettingsRow::Capability(1)),
            Self::Volume => SettingsRoute::Inline(SettingsRow::Capability(
                crate::service_ui::SETTINGS_VOLUME_ROW,
            )),
            Self::Keyboard => SettingsRoute::Inline(SettingsRow::Capability(3)),
            Self::ReduceMotion => SettingsRoute::Inline(SettingsRow::Capability(4)),
            Self::KeyBacklight => SettingsRoute::Inline(SettingsRow::Capability(
                crate::render::SETTINGS_KEY_BACKLIGHT_ROW,
            )),
        }
    }

    fn glyph(self) -> Option<Glyph> {
        match self {
            Self::Wifi => Some(Glyph::Wifi),
            Self::Cellular => Some(Glyph::Signal),
            Self::Location => Some(Glyph::Location),
            Self::DateTime => Some(Glyph::Clock),
            Self::About => Some(Glyph::Info),
            Self::DoNotDisturb => Some(Glyph::Moon),
            Self::Brightness => Some(Glyph::Sun),
            Self::Volume => Some(Glyph::Speaker),
            Self::Keyboard => Some(Glyph::Keyboard),
            Self::ReduceMotion => Some(Glyph::Motion),
            Self::KeyBacklight => Some(Glyph::KeyBacklight),
            Self::Themes | Self::Vision => None,
        }
    }
}

/// Label, extra words people type for it, and whether the hardware it needs
/// is there. Extend the keywords here; the tests pin the ones that matter.
const SETTINGS: &[(SettingsDest, &str, &[&str])] = &[
    (SettingsDest::Wifi, "Wi-Fi", &["wifi", "wireless", "network", "internet"]),
    (SettingsDest::Cellular, "Cellular", &["mobile", "modem", "sim", "lte", "data"]),
    (SettingsDest::Location, "Location", &["gps", "gnss", "position"]),
    (SettingsDest::DateTime, "Date & time", &["date", "time", "clock", "time zone"]),
    (SettingsDest::About, "About", &["version", "build", "device", "info"]),
    (SettingsDest::Themes, "Themes", &["theme", "wallpaper", "background", "appearance"]),
    (SettingsDest::Vision, "Vision", &["text size", "large text", "contrast", "accessibility"]),
    (SettingsDest::DoNotDisturb, "Do Not Disturb", &["dnd", "quiet", "silent"]),
    (SettingsDest::Brightness, "Brightness", &["screen", "dim", "display"]),
    (SettingsDest::Volume, "Volume", &["sound", "audio", "speaker", "mute"]),
    (SettingsDest::Keyboard, "Keyboard", &["osk", "on-screen keyboard", "typing"]),
    (SettingsDest::ReduceMotion, "Reduce motion", &["motion", "animation", "animations"]),
    (SettingsDest::KeyBacklight, "Key backlight", &["keys", "led", "light"]),
];

fn present(dest: SettingsDest, hardware: Hardware) -> bool {
    match dest {
        SettingsDest::Cellular | SettingsDest::Location => hardware.modem,
        SettingsDest::KeyBacklight => hardware.key_backlight,
        _ => true,
    }
}

/// Kinds in tie-break order: Apps, then App actions, then Settings.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum ResultKind {
    App,
    Action,
    Settings,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Target {
    /// A catalog index, as `launch_app` takes it.
    App(usize),
    /// A catalog index and the desktop action's id.
    Action(usize, String),
    Settings(SettingsDest),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SearchResult {
    pub kind: ResultKind,
    pub label: String,
    /// The second line: what kind of thing this is.
    pub detail: String,
    /// The app's themed icon name, for App and Action rows.
    pub icon: Option<String>,
    /// The shell's own glyph, for Settings rows that have one.
    pub glyph: Option<Glyph>,
    pub target: Target,
}

/// What choosing a result does, decided without touching the compositor so
/// it can be tested.
#[derive(Clone, Debug, PartialEq)]
pub enum Activation {
    Launch(usize),
    AppAction(usize, AppAction),
    Settings(SettingsDest),
}

impl SearchResult {
    pub fn activation(&self) -> Activation {
        match &self.target {
            Target::App(index) => Activation::Launch(*index),
            Target::Action(index, id) => Activation::AppAction(*index, action_for(id)),
            Target::Settings(dest) => Activation::Settings(*dest),
        }
    }
}

/// The app menu lists a declared new-window action as `NewWindow(Some(id))`
/// and every other one as `Desktop(id)`; `run_app_action` only accepts the
/// forms `app_actions::rows` produced.
pub fn action_for(id: &str) -> AppAction {
    if matches!(id, "new-window" | "NewWindow") {
        AppAction::NewWindow(Some(id.to_string()))
    } else {
        AppAction::Desktop(id.to_string())
    }
}

/// Rank of `needle` in `haystack` (both already lower case): 0 prefix, 1 a
/// later word's prefix, 2 substring; `None` for no match.
fn text_rank(haystack: &str, needle: &str) -> Option<u8> {
    if haystack.starts_with(needle) {
        return Some(0);
    }
    let mut previous_alnum = false;
    for (offset, character) in haystack.char_indices() {
        if !previous_alnum && offset > 0 && haystack[offset..].starts_with(needle) {
            return Some(1);
        }
        previous_alnum = character.is_alphanumeric();
    }
    haystack.contains(needle).then_some(2)
}

/// The ranked results for `query`: empty for an empty query (the drawer shows
/// its grid then). Lower rank first (prefix, word start, substring, keyword),
/// then Apps before App actions before Settings, then catalog order. A linear
/// pass over at most about 150 short strings, redone per keystroke.
pub fn search(apps: &[AppEntry], query: &str, hardware: Hardware) -> Vec<SearchResult> {
    let needle = query.trim().to_lowercase();
    if needle.is_empty() {
        return Vec::new();
    }
    // (rank, kind, order, result)
    let mut found: Vec<(u8, ResultKind, usize, SearchResult)> = Vec::new();
    let mut order = 0usize;
    for (index, app) in apps.iter().enumerate() {
        if let Some(rank) = text_rank(&app.name.to_lowercase(), &needle) {
            found.push((rank, ResultKind::App, order, SearchResult {
                kind: ResultKind::App,
                label: app.name.clone(),
                detail: "App".into(),
                icon: app.icon.clone(),
                glyph: None,
                target: Target::App(index),
            }));
        }
        order += 1;
        for (id, name) in &app.actions {
            let label = format!("{name} - {}", app.name);
            if let Some(rank) = text_rank(&label.to_lowercase(), &needle) {
                found.push((rank, ResultKind::Action, order, SearchResult {
                    kind: ResultKind::Action,
                    label,
                    detail: "App action".into(),
                    icon: app.icon.clone(),
                    glyph: None,
                    target: Target::Action(index, id.clone()),
                }));
            }
            order += 1;
        }
    }
    for (dest, label, keywords) in SETTINGS {
        if !present(*dest, hardware) {
            continue;
        }
        let rank = text_rank(&label.to_lowercase(), &needle).or_else(|| {
            keywords.iter().any(|word| word.starts_with(&needle)).then_some(3)
        });
        if let Some(rank) = rank {
            found.push((rank, ResultKind::Settings, order, SearchResult {
                kind: ResultKind::Settings,
                label: (*label).into(),
                detail: "Settings".into(),
                icon: None,
                glyph: dest.glyph(),
                target: Target::Settings(*dest),
            }));
        }
        order += 1;
    }
    found.sort_by_key(|(rank, kind, order, _)| (*rank, *kind, *order));
    found.into_iter().map(|(.., result)| result).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn app(id: &str, name: &str, actions: &[(&str, &str)]) -> AppEntry {
        AppEntry {
            actions: actions.iter().map(|(i, n)| (i.to_string(), n.to_string())).collect(),
            id: id.into(),
            name: name.into(),
            icon: None,
            path: PathBuf::new(),
        }
    }

    fn labels(results: &[SearchResult]) -> Vec<&str> {
        results.iter().map(|result| result.label.as_str()).collect()
    }

    const BOTH: Hardware = Hardware { modem: true, key_backlight: true };

    #[test]
    fn prefix_beats_word_start_beats_substring() {
        let apps = [
            app("a", "Photo Timer", &[]),
            app("b", "Overtime", &[]),
            app("c", "Timer", &[]),
        ];
        let results = search(&apps, "tim", Hardware::default());
        // Rank 0 Timer; rank 1 Photo Timer, then the Settings page whose
        // word "time" also starts with it (Apps before Settings on a tie);
        // rank 2 Overtime.
        assert_eq!(
            labels(&results),
            ["Timer", "Photo Timer", "Date & time", "Overtime"],
            "prefix, then a later word's start, then a substring"
        );
    }

    #[test]
    fn query_case_is_ignored() {
        let apps = [app("a", "Terminal", &[])];
        assert_eq!(labels(&search(&apps, "TERM", Hardware::default())), ["Terminal"]);
    }

    #[test]
    fn ties_keep_apps_then_actions_then_settings() {
        // All four start with "ab": an app, its action and the About page
        // tie on rank 0, so kind decides, then catalog order.
        let apps = [
            app("a", "About Me", &[]),
            app("b", "Zed", &[("ab", "About Zed")]),
            app("c", "Aboard", &[]),
        ];
        let results = search(&apps, "abo", Hardware::default());
        assert_eq!(
            labels(&results),
            ["About Me", "Aboard", "About Zed - Zed", "About"]
        );
        let kinds: Vec<_> = results.iter().map(|result| result.kind).collect();
        assert_eq!(
            kinds,
            [ResultKind::App, ResultKind::App, ResultKind::Action, ResultKind::Settings]
        );
    }

    #[test]
    fn wifi_and_wi_fi_both_find_wifi() {
        for query in ["wifi", "wi-fi", "Wi-F", "wireless"] {
            let results = search(&[], query, Hardware::default());
            assert_eq!(labels(&results), ["Wi-Fi"], "query {query:?}");
            assert_eq!(results[0].target, Target::Settings(SettingsDest::Wifi));
        }
    }

    #[test]
    fn hardware_gated_destinations_need_their_hardware() {
        let none = Hardware::default();
        for (query, label) in [("cell", "Cellular"), ("location", "Location"), ("key back", "Key backlight")] {
            assert!(search(&[], query, none).is_empty(), "{label} must be absent without its hardware");
            assert_eq!(labels(&search(&[], query, BOTH)), [label]);
        }
        // Each gate is its own: a modem does not bring the base's LED.
        assert!(search(&[], "key back", Hardware { modem: true, key_backlight: false }).is_empty());
        assert!(search(&[], "location", Hardware { modem: false, key_backlight: true }).is_empty());
        // Keywords respect the gate too.
        assert!(search(&[], "gps", none).is_empty());
        assert_eq!(labels(&search(&[], "gps", BOTH)), ["Location"]);
    }

    #[test]
    fn an_empty_or_blank_query_yields_no_list() {
        let apps = [app("a", "Terminal", &[])];
        assert!(search(&apps, "", BOTH).is_empty());
        assert!(search(&apps, "   ", BOTH).is_empty());
    }

    #[test]
    fn every_settings_destination_is_findable_by_its_label() {
        for (dest, label, _) in SETTINGS {
            let results = search(&[], label, BOTH);
            assert_eq!(results.first().map(|r| &r.target), Some(&Target::Settings(*dest)), "{label}");
        }
        assert_eq!(SETTINGS.len(), 13);
    }

    #[test]
    fn app_actions_read_action_dash_app_and_activate_through_the_menus_forms() {
        let apps = [app("t", "Terminal", &[("new-window", "New Window"), ("prefs", "Preferences")])];
        let results = search(&apps, "pref", Hardware::default());
        assert_eq!(labels(&results), ["Preferences - Terminal"]);
        assert_eq!(
            results[0].activation(),
            Activation::AppAction(0, AppAction::Desktop("prefs".into()))
        );
        let results = search(&apps, "new window", Hardware::default());
        assert_eq!(
            results[0].activation(),
            Activation::AppAction(0, AppAction::NewWindow(Some("new-window".into())))
        );
    }

    #[test]
    fn matching_an_app_name_does_not_list_every_action_ahead_of_it() {
        let apps = [app("t", "Terminal", &[("prefs", "Preferences")])];
        let results = search(&apps, "term", Hardware::default());
        assert_eq!(results[0].target, Target::App(0));
    }

    #[test]
    fn drawer_search_activation_maps_each_target() {
        let apps = [app("t", "Terminal", &[("prefs", "Preferences")])];
        assert_eq!(search(&apps, "terminal", Hardware::default())[0].activation(), Activation::Launch(0));
        assert_eq!(
            search(&[], "about", Hardware::default())[0].activation(),
            Activation::Settings(SettingsDest::About)
        );
    }

    #[test]
    fn drawer_search_activation_routes_only_to_navigation() {
        use SettingsRoute::*;
        assert_eq!(SettingsDest::Wifi.route(), Panel(PanelIntent::OpenWifi));
        assert_eq!(SettingsDest::Cellular.route(), Panel(PanelIntent::OpenCellular));
        assert_eq!(SettingsDest::Location.route(), Panel(PanelIntent::OpenLocation));
        assert_eq!(SettingsDest::DateTime.route(), Panel(PanelIntent::OpenDateTime));
        assert_eq!(SettingsDest::About.route(), Panel(PanelIntent::OpenAbout));
        assert_eq!(SettingsDest::Themes.route(), Theme(ThemeIntent::Open));
        assert_eq!(SettingsDest::Vision.route(), Theme(ThemeIntent::OpenVision));
        // The inline controls open Settings on their row; none maps to a
        // toggle or a request, so choosing one cannot change a setting.
        for (dest, row) in [
            (SettingsDest::DoNotDisturb, SettingsRow::Info(0)),
            (SettingsDest::Brightness, SettingsRow::Capability(1)),
            (SettingsDest::Volume, SettingsRow::Capability(2)),
            (SettingsDest::Keyboard, SettingsRow::Capability(3)),
            (SettingsDest::ReduceMotion, SettingsRow::Capability(4)),
            (SettingsDest::KeyBacklight, SettingsRow::Capability(5)),
        ] {
            assert_eq!(dest.route(), Inline(row));
        }
        for (dest, _, _) in SETTINGS {
            assert!(
                !matches!(
                    dest.route(),
                    Panel(PanelIntent::ToggleDoNotDisturb | PanelIntent::ToggleLocation
                        | PanelIntent::ToggleChargerIdle | PanelIntent::Request(_))
                ),
                "{dest:?} must only navigate"
            );
        }
    }
}

/// The privacy rules, as checks a refactor cannot quietly drop: the result
/// sources are the catalog and the static table only, and the query is never
/// logged.
#[cfg(test)]
mod privacy {
    use super::*;

    #[test]
    fn text_that_only_a_notification_window_or_file_holds_finds_nothing() {
        // `search` takes only the catalog, the query and two flags; there is
        // no argument through which a notification body, a window title or a
        // file name could arrive. Text that exists only in those places
        // therefore finds nothing, whatever it is.
        let apps = [AppEntry {
            actions: vec![("prefs".into(), "Preferences".into())],
            id: "t.desktop".into(),
            name: "Terminal".into(),
            icon: None,
            path: std::path::PathBuf::from("/home/someone/secret-file-name.desktop"),
        }];
        let hardware = Hardware { modem: true, key_backlight: true };
        for private in ["meet me at noon", "bank statement.pdf", "vim /etc/passwd", "someone", "secret-file"] {
            assert!(search(&apps, private, hardware).is_empty(), "{private:?}");
        }
        // The desktop file's path is never part of a result.
        for result in search(&apps, "t", hardware) {
            assert!(!result.label.contains("someone") && !result.detail.contains("someone"));
        }
    }

    #[test]
    fn the_search_module_reads_no_files_notifications_or_windows() {
        let source = include_str!("search.rs");
        let code: String = source
            .split("#[cfg(test)]")
            .next()
            .unwrap()
            .lines()
            .filter(|line| !line.trim_start().starts_with("//"))
            .collect::<Vec<_>>()
            .join("\n");
        for forbidden in [
            "std::fs", "File::", "read_dir", "gio::", "DesktopAppInfo", "Command", "sway_ipc",
            "notification", "app_tree", "println!", "eprintln!", "log(",
        ] {
            assert!(!code.contains(forbidden), "search.rs must not use {forbidden}");
        }
    }

    #[test]
    fn the_query_is_not_written_to_the_shell_log() {
        // Every log call in the client formats its own message; none may
        // mention the drawer's query or the search results.
        for (name, source) in [
            ("main.rs", include_str!("main.rs")),
            ("service_ui.rs", include_str!("service_ui.rs")),
        ] {
            for (number, line) in source.lines().enumerate() {
                if line.contains("log(") || line.contains("println!") || line.contains("eprintln!") {
                    assert!(
                        !line.contains("query") && !line.contains("drawer_search") && !line.contains("search_results"),
                        "{name}:{} logs the search: {line}",
                        number + 1
                    );
                }
            }
        }
    }
}

//! Desktop-entry app actions shared by Home, dock and All apps.
//! Touch hold remains the existing icon grab. Only secondary click opens this UI.
use crate::{catalog::AppEntry, home_screen::app_id_matches};
use gio::prelude::*;
use serde_json::Value;
use std::path::Path;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum AppAction {
    Activate,
    NewWindow(Option<String>),
    Desktop(String),
    Window(i64),
    Pin,
    Unpin,
    Arrange,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ActionRow {
    pub label: String,
    pub action: AppAction,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AppWindow {
    pub id: i64,
    pub title: String,
}

/// Sway's focus arrays rank immediate children most-recent first. Follow them
/// at every level; raw tree storage order is not window activation history.
pub fn windows(tree: &Value, entry: &str, hint: Option<&str>) -> Vec<AppWindow> {
    let mut result = Vec::new();
    let mut pending = vec![tree];
    let mut budget = 4096;
    while let Some(node) = pending.pop() {
        if budget == 0 {
            break;
        }
        budget -= 1;
        let Some(object) = node.as_object() else {
            continue;
        };
        let identity = object
            .get("app_id")
            .and_then(Value::as_str)
            .or_else(|| object.get("window_properties")?.get("class")?.as_str());
        if matches!(
            object.get("type").and_then(Value::as_str),
            Some("con" | "floating_con")
        ) && identity.is_some_and(|id| app_id_matches(id, entry, hint))
        {
            if let Some(id) = object
                .get("id")
                .and_then(Value::as_i64)
                .filter(|id| *id > 0)
            {
                let private = object
                    .get("marks")
                    .and_then(Value::as_array)
                    .is_some_and(|marks| {
                        marks
                            .iter()
                            .any(|m| m.as_str() == Some("k230_card_private"))
                    });
                let title = if private {
                    "Private window".into()
                } else {
                    object
                        .get("name")
                        .and_then(Value::as_str)
                        .unwrap_or("Window")
                        .chars()
                        .filter(|c| !c.is_control())
                        .take(96)
                        .collect()
                };
                result.push(AppWindow { id, title });
            }
        }
        let mut children: Vec<&Value> = ["nodes", "floating_nodes"]
            .into_iter()
            .flat_map(|key| {
                object
                    .get(key)
                    .and_then(Value::as_array)
                    .into_iter()
                    .flatten()
            })
            .collect();
        let order = object.get("focus").and_then(Value::as_array);
        children.sort_by_key(|child| {
            let id = child.get("id").and_then(Value::as_i64);
            order
                .and_then(|ids| ids.iter().position(|v| v.as_i64() == id))
                .unwrap_or(usize::MAX)
        });
        pending.extend(children.into_iter().rev());
    }
    result
}

/// Share the same desktop identity fallbacks for primary activation, window
/// menus and stale-window validation. All callers run off the dispatch thread.
pub fn entry_windows(tree: &Value, entry: &str, path: Option<&Path>) -> Vec<AppWindow> {
    let info = path.and_then(gio::DesktopAppInfo::from_filename);
    let startup = info.as_ref().and_then(|app| app.startup_wm_class());
    let matched = windows(tree, entry, startup.as_deref());
    if !matched.is_empty() {
        return matched;
    }
    let executable = info.and_then(|app| {
        app.executable()
            .file_name()
            .map(|name| name.to_string_lossy().into_owned())
    });
    windows(tree, entry, executable.as_deref())
}

pub fn rows(entry: &AppEntry, running: &[AppWindow], pinned: bool) -> Vec<ActionRow> {
    let Some(info) = gio::DesktopAppInfo::from_filename(&entry.path)
        .filter(|info| info.should_show() && !info.is_hidden())
    else {
        return vec![];
    };
    let actions: Vec<String> = info
        .list_actions()
        .iter()
        .map(ToString::to_string)
        .collect();
    let single = info.boolean("X-GNOME-SingleWindow") || info.boolean("SingleMainWindow");
    let declared_new = actions
        .iter()
        .find(|id| matches!(id.as_str(), "new-window" | "NewWindow"));
    let mut result = vec![ActionRow {
        label: "Open".into(),
        action: AppAction::Activate,
    }];
    if !single {
        if let Some(id) = declared_new {
            result.push(ActionRow {
                label: info.action_name(id).to_string(),
                action: AppAction::NewWindow(Some(id.clone())),
            });
        } else if !info.boolean("DBusActivatable") {
            result.push(ActionRow {
                label: "New Window".into(),
                action: AppAction::NewWindow(None),
            });
        }
    }
    result.extend(running.iter().map(|window| ActionRow {
        label: window.title.clone(),
        action: AppAction::Window(window.id),
    }));
    result.extend(
        actions
            .iter()
            .filter(|id| !matches!(id.as_str(), "new-window" | "NewWindow"))
            .map(|id| ActionRow {
                label: info
                    .action_name(id)
                    .chars()
                    .filter(|c| !c.is_control())
                    .take(96)
                    .collect(),
                action: AppAction::Desktop(id.clone()),
            }),
    );
    result.push(ActionRow {
        label: if pinned {
            "Remove from Home"
        } else {
            "Add to Home"
        }
        .into(),
        action: if pinned {
            AppAction::Unpin
        } else {
            AppAction::Pin
        },
    });
    if pinned {
        result.push(ActionRow {
            label: "Rearrange icons".into(),
            action: AppAction::Arrange,
        });
    }
    result.truncate(128);
    result
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum MenuOutcome {
    Action(AppAction),
    Dismiss,
    Consumed,
}

#[derive(Clone, Debug)]
pub struct AppMenu {
    pub entry: AppEntry,
    pub rows: Vec<ActionRow>,
    pub from_home: bool,
    pub serial: u64,
    pub scroll: f64,
    pub ready: bool,
    contact: Option<(i32, (f64, f64), f64)>,
}
impl AppMenu {
    pub fn new(entry: AppEntry, from_home: bool, serial: u64) -> Self {
        Self {
            entry,
            from_home,
            serial,
            rows: vec![],
            scroll: 0.0,
            ready: false,
            contact: None,
        }
    }
    pub fn geometry(&self, width: u32, height: u32) -> (f64, f64, f64, f64, f64) {
        let scale = crate::density_scale(width, height);
        let w = (440.0 * scale).min(f64::from(width) - 32.0);
        let row = 56.0 * scale;
        let h = (90.0 * scale + self.rows.len().max(1) as f64 * row).min(f64::from(height) - 64.0);
        (
            (f64::from(width) - w) / 2.0,
            (f64::from(height) - h) / 2.0,
            w,
            h,
            row,
        )
    }
    pub fn scroll_by(&mut self, delta: f64, width: u32, height: u32) {
        let (_, _, _, h, row) = self.geometry(width, height);
        let scale = crate::density_scale(width, height);
        self.scroll = (self.scroll + delta).clamp(
            0.0,
            (self.rows.len() as f64 * row - (h - 90.0 * scale)).max(0.0),
        );
    }
    pub fn down(&mut self, id: i32, point: (f64, f64)) {
        self.contact = Some((id, point, self.scroll));
    }
    pub fn motion(&mut self, id: i32, point: (f64, f64), width: u32, height: u32) {
        if let Some((owner, start, origin)) = self.contact {
            if id == owner {
                self.scroll = origin;
                self.scroll_by(start.1 - point.1, width, height);
            }
        }
    }
    /// Outside/header clicks dismiss; a dragged or cancelled stream never acts.
    pub fn up(&mut self, id: i32, point: (f64, f64), width: u32, height: u32) -> MenuOutcome {
        let Some((owner, start, _)) = self.contact.take() else {
            return MenuOutcome::Consumed;
        };
        if owner != id || (point.0 - start.0).hypot(point.1 - start.1) > 12.0 {
            return MenuOutcome::Consumed;
        }
        let (x, y, w, h, row) = self.geometry(width, height);
        let top = y + 78.0 * crate::density_scale(width, height);
        if point.0 < x || point.0 >= x + w || point.1 < top || point.1 >= y + h - 12.0 {
            return MenuOutcome::Dismiss;
        }
        self.rows
            .get(((point.1 - top + self.scroll) / row).floor() as usize)
            .map_or(MenuOutcome::Consumed, |r| {
                MenuOutcome::Action(r.action.clone())
            })
    }
    pub fn cancel(&mut self) {
        self.contact = None;
    }
    pub fn dragging(&self) -> bool {
        self.contact.is_some()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    #[test]
    fn window_selection_uses_focus_history_and_never_matches_unknown_apps() {
        let tree = json!({"focus":[3,1,2],"nodes":[
            {"type":"con","id":1,"app_id":"foot","name":"old"},
            {"type":"con","id":2,"app_id":"files","name":"unrelated"},
            {"type":"con","id":3,"app_id":"foot","name":"recent"}]});
        assert_eq!(
            windows(&tree, "terminal.desktop", Some("foot"))
                .iter()
                .map(|w| w.id)
                .collect::<Vec<_>>(),
            [3, 1]
        );
        assert!(windows(&tree, "unknown.desktop", None).is_empty());
    }
    #[test]
    fn private_windows_have_no_title_disclosure() {
        let tree = json!({"type":"con","id":1,"app_id":"foot","name":"private document","marks":["k230_card_private"]});
        assert_eq!(
            windows(&tree, "foot.desktop", None)[0].title,
            "Private window"
        );
    }
    #[test]
    fn menu_cancel_and_drag_do_not_activate_rows() {
        let mut menu = AppMenu::new(
            AppEntry {
                id: "a".into(),
                name: "App".into(),
                icon: None,
                path: "/missing".into(),
            },
            true,
            1,
        );
        menu.rows = vec![ActionRow {
            label: "Open".into(),
            action: AppAction::Activate,
        }];
        let (x, y, _, _, _) = menu.geometry(568, 1232);
        let point = (x + 30.0, y + 100.0);
        menu.down(1, point);
        menu.cancel();
        assert_eq!(menu.up(1, point, 568, 1232), MenuOutcome::Consumed);
        menu.down(1, point);
        assert_eq!(
            menu.up(1, (point.0, point.1 + 30.0), 568, 1232),
            MenuOutcome::Consumed
        );
        menu.down(1, point);
        assert_eq!(
            menu.up(1, point, 568, 1232),
            MenuOutcome::Action(AppAction::Activate)
        );
    }
    #[test]
    fn desktop_actions_single_window_metadata_and_missing_entries_control_the_menu() {
        let root = std::env::temp_dir().join(format!("k230-menu-policy-{}", std::process::id()));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("app.desktop");
        let source="[Desktop Entry]\nType=Application\nName=Fixture\nExec=/bin/true\nActions=new-window;preferences;\n[Desktop Action new-window]\nName=New Window\nExec=/bin/true\n[Desktop Action preferences]\nName=Preferences\nExec=/bin/true\n";
        std::fs::write(&path, source).unwrap();
        let entry = AppEntry {
            id: "app.desktop".into(),
            name: "Fixture".into(),
            icon: None,
            path: path.clone(),
        };
        let actions = rows(&entry, &[], false);
        assert_eq!(
            actions
                .iter()
                .filter(|r| matches!(r.action, AppAction::NewWindow(_)))
                .count(),
            1
        );
        assert!(actions
            .iter()
            .any(|r| r.action == AppAction::Desktop("preferences".into())));
        assert!(actions.iter().any(|r| r.action == AppAction::Pin));
        std::fs::write(
            &path,
            source.replace(
                "Type=Application",
                "Type=Application\nX-GNOME-SingleWindow=true",
            ),
        )
        .unwrap();
        assert!(!rows(&entry, &[], true)
            .iter()
            .any(|r| matches!(r.action, AppAction::NewWindow(_))));
        std::fs::remove_file(&path).unwrap();
        assert!(rows(&entry, &[], false).is_empty());
        std::fs::remove_dir(root).unwrap();
    }
}

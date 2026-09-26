//! Home screen layout persistence and fresh-install defaults.
//!
//! Follows the exact fallback shape `theme_thumbnails.rs::disk_cache_dir_from`
//! already established for this client's other on-disk state, one directory
//! family over: state (must not be silently dropped), not cache.
use crate::catalog::AppEntry;
use crate::home_grid::HomeSlot;
use serde::{Deserialize, Serialize};
use std::{
    io::Write,
    path::{Path, PathBuf},
};

/// Current on-disk schema version. Bump and add a migration if the shape of
/// [`HomeLayout`] ever changes incompatibly.
pub const SCHEMA: u32 = 1;

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Eq, Default)]
pub struct HomeLayout {
    pub schema: u32,
    /// Pages of grid slots, row-major within each page. `None` is an empty
    /// slot -- kept, not compacted, so removing or uninstalling one app
    /// never shifts every later icon (and a reinstall restores its place).
    pub pages: Vec<Vec<Option<String>>>,
    /// Fixed dock slots, independent of the current page.
    pub dock: Vec<Option<String>>,
}

impl HomeLayout {
    fn empty(dock_slots: usize) -> Self {
        Self {
            schema: SCHEMA,
            pages: vec![Vec::new()],
            dock: vec![None; dock_slots],
        }
    }

    /// Number of pages, always at least 1 so a fresh/empty Home still has a
    /// page to show.
    pub fn page_count(&self) -> usize {
        self.pages.len().max(1)
    }

    fn ensure_page(&mut self, page: usize, apps_per_page: usize) {
        while self.pages.len() <= page {
            self.pages.push(vec![None; apps_per_page.max(1)]);
        }
        let row = &mut self.pages[page];
        if row.len() < apps_per_page {
            row.resize(apps_per_page.max(1), None);
        }
    }

    /// The desktop-entry id occupying `slot`, if any. Out-of-range pages
    /// read as empty rather than panicking, since the saved layout's page
    /// count can be smaller than the panel's current `apps_per_page`.
    pub fn get(&self, slot: HomeSlot) -> Option<&str> {
        match slot {
            HomeSlot::Grid { page, slot } => self
                .pages
                .get(page)
                .and_then(|row| row.get(slot))
                .and_then(|entry| entry.as_deref()),
            HomeSlot::Dock { slot } => self.dock.get(slot).and_then(|entry| entry.as_deref()),
        }
    }

    /// Writes `id` into `slot`, growing pages/rows as needed. A `Dock`
    /// index past the fixed dock length is ignored (the dock never grows).
    pub fn set(&mut self, slot: HomeSlot, id: Option<String>, apps_per_page: usize) {
        match slot {
            HomeSlot::Grid { page, slot } => {
                self.ensure_page(page, apps_per_page);
                if let Some(cell) = self.pages[page].get_mut(slot) {
                    *cell = id;
                }
            }
            HomeSlot::Dock { slot } => {
                if let Some(cell) = self.dock.get_mut(slot) {
                    *cell = id;
                }
            }
        }
    }

    /// Removes every occurrence of `id` from the grid and dock (an icon
    /// should occupy at most one slot at a time; this keeps that true even
    /// if a caller's bookkeeping ever drifted).
    pub fn remove_id(&mut self, id: &str) {
        for row in &mut self.pages {
            for cell in row.iter_mut() {
                if cell.as_deref() == Some(id) {
                    *cell = None;
                }
            }
        }
        for cell in self.dock.iter_mut() {
            if cell.as_deref() == Some(id) {
                *cell = None;
            }
        }
    }

    /// Whether `id` already occupies some grid or dock slot.
    pub fn contains(&self, id: &str) -> bool {
        self.pages
            .iter()
            .flatten()
            .chain(self.dock.iter())
            .any(|entry| entry.as_deref() == Some(id))
    }

    /// Pins `id` into the first free grid slot, adding a new page when
    /// every existing page is full. A no-op if `id` is already pinned
    /// anywhere (grid or dock) -- long-pressing an app in the drawer that
    /// is already on Home does not relocate it. Used by the drawer's
    /// "Add to Home" action.
    pub fn pin(&mut self, id: String, apps_per_page: usize) {
        if self.contains(&id) {
            return;
        }
        let apps_per_page = apps_per_page.max(1);
        for row in self.pages.iter_mut() {
            if row.len() < apps_per_page {
                row.resize(apps_per_page, None);
            }
            if let Some(cell) = row.iter_mut().find(|cell| cell.is_none()) {
                *cell = Some(id);
                return;
            }
        }
        let mut page = vec![None; apps_per_page];
        page[0] = Some(id);
        self.pages.push(page);
    }
}

/// `$XDG_STATE_HOME/k230-shell/home.json`, or
/// `$HOME/.local/state/k230-shell/home.json` when `XDG_STATE_HOME` is unset
/// or empty. `None` when neither is available (a stripped test/service
/// environment): callers simply run with an in-memory default in that case.
pub fn state_path() -> Option<PathBuf> {
    state_path_from(
        std::env::var("XDG_STATE_HOME").ok().as_deref(),
        std::env::var("HOME").ok().as_deref(),
    )
}

/// `state_path`'s actual logic, taking its two env var readings as plain
/// arguments so tests can exercise the XDG/HOME fallback without mutating
/// real process-wide environment state.
fn state_path_from(xdg_state_home: Option<&str>, home: Option<&str>) -> Option<PathBuf> {
    if let Some(dir) = xdg_state_home {
        if !dir.trim().is_empty() {
            return Some(PathBuf::from(dir).join("k230-shell/home.json"));
        }
    }
    let home = home?;
    if home.trim().is_empty() {
        return None;
    }
    Some(PathBuf::from(home).join(".local/state/k230-shell/home.json"))
}

const MAX_FILE_BYTES: u64 = 256 * 1024;

/// Loads a previously saved layout. Returns `None` on a missing file,
/// oversized file, or any parse failure -- callers fall back to
/// [`seed_default`] in every one of those cases, so a corrupt file never
/// crashes the shell, it just re-seeds.
pub fn load(path: &Path) -> Option<HomeLayout> {
    let metadata = std::fs::metadata(path).ok()?;
    if !metadata.is_file() || metadata.len() > MAX_FILE_BYTES {
        return None;
    }
    let bytes = std::fs::read(path).ok()?;
    serde_json::from_slice(&bytes).ok()
}

/// Writes `layout` atomically: a sibling temp file, then a rename, so a
/// crash or power loss mid-write never leaves a half-written layout file
/// behind for the next `load` to choke on.
pub fn save(path: &Path, layout: &HomeLayout) -> Result<(), String> {
    let Some(parent) = path.parent() else {
        return Err("state path has no parent directory".into());
    };
    std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    let bytes = serde_json::to_vec_pretty(layout).map_err(|error| error.to_string())?;
    let temp = parent.join(format!(
        ".home.json.tmp.{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or_default()
    ));
    {
        let mut file = std::fs::File::create(&temp).map_err(|error| error.to_string())?;
        file.write_all(&bytes).map_err(|error| error.to_string())?;
        file.sync_all().map_err(|error| error.to_string())?;
    }
    std::fs::rename(&temp, path).map_err(|error| error.to_string())
}

/// One curated default category: a human label (unused at runtime, kept for
/// readability/tests) and the lowercase substrings matched against both the
/// desktop-entry id and its display name. The first installed app matching
/// any keyword in a category is used; a category with no installed match is
/// silently omitted, never shown as a placeholder.
const DEFAULT_CATEGORIES: &[(&str, &[&str])] = &[
    ("terminal", &["term", "foot", "console"]),
    (
        "files",
        &["files", "nautilus", "filemanager", "file-manager", "pcmanfm", "thunar", "file manager"],
    ),
    (
        "editor",
        &["texteditor", "text-editor", "text editor", "gedit", "editor", "code"],
    ),
    (
        "monitor",
        &["htop", "monitor", "system-monitor", "system monitor", "taskmanager", "task manager"],
    ),
    ("video", &["video", "player", "mpv", "vlc"]),
    (
        "settings",
        &["settings", "control-center", "control center", "preferences"],
    ),
];

fn matches_category(app: &AppEntry, keywords: &[&str]) -> bool {
    let id = app.id.to_lowercase();
    let name = app.name.to_lowercase();
    keywords.iter().any(|word| id.contains(word) || name.contains(word))
}

/// Picks the curated default apps present on this image, in
/// `DEFAULT_CATEGORIES` priority order, each category contributing at most
/// one app and never a placeholder when nothing installed matches it.
pub fn curated_defaults(apps: &[AppEntry]) -> Vec<String> {
    let mut chosen = Vec::new();
    for (_label, keywords) in DEFAULT_CATEGORIES {
        if let Some(app) = apps.iter().find(|app| matches_category(app, keywords)) {
            if !chosen.contains(&app.id) {
                chosen.push(app.id.clone());
            }
        }
    }
    chosen
}

/// Builds a fresh Home layout when no saved one exists: the curated
/// defaults fill the dock first (up to `dock_slots`, webOS Quick Launch /
/// Android hotseat style -- the handful of apps a person reaches for most),
/// then the remaining curated defaults (if any) fill the first grid page.
/// Per `openspec/config.yaml`'s standing rule, this always runs against the
/// real installed catalog -- there is no hardcoded icon set, only a
/// hardcoded *preference order* that is skipped entirely when nothing
/// installed matches it.
pub fn seed_default(apps: &[AppEntry], dock_slots: usize, apps_per_page: usize) -> HomeLayout {
    let defaults = curated_defaults(apps);
    let mut layout = HomeLayout::empty(dock_slots);
    let mut iter = defaults.into_iter();
    for slot in layout.dock.iter_mut() {
        let Some(id) = iter.next() else { break };
        *slot = Some(id);
    }
    let remaining: Vec<String> = iter.collect();
    if !remaining.is_empty() {
        let mut page = vec![None; apps_per_page.max(1)];
        for (index, id) in remaining.into_iter().enumerate().take(page.len()) {
            page[index] = Some(id);
        }
        layout.pages = vec![page];
    }
    layout
}

/// Loads the saved layout, or seeds and immediately persists a fresh
/// default when none exists (or the saved file could not be read), so a
/// second boot is stable even before anything is intentionally pinned.
/// `path` is `None` in a stripped environment with no usable state
/// directory; the seed then simply is not persisted, exactly as if a write
/// failed, and the shell continues with an in-memory default.
pub fn load_or_seed(
    path: Option<&Path>,
    apps: &[AppEntry],
    dock_slots: usize,
    apps_per_page: usize,
) -> HomeLayout {
    if let Some(path) = path {
        if let Some(layout) = load(path) {
            return layout;
        }
    }
    let layout = seed_default(apps, dock_slots, apps_per_page);
    if let Some(path) = path {
        let _ = save(path, &layout);
    }
    layout
}

#[cfg(test)]
mod tests {
    use super::*;

    fn app(id: &str, name: &str) -> AppEntry {
        AppEntry {
            id: id.into(),
            name: name.into(),
            icon: None,
            path: PathBuf::new(),
        }
    }

    #[test]
    fn state_path_prefers_xdg_then_home_then_none() {
        assert_eq!(
            state_path_from(Some("/xdg"), Some("/home/user")),
            Some(PathBuf::from("/xdg/k230-shell/home.json"))
        );
        assert_eq!(
            state_path_from(Some(""), Some("/home/user")),
            Some(PathBuf::from("/home/user/.local/state/k230-shell/home.json"))
        );
        assert_eq!(state_path_from(None, Some("")), None);
        assert_eq!(state_path_from(None, None), None);
    }

    #[test]
    fn curated_defaults_skip_missing_categories_and_dedupe() {
        let apps = vec![
            app("foot.desktop", "Foot"),
            app("org.gnome.TextEditor.desktop", "Text Editor"),
            app("htop.desktop", "Htop"),
        ];
        let defaults = curated_defaults(&apps);
        assert_eq!(
            defaults,
            vec!["foot.desktop", "org.gnome.TextEditor.desktop", "htop.desktop"],
            "priority order, files/video/settings omitted (not installed)"
        );
    }

    #[test]
    fn seed_default_fills_dock_before_grid() {
        let apps = vec![
            app("foot.desktop", "Foot"),
            app("files.desktop", "Files"),
            app("editor.desktop", "Text Editor"),
            app("htop.desktop", "System Monitor"),
            app("video.desktop", "Video Player"),
            app("settings.desktop", "Settings"),
        ];
        let layout = seed_default(&apps, 4, 8);
        assert_eq!(
            layout.dock,
            vec![
                Some("foot.desktop".into()),
                Some("files.desktop".into()),
                Some("editor.desktop".into()),
                Some("htop.desktop".into()),
            ]
        );
        assert_eq!(layout.pages.len(), 1);
        assert_eq!(layout.pages[0][0], Some("video.desktop".into()));
        assert_eq!(layout.pages[0][1], Some("settings.desktop".into()));
        assert!(layout.pages[0][2..].iter().all(Option::is_none));
    }

    #[test]
    fn seed_default_with_nothing_installed_is_an_empty_home() {
        let layout = seed_default(&[], 4, 8);
        assert_eq!(layout.dock, vec![None, None, None, None]);
        assert_eq!(layout.pages, vec![vec![]]);
    }

    #[test]
    fn save_then_load_round_trips_exactly() {
        let dir = std::env::temp_dir().join(format!(
            "k230-home-state-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let path = dir.join("home.json");
        let layout = HomeLayout {
            schema: SCHEMA,
            pages: vec![vec![Some("a.desktop".into()), None, Some("b.desktop".into())]],
            dock: vec![Some("c.desktop".into()), None],
        };
        save(&path, &layout).unwrap();
        assert_eq!(load(&path), Some(layout));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn load_or_seed_persists_the_seed_so_a_second_boot_is_stable() {
        let dir = std::env::temp_dir().join(format!(
            "k230-home-state-seed-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let path = dir.join("home.json");
        let apps = vec![app("foot.desktop", "Foot")];
        let first = load_or_seed(Some(&path), &apps, 4, 8);
        assert_eq!(first.dock[0], Some("foot.desktop".into()));
        // Second boot: even if the catalog has since changed, the saved
        // layout -- not a fresh reseed -- is what comes back.
        let changed_apps = vec![app("other.desktop", "Other")];
        let second = load_or_seed(Some(&path), &changed_apps, 4, 8);
        assert_eq!(second, first);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn missing_entry_keeps_its_slot_on_load() {
        // An app pinned, then uninstalled: `load` itself does not filter
        // anything (the missing-entry-preserves-slot behavior is a
        // property of never compacting `Option` slots, not of load doing
        // any lookup), so the id simply comes back and the caller renders
        // an empty tile for any id `installed_apps()` no longer lists.
        let dir = std::env::temp_dir().join(format!(
            "k230-home-state-missing-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let path = dir.join("home.json");
        let layout = HomeLayout {
            schema: SCHEMA,
            pages: vec![vec![Some("gone.desktop".into()), None]],
            dock: vec![None; 4],
        };
        save(&path, &layout).unwrap();
        let loaded = load(&path).unwrap();
        assert_eq!(loaded.pages[0][0], Some("gone.desktop".into()));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn corrupt_file_falls_back_to_seed_rather_than_crashing() {
        let dir = std::env::temp_dir().join(format!(
            "k230-home-state-corrupt-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("home.json");
        std::fs::write(&path, b"not json").unwrap();
        assert_eq!(load(&path), None);
        let apps = vec![app("foot.desktop", "Foot")];
        let layout = load_or_seed(Some(&path), &apps, 4, 8);
        assert_eq!(layout.dock[0], Some("foot.desktop".into()));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn pin_fills_first_free_slot_then_adds_a_page_when_full() {
        let mut layout = HomeLayout::empty(4);
        layout.set(HomeSlot::Grid { page: 0, slot: 0 }, Some("a.desktop".into()), 2);
        layout.pin("b.desktop".into(), 2);
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 1 }), Some("b.desktop"));
        layout.pin("c.desktop".into(), 2);
        assert_eq!(layout.page_count(), 2);
        assert_eq!(layout.get(HomeSlot::Grid { page: 1, slot: 0 }), Some("c.desktop"));
    }

    #[test]
    fn pin_is_a_no_op_for_an_already_pinned_app() {
        let mut layout = HomeLayout::empty(4);
        layout.set(HomeSlot::Grid { page: 0, slot: 2 }, Some("a.desktop".into()), 4);
        layout.pin("a.desktop".into(), 4);
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 2 }), Some("a.desktop"));
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 0 }), None, "did not duplicate elsewhere");
        // Also true when the existing pin is in the dock, not the grid.
        let mut layout = HomeLayout::empty(4);
        layout.set(HomeSlot::Dock { slot: 1 }, Some("b.desktop".into()), 4);
        layout.pin("b.desktop".into(), 4);
        assert_eq!(layout.get(HomeSlot::Dock { slot: 1 }), Some("b.desktop"));
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 0 }), None);
    }

    #[test]
    fn remove_id_clears_grid_and_dock_without_shifting_neighbors() {
        let mut layout = HomeLayout::empty(4);
        layout.set(HomeSlot::Grid { page: 0, slot: 0 }, Some("a.desktop".into()), 4);
        layout.set(HomeSlot::Grid { page: 0, slot: 1 }, Some("b.desktop".into()), 4);
        layout.remove_id("a.desktop");
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 0 }), None);
        assert_eq!(layout.get(HomeSlot::Grid { page: 0, slot: 1 }), Some("b.desktop"));
    }
}

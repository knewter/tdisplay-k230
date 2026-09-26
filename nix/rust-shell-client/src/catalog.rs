//! Installed desktop entries, using GIO's visibility and Exec semantics but
//! our own directory scan for *which files exist right now*.
//!
//! `gio::AppInfo::all()` (the previous source of truth here) reads from
//! GIO's own desktop-file cache/registry, which is populated once and is
//! never guaranteed to notice a file that appeared or vanished after that --
//! doubly so on NixOS, where `nixos-rebuild switch` atomically swaps the
//! `/run/current-system` symlink out from under any process that resolved
//! it earlier. Scanning `XDG_DATA_HOME`/`XDG_DATA_DIRS` directly, and
//! parsing each file fresh with [`gio::DesktopAppInfo::from_filename`]
//! (which never touches that cache), makes every call here see the current
//! filesystem state.
use gio::prelude::*;
use std::{
    collections::HashSet,
    ffi::OsStr,
    path::{Path, PathBuf},
};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AppEntry {
    pub id: String,
    pub name: String,
    pub icon: Option<String>,
    /// The `.desktop` file this entry was parsed from -- kept so launching
    /// can re-parse the exact same file with
    /// [`gio::DesktopAppInfo::from_filename`] rather than trusting GIO's
    /// id-keyed lookup (`DesktopAppInfo::new`) to still resolve the same id
    /// to the same file after a later rescan.
    pub path: PathBuf,
}

/// The `applications` directories this client searches, in XDG precedence
/// order (`XDG_DATA_HOME` first, then each `XDG_DATA_DIRS` entry). Also the
/// directories [`crate::app_watch::CatalogWatcher`] watches, so a rescan and
/// the watch set are always looking at exactly the same list.
pub fn applications_dirs() -> Vec<PathBuf> {
    applications_dirs_from(
        std::env::var("XDG_DATA_HOME").ok(),
        std::env::var("HOME").ok(),
        std::env::var("XDG_DATA_DIRS").ok(),
    )
}

fn applications_dirs_from(
    xdg_data_home: Option<String>,
    home: Option<String>,
    xdg_data_dirs: Option<String>,
) -> Vec<PathBuf> {
    data_dirs_from(xdg_data_home, home, xdg_data_dirs)
        .into_iter()
        .map(|dir| dir.join("applications"))
        .collect()
}

/// The plain `XDG_DATA_HOME`/`XDG_DATA_DIRS` directories (before the
/// `applications` suffix), in precedence order. Split out from
/// [`applications_dirs_from`] only so tests can assert on it directly.
fn data_dirs_from(
    xdg_data_home: Option<String>,
    home: Option<String>,
    xdg_data_dirs: Option<String>,
) -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    let data_home = xdg_data_home
        .filter(|value| !value.trim().is_empty())
        .map(PathBuf::from)
        .or_else(|| {
            home.filter(|value| !value.trim().is_empty())
                .map(|home| PathBuf::from(home).join(".local/share"))
        });
    if let Some(dir) = data_home {
        dirs.push(dir);
    }
    // Same fallback the freedesktop base-dir spec gives `XDG_DATA_DIRS`.
    let data_dirs = xdg_data_dirs
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| "/usr/local/share/:/usr/share/".to_string());
    for entry in data_dirs.split(':') {
        if !entry.trim().is_empty() {
            dirs.push(PathBuf::from(entry));
        }
    }
    dirs
}

/// The live catalog: a fresh scan of [`applications_dirs`], parsed and
/// filtered. Called at startup and again on every debounced rescan (see
/// `app_watch::CatalogWatcher`); never trusts any cache.
pub fn installed_apps() -> Vec<AppEntry> {
    scan_apps(&applications_dirs())
}

/// [`installed_apps`]'s actual logic, taking the directories to search as a
/// plain argument so tests (and the live watcher's rescan) can point it at a
/// temp tree instead of the real environment.
pub fn scan_apps(applications_dirs: &[PathBuf]) -> Vec<AppEntry> {
    let mut seen_ids: HashSet<String> = HashSet::new();
    let mut apps = Vec::new();
    for dir in applications_dirs {
        let mut files = Vec::new();
        collect_desktop_files(dir, dir, &mut files, 0);
        for (id, path) in files {
            // First directory in precedence order wins for a given id --
            // `seen_ids` is checked (and populated) in the same
            // `applications_dirs` order this loop already walks in, so a
            // later directory's file for an id already claimed is simply
            // dropped, exactly like the freedesktop spec's own override
            // rule for desktop-file ids.
            if !seen_ids.insert(id.clone()) {
                continue;
            }
            if let Some(entry) = parse_entry(id, path) {
                apps.push(entry);
            }
        }
    }
    apps.sort_by(|a, b| {
        a.name
            .to_lowercase()
            .cmp(&b.name.to_lowercase())
            .then(a.id.cmp(&b.id))
    });
    apps.truncate(128);
    apps
}

/// Recursively collects every `*.desktop` file under `dir` (which starts
/// out equal to `root`, the `applications` directory itself; `root` stays
/// fixed across the recursion so [`desktop_id`] always computes the id
/// relative to it), pairing each with its computed desktop-file id.
/// Missing/unreadable directories simply contribute nothing -- this is
/// called once per XDG dir on every rescan, so a dir that does not exist
/// right now (not yet created, or NixOS mid-symlink-swap) is not an error.
fn collect_desktop_files(root: &Path, dir: &Path, out: &mut Vec<(String, PathBuf)>, depth: u32) {
    // Guards against a symlink cycle in a hand-crafted or malicious tree;
    // real desktop-file trees are only a few levels deep at most.
    if depth > 16 {
        return;
    }
    let Ok(read_dir) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in read_dir.flatten() {
        let path = entry.path();
        let is_dir = entry
            .file_type()
            .map(|file_type| file_type.is_dir())
            .unwrap_or(false)
            || (entry
                .file_type()
                .map(|file_type| file_type.is_symlink())
                .unwrap_or(false)
                && std::fs::metadata(&path)
                    .map(|metadata| metadata.is_dir())
                    .unwrap_or(false));
        if is_dir {
            collect_desktop_files(root, &path, out, depth + 1);
            continue;
        }
        if path.extension() == Some(OsStr::new("desktop")) {
            if let Some(id) = desktop_id(root, &path) {
                out.push((id, path));
            }
        }
    }
}

/// The desktop-file id for `path`, computed as its path relative to `root`
/// (the `applications` directory) with every `/` turned into `-` -- e.g.
/// `kde/foo.desktop` under `root` becomes `kde-foo.desktop`.
fn desktop_id(root: &Path, path: &Path) -> Option<String> {
    let relative = path.strip_prefix(root).ok()?;
    let mut id = String::new();
    for component in relative.components() {
        if !id.is_empty() {
            id.push('-');
        }
        id.push_str(&component.as_os_str().to_string_lossy());
    }
    if id.is_empty() {
        None
    } else {
        Some(id)
    }
}

/// Parses one `.desktop` file fresh (never through GIO's cache -- see this
/// module's own doc) and applies the same visibility/bounds filters
/// `installed_apps` always has. `None` on a parse failure, a hidden/
/// `NoDisplay` entry, or any bound violation, exactly as the previous
/// `gio::AppInfo::all()`-based filter did.
fn parse_entry(id: String, path: PathBuf) -> Option<AppEntry> {
    if id.is_empty() || id.len() > 160 {
        return None;
    }
    let app = gio::DesktopAppInfo::from_filename(&path)?;
    // `should_show()` covers `NoDisplay` and `OnlyShowIn`/`NotShowIn`, but
    // not `Hidden` (per the freedesktop spec, `Hidden=true` means "treat as
    // if this file were not present at all" -- a stronger, unconditional
    // exclusion than `NoDisplay`'s "don't list, but the entry still
    // exists"), so it needs its own explicit check.
    if !app.should_show() || app.is_hidden() {
        return None;
    }
    let name: String = app
        .display_name()
        .chars()
        .filter(|character| !character.is_control())
        .take(96)
        .collect();
    if name.trim().is_empty() {
        return None;
    }
    Some(AppEntry {
        id,
        name,
        icon: app
            .icon()
            .and_then(|icon| icon.to_string())
            .map(|value| value.to_string())
            .filter(|value| value.len() <= 512),
        path,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn catalog_is_bounded_and_stably_sorted() {
        let apps = installed_apps();
        assert!(apps.len() <= 128);
        assert!(apps
            .iter()
            .all(|app| !app.id.is_empty() && !app.name.is_empty()));
        assert!(apps.iter().all(|app| app.id.len() <= 160
            && app.name.chars().count() <= 96
            && app.icon.as_ref().is_none_or(|icon| icon.len() <= 512)));
        assert!(apps.windows(2).all(|pair| {
            (pair[0].name.to_lowercase(), &pair[0].id) <= (pair[1].name.to_lowercase(), &pair[1].id)
        }));
    }

    #[test]
    fn data_dirs_from_prefers_xdg_data_home_then_falls_back_to_home() {
        let dirs = data_dirs_from(
            Some("/xdg/data".into()),
            Some("/home/user".into()),
            Some("/a:/b".into()),
        );
        assert_eq!(
            dirs,
            vec![PathBuf::from("/xdg/data"), PathBuf::from("/a"), PathBuf::from("/b")]
        );
        let dirs = data_dirs_from(None, Some("/home/user".into()), Some("/a".into()));
        assert_eq!(
            dirs,
            vec![PathBuf::from("/home/user/.local/share"), PathBuf::from("/a")]
        );
        let dirs = data_dirs_from(None, None, None);
        assert_eq!(dirs, vec![PathBuf::from("/usr/local/share/"), PathBuf::from("/usr/share/")]);
    }

    fn temp_root(label: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "k230-catalog-test-{label}-{}-{}",
            std::process::id(),
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        ))
    }

    fn write_entry(applications_dir: &Path, relative: &str, body: &str) -> PathBuf {
        let path = applications_dir.join(relative);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(&path, format!("[Desktop Entry]\nType=Application\n{body}")).unwrap();
        path
    }

    #[test]
    fn nested_desktop_file_id_replaces_slashes_with_dashes() {
        let root = temp_root("id-derivation");
        let applications = root.join("applications");
        write_entry(&applications, "kde/foo.desktop", "Name=Foo\nExec=true\n");
        let apps = scan_apps(&[applications]);
        assert_eq!(apps.len(), 1);
        assert_eq!(apps[0].id, "kde-foo.desktop");
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn first_directory_in_precedence_order_wins_for_a_shared_id() {
        let root = temp_root("precedence");
        let home = root.join("home/applications");
        let system = root.join("system/applications");
        write_entry(&home, "same.desktop", "Name=Home\nExec=true\n");
        write_entry(&system, "same.desktop", "Name=System\nExec=true\n");
        // `home` listed first, matching XDG_DATA_HOME coming before
        // XDG_DATA_DIRS -- its copy must be the one that wins.
        let apps = scan_apps(&[home.clone(), system.clone()]);
        assert_eq!(apps.len(), 1);
        assert_eq!(apps[0].name, "Home");
        assert_eq!(apps[0].path, home.join("same.desktop"));
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn no_display_and_hidden_entries_are_filtered() {
        let root = temp_root("visibility");
        let applications = root.join("applications");
        write_entry(&applications, "visible.desktop", "Name=Visible\nExec=true\n");
        write_entry(
            &applications,
            "nodisplay.desktop",
            "Name=NoDisplay\nExec=true\nNoDisplay=true\n",
        );
        write_entry(
            &applications,
            "hidden.desktop",
            "Name=Hidden\nExec=true\nHidden=true\n",
        );
        let apps = scan_apps(&[applications]);
        assert_eq!(apps.len(), 1);
        assert_eq!(apps[0].id, "visible.desktop");
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn a_file_added_after_the_first_scan_appears_on_the_next_one() {
        let root = temp_root("fresh-scan");
        let applications = root.join("applications");
        write_entry(&applications, "first.desktop", "Name=First\nExec=true\n");
        let first_scan = scan_apps(&[applications.clone()]);
        assert_eq!(first_scan.len(), 1);
        write_entry(&applications, "second.desktop", "Name=Second\nExec=true\n");
        let second_scan = scan_apps(&[applications]);
        assert_eq!(second_scan.len(), 2);
        assert!(second_scan.iter().any(|app| app.id == "second.desktop"));
        std::fs::remove_dir_all(&root).unwrap();
    }
}

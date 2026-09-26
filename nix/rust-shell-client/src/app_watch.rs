//! inotify-based watch over the `.desktop` search path, so
//! `catalog::installed_apps` gets rescanned promptly instead of only once at
//! startup.
//!
//! The tricky case is NixOS itself: `nixos-rebuild switch` (and
//! `home-manager switch`, and `nix-env`) replace an entire tree by atomically
//! swapping a symlink -- `/run/current-system` most notably, but also
//! `~/.nix-profile` and `/etc/profiles/per-user/<user>` -- rather than
//! mutating any file a plain recursive watch on the resolved directory would
//! ever see change. Detecting that requires watching each symlink
//! *component* along the path from its own parent directory, not the
//! resolved target.
use std::{
    collections::HashMap,
    ffi::{CString, OsStr, OsString},
    io,
    os::fd::{AsRawFd, FromRawFd, OwnedFd, RawFd},
    os::unix::ffi::OsStrExt,
    path::{Path, PathBuf},
};

/// One inotify watch this module owns, keyed by its watch descriptor.
enum WatchKind {
    /// `dir` is watched only for a create/delete/rename/self-delete
    /// touching the single child named `name` -- the ancestor-chain
    /// mechanism that notices a symlink swap or a not-yet-existing
    /// directory coming into being. `/run` itself is far too noisy to
    /// watch unfiltered, hence the name check.
    Ancestor { name: OsString },
    /// A real, currently-resolved `applications` directory (or a
    /// subdirectory of one): any create/delete/rename/close-write here
    /// means the catalog needs a rescan, no name filtering needed since
    /// this watch is already scoped to just that tree.
    AppsDir,
}

struct Watch {
    #[allow(dead_code)] // kept for debugging/logging, not read elsewhere
    path: PathBuf,
    kind: WatchKind,
}

/// 8-byte-aligned so the raw event buffer inotify writes into (a sequence
/// of native-endian `struct inotify_event`s, each starting with `u32`
/// fields) can be read back through a `libc::inotify_event` pointer without
/// ever being unaligned.
#[repr(align(8))]
struct EventBuffer([u8; 8192]);

pub struct CatalogWatcher {
    fd: OwnedFd,
    watches: HashMap<i32, Watch>,
}

impl CatalogWatcher {
    /// `candidates` is the same list `catalog::applications_dirs()` returns
    /// -- every `<data-dir>/applications` this client searches, in
    /// precedence order.
    pub fn new(candidates: &[PathBuf]) -> io::Result<Self> {
        let raw = unsafe { libc::inotify_init1(libc::IN_NONBLOCK | libc::IN_CLOEXEC) };
        if raw < 0 {
            return Err(io::Error::last_os_error());
        }
        let fd = unsafe { OwnedFd::from_raw_fd(raw) };
        let mut watcher = Self { fd, watches: HashMap::new() };
        watcher.rebuild(candidates);
        Ok(watcher)
    }

    pub fn as_raw_fd(&self) -> RawFd {
        self.fd.as_raw_fd()
    }

    /// Drops every existing watch and recomputes the full set against the
    /// current filesystem state. Called once at construction and again any
    /// time [`Self::drain`] sees a structural change (a symlink swap, or an
    /// ancestor appearing/disappearing) -- cheap enough to always redo from
    /// scratch since `candidates` is a handful of XDG directories, never
    /// thousands.
    pub fn rebuild(&mut self, candidates: &[PathBuf]) {
        for wd in self.watches.keys().copied().collect::<Vec<_>>() {
            unsafe { libc::inotify_rm_watch(self.as_raw_fd(), wd) };
        }
        self.watches.clear();
        for apps_dir in candidates {
            for (dir, name) in ancestor_watch_points(apps_dir) {
                self.add_watch(&dir, WatchKind::Ancestor { name });
            }
            if !is_immutable(apps_dir) && apps_dir.is_dir() {
                self.add_apps_dir_recursive(apps_dir);
            }
        }
    }

    fn add_watch(&mut self, dir: &Path, kind: WatchKind) {
        let mask = match kind {
            WatchKind::Ancestor { .. } => {
                (libc::IN_CREATE | libc::IN_DELETE | libc::IN_MOVED_FROM | libc::IN_MOVED_TO
                    | libc::IN_DELETE_SELF) as u32
            }
            WatchKind::AppsDir => {
                (libc::IN_CREATE
                    | libc::IN_DELETE
                    | libc::IN_MOVED_FROM
                    | libc::IN_MOVED_TO
                    | libc::IN_CLOSE_WRITE
                    | libc::IN_DELETE_SELF) as u32
            }
        };
        let Ok(cpath) = CString::new(dir.as_os_str().as_bytes()) else {
            return;
        };
        let wd = unsafe { libc::inotify_add_watch(self.as_raw_fd(), cpath.as_ptr(), mask) };
        if wd >= 0 {
            self.watches.insert(wd, Watch { path: dir.to_path_buf(), kind });
        }
    }

    /// Watches `dir` itself, then every subdirectory beneath it (skipping
    /// anything under `/nix/store`, which is immutable and so never fires
    /// an event worth waiting on).
    fn add_apps_dir_recursive(&mut self, dir: &Path) {
        if is_immutable(dir) {
            return;
        }
        self.add_watch(dir, WatchKind::AppsDir);
        let Ok(read_dir) = std::fs::read_dir(dir) else {
            return;
        };
        for entry in read_dir.flatten() {
            let path = entry.path();
            let is_dir = entry
                .file_type()
                .map(|file_type| file_type.is_dir())
                .unwrap_or(false)
                || std::fs::metadata(&path).map(|metadata| metadata.is_dir()).unwrap_or(false);
            if is_dir {
                self.add_apps_dir_recursive(&path);
            }
        }
    }

    /// Drains every pending inotify event. Returns `true` if a rescan is
    /// warranted: either a real, mutable `applications` directory's
    /// contents changed, or a structural change (a symlink swap, or an
    /// ancestor coming into/out of existence) occurred -- in which case the
    /// whole watch set is also rebuilt against `candidates` before
    /// returning, so the next `drain` is watching the right places again.
    pub fn drain(&mut self, candidates: &[PathBuf]) -> bool {
        let mut relevant = false;
        let mut structural = false;
        let mut buffer = EventBuffer([0u8; 8192]);
        loop {
            let read = unsafe {
                libc::read(
                    self.as_raw_fd(),
                    buffer.0.as_mut_ptr().cast(),
                    buffer.0.len(),
                )
            };
            if read <= 0 {
                break;
            }
            let read = read as usize;
            let mut offset = 0usize;
            let header_len = std::mem::size_of::<libc::inotify_event>();
            while offset + header_len <= read {
                // SAFETY: `buffer` is 8-byte aligned and `offset` always
                // lands on the start of a kernel-written `inotify_event`
                // (the loop advances by exactly `header_len + event.len`
                // each time), so this pointer is both aligned and in
                // bounds for the read below.
                let event = unsafe { &*(buffer.0.as_ptr().add(offset).cast::<libc::inotify_event>()) };
                let name_start = offset + header_len;
                let name_len = event.len as usize;
                let name = if name_len > 0 && name_start + name_len <= read {
                    let bytes = &buffer.0[name_start..name_start + name_len];
                    let end = bytes.iter().position(|&byte| byte == 0).unwrap_or(name_len);
                    Some(OsStr::from_bytes(&bytes[..end]).to_os_string())
                } else {
                    None
                };
                if let Some(watch) = self.watches.get(&event.wd) {
                    match &watch.kind {
                        WatchKind::Ancestor { name: tracked } => {
                            let self_deleted = event.mask & libc::IN_DELETE_SELF as u32 != 0;
                            let name_matches = name.as_deref() == Some(tracked.as_os_str());
                            if self_deleted || name_matches {
                                structural = true;
                                relevant = true;
                            }
                        }
                        WatchKind::AppsDir => {
                            relevant = true;
                        }
                    }
                }
                offset = name_start + name_len;
            }
        }
        if structural {
            self.rebuild(candidates);
        }
        relevant
    }
}

fn is_immutable(path: &Path) -> bool {
    path.starts_with("/nix/store")
}

/// Ancestor watch points for `path`, from the root down: for each existing
/// symlink component, the pair `(that component's parent directory, that
/// component's own name)`; for the first missing component, the pair
/// `(nearest existing ancestor, the missing name)`. Descent stops at the
/// first missing component (nothing further down can be inspected yet, and
/// creating it is exactly the event the returned watch point is for).
fn ancestor_watch_points(path: &Path) -> Vec<(PathBuf, OsString)> {
    let mut points = Vec::new();
    let mut current = PathBuf::new();
    for component in path.components() {
        current.push(component);
        match std::fs::symlink_metadata(&current) {
            Ok(metadata) if metadata.file_type().is_symlink() => {
                if let (Some(parent), Some(name)) = (current.parent(), current.file_name()) {
                    points.push((parent.to_path_buf(), name.to_os_string()));
                }
            }
            Ok(_) => {}
            Err(_) => {
                if let (Some(parent), Some(name)) = (current.parent(), current.file_name()) {
                    points.push((parent.to_path_buf(), name.to_os_string()));
                }
                break;
            }
        }
    }
    points
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        os::unix::fs::symlink,
        thread,
        time::{Duration, Instant, SystemTime, UNIX_EPOCH},
    };

    fn temp_root(label: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "k230-app-watch-test-{label}-{}-{}",
            std::process::id(),
            SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        ))
    }

    /// Polls `watcher.drain(candidates)` for up to `timeout`, returning
    /// `true` as soon as one call reports a relevant change. Real inotify
    /// events land on their own schedule (a rename() happens on another
    /// thread/process boundary in the real system this mirrors), so tests
    /// poll rather than assume the very next `drain` call already sees it.
    fn wait_for_signal(
        watcher: &mut CatalogWatcher,
        candidates: &[PathBuf],
        timeout: Duration,
    ) -> bool {
        let deadline = Instant::now() + timeout;
        loop {
            if watcher.drain(candidates) {
                return true;
            }
            if Instant::now() >= deadline {
                return false;
            }
            thread::sleep(Duration::from_millis(10));
        }
    }

    fn write_entry(applications_dir: &Path, relative: &str, body: &str) {
        let path = applications_dir.join(relative);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(&path, format!("[Desktop Entry]\nType=Application\n{body}")).unwrap();
    }

    #[test]
    fn ancestor_watch_points_cover_symlink_components_and_missing_tail() {
        let root = temp_root("ancestor-points");
        std::fs::create_dir_all(root.join("real")).unwrap();
        symlink(root.join("real"), root.join("current")).unwrap();
        let candidate = root.join("current/share/applications");
        let points = ancestor_watch_points(&candidate);
        assert!(
            points.iter().any(|(dir, name)| dir == &root && name == OsStr::new("current")),
            "expected a watch point on the symlink component itself: {points:?}"
        );
        // The nearest existing ancestor of the missing `share` component is
        // reached by walking the literal (unresolved) path -- `root/current`,
        // not `root/real` -- since intermediate symlink components resolve
        // transparently through the kernel's own path lookup; watching
        // `root/current` for a `share` child therefore already watches
        // whatever `current` currently resolves to, exactly like `open()`
        // or `readdir()` on that same path would.
        assert!(
            points
                .iter()
                .any(|(dir, name)| dir == &root.join("current") && name == OsStr::new("share")),
            "expected a watch point on the first missing component's existing parent: {points:?}"
        );
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn a_symlink_swap_like_nixos_switch_signals_a_rescan_and_the_new_app_appears() {
        let root = temp_root("symlink-swap");
        let old_target = root.join("old-system/share/applications");
        let new_target = root.join("new-system/share/applications");
        write_entry(&old_target, "old.desktop", "Name=Old\nExec=true\n");
        write_entry(&new_target, "new.desktop", "Name=New\nExec=true\n");
        symlink(root.join("old-system"), root.join("current-system")).unwrap();

        let candidate = root.join("current-system/share/applications");
        let candidates = vec![candidate.clone()];
        let mut watcher = CatalogWatcher::new(&candidates).unwrap();

        let before = crate::catalog::scan_apps(&candidates);
        assert_eq!(before.len(), 1);
        assert_eq!(before[0].id, "old.desktop");

        // The exact rename-over-a-tmp-symlink NixOS uses to swap
        // `/run/current-system` atomically: build the new link under a
        // temp name, then `rename()` it over the old one in one step.
        let tmp_link = root.join("current-system.tmp");
        symlink(root.join("new-system"), &tmp_link).unwrap();
        std::fs::rename(&tmp_link, root.join("current-system")).unwrap();

        assert!(
            wait_for_signal(&mut watcher, &candidates, Duration::from_secs(2)),
            "expected the symlink swap to signal a rescan"
        );
        let after = crate::catalog::scan_apps(&candidates);
        assert_eq!(after.len(), 1);
        assert_eq!(after[0].id, "new.desktop", "watcher should now see the new target");
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn adding_and_removing_a_file_in_a_plain_mutable_dir_each_signal_a_rescan() {
        let root = temp_root("plain-mutable");
        let applications = root.join("applications");
        write_entry(&applications, "first.desktop", "Name=First\nExec=true\n");
        let candidates = vec![applications.clone()];
        let mut watcher = CatalogWatcher::new(&candidates).unwrap();

        write_entry(&applications, "second.desktop", "Name=Second\nExec=true\n");
        assert!(
            wait_for_signal(&mut watcher, &candidates, Duration::from_secs(2)),
            "expected an added file to signal a rescan"
        );
        let after_add = crate::catalog::scan_apps(&candidates);
        assert_eq!(after_add.len(), 2);

        std::fs::remove_file(applications.join("second.desktop")).unwrap();
        assert!(
            wait_for_signal(&mut watcher, &candidates, Duration::from_secs(2)),
            "expected a removed file to signal a rescan"
        );
        let after_remove = crate::catalog::scan_apps(&candidates);
        assert_eq!(after_remove.len(), 1);
        std::fs::remove_dir_all(&root).unwrap();
    }
}

//! Bounded freedesktop icon lookup and native SVG/PNG decode. The renderer
//! keeps decoded surfaces across frames; theme changes replace this cache.
use cairo::{Context, Format, ImageSurface};
use gio::prelude::*;
use glib::{KeyFile, KeyFileFlags};
use std::{
    ffi::CString,
    fs::{self, File},
    io::Read,
    os::unix::ffi::OsStrExt,
    path::{Path, PathBuf},
};

const FILE_LIMIT: u64 = 512 * 1024;
const INDEX_LIMIT: u64 = 64 * 1024;
/// Bumped from the drawer-era 12 so a full Home page (up to a 4-column grid)
/// plus its dock can stay resident without every icon evicting its own
/// neighbor on each frame -- see `home_grid.rs`'s `apps_per_page`/
/// `DOCK_SLOTS`. Still small enough that one full cache is a bounded,
/// modest amount of decoded ARGB32 memory at the icon sizes this shell uses.
const CACHE_LIMIT: usize = 24;
const MAX_ROOTS: usize = 16;
const MAX_DIRS: usize = 128;
const MAX_DEPTH: usize = 4;

#[repr(C)]
struct RsvgRectangle {
    x: f64,
    y: f64,
    width: f64,
    height: f64,
}

#[link(name = "rsvg-2")]
unsafe extern "C" {
    fn rsvg_handle_new_from_file(
        path: *const libc::c_char,
        error: *mut *mut libc::c_void,
    ) -> *mut libc::c_void;
    fn rsvg_handle_render_document(
        handle: *mut libc::c_void,
        cr: *mut libc::c_void,
        viewport: *const RsvgRectangle,
        error: *mut *mut libc::c_void,
    ) -> libc::c_int;
}

#[link(name = "gobject-2.0")]
unsafe extern "C" {
    fn g_object_unref(object: *mut libc::c_void);
}

fn safe_name(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 160
        && value != "."
        && value != ".."
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"_.+-".contains(&byte))
}

fn data_roots() -> Vec<PathBuf> {
    let mut roots = Vec::new();
    if let Some(home) = std::env::var_os("XDG_DATA_HOME") {
        let path = PathBuf::from(home);
        if path.is_absolute() {
            roots.push(path);
        }
    }
    if roots.is_empty() {
        if let Some(home) = std::env::var_os("HOME") {
            roots.push(PathBuf::from(home).join(".local/share"));
        }
    }
    let system =
        std::env::var("XDG_DATA_DIRS").unwrap_or_else(|_| "/usr/local/share:/usr/share".into());
    roots.extend(
        system
            .split(':')
            .filter(|part| !part.is_empty())
            .map(PathBuf::from)
            .filter(|path| path.is_absolute())
            .take(MAX_ROOTS - roots.len()),
    );
    roots
}

fn usable(path: &Path) -> bool {
    fs::metadata(path)
        .is_ok_and(|meta| meta.is_file() && meta.len() > 0 && meta.len() <= FILE_LIMIT)
}

fn try_file(directory: &Path, name: &str) -> Option<PathBuf> {
    ["png", "svg"]
        .into_iter()
        .map(|ext| directory.join(format!("{name}.{ext}")))
        .find(|path| usable(path))
}

fn score(index: &KeyFile, directory: &str, wanted: i32) -> i32 {
    let size = index.integer(directory, "Size").unwrap_or(0);
    let scale = index.integer(directory, "Scale").unwrap_or(1).max(1);
    if size <= 0 {
        return 1000;
    }
    if index.string(directory, "Type").ok().as_deref() == Some("Scalable") {
        let min = index.integer(directory, "MinSize").unwrap_or(size) * scale;
        let max = index.integer(directory, "MaxSize").unwrap_or(size) * scale;
        if wanted < min {
            min - wanted
        } else {
            (wanted - max).max(0)
        }
    } else {
        (size * scale - wanted).abs()
    }
}

fn theme_lookup(
    roots: &[PathBuf],
    theme: &str,
    name: &str,
    wanted: i32,
    depth: usize,
    visited: &mut Vec<String>,
) -> Option<PathBuf> {
    if depth >= MAX_DEPTH || !safe_name(theme) || visited.iter().any(|item| item == theme) {
        return None;
    }
    visited.push(theme.into());
    let mut inherits = Vec::new();
    for root in roots {
        let base = root.join("icons").join(theme);
        let index = KeyFile::new();
        index.set_list_separator(b','.into());
        let index_path = base.join("index.theme");
        if fs::metadata(&index_path).is_ok_and(|meta| meta.is_file() && meta.len() <= INDEX_LIMIT)
            && index.load_from_file(index_path, KeyFileFlags::NONE).is_ok()
        {
            if inherits.is_empty() {
                inherits = index
                    .string_list("Icon Theme", "Inherits")
                    .map(|list| list.iter().take(8).map(ToString::to_string).collect())
                    .unwrap_or_default();
            }
            let mut directories = index
                .string_list("Icon Theme", "Directories")
                .map(|list| list.iter().map(ToString::to_string).collect::<Vec<_>>())
                .unwrap_or_default();
            if let Ok(scaled) = index.string_list("Icon Theme", "ScaledDirectories") {
                directories.extend(scaled.iter().map(ToString::to_string));
            }
            if !directories.is_empty() {
                let mut candidates = directories
                    .iter()
                    .take(MAX_DIRS)
                    .filter(|directory| {
                        !directory.starts_with('/')
                            && directory
                                .split('/')
                                .all(|part| safe_name(part) && part != "..")
                    })
                    .filter_map(|directory| {
                        let path = try_file(&base.join(directory.as_str()), name)?;
                        Some((score(&index, directory, wanted), path))
                    })
                    .collect::<Vec<_>>();
                candidates.sort_by_key(|(score, _)| *score);
                if let Some((_, path)) = candidates.into_iter().next() {
                    return Some(path);
                }
            }
        }
        for size in [
            format!("{wanted}x{wanted}"),
            "48x48".into(),
            "64x64".into(),
            "32x32".into(),
            "24x24".into(),
            "128x128".into(),
            "256x256".into(),
            "scalable".into(),
            "16x16".into(),
        ] {
            if let Some(path) = try_file(&base.join(size).join("apps"), name) {
                return Some(path);
            }
        }
    }
    for inherited in inherits {
        if let Some(path) = theme_lookup(roots, &inherited, name, wanted, depth + 1, visited) {
            return Some(path);
        }
    }
    None
}

fn resolve(icon: &str, theme: &str, wanted: i32, roots: &[PathBuf]) -> Option<PathBuf> {
    let parsed = gio::Icon::for_string(icon).ok()?;
    if let Some(file) = parsed.downcast_ref::<gio::FileIcon>() {
        let path = file.file().path()?;
        return (path.is_absolute() && usable(&path)).then_some(path);
    }
    let themed = parsed.downcast_ref::<gio::ThemedIcon>()?;
    for name in themed.names().iter().take(16) {
        if !safe_name(name) {
            continue;
        }
        let mut visited = Vec::new();
        if let Some(path) = theme_lookup(roots, theme, name, wanted, 0, &mut visited) {
            return Some(path);
        }
        let mut visited = Vec::new();
        if theme != "hicolor" {
            if let Some(path) = theme_lookup(roots, "hicolor", name, wanted, 0, &mut visited) {
                return Some(path);
            }
        }
        for root in roots {
            if let Some(path) = try_file(&root.join("pixmaps"), name) {
                return Some(path);
            }
        }
    }
    None
}

fn decode(path: &Path, size: i32) -> Option<ImageSurface> {
    if !usable(path) || !(16..=192).contains(&size) {
        return None;
    }
    let output = ImageSurface::create(Format::ARgb32, size, size).ok()?;
    let cr = Context::new(&output).ok()?;
    let ok = match path.extension().and_then(|part| part.to_str()) {
        Some("svg") => {
            let path = CString::new(path.as_os_str().as_bytes()).ok()?;
            let handle = unsafe { rsvg_handle_new_from_file(path.as_ptr(), std::ptr::null_mut()) };
            if handle.is_null() {
                false
            } else {
                let viewport = RsvgRectangle {
                    x: 0.0,
                    y: 0.0,
                    width: size.into(),
                    height: size.into(),
                };
                let rendered = unsafe {
                    rsvg_handle_render_document(
                        handle,
                        cr.to_raw_none().cast(),
                        &viewport,
                        std::ptr::null_mut(),
                    ) != 0
                };
                unsafe { g_object_unref(handle) };
                rendered
            }
        }
        Some("png") => {
            let mut file = File::open(path).ok()?;
            let mut header = [0u8; 24];
            file.read_exact(&mut header).ok()?;
            if &header[..8] != b"\x89PNG\r\n\x1a\n" || &header[12..16] != b"IHDR" {
                return None;
            }
            let width = u32::from_be_bytes(header[16..20].try_into().ok()?);
            let height = u32::from_be_bytes(header[20..24].try_into().ok()?);
            if width == 0 || height == 0 || width > 4096 || height > 4096 {
                return None;
            }
            let source = ImageSurface::create_from_png(&mut File::open(path).ok()?).ok()?;
            let scale = (size as f64 / f64::from(width)).min(size as f64 / f64::from(height));
            cr.translate(
                (size as f64 - f64::from(width) * scale) / 2.0,
                (size as f64 - f64::from(height) * scale) / 2.0,
            );
            cr.scale(scale, scale);
            cr.set_source_surface(&source, 0.0, 0.0).ok()?;
            cr.paint().is_ok()
        }
        _ => false,
    };
    drop(cr);
    ok.then_some(output)
}

pub struct IconCache {
    theme: String,
    roots: Vec<PathBuf>,
    entries: Vec<(String, Option<ImageSurface>)>,
    decode_count: u64,
}

impl IconCache {
    pub fn new() -> Self {
        Self {
            theme: std::env::var("K230_ICON_THEME")
                .ok()
                .filter(|name| safe_name(name))
                .unwrap_or_else(|| "hicolor".into()),
            roots: data_roots(),
            entries: Vec::new(),
            decode_count: 0,
        }
    }

    pub fn set_theme(&mut self, name: &str) {
        let accepted = if safe_name(name) { name } else { "hicolor" };
        self.theme = accepted.into();
        self.roots = data_roots();
        self.entries.clear();
    }

    pub fn decode_count(&self) -> u64 {
        self.decode_count
    }
    pub fn cache_count(&self) -> usize {
        self.entries.len()
    }

    #[cfg(test)]
    pub(crate) fn use_fixture_root(&mut self, root: PathBuf) {
        self.roots = vec![root];
        self.entries.clear();
    }

    pub fn paint(&mut self, cr: &Context, icon: &str, size: i32, x: f64, y: f64) -> bool {
        let key = format!("{size}:{icon}");
        if let Some(index) = self.entries.iter().position(|(entry, _)| entry == &key) {
            let item = self.entries.remove(index);
            self.entries.push(item);
        } else {
            let surface =
                resolve(icon, &self.theme, size, &self.roots).and_then(|path| decode(&path, size));
            if surface.is_some() {
                self.decode_count += 1;
            }
            if self.entries.len() == CACHE_LIMIT {
                self.entries.remove(0);
            }
            self.entries.push((key, surface));
        }
        let Some((_, Some(surface))) = self.entries.last() else {
            return false;
        };
        cr.set_source_surface(surface, x, y).is_ok() && cr.paint().is_ok()
    }
}

impl Default for IconCache {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_and_bounds() {
        assert!(safe_name("foot"));
        assert!(!safe_name("../x"));
        assert!(!safe_name("a/b"));
        let mut cache = IconCache::new();
        cache.set_theme("../../bad");
        assert_eq!(cache.theme, "hicolor");
        let default = IconCache::default();
        assert!(!default.theme.is_empty());
        assert!(!default.roots.is_empty());
    }

    /// The launch splash asks for a 176px icon (`render::SPLASH_ICON_SIZE`)
    /// -- above the drawer/Home era's 128px cap. Bumping `decode`'s bound
    /// to admit it (while still rejecting an unreasonably large request)
    /// is the one behavior change this feature makes to this module.
    #[test]
    fn decode_admits_the_larger_splash_icon_size_but_still_bounds_it() {
        let root = std::env::temp_dir().join(format!(
            "k230-rust-icon-splash-size-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let apps = root.join("icons/hicolor/scalable/apps");
        fs::create_dir_all(&apps).unwrap();
        fs::write(
            apps.join("foot.svg"),
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"48\" height=\"48\"><rect width=\"48\" height=\"48\" fill=\"#e85631\"/></svg>",
        )
        .unwrap();
        let mut cache = IconCache::new();
        cache.set_theme("hicolor");
        cache.use_fixture_root(root.clone());
        let target = ImageSurface::create(Format::ARgb32, 176, 176).unwrap();
        let cr = Context::new(&target).unwrap();
        assert!(cache.paint(&cr, "foot", 176, 0.0, 0.0));
        drop(cr);
        assert!(decode(&apps.join("foot.svg"), 500).is_none());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn theme_inheritance_svg_decode_and_bounded_cache() {
        let root = std::env::temp_dir().join(format!(
            "k230-rust-icons-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let primary = root.join("icons/custom");
        let inherited = root.join("icons/hicolor/scalable/apps");
        fs::create_dir_all(&primary).unwrap();
        fs::create_dir_all(&inherited).unwrap();
        fs::write(primary.join("index.theme"), "[Icon Theme]\nName=custom\nDirectories=scalable/apps\nInherits=hicolor\n[scalable/apps]\nSize=48\nType=Scalable\nMinSize=16\nMaxSize=128\n").unwrap();
        fs::write(inherited.join("foot.svg"), "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"48\" height=\"48\"><rect width=\"48\" height=\"48\" fill=\"#e85631\"/></svg>").unwrap();
        let mut cache = IconCache::new();
        cache.set_theme("custom");
        cache.roots = vec![root.clone()];
        let target = ImageSurface::create(Format::ARgb32, 64, 64).unwrap();
        let cr = Context::new(&target).unwrap();
        assert!(cache.paint(&cr, "foot", 48, 0.0, 0.0));
        assert_eq!(cache.decode_count(), 1);
        assert!(cache.paint(&cr, "foot", 48, 0.0, 0.0));
        assert_eq!(cache.decode_count(), 1);
        assert_eq!(cache.cache_count(), 1);
        cache.set_theme("custom");
        cache.roots = vec![root.clone()];
        assert_eq!(cache.cache_count(), 0);
        assert!(cache.paint(&cr, "foot", 48, 0.0, 0.0));
        assert_eq!(cache.decode_count(), 2);
        cache.set_theme("hicolor");
        cache.roots = vec![root.clone()];
        assert_eq!(cache.cache_count(), 0);
        assert!(cache.paint(&cr, "foot", 48, 0.0, 0.0));
        assert_eq!(cache.decode_count(), 3);
        drop(cr);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn comma_lists_reach_second_inherited_theme_and_later_directory() {
        let root = std::env::temp_dir().join(format!(
            "k230-rust-icon-list-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let custom = root.join("icons/custom");
        let second = root.join("icons/second");
        fs::create_dir_all(&custom).unwrap();
        fs::create_dir_all(second.join("scalable/apps")).unwrap();
        fs::create_dir_all(second.join("scaled/apps")).unwrap();
        fs::write(custom.join("index.theme"), "[Icon Theme]\nName=custom\nDirectories=unused/apps,missing/apps\nInherits=first,second\n").unwrap();
        fs::write(second.join("index.theme"), "[Icon Theme]\nName=second\nDirectories=unused/apps,scalable/apps\nScaledDirectories=scaled/apps\n[scalable/apps]\nSize=48\nType=Scalable\nMinSize=16\nMaxSize=128\n[scaled/apps]\nSize=48\nScale=1\nType=Scalable\nMinSize=16\nMaxSize=128\n").unwrap();
        let svg = "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"48\" height=\"48\"><rect width=\"48\" height=\"48\" fill=\"#e85631\"/></svg>";
        fs::write(second.join("scalable/apps/foot.svg"), svg).unwrap();
        fs::write(second.join("scaled/apps/scaled.svg"), svg).unwrap();
        assert_eq!(
            resolve("foot", "custom", 48, std::slice::from_ref(&root)),
            Some(second.join("scalable/apps/foot.svg"))
        );
        assert_eq!(
            resolve("scaled", "custom", 48, std::slice::from_ref(&root)),
            Some(second.join("scaled/apps/scaled.svg"))
        );
        fs::remove_dir_all(root).unwrap();
    }
}

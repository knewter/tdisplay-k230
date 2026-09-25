//! Bounded carousel-slice thumbnails for the touch theme chooser.
//!
//! Mirrors Omarchy's per-theme `preview.png` convention (or, when a theme
//! ships none, a representative background image chosen by
//! `tools/theme_catalog.py`) as the photo drawn on each carousel slice
//! (`theme_carousel.rs`), for both the theme carousel and a theme's
//! background carousel. Decoding runs off the Wayland dispatch thread and
//! is cached per opaque id (a theme id or a background id) for the life of
//! the chooser: none of this art changes while the chooser is open, so a
//! decoded bitmap is kept rather than re-requested on every drag frame.
//!
//! Quattro's own slices are two different aspect ratios -- the expanded
//! centered slice is a wide landscape crop, a side slice is a narrow tall
//! strip -- and a slice's *blended* size changes every frame while
//! dragging. Re-cropping the source image at the exact blended aspect each
//! frame is exactly the "needlessly expensive per-frame transform" this
//! change is told to avoid on the K230's software (Pixman/Cairo) renderer.
//! Instead, each catalog id gets exactly two cached bitmaps -- one already
//! cropped to [`Variant::Expanded`]'s aspect, one to [`Variant::Slice`]'s --
//! and the renderer picks whichever is closer to a slice's current blend
//! and scales it onto the slice with a Cairo matrix, never a fresh decode.
//! Both endpoints of a drag are pixel-exact; a few frames near the halfway
//! point of a transition use the "wrong" aspect's crop, scaled -- a
//! deliberate, cheap tradeoff, not a decode-time approximation.
//!
//! ## Two geometries, so two sizes per variant
//!
//! `theme_carousel.rs` now sizes the Themes page's hero carousel and the
//! Preview page's background carousel independently
//! (`theme_carousel::{THEME_GEOMETRY, BACKGROUND_GEOMETRY}`), rather than
//! one shared set of constants. A theme id is only ever drawn on the theme
//! carousel and a background id only ever on the background carousel (the
//! two id spaces never collide -- see `ThumbnailKey::id`'s own doc), so
//! nothing here needs to know which geometry produced a given request, but
//! the two carousels' `Expanded` bitmaps are no longer the same pixel size.
//! `ThumbnailKey` therefore carries its own explicit `width`/`height`
//! (the caller's job to fill in from whichever geometry it is painting,
//! mirroring `theme_ui::ThemeImageKey`'s own explicit dimensions) rather
//! than `Variant` mapping to one fixed size.

use crate::background_decode::{BackgroundCache, FitMode};
use cairo::{Format, ImageSurface};
use sha2::{Digest, Sha256};
use std::{
    collections::{HashMap, HashSet, VecDeque},
    fs::OpenOptions,
    io::{Read, Write},
    os::unix::fs::OpenOptionsExt,
    path::{Path, PathBuf},
    sync::mpsc::{self, Receiver, SyncSender},
    thread,
};

/// ## Two disk caches, ahead of the in-memory `ThemeThumbnailCache` above
///
/// Beyond the in-memory cache (bounded, cleared when the chooser process
/// exits), two on-disk mechanisms make a *first* view of a given (source,
/// size) fast too, not just a second view within one run. Both are keyed
/// identically -- the source file's own content hash plus variant/size (see
/// [`hashed_cache_file`]) -- rather than by source *path*:
///
/// - **Build-time seed, for the bundled built-in themes.** `nix/handheld-
///   theme-default/default.nix` runs this same binary's hidden
///   `--write-thumbnail-cache` verb over every pinned theme's `preview.png`
///   and background images, at exactly the sizes `theme_carousel`'s two
///   geometries need, into a read-only directory shipped inside the
///   package (`share/omarchy/thumbs-by-hash/`, wired to this process via
///   `K230_THEME_THUMBNAIL_SEED` -- see [`builtin_seed_dir`]). Checked
///   first, never written to at runtime; the Nix store's own garbage
///   collection owns its lifetime.
/// - **Runtime, for everything else (chiefly user themes, and any seed
///   miss).** A small, size-bounded cache under the shell user's
///   `$XDG_CACHE_HOME` (see [`disk_cache_dir`]): the first view in the
///   *worker* thread (never the render thread -- this module's whole
///   point, see the module doc) pays a full decode and persists the
///   result; a later view, even after a restart, loads the small
///   already-cropped file directly.
///
/// **Why content hash, not source path.** An earlier version of the
/// build-time seed looked a precomputed thumbnail up by mirroring the
/// source's own path (`share/omarchy/themes/<name>/<rest>` ->
/// `share/omarchy/thumbs/<name>/<rest>`). That broke the moment a theme was
/// actually *used*: `tools/theme_activate.py::prepare` stages a byte-for-
/// byte copy of a theme's background under `~/.local/state/omarchy/current/
/// generations/<gen>/theme/<rest>` before the chooser ever sees its path,
/// and the Rust client only ever decodes that staged copy -- which has no
/// `themes` path component to mirror, so the precomputed file was silently
/// never found and every first view paid for a full 4K decode anyway (a
/// real gap the board caught: 16s and 40 commits for a background carousel
/// that should have been instant). A staged copy's *bytes* are identical to
/// the pinned source's, though (`checked_copy` never re-encodes), so
/// content-hash keying finds the same precomputed entry regardless of which
/// of the two paths -- or any future third one -- asked for it.
///
/// Both are strictly advisory: a missing, unreadable, or geometry-mismatched
/// file of either kind is exactly the same, slower, fully correct full
/// decode this cache didn't exist to skip.
const DISK_CACHE_MAGIC: &[u8; 8] = b"K230THC1";
/// 8 (magic) + 4 (width) + 4 (height).
const DISK_CACHE_HEADER_LEN: u64 = 16;
/// Bounds the runtime on-disk cache's total footprint -- a small, fixed,
/// explicitly stated bound, the same engineering choice `CACHE_CAP` above
/// and `background_decode.rs`'s own cache make. Comparable to (slightly
/// above) this process's own in-memory bound, since the disk cache serves
/// every chooser session on this device, not just the current one.
const DISK_CACHE_MAX_BYTES: u64 = 24 * 1024 * 1024;
/// Source files larger than this are still decoded and shown normally, but
/// never content-hashed or persisted: hashing a large file just to persist
/// a small thumbnail of it spends more I/O than a single decode saves, and
/// the persistent win this cache exists for is *repeat* views across
/// restarts, not the very first one. Matches
/// `background_decode.rs::MAX_SOURCE_BYTES`.
const DISK_CACHE_MAX_SOURCE_BYTES: u64 = 32 * 1024 * 1024;

fn output_len(width: u32, height: u32) -> Option<u64> {
    u64::from(width)
        .checked_mul(u64::from(height))?
        .checked_mul(4)
}

/// Read a disk-cached thumbnail file if it exists and matches `width`/
/// `height` exactly. Any structural problem (wrong size, bad magic,
/// unreadable, a symlink) is a cache miss, never an error -- same
/// contract as `background_decode.rs::load_cached`.
fn read_disk_cache(path: &Path, width: u32, height: u32) -> Option<Vec<u8>> {
    let expected_pixels = output_len(width, height)?;
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)
        .ok()?;
    let metadata = file.metadata().ok()?;
    let expected_len = DISK_CACHE_HEADER_LEN.checked_add(expected_pixels)?;
    if !metadata.is_file() || metadata.len() != expected_len {
        return None;
    }
    let mut bytes = Vec::new();
    file.take(expected_len + 1).read_to_end(&mut bytes).ok()?;
    if bytes.len() as u64 != expected_len {
        return None;
    }
    if &bytes[0..8] != DISK_CACHE_MAGIC {
        return None;
    }
    let cached_width = u32::from_le_bytes(bytes[8..12].try_into().ok()?);
    let cached_height = u32::from_le_bytes(bytes[12..16].try_into().ok()?);
    if cached_width != width || cached_height != height {
        return None;
    }
    bytes.drain(0..DISK_CACHE_HEADER_LEN as usize);
    Some(bytes)
}

/// Write `pixels` as a disk-cache file at exactly `path`, via a sibling
/// temporary file and an atomic rename so a concurrent reader never sees a
/// partial file. The parent directory is created if missing. Advisory:
/// callers treat any failure as a missed optimization, never a hard error.
fn write_disk_cache(path: &Path, width: u32, height: u32, pixels: &[u8]) -> Result<(), String> {
    let expected = output_len(width, height).ok_or("thumbnail geometry overflow")?;
    if pixels.len() as u64 != expected {
        return Err("thumbnail cache payload size mismatch".into());
    }
    let parent = path.parent().ok_or("thumbnail cache path has no parent")?;
    std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    let temporary = parent.join(format!(".tmp-{}-{}", std::process::id(), fastrand_suffix()));
    let mut file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .custom_flags(libc::O_NOFOLLOW)
        .mode(0o600)
        .open(&temporary)
        .map_err(|error| error.to_string())?;
    file.write_all(DISK_CACHE_MAGIC)
        .and_then(|_| file.write_all(&width.to_le_bytes()))
        .and_then(|_| file.write_all(&height.to_le_bytes()))
        .and_then(|_| file.write_all(pixels))
        .and_then(|_| file.sync_all())
        .map_err(|error| error.to_string())?;
    drop(file);
    std::fs::rename(&temporary, path).map_err(|error| error.to_string())?;
    Ok(())
}

/// A cheap per-call disambiguator for the temporary write path -- this
/// process is single-threaded for thumbnail decodes (one worker thread),
/// but the PID alone would collide if a stale temp file from a killed
/// previous run were ever left behind at the same PID.
fn fastrand_suffix() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(0)
}

/// Evicts oldest-modified files under `dir` until its total size is back
/// under `DISK_CACHE_MAX_BYTES`. Called after every write; a directory this
/// small (a few dozen files at most) is cheap to scan fully each time, and
/// needs no separate index to go stale.
fn evict_oldest(dir: &Path) {
    evict_until(dir, DISK_CACHE_MAX_BYTES);
}

/// `evict_oldest`'s actual logic, parameterized on the cap so tests can
/// exercise real eviction behavior against a tiny cap instead of writing
/// tens of megabytes of fixture data to trigger it.
fn evict_until(dir: &Path, cap: u64) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    let mut files: Vec<(PathBuf, u64, std::time::SystemTime)> = entries
        .filter_map(Result::ok)
        .filter_map(|entry| {
            let metadata = entry.metadata().ok()?;
            if !metadata.is_file() {
                return None;
            }
            let modified = metadata.modified().ok()?;
            Some((entry.path(), metadata.len(), modified))
        })
        .collect();
    let mut total: u64 = files.iter().map(|(_, size, _)| *size).sum();
    if total <= cap {
        return;
    }
    files.sort_by_key(|(_, _, modified)| *modified);
    for (path, size, _) in files {
        if total <= cap {
            break;
        }
        if std::fs::remove_file(&path).is_ok() {
            total = total.saturating_sub(size);
        }
    }
}

/// `$XDG_CACHE_HOME/k230-shell/thumbs`, or `$HOME/.cache/k230-shell/thumbs`
/// when `XDG_CACHE_HOME` is unset or empty. `None` when neither is
/// available (e.g. a stripped test environment): callers simply skip the
/// runtime disk cache in that case, exactly as if every lookup missed.
fn disk_cache_dir() -> Option<PathBuf> {
    disk_cache_dir_from(
        std::env::var("XDG_CACHE_HOME").ok().as_deref(),
        std::env::var("HOME").ok().as_deref(),
    )
}

/// `disk_cache_dir`'s actual logic, taking its two env var readings as
/// plain arguments so tests can exercise the XDG/HOME fallback without
/// mutating real process-wide environment state (`std::env::set_var` is
/// unsound across concurrently running tests in one process).
fn disk_cache_dir_from(xdg_cache_home: Option<&str>, home: Option<&str>) -> Option<PathBuf> {
    if let Some(dir) = xdg_cache_home {
        if !dir.trim().is_empty() {
            return Some(PathBuf::from(dir).join("k230-shell/thumbs"));
        }
    }
    let home = home?;
    if home.trim().is_empty() {
        return None;
    }
    Some(PathBuf::from(home).join(".cache/k230-shell/thumbs"))
}

/// Content hash of `path`'s current bytes, hex-encoded, or `None` if the
/// file is missing, not a regular file, or larger than
/// `DISK_CACHE_MAX_SOURCE_BYTES` (see its own doc).
fn content_hash(path: &Path) -> Option<String> {
    let metadata = std::fs::metadata(path).ok()?;
    if !metadata.is_file() || metadata.len() > DISK_CACHE_MAX_SOURCE_BYTES {
        return None;
    }
    let bytes = std::fs::read(path).ok()?;
    let mut hasher = Sha256::new();
    hasher.update(&bytes);
    Some(format!("{:x}", hasher.finalize()))
}

/// The on-disk filename for a given content hash/variant/size, shared by
/// both the read-only build-time seed and the writable runtime cache --
/// they are the same key format at two different roots (see the module
/// doc's "Two disk caches" section). The full hash (not a path or stem)
/// makes collisions a non-concern.
fn hashed_cache_file(dir: &Path, hash: &str, variant: Variant, width: u32, height: u32) -> PathBuf {
    dir.join(format!("{hash}-{}-{width}x{height}.rgba", variant.tag()))
}

/// `$K230_THEME_THUMBNAIL_SEED`, if set and non-empty: the read-only,
/// build-time-populated seed directory `nix/handheld-theme-default` ships
/// (wired to this process by `nix/shell.nix`, mirroring how
/// `K230_THEME_DEFAULT_GENERATION` is wired). `None` when unset -- exactly
/// as if every seed lookup missed, falling straight through to the runtime
/// disk cache.
fn builtin_seed_dir() -> Option<PathBuf> {
    builtin_seed_dir_from(std::env::var("K230_THEME_THUMBNAIL_SEED").ok().as_deref())
}

/// `builtin_seed_dir`'s actual logic, taking its env var reading as a plain
/// argument (see `disk_cache_dir_from`'s own doc for why).
fn builtin_seed_dir_from(value: Option<&str>) -> Option<PathBuf> {
    let value = value?;
    if value.trim().is_empty() {
        return None;
    }
    Some(PathBuf::from(value))
}

/// Precomputes and persists a build-time thumbnail for `source` at
/// `variant`/`width`/`height` into `dest_dir` (the seed directory
/// `nix/handheld-theme-default/default.nix` builds and ships -- see the
/// module doc's "Two disk caches" section), keyed by `source`'s own content
/// hash so a later lookup finds it regardless of which path -- the pinned
/// Nix store source, or a staged generation's byte-identical copy -- asked.
/// Used only by the hidden `--write-thumbnail-cache` CLI verb, invoked by a
/// native-arch build of this binary from `nix/handheld-theme-default/
/// default.nix` (the same pattern as
/// `background_decode::write_wallpaper_cache`). Never runs on the board.
pub fn write_builtin_thumbnail(
    source: &Path,
    dest_dir: &Path,
    variant: Variant,
    width: u32,
    height: u32,
) -> Result<(), String> {
    let hash = content_hash(source).ok_or("source unreadable or exceeds the size bound")?;
    let destination = hashed_cache_file(dest_dir, &hash, variant, width, height);
    let mut cache = BackgroundCache::new();
    let pixels = cache
        .render(source, None, width, height, FitMode::Crop)?
        .to_vec();
    write_disk_cache(&destination, width, height, &pixels)
}

/// Resolves one thumbnail decode, preferring (in order) a build-time seed
/// hit, then a runtime disk-cache hit, before paying for a full decode --
/// and, on a full decode, persists the result to the runtime disk cache for
/// the next view (this run or a later restart; never to the read-only
/// seed). See the module doc's "Two disk caches" section.
fn resolve(cache: &mut BackgroundCache, key: &ThumbnailKey) -> Result<Vec<u8>, String> {
    resolve_with_dirs(cache, key, builtin_seed_dir(), disk_cache_dir())
}

/// `resolve`'s actual logic, taking both cache directories as plain
/// arguments (see `disk_cache_dir_from`'s own doc for why: tests exercise
/// this directly with fixture directories rather than mutating
/// process-wide environment state).
fn resolve_with_dirs(
    cache: &mut BackgroundCache,
    key: &ThumbnailKey,
    seed_dir: Option<PathBuf>,
    runtime_dir: Option<PathBuf>,
) -> Result<Vec<u8>, String> {
    let hash = if seed_dir.is_some() || runtime_dir.is_some() {
        content_hash(&key.path)
    } else {
        None
    };
    if let (Some(dir), Some(hash)) = (seed_dir.as_ref(), hash.as_ref()) {
        let file = hashed_cache_file(dir, hash, key.variant, key.width, key.height);
        if let Some(pixels) = read_disk_cache(&file, key.width, key.height) {
            return Ok(pixels);
        }
    }
    if let (Some(dir), Some(hash)) = (runtime_dir.as_ref(), hash.as_ref()) {
        let file = hashed_cache_file(dir, hash, key.variant, key.width, key.height);
        if let Some(pixels) = read_disk_cache(&file, key.width, key.height) {
            return Ok(pixels);
        }
    }
    let pixels = cache
        .render(&key.path, None, key.width, key.height, FitMode::Crop)?
        .to_vec();
    if let (Some(dir), Some(hash)) = (runtime_dir.as_ref(), hash.as_ref()) {
        let file = hashed_cache_file(dir, hash, key.variant, key.width, key.height);
        if write_disk_cache(&file, key.width, key.height, &pixels).is_ok() {
            evict_oldest(dir);
        }
    }
    Ok(pixels)
}

/// Which cache slot a bitmap belongs to for a given catalog id -- the wide
/// centered crop, or the narrow collapsed-slice crop. The actual decode
/// target size is carried on `ThumbnailKey` itself (see the module doc),
/// since the two carousel contexts no longer share one fixed size per
/// variant.
#[derive(Clone, Copy, Debug, Eq, PartialEq, Hash)]
pub enum Variant {
    Expanded,
    Slice,
}

impl Variant {
    fn tag(self) -> &'static str {
        match self {
            Variant::Expanded => "expanded",
            Variant::Slice => "slice",
        }
    }
}

/// Bounds cache memory. The largest possible entry is now the Themes page
/// hero carousel's `Expanded` bitmap (`theme_carousel::THEME_GEOMETRY`:
/// `480*640*4` = 1,228,800 bytes, ~1.17 MiB) rather than the old shared
/// `300*186*4` (~218 KiB) -- a direct consequence of that carousel's
/// centered slice becoming the page's hero (see `theme_carousel.rs`'s
/// module doc). `NEARBY_LIMIT` (8, unchanged) means one fully-populated
/// carousel needs at most `(8*2+1)*2` = 34 entries (17 nearby ids, each an
/// `Expanded`+`Slice` pair); `CACHE_CAP` shrank from 48 to 36 -- just above
/// that steady-state need, not the old flat headroom -- so the *count* of
/// cached bitmaps offsets most of each bitmap's bigger footprint. Worst
/// realistic case (the hero carousel fully populated: 17 `Expanded` + 17
/// `Slice`) is `17*1,228,800 + 17*158,304` (`68*582*4`, the hero's own
/// `Slice` size) = 23,580,768 bytes, ~22.5 MiB -- up from the previous
/// ~10 MiB, still a small, fixed, and now explicitly stated bound. The
/// Preview page's background carousel is far smaller
/// (`theme_carousel::BACKGROUND_GEOMETRY`: `420*260*4` = 436,800 bytes per
/// `Expanded` entry), so browsing only ever there stays well under half
/// that figure.
const CACHE_CAP: usize = 36;
/// Concurrent in-flight decodes; bounds the worker's request channel.
const QUEUE: usize = 4;

#[derive(Clone, Debug, Eq, PartialEq, Hash)]
pub struct ThumbnailKey {
    /// Opaque catalog id: a theme id on the theme carousel, a background id
    /// on a theme's background carousel. The two id spaces never collide
    /// (both are 24-hex catalog identities minted by
    /// `tools/theme_catalog.py`'s `identity()` over disjoint inputs), so
    /// one cache safely serves both carousels.
    pub id: String,
    pub path: PathBuf,
    pub variant: Variant,
    /// The decode target size, chosen by the caller from whichever
    /// `CarouselGeometry` this (id, variant) belongs to (see the module
    /// doc): `geometry.expanded_w/expanded_h` for `Variant::Expanded`,
    /// `geometry.slice_w/slice_h` for `Variant::Slice`.
    pub width: u32,
    pub height: u32,
}

impl ThumbnailKey {
    fn cache_key(&self) -> String {
        format!("{}#{}", self.id, self.variant.tag())
    }
}

struct ThumbnailReply {
    key: ThumbnailKey,
    pixels: Result<Vec<u8>, String>,
}

struct ThumbnailWorker {
    requests: SyncSender<ThumbnailKey>,
    replies: Receiver<ThumbnailReply>,
}

impl Default for ThumbnailWorker {
    fn default() -> Self {
        let (requests, incoming) = mpsc::sync_channel::<ThumbnailKey>(QUEUE);
        let (outgoing, replies) = mpsc::sync_channel::<ThumbnailReply>(QUEUE);
        thread::spawn(move || {
            let mut cache = BackgroundCache::new();
            while let Ok(key) = incoming.recv() {
                let pixels = resolve(&mut cache, &key);
                if outgoing.send(ThumbnailReply { key, pixels }).is_err() {
                    break;
                }
            }
        });
        Self { requests, replies }
    }
}

#[derive(Default)]
pub struct ThemeThumbnailCache {
    worker: ThumbnailWorker,
    ready: HashMap<String, Option<ImageSurface>>,
    order: VecDeque<String>,
    in_flight: HashSet<String>,
}

impl ThemeThumbnailCache {
    /// The decoded bitmap for a catalog id's given variant, if one is ready
    /// and decoded without error.
    pub fn get(&self, id: &str, variant: Variant) -> Option<&ImageSurface> {
        self.ready
            .get(&format!("{id}#{}", variant.tag()))
            .and_then(Option::as_ref)
    }

    /// Whether this (id, variant) has finished decoding one way or the
    /// other -- successfully, or permanently as absent. `false` means a
    /// caller still needs to keep calling `request`/`poll` (or nothing ever
    /// asked for this pair): a dropped request (the worker's bounded queue
    /// was full) leaves it in neither map, and only another `request` call
    /// retries it, so a caller driving its own redraw loop from this can
    /// keep polling until every pair it cares about is actually resolved,
    /// rather than only while something else happens to be animating.
    pub fn is_resolved(&self, id: &str, variant: Variant) -> bool {
        self.ready.contains_key(&format!("{id}#{}", variant.tag()))
    }

    /// Requests a decode if this (id, variant) is not already cached or in
    /// flight. A full worker queue silently defers the request to a later
    /// call; callers request the whole visible/known slice set each poll,
    /// so a deferred entry is retried on the next frame.
    pub fn request(&mut self, key: ThumbnailKey) {
        let cache_key = key.cache_key();
        if self.ready.contains_key(&cache_key) || self.in_flight.contains(&cache_key) {
            return;
        }
        if self.worker.requests.try_send(key).is_ok() {
            self.in_flight.insert(cache_key);
        }
    }

    /// Drains completed decodes into the bounded cache. Returns true if any
    /// result arrived, so callers know to invalidate a painted scene.
    pub fn poll(&mut self) -> bool {
        let mut changed = false;
        while let Ok(reply) = self.worker.replies.try_recv() {
            let cache_key = reply.key.cache_key();
            self.in_flight.remove(&cache_key);
            let (width, height) = (reply.key.width, reply.key.height);
            let surface = reply.pixels.ok().and_then(|pixels| {
                ImageSurface::create_for_data(
                    pixels,
                    Format::ARgb32,
                    width as i32,
                    height as i32,
                    (width * 4) as i32,
                )
                .ok()
            });
            if !self.ready.contains_key(&cache_key) {
                self.order.push_back(cache_key.clone());
            }
            self.ready.insert(cache_key, surface);
            while self.order.len() > CACHE_CAP {
                if let Some(oldest) = self.order.pop_front() {
                    self.ready.remove(&oldest);
                }
            }
            changed = true;
        }
        changed
    }

    #[cfg(test)]
    pub fn known_len(&self) -> usize {
        self.ready.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decode_completes_and_is_cached_without_re_requesting() {
        let path = std::env::temp_dir().join(format!(
            "k230-theme-thumb-{}-{}.png",
            std::process::id(),
            std::thread::current().name().unwrap_or("test")
        ));
        image::RgbaImage::from_pixel(40, 40, image::Rgba([12, 200, 90, 255]))
            .save(&path)
            .unwrap();
        let path = path.canonicalize().unwrap();
        let mut cache = ThemeThumbnailCache::default();
        let key = ThumbnailKey {
            id: "fixture".into(),
            path: path.clone(),
            variant: Variant::Expanded,
            width: 480,
            height: 640,
        };
        cache.request(key.clone());
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while cache.get("fixture", Variant::Expanded).is_none() && std::time::Instant::now() < deadline
        {
            cache.poll();
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert!(cache.get("fixture", Variant::Expanded).is_some());
        assert_eq!(cache.known_len(), 1);
        // A second request for the same (id, variant) must not be
        // re-queued: dropping the source file would otherwise surface as a
        // decode failure on an unwanted re-decode.
        std::fs::remove_file(&path).unwrap();
        cache.request(key);
        assert!(cache.get("fixture", Variant::Expanded).is_some());
    }

    #[test]
    fn expanded_and_slice_variants_of_the_same_id_are_cached_distinctly() {
        let path = std::env::temp_dir().join(format!(
            "k230-theme-thumb-variants-{}.png",
            std::process::id()
        ));
        image::RgbaImage::from_pixel(80, 80, image::Rgba([90, 90, 200, 255]))
            .save(&path)
            .unwrap();
        let path = path.canonicalize().unwrap();
        let mut cache = ThemeThumbnailCache::default();
        cache.request(ThumbnailKey {
            id: "two-variants".into(),
            path: path.clone(),
            variant: Variant::Expanded,
            width: 480,
            height: 640,
        });
        cache.request(ThumbnailKey {
            id: "two-variants".into(),
            path: path.clone(),
            variant: Variant::Slice,
            width: 68,
            height: 582,
        });
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while cache.known_len() < 2 && std::time::Instant::now() < deadline {
            cache.poll();
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert_eq!(cache.known_len(), 2, "both variants cached separately");
        let expanded = cache.get("two-variants", Variant::Expanded).unwrap();
        let slice = cache.get("two-variants", Variant::Slice).unwrap();
        // Each bitmap is decoded at whichever explicit size the caller's
        // request carried -- the Themes hero carousel's sizes here -- not a
        // fixed size baked into `Variant` itself.
        assert_eq!((expanded.width(), expanded.height()), (480, 640));
        assert_eq!((slice.width(), slice.height()), (68, 582));
        std::fs::remove_file(&path).unwrap();
    }

    #[test]
    fn failed_decode_is_cached_as_absent_rather_than_retried_forever() {
        let mut cache = ThemeThumbnailCache::default();
        let key = ThumbnailKey {
            id: "missing".into(),
            path: PathBuf::from("/nonexistent/k230-theme-thumbnail-fixture.png"),
            variant: Variant::Slice,
            width: 68,
            height: 582,
        };
        cache.request(key);
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while cache.known_len() == 0 && std::time::Instant::now() < deadline {
            cache.poll();
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert_eq!(cache.known_len(), 1);
        assert!(cache.get("missing", Variant::Slice).is_none());
    }

    #[test]
    fn theme_and_background_ids_share_one_cache_without_colliding() {
        let theme_path = std::env::temp_dir().join(format!(
            "k230-theme-thumb-theme-{}.png",
            std::process::id()
        ));
        let background_path = std::env::temp_dir().join(format!(
            "k230-theme-thumb-background-{}.png",
            std::process::id()
        ));
        image::RgbaImage::from_pixel(20, 20, image::Rgba([200, 10, 10, 255]))
            .save(&theme_path)
            .unwrap();
        image::RgbaImage::from_pixel(20, 20, image::Rgba([10, 10, 200, 255]))
            .save(&background_path)
            .unwrap();
        let mut cache = ThemeThumbnailCache::default();
        cache.request(ThumbnailKey {
            id: "shared-id-space-a".into(),
            path: theme_path.canonicalize().unwrap(),
            variant: Variant::Expanded,
            width: 480,
            height: 640,
        });
        cache.request(ThumbnailKey {
            id: "shared-id-space-b".into(),
            path: background_path.canonicalize().unwrap(),
            variant: Variant::Slice,
            width: 59,
            height: 237,
        });
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while cache.known_len() < 2 && std::time::Instant::now() < deadline {
            cache.poll();
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert!(cache.get("shared-id-space-a", Variant::Expanded).is_some());
        assert!(cache.get("shared-id-space-b", Variant::Slice).is_some());
        std::fs::remove_file(&theme_path).unwrap();
        std::fs::remove_file(&background_path).unwrap();
    }

    fn temp_subdir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "k230-thumb-{name}-{}-{}",
            std::process::id(),
            fastrand_suffix()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn disk_cache_round_trips_and_rejects_mismatched_geometry() {
        let dir = temp_subdir("round-trip");
        let file = dir.join("entry.rgba");
        let pixels = vec![7u8; 4 * 5 * 4];
        write_disk_cache(&file, 4, 5, &pixels).unwrap();
        assert_eq!(read_disk_cache(&file, 4, 5), Some(pixels));
        assert_eq!(
            read_disk_cache(&file, 5, 4),
            None,
            "a size mismatch must be a cache miss, not stale/garbled pixels"
        );
        assert_eq!(read_disk_cache(&dir.join("missing.rgba"), 4, 5), None);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn evict_until_removes_oldest_files_first_until_back_under_the_cap() {
        let dir = temp_subdir("evict");
        let now = std::time::SystemTime::now();
        for (name, age_secs) in [("oldest", 30), ("middle", 20), ("newest", 10)] {
            let path = dir.join(name);
            std::fs::write(&path, vec![0u8; 10]).unwrap();
            let file = OpenOptions::new().write(true).open(&path).unwrap();
            file.set_modified(now - std::time::Duration::from_secs(age_secs))
                .unwrap();
        }
        // Three 10-byte files (30 bytes total) against a 25-byte cap: only
        // the single oldest file needs to go.
        evict_until(&dir, 25);
        let remaining: std::collections::HashSet<_> = std::fs::read_dir(&dir)
            .unwrap()
            .map(|entry| entry.unwrap().file_name().to_string_lossy().into_owned())
            .collect();
        assert_eq!(
            remaining,
            std::collections::HashSet::from(["middle".to_string(), "newest".to_string()]),
            "the oldest file is evicted first, newer ones are kept"
        );
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn resolve_prefers_a_precomputed_seed_thumbnail_over_a_fresh_decode() {
        // The source must stay present and unchanged (a content-hash key
        // can only be looked up by reading the source), so this is proven
        // the same way as the runtime-cache-hit test below: seed the file
        // with pixels a real decode of the source would never produce, and
        // confirm those exact seeded pixels come back rather than the
        // source's own, different content.
        let root = temp_subdir("builtin");
        let seed_dir = root.join("seed");
        let source = root.join("preview.png");
        image::RgbaImage::from_pixel(30, 30, image::Rgba([55, 66, 77, 255]))
            .save(&source)
            .unwrap();
        let source = source.canonicalize().unwrap();
        write_builtin_thumbnail(&source, &seed_dir, Variant::Expanded, 12, 16).unwrap();
        let hash = content_hash(&source).unwrap();
        let seed_file = hashed_cache_file(&seed_dir, &hash, Variant::Expanded, 12, 16);
        let precomputed = read_disk_cache(&seed_file, 12, 16).expect("precompute must write the seed file");
        // Overwrite the seed entry with distinctive pixels no decode of
        // `source` would ever produce, so a later hit is unambiguous.
        let distinctive = vec![250u8; 12 * 16 * 4];
        assert_ne!(precomputed, distinctive, "fixture must actually differ from a real decode");
        write_disk_cache(&seed_file, 12, 16, &distinctive).unwrap();

        let mut cache = BackgroundCache::new();
        let key = ThumbnailKey {
            id: "builtin-fixture".into(),
            path: source,
            variant: Variant::Expanded,
            width: 12,
            height: 16,
        };
        let pixels = resolve_with_dirs(&mut cache, &key, Some(seed_dir), None)
            .expect("a precomputed seed thumbnail must resolve");
        assert_eq!(
            pixels, distinctive,
            "the seed entry must be returned as-is, not overwritten by a fresh decode"
        );
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn resolve_finds_a_seed_thumbnail_for_a_staged_generation_copy_at_a_different_path() {
        // Regression test for the exact gap the coordinator's board run
        // caught: `tools/theme_activate.py::prepare` stages a byte-for-byte
        // copy of a theme's background under `~/.local/state/omarchy/
        // current/generations/<gen>/theme/backgrounds/...` (no `themes`
        // path component at all) before the chooser ever sees its path, so
        // a lookup keyed by source *path* can never find a precomputed
        // thumbnail built from the theme's original, differently-located
        // source. Content-hash keying must find it anyway, since the staged
        // copy's bytes are identical to the pinned source's.
        let root = temp_subdir("staged-regression");
        let pinned_source = root
            .join("share/omarchy/themes/fixture-theme/backgrounds")
            .join("1-fixture.webp");
        std::fs::create_dir_all(pinned_source.parent().unwrap()).unwrap();
        image::RgbaImage::from_pixel(40, 24, image::Rgba([10, 20, 30, 255]))
            .save(&pinned_source)
            .unwrap();
        let seed_dir = root.join("seed");
        write_builtin_thumbnail(&pinned_source, &seed_dir, Variant::Slice, 8, 10).unwrap();

        // A path shaped exactly like a real staged generation copy -- no
        // `themes` component anywhere in it -- holding the same bytes.
        let staged_copy = root
            .join(".local/state/omarchy/current/generations")
            .join("a".repeat(24))
            .join("theme/backgrounds/1-fixture.webp");
        std::fs::create_dir_all(staged_copy.parent().unwrap()).unwrap();
        std::fs::copy(&pinned_source, &staged_copy).unwrap();
        assert!(
            !staged_copy
                .components()
                .any(|c| c.as_os_str() == "themes"),
            "the fixture must actually exercise a path with no `themes` component"
        );

        let mut cache = BackgroundCache::new();
        let key = ThumbnailKey {
            id: "staged-fixture".into(),
            path: staged_copy.clone(),
            variant: Variant::Slice,
            width: 8,
            height: 10,
        };
        // Delete the pinned source (but keep the staged copy): only a
        // content-hash hit against the seed can still succeed from here.
        std::fs::remove_file(&pinned_source).unwrap();
        let pixels = resolve_with_dirs(&mut cache, &key, Some(seed_dir), None).expect(
            "a staged generation copy must still hit the seed thumbnail built from its pinned source",
        );
        assert_eq!(pixels.len(), 8 * 10 * 4);
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn resolve_persists_a_fresh_decode_to_the_runtime_disk_cache_for_next_time() {
        let cache_root = temp_subdir("runtime-cache-home");
        let source_dir = temp_subdir("runtime-cache-source");
        let source = source_dir.join("wallpaper.png");
        image::RgbaImage::from_pixel(25, 25, image::Rgba([1, 2, 3, 255]))
            .save(&source)
            .unwrap();
        let source = source.canonicalize().unwrap();
        let key = ThumbnailKey {
            id: "runtime-fixture".into(),
            path: source.clone(),
            variant: Variant::Slice,
            width: 10,
            height: 11,
        };
        let mut cache = BackgroundCache::new();
        let decoded = resolve_with_dirs(&mut cache, &key, None, Some(cache_root.clone()))
            .expect("first decode must succeed");
        let hash = content_hash(&source).unwrap();
        let cache_file = hashed_cache_file(&cache_root, &hash, Variant::Slice, 10, 11);
        assert_eq!(
            read_disk_cache(&cache_file, 10, 11),
            Some(decoded),
            "a fresh decode's exact pixels must be persisted to the runtime disk cache"
        );
        std::fs::remove_dir_all(&cache_root).unwrap();
        std::fs::remove_dir_all(&source_dir).unwrap();
    }

    #[test]
    fn resolve_prefers_an_existing_runtime_cache_hit_over_a_fresh_decode() {
        // The source stays present and unchanged throughout (a content-hash
        // key can only be looked up by reading the source, so unlike the
        // seed lookup above, this cache cannot be proven by deleting the
        // source). Instead: seed the cache file with pixels a real decode of
        // this source would never produce, then confirm `resolve_with_dirs`
        // returns exactly those seeded pixels rather than the source's
        // actual, different content -- proof the cache was read instead of
        // decoding.
        let cache_root = temp_subdir("runtime-cache-hit-home");
        let source_dir = temp_subdir("runtime-cache-hit-source");
        let source = source_dir.join("wallpaper.png");
        image::RgbaImage::from_pixel(25, 25, image::Rgba([9, 9, 9, 255]))
            .save(&source)
            .unwrap();
        let source = source.canonicalize().unwrap();
        let key = ThumbnailKey {
            id: "runtime-fixture-hit".into(),
            path: source.clone(),
            variant: Variant::Slice,
            width: 10,
            height: 11,
        };
        let hash = content_hash(&source).unwrap();
        let cache_file = hashed_cache_file(&cache_root, &hash, Variant::Slice, 10, 11);
        let seeded = vec![250u8; 10 * 11 * 4];
        write_disk_cache(&cache_file, 10, 11, &seeded).unwrap();
        let mut cache = BackgroundCache::new();
        let result = resolve_with_dirs(&mut cache, &key, None, Some(cache_root.clone()))
            .expect("a seeded runtime cache entry must resolve");
        assert_eq!(
            result, seeded,
            "an existing runtime cache entry must be returned as-is, not overwritten by a fresh decode"
        );
        std::fs::remove_dir_all(&cache_root).unwrap();
        std::fs::remove_dir_all(&source_dir).unwrap();
    }

    #[test]
    fn builtin_seed_dir_ignores_an_unset_or_empty_env_var() {
        assert_eq!(builtin_seed_dir_from(None), None);
        assert_eq!(builtin_seed_dir_from(Some("")), None);
        assert_eq!(builtin_seed_dir_from(Some("   ")), None);
        assert_eq!(
            builtin_seed_dir_from(Some("/nix/store/xyz-handheld-theme-default/share/omarchy/thumbs-by-hash")),
            Some(PathBuf::from(
                "/nix/store/xyz-handheld-theme-default/share/omarchy/thumbs-by-hash"
            ))
        );
    }

    #[test]
    fn resolve_prefers_a_seed_hit_over_a_runtime_cache_hit_when_both_exist() {
        // Seed is read-only and shipped by Nix; if a runtime-cache entry
        // ever also exists for the same key (e.g. left over from before a
        // theme got its own seed), the seed still wins -- it is checked
        // first, and never overwritten.
        let root = temp_subdir("seed-precedence");
        let source = root.join("bg.png");
        image::RgbaImage::from_pixel(20, 20, image::Rgba([1, 1, 1, 255]))
            .save(&source)
            .unwrap();
        let source = source.canonicalize().unwrap();
        let hash = content_hash(&source).unwrap();

        let seed_dir = root.join("seed");
        let seeded = vec![7u8; 6 * 6 * 4];
        write_disk_cache(
            &hashed_cache_file(&seed_dir, &hash, Variant::Expanded, 6, 6),
            6,
            6,
            &seeded,
        )
        .unwrap();
        let runtime_dir = root.join("runtime");
        let runtime_seeded = vec![9u8; 6 * 6 * 4];
        write_disk_cache(
            &hashed_cache_file(&runtime_dir, &hash, Variant::Expanded, 6, 6),
            6,
            6,
            &runtime_seeded,
        )
        .unwrap();

        let mut cache = BackgroundCache::new();
        let key = ThumbnailKey {
            id: "precedence-fixture".into(),
            path: source,
            variant: Variant::Expanded,
            width: 6,
            height: 6,
        };
        let result =
            resolve_with_dirs(&mut cache, &key, Some(seed_dir), Some(runtime_dir)).unwrap();
        assert_eq!(result, seeded, "the seed entry must win over a runtime-cache entry");
        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn disk_cache_dir_prefers_xdg_cache_home_then_falls_back_to_home_then_none() {
        assert_eq!(
            disk_cache_dir_from(Some("/xdg"), Some("/home/user")),
            Some(PathBuf::from("/xdg/k230-shell/thumbs"))
        );
        assert_eq!(
            disk_cache_dir_from(None, Some("/home/user")),
            Some(PathBuf::from("/home/user/.cache/k230-shell/thumbs"))
        );
        assert_eq!(
            disk_cache_dir_from(Some(""), Some("/home/user")),
            Some(PathBuf::from("/home/user/.cache/k230-shell/thumbs")),
            "an empty XDG_CACHE_HOME must fall back to HOME, not join an empty path"
        );
        assert_eq!(disk_cache_dir_from(None, None), None);
        assert_eq!(disk_cache_dir_from(Some(""), Some("")), None);
    }
}

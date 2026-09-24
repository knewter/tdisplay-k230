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
use std::{
    collections::{HashMap, HashSet, VecDeque},
    path::PathBuf,
    sync::mpsc::{self, Receiver, SyncSender},
    thread,
};

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
                let (width, height) = (key.width, key.height);
                let pixels = cache
                    .render(&key.path, None, width, height, FitMode::Crop)
                    .map(<[u8]>::to_vec);
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
}

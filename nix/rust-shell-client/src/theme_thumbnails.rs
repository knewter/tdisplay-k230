//! Bounded small-image thumbnails for the touch theme chooser.
//!
//! Mirrors Omarchy's per-theme `preview.png` convention (or, when a theme
//! ships none, a representative background image chosen by
//! `tools/theme_catalog.py`) as a small thumbnail beside each theme row on
//! the list page, and reuses the same bounded decode/cache for each
//! background's own row on the preview page. Decoding runs off the Wayland
//! dispatch thread and is cached per opaque id (a theme id or a background
//! id) for the life of the chooser: unlike the single live wallpaper
//! preview on the Preview page, none of this art changes while the chooser
//! is open, so a decoded thumbnail is kept rather than re-requested on
//! every scroll frame.

use crate::background_decode::{BackgroundCache, FitMode};
use cairo::{Format, ImageSurface};
use std::{
    collections::{HashMap, HashSet, VecDeque},
    path::PathBuf,
    sync::mpsc::{self, Receiver, SyncSender},
    thread,
};

/// Square crop side. The shortest chooser row (a Preview-page background,
/// 70px tall) leaves comfortable padding above/below at this size.
pub const THUMBNAIL_SIZE: u32 = 64;
/// Bounds cache memory: each entry is at most `THUMBNAIL_SIZE^2 * 4` bytes
/// (16 KiB at the current size). 128 entries (2 MiB at the generous end)
/// comfortably covers the 22-theme built-in catalog, any realistic number
/// of user themes, and a session that has opened several themes' background
/// pages in turn.
const CACHE_CAP: usize = 128;
/// Concurrent in-flight decodes; bounds the worker's request channel.
const QUEUE: usize = 4;

#[derive(Clone, Debug, Eq, PartialEq, Hash)]
pub struct ThumbnailKey {
    /// Opaque catalog id: a theme id on the list page, a background id on
    /// the preview page. The two id spaces never collide (both are 24-hex
    /// catalog identities minted by `tools/theme_catalog.py`'s `identity()`
    /// over disjoint inputs), so one cache safely serves both rows.
    pub id: String,
    pub path: PathBuf,
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
                let pixels = cache
                    .render(&key.path, THUMBNAIL_SIZE, THUMBNAIL_SIZE, FitMode::Crop)
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
    /// The decoded thumbnail for a catalog id, if one is ready and decoded
    /// without error.
    pub fn get(&self, id: &str) -> Option<&ImageSurface> {
        self.ready.get(id).and_then(Option::as_ref)
    }

    /// Requests a decode if this id is not already cached or in flight. A
    /// full worker queue silently defers the request to a later call;
    /// callers request the whole visible/known row set each poll, so a
    /// deferred entry is retried on the next frame.
    pub fn request(&mut self, key: ThumbnailKey) {
        if self.ready.contains_key(&key.id) || self.in_flight.contains(&key.id) {
            return;
        }
        if self.worker.requests.try_send(key.clone()).is_ok() {
            self.in_flight.insert(key.id);
        }
    }

    /// Drains completed decodes into the bounded cache. Returns true if any
    /// result arrived, so callers know to invalidate a painted scene.
    pub fn poll(&mut self) -> bool {
        let mut changed = false;
        while let Ok(reply) = self.worker.replies.try_recv() {
            self.in_flight.remove(&reply.key.id);
            let surface = reply.pixels.ok().and_then(|pixels| {
                ImageSurface::create_for_data(
                    pixels,
                    Format::ARgb32,
                    THUMBNAIL_SIZE as i32,
                    THUMBNAIL_SIZE as i32,
                    (THUMBNAIL_SIZE * 4) as i32,
                )
                .ok()
            });
            if !self.ready.contains_key(&reply.key.id) {
                self.order.push_back(reply.key.id.clone());
            }
            self.ready.insert(reply.key.id, surface);
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
        };
        cache.request(key.clone());
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while cache.get("fixture").is_none() && std::time::Instant::now() < deadline {
            cache.poll();
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert!(cache.get("fixture").is_some());
        assert_eq!(cache.known_len(), 1);
        // A second request for the same id must not be re-queued: dropping
        // the source file would otherwise surface as a decode failure on
        // an unwanted re-decode.
        std::fs::remove_file(&path).unwrap();
        cache.request(key);
        assert!(cache.get("fixture").is_some());
    }

    #[test]
    fn failed_decode_is_cached_as_absent_rather_than_retried_forever() {
        let mut cache = ThemeThumbnailCache::default();
        let key = ThumbnailKey {
            id: "missing".into(),
            path: PathBuf::from("/nonexistent/k230-theme-thumbnail-fixture.png"),
        };
        cache.request(key);
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while cache.known_len() == 0 && std::time::Instant::now() < deadline {
            cache.poll();
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert_eq!(cache.known_len(), 1);
        assert!(cache.get("missing").is_none());
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
        });
        cache.request(ThumbnailKey {
            id: "shared-id-space-b".into(),
            path: background_path.canonicalize().unwrap(),
        });
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(2);
        while cache.known_len() < 2 && std::time::Instant::now() < deadline {
            cache.poll();
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
        assert!(cache.get("shared-id-space-a").is_some());
        assert!(cache.get("shared-id-space-b").is_some());
        std::fs::remove_file(&theme_path).unwrap();
        std::fs::remove_file(&background_path).unwrap();
    }
}

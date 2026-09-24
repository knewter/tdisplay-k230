#[path = "../src/background_decode.rs"]
mod background_decode;

use background_decode::{BackgroundCache, FitMode};
use image::{DynamicImage, ImageFormat, Rgba, RgbaImage};
use std::{
    fs,
    os::unix::fs::symlink,
    path::PathBuf,
    time::{SystemTime, UNIX_EPOCH},
};

struct Fixture {
    root: PathBuf,
}
impl Fixture {
    fn new() -> Self {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root =
            std::env::temp_dir().join(format!("k230-background-{}-{nonce}", std::process::id()));
        fs::create_dir(&root).unwrap();
        Self { root }
    }
    fn path(&self, name: &str) -> PathBuf {
        self.root.join(name)
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

fn save(path: &std::path::Path, image: RgbaImage) {
    DynamicImage::ImageRgba8(image)
        .save_with_format(path, ImageFormat::Png)
        .unwrap();
}

fn pixel(bytes: &[u8], width: usize, x: usize, y: usize) -> &[u8] {
    &bytes[(y * width + x) * 4..(y * width + x + 1) * 4]
}

#[test]
fn crop_fit_center_and_cairo_byte_order() {
    let fixture = Fixture::new();
    let path = fixture.path("still.png");
    let mut source = RgbaImage::new(4, 2);
    for (x, _, color) in source.enumerate_pixels_mut() {
        *color = if x < 2 {
            Rgba([255, 0, 0, 255])
        } else {
            Rgba([0, 0, 255, 255])
        };
    }
    save(&path, source);
    let mut cache = BackgroundCache::new();
    let crop = cache.render(&path, None, 2, 2, FitMode::Crop).unwrap().to_vec();
    assert_eq!(crop.len(), 16);
    assert_eq!(pixel(&crop, 2, 0, 0)[3], 255);
    assert!(pixel(&crop, 2, 0, 0)[2] > pixel(&crop, 2, 0, 0)[0]); // BGRA red side.
    assert!(pixel(&crop, 2, 1, 0)[0] > pixel(&crop, 2, 1, 0)[2]); // Blue side.
    let fit = cache.render(&path, None, 4, 4, FitMode::Fit).unwrap().to_vec();
    assert_eq!(pixel(&fit, 4, 0, 0), &[0, 0, 0, 255]);
    assert_eq!(pixel(&fit, 4, 0, 1), &[0, 0, 255, 255]);
    let center = cache.render(&path, None, 4, 4, FitMode::Center).unwrap().to_vec();
    assert_eq!(pixel(&center, 4, 0, 0), &[0, 0, 0, 255]);
    assert_eq!(pixel(&center, 4, 3, 1), &[255, 0, 0, 255]);
}

#[test]
fn cache_reuses_frame_and_clear_retries_failure() {
    let fixture = Fixture::new();
    let path = fixture.path("still.png");
    let mut cache = BackgroundCache::new();
    assert!(cache.render(&path, None, 2, 2, FitMode::Crop).is_err());
    save(&path, RgbaImage::from_pixel(2, 2, Rgba([255, 0, 0, 255])));
    assert!(cache.render(&path, None, 2, 2, FitMode::Crop).is_err());
    cache.clear();
    let first = cache.render(&path, None, 2, 2, FitMode::Crop).unwrap().to_vec();
    save(&path, RgbaImage::from_pixel(2, 2, Rgba([0, 0, 255, 255])));
    assert_eq!(cache.render(&path, None, 2, 2, FitMode::Crop).unwrap(), first);
    cache.clear();
    assert_ne!(cache.render(&path, None, 2, 2, FitMode::Crop).unwrap(), first);
}

#[test]
fn source_output_format_and_symlink_bounds_fail_closed() {
    let fixture = Fixture::new();
    let path = fixture.path("still.png");
    save(&path, RgbaImage::from_pixel(2, 2, Rgba([0, 0, 0, 255])));
    let mut cache = BackgroundCache::new();
    assert!(cache.render(&path, None, 1025, 2, FitMode::Crop).is_err());
    assert!(cache.render(&path, None, 1024, 2049, FitMode::Crop).is_err());
    let disguised = fixture.path("still.jpg");
    fs::copy(&path, &disguised).unwrap();
    assert!(cache.render(&disguised, None, 2, 2, FitMode::Crop).is_err());
    let link = fixture.path("linked.png");
    symlink(&path, &link).unwrap();
    assert!(cache.render(&link, None, 2, 2, FitMode::Crop).is_err());
    let oversized = fixture.path("large.png");
    let file = fs::File::create(&oversized).unwrap();
    file.set_len(32 * 1024 * 1024 + 1).unwrap();
    assert!(cache.render(&oversized, None, 2, 2, FitMode::Crop).is_err());
}

#[test]
fn decoded_dimension_edge_bound_rejects_small_compressed_file() {
    let fixture = Fixture::new();
    let path = fixture.path("wide.png");
    save(&path, RgbaImage::from_pixel(8193, 1, Rgba([0, 0, 0, 255])));
    let mut cache = BackgroundCache::new();
    assert!(cache
        .render(&path, None, 2, 2, FitMode::Crop)
        .unwrap_err()
        .contains("dimension"));
}

#[test]
fn importer_still_formats_decode_without_loader_plugins() {
    let fixture = Fixture::new();
    let source = DynamicImage::ImageRgba8(RgbaImage::from_pixel(2, 2, Rgba([30, 90, 150, 255])));
    let mut cache = BackgroundCache::new();
    for (extension, format) in [
        ("jpg", ImageFormat::Jpeg),
        ("jpeg", ImageFormat::Jpeg),
        ("png", ImageFormat::Png),
        ("gif", ImageFormat::Gif),
        ("bmp", ImageFormat::Bmp),
        ("webp", ImageFormat::WebP),
    ] {
        let path = fixture.path(&format!("still.{extension}"));
        source.save_with_format(&path, format).unwrap();
        assert_eq!(cache.render(&path, None, 2, 2, FitMode::Crop).unwrap().len(), 16);
    }
}

#[test]
fn wallpaper_cache_hit_bypasses_a_changed_source_and_a_mismatch_falls_back() {
    let fixture = Fixture::new();
    let path = fixture.path("still.png");
    save(&path, RgbaImage::from_pixel(4, 4, Rgba([255, 0, 0, 255])));
    background_decode::write_wallpaper_cache(&path, &fixture.root, 4, 4).unwrap();
    let cache_file = fixture.path("background.cache");
    assert!(cache_file.is_file());

    // Change the source on disk without touching the cache file. A cache
    // hit must return the bytes computed when the cache was written, not a
    // fresh decode of the now-different source.
    save(&path, RgbaImage::from_pixel(4, 4, Rgba([0, 0, 255, 255])));
    let mut cache = BackgroundCache::new();
    let hit = cache
        .render(&path, Some(&fixture.root), 4, 4, FitMode::Crop)
        .unwrap()
        .to_vec();
    assert_eq!(pixel(&hit, 4, 0, 0), &[0, 0, 255, 255]); // BGRA red, from the stale cache.

    // A geometry that does not match the cached width/height falls back to
    // a full decode of the (changed) source, never an error.
    cache.clear();
    let miss = cache
        .render(&path, Some(&fixture.root), 5, 5, FitMode::Crop)
        .unwrap()
        .to_vec();
    assert_eq!(pixel(&miss, 5, 0, 0), &[255, 0, 0, 255]); // BGRA blue, from the live decode.

    // No generation root, or a root with no cache file at all, also falls
    // back cleanly.
    let empty_root = fixture.path("no-cache-here");
    fs::create_dir(&empty_root).unwrap();
    cache.clear();
    let no_cache = cache
        .render(&path, Some(&empty_root), 4, 4, FitMode::Crop)
        .unwrap()
        .to_vec();
    assert_eq!(pixel(&no_cache, 4, 0, 0), &[255, 0, 0, 255]); // live decode of the changed source.
}

#[test]
fn wallpaper_cache_write_rejects_a_video_or_unsupported_destination() {
    let fixture = Fixture::new();
    let path = fixture.path("missing.png");
    assert!(background_decode::write_wallpaper_cache(&path, &fixture.root, 4, 4).is_err());
    assert!(!fixture.path("background.cache").exists());
}

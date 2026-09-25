//! Bounded still-wallpaper decode and software placement for the Rust shell.
//!
//! The appearance receiver validates generation provenance. This module
//! independently bounds the selected regular file, decoded image dimensions,
//! and Cairo SHM output. It does not decode video backgrounds.

use image::{
    imageops::{self, FilterType},
    ImageFormat, ImageReader, Limits, RgbaImage,
};
use std::{
    fs::OpenOptions,
    io::{Cursor, Read, Write},
    os::unix::fs::OpenOptionsExt,
    path::{Path, PathBuf},
};

const MAX_SOURCE_BYTES: u64 = 32 * 1024 * 1024;
const MAX_SOURCE_EDGE: u32 = 8192;
const MAX_SOURCE_PIXELS: u64 = 16 * 1024 * 1024;
const MAX_DECODE_ALLOC: u64 = 128 * 1024 * 1024;
const MAX_OUTPUT_WIDTH: u32 = 1024;
const MAX_OUTPUT_HEIGHT: u32 = 2048;
const MAX_OUTPUT_PIXELS: u64 = 1024 * 2048;

/// On-disk cache of an already-decoded, already-cropped-to-panel-size still
/// wallpaper, written once per prepared theme generation (either by
/// `tools/theme_activate.py`'s `prepare()` at runtime, through the hidden
/// `--write-wallpaper-cache` verb, or by a native-arch build of this same
/// binary at Nix build time for the one pinned bundled generation). The
/// generation directory is already an immutable, hash-identified, one-shot
/// staged copy (see `tools/theme_activate.py`), so this file lives beside
/// its `theme/`, `report.json` and `appearance.json` and is invalidated
/// exactly when the generation itself is: a new generation gets a new
/// directory, never a mutated one.
///
/// This cache is strictly an optimization. A missing, truncated, or
/// geometry-mismatched cache file silently falls back to a full decode --
/// it can never change what gets rendered, only how fast.
const CACHE_MAGIC: &[u8; 8] = b"K230BGC1";
const CACHE_HEADER_LEN: u64 = 17; // 8 (magic) + 4 (width) + 4 (height) + 1 (mode)

fn mode_tag(mode: FitMode) -> u8 {
    match mode {
        FitMode::Crop => 0,
        FitMode::Fit => 1,
        FitMode::Center => 2,
    }
}

fn cache_file_path(generation_root: &Path) -> PathBuf {
    generation_root.join("background.cache")
}

/// Read a cache file for `generation_root` if one exists and matches the
/// requested `width`/`height`/`mode` exactly. Any structural problem (wrong
/// size, bad magic, unreadable file, symlink) is treated as a cache miss,
/// never as an error.
fn load_cached(generation_root: &Path, width: u32, height: u32, mode: FitMode) -> Option<Vec<u8>> {
    let expected_pixels = output_pixels(width, height).ok()?;
    let path = cache_file_path(generation_root);
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)
        .ok()?;
    let metadata = file.metadata().ok()?;
    let expected_len = CACHE_HEADER_LEN.checked_add(expected_pixels as u64)?;
    if !metadata.is_file() || metadata.len() != expected_len {
        return None;
    }
    let mut bytes = Vec::new();
    file.take(expected_len + 1).read_to_end(&mut bytes).ok()?;
    if bytes.len() as u64 != expected_len {
        return None;
    }
    if &bytes[0..8] != CACHE_MAGIC {
        return None;
    }
    let cached_width = u32::from_le_bytes(bytes[8..12].try_into().ok()?);
    let cached_height = u32::from_le_bytes(bytes[12..16].try_into().ok()?);
    let cached_mode = bytes[16];
    if cached_width != width || cached_height != height || cached_mode != mode_tag(mode) {
        return None;
    }
    bytes.drain(0..CACHE_HEADER_LEN as usize);
    Some(bytes)
}

/// Write `pixels` (already rendered by `render_uncached` for `width` x
/// `height` at `mode`) as a cache file under `generation_root`. Written to a
/// sibling temporary file and atomically renamed so a reader never observes
/// a partial file. Advisory: callers treat failure as a missed optimization,
/// never as a reason to fail a theme activation.
fn write_cache(
    generation_root: &Path,
    width: u32,
    height: u32,
    mode: FitMode,
    pixels: &[u8],
) -> Result<(), String> {
    let expected_pixels = output_pixels(width, height)?;
    if pixels.len() != expected_pixels {
        return Err("wallpaper cache payload size mismatch".into());
    }
    let destination = cache_file_path(generation_root);
    let temporary = generation_root.join(".background.cache.tmp");
    let mut file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .custom_flags(libc::O_NOFOLLOW)
        .mode(0o600)
        .open(&temporary)
        .map_err(|error| error.to_string())?;
    file.write_all(CACHE_MAGIC)
        .and_then(|_| file.write_all(&width.to_le_bytes()))
        .and_then(|_| file.write_all(&height.to_le_bytes()))
        .and_then(|_| file.write_all(&[mode_tag(mode)]))
        .and_then(|_| file.write_all(pixels))
        .and_then(|_| file.sync_all())
        .map_err(|error| error.to_string())?;
    drop(file);
    std::fs::rename(&temporary, &destination).map_err(|error| error.to_string())?;
    Ok(())
}

/// Compute pixels for `source` at `width` x `height`/`mode` (a full decode,
/// bypassing any cache) and persist them as `generation_root`'s wallpaper
/// cache. Used by the hidden `--write-wallpaper-cache` CLI verb, which is
/// invoked both by `tools/theme_activate.py`'s `prepare()` (a fresh runtime
/// generation, once) and by a native-arch build of this binary at Nix build
/// time (the one pinned bundled generation).
pub fn write_wallpaper_cache(
    source: &Path,
    generation_root: &Path,
    width: u32,
    height: u32,
) -> Result<(), String> {
    let pixels = render_uncached(source, width, height, FitMode::Crop)?;
    write_cache(generation_root, width, height, FitMode::Crop, &pixels)
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum FitMode {
    #[default]
    Crop,
    Fit,
    Center,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct CacheKey {
    path: PathBuf,
    width: u32,
    height: u32,
    mode: FitMode,
}

/// How many distinct (path, width, height, mode) entries `BackgroundCache`
/// keeps decoded simultaneously. A single slot (this cache's design before
/// task 3.1b) already made an *immediately preceding* prepare-then-commit for
/// the same candidate a guaranteed in-memory hit, but evicted that entry the
/// moment any other candidate was prepared -- e.g. task 3.2 warming a
/// different theme while the person kept browsing, or the Preview page's own
/// background carousel stepping through a theme's other wallpapers -- so an
/// Apply that landed on anything but the single most-recently-viewed
/// candidate still paid at least a `background.cache` file read at commit.
/// A small bounded LRU keeps a short recent history warm instead, so commit
/// is a guaranteed in-memory hit for any of the last few candidates actually
/// prepared, not just the last one.
const CACHE_CAPACITY: usize = 4;

#[derive(Default)]
pub struct BackgroundCache {
    /// Most-recently-used first. Bounded to `CACHE_CAPACITY` entries; never
    /// reallocated beyond it, so memory stays proportional to a small,
    /// fixed recent-candidate history, not to how many themes were ever
    /// browsed.
    entries: Vec<(CacheKey, Result<Vec<u8>, String>)>,
}

impl BackgroundCache {
    pub fn new() -> Self {
        Self::default()
    }

    /// Returns native little-endian Cairo ARGB32 bytes (B,G,R,255). The
    /// wallpaper is composited against opaque black, including Fit letterbox.
    /// Up to `CACHE_CAPACITY` distinct keys' results stay cached at once,
    /// most-recently-used first; a key beyond that bound evicts the least
    /// recently used entry.
    ///
    /// `generation_root`, when given, is the prepared theme generation
    /// directory that `path` lives under (see `AppearanceSnapshot::path`).
    /// If it holds a `background.cache` file matching `width`/`height`/
    /// `mode`, that is used instead of a full decode; the miss path is
    /// identical to passing `None`.
    pub fn render(
        &mut self,
        path: &Path,
        generation_root: Option<&Path>,
        width: u32,
        height: u32,
        mode: FitMode,
    ) -> Result<&[u8], String> {
        let key = CacheKey {
            path: path.to_path_buf(),
            width,
            height,
            mode,
        };
        let position = self.entries.iter().position(|(found, _)| found == &key);
        let index = match position {
            Some(index) => index,
            None => {
                let rendered = generation_root
                    .and_then(|root| load_cached(root, width, height, mode))
                    .map(Ok)
                    .unwrap_or_else(|| render_uncached(path, width, height, mode));
                self.entries.insert(0, (key, rendered));
                if self.entries.len() > CACHE_CAPACITY {
                    self.entries.pop();
                }
                0
            }
        };
        if index != 0 {
            let entry = self.entries.remove(index);
            self.entries.insert(0, entry);
        }
        match &self.entries[0].1 {
            Ok(bytes) => Ok(bytes),
            Err(error) => Err(error.clone()),
        }
    }

    pub fn clear(&mut self) {
        self.entries.clear();
    }

    #[cfg(test)]
    pub fn len(&self) -> usize {
        self.entries.len()
    }
}

fn output_pixels(width: u32, height: u32) -> Result<usize, String> {
    let pixels = u64::from(width)
        .checked_mul(u64::from(height))
        .ok_or("wallpaper geometry overflow")?;
    if width == 0
        || height == 0
        || width > MAX_OUTPUT_WIDTH
        || height > MAX_OUTPUT_HEIGHT
        || pixels > MAX_OUTPUT_PIXELS
    {
        return Err("wallpaper output geometry exceeds bound".into());
    }
    usize::try_from(pixels.checked_mul(4).ok_or("wallpaper output overflow")?)
        .map_err(|_| "wallpaper output overflow".into())
}

fn expected_format(path: &Path) -> Result<ImageFormat, String> {
    match path
        .extension()
        .and_then(|extension| extension.to_str())
        .unwrap_or("")
        .to_ascii_lowercase()
        .as_str()
    {
        "png" => Ok(ImageFormat::Png),
        "jpg" | "jpeg" => Ok(ImageFormat::Jpeg),
        "webp" => Ok(ImageFormat::WebP),
        "gif" => Ok(ImageFormat::Gif),
        "bmp" => Ok(ImageFormat::Bmp),
        _ => Err("unsupported still-wallpaper extension".into()),
    }
}

fn decode(path: &Path) -> Result<RgbaImage, String> {
    if !path.is_absolute()
        || path
            .canonicalize()
            .map_err(|_| "wallpaper path unavailable")?
            != path
    {
        return Err("wallpaper path is not canonical".into());
    }
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK)
        .open(path)
        .map_err(|_| "wallpaper file unavailable")?;
    let metadata = file
        .metadata()
        .map_err(|_| "wallpaper metadata unavailable")?;
    if !metadata.is_file() || metadata.len() > MAX_SOURCE_BYTES {
        return Err("wallpaper source exceeds bound or is not regular".into());
    }
    let mut bytes = Vec::new();
    file.take(MAX_SOURCE_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "wallpaper read failed")?;
    if bytes.len() as u64 > MAX_SOURCE_BYTES {
        return Err("wallpaper source exceeds bound".into());
    }
    let expected = expected_format(path)?;
    let format = image::guess_format(&bytes).map_err(|_| "unrecognized wallpaper format")?;
    if format != expected {
        return Err("wallpaper format/extension mismatch".into());
    }
    let limits = || {
        let mut limits = Limits::default();
        limits.max_image_width = Some(MAX_SOURCE_EDGE);
        limits.max_image_height = Some(MAX_SOURCE_EDGE);
        limits.max_alloc = Some(MAX_DECODE_ALLOC);
        limits
    };
    let mut dimensions = ImageReader::with_format(Cursor::new(bytes.as_slice()), format);
    dimensions.limits(limits());
    let (width, height) = dimensions
        .into_dimensions()
        .map_err(|_| "wallpaper dimensions unavailable")?;
    if width == 0
        || height == 0
        || width > MAX_SOURCE_EDGE
        || height > MAX_SOURCE_EDGE
        || u64::from(width) * u64::from(height) > MAX_SOURCE_PIXELS
    {
        return Err("wallpaper decoded dimensions exceed bound".into());
    }
    let mut reader = ImageReader::with_format(Cursor::new(bytes.as_slice()), format);
    reader.limits(limits());
    let image = reader.decode().map_err(|_| "wallpaper decode failed")?;
    if image.width() != width || image.height() != height {
        return Err("wallpaper dimensions changed during decode".into());
    }
    Ok(image.to_rgba8())
}

fn place(source: &RgbaImage, width: u32, height: u32, mode: FitMode) -> Result<RgbaImage, String> {
    let (source_width, source_height) = source.dimensions();
    let mut canvas = RgbaImage::new(width, height);
    for pixel in canvas.pixels_mut() {
        *pixel = image::Rgba([0, 0, 0, 255]);
    }
    let (scaled, x, y) = match mode {
        FitMode::Crop => {
            let (crop_width, crop_height) = if u64::from(source_width) * u64::from(height)
                > u64::from(source_height) * u64::from(width)
            {
                (
                    (u64::from(source_height) * u64::from(width) / u64::from(height)).max(1) as u32,
                    source_height,
                )
            } else {
                (
                    source_width,
                    (u64::from(source_width) * u64::from(height) / u64::from(width)).max(1) as u32,
                )
            };
            let left = (source_width - crop_width) / 2;
            let top = (source_height - crop_height) / 2;
            let crop = imageops::crop_imm(source, left, top, crop_width, crop_height).to_image();
            (
                imageops::resize(&crop, width, height, FilterType::Triangle),
                0,
                0,
            )
        }
        FitMode::Fit => {
            let (fit_width, fit_height) = if u64::from(source_width) * u64::from(height)
                >= u64::from(source_height) * u64::from(width)
            {
                (
                    width,
                    (u64::from(source_height) * u64::from(width) / u64::from(source_width)).max(1)
                        as u32,
                )
            } else {
                (
                    (u64::from(source_width) * u64::from(height) / u64::from(source_height)).max(1)
                        as u32,
                    height,
                )
            };
            (
                imageops::resize(source, fit_width, fit_height, FilterType::Triangle),
                (width - fit_width) / 2,
                (height - fit_height) / 2,
            )
        }
        FitMode::Center => {
            let copy_width = source_width.min(width);
            let copy_height = source_height.min(height);
            let crop = imageops::crop_imm(
                source,
                (source_width - copy_width) / 2,
                (source_height - copy_height) / 2,
                copy_width,
                copy_height,
            )
            .to_image();
            (crop, (width - copy_width) / 2, (height - copy_height) / 2)
        }
    };
    imageops::overlay(&mut canvas, &scaled, i64::from(x), i64::from(y));
    Ok(canvas)
}

fn render_uncached(path: &Path, width: u32, height: u32, mode: FitMode) -> Result<Vec<u8>, String> {
    let output_len = output_pixels(width, height)?;
    let source = decode(path)?;
    let placed = place(&source, width, height, mode)?;
    let mut output = Vec::with_capacity(output_len);
    for rgba in placed.pixels() {
        let alpha = u16::from(rgba[3]);
        // Flatten alpha over black so the persistent layer is fully opaque.
        let premultiply = |channel: u8| ((u16::from(channel) * alpha + 127) / 255) as u8;
        output.extend_from_slice(&[
            premultiply(rgba[2]),
            premultiply(rgba[1]),
            premultiply(rgba[0]),
            255,
        ]);
    }
    if output.len() != output_len {
        return Err("wallpaper output length mismatch".into());
    }
    Ok(output)
}

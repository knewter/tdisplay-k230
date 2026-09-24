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
    io::{Cursor, Read},
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

#[derive(Default)]
pub struct BackgroundCache {
    cached: Option<(CacheKey, Result<Vec<u8>, String>)>,
}

impl BackgroundCache {
    pub fn new() -> Self {
        Self::default()
    }

    /// Returns native little-endian Cairo ARGB32 bytes (B,G,R,255). The
    /// wallpaper is composited against opaque black, including Fit letterbox.
    /// A single success or failure stays cached until key changes.
    pub fn render(
        &mut self,
        path: &Path,
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
        if self
            .cached
            .as_ref()
            .is_none_or(|(previous, _)| previous != &key)
        {
            self.cached = Some((key, render_uncached(path, width, height, mode)));
        }
        match &self.cached.as_ref().expect("cache populated").1 {
            Ok(bytes) => Ok(bytes),
            Err(error) => Err(error.clone()),
        }
    }

    pub fn clear(&mut self) {
        self.cached = None;
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

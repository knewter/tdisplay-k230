//! Host render of every background fit mode, for
//! `openspec/changes/the-background-chooser-supports-fill-solid-and-video`
//! task 1.x evidence.
//!
//! Each mode is rendered through the production path the shell uses for a
//! generation's wallpaper: a generation `report.json` carrying `fit_mode` and
//! the resolved `background` palette role is read by
//! `appearance::generation_wallpaper_fit`, and the resulting `FitMode` goes
//! to `BackgroundCache::render`. The pixels are native Cairo ARGB32 (B,G,R,A),
//! converted to RGBA only to write the PNG. This proves placement math on
//! the host; it is not a panel capture.
//!
//! `cargo run --offline --example render_background_fit_evidence -- <out-dir>
//! <label> <source-image> <background-hex> [<label> <source-image> <hex> ...]`
//! writes `<label>-<mode>-<W>x<H>.png` for each mode. Output is the native
//! panel's aspect (568x1232) at half size so the committed PNGs stay small;
//! every fit mode is scale-invariant.
use image::{ImageFormat, RgbaImage};
use k230_shell_rust::{appearance, background_decode::{BackgroundCache, FitMode}};
use std::{env, fs, path::PathBuf};

const WIDTH: u32 = 284;
const HEIGHT: u32 = 616;

fn main() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let out_dir = PathBuf::from(args.next().ok_or("usage: <out-dir> (<label> <image> <hex>)+")?);
    fs::create_dir_all(&out_dir).map_err(|e| e.to_string())?;
    let scratch = env::temp_dir().join(format!("k230-fit-evidence-{}", std::process::id()));
    fs::create_dir_all(&scratch).map_err(|e| e.to_string())?;
    let mut cache = BackgroundCache::new();
    let rest: Vec<String> = args.collect();
    if rest.is_empty() || rest.len() % 3 != 0 {
        return Err("expected <label> <image> <background-hex> triples".into());
    }
    for triple in rest.chunks(3) {
        let (label, image, hex) = (&triple[0], PathBuf::from(&triple[1]), &triple[2]);
        for name in FitMode::NAMES {
            fs::write(
                scratch.join("report.json"),
                serde_json::json!({"fit_mode": name, "palette": {"background": hex}}).to_string(),
            )
            .map_err(|e| e.to_string())?;
            let mode = appearance::generation_wallpaper_fit(&scratch);
            assert_eq!(mode.name(), name);
            let bgra = cache.render(&image, None, WIDTH, HEIGHT, mode)?.to_vec();
            let mut png = RgbaImage::new(WIDTH, HEIGHT);
            for (pixel, src) in png.pixels_mut().zip(bgra.chunks_exact(4)) {
                *pixel = image::Rgba([src[2], src[1], src[0], src[3]]);
            }
            let path = out_dir.join(format!("{label}-{name}-{WIDTH}x{HEIGHT}.png"));
            png.save_with_format(&path, ImageFormat::Png).map_err(|e| e.to_string())?;
            eprintln!("rendered {}", path.display());
        }
    }
    let _ = fs::remove_dir_all(&scratch);
    Ok(())
}

//! The two build-time cache verbs of `k230-shell-rust`
//! (`--write-wallpaper-cache`, `--write-thumbnail-cache`) as a small native
//! tool for nix/handheld-theme-default. It compiles the shell's decode
//! modules from their own files, so the cached bytes match what the shell
//! would write, while an edit anywhere else in the shell leaves this tool and
//! the theme package unchanged.
#![allow(dead_code)]

#[path = "../../rust-shell-client/src/background_decode.rs"]
mod background_decode;
#[path = "../../rust-shell-client/src/runtime_trace.rs"]
mod runtime_trace;
#[path = "../../rust-shell-client/src/theme_thumbnails.rs"]
mod theme_thumbnails;

use std::path::Path;

fn run(args: &[String]) -> Result<(), String> {
    match args {
        [_, flag, source, generation_root, width, height] if flag == "--write-wallpaper-cache" => {
            match (width.parse::<u32>(), height.parse::<u32>()) {
                (Ok(width), Ok(height)) => background_decode::write_wallpaper_cache(
                    Path::new(source), Path::new(generation_root), width, height),
                _ => Err("invalid wallpaper cache geometry".into()),
            }
        }
        [_, flag, source, dest_dir, variant, width, height] if flag == "--write-thumbnail-cache" => {
            let variant = match variant.as_str() {
                "expanded" => theme_thumbnails::Variant::Expanded,
                "slice" => theme_thumbnails::Variant::Slice,
                _ => return Err("invalid thumbnail cache variant".into()),
            };
            match (width.parse::<u32>(), height.parse::<u32>()) {
                (Ok(width), Ok(height)) => theme_thumbnails::write_builtin_thumbnail(
                    Path::new(source), Path::new(dest_dir), variant, width, height),
                _ => Err("invalid thumbnail cache geometry".into()),
            }
        }
        _ => Err("usage: k230-theme-cache --write-wallpaper-cache SOURCE GENERATION_ROOT WIDTH HEIGHT | --write-thumbnail-cache SOURCE DEST_DIR expanded|slice WIDTH HEIGHT".into()),
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if let Err(error) = run(&args) {
        eprintln!("k230-theme-cache: {error}");
        std::process::exit(1);
    }
}

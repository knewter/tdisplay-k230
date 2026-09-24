# Pinned built-in backgrounds, host and package checkpoint

Source artifact: `omacom/omarchy` revision `28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`, fetched by a fixed-output Nix hash `sha256-wxvTIkTGJCwQI65KxAErhXhTrnpbWgIvNfDLG4pfJKs=`. The installed `catppuccin` and `catppuccin-latte` directories are unchanged upstream collection members. `nix/handheld-theme-default/source-inventory.json` records SHA-256 of all 20 files, including five original `.webp` background choices. Upstream `LICENSE` is bundled (MIT). No host fixture directory enters the derivation.

The default generation now selects the original dark Catppuccin `backgrounds/2-waves.webp`, which was visually inspected alongside `3-blue-eye.webp` and Latte's `1-color-fade.webp`. Its source SHA-256 is in the inventory and selected path is in both the committed report and native appearance payload. The old palette-only generation `20f2d477bb758593d831e427` remains available for recovery; the fresh default is `0d16475245f13b3d7d3f036f`.

Host commands and result on 2026-09-24:

```sh
nix build .#handheld-theme-default --max-jobs 1 --cores 4 --no-link --print-out-paths
python3 tests/test_handheld_theme_bundle.py --package /nix/store/aajw0dknkkwx4mdswaa0vd52li64d6i7-handheld-theme-default-28ceaae7
cd nix/rust-shell-client
cargo run --offline --example verify_bundled_default -- /nix/store/aajw0dknkkwx4mdswaa0vd52li64d6i7-handheld-theme-default-28ceaae7
```

The narrow package build passed at `/nix/store/aajw0dknkkwx4mdswaa0vd52li64d6i7-handheld-theme-default-28ceaae7` (derivation `/nix/store/4jbbbz109pyigrrnhp9fy12byzzwxzyp-handheld-theme-default-28ceaae7.drv`). Inventory test passed: all 20 upstream files match, both generations exist, and selected media is staged. The actual Rust appearance receiver accepted the pinned default; the bounded decoder produced a non-flat 568×1232 frame from the selected WebP. It also accepted the palette-only recovery default. This is host and cross-package evidence, not a panel capture.

Still open: integrated image build/install, real wallpaper pixel review on the panel, touch switching between Catppuccin and Latte, preview thumbnails, video, persistence and measured physical performance. No theme proposal task is marked complete from this package check alone.

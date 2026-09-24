# Selected Omarchy wallpaper previews: host render

Captured 2026-09-24 from this change's Rust source on a native host at
568×1232. These are renderer fixtures, not QEMU, installed-device, or real
glass observations. The selected still is decoded on a bounded worker thread
and painted as a **512×176 center-crop sample** inside the chooser. It does not
represent the full-screen wallpaper fit or prove final image-picker task 4.1.

The staged immutable generations came from unchanged pinned `omacom/omarchy`
revision `28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`, as recorded in the
[theme visual evidence](../../coherent-shell/rust-visual-themes-host/README.md).
Catppuccin generation `cd73257753c4a1a64fa092b3` selected
`backgrounds/1-totoro.webp`; Catppuccin Latte generation
`c55da9f13ae1265e4ff18435` selected
`backgrounds/1-color-fade.webp`. The icon root was
`/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share`.
The fixtures use public theme assets and sample text only.

```sh
XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share K230_VISUAL_GENERATION_DIR=/tmp/k230-rust-visual-catppuccin/generations/cd73257753c4a1a64fa092b3 K230_VISUAL_FIXTURE_DIR=/tmp/k230-wallpaper-preview-dark K230_VISUAL_REQUIRE_ICONS=1 K230_VISUAL_REQUIRE_BACKGROUND=1 cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline --locked themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles
XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share K230_VISUAL_GENERATION_DIR=/tmp/k230-rust-visual-latte/generations/c55da9f13ae1265e4ff18435 K230_VISUAL_FIXTURE_DIR=/tmp/k230-wallpaper-preview-latte K230_VISUAL_REQUIRE_ICONS=1 K230_VISUAL_REQUIRE_BACKGROUND=1 cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline --locked themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles
```

Both fixture commands passed. The [dark](catppuccin-preview.png) and
[light](latte-preview.png) captures were visually inspected: each selected
still appears in the preview, with readable label and palette. The preview
does not activate a theme. Video is explicitly unavailable. Decode failures
show an unavailable state without logging the private source path. Physical
latency, RSS, touch selection, rollback, and full wallpaper placement remain
separate open gates.

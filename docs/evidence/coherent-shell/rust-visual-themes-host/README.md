# Rust shell visual pass: actual pinned theme generations

Captured 2026-09-24 06:52 UTC from source `f9978fe69a6dcd29430f83e35685c79ada33457b`
(base `f80eedcd19e563d2804fe682ed9d75deac9a3adb`). These are native **host
renderer** PNGs at 568×1232, not QEMU or panel captures. The two apps and one
notification contain public fixture text; the app/notification icons were
decoded from the selected pinned Yaru bundle, not synthesized initials. The
transparent top of `drawer.png` and lower part of `shade.png` display black in
standalone viewers; in the compositor those areas preserve the underlying
live scene. The previews show a selected still filename from each real theme
report; they do not render the wallpaper image.

The unchanged theme sources are pinned `omacom/omarchy` revision
`28ceaae70ebac3a0edcc21f2faa77a90dc6d404c`: Catppuccin source SHA256
`72e8f8f39a1209893b30b651fece6c1d1ce47ec643df9e596c7cd282ea97d4c6`,
Catppuccin Latte source SHA256
`11ea23e5a4659b09ecda0658dd86921489d6f536b86ffa60af2f601912a70cdc`.
`theme_activate.py --prepare-only` generated immutable dark
`cd73257753c4a1a64fa092b3` (Yaru-purple) and light
`c55da9f13ae1265e4ff18435` (Yaru-blue) appearance/report pairs. The icon
root was `/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share`.
The renderer fixture requires at least two successful icon decodes per run.

The narrow host commands were:

```sh
python3 tools/theme_activate.py catppuccin --source /tmp/k230-omarchy-theme-fixtures/builtins/themes/catppuccin --state-root /tmp/k230-rust-visual-catppuccin --tools nix/omarchy-theme-tools/upstream --prepare-only
python3 tools/theme_activate.py catppuccin-latte --source /tmp/k230-omarchy-theme-fixtures/builtins/themes/catppuccin-latte --state-root /tmp/k230-rust-visual-latte --tools nix/omarchy-theme-tools/upstream --prepare-only
XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share K230_VISUAL_GENERATION_DIR=/tmp/k230-rust-visual-catppuccin/generations/cd73257753c4a1a64fa092b3 K230_VISUAL_FIXTURE_DIR=/tmp/k230-rust-visual-dark-accepted K230_VISUAL_REQUIRE_ICONS=1 cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline -q themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles
XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share K230_VISUAL_GENERATION_DIR=/tmp/k230-rust-visual-latte/generations/c55da9f13ae1265e4ff18435 K230_VISUAL_FIXTURE_DIR=/tmp/k230-rust-visual-latte-accepted K230_VISUAL_REQUIRE_ICONS=1 cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline -q themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline -q
```

Both real-generation fixture runs passed and all 62 host Cargo tests passed
(33 library, 6 route, 10 appearance, 5 background decoder, 8 service). The
screens were visually inspected: dark and Latte drawer, shade, Settings,
theme list, and theme preview retain readable foreground and secondary text;
selected controls and app/notification rows use authored theme colors. The
Settings background comes from the authored `menu.background` because the
upstream `controls` section defines control states, not a panel background.

The pass preserves existing hit regions and gesture routing. Cross-built
package, installed board pixels, wallpaper composition, motion quality, real
touch, optical contrast, and CPU/frame budgets are separate open gates.

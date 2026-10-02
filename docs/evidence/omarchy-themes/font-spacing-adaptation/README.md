# Host rendering: font and spacing adaptation

Captured 2026-10-02 05:43 UTC on x86_64. These production Rust
`RendererCache` / Cairo / Pango frames use identical Settings service fixtures
and the pinned Catppuccin appearance. The baseline leaves generated theme
metrics unchanged. The adapted private fixture changes only `[font]
base-size=15`, an optional `caption=13` role override, and upstream `[spacing]
scale=1.25`. Both frames retain the same values, including the unavailable
audio-device state. No selected theme, palette, icons, wallpaper, or service
fixture changes between them.

The adapted capture shows label sizes and row text inset changing. Settings
row positions and touch target geometry remain fixed; the Rust regression
checks `settings_row_y(1) == 288` alongside bounded font sizes and spacing.
This is host renderer evidence only: it does not establish panel readability,
real-theme appearance, or physical touch acceptance. Existing authored
dark/light captures remain in [`shell-polish/after/`](../../shell-polish/after/)
and the native board captures in
[`settings-volume-layout/board/`](../../shell-polish/settings-volume-layout/board/).

Reproduce from the repository root:

```sh
python3 tools/theme_field_inventory.py > docs/evidence/omarchy-themes/token-adaptation-inventory.md
python3 tests/test_handheld_theme_rendering.py
CARGO_TARGET_DIR="$HOME/tmp/k230-theme-parent-inventory-cargo-target" \
  cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib
CARGO_TARGET_DIR="$HOME/tmp/k230-theme-parent-inventory-cargo-target" \
  cargo run --offline --manifest-path nix/rust-shell-client/Cargo.toml \
  --example render_theme_metrics_evidence -- "$HOME/tmp/k230-theme-metrics-review"
```

`font-spacing-adapted.png` SHA-256: `2c971a30f7138e3ed0b0cfeb4538bbdf432e33ac65cc329225fc7b5af9d52a6f`.
`baseline.png` SHA-256: `e25bde2aeed303bb0f318292e527f6dc12752579d018309514a851c0236eab0b`.
Renderer source SHA-256: `0e964b6c2192c595075d97959b964ce10177dd447d187d02c106ba9101582091`.
Example source SHA-256: `2ec06b2414fa870d232faed57198d53d3c1861d0cb02c45ea6378fedcb4f1a40`.

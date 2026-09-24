# Three-column Rust drawer: host visual checkpoint

The two 568×1232 PNGs are native host renderer output, visually reviewed on 24 September 2026. They use seven public fixture desktop entries; the first two resolve real icons through the selected pinned Yaru root, while the remaining five exercise the fixed-size fallback. They are not installed catalog, compositor, panel, finger, optical-contrast, CPU or frame-cadence proof. In standalone viewers the transparent upper portion looks black; it is the live deck in the actual layered session.

The source uses the actual Catppuccin (`cd73257753c4a1a64fa092b3`) and Latte (`c55da9f13ae1265e4ff18435`) generations prepared by the commands in [the prior visual evidence](../rust-visual-themes-host/README.md). Reproduce from the repository root after preparing those generations:

```sh
XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share K230_VISUAL_GENERATION_DIR=/tmp/k230-rust-visual-catppuccin/generations/cd73257753c4a1a64fa092b3 K230_VISUAL_FIXTURE_DIR=/tmp/k230-drawer-grid-dark K230_VISUAL_REQUIRE_ICONS=1 cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline --locked -q themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles
XDG_DATA_DIRS=/nix/store/in3nc21zx02xiz2rdp5bpq36719x3axd-handheld-theme-icons-25.10.3/share K230_VISUAL_GENERATION_DIR=/tmp/k230-rust-visual-latte/generations/c55da9f13ae1265e4ff18435 K230_VISUAL_FIXTURE_DIR=/tmp/k230-drawer-grid-latte K230_VISUAL_REQUIRE_ICONS=1 cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline --locked -q themed_surface_fixtures_keep_live_area_clear_and_use_authored_roles
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline --locked
```

Both targeted fixture runs and all 65 host Rust tests passed (36 library, 6 route, 10 appearance, 5 decoder, 8 service). The [dark PNG](dark.png) SHA256 is `0ec94093d0139736c5c6d0c7b1a707d555cc845c2d3d62e4b07cead826d7e14c`; [Latte](latte.png) is `fb552085a88544e9759aa17a136505b6369ddeb40504a3752fcad588c142bb95`.

The grid paint and hit tests share tile geometry. Seven entries fit three columns and scroll by rows when needed; pressed selection has a visible border and a second contact or drag cancels launch. A theme-colored opaque plate sits *behind* the authored launcher brush, retaining its authored stops and alpha in the surface while preventing underlying card text from showing through app labels. The host fixture checks the composed drawer panel is opaque and leaves its upper live-deck area transparent. Real compositor stacking and glass readability remain open.

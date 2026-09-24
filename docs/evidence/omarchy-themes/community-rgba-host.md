# Community palette receiver correction: host checkpoint

Base source `017125c89a1103c0371035f95544a801f41c14e0`. The unchanged pinned Fuchsblau clone at `/tmp/k230-omarchy-theme-fixtures/community` has source digest `f72ece7c9eead4fb049ebead18d918b4b11be6f35dcc861b8862e5c8f0693e75` (see [source fixtures](source-fixtures.md)). Its generated report retains upstream `hyprland_inactive_border = "rgba(4e578499)"`. The Rust appearance receiver treated every non-mode palette value as `#RRGGBB[AA]`, so it rejected this otherwise valid generation at `prepare`. The host C deck receiver accepted the same generated report and appearance payload.

The Rust parser now recognizes `rgba(RRGGBBAA)` only for `hyprland_active_border` and `hyprland_inactive_border`, preserving a typed color with alpha. It still rejects that spelling for shell background and unrelated keys. The generated community generation `3881c9a350717403ef4b4772` was prepared from the unchanged clone twice with the same identity, then loaded by the Rust receiver on host. The permanent test uses the generated fixture when `K230_COMMUNITY_GENERATION` is supplied, and the synthetic test exercises the positive and negative parser cases without an external clone.

```sh
python3 tools/theme_catalog.py --user-themes /tmp/k230-omarchy-theme-fixtures --state-root /tmp/k230-community-theme-repro preview f2537de459fd09dcf2f01436 --json
K230_COMMUNITY_GENERATION=/tmp/k230-community-theme-repro/generations/3881c9a350717403ef4b4772 cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline --locked --test appearance_module prepared_real_community_generation_loads_when_fixture_is_available
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --offline --locked --test appearance_module community_hyprland_rgba_palette_prepares_without_relaxing_shell_colors
```

This proves host parsing only. A rebuilt installed Rust receiver and repeated community activation on the board are still required. The earlier board trial failed at `activate-community` and restored the prior selection; that trial does not count as successful activation or visual acceptance.

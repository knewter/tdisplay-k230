# Rust theme chooser host checkpoint

Source base: `8b8b4666ed78503f807e8c7a10ce559ad717209b` (the pinned `k230-theme` bridge is already present). The subsequent frontend commit is the source artifact for this note. This is a host-only UI checkpoint, not an installed or physical touch result.

The persistent Rust shell now exposes **Themes** within Settings. The chooser requests a bounded asynchronous list, previews a selected theme without activating it, displays its reported palette and background choices, and sends an explicit Apply request with the preview's exact generation and selected background ID. A video background remains visible as unavailable because the Rust shell has no video renderer. Cancel/back leaves the compositor-owned live deck and theme unchanged; an activation already dispatched cannot be cancelled locally. Worker or backend errors remain visible in the chooser.

Host checks in `nix/rust-shell-client`:

```sh
cargo fmt --all -- --check
cargo test --offline
cargo clippy --offline --lib --bin k230-shell-rust -- -D warnings
K230_THEME_FIXTURE_PNG=/tmp/k230-rust-theme-preview.png cargo test --offline theme_list_preview_and_scroll_paint_distinct_handheld_scenes
```

Result on 2026-09-24: 31 library, 6 main, 10 appearance, 5 background, and 8 service integration tests passed; strict library/binary Clippy passed. The 568×1232 fixed-content preview PNG was opened and visually checked for readable heading, palette, background list, unsupported-video label, and explicit Apply. That `/tmp` capture is a host fixture, not device evidence and not a private application capture.

Still open: exact cross-build and installed image, a paired Sway/Rust QEMU route and backend transaction check, real touch scrolling/preview/Apply, and the sibling theme proposal's full background thumbnail/motion and physical acceptance gates. No OpenSpec task is checked by this host source checkpoint alone.

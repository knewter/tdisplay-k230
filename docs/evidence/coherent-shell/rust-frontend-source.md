# Opt-in Rust shell client rendering checkpoint

2026-09-24, branch `implement/rust-shell-client`, base `7017c5ed`. This is a
source and target-package checkpoint, not a completed drawer, theme, Settings,
notification or real-touch result. OpenSpec groups 1–5 remain open.

The new `nix/rust-shell-client/` is separate from the immutable diagnostic
probe. Its `Cargo.lock` pins SCTK 0.20.0, Cairo/Pango/PangoCairo/GIO 0.21.5
bindings and their transitive crates. `k230-shell-rust --serve` retains the
probe's idle private route socket and released Wayland SHM buffer discipline;
`--surface drawer|shade|settings|hide` accepts only an explicit route. The
render path now uses Cairo/Pango text and GIO installed desktop-entry names.
The host fixture shows a transparent upper region over a real compositor
scene, a readable panel and generic initial glyphs. Those glyphs are
placeholders: icon theme resolution and private-state integration are not
proved. Shade and Settings display explicit unloaded states until their
real services are connected. The source still lacks finger tracking and
theme-generation consumption.

Host commands:

```text
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked
  PASS: 7 unit checks, including Cairo SHM alpha/panel bounds and bounded GIO catalog
cargo clippy --manifest-path nix/rust-shell-client/Cargo.toml --locked --all-targets -- -D warnings
  PASS
cargo fmt --manifest-path nix/rust-shell-client/Cargo.toml --check
  PASS
cargo run --manifest-path nix/rust-shell-client/Cargo.toml --locked -- --render-fixture drawer /tmp/k230-rust-frontend-drawer.png
  PASS: local 568x1232 PNG visually reviewed; it contains workstation desktop names
nix build .#handheld-shell-rust --max-jobs 1 --cores 4 --no-link --print-out-paths
  PASS: /nix/store/gfgfp39jxbpfk0wymd9jk37jqjb8kkgb-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0
```

The target output is ELF64 RISC-V LP64D, dynamically linked against the
expected Cairo/Pango/GIO/GLib and libc libraries. `nix path-info -S
--closure-size` reports 86,357,080 bytes for this partial package and its
recursive runtime closure; neither that number nor the host PNG measures
board RSS, CPU, touch latency or panel rendering. It is not installed as the
normal session. The board's diagnostic probe observation is recorded
separately and does not transfer to this client.

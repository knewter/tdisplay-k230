# Rust layer-shell software-client feasibility checkpoint

Source branch: `probe/rust-shell-client`, based on `3d3d915fc57f` with the
Rust-target plan landed separately. Date: 2026-09-24. This is an opt-in probe, not the normal
handheld shell or a substitute for the physical acceptance tasks.

`nix/rust-shell-probe` pins `smithay-client-toolkit` 0.20.0,
`wayland-client` 0.31.11 and `libc` 0.2.175 in `Cargo.toml`; its committed
`Cargo.lock` resolves 37 Cargo packages. The target package uses
`pkgsCross.riscv64.rustPlatform.buildRustPackage` and SCTK's wlr-layer-shell
and `SlotPool` software `wl_shm` interfaces. The direct target is
`riscv64-unknown-linux-gnu` according to the evaluated Nix derivation. No
Vulkan/OpenGL renderer is required by the probe source.

The persistent `--serve` command remains unmapped when idle. It listens on a
mode-0600 Unix socket in a session-owned private runtime directory, accepts
`--surface drawer|shade|settings|hide`, and acknowledges after submitting and
flushing a layer-shell map/unmap request. The response is not a presentation
timestamp. Its `k230-shell-drawer` overlay namespace matches the compositing
route contract. A mapped probe paints a distinct ARGB8888 software panel at
the configured size with a transparent upper strip so the real compositor
scene remains visible. Touch down/move/up/cancel events log monotonic offsets
and change a visible crosshair. The bounded three-slot pool never writes a
slot whose Wayland buffer has not been released. This is diagnostic content,
not the final visual design or app drawer.

Host commands from the source tree:

```text
cargo test --manifest-path nix/rust-shell-probe/Cargo.toml --locked
  PASS: 5 pure state/render tests
python3 tests/test_rust_shell_probe.py --case route-timeout --case configure-resize --case buffer-release --case touch-cancel
  PASS: 4 focused host gates; route-timeout executes the compiled helper
  against a silent local socket; other gates exercise geometry, slot choice,
  and touch cancellation state
nix build .#handheld-shell-rust-probe --dry-run --print-out-paths --max-jobs 1 --cores 4
  PASS: evaluates target derivation; 38 derivations to build and 23 paths to
  fetch (5.0 MiB download, 44.0 MiB unpacked) in this cached host state
```

The independent Qt Quick software probe uses pinned Qt 6.11.2 through the
same nixpkgs input, targets Qt Base/Declarative/Wayland, and forces Wayland
plus the software scene-graph backend. Its reported dry-run had 40
derivations, with incidental QtSvg/ShaderTools/XCB/Vulkan-loader inputs. The
dry-run counts depend on store cache state and are **not** a closure-size or
runtime-performance comparison. Rust uses a small Wayland/SHM client graph;
Qt includes a fuller scene graph and QML stack. Neither target's actual
binary, closure, cold-start, RSS, CPU or touch-to-present numbers follow from
these evaluations.

The pinned Qt Declarative 6.11.2 source archive
`/nix/store/wv7whhmb9kmmjh0hcf10bl1w3vkmzvmv-qtdeclarative-everywhere-src-6.11.2.tar.xz`
has a QML JIT condition in `src/qml/configure.cmake` lines 88–101 that names
i386/x86_64/arm/arm64, not RISC-V. This suggests the target QV4 JIT may be
off; only the actual Qt target configure log can confirm it. It is not a
measured animation or binding cost.

Remaining proof: the reserved narrow Rust cross-build, actual target/store
closure inspection, QEMU or compositor mapping if useful, and a separately
reserved real board/camera run at 568×1232 with real touch, frame cadence,
CPU/RSS and C/Qt comparison. No panel presentation or installed-image claim
is made here. Source API inspiration is SCTK's
[MIT-licensed `simple_layer` example](https://github.com/Smithay/client-toolkit/blob/v0.20.0/examples/simple_layer.rs).

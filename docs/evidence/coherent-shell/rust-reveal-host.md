# Rust shell reveal stream: host checkpoint

Source: `nix/rust-shell-client/src/protocol.rs`, `src/main.rs`, and `src/render.rs` in this commit. This is an opt-in Rust client checkpoint; it is not an installed session or physical touch result.

The client accepts the compositor's bounded newline JSON v1 `begin`, `update`, `finish`, and `cancel` messages on the private 0600 `k230-shell-rust.sock`. A complete `finish` followed by EOF retains the settled-open drawer or shade; an incomplete stream settles closed. Sequence and route must remain consistent, malformed or oversized lines abort, and a five-second idle peer timeout bounds abandoned contacts. The compositor continues to own gesture classification and live app or deck pixels. The client renders a transparent full-output overlay with no input region during tracking; the panel receives input only after the open settle. Cairo/Pango scene shaping is cached across progress updates, which copy/translate the prepared scene into bounded SHM buffers. This says nothing yet about presented frame rate on the board.

Host proof from the source tree:

```sh
cargo fmt --manifest-path nix/rust-shell-client/Cargo.toml --check
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked
cargo clippy --manifest-path nix/rust-shell-client/Cargo.toml --locked --all-targets -- -D warnings
git diff --check
```

All completed successfully on 2026-09-23. The Rust unit tests include split socket writes, mid-drag reversal, cancellation, premature EOF, completed-finish EOF, input progress, renderer cache reuse, and geometry bounds.

The exact committed source `a8fa5d3283e679724a554d9db52203b98f90ce0e` was built with:

```sh
nix build "git+file://$PWD?rev=a8fa5d3283e679724a554d9db52203b98f90ce0e#handheld-shell-rust" --max-jobs 1 --cores 4 --no-link --print-out-paths
```

The target derivation was `/nix/store/f7kn0zqldgh9bkj48k2pjx2b966wd3k4-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv`; output `/nix/store/kn3x90rplwfrf83z1nk0jjpa0whigrk1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`. `file` reports ELF64 RISC-V LP64D. `nix path-info -S` reports an 86,450,072-byte recursive closure. This is package proof only. Paired QEMU pixels/input routing and physical board observations remain open.

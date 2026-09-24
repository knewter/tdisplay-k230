# Rust wallpaper layer: source and host checkpoint

The opt-in Rust shell maps a separate input-empty layer-shell `Background` surface across the configured output. It stays mapped when the drawer or shade unmaps, so Sway remains the owner of live app/deck pixels above it. Without selected media it paints the authored `launcher.background` brush over an opaque fallback; a host pixel fixture checks this path. The layer owns at most two SHM slots and shares the client's bounded pool. It does not receive touch input.

A selected still is decoded at prepare using the validated immutable appearance path and cached by path, output geometry and placement mode. The pinned pure-Rust image decoder accepts PNG, JPEG, WebP, GIF and BMP, with a 32 MiB source cap, 8192-pixel edge and 16-million-pixel decoded cap, and a 1024×2048 output cap. Current placement is centered crop; transparent pixels are composited over black. Fit/center selection and an authored solid color are decoder capabilities, but the touch chooser and per-theme preference UI have not exposed those choices yet. Decode failure rejects prepare. Video selection is rejected until a bounded playback layer exists.

On commit or rollback, the client stages wallpaper and overlay pixels, waits for their released frame slots, attaches both new buffers and flushes Wayland before sending the protocol ACK. If either draw or flush fails, it rejects the transaction and restores the prior in-memory appearance and selected path. The initial still path and layer map are source behavior, not physical presentation proof. The exact target build, paired Sway/theme transaction under QEMU, real panel image, RSS/decode cost, fit-mode UI, and video lifecycle remain open.

```sh
cargo fmt --manifest-path nix/rust-shell-client/Cargo.toml --check
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked
cargo clippy --manifest-path nix/rust-shell-client/Cargo.toml --locked --all-targets -- -D warnings
git diff --check
```

Host checks on 2026-09-24 UTC passed: 21 library tests, 4 main tests, 8 appearance receiver tests, 5 decoder tests, formatting and strict clippy. The decoder's `image` allocation limit is not a strict process RSS ceiling; measured physical memory remains a required gate.

The exact source commit `0a56fb1ca9cab284217f38d38914324dcbc8ecf1` subsequently passed the RISC-V target build:

```sh
nix build "git+file://$PWD?rev=0a56fb1ca9cab284217f38d38914324dcbc8ecf1#handheld-shell-rust" --max-jobs 1 --cores 4 --no-link --print-out-paths
```

Derivation `/nix/store/j2plrfjnjbzjlb8bhd52zlb9ij397f02-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv` produced `/nix/store/wlcbjyzi8447gdslp7xfr842ppwxyvny-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`. This is a target package, not an installed session or panel image.

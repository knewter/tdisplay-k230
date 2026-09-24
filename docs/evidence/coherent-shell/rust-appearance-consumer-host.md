# Rust appearance consumer: source and host checkpoint

The opt-in Rust shell now binds the private protocol-1 appearance socket beside its reveal socket. It accepts a validated immutable generation, changes the live drawer's `launcher.background` and `menu.background` brushes and `menu.text`, and invalidates the icon cache for the generation's icon theme. Shade and Settings backgrounds use their corresponding authored sections when present. Missing tokens retain the existing legible fallback. A host pixel fixture confirms an authored red launcher brush reaches the default live `RendererCache`, rather than only the export function.

Prepare stages the receiver snapshot. For commit or rollback while a panel is mapped, the client waits for a released frame slot, renders and attaches a new SHM buffer, flushes Wayland, then acknowledges the exact phase/generation. Other draws defer while this transaction waits, so a frame callback cannot consume its released slot first. If the panel is idle, ACK means in-memory adoption for its next map, not presentation. A failed draw/flush restores the prior in-memory render snapshot and rejects the transaction. The wait is bounded to 1.4 seconds within the receiver's two-second peer deadline. The appearance socket is separate from the compositor's continuous reveal socket, and no per-motion theme work is added.

Selected background media are currently rejected during prepare. The persistent wallpaper layer, decoded still fit/crop, video handling, complete authored roles, and paired compositor theme transaction remain open. This checkpoint does not claim an Omarchy theme is visible on the board.

```sh
cargo fmt --manifest-path nix/rust-shell-client/Cargo.toml --check
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked
cargo clippy --manifest-path nix/rust-shell-client/Cargo.toml --locked --all-targets -- -D warnings
git diff --check
```

Host checks passed on 2026-09-24 UTC: 21 library tests, 3 route/launch tests, 8 appearance receiver tests, formatting and strict clippy. Exact RISC-V target build and paired compositor transaction remain open at this source checkpoint.

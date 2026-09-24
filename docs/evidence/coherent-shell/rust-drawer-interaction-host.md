# Rust drawer interaction: host checkpoint

The opt-in Rust shell now routes touch events on its settled drawer layer to a clipped installed-app list. One contact follows the finger, reverses without snapping, and can coast after release. A new touch stops coasting; cancellation or a second contact cannot become an app tap. Taps use the scrolled row index, retain labels and real icons, and ignore row gaps. A downward drag at the top unmaps the drawer to reveal the existing live deck. The compositor owns bottom-edge app/deck reveal; this client handles touch only after its input region is enabled on settled-open.

On selecting an app, the client unmaps its overlay, runs the exact `K230_SWAYMSG card_shell back` command with a two-second child deadline in a worker, then asks GIO to launch the selected `.desktop` ID only if Sway reports success. Sway's pinned `swaymsg` exits nonzero for an IPC `success:false` response. A failed command or disappeared app reopens the drawer; neither starts an unchecked executable string. The Wayland input loop never waits for Sway or GIO. Only one launch worker may be in flight; the UI reopens after three seconds while retaining the worker attempt until its result arrives, and a late result cannot complete a newer attempt. A stuck GIO call would keep new app launches disabled until it returns, rather than accumulating workers. This is source and host-test evidence, not proof that a selected app became visible on the board.

```sh
cargo fmt --manifest-path nix/rust-shell-client/Cargo.toml --check
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked
cargo clippy --manifest-path nix/rust-shell-client/Cargo.toml --locked --all-targets -- -D warnings
git diff --check
```

All passed on 2026-09-24 UTC: 20 library tests and 3 route/launch tests. Focused fixtures cover scrolled hit mapping, finger reversal, second-touch cancellation, fling stop, list clipping with a stable header, named icon resolution in the live renderer, and Sway command failure gating. The SCTK `TouchHandler` callbacks use the second `u32` for Wayland event time; the first is the serial. Integrated QEMU app launch/scroll, physical finger use, frame time and CPU cost remain open. The source leaves Settings, shade history, and theme transaction consumers for separate checkpoints.

The exact corrected source commit `22db5329327c6fcafcfad111cd4cf7ce6ce2c22f` also passed the RISC-V target build:

```sh
nix build "git+file://$PWD?rev=22db5329327c6fcafcfad111cd4cf7ce6ce2c22f#handheld-shell-rust" --max-jobs 1 --cores 4 --no-link --print-out-paths
```

Derivation `/nix/store/132np5g3znfh1c4gfpnbgb00763ar1yl-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv` produced `/nix/store/6833xrvjzznh11m8hx0fvnz01qpggw49-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`. It is not an installed session or physical observation.

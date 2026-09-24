# Rust theme restart and wallpaper-layer recovery: host checkpoint

On service start, the Rust appearance receiver now validates the private theme state's `active` symlink and loads that immutable generation before mapping the drawer or wallpaper. The target must resolve to a direct child of the state's `generations` directory and pass the same bounded appearance/report checks as an incoming transaction. An absent, stale, malformed or escaping pointer falls back to the pinned default generation. A host restart fixture selects a user generation, rebinds the receiver, then checks the selected snapshot; it also checks fallback from a foreign pointer.

If a commit's ACK is lost after the receiver has adopted it, the coordinator can still send its idempotent rollback. A host fixture closes the commit peer before reading its reply, then checks that rollback restores the prior snapshot with an exact protocol response.

The persistent no-input wallpaper layer now schedules a remap after compositor `closed` and retries no faster than once per second if creation fails. A map without configure is retired after three seconds and retried, so output loss does not leave a permanently absent wallpaper surface or grow an unbounded layer list. This lifecycle path has source review and host compile proof only; the paired Sway/output-close behavior still needs QEMU and real device evidence.

```sh
cargo fmt --manifest-path nix/rust-shell-client/Cargo.toml --check
cargo test --manifest-path nix/rust-shell-client/Cargo.toml --locked
cargo clippy --manifest-path nix/rust-shell-client/Cargo.toml --locked --all-targets -- -D warnings
```

Host checks on 2026-09-24 UTC passed: 21 library tests, 4 main tests, 10 appearance receiver tests, 5 background decoder tests, formatting and strict clippy. Exact target build, paired Sway transaction/restart and physical output recovery remain open.

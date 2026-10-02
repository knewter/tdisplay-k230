# Row-repaint closeout against the persistent combined source

Audit date: 2026-10-01. This is a source/evidence reconciliation; no board,
serial port, build slot, or runtime was used by this audit.

## Existing matched pair

`../row-repaint/pair/README.md` records physical injected-input runs for both
picker rows, six swipes per row in each arm, with separate restoration and
identities. It compares the previous Rust client from source
`b57ba41ccf6755c54039fc85b0a54145001b186a` against candidate source
`42e22d4353e35d9c4f6367ed5b159c80b489ec5d` and candidate binary
`/nix/store/2mprr7lqh4hznwz9z1zmv7vamf5nbnna-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
For that pair, active presentation-gap median improved from 134.121 ms to
76.641 ms and p95 from 210.765 ms to 153.287 ms. It also records that the
selected preview differed between the two arms, cadence/jank was not resolved,
and the candidate was restored afterward. This is injected-touch performance
evidence, not real-finger acceptance.

## Current installed source

The committed
`docs/evidence/boot-verification/coherent-ordinary-boot/README.md` and
`postboot.json` identify the persistent system as
`/nix/store/p1a1hz9n8s4g8qyr55ffl3dzbnjgqwr8-nixos-system-nixos-26.11.20260919.20b1ddd`,
the running Rust executable as
`/nix/store/3hy6h165ii649z6vjzjd36jwg16d37rc-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust`,
and the installed application source as `5bb67db128210f830dab4de0d20a4b0eca13c578`.
The ordinary reboot record shows the selected system and profile agree, the
shell services are active, and the saved appearance generation/report hash
matches before and after boot. The record explicitly leaves real-finger
verification false.

The current source is a descendant of the measured row-repaint change, but
the pair does not identify this exact combined Rust binary. The read-only
comparison command was:

```sh
git diff --stat \
  42e22d4353e35d9c4f6367ed5b159c80b489ec5d..5bb67db128210f830dab4de0d20a4b0eca13c578 \
  -- nix/rust-shell-client/src/theme_ui.rs \
     nix/rust-shell-client/src/theme_carousel.rs \
     nix/rust-shell-client/src/main.rs \
     nix/rust-shell-client/src/render.rs \
     nix/rust-shell-client/src/background_decode.rs \
     nix/rust-shell-client/src/theme_thumbnails.rs
```

`main.rs` and `render.rs` changed between the measured and installed source
identities; `render.rs` includes changes in `variant_size` and
`paint_carousel`. The pair therefore cannot establish the current build's
render or presentation cost. The ordinary reboot proves persistence and saved
appearance only. No new task is marked complete by this audit. Task 17.3 still
needs a matched baseline/current-candidate injected comparison on the reserved
board, with independent restoration and the existing identity/capture rules.
Task 14.4 real-finger acceptance, task 10.7 picker fit and tap timing, and the
wider 13/15 gates also remain open.

# Rust shell appearance receiver module: host checkpoint

Observed 2026-09-23 from pushed base `e05e21d5` in the isolated
`implement/rust-appearance-receiver` branch. This checkpoint adds only
`nix/rust-shell-client/src/appearance.rs` and a standalone integration test;
the Rust frontend owner retains `main.rs`, `render.rs`, `lib.rs`, Cargo/Nix
integration. The module is compiled by the test through a local `#[path]`
import, but is **not yet linked into the production Rust shell**.

`AppearanceReceiver::bind` creates a private mode-0600 theme socket under an
owned mode-0700 runtime directory; the planned service path is
`/run/shell/k230-shell-rust-appearance.sock`, separate from the reveal/route
socket. It exposes nonblocking listener/peer descriptors for the existing
Wayland `poll` loop, bounded line reads, typed phase events, and explicit
`respond(event, accepted)`. The scene owner must call `respond` only after
staging a prepare or adopting and flushing a commit/rollback. Exact
protocol-1 phase/generation ACK is then sent. A null rollback restores the
pinned default, and rollback is idempotent even without a prior prepare.

The receiver accepts a generation only from the private user cache or the
exact declared pinned default path. It checks the 24-character generation
identity against both bounded `report.json` and `appearance.json`, uses
no-follow, nonblocking bounded reads (including FIFO rejection), validates
typed sections and the report palette, and freezes the parsed
snapshot at prepare. Brush gradient stops, angle and alpha, four-sided widths,
numbers, booleans and raw values remain distinct. The snapshot retains the
selected validated still path, the selected media path even when it is video,
every staged background choice, icon selector, and compatibility lists.
Every staged background resolves under this generation's real
`theme/backgrounds` directory; intermediate symlink escapes are refused.
No media is decoded here. User crop/fit preference is not yet in the current
generated payload and remains task 4.1 work; this module does not invent it.

```text
CARGO_TARGET_DIR=/tmp/k230-rust-appearance-cargo cargo test --offline --test appearance_module
  PASS 8 host integration tests
rustfmt --edition 2021 --check src/appearance.rs tests/appearance_module.rs
  PASS
```

The tests exercise exact prepare/commit/rollback ACKs, idle repeated
rollback, full background and gradient preservation, fragmented and oversized
requests, wrong generation paths, malformed alpha, FIFO payload refusal,
intermediate background symlink escape refusal, and a prepared snapshot
remaining stable when a cache file changes before commit. No target cross-build,
actual Rust scene adoption, Wayland frame, physical panel, background decode,
or device performance result is claimed. OpenSpec theme tasks 2.2, 3.1/3.3,
4.1, and the physical gates remain open.

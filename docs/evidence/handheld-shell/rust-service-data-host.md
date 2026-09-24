# Rust shell service data: host checkpoint

Observed 2026-09-24 from base `cfc41aa1` in isolated branch
`implement/rust-service-data`. The new Rust module parses already-read JSON;
it is not yet linked into the production frontend. The frontend owner retains
`main.rs`, `render.rs`, `lib.rs`, Cargo/Nix, async transport, and presentation.

`parse_settings` validates the current `tools/device_settings.py status`
schema, preserving writable, read-only, action, and unavailable states. It
does not invent a battery or connectivity claim. `parse_history` validates
the `tools/notification_center.py` history schema, event count and priority,
and keeps the broker's privacy-filtered preview separate from full history.
It never derives a preview from possibly private history text. Input bounds
are 16 KiB for settings and 128 KiB/64 events for history.

```text
cd nix/rust-shell-client
CARGO_TARGET_DIR=/tmp/k230-rust-service-cargo cargo test --offline --test service_data_module
  PASS 4 host parser tests
rustfmt --edition 2021 --check src/service_data.rs tests/service_data_module.rs
  PASS
```

The follow-up worker runs trusted settings commands and connects to the
private notification socket on a dedicated thread. Its UI API uses only
nonblocking `try_submit` and `try_recv`; the queue holds at most eight
outstanding requests, coalesces duplicate refreshes, and returns one explicit
result per accepted request. Process and socket operations have total
deadlines, size bounds, fixed operation names, and narrow action arguments.
The socket requires a private owned directory, mode-0600 socket, and same-UID
peer credentials. This does not give the UI arbitrary command authority.

```text
cd nix/rust-shell-client
CARGO_TARGET_DIR=/tmp/k230-rust-service-cargo cargo test --offline --test service_data_module
  PASS 7 host tests, including private-socket history and slow-peer deadline
rustfmt --edition 2021 --check src/service_data.rs tests/service_data_module.rs
  PASS
```

The worker tests use host fakes. The module is not yet linked into the
production frontend; target cross-build, real shell rendering, and physical
panel interaction remain unverified.

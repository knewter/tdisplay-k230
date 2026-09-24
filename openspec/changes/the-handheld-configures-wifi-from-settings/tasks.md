## 1. Protected Wi-Fi service

- [x] 1.1 Implement bounded private broker protocol, peer identity and fixed error codes; prove malformed, oversized, unauthorized, timed-out and secret-redaction cases with `python3 -m unittest tests.test_wifi_settings_broker` (host proof only).
- [x] 1.2 Implement bounded scan/status parsing and saved/current identity without returning stored credentials; prove duplicate, malformed, unavailable, stale and empty synthetic responses with `python3 -m unittest tests.test_wifi_settings_broker` (host proof only).
- [x] 1.3 Implement open/WPA2 connection, confirmed-only atomic root-private persistence, and explicit Forget, preserving prior config on failure; prove synthetic service and permission/rollback cases with `python3 -m unittest tests.test_wifi_settings_broker` (host proof only).
- [ ] 1.4 Package and confine the broker alongside existing `k230-wifi.service` without changing the protected `LoadCredential` path; prove Nix unit values with `tools/test-k230-wifi-persistent-service.sh` and a narrow `nix build .#wifi-settings-broker` (build proof only).

## 2. Touch Settings client

- [x] 2.1 Add bounded typed asynchronous Wi-Fi scan/status/connect/forget worker responses with request IDs and secret-safe errors; prove stale replies, queue bounds and no-argv credential transport with `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml wifi_` (host proof only).
- [x] 2.2 Add Settings Network list, current/saved badges, empty/loading/error/retry and selection routes; prove touch routing and scroll/reversal with `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml wifi_` (host proof only).
- [x] 2.3 Add masked passphrase editor with integrated touch keyboard, correction/cancel and open-network skip; prove keyboard hit regions, masking and secret teardown with `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml wifi_` (host proof only).
- [ ] 2.4 Add Connect pending/result and explicit Forget confirmation, preserving selected context and rejecting stale responses; prove fake-broker host tests and paired Sway QEMU touch capture with `python3 tests/test_rust_wifi_settings_runtime.py` (QEMU proof only).
- [ ] 2.5 Cross-build the integrated shell and system closure using `nix build .#handheld-shell-rust` and `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel`; record output identity, without claiming deployment (build proof only).

## 3. Physical acceptance

- [ ] 3.1 Under the reserved board lock, verify real-glass scan, open/WPA2 selection, masked keyboard, connection, failure/retry and Forget; commit only redacted UI/console evidence under `docs/evidence/wifi-settings/` using the project's capture and console procedures (hardware proof only).
- [ ] 3.2 Reboot the board after accepted setup and verify automatic reconnect, then Forget and reboot again to verify no reconnect; record credential-free service state and file mode, never SSID/password/addresses, via `flock /tmp/k230-board.lock ./tools/console.py /dev/ttyACM0 --wait=3 '<sanitized fixed status probe>'` (hardware proof only).

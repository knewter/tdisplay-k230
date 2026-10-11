## 1. Contract and host tests
- [ ] 1.1 Add shared state IDs/copy keys and recovery mapping for loading, empty, stale, denied action, video Stop, EOF, cancelled in `nix/rust-shell-client`, without moving video/card lifecycle ownership. Host proof: `cargo test --manifest-path nix/rust-shell-client/Cargo.toml`.
- [ ] 1.2 Add test cases for each state asserting the named recovery action and that no raw path, GLib text, or secret is rendered. Host proof: `cargo test --manifest-path nix/rust-shell-client/Cargo.toml`.
## 2. Build
- [ ] 2.1 Build the client after builder coordination. Build proof (not board proof): `nix build .#handheld-shell-rust`.
## 3. Physical acceptance
- [ ] 3.1 Capture real-finger recovery/error readability after the image is deployed: `python3 tools/capture-feature.py recovery-routes --provenance real-touch --duration 30 --description 'Recovery routes for stale, denied, and ended states' --output-dir docs/evidence/recovery-routes`. Hardware proof; keep separate from host fixtures. Stays open until this capture exists.
